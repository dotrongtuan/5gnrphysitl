from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from experiments.common import simulate_link_sequence
from gui.phy_pipeline import PhyPipelinePanel
from utils.io import load_yaml
from utils.validators import validate_config


def _pbch_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["link"]["direction"] = "downlink"
    config["link"]["channel_type"] = "pbch"
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True
    config["simulation"]["capture_slots"] = 2
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = 28.0
    return config


def test_simulate_pbch_sequence_uses_ssb_region() -> None:
    result = simulate_link_sequence(_pbch_config())

    assert result["captured_slots"] == 2
    assert result["tx"].metadata.channel_type == "pbch"
    assert result["tx"].metadata.ssb["positions"].shape[0] > 0
    assert result["tx"].metadata.ssb["pss_positions"].shape[0] == 127
    assert result["tx"].metadata.ssb["sss_positions"].shape[0] == 127
    assert result["tx"].metadata.ssb["pbch_dmrs_positions"].shape[0] > 0
    assert result["tx"].metadata.mapping.positions.shape[0] > 0
    assert result["rx"].crc_ok is True
    assert result["rx"].detected_n_id_2 == result["tx"].metadata.ssb["n_id_2"]
    assert result["rx"].detected_n_id_1 == result["tx"].metadata.ssb["n_id_1"]
    assert result["rx"].detected_cell_id == result["tx"].metadata.ssb["physical_cell_id"]
    assert result["tx"].metadata.broadcast_payload_fields["system_frame_number"] == result["rx"].decoded_broadcast_payload["system_frame_number"]
    assert result["tx"].metadata.broadcast_payload_fields["k_ssb"] == result["rx"].decoded_broadcast_payload["k_ssb"]
    assert (
        result["tx"].metadata.broadcast_payload_fields["subcarrier_spacing_common"]
        == result["rx"].decoded_broadcast_payload["subcarrier_spacing_common"]
    )
    stage_names = [stage["stage"] for stage in result["pipeline"]]
    assert "SSB / PBCH broadcast layout" in stage_names
    assert "PSS / SSS cell search" in stage_names
    assert "PBCH / MIB semantic decode" in stage_names


def test_phy_pipeline_panel_shows_pbch_stage() -> None:
    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()

    result = simulate_link_sequence(_pbch_config())
    panel.set_result(result)

    stage_titles = [stage["title"].lower() for stage in panel.stages]
    assert "ssb / pbch broadcast layout" in stage_titles
