from __future__ import annotations

from copy import deepcopy


def deep_merge(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def validate_config(config: dict) -> dict:
    numerology = config.get("numerology", {})
    if int(numerology.get("n_rb", 1)) * 12 >= int(numerology.get("fft_size", 1)):
        raise ValueError("n_rb * 12 must stay below fft_size to keep guard bands and DC.")

    modulation = str(config.get("modulation", {}).get("scheme", "QPSK")).upper()
    if modulation not in {"QPSK", "16QAM", "64QAM", "256QAM"}:
        raise ValueError(f"Unsupported modulation scheme: {modulation}")

    direction = str(config.get("link", {}).get("direction", "downlink")).lower()
    if direction not in {"downlink", "uplink"}:
        raise ValueError(f"Unsupported link.direction: {direction}")

    spatial = config.get("spatial", {})
    for key in ("num_codewords", "num_layers", "num_ports", "num_tx_antennas", "num_rx_antennas"):
        if int(spatial.get(key, 1)) < 1:
            raise ValueError(f"spatial.{key} must be at least 1.")
    if int(spatial.get("num_codewords", 1)) > 2:
        raise ValueError("P2 baseline supports at most 2 codewords.")
    if int(spatial.get("num_codewords", 1)) > int(spatial.get("num_layers", 1)):
        raise ValueError("spatial.num_codewords must not exceed spatial.num_layers.")
    precoding = config.get("precoding", {})
    if str(precoding.get("mode", "identity")).lower() not in {"identity", "dft", "type1_sp"}:
        raise ValueError("precoding.mode must be one of: identity, dft, type1_sp.")
    csi = config.get("csi", {})
    if int(csi.get("max_rank", 1)) < 1:
        raise ValueError("csi.max_rank must be at least 1.")
    candidate_precoders = csi.get("candidate_precoders", ["identity", "dft"])
    if isinstance(candidate_precoders, str):
        candidate_precoders = [candidate_precoders]
    normalized_precoders = {str(mode).lower() for mode in candidate_precoders}
    if not normalized_precoders:
        raise ValueError("csi.candidate_precoders must not be empty.")
    if not normalized_precoders.issubset({"identity", "dft", "type1_sp"}):
        raise ValueError("csi.candidate_precoders must only contain: identity, dft, type1_sp.")

    coding = config.get("coding", {})
    if int(coding.get("code_block_payload_bits", 1)) < 1:
        raise ValueError("coding.code_block_payload_bits must be at least 1.")
    if str(coding.get("code_block_crc", "crc8")) not in {"crc8", "crc16"}:
        raise ValueError("coding.code_block_crc must be one of: crc8, crc16.")

    broadcast = config.get("broadcast", {})
    if not (0 <= int(broadcast.get("physical_cell_id", 0)) <= 1007):
        raise ValueError("broadcast.physical_cell_id must be in [0, 1007].")
    if int(broadcast.get("ssb_block_index", 0)) < 0:
        raise ValueError("broadcast.ssb_block_index must be non-negative.")
    if not (0 <= int(broadcast.get("system_frame_number", 0)) <= 1023):
        raise ValueError("broadcast.system_frame_number must be in [0, 1023].")
    if int(broadcast.get("half_frame_bit", 0)) not in {0, 1}:
        raise ValueError("broadcast.half_frame_bit must be 0 or 1.")
    if str(broadcast.get("subcarrier_spacing_common", "scs30or120")) not in {"scs15or60", "scs30or120"}:
        raise ValueError("broadcast.subcarrier_spacing_common must be 'scs15or60' or 'scs30or120'.")
    if not (0 <= int(broadcast.get("k_ssb", 0)) <= 31):
        raise ValueError("broadcast.k_ssb must be in [0, 31].")
    if str(broadcast.get("dmrs_type_a_position", "pos2")) not in {"pos2", "pos3"}:
        raise ValueError("broadcast.dmrs_type_a_position must be 'pos2' or 'pos3'.")
    if not (0 <= int(broadcast.get("pdcch_config_sib1", 0)) <= 255):
        raise ValueError("broadcast.pdcch_config_sib1 must be in [0, 255].")
    if int(broadcast.get("spare", 0)) not in {0, 1}:
        raise ValueError("broadcast.spare must be 0 or 1.")

    frame = config.get("frame", {})
    active_subcarriers = int(numerology.get("n_rb", 1)) * 12
    if int(frame.get("pusch_start_symbol", frame.get("pdsch_start_symbol", 0))) < 0:
        raise ValueError("frame.pusch_start_symbol must be non-negative.")
    if int(frame.get("prach_start_symbol", 0)) < 0:
        raise ValueError("frame.prach_start_symbol must be non-negative.")
    if int(frame.get("prach_symbol_count", 1)) < 1:
        raise ValueError("frame.prach_symbol_count must be at least 1.")
    if int(frame.get("prach_subcarriers", 12)) < 12:
        raise ValueError("frame.prach_subcarriers must be at least 12.")
    if int(frame.get("prach_subcarrier_offset", 0)) < 0:
        raise ValueError("frame.prach_subcarrier_offset must be non-negative.")
    if int(frame.get("rs_comb", 1)) < 1:
        raise ValueError("frame.rs_comb must be at least 1.")
    if int(frame.get("ptrs_subcarrier_offset", 0)) < 0:
        raise ValueError("frame.ptrs_subcarrier_offset must be non-negative.")
    if int(frame.get("ssb_symbol_count", 1)) < 1:
        raise ValueError("frame.ssb_symbol_count must be at least 1.")
    if int(frame.get("ssb_subcarriers", 12)) < 12:
        raise ValueError("frame.ssb_subcarriers must be at least 12.")
    if int(frame.get("ssb_subcarrier_offset", 0)) < 0:
        raise ValueError("frame.ssb_subcarrier_offset must be non-negative.")
    if int(frame.get("pbch_dmrs_subcarrier_offset", 0)) < 0:
        raise ValueError("frame.pbch_dmrs_subcarrier_offset must be non-negative.")
    if int(frame.get("coreset_symbol_count", 1)) < 1:
        raise ValueError("frame.coreset_symbol_count must be at least 1.")
    if int(frame.get("coreset_subcarriers", 12)) < 12:
        raise ValueError("frame.coreset_subcarriers must be at least 12.")
    if int(frame.get("coreset_subcarrier_offset", 0)) < 0:
        raise ValueError("frame.coreset_subcarrier_offset must be non-negative.")
    if int(frame.get("search_space_stride", 1)) < 1:
        raise ValueError("frame.search_space_stride must be at least 1.")
    if int(frame.get("search_space_offset", 0)) < 0:
        raise ValueError("frame.search_space_offset must be non-negative.")
    for key in (
        "prach_period_slots",
        "csi_rs_period_slots",
        "srs_period_slots",
        "ptrs_period_slots",
        "ssb_period_slots",
        "search_space_period_slots",
    ):
        if int(frame.get(key, 1)) < 1:
            raise ValueError(f"frame.{key} must be at least 1.")
    for key in (
        "prach_slot_offset",
        "csi_rs_slot_offset",
        "srs_slot_offset",
        "ptrs_slot_offset",
        "ssb_slot_offset",
        "search_space_slot_offset",
    ):
        if int(frame.get(key, 0)) < 0:
            raise ValueError(f"frame.{key} must be non-negative.")
    search_space_symbols = frame.get("search_space_symbols", [])
    if any(int(symbol) < 0 or int(symbol) >= int(numerology.get("symbols_per_slot", 14)) for symbol in search_space_symbols):
        raise ValueError("frame.search_space_symbols must contain valid OFDM symbol indices.")
    if int(frame.get("prach_subcarrier_offset", 0)) + int(frame.get("prach_subcarriers", 12)) > active_subcarriers:
        raise ValueError("frame.prach_subcarrier_offset + frame.prach_subcarriers exceeds the active bandwidth.")
    if int(frame.get("ssb_subcarrier_offset", 0)) + int(frame.get("ssb_subcarriers", 12)) > active_subcarriers:
        raise ValueError("frame.ssb_subcarrier_offset + frame.ssb_subcarriers exceeds the active bandwidth.")
    if int(frame.get("coreset_subcarrier_offset", 0)) + int(frame.get("coreset_subcarriers", 12)) > active_subcarriers:
        raise ValueError("frame.coreset_subcarrier_offset + frame.coreset_subcarriers exceeds the active bandwidth.")

    reference_signals = config.get("reference_signals", {})
    if int(reference_signals.get("sequence_seed", 0)) < 0:
        raise ValueError("reference_signals.sequence_seed must be non-negative.")

    receiver = config.get("receiver", {})
    if str(receiver.get("mimo_detector", "mmse")).lower() not in {"zf", "mmse", "osic"}:
        raise ValueError("receiver.mimo_detector must be one of: zf, mmse, osic.")

    return config
