from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import numpy as np

from experiments.common import simulate_link_sequence
from phy.frame_structure import build_default_allocation
from phy.numerology import NumerologyConfig
from phy.resource_grid import ResourceGrid
from phy.scheduler import apply_grant_to_config
from phy.vrb_mapping import build_vrb_prb_mapping
from utils.io import load_yaml
from utils.validators import deep_merge, validate_config


def test_non_interleaved_vrb_mapping_selects_contiguous_prbs() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {
        "vrb_mapping": {
            "enabled": True,
            "mapping_type": "non_interleaved",
            "bwp_start_prb": 4,
            "bwp_size_prb": 8,
            "start_vrb": 2,
            "num_vrbs": 3,
        }
    }

    mapping = build_vrb_prb_mapping(config, numerology)

    np.testing.assert_array_equal(mapping.vrb_indices, np.asarray([2, 3, 4]))
    np.testing.assert_array_equal(mapping.prb_indices, np.asarray([6, 7, 8]))
    assert mapping.allocated_subcarrier_count == 36
    assert int(mapping.subcarrier_indices[0]) == 72
    assert int(mapping.subcarrier_indices[-1]) == 107


def test_interleaved_vrb_mapping_permutates_prbs_for_teaching_view() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {
        "vrb_mapping": {
            "enabled": True,
            "mapping_type": "interleaved",
            "bwp_start_prb": 0,
            "bwp_size_prb": 8,
            "start_vrb": 0,
            "num_vrbs": 8,
            "interleaver_size": 2,
        }
    }

    mapping = build_vrb_prb_mapping(config, numerology)

    np.testing.assert_array_equal(mapping.vrb_indices, np.arange(8))
    np.testing.assert_array_equal(mapping.prb_indices, np.asarray([0, 4, 1, 5, 2, 6, 3, 7]))
    assert sorted(mapping.prb_indices.tolist()) == list(range(8))


def test_resource_grid_uses_vrb_prb_mapping_for_pdsch_and_dmrs() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {
        "frame": {"control_symbols": 2, "pdsch_start_symbol": 2, "dmrs_symbols": [3, 10]},
        "vrb_mapping": {
            "enabled": True,
            "mapping_type": "non_interleaved",
            "bwp_start_prb": 0,
            "bwp_size_prb": 24,
            "start_vrb": 4,
            "num_vrbs": 2,
        },
    }
    allocation = build_default_allocation(numerology, config)
    vrb_mapping = build_vrb_prb_mapping(config, numerology)
    grid = ResourceGrid(numerology, allocation, vrb_mapping=vrb_mapping)

    pdsch = grid.pdsch_positions()
    dmrs = grid.dmrs_positions()

    assert pdsch.shape[0] > 0
    assert dmrs.shape[0] > 0
    assert set(pdsch[:, 1].tolist()).issubset(set(range(48, 72)))
    assert set(dmrs[:, 1].tolist()).issubset(set(range(48, 72)))
    assert grid.mapping_for("data", bits_per_symbol=2, modulation="QPSK").vrb_mapping is vrb_mapping


def test_scheduler_grant_can_change_vrb_allocation_and_pipeline_exposes_stage() -> None:
    root = Path(__file__).resolve().parents[1]
    base = load_yaml(root / "configs" / "default.yaml")
    override = {
        "simulation": {"capture_slots": 1},
        "scheduler": {
            "enabled": True,
            "grants": [
                {
                    "grant_id": 700,
                    "channel_type": "data",
                    "modulation": "QPSK",
                    "start_vrb": 3,
                    "num_vrbs": 4,
                    "vrb_mapping_type": "non_interleaved",
                }
            ],
        },
        "reference_signals": {"enable_csi_rs": False, "enable_srs": False, "enable_ptrs": False},
    }
    config = validate_config(deep_merge(deepcopy(base), override))

    updated = apply_grant_to_config(config, config["scheduler"]["grants"][0])
    result = simulate_link_sequence(validate_config(updated))
    tx_meta = result["slot_history"][0]["result"]["tx"].metadata

    assert tx_meta.vrb_mapping.start_vrb == 3
    assert tx_meta.vrb_mapping.num_vrbs == 4
    assert result["slot_history"][0]["result"]["scheduled_grant"]["allocated_prb_count"] == 4
    stage_names = [stage["stage"] for stage in result["slot_history"][0]["result"]["pipeline"]]
    assert "VRB-to-PRB mapping" in stage_names


def test_phy_pipeline_panel_shows_vrb_mapping_stage() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        return

    from gui.phy_pipeline import PhyPipelinePanel

    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    app = QApplication.instance() or QApplication([])
    panel = PhyPipelinePanel()
    panel.set_result(simulate_link_sequence(config))

    stage = next(stage for stage in panel.stages if stage["key"] == "vrb_prb_mapping")
    assert stage["metrics"]["Mapping type"] == "non_interleaved"
    assert stage["metrics"]["Allocated PRBs"] == 24
    panel.deleteLater()
    app.processEvents()
