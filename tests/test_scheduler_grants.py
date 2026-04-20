from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from experiments.common import simulate_link_sequence
from utils.io import load_yaml
from utils.validators import deep_merge, validate_config


def _scheduler_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    base = load_yaml(root / "configs" / "default.yaml")
    override = load_yaml(root / "configs" / "scenario_scheduler_grant_replay.yaml")
    return validate_config(deep_merge(deepcopy(base), override))


def _scheduler_harq_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    base = load_yaml(root / "configs" / "default.yaml")
    override = load_yaml(root / "configs" / "scenario_p3_harq_scheduler_loop.yaml")
    return validate_config(deep_merge(deepcopy(base), override))


def test_scheduler_replays_configured_grant_sequence() -> None:
    result = simulate_link_sequence(_scheduler_config())
    schedule = result["sequence_summary"]["schedule_trace"]

    assert result["sequence_summary"]["scheduler_enabled"] is True
    assert [entry["grant_id"] for entry in schedule] == [100, 101, 100, 101]
    assert [entry["scheduled_modulation"] for entry in schedule] == ["QPSK", "16QAM", "QPSK", "16QAM"]
    assert [entry["scheduled_layers"] for entry in schedule] == [1, 2, 1, 2]
    assert [entry["scheduled_precoding_mode"] for entry in schedule] == ["identity", "dft", "identity", "dft"]


def test_scheduler_grant_is_exposed_in_each_slot_pipeline() -> None:
    result = simulate_link_sequence(_scheduler_config())

    for history_entry in result["slot_history"]:
        slot_result = history_entry["result"]
        assert slot_result["scheduled_grant"]["grant_source"] == "configured"
        assert slot_result["pipeline"][0]["stage"] == "DCI-like scheduling grant"


def test_scheduler_grants_drive_harq_process_ndi_and_rv() -> None:
    result = simulate_link_sequence(_scheduler_harq_config())
    summary = result["sequence_summary"]
    schedule = summary["schedule_trace"]
    harq = summary["harq_trace"]

    assert summary["scheduler_enabled"] is True
    assert summary["harq_enabled"] is True
    assert [entry["harq_process_id"] for entry in schedule] == [0, 0, 1, 1]
    assert [entry["harq_redundancy_version"] for entry in schedule] == [0, 2, 0, 2]
    assert [entry["process_id"] for entry in harq] == [0, 0, 1, 1]
    assert [entry["rv"] for entry in harq] == [0, 2, 0, 2]
    assert [entry["ndi"] for entry in harq] == [1, 1, 1, 1]
    assert [entry["new_data"] for entry in harq] == [True, False, True, False]
    assert [entry["soft_observations"] for entry in harq] == [1, 2, 1, 2]


def test_phy_pipeline_panel_shows_scheduler_timeline_stage() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    panel.set_result(simulate_link_sequence(_scheduler_config()))

    stage_keys = {stage["key"] for stage in panel.stages}
    assert "scheduler_timeline" in stage_keys
    scheduler_stage = next(stage for stage in panel.stages if stage["key"] == "scheduler_timeline")
    assert scheduler_stage["metrics"]["Current grant"] in {100, 101}
    panel.deleteLater()
    app.processEvents()
