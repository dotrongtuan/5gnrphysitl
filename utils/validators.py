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

    coding = config.get("coding", {})
    if int(coding.get("code_block_payload_bits", 1)) < 1:
        raise ValueError("coding.code_block_payload_bits must be at least 1.")
    if str(coding.get("code_block_crc", "crc8")) not in {"crc8", "crc16"}:
        raise ValueError("coding.code_block_crc must be one of: crc8, crc16.")

    frame = config.get("frame", {})
    if int(frame.get("pusch_start_symbol", frame.get("pdsch_start_symbol", 0))) < 0:
        raise ValueError("frame.pusch_start_symbol must be non-negative.")

    return config
