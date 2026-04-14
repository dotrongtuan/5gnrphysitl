from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import pandas as pd

from experiments.csi_loop_compare import run_experiment as run_csi_loop_compare
from experiments.common import simulate_link, simulate_link_sequence
from phy.precoding import build_type1_single_panel_codebook
from utils.io import load_yaml
from utils.validators import validate_config


def _csi_config(*, layers: int, ports: int, tx_antennas: int, rx_antennas: int, replay: bool, capture_slots: int) -> dict:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = 24.0
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True
    config["simulation"]["capture_slots"] = capture_slots
    config["spatial"]["num_layers"] = layers
    config["spatial"]["num_ports"] = ports
    config["spatial"]["num_tx_antennas"] = tx_antennas
    config["spatial"]["num_rx_antennas"] = rx_antennas
    config["precoding"]["mode"] = "dft"
    config["csi"]["enabled"] = True
    config["csi"]["replay_feedback"] = replay
    config["csi"]["max_rank"] = 4
    return config


def test_simulate_link_reports_csi_feedback() -> None:
    result = simulate_link(_csi_config(layers=2, ports=2, tx_antennas=2, rx_antennas=2, replay=False, capture_slots=1))

    feedback = result.get("csi_feedback")
    assert feedback is not None
    assert set(["cqi", "pmi", "ri", "rank_scores", "codebook_scores", "singular_values"]).issubset(feedback.keys())
    assert int(feedback["ri"]) >= 1
    assert str(feedback["pmi"]) in {"identity", "dft"}


def test_simulate_link_sequence_replays_csi_feedback_across_slots() -> None:
    result = simulate_link_sequence(
        _csi_config(layers=2, ports=2, tx_antennas=2, rx_antennas=2, replay=True, capture_slots=4)
    )

    summary = result["sequence_summary"]
    assert summary["csi_replay_enabled"] is True
    assert len(summary["csi_trace"]) == 4
    assert len(summary["schedule_trace"]) == 4
    assert int(summary["schedule_trace"][0]["scheduled_layers"]) == 2
    assert int(summary["schedule_trace"][1]["scheduled_layers"]) == int(summary["csi_trace"][0]["ri"])
    if str(summary["csi_trace"][0]["pmi"]).startswith("type1sp-"):
        assert str(summary["schedule_trace"][1]["scheduled_precoding_mode"]) == "type1_sp"
        assert str(summary["schedule_trace"][1]["scheduled_pmi"]) == str(summary["csi_trace"][0]["pmi"])
    else:
        assert str(summary["schedule_trace"][1]["scheduled_precoding_mode"]) == str(summary["csi_trace"][0]["pmi"])
    assert str(summary["schedule_trace"][1]["scheduled_modulation"]) == str(summary["csi_trace"][0]["modulation"])
    assert abs(float(summary["schedule_trace"][1]["scheduled_target_rate"]) - float(summary["csi_trace"][0]["target_rate"])) < 1e-9


def test_type1_single_panel_codebook_baseline_is_available() -> None:
    codebook = build_type1_single_panel_codebook(num_ports=2, num_layers=2)

    assert "type1sp-r2-p0" in codebook
    assert "type1sp-r2-p1" in codebook
    assert codebook["type1sp-r2-p0"].shape == (2, 2)


def test_csi_loop_compare_batch_outputs_open_and_closed_loop(tmp_path: Path) -> None:
    config = _csi_config(layers=2, ports=2, tx_antennas=2, rx_antennas=2, replay=True, capture_slots=4)
    config["experiments"]["snr_sweep_db"] = [8, 16]

    dataframe = run_csi_loop_compare(config=config, output_dir=tmp_path)

    assert isinstance(dataframe, pd.DataFrame)
    assert set(dataframe["loop_mode"]) == {"open_loop", "closed_loop"}
    assert {"latest_cqi", "latest_pmi", "latest_ri", "average_scheduled_target_rate"}.issubset(dataframe.columns)


def test_phy_pipeline_panel_shows_csi_feedback_stage() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    panel.set_result(simulate_link(_csi_config(layers=2, ports=2, tx_antennas=2, rx_antennas=2, replay=False, capture_slots=1)))

    stage_keys = {stage["key"] for stage in panel.stages}
    assert "csi_feedback" in stage_keys
    csi_stage = next(stage for stage in panel.stages if stage["key"] == "csi_feedback")
    assert {"CQI", "PMI", "RI"}.issubset(csi_stage["metrics"].keys())
    panel.deleteLater()
    app.processEvents()
