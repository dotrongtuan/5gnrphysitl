from __future__ import annotations

import numpy as np

from phy.coding import NrLdpcInspiredCoder


def test_ldpc_inspired_coder_exposes_code_block_metadata() -> None:
    payload = np.arange(1024, dtype=np.uint8) % 2
    coder = NrLdpcInspiredCoder(
        target_rate=0.5,
        crc_type="crc16",
        seed=7,
        code_block_crc_type="crc8",
        max_code_block_payload_bits=320,
    )

    coded_bits, metadata = coder.encode(payload_bits=payload, target_length=2144, redundancy_version=0)

    assert coded_bits.size == 2144
    assert metadata.code_block_count > 1
    assert metadata.code_block_crc_type == "crc8"
    assert len(metadata.code_block_payload_lengths) == metadata.code_block_count
    assert len(metadata.code_block_with_crc_lengths) == metadata.code_block_count
    assert len(metadata.mother_block_lengths) == metadata.code_block_count
    assert len(metadata.code_block_interleavers) == metadata.code_block_count
    assert len(metadata.code_block_repetition_factors) == metadata.code_block_count
    assert metadata.transport_block_with_crc is not None
    assert sum(metadata.code_block_payload_lengths) == metadata.transport_block_with_crc.size
    assert sum(metadata.code_block_with_crc_lengths) > sum(metadata.code_block_payload_lengths)
    assert sum(metadata.mother_block_lengths) == metadata.mother_length


def test_ldpc_inspired_decode_trace_round_trips_segmented_payload() -> None:
    payload = np.arange(1024, dtype=np.uint8) % 2
    coder = NrLdpcInspiredCoder(
        target_rate=0.5,
        crc_type="crc16",
        seed=11,
        code_block_crc_type="crc8",
        max_code_block_payload_bits=320,
    )

    coded_bits, metadata = coder.encode(payload_bits=payload, target_length=2144, redundancy_version=0)
    llrs = np.where(coded_bits == 0, 4.0, -4.0)
    recovered_bits, crc_ok, trace = coder.decode_with_trace(llrs, metadata)

    assert crc_ok is True
    assert np.array_equal(recovered_bits, payload)
    assert len(trace.rate_recovered_blocks) == metadata.code_block_count
    assert len(trace.decoder_input_blocks) == metadata.code_block_count
    assert len(trace.recovered_code_blocks) == metadata.code_block_count
    assert len(trace.code_block_crc_ok) == metadata.code_block_count
    assert all(trace.code_block_crc_ok)
    assert trace.transport_block_with_crc_bits.size == metadata.transport_block_with_crc.size
