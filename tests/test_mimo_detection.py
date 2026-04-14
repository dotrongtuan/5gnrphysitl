from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from experiments.common import simulate_link
from utils.io import load_yaml
from utils.validators import validate_config


def _mimo_config(*, layers: int, ports: int, rx_antennas: int, detector: str, snr_db: float) -> dict:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = float(snr_db)
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True
    config["receiver"]["mimo_detector"] = detector
    config["spatial"]["num_layers"] = layers
    config["spatial"]["num_ports"] = ports
    config["spatial"]["num_tx_antennas"] = ports
    config["spatial"]["num_rx_antennas"] = rx_antennas
    config["precoding"]["mode"] = "dft"
    return config


def test_2x2_mimo_detector_runs_end_to_end() -> None:
    result = simulate_link(_mimo_config(layers=2, ports=2, rx_antennas=2, detector="mmse", snr_db=20.0))

    assert result["rx"].crc_ok is True
    assert result["rx"].channel_tensor.shape[:2] == (2, 2)
    assert result["rx"].effective_channel_tensor.shape[:2] == (2, 2)
    assert result["rx"].equalized_port_symbols.shape[0] == 2
    assert result["rx"].equalized_layer_symbols.shape[0] == 2


def test_4x4_mimo_detector_runs_end_to_end() -> None:
    result = simulate_link(_mimo_config(layers=4, ports=4, rx_antennas=4, detector="mmse", snr_db=24.0))

    assert result["rx"].crc_ok is True
    assert result["rx"].channel_tensor.shape[:2] == (4, 4)
    assert result["rx"].effective_channel_tensor.shape[:2] == (4, 4)
    assert result["rx"].equalized_port_symbols.shape[0] == 4
    assert result["rx"].equalized_layer_symbols.shape[0] == 4


def test_detector_choice_changes_observable_metrics() -> None:
    zf = simulate_link(_mimo_config(layers=2, ports=2, rx_antennas=2, detector="zf", snr_db=4.0))
    mmse = simulate_link(_mimo_config(layers=2, ports=2, rx_antennas=2, detector="mmse", snr_db=4.0))

    assert abs(zf["kpis"].evm - mmse["kpis"].evm) > 1e-9 or abs(zf["kpis"].ber - mmse["kpis"].ber) > 1e-12


def test_phy_pipeline_panel_shows_mimo_detection_stage() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    panel.set_result(simulate_link(_mimo_config(layers=2, ports=2, rx_antennas=2, detector="osic", snr_db=12.0)))

    stage_keys = {stage["key"] for stage in panel.stages}
    assert {"mimo_detection", "layer_recovery"}.issubset(stage_keys)
    detection_stage = next(stage for stage in panel.stages if stage["key"] == "mimo_detection")
    assert detection_stage["metrics"]["Detector"] == "osic"
    panel.deleteLater()
    app.processEvents()
