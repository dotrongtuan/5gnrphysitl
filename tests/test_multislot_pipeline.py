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
    assert result["pipeline_contract_version"] == 1
    assert result["pipeline"][0]["artifact_type"] == "bits"
    assert "input_shape" in result["pipeline"][0]
    assert "output_shape" in result["pipeline"][0]
    assert result["slot_context"]["slot_label"] == "Frame 0 / Slot 0"
    stage_names = [stage["stage"] for stage in result["pipeline"]]
    assert "TB CRC attachment" in stage_names
    assert "Code block segmentation + CB CRC" in stage_names
    assert "Remove CP" in stage_names
    assert "Resource element extraction" in stage_names
    assert "Rate recovery" in stage_names
    assert "Soft LLR before decoding" in stage_names
    rx = result["rx"]
    assert rx.cp_removed_tensor.shape[1] == config["numerology"]["symbols_per_slot"]
    assert rx.fft_bins_tensor.shape[2] == config["numerology"]["fft_size"]
    assert rx.re_data_positions.shape[0] == rx.re_data_symbols.shape[0]
    assert rx.rate_recovered_llrs.size == sum(result["tx"].metadata.coding_metadata.mother_block_lengths)
    assert rx.decoder_input_llrs.size == sum(result["tx"].metadata.coding_metadata.code_block_with_crc_lengths)
    assert len(rx.code_block_crc_ok) == result["tx"].metadata.coding_metadata.code_block_count


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
    assert panel.stages[0]["artifact_type"] == "bits"
    assert "Input shape" in panel.stages[0]["metrics"]
    stage_keys = {stage["key"] for stage in panel.stages}
    assert {"segmentation", "remove_cp", "re_extraction", "rate_recovery", "soft_llr"}.issubset(stage_keys)
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
