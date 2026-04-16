from __future__ import annotations

from phy.broadcast import build_pbch_semantic_payload, decode_pbch_semantic_payload


def test_pbch_semantic_payload_roundtrip() -> None:
    semantic = build_pbch_semantic_payload(
        broadcast_cfg={
            "system_frame_number": 513,
            "half_frame_bit": 1,
            "subcarrier_spacing_common": "scs30or120",
            "k_ssb": 19,
            "dmrs_type_a_position": "pos3",
            "pdcch_config_sib1": 21,
            "cell_barred": False,
            "intra_freq_reselection": True,
            "spare": 0,
        },
        numerology_scs_khz=30,
        slot_index=7,
        slots_per_frame=10,
        payload_length_bits=128,
        ssb_block_index=5,
    )

    decoded = decode_pbch_semantic_payload(semantic.payload_bits)

    assert decoded["system_frame_number"] == 513
    assert decoded["subcarrier_spacing_common"] == "scs30or120"
    assert decoded["k_ssb"] == 19
    assert decoded["dmrs_type_a_position"] == "pos3"
    assert decoded["pdcch_config_sib1"] == 21
    assert decoded["cell_barred"] is False
    assert decoded["intra_freq_reselection"] is True
    assert decoded["half_frame_bit"] == 1
    assert decoded["ssb_index_lsb3"] == (5 & 0x7)
