from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from experiments.common import simulate_link_sequence
from utils.io import load_yaml
from utils.validators import validate_config


def _downlink_control_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["link"]["direction"] = "downlink"
    config["link"]["channel_type"] = "control"
    config["simulation"]["capture_slots"] = 2
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = 28.0
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True
    return config


def test_simulate_downlink_control_sequence_uses_coreset_search_space() -> None:
    result = simulate_link_sequence(_downlink_control_config())

    assert result["captured_slots"] == 2
    assert result["tx"].metadata.direction == "downlink"
    assert result["tx"].metadata.channel_type == "control"
    assert result["tx"].metadata.mapping.positions.shape[0] > 0

    stage_names = [stage["stage"] for stage in result["pipeline"]]
    assert "CORESET / SearchSpace selection" in stage_names
    assert result["rx"].crc_ok is True


def test_phy_pipeline_panel_shows_coreset_stage_for_control() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    result = simulate_link_sequence(_downlink_control_config())
    panel.set_result(result)

    stage_titles = {str(stage["title"]).lower() for stage in panel.stages}
    assert "coreset / searchspace selection" in stage_titles
    panel.deleteLater()
    app.processEvents()


def test_dedicated_control_scenario_keeps_search_space_monitoring_active() -> None:
    config = _downlink_control_config()
    config["frame"]["search_space_period_slots"] = 2
    config["frame"]["search_space_slot_offset"] = 1
    config["frame"]["search_space_symbols"] = [1]

    result = simulate_link_sequence(config)
    slot0 = result["slot_history"][0]["result"]
    slot1 = result["slot_history"][1]["result"]

    assert slot0["tx"].metadata.procedure_state["search_space_active"] is True
    assert slot1["tx"].metadata.procedure_state["search_space_active"] is True
    assert slot0["tx"].metadata.procedure_state["search_space_symbols"] == [1]
    assert slot1["tx"].metadata.procedure_state["search_space_symbols"] == [1]
