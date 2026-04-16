from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np


def _int_to_bits(value: int, width: int) -> np.ndarray:
    return np.asarray([(int(value) >> shift) & 1 for shift in range(int(width) - 1, -1, -1)], dtype=np.uint8)


def _bits_to_int(bits: np.ndarray) -> int:
    value = 0
    for bit in np.asarray(bits, dtype=np.uint8).reshape(-1):
        value = (value << 1) | int(bit)
    return int(value)


@dataclass(slots=True)
class PbchSemanticPayload:
    payload_bits: np.ndarray
    higher_layer_bits: np.ndarray
    timing_bits: np.ndarray
    fields: Dict[str, Any]


def _scs_common_from_numerology(scs_khz: int) -> str:
    return "scs15or60" if int(scs_khz) in {15, 60} else "scs30or120"


def build_pbch_semantic_payload(
    *,
    broadcast_cfg: Dict[str, Any],
    numerology_scs_khz: int,
    slot_index: int,
    slots_per_frame: int,
    payload_length_bits: int,
    ssb_block_index: int,
) -> PbchSemanticPayload:
    payload_length_bits = int(payload_length_bits)
    if payload_length_bits < 32:
        raise ValueError("PBCH semantic baseline requires at least 32 payload bits.")

    system_frame_number_base = int(broadcast_cfg.get("system_frame_number", 0)) % 1024
    frame_index = int(slot_index) // max(int(slots_per_frame), 1)
    system_frame_number = (system_frame_number_base + frame_index) % 1024
    slot_in_frame = int(slot_index) % max(int(slots_per_frame), 1)
    half_frame_bit = int(broadcast_cfg.get("half_frame_bit", 1 if slot_in_frame >= max(int(slots_per_frame), 1) // 2 else 0)) & 1
    subcarrier_spacing_common = str(
        broadcast_cfg.get("subcarrier_spacing_common", _scs_common_from_numerology(numerology_scs_khz))
    )
    scs_flag = 0 if subcarrier_spacing_common == "scs15or60" else 1
    k_ssb = int(broadcast_cfg.get("k_ssb", 0)) % 32
    dmrs_type_a_position = str(broadcast_cfg.get("dmrs_type_a_position", "pos2"))
    dmrs_flag = 1 if dmrs_type_a_position == "pos3" else 0
    pdcch_config_sib1 = int(broadcast_cfg.get("pdcch_config_sib1", 0)) % 256
    cell_barred = 1 if bool(broadcast_cfg.get("cell_barred", False)) else 0
    intra_freq_reselection = 1 if bool(broadcast_cfg.get("intra_freq_reselection", True)) else 0
    spare = int(broadcast_cfg.get("spare", 0)) & 1
    ssb_index_lsb3 = int(ssb_block_index) & 0x7

    higher_layer_bits = np.concatenate(
        [
            _int_to_bits(system_frame_number >> 4, 6),
            np.asarray([scs_flag], dtype=np.uint8),
            _int_to_bits(k_ssb & 0xF, 4),
            np.asarray([dmrs_flag], dtype=np.uint8),
            _int_to_bits(pdcch_config_sib1, 8),
            np.asarray([cell_barred, intra_freq_reselection, spare, (k_ssb >> 4) & 1], dtype=np.uint8),
        ]
    )
    timing_bits = np.concatenate(
        [
            _int_to_bits(system_frame_number & 0xF, 4),
            np.asarray([half_frame_bit], dtype=np.uint8),
            _int_to_bits(ssb_index_lsb3, 3),
        ]
    )
    semantic_bits = np.concatenate([higher_layer_bits, timing_bits])
    payload_bits = np.zeros(payload_length_bits, dtype=np.uint8)
    payload_bits[: semantic_bits.size] = semantic_bits

    fields = {
        "system_frame_number": int(system_frame_number),
        "subcarrier_spacing_common": subcarrier_spacing_common,
        "k_ssb": int(k_ssb),
        "dmrs_type_a_position": dmrs_type_a_position,
        "pdcch_config_sib1": int(pdcch_config_sib1),
        "cell_barred": bool(cell_barred),
        "intra_freq_reselection": bool(intra_freq_reselection),
        "spare": int(spare),
        "half_frame_bit": int(half_frame_bit),
        "ssb_index_lsb3": int(ssb_index_lsb3),
        "semantic_payload_bits": int(semantic_bits.size),
        "higher_layer_bits": int(higher_layer_bits.size),
        "timing_bits": int(timing_bits.size),
    }
    return PbchSemanticPayload(
        payload_bits=payload_bits,
        higher_layer_bits=higher_layer_bits,
        timing_bits=timing_bits,
        fields=fields,
    )


def decode_pbch_semantic_payload(payload_bits: np.ndarray) -> Dict[str, Any]:
    bits = np.asarray(payload_bits, dtype=np.uint8).reshape(-1)
    if bits.size < 32:
        raise ValueError("PBCH semantic baseline expects at least 32 bits at RX.")

    higher_layer_bits = bits[:24].copy()
    timing_bits = bits[24:32].copy()

    system_frame_number_msb6 = _bits_to_int(higher_layer_bits[0:6])
    scs_flag = int(higher_layer_bits[6])
    k_ssb_lsb4 = _bits_to_int(higher_layer_bits[7:11])
    dmrs_flag = int(higher_layer_bits[11])
    pdcch_config_sib1 = _bits_to_int(higher_layer_bits[12:20])
    cell_barred = bool(int(higher_layer_bits[20]))
    intra_freq_reselection = bool(int(higher_layer_bits[21]))
    spare = int(higher_layer_bits[22])
    k_ssb_msb = int(higher_layer_bits[23])

    system_frame_number = (system_frame_number_msb6 << 4) | _bits_to_int(timing_bits[0:4])
    half_frame_bit = int(timing_bits[4])
    ssb_index_lsb3 = _bits_to_int(timing_bits[5:8])
    k_ssb = (k_ssb_msb << 4) | k_ssb_lsb4

    return {
        "system_frame_number": int(system_frame_number),
        "subcarrier_spacing_common": "scs15or60" if scs_flag == 0 else "scs30or120",
        "k_ssb": int(k_ssb),
        "dmrs_type_a_position": "pos2" if dmrs_flag == 0 else "pos3",
        "pdcch_config_sib1": int(pdcch_config_sib1),
        "cell_barred": bool(cell_barred),
        "intra_freq_reselection": bool(intra_freq_reselection),
        "spare": int(spare),
        "half_frame_bit": int(half_frame_bit),
        "ssb_index_lsb3": int(ssb_index_lsb3),
        "semantic_payload_bits": 32,
        "higher_layer_bits": 24,
        "timing_bits": 8,
        "higher_layer_payload": higher_layer_bits.copy(),
        "timing_payload": timing_bits.copy(),
    }
