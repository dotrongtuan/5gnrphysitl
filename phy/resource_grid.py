from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from .dmrs import dmrs_pattern
from .frame_structure import FrameAllocation
from .numerology import NumerologyConfig
from .types import SpatialLayout, TensorViewSpec


@dataclass(slots=True)
class ChannelMapping:
    positions: np.ndarray
    bits_capacity: int
    modulation: str


class ResourceGrid:
    """Single-slot active-subcarrier resource grid with layer/port/RX views."""

    def __init__(
        self,
        numerology: NumerologyConfig,
        allocation: FrameAllocation,
        spatial_layout: SpatialLayout | None = None,
    ) -> None:
        self.numerology = numerology
        self.allocation = allocation
        self.spatial_layout = spatial_layout or SpatialLayout()
        grid_shape = (numerology.symbols_per_slot, numerology.active_subcarriers)
        self.layer_grid = np.zeros(
            (self.spatial_layout.num_layers, *grid_shape),
            dtype=np.complex128,
        )
        self.port_grid = np.zeros(
            (self.spatial_layout.num_ports, *grid_shape),
            dtype=np.complex128,
        )
        self.rx_grid_tensor = np.zeros(
            (self.spatial_layout.num_rx_antennas, *grid_shape),
            dtype=np.complex128,
        )

    @property
    def shape(self) -> tuple[int, int]:
        return self.grid.shape

    @property
    def grid(self) -> np.ndarray:
        return self.port_grid[0]

    @grid.setter
    def grid(self, value: np.ndarray) -> None:
        self.port_grid[0, :, :] = np.asarray(value, dtype=np.complex128)

    def layer_view(self, layer: int = 0) -> np.ndarray:
        return self.layer_grid[int(layer)]

    def port_view(self, port: int = 0) -> np.ndarray:
        return self.port_grid[int(port)]

    def rx_view(self, rx_ant: int = 0) -> np.ndarray:
        return self.rx_grid_tensor[int(rx_ant)]

    def tensor_view_specs(self) -> dict[str, TensorViewSpec]:
        return {
            "layer_grid": TensorViewSpec(
                name="layer_grid",
                axes=("layer", "symbol", "subcarrier"),
                shape=tuple(int(dim) for dim in self.layer_grid.shape),
                description="Layer-domain resource grid before precoding and port mapping.",
            ),
            "port_grid": TensorViewSpec(
                name="port_grid",
                axes=("port", "symbol", "subcarrier"),
                shape=tuple(int(dim) for dim in self.port_grid.shape),
                description="Antenna-port resource grid after layer-to-port mapping.",
            ),
            "rx_grid_tensor": TensorViewSpec(
                name="rx_grid_tensor",
                axes=("rx_ant", "symbol", "subcarrier"),
                shape=tuple(int(dim) for dim in self.rx_grid_tensor.shape),
                description="Per-receive-antenna FFT grid.",
            ),
        }

    def tensor_view_specs_as_dict(self) -> dict[str, dict[str, object]]:
        return {name: spec.as_dict() for name, spec in self.tensor_view_specs().items()}

    def pdcch_positions(self) -> np.ndarray:
        positions = []
        for symbol in self.allocation.pdcch_symbols:
            for sc in range(self.allocation.control_subcarriers):
                positions.append((symbol, sc))
        return np.asarray(positions, dtype=int)

    def dmrs_positions(self) -> np.ndarray:
        positions = []
        for symbol in self.allocation.dmrs_symbols:
            if symbol < self.allocation.pdsch_start_symbol:
                continue
            subcarriers, _ = dmrs_pattern(self.numerology.active_subcarriers, dmrs_symbol=symbol)
            for sc in subcarriers:
                positions.append((symbol, sc))
        return np.asarray(positions, dtype=int)

    def pdsch_positions(self) -> np.ndarray:
        positions = []
        dmrs = {tuple(position) for position in self.dmrs_positions().tolist()}
        for symbol in self.allocation.pdsch_symbols(self.numerology):
            for sc in range(self.numerology.active_subcarriers):
                if (symbol, sc) not in dmrs:
                    positions.append((symbol, sc))
        return np.asarray(positions, dtype=int)

    def pusch_positions(self) -> np.ndarray:
        positions = []
        dmrs = {tuple(position) for position in self.dmrs_positions().tolist()}
        for symbol in self.allocation.pusch_symbols(self.numerology):
            for sc in range(self.numerology.active_subcarriers):
                if (symbol, sc) not in dmrs:
                    positions.append((symbol, sc))
        return np.asarray(positions, dtype=int)

    def control_re_mask(self) -> np.ndarray:
        mask = np.zeros(self.shape, dtype=np.uint8)
        positions = self.pdcch_positions()
        if positions.size:
            mask[positions[:, 0], positions[:, 1]] = 1
        return mask

    def dmrs_re_mask(self) -> np.ndarray:
        mask = np.zeros(self.shape, dtype=np.uint8)
        positions = self.dmrs_positions()
        if positions.size:
            mask[positions[:, 0], positions[:, 1]] = 1
        return mask

    def data_re_mask(self, *, direction: str = "downlink") -> np.ndarray:
        mask = np.zeros(self.shape, dtype=np.uint8)
        positions = self.pusch_positions() if str(direction).lower() == "uplink" else self.pdsch_positions()
        if positions.size:
            mask[positions[:, 0], positions[:, 1]] = 1
        return mask

    def re_masks(self, *, direction: str = "downlink") -> Dict[str, np.ndarray]:
        return {
            "control": self.control_re_mask(),
            "dmrs": self.dmrs_re_mask(),
            "data": self.data_re_mask(direction=direction),
        }

    def mapping_for(self, channel_type: str, bits_per_symbol: int, modulation: str, *, direction: str = "downlink") -> ChannelMapping:
        channel_type = channel_type.lower()
        direction = str(direction).lower()
        if direction == "uplink":
            if channel_type in {"control", "pucch"}:
                raise NotImplementedError("PUCCH mapping is not implemented yet.")
            positions = self.pusch_positions()
        elif channel_type in {"control", "pdcch"}:
            positions = self.pdcch_positions()
        else:
            positions = self.pdsch_positions()
        return ChannelMapping(
            positions=positions,
            bits_capacity=positions.shape[0] * bits_per_symbol,
            modulation=modulation,
        )

    def map_symbols(
        self,
        symbols: np.ndarray,
        positions: np.ndarray,
        *,
        layer: int = 0,
        port: int = 0,
    ) -> None:
        positions = np.asarray(positions, dtype=int)
        count = min(symbols.size, positions.shape[0])
        if count <= 0:
            return
        self.layer_grid[layer, positions[:count, 0], positions[:count, 1]] = symbols[:count]
        self.port_grid[port, positions[:count, 0], positions[:count, 1]] = symbols[:count]

    def extract_symbols(self, positions: np.ndarray, *, domain: str = "port", index: int = 0) -> np.ndarray:
        positions = np.asarray(positions, dtype=int)
        domain_name = str(domain).lower()
        if domain_name == "layer":
            view = self.layer_view(index)
        elif domain_name == "rx":
            view = self.rx_view(index)
        else:
            view = self.port_view(index)
        return view[positions[:, 0], positions[:, 1]]

    def insert_dmrs(self, slot: int = 0, *, port: int = 0) -> Dict[str, np.ndarray]:
        inserted = []
        port_view = self.port_view(port)
        for symbol in self.allocation.dmrs_symbols:
            if symbol < self.allocation.pdsch_start_symbol:
                continue
            subcarriers, sequence = dmrs_pattern(self.numerology.active_subcarriers, dmrs_symbol=symbol, slot=slot)
            port_view[symbol, subcarriers] = sequence
            inserted.extend([(symbol, sc) for sc in subcarriers])
        position_array = np.asarray(inserted, dtype=int) if inserted else np.zeros((0, 2), dtype=int)
        return {
            "positions": position_array,
            "symbols": port_view[position_array[:, 0], position_array[:, 1]]
            if inserted
            else np.array([], dtype=np.complex128),
            "port": int(port),
        }

    def active_to_ifft_bins(self, active_symbol: np.ndarray) -> np.ndarray:
        fft_bins = np.zeros(self.numerology.fft_size, dtype=np.complex128)
        shifted = np.zeros(self.numerology.fft_size, dtype=np.complex128)
        center = self.numerology.fft_size // 2
        left = self.numerology.active_subcarriers // 2
        right = self.numerology.active_subcarriers - left
        shifted[center - left : center] = active_symbol[:left]
        shifted[center + 1 : center + 1 + right] = active_symbol[left:]
        fft_bins[:] = np.fft.ifftshift(shifted)
        return fft_bins

    def ifft_bins_to_active(self, fft_bins: np.ndarray) -> np.ndarray:
        shifted = np.fft.fftshift(fft_bins)
        center = self.numerology.fft_size // 2
        left = self.numerology.active_subcarriers // 2
        right = self.numerology.active_subcarriers - left
        return np.concatenate(
            [
                shifted[center - left : center],
                shifted[center + 1 : center + 1 + right],
            ]
        )
