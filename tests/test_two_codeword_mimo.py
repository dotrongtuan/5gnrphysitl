from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import numpy as np

from experiments.common import simulate_link
from utils.io import load_yaml
from utils.validators import validate_config


def _two_codeword_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = 40.0
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True
    config["receiver"]["mimo_detector"] = "mmse"
    config["spatial"]["num_codewords"] = 2
    config["spatial"]["num_layers"] = 2
    config["spatial"]["num_ports"] = 2
    config["spatial"]["num_tx_antennas"] = 2
    config["spatial"]["num_rx_antennas"] = 2
    config["precoding"]["mode"] = "type1_sp"
    config["precoding"]["pmi"] = "type1sp-r2-p0"
    config["csi"]["enabled"] = True
    config["csi"]["replay_feedback"] = True
    config["csi"]["max_rank"] = 2
    return config


def test_two_codeword_su_mimo_runs_end_to_end() -> None:
    result = simulate_link(_two_codeword_config())
    tx = result["tx"]
    rx = result["rx"]

    assert int(tx.metadata.spatial_layout.num_codewords) == 2
    assert len(tx.metadata.codeword_payload_bits) == 2
    assert len(tx.metadata.codeword_coding_metadata) == 2
    assert len(tx.metadata.codeword_modulation_symbols) == 2
    assert tx.metadata.codeword_layer_ranges == ((0, 1), (1, 2))
    assert len(rx.recovered_bits_by_codeword) == 2
    assert len(rx.codeword_crc_ok) == 2
    assert all(bool(status) for status in rx.codeword_crc_ok)
    assert rx.crc_ok is True
    np.testing.assert_array_equal(
        np.concatenate(rx.recovered_bits_by_codeword),
        tx.metadata.payload_bits,
    )


def test_pipeline_contract_exposes_codeword_partitioning() -> None:
    result = simulate_link(_two_codeword_config())

    stage_names = [stage["stage"] for stage in result["pipeline"]]
    assert "Codeword partitioning" in stage_names


def test_phy_pipeline_panel_shows_codeword_stage() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    panel.set_result(simulate_link(_two_codeword_config()))

    stage = next(stage for stage in panel.stages if stage["key"] == "codeword_split")
    assert stage["metrics"]["Codewords"] == 2
    assert "Layer ranges" in stage["metrics"]
    artifact_names = [artifact["name"] for artifact in stage["artifacts"]]
    assert "Per-codeword constellation" in artifact_names
    assert "Codeword summary" in artifact_names
    panel.deleteLater()
    app.processEvents()
