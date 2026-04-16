from __future__ import annotations

import numpy as np

from phy.frame_structure import build_default_allocation
from phy.numerology import NumerologyConfig
from phy.resource_grid import ResourceGrid
from phy.types import SpatialLayout


def test_resource_grid_positions_are_non_empty() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {"frame": {"control_symbols": 2, "pdsch_start_symbol": 2, "pusch_start_symbol": 2, "dmrs_symbols": [3, 10]}}
    allocation = build_default_allocation(numerology, config)
    grid = ResourceGrid(numerology, allocation)
    assert grid.pdcch_positions().shape[0] > 0
    assert grid.coreset_positions().shape[0] > 0
    assert grid.search_space_positions().shape[0] > 0
    assert grid.pdcch_positions().shape[0] <= grid.coreset_positions().shape[0]
    assert grid.pdsch_positions().shape[0] > 0
    assert grid.pusch_positions().shape[0] > 0
    assert grid.pucch_positions().shape[0] > 0
    assert grid.prach_positions().shape[0] > 0
    assert grid.csi_rs_positions().shape[0] > 0
    assert grid.srs_positions().shape[0] > 0
    assert grid.ptrs_positions().shape[0] > 0
    assert grid.ssb_positions().shape[0] > 0
    assert grid.pbch_positions().shape[0] > 0
    assert grid.pbch_dmrs_positions().shape[0] > 0
    assert grid.dmrs_positions().shape[0] > 0
    assert grid.pss_positions().shape[0] == 127
    assert grid.sss_positions().shape[0] == 127


def test_resource_grid_exposes_tensor_views_and_preserves_legacy_grid() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {"frame": {"control_symbols": 2, "pdsch_start_symbol": 2, "pusch_start_symbol": 2, "dmrs_symbols": [3, 10]}}
    allocation = build_default_allocation(numerology, config)
    layout = SpatialLayout(num_layers=2, num_ports=2, num_rx_antennas=2)
    grid = ResourceGrid(numerology, allocation, spatial_layout=layout)

    assert grid.layer_grid.shape == (2, numerology.symbols_per_slot, numerology.active_subcarriers)
    assert grid.port_grid.shape == (2, numerology.symbols_per_slot, numerology.active_subcarriers)
    assert grid.rx_grid_tensor.shape == (2, numerology.symbols_per_slot, numerology.active_subcarriers)
    assert grid.shape == (numerology.symbols_per_slot, numerology.active_subcarriers)

    positions = np.asarray([[2, 4], [2, 5], [2, 6]], dtype=int)
    symbols = np.asarray([1 + 1j, 2 + 2j, 3 + 3j], dtype=np.complex128)
    grid.map_symbols(symbols, positions, layer=1, port=1)

    np.testing.assert_allclose(grid.layer_view(1)[positions[:, 0], positions[:, 1]], symbols)
    np.testing.assert_allclose(grid.port_view(1)[positions[:, 0], positions[:, 1]], symbols)

    legacy_symbols = np.asarray([4 + 0j, 5 + 0j], dtype=np.complex128)
    legacy_positions = np.asarray([[0, 1], [0, 2]], dtype=int)
    grid.map_symbols(legacy_symbols, legacy_positions)
    np.testing.assert_allclose(grid.grid[legacy_positions[:, 0], legacy_positions[:, 1]], legacy_symbols)
    np.testing.assert_allclose(grid.layer_view(0)[legacy_positions[:, 0], legacy_positions[:, 1]], legacy_symbols)
    np.testing.assert_allclose(grid.port_view(0)[legacy_positions[:, 0], legacy_positions[:, 1]], legacy_symbols)

    specs = grid.tensor_view_specs_as_dict()
    assert specs["layer_grid"]["shape"] == [2, numerology.symbols_per_slot, numerology.active_subcarriers]
    assert specs["port_grid"]["shape"] == [2, numerology.symbols_per_slot, numerology.active_subcarriers]
    assert specs["rx_grid_tensor"]["shape"] == [2, numerology.symbols_per_slot, numerology.active_subcarriers]

    masks = grid.re_masks()
    assert set(masks) == {"control", "coreset", "search_space", "dmrs", "data", "prach", "csi_rs", "srs", "ptrs", "ssb"}
    assert masks["control"].shape == grid.shape
    assert masks["coreset"].shape == grid.shape
    assert masks["search_space"].shape == grid.shape
    assert masks["dmrs"].shape == grid.shape
    assert masks["data"].shape == grid.shape
    assert masks["prach"].shape == grid.shape
    assert masks["csi_rs"].shape == grid.shape
    assert masks["srs"].shape == grid.shape
    assert masks["ptrs"].shape == grid.shape
    assert masks["ssb"].shape == grid.shape
    assert np.sum(masks["search_space"]) <= np.sum(masks["coreset"])
    assert np.sum(masks["ptrs"]) > 0
    assert np.sum(masks["ssb"]) > 0


def test_resource_grid_supports_slot_aware_procedure_scheduling_and_offsets() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {
        "frame": {
            "control_symbols": 2,
            "pdsch_start_symbol": 2,
            "pusch_start_symbol": 2,
            "dmrs_symbols": [3, 10],
            "prach_start_symbol": 1,
            "prach_subcarriers": 24,
            "prach_subcarrier_offset": 36,
            "prach_period_slots": 4,
            "prach_slot_offset": 1,
            "coreset_start_symbol": 0,
            "coreset_symbol_count": 2,
            "coreset_subcarriers": 24,
            "coreset_subcarrier_offset": 12,
            "search_space_symbols": [1],
            "search_space_period_slots": 3,
            "search_space_slot_offset": 1,
            "csi_rs_symbols": [12],
            "csi_rs_period_slots": 2,
            "csi_rs_slot_offset": 1,
            "srs_symbols": [13],
            "srs_period_slots": 2,
            "srs_slot_offset": 1,
            "ptrs_symbols": [6],
            "ptrs_period_slots": 5,
            "ptrs_slot_offset": 2,
            "ssb_start_symbol": 0,
            "ssb_symbol_count": 4,
            "ssb_subcarriers": 120,
            "ssb_subcarrier_offset": 48,
            "ssb_period_slots": 2,
            "ssb_slot_offset": 1,
        },
        "reference_signals": {"enable_csi_rs": True, "enable_srs": True, "enable_ptrs": True},
    }
    allocation = build_default_allocation(numerology, config)

    inactive_grid = ResourceGrid(numerology, allocation, slot_index=0)
    active_grid = ResourceGrid(numerology, allocation, slot_index=1)

    assert inactive_grid.csi_rs_positions().shape[0] == 0
    assert active_grid.csi_rs_positions().shape[0] > 0
    assert inactive_grid.srs_positions().shape[0] == 0
    assert active_grid.srs_positions().shape[0] > 0
    assert inactive_grid.ssb_positions().shape[0] == 0
    assert active_grid.ssb_positions().shape[0] > 0
    assert inactive_grid.prach_positions().shape[0] == 0
    assert active_grid.prach_positions().shape[0] > 0
    assert inactive_grid.search_space_positions().shape[0] == 0
    assert active_grid.search_space_positions().shape[0] > 0

    coreset_positions = active_grid.coreset_positions()
    assert np.min(coreset_positions[:, 1]) == 12
    assert set(active_grid.search_space_positions()[:, 0].tolist()) == {1}
    assert np.min(active_grid.ssb_positions()[:, 1]) == 48
    assert np.min(active_grid.prach_positions()[:, 1]) == 36
    assert set(active_grid.prach_positions()[:, 0].tolist()) == {1}


def test_pbch_dmrs_positions_follow_physical_cell_id_offset() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {"frame": {"ssb_start_symbol": 0, "ssb_symbol_count": 4, "ssb_subcarriers": 240, "ssb_subcarrier_offset": 0}}
    allocation = build_default_allocation(numerology, config)
    grid = ResourceGrid(numerology, allocation, physical_cell_id=321)

    pbch_dmrs = grid.pbch_dmrs_positions(force_active=True)

    assert pbch_dmrs.shape[0] > 0
    assert int(np.min(pbch_dmrs[:, 1]) % 4) == (321 % 4)
