from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import numpy as np

from experiments.common import simulate_link_sequence
from phy.harq import HarqProcessManager
from utils.io import load_yaml
from utils.validators import validate_config


def _harq_config(*, snr_db: float = -20.0, capture_slots: int = 4) -> dict:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["simulation"]["capture_slots"] = capture_slots
    config["transport_block"]["size_bits"] = 256
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = snr_db
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True
    config["csi"]["enabled"] = False
    config["csi"]["replay_feedback"] = False
    config["harq"]["enabled"] = True
    config["harq"]["process_count"] = 1
    config["harq"]["max_retransmissions"] = 3
    config["harq"]["rv_sequence"] = [0, 2, 3, 1]
    config["harq"]["soft_combining"] = True
    return config


def test_harq_manager_tracks_rv_ndi_and_soft_buffer() -> None:
    manager = HarqProcessManager(_harq_config())
    rng = np.random.default_rng(123)

    process, payload, first = manager.prepare_payload(
        timeline_index=0,
        payload_bits=None,
        payload_size_bits=16,
        rng=rng,
    )
    assert first["enabled"] is True
    assert first["rv"] == 0
    assert first["new_data"] is True
    first_combined = process.combine((np.ones(8),), soft_combining=True)
    process.complete_attempt(False)

    _, retransmission_payload, second = manager.prepare_payload(
        timeline_index=1,
        payload_bits=None,
        payload_size_bits=16,
        rng=rng,
    )
    assert second["rv"] == 2
    assert second["new_data"] is False
    assert np.array_equal(payload, retransmission_payload)
    second_combined = process.combine((np.ones(8),), soft_combining=True)
    assert np.allclose(second_combined[0], first_combined[0] + 1.0)


def test_harq_sequence_exposes_rv_trace_and_pipeline_stage() -> None:
    result = simulate_link_sequence(_harq_config())

    summary = result["sequence_summary"]
    assert summary["harq_enabled"] is True
    assert len(summary["harq_trace"]) == 4
    assert [entry["rv"] for entry in summary["harq_trace"]] == [0, 2, 3, 1]
    assert [entry["soft_observations"] for entry in summary["harq_trace"]] == [1, 2, 3, 4]

    second_slot_pipeline = result["slot_history"][1]["result"]["pipeline"]
    assert "HARQ soft combining" in {stage["stage"] for stage in second_slot_pipeline}


def test_harq_sequence_keeps_schedule_trace_in_sync() -> None:
    result = simulate_link_sequence(_harq_config())
    schedule_trace = result["sequence_summary"]["schedule_trace"]

    assert [entry["harq_process_id"] for entry in schedule_trace] == [0, 0, 0, 0]
    assert [entry["harq_redundancy_version"] for entry in schedule_trace] == [0, 2, 3, 1]


def test_phy_pipeline_panel_shows_harq_timeline_stage() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    panel.set_result(simulate_link_sequence(_harq_config()))

    stage_keys = {stage["key"] for stage in panel.stages}
    assert "harq_timeline" in stage_keys
    harq_stage = next(stage for stage in panel.stages if stage["key"] == "harq_timeline")
    assert harq_stage["metrics"]["Soft observations"] == 1
    panel.deleteLater()
    app.processEvents()
