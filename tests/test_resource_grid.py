from __future__ import annotations

import numpy as np

from phy.frame_structure import build_default_allocation
from phy.numerology import NumerologyConfig
from phy.resource_grid import ResourceGrid
from phy.types import SpatialLayout


def test_resource_grid_positions_are_non_empty() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {"frame": {"control_symbols": 2, "pdsch_start_symbol": 2, "dmrs_symbols": [3, 10]}}
    allocation = build_default_allocation(numerology, config)
    grid = ResourceGrid(numerology, allocation)
    assert grid.pdcch_positions().shape[0] > 0
    assert grid.pdsch_positions().shape[0] > 0
    assert grid.dmrs_positions().shape[0] > 0


def test_resource_grid_exposes_tensor_views_and_preserves_legacy_grid() -> None:
    numerology = NumerologyConfig(scs_khz=30, fft_size=512, cp_length=36, n_rb=24)
    config = {"frame": {"control_symbols": 2, "pdsch_start_symbol": 2, "dmrs_symbols": [3, 10]}}
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
