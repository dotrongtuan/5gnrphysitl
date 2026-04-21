from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np

from .broadcast import build_pbch_semantic_payload, decode_pbch_semantic_payload
from .coding import CodingMetadata, build_channel_coder
from .frame_structure import FrameAllocation, build_default_allocation
from .layer_mapping import combine_layer_symbols, layer_map_symbols
from .modulation import ModulationMapper, bits_per_symbol
from .precoding import build_precoder, apply_precoder
from .prach import PrachMapper, bits_to_preamble_id, generate_prach_sequence, preamble_id_to_bits
from .numerology import NumerologyConfig
from .resource_grid import ChannelMapping, ResourceGrid
from .scrambling import scramble_bits
from .types import SpatialLayout
from .uplink import apply_transform_precoding
from .vrb_mapping import VrbPrbMapping, build_vrb_prb_mapping


@dataclass(slots=True)
class TxMetadata:
    direction: str
    channel_type: str
    slot_index: int
    frame_index: int
    numerology: NumerologyConfig
    allocation: FrameAllocation
    spatial_layout: SpatialLayout
    procedure_state: Dict[str, object]
    transform_precoding_enabled: bool
    payload_bits: np.ndarray
    coded_bits: np.ndarray
    scrambled_bits: np.ndarray
    scrambling_sequence: np.ndarray
    coding_metadata: CodingMetadata
    modulation: str
    mapper: object
    mapping: ChannelMapping
    vrb_mapping: VrbPrbMapping
    dmrs: Dict[str, np.ndarray]
    csi_rs: Dict[str, np.ndarray]
    srs: Dict[str, np.ndarray]
    ptrs: Dict[str, np.ndarray]
    ssb: Dict[str, np.ndarray]
    tensor_view_specs: Dict[str, Dict[str, object]]
    modulation_symbols: np.ndarray
    tx_layer_symbols: np.ndarray
    precoding_mode: str
    precoder_matrix: np.ndarray
    tx_port_symbols: np.ndarray
    tx_layer_grid: np.ndarray
    tx_port_grid: np.ndarray
    tx_grid_data: np.ndarray
    tx_grid: np.ndarray
    tx_symbols: np.ndarray
    tx_port_waveforms: np.ndarray
    sample_rate: float
    prach_preamble_id: int | None = None
    prach_root_sequence_index: int | None = None
    prach_cyclic_shift: int | None = None
    prach_sequence: np.ndarray | None = None
    broadcast_payload_fields: Dict[str, object] = field(default_factory=dict)
    codeword_payload_bits: tuple[np.ndarray, ...] = field(default_factory=tuple)
    codeword_coded_bits: tuple[np.ndarray, ...] = field(default_factory=tuple)
    codeword_scrambled_bits: tuple[np.ndarray, ...] = field(default_factory=tuple)
    codeword_scrambling_sequences: tuple[np.ndarray, ...] = field(default_factory=tuple)
    codeword_coding_metadata: tuple[CodingMetadata, ...] = field(default_factory=tuple)
    codeword_modulation_symbols: tuple[np.ndarray, ...] = field(default_factory=tuple)
    codeword_tx_symbols: tuple[np.ndarray, ...] = field(default_factory=tuple)
    codeword_layer_ranges: tuple[tuple[int, int], ...] = field(default_factory=tuple)


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
        self.broadcast_cfg = dict(config.get("broadcast", {}))
        self.physical_cell_id = int(self.broadcast_cfg.get("physical_cell_id", 0)) % 1008
        self.ssb_block_index = int(self.broadcast_cfg.get("ssb_block_index", 0))
        self.vrb_mapping = build_vrb_prb_mapping(config, self.numerology)
        self.precoder_spec = build_precoder(config, self.spatial_layout)
        if self.spatial_layout.num_codewords not in {1, 2}:
            raise ValueError("P2 baseline currently supports spatial.num_codewords in {1, 2}.")
        if self.spatial_layout.num_codewords > self.spatial_layout.num_layers:
            raise ValueError("P2 baseline requires spatial.num_layers >= spatial.num_codewords.")
        if self.spatial_layout.num_layers > self.spatial_layout.num_ports:
            raise ValueError("P2 layer-mapping baseline requires spatial.num_ports >= spatial.num_layers.")
        if self.spatial_layout.num_ports > self.spatial_layout.num_tx_antennas:
            raise ValueError("P2 layer-mapping baseline requires spatial.num_tx_antennas >= spatial.num_ports.")
        if self.spatial_layout.num_layers > self.spatial_layout.num_rx_antennas:
            raise ValueError("P2 layer-mapping baseline requires spatial.num_rx_antennas >= spatial.num_layers.")

    def _split_payload_across_codewords(self, payload: np.ndarray) -> tuple[np.ndarray, ...]:
        parts = np.array_split(np.asarray(payload, dtype=np.uint8), int(self.spatial_layout.num_codewords))
        return tuple(np.asarray(part, dtype=np.uint8).copy() for part in parts)

    def _codeword_layer_ranges(self) -> tuple[tuple[int, int], ...]:
        codeword_count = int(self.spatial_layout.num_codewords)
        layer_count = int(self.spatial_layout.num_layers)
        per_codeword = [layer_count // codeword_count] * codeword_count
        for index in range(layer_count % codeword_count):
            per_codeword[index] += 1
        ranges: list[tuple[int, int]] = []
        start = 0
        for count in per_codeword:
            ranges.append((start, start + int(count)))
            start += int(count)
        return tuple(ranges)

    def _generate_payload(self, channel_type: str, *, slot_index: int = 0) -> np.ndarray:
        if channel_type.lower() == "prach":
            prach_cfg = self.config.get("prach", {})
            width = int(prach_cfg.get("preamble_id_bits", 6))
            preamble_id = int(prach_cfg.get("preamble_id", 0))
            return preamble_id_to_bits(preamble_id, width=width)
        if channel_type.lower() in {"pbch", "broadcast"}:
            size = int(self.config.get("control_channel", {}).get("payload_bits", 128))
            semantic = build_pbch_semantic_payload(
                broadcast_cfg=self.broadcast_cfg,
                numerology_scs_khz=int(self.numerology.scs_khz),
                slot_index=int(slot_index),
                slots_per_frame=int(self.numerology.slots_per_frame),
                payload_length_bits=size,
                ssb_block_index=int(self.ssb_block_index),
            )
            return semantic.payload_bits.copy()
        if channel_type.lower() in {"control", "pdcch", "pucch", "pbch"}:
            size = int(self.config.get("control_channel", {}).get("payload_bits", 128))
        else:
            size = int(self.config.get("transport_block", {}).get("size_bits", 1024))
        return self.rng.integers(0, 2, size=size, dtype=np.uint8)

    def _ofdm_modulate_view(self, active_grid: np.ndarray) -> np.ndarray:
        waveform = []
        for symbol in range(self.numerology.symbols_per_slot):
            bins = ResourceGrid(
                self.numerology,
                self.allocation,
                spatial_layout=self.spatial_layout,
                physical_cell_id=self.physical_cell_id,
                ssb_block_index=self.ssb_block_index,
                vrb_mapping=self.vrb_mapping,
            ).active_to_ifft_bins(
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

    def _transmit_prach(self, *, direction: str, payload: np.ndarray, slot_index: int = 0) -> TxResult:
        grid = ResourceGrid(
            self.numerology,
            self.allocation,
            spatial_layout=self.spatial_layout,
            slot_index=slot_index,
            physical_cell_id=self.physical_cell_id,
            ssb_block_index=self.ssb_block_index,
            vrb_mapping=self.vrb_mapping,
        )
        procedure_state = grid.procedure_state()
        procedure_state["prach_active"] = True
        prach_cfg = self.config.get("prach", {})
        preamble_id = bits_to_preamble_id(payload, width=int(prach_cfg.get("preamble_id_bits", 6)))
        mapping = grid.mapping_for(
            channel_type="prach",
            bits_per_symbol=1,
            modulation="PRACH",
            direction=direction,
        )
        prach_sequence = generate_prach_sequence(
            preamble_id,
            max(int(mapping.positions.shape[0]), 1),
            root_sequence_index=int(prach_cfg.get("root_sequence_index", 25)),
            cyclic_shift=int(prach_cfg.get("cyclic_shift", 13)),
        )
        if mapping.positions.shape[0]:
            grid.map_symbols(prach_sequence, mapping.positions)
        tx_grid_data = grid.grid.copy()
        port_waveforms = self._ofdm_modulate(grid)
        waveform = port_waveforms[0].copy() if port_waveforms.size else np.array([], dtype=np.complex128)
        coding_metadata = CodingMetadata(
            channel_type="prach",
            crc_type="crc8",
            payload_length=int(payload.size),
            rate_matched_length=int(payload.size),
            mother_length=int(payload.size),
            redundancy_version=0,
            tb_crc_width=0,
            code_block_count=1,
            code_block_payload_lengths=(int(payload.size),),
            code_block_with_crc_lengths=(int(payload.size),),
            mother_block_lengths=(int(payload.size),),
            transport_block_with_crc=payload.copy(),
            code_block_payloads=(payload.copy(),),
            code_blocks_with_crc=(payload.copy(),),
            mother_code_blocks=(payload.copy(),),
        )
        empty_dmrs = {
            "positions": np.zeros((0, 2), dtype=int),
            "symbols": np.array([], dtype=np.complex128),
            "port": 0,
        }
        empty_rs = {
            "positions": np.zeros((0, 2), dtype=int),
            "symbols": np.array([], dtype=np.complex128),
            "port": 0,
        }
        empty_ssb = {
            "positions": np.zeros((0, 2), dtype=int),
            "symbols": np.array([], dtype=np.complex128),
            "pss_positions": np.zeros((0, 2), dtype=int),
            "pss_symbols": np.array([], dtype=np.complex128),
            "sss_positions": np.zeros((0, 2), dtype=int),
            "sss_symbols": np.array([], dtype=np.complex128),
            "pbch_dmrs_positions": np.zeros((0, 2), dtype=int),
            "pbch_dmrs_symbols": np.array([], dtype=np.complex128),
            "physical_cell_id": int(self.physical_cell_id),
            "n_id_1": int(self.physical_cell_id // 3),
            "n_id_2": int(self.physical_cell_id % 3),
            "ssb_block_index": int(self.ssb_block_index),
            "port": 0,
        }
        return TxResult(
            waveform=waveform,
            metadata=TxMetadata(
                direction=direction,
                channel_type="prach",
                slot_index=int(slot_index),
                frame_index=int(slot_index) // max(int(self.numerology.slots_per_frame), 1),
                numerology=self.numerology,
                allocation=self.allocation,
                spatial_layout=self.spatial_layout,
                procedure_state=procedure_state,
                transform_precoding_enabled=False,
                payload_bits=payload,
                coded_bits=payload.copy(),
                scrambled_bits=payload.copy(),
                scrambling_sequence=np.zeros(payload.size, dtype=np.uint8),
                coding_metadata=coding_metadata,
                modulation="PRACH",
                mapper=PrachMapper(prach_sequence),
                mapping=mapping,
                vrb_mapping=self.vrb_mapping,
                dmrs=empty_dmrs,
                csi_rs=empty_rs.copy(),
                srs=empty_rs.copy(),
                ptrs=empty_rs.copy(),
                ssb=empty_ssb.copy(),
                tensor_view_specs=grid.tensor_view_specs_as_dict(),
                modulation_symbols=prach_sequence.copy(),
                tx_layer_symbols=prach_sequence.reshape(1, -1).copy(),
                precoding_mode="identity",
                precoder_matrix=np.eye(1, dtype=np.complex128),
                tx_port_symbols=prach_sequence.reshape(1, -1).copy(),
                tx_layer_grid=grid.layer_grid.copy(),
                tx_port_grid=grid.port_grid.copy(),
                tx_grid_data=tx_grid_data,
                tx_grid=grid.grid.copy(),
                tx_symbols=prach_sequence.copy(),
                tx_port_waveforms=port_waveforms.copy(),
                sample_rate=self.numerology.sample_rate,
                prach_preamble_id=int(preamble_id),
                prach_root_sequence_index=int(prach_cfg.get("root_sequence_index", 25)),
                prach_cyclic_shift=int(prach_cfg.get("cyclic_shift", 13)),
                prach_sequence=prach_sequence.copy(),
            ),
        )

    def transmit(self, channel_type: str = "data", payload_bits: np.ndarray | None = None, slot_index: int = 0) -> TxResult:
        channel_type = channel_type.lower()
        direction = str(self.config.get("link", {}).get("direction", "downlink")).lower()
        if direction not in {"downlink", "uplink"}:
            raise ValueError(f"Unsupported link.direction: {direction}")

        payload = (
            np.asarray(payload_bits, dtype=np.uint8)
            if payload_bits is not None
            else self._generate_payload(channel_type, slot_index=slot_index)
        )
        if channel_type == "prach":
            return self._transmit_prach(direction=direction, payload=payload, slot_index=slot_index)
        transform_precoding_enabled = bool(self.config.get("uplink", {}).get("transform_precoding", False)) and direction == "uplink" and channel_type in {"data", "pusch"}

        modulation_name = str(
            self.config.get("modulation", {}).get(
                "scheme",
                self.config.get("control_channel", {}).get("modulation", "QPSK")
                if channel_type in {"control", "pdcch", "pucch"}
                else "QPSK",
            )
        ).upper()
        mapper = ModulationMapper(modulation_name)

        grid = ResourceGrid(
            self.numerology,
            self.allocation,
            spatial_layout=self.spatial_layout,
            slot_index=slot_index,
            physical_cell_id=self.physical_cell_id,
            ssb_block_index=self.ssb_block_index,
            vrb_mapping=self.vrb_mapping,
        )
        procedure_state = grid.procedure_state()
        if direction == "downlink" and channel_type in {"control", "pdcch"}:
            procedure_state["search_space_active"] = True
            procedure_state["search_space_symbols"] = [
                int(symbol)
                for symbol in self.allocation.monitored_search_space_symbols(
                    self.numerology,
                    slot=slot_index,
                    force_active=True,
                )
            ]
        if direction == "downlink" and channel_type in {"pbch", "broadcast"}:
            procedure_state["ssb_active"] = True
        mapping = grid.mapping_for(
            channel_type=channel_type,
            bits_per_symbol=bits_per_symbol(modulation_name),
            modulation=modulation_name,
            direction=direction,
        )

        if self.spatial_layout.num_codewords > 1 and channel_type not in {"data", "pdsch", "pusch"}:
            raise ValueError("P2 two-codeword baseline currently supports data-channel mapping only.")

        codeword_payload_bits = self._split_payload_across_codewords(payload)
        codeword_layer_ranges = self._codeword_layer_ranges()
        positions_per_layer = int(mapping.positions.shape[0])
        scrambling_cfg = self.config.get("scrambling", {})
        codeword_coded_bits = []
        codeword_coding_metadata = []
        codeword_scrambled_bits = []
        codeword_scrambling_sequences = []
        codeword_modulation_symbols = []
        codeword_tx_symbols = []
        layer_symbol_views = []
        tx_layer_symbols = np.zeros((self.spatial_layout.num_layers, positions_per_layer), dtype=np.complex128)
        modulation_layer_symbols = np.zeros_like(tx_layer_symbols)
        for codeword_index, (cw_payload, layer_range) in enumerate(zip(codeword_payload_bits, codeword_layer_ranges)):
            layer_start, layer_end = layer_range
            cw_layers = max(layer_end - layer_start, 1)
            target_length = positions_per_layer * mapper.bits_per_symbol * cw_layers
            coder = build_channel_coder(channel_type=channel_type, config=self.config)
            coded_bits, coding_metadata = coder.encode(payload_bits=cw_payload, target_length=target_length)
            scrambled_bits, scrambling_sequence = scramble_bits(
                coded_bits,
                nid=int(scrambling_cfg.get("nid", 1)),
                rnti=int(scrambling_cfg.get("rnti", 0x1234)),
                q=codeword_index if channel_type in {"data", "pdsch", "pusch"} else 1,
            )
            modulation_symbols = mapper.map_bits(scrambled_bits)
            cw_tx_symbols = (
                apply_transform_precoding(modulation_symbols)
                if transform_precoding_enabled
                else modulation_symbols.copy()
            )
            cw_layer_symbols = layer_map_symbols(cw_tx_symbols, cw_layers)
            cw_modulation_layer_symbols = layer_map_symbols(modulation_symbols, cw_layers)

            codeword_coded_bits.append(coded_bits.copy())
            codeword_coding_metadata.append(coding_metadata)
            codeword_scrambled_bits.append(scrambled_bits.copy())
            codeword_scrambling_sequences.append(scrambling_sequence.copy())
            codeword_modulation_symbols.append(modulation_symbols.copy())
            codeword_tx_symbols.append(cw_tx_symbols.copy())
            layer_symbol_views.append(cw_layer_symbols.copy())
            tx_layer_symbols[layer_start:layer_end, : cw_layer_symbols.shape[1]] = cw_layer_symbols
            modulation_layer_symbols[layer_start:layer_end, : cw_modulation_layer_symbols.shape[1]] = cw_modulation_layer_symbols

        coded_bits = np.concatenate(codeword_coded_bits) if codeword_coded_bits else np.array([], dtype=np.uint8)
        coding_metadata = codeword_coding_metadata[0]
        scrambled_bits = np.concatenate(codeword_scrambled_bits) if codeword_scrambled_bits else np.array([], dtype=np.uint8)
        scrambling_sequence = (
            np.concatenate(codeword_scrambling_sequences)
            if codeword_scrambling_sequences
            else np.array([], dtype=np.uint8)
        )
        modulation_symbols = combine_layer_symbols(modulation_layer_symbols, total_symbols=positions_per_layer * self.spatial_layout.num_layers)
        tx_symbols = combine_layer_symbols(tx_layer_symbols, total_symbols=positions_per_layer * self.spatial_layout.num_layers)
        tx_port_symbols = apply_precoder(tx_layer_symbols, self.precoder_spec.matrix)
        grid.map_layer_streams(tx_layer_symbols, mapping.positions, port_symbols=tx_port_symbols)
        tx_grid_data = grid.grid.copy()
        reference_cfg = self.config.get("reference_signals", {})
        empty_rs = {"positions": np.zeros((0, 2), dtype=int), "symbols": np.array([], dtype=np.complex128), "port": 0}
        empty_ssb = {
            "positions": np.zeros((0, 2), dtype=int),
            "symbols": np.array([], dtype=np.complex128),
            "pss_positions": np.zeros((0, 2), dtype=int),
            "pss_symbols": np.array([], dtype=np.complex128),
            "sss_positions": np.zeros((0, 2), dtype=int),
            "sss_symbols": np.array([], dtype=np.complex128),
            "pbch_dmrs_positions": np.zeros((0, 2), dtype=int),
            "pbch_dmrs_symbols": np.array([], dtype=np.complex128),
            "physical_cell_id": int(self.physical_cell_id),
            "n_id_1": int(self.physical_cell_id // 3),
            "n_id_2": int(self.physical_cell_id % 3),
            "ssb_block_index": int(self.ssb_block_index),
            "port": 0,
        }
        insert_csi_rs = bool(reference_cfg.get("enable_csi_rs", True)) and direction == "downlink" and channel_type in {"data", "pdsch", "control", "pdcch"}
        insert_srs = bool(reference_cfg.get("enable_srs", True)) and direction == "uplink" and channel_type in {"data", "pusch"}
        insert_ptrs = bool(reference_cfg.get("enable_ptrs", True)) and (
            (direction == "downlink" and channel_type in {"data", "pdsch"})
            or (direction == "uplink" and channel_type in {"data", "pusch"})
        )
        insert_ssb = direction == "downlink" and channel_type in {"pbch", "broadcast"}
        csi_rs = (
            grid.insert_csi_rs(slot=slot_index, seed=int(reference_cfg.get("sequence_seed", 73)))
            if insert_csi_rs
            else empty_rs.copy()
        )
        srs = (
            grid.insert_srs(slot=slot_index, seed=int(reference_cfg.get("sequence_seed", 73)))
            if insert_srs
            else empty_rs.copy()
        )
        ptrs = (
            grid.insert_ptrs(
                slot=slot_index,
                seed=int(reference_cfg.get("sequence_seed", 73)),
                direction=direction,
                channel_type=channel_type,
            )
            if insert_ptrs
            else empty_rs.copy()
        )
        ssb = (
            grid.insert_ssb(
                slot=slot_index,
                seed=int(reference_cfg.get("sequence_seed", 73)),
                force_active=channel_type in {"pbch", "broadcast"},
            )
            if insert_ssb
            else empty_ssb.copy()
        )
        dmrs = grid.insert_dmrs(slot=slot_index) if channel_type not in {"pbch", "broadcast"} else empty_rs.copy()
        port_waveforms = self._ofdm_modulate(grid)
        waveform = port_waveforms[0].copy() if port_waveforms.shape[0] == 1 else port_waveforms.copy()
        broadcast_payload_fields = {}
        if channel_type in {"pbch", "broadcast"}:
            broadcast_payload_fields = decode_pbch_semantic_payload(payload)

        return TxResult(
            waveform=waveform,
            metadata=TxMetadata(
                direction=direction,
                channel_type=channel_type,
                slot_index=int(slot_index),
                frame_index=int(slot_index) // max(int(self.numerology.slots_per_frame), 1),
                numerology=self.numerology,
                allocation=self.allocation,
                spatial_layout=self.spatial_layout,
                procedure_state=procedure_state,
                transform_precoding_enabled=transform_precoding_enabled,
                payload_bits=payload,
                coded_bits=coded_bits,
                scrambled_bits=scrambled_bits,
                scrambling_sequence=scrambling_sequence,
                coding_metadata=coding_metadata,
                modulation=modulation_name,
                mapper=mapper,
                mapping=mapping,
                vrb_mapping=self.vrb_mapping,
                dmrs=dmrs,
                csi_rs=csi_rs,
                srs=srs,
                ptrs=ptrs,
                ssb=ssb,
                tensor_view_specs=grid.tensor_view_specs_as_dict(),
                modulation_symbols=modulation_symbols,
                tx_layer_symbols=tx_layer_symbols.copy(),
                precoding_mode=self.precoder_spec.mode,
                precoder_matrix=self.precoder_spec.matrix.copy(),
                tx_port_symbols=tx_port_symbols.copy(),
                tx_layer_grid=grid.layer_grid.copy(),
                tx_port_grid=grid.port_grid.copy(),
                tx_grid_data=tx_grid_data,
                tx_grid=grid.grid.copy(),
                tx_symbols=tx_symbols,
                tx_port_waveforms=port_waveforms.copy(),
                sample_rate=self.numerology.sample_rate,
                broadcast_payload_fields=broadcast_payload_fields,
                codeword_payload_bits=tuple(block.copy() for block in codeword_payload_bits),
                codeword_coded_bits=tuple(block.copy() for block in codeword_coded_bits),
                codeword_scrambled_bits=tuple(block.copy() for block in codeword_scrambled_bits),
                codeword_scrambling_sequences=tuple(block.copy() for block in codeword_scrambling_sequences),
                codeword_coding_metadata=tuple(codeword_coding_metadata),
                codeword_modulation_symbols=tuple(block.copy() for block in codeword_modulation_symbols),
                codeword_tx_symbols=tuple(block.copy() for block in codeword_tx_symbols),
                codeword_layer_ranges=tuple((int(start), int(end)) for start, end in codeword_layer_ranges),
            ),
        )
