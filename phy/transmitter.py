from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from .coding import CodingMetadata, build_channel_coder
from .frame_structure import FrameAllocation, build_default_allocation
from .modulation import ModulationMapper, bits_per_symbol
from .numerology import NumerologyConfig
from .resource_grid import ChannelMapping, ResourceGrid
from .scrambling import scramble_bits
from .types import SpatialLayout
from .uplink import apply_transform_precoding


@dataclass(slots=True)
class TxMetadata:
    direction: str
    channel_type: str
    numerology: NumerologyConfig
    allocation: FrameAllocation
    spatial_layout: SpatialLayout
    transform_precoding_enabled: bool
    payload_bits: np.ndarray
    coded_bits: np.ndarray
    scrambled_bits: np.ndarray
    scrambling_sequence: np.ndarray
    coding_metadata: CodingMetadata
    modulation: str
    mapper: ModulationMapper
    mapping: ChannelMapping
    dmrs: Dict[str, np.ndarray]
    tensor_view_specs: Dict[str, Dict[str, object]]
    modulation_symbols: np.ndarray
    tx_layer_grid: np.ndarray
    tx_port_grid: np.ndarray
    tx_grid_data: np.ndarray
    tx_grid: np.ndarray
    tx_symbols: np.ndarray
    tx_port_waveforms: np.ndarray
    sample_rate: float


@dataclass(slots=True)
class TxResult:
    waveform: np.ndarray
    metadata: TxMetadata


class NrTransmitter:
    def __init__(self, config: Dict) -> None:
        self.config = config
        self.seed = int(config.get("simulation", {}).get("seed", 0))
        self.rng = np.random.default_rng(self.seed)
        self.numerology = NumerologyConfig.from_dict(config["numerology"])
        self.allocation = build_default_allocation(self.numerology, config)
        self.spatial_layout = SpatialLayout.from_config(config)

    def _generate_payload(self, channel_type: str) -> np.ndarray:
        if channel_type.lower() in {"control", "pdcch"}:
            size = int(self.config.get("control_channel", {}).get("payload_bits", 128))
        else:
            size = int(self.config.get("transport_block", {}).get("size_bits", 1024))
        return self.rng.integers(0, 2, size=size, dtype=np.uint8)

    def _ofdm_modulate_view(self, active_grid: np.ndarray) -> np.ndarray:
        waveform = []
        for symbol in range(self.numerology.symbols_per_slot):
            bins = ResourceGrid(self.numerology, self.allocation, spatial_layout=self.spatial_layout).active_to_ifft_bins(
                active_grid[symbol]
            )
            time_symbol = np.fft.ifft(bins, n=self.numerology.fft_size)
            cp = time_symbol[-self.numerology.cp_length :]
            waveform.append(np.concatenate([cp, time_symbol]))
        return np.concatenate(waveform).astype(np.complex128)

    def _ofdm_modulate(self, grid: ResourceGrid) -> np.ndarray:
        port_waveforms = [
            self._ofdm_modulate_view(grid.port_view(port_index)) for port_index in range(grid.port_grid.shape[0])
        ]
        return np.stack(port_waveforms, axis=0) if port_waveforms else np.zeros((0, 0), dtype=np.complex128)

    def transmit(self, channel_type: str = "data", payload_bits: np.ndarray | None = None) -> TxResult:
        channel_type = channel_type.lower()
        direction = str(self.config.get("link", {}).get("direction", "downlink")).lower()
        if direction not in {"downlink", "uplink"}:
            raise ValueError(f"Unsupported link.direction: {direction}")
        if direction == "uplink" and channel_type in {"control", "pucch"}:
            raise NotImplementedError("Uplink control-channel mapping is not implemented yet. Use data/PUSCH baseline.")

        payload = np.asarray(payload_bits, dtype=np.uint8) if payload_bits is not None else self._generate_payload(channel_type)
        transform_precoding_enabled = bool(self.config.get("uplink", {}).get("transform_precoding", False)) and direction == "uplink" and channel_type in {"data", "pusch"}

        modulation_name = str(
            self.config.get("modulation", {}).get(
                "scheme",
                self.config.get("control_channel", {}).get("modulation", "QPSK")
                if channel_type in {"control", "pdcch"}
                else "QPSK",
            )
        ).upper()
        mapper = ModulationMapper(modulation_name)

        grid = ResourceGrid(self.numerology, self.allocation, spatial_layout=self.spatial_layout)
        mapping = grid.mapping_for(
            channel_type=channel_type,
            bits_per_symbol=bits_per_symbol(modulation_name),
            modulation=modulation_name,
            direction=direction,
        )

        coder = build_channel_coder(channel_type=channel_type, config=self.config)
        coded_bits, coding_metadata = coder.encode(payload_bits=payload, target_length=mapping.bits_capacity)
        scrambling_cfg = self.config.get("scrambling", {})
        scrambled_bits, scrambling_sequence = scramble_bits(
            coded_bits,
            nid=int(scrambling_cfg.get("nid", 1)),
            rnti=int(scrambling_cfg.get("rnti", 0x1234)),
            q=0 if channel_type in {"data", "pdsch"} else 1,
        )
        modulation_symbols = mapper.map_bits(scrambled_bits)
        tx_symbols = apply_transform_precoding(modulation_symbols) if transform_precoding_enabled else modulation_symbols.copy()
        grid.map_symbols(tx_symbols, mapping.positions)
        tx_grid_data = grid.grid.copy()
        dmrs = grid.insert_dmrs(slot=0)
        port_waveforms = self._ofdm_modulate(grid)
        waveform = port_waveforms[0].copy()

        return TxResult(
            waveform=waveform,
            metadata=TxMetadata(
                direction=direction,
                channel_type=channel_type,
                numerology=self.numerology,
                allocation=self.allocation,
                spatial_layout=self.spatial_layout,
                transform_precoding_enabled=transform_precoding_enabled,
                payload_bits=payload,
                coded_bits=coded_bits,
                scrambled_bits=scrambled_bits,
                scrambling_sequence=scrambling_sequence,
                coding_metadata=coding_metadata,
                modulation=modulation_name,
                mapper=mapper,
                mapping=mapping,
                dmrs=dmrs,
                tensor_view_specs=grid.tensor_view_specs_as_dict(),
                modulation_symbols=modulation_symbols,
                tx_layer_grid=grid.layer_grid.copy(),
                tx_port_grid=grid.port_grid.copy(),
                tx_grid_data=tx_grid_data,
                tx_grid=grid.grid.copy(),
                tx_symbols=tx_symbols,
                tx_port_waveforms=port_waveforms.copy(),
                sample_rate=self.numerology.sample_rate,
            ),
        )
