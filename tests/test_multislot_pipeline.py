from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from experiments.common import simulate_link_sequence
from utils.io import load_yaml
from utils.validators import validate_config


def _base_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    config = load_yaml(root / "configs" / "default.yaml")
    config = validate_config(config)
    config = deepcopy(config)
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = 18.0
    config["simulation"]["capture_slots"] = 3
    config["receiver"]["perfect_sync"] = False
    config["receiver"]["perfect_channel_estimation"] = False
    return config


def test_simulate_link_sequence_returns_multiple_slots() -> None:
    config = _base_config()
    result = simulate_link_sequence(config)

    assert result["captured_slots"] == 3
    assert len(result["slot_history"]) == 3
    assert [entry["timeline_index"] for entry in result["slot_history"]] == [0, 1, 2]
    assert [entry["slot_index"] for entry in result["slot_history"]] == [0, 1, 2]
    assert result["sequence_summary"]["captured_slots"] == 3
    assert result["kpis"].extra["captured_slots"] == 3.0


def test_phy_pipeline_panel_uses_multislot_scrubber() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    config = _base_config()
    config["simulation"]["capture_slots"] = 12
    result = simulate_link_sequence(config)
    panel.set_result(result)

    assert panel.frame_slider.maximum() == 1
    assert panel.slot_slider.maximum() == 9
    panel.frame_slider.setValue(1)
    panel.slot_slider.setValue(1)
    assert panel.current_slot_record is not None
    assert int(panel.current_slot_record["frame_index"]) == 1
    assert int(panel.current_slot_record["slot_index"]) == 1
    assert "Frame 1 / Slot 1" in panel.stage_title.text()
    panel.deleteLater()
    app.processEvents()


def test_phy_pipeline_playback_rolls_across_slots_and_frames() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    config = _base_config()
    config["simulation"]["capture_slots"] = 12
    result = simulate_link_sequence(config)
    panel.set_result(result)

    panel.frame_slider.setValue(0)
    panel.slot_slider.setValue(9)
    panel._set_current_stage(len(panel.stages) - 1)
    panel._advance_animation()

    assert panel.current_slot_record is not None
    assert int(panel.current_slot_record["frame_index"]) == 1
    assert int(panel.current_slot_record["slot_index"]) == 0
    assert panel.current_stage_index == 0

    panel.step_backward()
    assert int(panel.current_slot_record["frame_index"]) == 0
    assert int(panel.current_slot_record["slot_index"]) == 9
    assert panel.current_stage_index == len(panel.stages) - 1

    panel.deleteLater()
    app.processEvents()
