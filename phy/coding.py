from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


CRC_DEFINITIONS = {
    "crc8": (8, 0x07),
    "crc16": (16, 0x1021),
}


def _int_to_bits(value: int, width: int) -> np.ndarray:
    return np.array([(value >> shift) & 1 for shift in range(width - 1, -1, -1)], dtype=np.uint8)


def crc_remainder(bits: np.ndarray, crc_type: str) -> np.ndarray:
    width, polynomial = CRC_DEFINITIONS[crc_type]
    register = 0
    mask = (1 << width) - 1
    padded = np.concatenate([bits.astype(np.uint8), np.zeros(width, dtype=np.uint8)])
    for bit in padded:
        msb = (register >> (width - 1)) & 1
        register = ((register << 1) & mask) | int(bit)
        if msb:
            register ^= polynomial
    return _int_to_bits(register, width)


def attach_crc(bits: np.ndarray, crc_type: str) -> np.ndarray:
    return np.concatenate([bits.astype(np.uint8), crc_remainder(bits, crc_type)])


def check_crc(bits_with_crc: np.ndarray, crc_type: str) -> Tuple[np.ndarray, bool]:
    width, _ = CRC_DEFINITIONS[crc_type]
    payload = bits_with_crc[:-width]
    remainder = bits_with_crc[-width:]
    expected = crc_remainder(payload, crc_type)
    return payload, bool(np.array_equal(remainder, expected))


def _circular_rate_match(bits: np.ndarray, target_length: int, rv: int) -> np.ndarray:
    if bits.size == 0:
        return bits
    start = (rv * max(bits.size // 4, 1)) % bits.size
    indices = (np.arange(target_length) + start) % bits.size
    return bits[indices]


def _circular_rate_recover(llrs: np.ndarray, mother_length: int, rv: int) -> np.ndarray:
    if mother_length == 0:
        return np.array([], dtype=np.float64)
    start = (rv * max(mother_length // 4, 1)) % mother_length
    recovered = np.zeros(mother_length, dtype=np.float64)
    indices = (np.arange(llrs.size) + start) % mother_length
    np.add.at(recovered, indices, llrs)
    return recovered


def _split_by_lengths(values: np.ndarray, lengths: Tuple[int, ...]) -> tuple[np.ndarray, ...]:
    array = np.asarray(values)
    parts: list[np.ndarray] = []
    start = 0
    for length in lengths:
        end = start + int(length)
        parts.append(array[start:end].copy())
        start = end
    return tuple(parts)


def _segment_transport_block(bits_with_crc: np.ndarray, max_payload_bits: int) -> tuple[np.ndarray, ...]:
    block_payload_limit = max(1, int(max_payload_bits))
    return tuple(
        np.asarray(bits_with_crc[start : start + block_payload_limit], dtype=np.uint8).copy()
        for start in range(0, int(bits_with_crc.size), block_payload_limit)
    )


def rate_recover_llrs(llrs: np.ndarray, metadata: "CodingMetadata") -> np.ndarray:
    return _circular_rate_recover(
        llrs=np.asarray(llrs, dtype=np.float64),
        mother_length=int(metadata.mother_length),
        rv=int(metadata.redundancy_version),
    )


def _next_power_of_two(value: int) -> int:
    return 1 << max(1, int(np.ceil(np.log2(max(2, value)))))


def _polar_weight(index: int, n_bits: int) -> float:
    beta = 2 ** 0.25
    return sum(((index >> bit) & 1) * (beta**bit) for bit in range(n_bits))


def _reliability_order(length: int) -> np.ndarray:
    n_bits = int(np.log2(length))
    scores = np.array([_polar_weight(index, n_bits) for index in range(length)])
    return np.argsort(scores)


def _polar_transform(u: np.ndarray) -> np.ndarray:
    x = u.copy()
    step = 1
    while step < x.size:
        for start in range(0, x.size, 2 * step):
            left = slice(start, start + step)
            right = slice(start + step, start + 2 * step)
            x[left] ^= x[right]
        step *= 2
    return x


def _f_function(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.sign(a) * np.sign(b) * np.minimum(np.abs(a), np.abs(b))


def _g_function(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    return b + (1.0 - 2.0 * c.astype(np.float64)) * a


def _sc_decode(llr: np.ndarray, frozen: np.ndarray) -> np.ndarray:
    if llr.size == 1:
        if frozen[0]:
            return np.array([0], dtype=np.uint8)
        return np.array([0 if llr[0] >= 0 else 1], dtype=np.uint8)

    half = llr.size // 2
    left = _sc_decode(_f_function(llr[:half], llr[half:]), frozen[:half])
    right = _sc_decode(_g_function(llr[:half], llr[half:], left), frozen[half:])
    return np.concatenate([left ^ right, right]).astype(np.uint8)


@dataclass(slots=True)
class CodingMetadata:
    channel_type: str
    crc_type: str
    payload_length: int
    rate_matched_length: int
    mother_length: int
    redundancy_version: int
    interleaver: np.ndarray | None = None
    repetition_factor: int = 1
    polar_length: int | None = None
    info_positions: np.ndarray | None = None
    tb_crc_width: int = 0
    code_block_crc_type: str | None = None
    code_block_count: int = 1
    code_block_payload_lengths: tuple[int, ...] = ()
    code_block_with_crc_lengths: tuple[int, ...] = ()
    mother_block_lengths: tuple[int, ...] = ()
    code_block_interleavers: tuple[np.ndarray, ...] = ()
    code_block_repetition_factors: tuple[int, ...] = ()
    transport_block_with_crc: np.ndarray | None = None
    code_block_payloads: tuple[np.ndarray, ...] = ()
    code_blocks_with_crc: tuple[np.ndarray, ...] = ()
    mother_code_blocks: tuple[np.ndarray, ...] = ()


@dataclass(slots=True)
class DecodingTrace:
    rate_recovered_blocks: tuple[np.ndarray, ...]
    decoder_input_blocks: tuple[np.ndarray, ...]
    recovered_code_blocks: tuple[np.ndarray, ...]
    code_block_crc_ok: tuple[bool, ...]
    transport_block_with_crc_bits: np.ndarray


class NrLdpcInspiredCoder:
    """Simplified rate-compatible data-channel coder.

    This is not a standards-compliant LDPC implementation. It preserves the
    processing stages expected in an NR-like PHY chain.
    """

    def __init__(
        self,
        target_rate: float = 0.5,
        crc_type: str = "crc16",
        seed: int = 0,
        code_block_crc_type: str = "crc8",
        max_code_block_payload_bits: int = 320,
    ) -> None:
        self.target_rate = float(target_rate)
        self.crc_type = crc_type
        self.seed = int(seed)
        self.code_block_crc_type = str(code_block_crc_type)
        self.max_code_block_payload_bits = int(max_code_block_payload_bits)

    def encode(
        self,
        payload_bits: np.ndarray,
        target_length: int,
        redundancy_version: int = 0,
    ) -> Tuple[np.ndarray, CodingMetadata]:
        payload_crc = attach_crc(np.asarray(payload_bits, dtype=np.uint8), self.crc_type)
        code_block_payloads = _segment_transport_block(payload_crc, self.max_code_block_payload_bits)
        use_code_block_crc = len(code_block_payloads) > 1
        code_blocks_with_crc = tuple(
            attach_crc(block, self.code_block_crc_type) if use_code_block_crc else np.asarray(block, dtype=np.uint8).copy()
            for block in code_block_payloads
        )

        repetition_factor = max(2, int(np.ceil(1.0 / max(self.target_rate, 1e-3))))
        mother_code_blocks = []
        block_interleavers = []
        rng = np.random.default_rng(self.seed + payload_crc.size + redundancy_version)
        for block_index, code_block in enumerate(code_blocks_with_crc):
            mother_block = np.tile(code_block, repetition_factor)
            interleaver = rng.permutation(mother_block.size)
            mother_code_blocks.append(mother_block[interleaver])
            block_interleavers.append(interleaver)

        mother = np.concatenate(mother_code_blocks) if mother_code_blocks else np.array([], dtype=np.uint8)
        interleaved = mother.copy()
        interleaver = np.arange(mother.size, dtype=int)
        rate_matched = _circular_rate_match(interleaved, target_length=target_length, rv=redundancy_version)
        metadata = CodingMetadata(
            channel_type="data",
            crc_type=self.crc_type,
            payload_length=payload_bits.size,
            rate_matched_length=target_length,
            mother_length=mother.size,
            redundancy_version=redundancy_version,
            interleaver=interleaver,
            repetition_factor=repetition_factor,
            tb_crc_width=CRC_DEFINITIONS[self.crc_type][0],
            code_block_crc_type=self.code_block_crc_type if use_code_block_crc else None,
            code_block_count=len(code_block_payloads),
            code_block_payload_lengths=tuple(int(block.size) for block in code_block_payloads),
            code_block_with_crc_lengths=tuple(int(block.size) for block in code_blocks_with_crc),
            mother_block_lengths=tuple(int(block.size) for block in mother_code_blocks),
            code_block_interleavers=tuple(block_interleavers),
            code_block_repetition_factors=tuple(repetition_factor for _ in code_block_payloads),
            transport_block_with_crc=payload_crc.copy(),
            code_block_payloads=tuple(block.copy() for block in code_block_payloads),
            code_blocks_with_crc=tuple(block.copy() for block in code_blocks_with_crc),
            mother_code_blocks=tuple(block.copy() for block in mother_code_blocks),
        )
        return rate_matched.astype(np.uint8), metadata

    def decode(self, llrs: np.ndarray, metadata: CodingMetadata) -> Tuple[np.ndarray, bool]:
        payload, crc_ok, _ = self.decode_with_trace(llrs, metadata)
        return payload, crc_ok

    def decode_with_trace(self, llrs: np.ndarray, metadata: CodingMetadata) -> tuple[np.ndarray, bool, DecodingTrace]:
        recovered = rate_recover_llrs(llrs, metadata)
        recovered_blocks = _split_by_lengths(recovered, metadata.mother_block_lengths)
        decoder_input_blocks = []
        recovered_code_blocks = []
        code_block_crc_ok = []
        payload_parts = []

        for block_index, recovered_block in enumerate(recovered_blocks):
            interleaver = (
                metadata.code_block_interleavers[block_index]
                if block_index < len(metadata.code_block_interleavers)
                else np.arange(recovered_block.size)
            )
            deinterleaved = np.zeros_like(recovered_block)
            deinterleaved[np.asarray(interleaver, dtype=int)] = recovered_block

            repetition_factor = (
                int(metadata.code_block_repetition_factors[block_index])
                if block_index < len(metadata.code_block_repetition_factors)
                else int(metadata.repetition_factor)
            )
            decoder_input = deinterleaved.reshape(repetition_factor, -1).sum(axis=0)
            hard = (decoder_input < 0).astype(np.uint8)
            if metadata.code_block_crc_type:
                block_payload, block_crc_ok = check_crc(hard, metadata.code_block_crc_type)
            else:
                block_payload = hard
                block_crc_ok = True

            expected_payload_length = (
                int(metadata.code_block_payload_lengths[block_index])
                if block_index < len(metadata.code_block_payload_lengths)
                else int(block_payload.size)
            )
            decoder_input_blocks.append(decoder_input.copy())
            recovered_code_blocks.append(block_payload[:expected_payload_length].copy())
            code_block_crc_ok.append(bool(block_crc_ok))
            payload_parts.append(block_payload[:expected_payload_length].copy())

        transport_block_with_crc = (
            np.concatenate(payload_parts) if payload_parts else np.array([], dtype=np.uint8)
        ).astype(np.uint8)
        payload, tb_crc_ok = check_crc(transport_block_with_crc, metadata.crc_type)
        crc_ok = bool(tb_crc_ok and all(code_block_crc_ok))
        trace = DecodingTrace(
            rate_recovered_blocks=tuple(block.copy() for block in recovered_blocks),
            decoder_input_blocks=tuple(block.copy() for block in decoder_input_blocks),
            recovered_code_blocks=tuple(block.copy() for block in recovered_code_blocks),
            code_block_crc_ok=tuple(bool(status) for status in code_block_crc_ok),
            transport_block_with_crc_bits=transport_block_with_crc.copy(),
        )
        return payload[: metadata.payload_length], crc_ok, trace


class PolarLikeControlCoder:
    """Small-block control-channel coder using a simplified polar transform."""

    def __init__(self, target_rate: float = 0.25, crc_type: str = "crc8") -> None:
        self.target_rate = float(target_rate)
        self.crc_type = crc_type

    def encode(
        self,
        payload_bits: np.ndarray,
        target_length: int,
        redundancy_version: int = 0,
    ) -> Tuple[np.ndarray, CodingMetadata]:
        payload_crc = attach_crc(np.asarray(payload_bits, dtype=np.uint8), self.crc_type)
        polar_length = _next_power_of_two(max(payload_crc.size, int(np.ceil(payload_crc.size / max(self.target_rate, 1e-3)))))
        reliability = _reliability_order(polar_length)
        info_positions = np.sort(reliability[-payload_crc.size :])
        u = np.zeros(polar_length, dtype=np.uint8)
        u[info_positions] = payload_crc
        mother = _polar_transform(u)
        rate_matched = _circular_rate_match(mother, target_length=target_length, rv=redundancy_version)
        metadata = CodingMetadata(
            channel_type="control",
            crc_type=self.crc_type,
            payload_length=payload_bits.size,
            rate_matched_length=target_length,
            mother_length=mother.size,
            redundancy_version=redundancy_version,
            polar_length=polar_length,
            info_positions=info_positions,
            tb_crc_width=CRC_DEFINITIONS[self.crc_type][0],
            code_block_crc_type=None,
            code_block_count=1,
            code_block_payload_lengths=(int(payload_crc.size),),
            code_block_with_crc_lengths=(int(payload_crc.size),),
            mother_block_lengths=(int(mother.size),),
            code_block_interleavers=(np.arange(mother.size, dtype=int),),
            code_block_repetition_factors=(1,),
            transport_block_with_crc=payload_crc.copy(),
            code_block_payloads=(payload_crc.copy(),),
            code_blocks_with_crc=(payload_crc.copy(),),
            mother_code_blocks=(mother.copy(),),
        )
        return rate_matched.astype(np.uint8), metadata

    def decode(self, llrs: np.ndarray, metadata: CodingMetadata) -> Tuple[np.ndarray, bool]:
        payload, crc_ok, _ = self.decode_with_trace(llrs, metadata)
        return payload, crc_ok

    def decode_with_trace(self, llrs: np.ndarray, metadata: CodingMetadata) -> tuple[np.ndarray, bool, DecodingTrace]:
        recovered = rate_recover_llrs(llrs, metadata)
        assert metadata.polar_length is not None
        assert metadata.info_positions is not None
        frozen = np.ones(metadata.polar_length, dtype=bool)
        frozen[metadata.info_positions] = False
        u_hat = _sc_decode(recovered, frozen)
        payload_crc = u_hat[metadata.info_positions]
        payload, crc_ok = check_crc(payload_crc, metadata.crc_type)
        trace = DecodingTrace(
            rate_recovered_blocks=(recovered.copy(),),
            decoder_input_blocks=(recovered.copy(),),
            recovered_code_blocks=(payload_crc.copy(),),
            code_block_crc_ok=(bool(crc_ok),),
            transport_block_with_crc_bits=payload_crc.copy(),
        )
        return payload[: metadata.payload_length], crc_ok, trace


def build_channel_coder(channel_type: str, config: Dict) -> object:
    coding_cfg = config.get("coding", {})
    if channel_type.lower() in {"control", "pdcch", "pbch"}:
        return PolarLikeControlCoder(
            target_rate=float(coding_cfg.get("control_rate", 0.25)),
            crc_type=str(coding_cfg.get("control_crc", "crc8")),
        )
    return NrLdpcInspiredCoder(
        target_rate=float(coding_cfg.get("target_rate", 0.5)),
        crc_type=str(coding_cfg.get("crc", "crc16")),
        seed=int(config.get("simulation", {}).get("seed", 0)),
        code_block_crc_type=str(coding_cfg.get("code_block_crc", "crc8")),
        max_code_block_payload_bits=int(coding_cfg.get("code_block_payload_bits", 320)),
    )
