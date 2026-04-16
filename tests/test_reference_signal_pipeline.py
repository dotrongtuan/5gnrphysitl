from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from experiments.common import simulate_link_sequence
from utils.io import load_yaml
from utils.validators import validate_config


def _base_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    return deepcopy(config)


def test_downlink_baseline_exposes_csi_rs() -> None:
    config = _base_config()
    config["link"]["direction"] = "downlink"
    config["link"]["channel_type"] = "data"
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True

    result = simulate_link_sequence(config)

    assert result["tx"].metadata.csi_rs["positions"].shape[0] > 0
    assert result["tx"].metadata.ptrs["positions"].shape[0] > 0
    assert result["tx"].metadata.srs["positions"].shape[0] == 0
    assert result["rx"].re_csi_rs_symbols.size == result["tx"].metadata.csi_rs["symbols"].size
    assert result["rx"].re_ptrs_symbols.size == result["tx"].metadata.ptrs["symbols"].size
    stage_names = [stage["stage"] for stage in result["pipeline"]]
    assert "CSI-RS insertion" in stage_names
    assert "CSI-RS extraction" in stage_names
    assert "PT-RS insertion" in stage_names
    assert "PT-RS extraction" in stage_names


def test_uplink_baseline_exposes_srs() -> None:
    config = _base_config()
    config["link"]["direction"] = "uplink"
    config["link"]["channel_type"] = "data"
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True

    result = simulate_link_sequence(config)

    assert result["tx"].metadata.srs["positions"].shape[0] > 0
    assert result["tx"].metadata.ptrs["positions"].shape[0] > 0
    assert result["tx"].metadata.csi_rs["positions"].shape[0] == 0
    assert result["rx"].re_srs_symbols.size == result["tx"].metadata.srs["symbols"].size
    assert result["rx"].re_ptrs_symbols.size == result["tx"].metadata.ptrs["symbols"].size
    stage_names = [stage["stage"] for stage in result["pipeline"]]
    assert "SRS insertion" in stage_names
    assert "SRS extraction" in stage_names
    assert "PT-RS insertion" in stage_names
    assert "PT-RS extraction" in stage_names


def test_reference_signal_periodicity_changes_visibility_across_slots() -> None:
    config = _base_config()
    config["link"]["direction"] = "downlink"
    config["link"]["channel_type"] = "data"
    config["simulation"]["capture_slots"] = 2
    config["frame"]["csi_rs_period_slots"] = 2
    config["frame"]["csi_rs_slot_offset"] = 1
    config["frame"]["ptrs_period_slots"] = 2
    config["frame"]["ptrs_slot_offset"] = 1
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True

    result = simulate_link_sequence(config)

    slot0 = result["slot_history"][0]["result"]
    slot1 = result["slot_history"][1]["result"]
    assert slot0["tx"].metadata.csi_rs["positions"].shape[0] == 0
    assert slot1["tx"].metadata.csi_rs["positions"].shape[0] > 0
    assert slot0["tx"].metadata.ptrs["positions"].shape[0] == 0
    assert slot1["tx"].metadata.ptrs["positions"].shape[0] > 0
