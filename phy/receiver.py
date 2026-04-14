from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from .channel_estimation import channel_mse, ls_estimate_from_dmrs
from .coding import build_channel_coder, rate_recover_llrs
from .equalization import equalize
from .layer_mapping import combine_layer_symbols, expand_positions_for_layers
from .kpi import (
    LinkKpiSummary,
    bit_error_rate,
    block_error_rate,
    error_vector_magnitude,
    estimate_snr_db,
    spectral_efficiency_bps_hz,
    throughput_bps,
)
from .mimo_detection import detect_layers
from .precoding import recover_layers_from_ports
from .prach import detect_prach_preamble, preamble_id_to_bits
from .resource_grid import ResourceGrid
from .scrambling import descramble_llrs
from .synchronization import correct_cfo, estimate_cfo_from_cp, estimate_symbol_timing
from .transmitter import TxMetadata
from .uplink import remove_transform_precoding


@dataclass(slots=True)
class RxResult:
    recovered_bits: np.ndarray
    crc_ok: bool
    corrected_waveform: np.ndarray
    spatial_layout: object
    tensor_view_specs: Dict[str, Dict[str, object]]
    cp_removed_tensor: np.ndarray
    fft_bins_tensor: np.ndarray
    rx_grid_tensor: np.ndarray
    rx_grid: np.ndarray
    re_data_positions: np.ndarray
    re_data_symbols: np.ndarray
    re_dmrs_positions: np.ndarray
    re_dmrs_symbols: np.ndarray
    re_csi_rs_positions: np.ndarray
    re_csi_rs_symbols: np.ndarray
    re_srs_positions: np.ndarray
    re_srs_symbols: np.ndarray
    re_ptrs_positions: np.ndarray
    re_ptrs_symbols: np.ndarray
    re_ssb_positions: np.ndarray
    re_ssb_symbols: np.ndarray
    re_pbch_dmrs_positions: np.ndarray
    re_pbch_dmrs_symbols: np.ndarray
    channel_tensor: np.ndarray
    effective_channel_tensor: np.ndarray
    rx_port_symbols: np.ndarray
    equalized_port_symbols: np.ndarray
    rx_layer_symbols: np.ndarray
    equalized_layer_symbols: np.ndarray
    detected_layer_symbols: np.ndarray
    rx_symbols: np.ndarray
    equalized_symbols: np.ndarray
    detected_symbols: np.ndarray
    channel_estimate: np.ndarray
    llrs: np.ndarray
    descrambled_llrs: np.ndarray
    rate_recovered_llrs: np.ndarray
    decoder_input_llrs: np.ndarray
    recovered_bits_by_codeword: tuple[np.ndarray, ...]
    llrs_by_codeword: tuple[np.ndarray, ...]
    descrambled_llrs_by_codeword: tuple[np.ndarray, ...]
    rate_recovered_llrs_by_codeword: tuple[np.ndarray, ...]
    decoder_input_llrs_by_codeword: tuple[np.ndarray, ...]
    rate_recovered_code_blocks: tuple[np.ndarray, ...]
    decoder_input_code_blocks: tuple[np.ndarray, ...]
    recovered_code_blocks: tuple[np.ndarray, ...]
    code_block_crc_ok: tuple[bool, ...]
    codeword_crc_ok: tuple[bool, ...]
    timing_offset: int
    cfo_estimate_hz: float
    kpis: LinkKpiSummary
    prach_reference_sequence: np.ndarray | None = None
    prach_candidate_metrics: np.ndarray | None = None
    detected_preamble_id: int | None = None
    prach_detection_metric: float | None = None


class NrReceiver:
    def __init__(self, config: Dict) -> None:
        self.config = config

    def _decode_codewords(
        self,
        *,
        detected_layer_symbols: np.ndarray,
        noise_variance: float,
        tx_metadata: TxMetadata,
    ) -> dict[str, object]:
        codeword_ranges = tuple(getattr(tx_metadata, "codeword_layer_ranges", ()) or ((0, detected_layer_symbols.shape[0]),))
        codeword_modulation_symbols = tuple(
            np.asarray(symbols, dtype=np.complex128).reshape(-1)
            for symbols in (getattr(tx_metadata, "codeword_modulation_symbols", ()) or (tx_metadata.modulation_symbols,))
        )
        codeword_scrambling_sequences = tuple(
            np.asarray(sequence, dtype=np.uint8).reshape(-1)
            for sequence in (getattr(tx_metadata, "codeword_scrambling_sequences", ()) or (tx_metadata.scrambling_sequence,))
        )
        codeword_coding_metadata = tuple(getattr(tx_metadata, "codeword_coding_metadata", ()) or (tx_metadata.coding_metadata,))

        llrs_by_codeword: list[np.ndarray] = []
        descrambled_llrs_by_codeword: list[np.ndarray] = []
        rate_recovered_llrs_by_codeword: list[np.ndarray] = []
        decoder_input_llrs_by_codeword: list[np.ndarray] = []
        recovered_bits_by_codeword: list[np.ndarray] = []
        codeword_crc_ok: list[bool] = []
        rate_recovered_code_blocks: list[np.ndarray] = []
        decoder_input_code_blocks: list[np.ndarray] = []
        recovered_code_blocks: list[np.ndarray] = []
        code_block_crc_ok: list[bool] = []

        coder = build_channel_coder(channel_type=tx_metadata.channel_type, config=self.config)
        for codeword_index, (layer_start, layer_end) in enumerate(codeword_ranges):
            layer_slice = np.asarray(
                detected_layer_symbols[int(layer_start) : int(layer_end)],
                dtype=np.complex128,
            )
            total_symbols = int(codeword_modulation_symbols[min(codeword_index, len(codeword_modulation_symbols) - 1)].size)
            detected_symbols = combine_layer_symbols(layer_slice, total_symbols=total_symbols)
            llrs = tx_metadata.mapper.demap_llr(detected_symbols, noise_variance=max(noise_variance, 1e-9))
            descrambled_llrs = descramble_llrs(
                llrs,
                codeword_scrambling_sequences[min(codeword_index, len(codeword_scrambling_sequences) - 1)],
            )
            coding_metadata = codeword_coding_metadata[min(codeword_index, len(codeword_coding_metadata) - 1)]
            rate_recovered_llrs = rate_recover_llrs(descrambled_llrs, coding_metadata)

            if hasattr(coder, "decode_with_trace"):
                recovered_bits, crc_ok, decode_trace = coder.decode_with_trace(descrambled_llrs, coding_metadata)
            else:  # pragma: no cover
                recovered_bits, crc_ok = coder.decode(descrambled_llrs, coding_metadata)
                decode_trace = None

            llrs_by_codeword.append(llrs.copy())
            descrambled_llrs_by_codeword.append(descrambled_llrs.copy())
            recovered_bits_by_codeword.append(np.asarray(recovered_bits, dtype=np.uint8).copy())
            codeword_crc_ok.append(bool(crc_ok))

            if decode_trace is not None:
                cw_rate_recovered = (
                    np.concatenate(decode_trace.rate_recovered_blocks)
                    if decode_trace.rate_recovered_blocks
                    else np.array([], dtype=np.float64)
                )
                cw_decoder_input = (
                    np.concatenate(decode_trace.decoder_input_blocks)
                    if decode_trace.decoder_input_blocks
                    else np.array([], dtype=np.float64)
                )
                rate_recovered_code_blocks.extend(block.copy() for block in decode_trace.rate_recovered_blocks)
                decoder_input_code_blocks.extend(block.copy() for block in decode_trace.decoder_input_blocks)
                recovered_code_blocks.extend(block.copy() for block in decode_trace.recovered_code_blocks)
                code_block_crc_ok.extend(bool(value) for value in decode_trace.code_block_crc_ok)
            else:
                cw_rate_recovered = rate_recovered_llrs.copy()
                cw_decoder_input = rate_recovered_llrs.copy()

            rate_recovered_llrs_by_codeword.append(cw_rate_recovered.copy())
            decoder_input_llrs_by_codeword.append(cw_decoder_input.copy())

        concat_float = lambda values: np.concatenate(values) if values else np.array([], dtype=np.float64)
        concat_bits = lambda values: np.concatenate(values) if values else np.array([], dtype=np.uint8)
        return {
            "llrs": concat_float(llrs_by_codeword),
            "descrambled_llrs": concat_float(descrambled_llrs_by_codeword),
            "rate_recovered_llrs": concat_float(rate_recovered_llrs_by_codeword),
            "decoder_input_llrs": concat_float(decoder_input_llrs_by_codeword),
            "recovered_bits": concat_bits(recovered_bits_by_codeword),
            "crc_ok": bool(all(codeword_crc_ok)),
            "recovered_bits_by_codeword": tuple(block.copy() for block in recovered_bits_by_codeword),
            "llrs_by_codeword": tuple(block.copy() for block in llrs_by_codeword),
            "descrambled_llrs_by_codeword": tuple(block.copy() for block in descrambled_llrs_by_codeword),
            "rate_recovered_llrs_by_codeword": tuple(block.copy() for block in rate_recovered_llrs_by_codeword),
            "decoder_input_llrs_by_codeword": tuple(block.copy() for block in decoder_input_llrs_by_codeword),
            "rate_recovered_code_blocks": tuple(block.copy() for block in rate_recovered_code_blocks),
            "decoder_input_code_blocks": tuple(block.copy() for block in decoder_input_code_blocks),
            "recovered_code_blocks": tuple(block.copy() for block in recovered_code_blocks),
            "code_block_crc_ok": tuple(code_block_crc_ok),
            "codeword_crc_ok": tuple(codeword_crc_ok),
        }

    def _ofdm_demodulate(self, waveform: np.ndarray, tx_metadata: TxMetadata, timing_offset: int) -> Dict[str, np.ndarray]:
        numerology = tx_metadata.numerology
        grid = ResourceGrid(numerology, tx_metadata.allocation, spatial_layout=tx_metadata.spatial_layout)
        symbol_length = numerology.fft_size + numerology.cp_length
        samples_needed = numerology.symbols_per_slot * symbol_length
        waveform_tensor = np.asarray(waveform, dtype=np.complex128)
        if waveform_tensor.ndim == 1:
            waveform_tensor = waveform_tensor[None, :]
        rx_ants = min(waveform_tensor.shape[0], tx_metadata.spatial_layout.num_rx_antennas)
        cp_removed_tensor = np.zeros(
            (tx_metadata.spatial_layout.num_rx_antennas, numerology.symbols_per_slot, numerology.fft_size),
            dtype=np.complex128,
        )
        fft_bins_tensor = np.zeros(
            (tx_metadata.spatial_layout.num_rx_antennas, numerology.symbols_per_slot, numerology.fft_size),
            dtype=np.complex128,
        )
        for rx_ant in range(rx_ants):
            aligned = waveform_tensor[rx_ant, timing_offset : timing_offset + samples_needed]
            if aligned.size < samples_needed:
                aligned = np.pad(aligned, (0, samples_needed - aligned.size))
            for symbol in range(numerology.symbols_per_slot):
                start = symbol * symbol_length
                block = aligned[start : start + symbol_length]
                no_cp = block[numerology.cp_length :]
                cp_removed_tensor[rx_ant, symbol] = no_cp
                fft_bins = np.fft.fft(no_cp, n=numerology.fft_size)
                fft_bins_tensor[rx_ant, symbol] = fft_bins
                grid.rx_grid_tensor[rx_ant, symbol] = grid.ifft_bins_to_active(fft_bins)
        return {
            "cp_removed_tensor": cp_removed_tensor,
            "fft_bins_tensor": fft_bins_tensor,
            "rx_grid_tensor": grid.rx_grid_tensor,
        }

    def _receive_prach(
        self,
        *,
        tx_metadata: TxMetadata,
        channel_state: Dict,
        corrected: np.ndarray,
        cp_removed_tensor: np.ndarray,
        fft_bins_tensor: np.ndarray,
        rx_grid_tensor: np.ndarray,
        timing_offset: int,
        cfo_estimate_hz: float,
    ) -> RxResult:
        rx_grid = rx_grid_tensor[0]
        positions = tx_metadata.mapping.positions
        rx_symbols = rx_grid[positions[:, 0], positions[:, 1]] if positions.size else np.array([], dtype=np.complex128)
        reference_sequence = (
            np.asarray(tx_metadata.prach_sequence, dtype=np.complex128).reshape(-1)
            if tx_metadata.prach_sequence is not None
            else np.array([], dtype=np.complex128)
        )

        if bool(self.config.get("receiver", {}).get("perfect_channel_estimation", False)) and "reference_channel_grid" in channel_state:
            channel_estimate = np.asarray(channel_state["reference_channel_grid"], dtype=np.complex128)
            h_symbols = channel_estimate[positions[:, 0], positions[:, 1]] if positions.size else np.array([], dtype=np.complex128)
            channel_est_mse = 0.0
        else:
            if rx_symbols.size and reference_sequence.size:
                ls_symbols = rx_symbols / np.where(np.abs(reference_sequence) > 1e-9, reference_sequence, 1.0)
                flat_estimate = np.mean(ls_symbols)
            else:
                flat_estimate = 1.0 + 0.0j
            channel_estimate = np.full_like(rx_grid, flat_estimate, dtype=np.complex128)
            reference = np.asarray(channel_state.get("reference_channel_grid", channel_estimate), dtype=np.complex128)
            channel_est_mse = channel_mse(channel_estimate, reference)
            h_symbols = channel_estimate[positions[:, 0], positions[:, 1]] if positions.size else np.array([], dtype=np.complex128)

        equalized = (
            rx_symbols / np.where(np.abs(h_symbols) > 1e-9, h_symbols, 1.0 + 0.0j)
            if rx_symbols.size
            else np.array([], dtype=np.complex128)
        )

        prach_cfg = self.config.get("prach", {})
        detection = detect_prach_preamble(
            equalized,
            num_preambles=int(prach_cfg.get("num_preambles", 64)),
            root_sequence_index=int(tx_metadata.prach_root_sequence_index or prach_cfg.get("root_sequence_index", 25)),
            cyclic_shift=int(tx_metadata.prach_cyclic_shift or prach_cfg.get("cyclic_shift", 13)),
            threshold=float(prach_cfg.get("detection_threshold", 0.45)),
        )
        recovered_bits = preamble_id_to_bits(
            detection.detected_preamble_id,
            width=int(prach_cfg.get("preamble_id_bits", tx_metadata.payload_bits.size or 6)),
        )
        expected_preamble_id = int(tx_metadata.prach_preamble_id or 0)
        crc_ok = bool(detection.detected and detection.detected_preamble_id == expected_preamble_id)
        evm = error_vector_magnitude(reference_sequence, equalized) if reference_sequence.size else 0.0
        est_snr = estimate_snr_db(reference_sequence, equalized - reference_sequence) if reference_sequence.size else float("-inf")
        kpis = LinkKpiSummary(
            ber=bit_error_rate(tx_metadata.payload_bits, recovered_bits),
            bler=block_error_rate(crc_ok),
            evm=evm,
            throughput_bps=0.0,
            spectral_efficiency_bps_hz=0.0,
            estimated_snr_db=est_snr,
            crc_ok=crc_ok,
            channel_estimation_mse=channel_est_mse,
            synchronization_error_samples=float(timing_offset - int(channel_state.get("sto_samples", 0))),
            extra={
                "cfo_estimate_hz": cfo_estimate_hz,
                "prach_detected": 1.0 if detection.detected else 0.0,
                "prach_detection_metric": float(detection.metric),
                "prach_detected_preamble_id": float(detection.detected_preamble_id),
                "prach_expected_preamble_id": float(expected_preamble_id),
            },
        )
        return RxResult(
            recovered_bits=recovered_bits,
            crc_ok=crc_ok,
            corrected_waveform=corrected,
            spatial_layout=tx_metadata.spatial_layout,
            tensor_view_specs={
                "cp_removed_tensor": {
                    "name": "cp_removed_tensor",
                    "axes": ["rx_ant", "symbol", "sample"],
                    "shape": [int(dim) for dim in cp_removed_tensor.shape],
                    "description": "Per-receive-antenna OFDM symbols after cyclic-prefix removal.",
                },
                "fft_bins_tensor": {
                    "name": "fft_bins_tensor",
                    "axes": ["rx_ant", "symbol", "fft_bin"],
                    "shape": [int(dim) for dim in fft_bins_tensor.shape],
                    "description": "Per-receive-antenna FFT bins before active-subcarrier extraction.",
                },
                "rx_grid_tensor": {
                    "name": "rx_grid_tensor",
                    "axes": ["rx_ant", "symbol", "subcarrier"],
                    "shape": [int(dim) for dim in rx_grid_tensor.shape],
                    "description": "Per-receive-antenna FFT grid.",
                },
            },
            cp_removed_tensor=cp_removed_tensor,
            fft_bins_tensor=fft_bins_tensor,
            rx_grid_tensor=rx_grid_tensor,
            rx_grid=rx_grid,
            re_data_positions=positions,
            re_data_symbols=rx_symbols,
            re_dmrs_positions=np.zeros((0, 2), dtype=int),
            re_dmrs_symbols=np.array([], dtype=np.complex128),
            re_csi_rs_positions=np.zeros((0, 2), dtype=int),
            re_csi_rs_symbols=np.array([], dtype=np.complex128),
            re_srs_positions=np.zeros((0, 2), dtype=int),
            re_srs_symbols=np.array([], dtype=np.complex128),
            re_ptrs_positions=np.zeros((0, 2), dtype=int),
            re_ptrs_symbols=np.array([], dtype=np.complex128),
            re_ssb_positions=np.zeros((0, 2), dtype=int),
            re_ssb_symbols=np.array([], dtype=np.complex128),
            re_pbch_dmrs_positions=np.zeros((0, 2), dtype=int),
            re_pbch_dmrs_symbols=np.array([], dtype=np.complex128),
            channel_tensor=np.ones((1, 1, tx_metadata.numerology.symbols_per_slot, tx_metadata.numerology.active_subcarriers), dtype=np.complex128),
            effective_channel_tensor=np.ones((1, 1, tx_metadata.numerology.symbols_per_slot, tx_metadata.numerology.active_subcarriers), dtype=np.complex128),
            rx_port_symbols=equalized.reshape(1, -1),
            equalized_port_symbols=equalized.reshape(1, -1),
            rx_layer_symbols=equalized.reshape(1, -1),
            equalized_layer_symbols=equalized.reshape(1, -1),
            detected_layer_symbols=equalized.reshape(1, -1),
            rx_symbols=rx_symbols,
            equalized_symbols=equalized,
            detected_symbols=equalized.copy(),
            channel_estimate=channel_estimate,
            llrs=np.array([], dtype=np.float64),
            descrambled_llrs=np.array([], dtype=np.float64),
            rate_recovered_llrs=np.array([], dtype=np.float64),
            decoder_input_llrs=np.array([], dtype=np.float64),
            recovered_bits_by_codeword=(recovered_bits.copy(),),
            llrs_by_codeword=(),
            descrambled_llrs_by_codeword=(),
            rate_recovered_llrs_by_codeword=(),
            decoder_input_llrs_by_codeword=(),
            rate_recovered_code_blocks=(),
            decoder_input_code_blocks=(),
            recovered_code_blocks=(),
            code_block_crc_ok=(),
            codeword_crc_ok=(crc_ok,),
            timing_offset=timing_offset,
            cfo_estimate_hz=cfo_estimate_hz,
            kpis=kpis,
            prach_reference_sequence=reference_sequence,
            prach_candidate_metrics=detection.candidate_metrics,
            detected_preamble_id=int(detection.detected_preamble_id),
            prach_detection_metric=float(detection.metric),
        )

    def receive(self, waveform: np.ndarray, tx_metadata: TxMetadata, channel_state: Dict | None = None) -> RxResult:
        receiver_cfg = self.config.get("receiver", {})
        channel_state = channel_state or {}
        numerology = tx_metadata.numerology
        waveform_tensor = np.asarray(waveform, dtype=np.complex128)
        if waveform_tensor.ndim == 1:
            waveform_tensor = waveform_tensor[None, :]
        sync_waveform = waveform_tensor[0]

        if bool(receiver_cfg.get("perfect_sync", False)):
            timing_offset = max(0, int(channel_state.get("sto_samples", 0)))
            cfo_estimate_hz = float(channel_state.get("cfo_hz", 0.0))
        else:
            timing_offset = estimate_symbol_timing(
                sync_waveform,
                fft_size=numerology.fft_size,
                cp_length=numerology.cp_length,
                search_window=int(receiver_cfg.get("timing_search_window", 2 * numerology.cp_length)),
            )
            cfo_estimate_hz = estimate_cfo_from_cp(
                sync_waveform[timing_offset:],
                fft_size=numerology.fft_size,
                cp_length=numerology.cp_length,
                sample_rate=numerology.sample_rate,
                symbols_to_average=int(receiver_cfg.get("cfo_symbols_to_average", 4)),
            )

        corrected_rows = [
            correct_cfo(row[timing_offset:], cfo_hz=cfo_estimate_hz, sample_rate=numerology.sample_rate)
            for row in waveform_tensor
        ]
        corrected = np.stack(corrected_rows, axis=0)
        demod_result = self._ofdm_demodulate(corrected, tx_metadata, timing_offset=0)
        cp_removed_tensor = demod_result["cp_removed_tensor"]
        fft_bins_tensor = demod_result["fft_bins_tensor"]
        rx_grid_tensor = demod_result["rx_grid_tensor"]
        rx_grid = rx_grid_tensor[0]

        if str(tx_metadata.channel_type).lower() == "prach":
            return self._receive_prach(
                tx_metadata=tx_metadata,
                channel_state=channel_state,
                corrected=corrected,
                cp_removed_tensor=cp_removed_tensor,
                fft_bins_tensor=fft_bins_tensor,
                rx_grid_tensor=rx_grid_tensor,
                timing_offset=timing_offset,
                cfo_estimate_hz=cfo_estimate_hz,
            )

        effective_dmrs_positions = np.asarray(tx_metadata.dmrs["positions"], dtype=int)
        effective_dmrs_symbols = np.asarray(tx_metadata.dmrs["symbols"], dtype=np.complex128)
        if str(tx_metadata.channel_type).lower() in {"pbch", "broadcast"} and not effective_dmrs_positions.size:
            effective_dmrs_positions = np.asarray(tx_metadata.ssb.get("pbch_dmrs_positions", np.zeros((0, 2), dtype=int)), dtype=int)
            effective_dmrs_symbols = np.asarray(tx_metadata.ssb.get("pbch_dmrs_symbols", np.array([], dtype=np.complex128)), dtype=np.complex128)

        channel_tensor_reference = np.asarray(
            channel_state.get(
                "reference_channel_tensor",
                np.ones((1, 1, numerology.symbols_per_slot, numerology.active_subcarriers), dtype=np.complex128),
            ),
            dtype=np.complex128,
        )
        if bool(receiver_cfg.get("perfect_channel_estimation", False)) and "reference_channel_grid" in channel_state:
            h_full = np.asarray(channel_state["reference_channel_grid"], dtype=np.complex128)
            h_tensor = channel_tensor_reference
            channel_est_mse = 0.0
        else:
            estimate = ls_estimate_from_dmrs(
                rx_grid=rx_grid,
                dmrs_positions=effective_dmrs_positions,
                dmrs_symbols=effective_dmrs_symbols,
            )
            h_full = estimate["h_full"]
            reference = np.asarray(channel_state.get("reference_channel_grid", h_full), dtype=np.complex128)
            channel_est_mse = channel_mse(h_full, reference)
            h_tensor = channel_tensor_reference

        positions = tx_metadata.mapping.positions
        port_count = min(int(tx_metadata.spatial_layout.num_ports), int(rx_grid_tensor.shape[0]))
        layer_count = min(int(tx_metadata.spatial_layout.num_layers), int(tx_metadata.precoder_matrix.shape[1]))
        repeated_positions = expand_positions_for_layers(
            positions,
            layer_count,
            total_symbols=tx_metadata.modulation_symbols.size,
        )
        rx_port_symbols = np.stack(
            [
                rx_grid_tensor[port_index, positions[:, 0], positions[:, 1]]
                for port_index in range(port_count)
            ],
            axis=0,
        ) if positions.size and port_count > 0 else np.zeros((port_count, 0), dtype=np.complex128)
        dmrs_positions = effective_dmrs_positions
        re_dmrs_symbols = (
            rx_grid[dmrs_positions[:, 0], dmrs_positions[:, 1]]
            if dmrs_positions.size
            else np.array([], dtype=np.complex128)
        )
        csi_rs_positions = np.asarray(tx_metadata.csi_rs["positions"], dtype=int)
        re_csi_rs_symbols = (
            rx_grid[csi_rs_positions[:, 0], csi_rs_positions[:, 1]]
            if csi_rs_positions.size
            else np.array([], dtype=np.complex128)
        )
        srs_positions = np.asarray(tx_metadata.srs["positions"], dtype=int)
        re_srs_symbols = (
            rx_grid[srs_positions[:, 0], srs_positions[:, 1]]
            if srs_positions.size
            else np.array([], dtype=np.complex128)
        )
        ptrs_positions = np.asarray(tx_metadata.ptrs["positions"], dtype=int)
        re_ptrs_symbols = (
            rx_grid[ptrs_positions[:, 0], ptrs_positions[:, 1]]
            if ptrs_positions.size
            else np.array([], dtype=np.complex128)
        )
        ssb_positions = np.asarray(tx_metadata.ssb["positions"], dtype=int)
        re_ssb_symbols = (
            rx_grid[ssb_positions[:, 0], ssb_positions[:, 1]]
            if ssb_positions.size
            else np.array([], dtype=np.complex128)
        )
        pbch_dmrs_positions = np.asarray(tx_metadata.ssb.get("pbch_dmrs_positions", np.zeros((0, 2), dtype=int)), dtype=int)
        re_pbch_dmrs_symbols = (
            rx_grid[pbch_dmrs_positions[:, 0], pbch_dmrs_positions[:, 1]]
            if pbch_dmrs_positions.size
            else np.array([], dtype=np.complex128)
        )
        h_symbols = h_full[positions[:, 0], positions[:, 1]]
        noise_variance = float(channel_state.get("noise_variance", 1e-3))
        detector_mode = str(receiver_cfg.get("mimo_detector", receiver_cfg.get("equalizer", "mmse"))).lower()
        if port_count > 1 or int(tx_metadata.spatial_layout.num_rx_antennas) > 1:
            equalized_port_symbols = np.zeros((port_count, positions.shape[0]), dtype=np.complex128)
            recovered_layer_symbols = np.zeros((layer_count, positions.shape[0]), dtype=np.complex128)
            for position_index, (symbol_index, subcarrier_index) in enumerate(positions):
                y_vector = rx_grid_tensor[: int(tx_metadata.spatial_layout.num_rx_antennas), symbol_index, subcarrier_index]
                h_port = h_tensor[
                    : int(tx_metadata.spatial_layout.num_rx_antennas),
                    :port_count,
                    symbol_index,
                    subcarrier_index,
                ]
                port_estimate = detect_layers(y_vector, h_port, noise_variance, detector_mode)
                equalized_port_symbols[:, position_index] = port_estimate
                recovered_layer_symbols[:, position_index] = recover_layers_from_ports(
                    port_estimate.reshape(-1, 1),
                    tx_metadata.precoder_matrix,
                ).reshape(-1)
        else:
            equalized_port_symbols = np.stack(
                [
                    equalize(
                        rx_symbols=rx_port_symbols[port_index],
                        channel_estimate=h_symbols,
                        noise_variance=noise_variance,
                        mode=str(receiver_cfg.get("equalizer", "mmse")),
                    )
                    for port_index in range(port_count)
                ],
                axis=0,
            ) if port_count > 0 else np.zeros((0, positions.shape[0]), dtype=np.complex128)
            if equalized_port_symbols.size:
                recovered_layer_symbols = recover_layers_from_ports(equalized_port_symbols, tx_metadata.precoder_matrix)
            else:
                recovered_layer_symbols = np.zeros((layer_count, positions.shape[0]), dtype=np.complex128)
        detected_layer_symbols = np.stack(
            [
                remove_transform_precoding(recovered_layer_symbols[layer_index])
                if bool(tx_metadata.transform_precoding_enabled) and str(tx_metadata.direction).lower() == "uplink"
                else recovered_layer_symbols[layer_index].copy()
                for layer_index in range(layer_count)
            ],
            axis=0,
        ) if layer_count > 0 else np.zeros((0, positions.shape[0]), dtype=np.complex128)
        rx_layer_symbols = recover_layers_from_ports(rx_port_symbols, tx_metadata.precoder_matrix) if rx_port_symbols.size else np.zeros((layer_count, positions.shape[0]), dtype=np.complex128)
        equalized_layer_symbols = recovered_layer_symbols
        rx_symbols = combine_layer_symbols(rx_layer_symbols, total_symbols=tx_metadata.modulation_symbols.size)
        equalized = combine_layer_symbols(equalized_layer_symbols, total_symbols=tx_metadata.modulation_symbols.size)
        detected_symbols = combine_layer_symbols(detected_layer_symbols, total_symbols=tx_metadata.modulation_symbols.size)
        codeword_decode = self._decode_codewords(
            detected_layer_symbols=detected_layer_symbols,
            noise_variance=noise_variance,
            tx_metadata=tx_metadata,
        )
        llrs = np.asarray(codeword_decode["llrs"], dtype=np.float64)
        descrambled_llrs = np.asarray(codeword_decode["descrambled_llrs"], dtype=np.float64)
        rate_recovered_llrs = np.asarray(codeword_decode["rate_recovered_llrs"], dtype=np.float64)
        decoder_input_llrs = np.asarray(codeword_decode["decoder_input_llrs"], dtype=np.float64)
        recovered_bits = np.asarray(codeword_decode["recovered_bits"], dtype=np.uint8)
        crc_ok = bool(codeword_decode["crc_ok"])
        recovered_bits_by_codeword = tuple(codeword_decode["recovered_bits_by_codeword"])
        llrs_by_codeword = tuple(codeword_decode["llrs_by_codeword"])
        descrambled_llrs_by_codeword = tuple(codeword_decode["descrambled_llrs_by_codeword"])
        rate_recovered_llrs_by_codeword = tuple(codeword_decode["rate_recovered_llrs_by_codeword"])
        decoder_input_llrs_by_codeword = tuple(codeword_decode["decoder_input_llrs_by_codeword"])
        rate_recovered_code_blocks = tuple(codeword_decode["rate_recovered_code_blocks"])
        decoder_input_code_blocks = tuple(codeword_decode["decoder_input_code_blocks"])
        recovered_code_blocks = tuple(codeword_decode["recovered_code_blocks"])
        code_block_crc_ok = tuple(codeword_decode["code_block_crc_ok"])
        codeword_crc_ok = tuple(codeword_decode["codeword_crc_ok"])

        reference_symbols = tx_metadata.modulation_symbols
        ber = bit_error_rate(tx_metadata.payload_bits, recovered_bits)
        evm = error_vector_magnitude(reference_symbols, equalized)
        slot_duration_s = numerology.slot_length_samples / numerology.sample_rate
        bandwidth_hz = self.config.get("carrier", {}).get(
            "bandwidth_hz", numerology.active_subcarriers * numerology.subcarrier_spacing_hz
        )
        throughput = throughput_bps(recovered_bits.size, slot_duration_s=slot_duration_s, crc_ok=crc_ok)
        spectral_efficiency = spectral_efficiency_bps_hz(throughput=throughput, bandwidth_hz=float(bandwidth_hz))
        est_snr = estimate_snr_db(reference_symbols, equalized - reference_symbols)
        effective_channel_tensor = np.einsum("rpsf,pl->rlsf", h_tensor[:, :port_count, :, :], tx_metadata.precoder_matrix[:port_count, :layer_count])

        kpis = LinkKpiSummary(
            ber=ber,
            bler=block_error_rate(crc_ok),
            evm=evm,
            throughput_bps=throughput,
            spectral_efficiency_bps_hz=spectral_efficiency,
            estimated_snr_db=est_snr,
            crc_ok=crc_ok,
            channel_estimation_mse=channel_est_mse,
            synchronization_error_samples=float(timing_offset - int(channel_state.get("sto_samples", 0))),
            extra={"cfo_estimate_hz": cfo_estimate_hz, "mimo_detector": detector_mode},
        )

        return RxResult(
            recovered_bits=recovered_bits,
            crc_ok=crc_ok,
            corrected_waveform=corrected,
            spatial_layout=tx_metadata.spatial_layout,
            tensor_view_specs={
                "cp_removed_tensor": {
                    "name": "cp_removed_tensor",
                    "axes": ["rx_ant", "symbol", "sample"],
                    "shape": [int(dim) for dim in cp_removed_tensor.shape],
                    "description": "Per-receive-antenna OFDM symbols after cyclic-prefix removal.",
                },
                "fft_bins_tensor": {
                    "name": "fft_bins_tensor",
                    "axes": ["rx_ant", "symbol", "fft_bin"],
                    "shape": [int(dim) for dim in fft_bins_tensor.shape],
                    "description": "Per-receive-antenna FFT bins before active-subcarrier extraction.",
                },
                "rx_grid_tensor": {
                    "name": "rx_grid_tensor",
                    "axes": ["rx_ant", "symbol", "subcarrier"],
                    "shape": [int(dim) for dim in rx_grid_tensor.shape],
                    "description": "Per-receive-antenna FFT grid.",
                }
            },
            cp_removed_tensor=cp_removed_tensor,
            fft_bins_tensor=fft_bins_tensor,
            rx_grid_tensor=rx_grid_tensor,
            rx_grid=rx_grid,
            re_data_positions=repeated_positions,
            re_data_symbols=rx_symbols,
            re_dmrs_positions=dmrs_positions,
            re_dmrs_symbols=re_dmrs_symbols,
            re_csi_rs_positions=csi_rs_positions,
            re_csi_rs_symbols=re_csi_rs_symbols,
            re_srs_positions=srs_positions,
            re_srs_symbols=re_srs_symbols,
            re_ptrs_positions=ptrs_positions,
            re_ptrs_symbols=re_ptrs_symbols,
            re_ssb_positions=ssb_positions,
            re_ssb_symbols=re_ssb_symbols,
            re_pbch_dmrs_positions=pbch_dmrs_positions,
            re_pbch_dmrs_symbols=re_pbch_dmrs_symbols,
            channel_tensor=h_tensor,
            effective_channel_tensor=effective_channel_tensor,
            rx_port_symbols=rx_port_symbols,
            equalized_port_symbols=equalized_port_symbols,
            rx_layer_symbols=rx_layer_symbols,
            equalized_layer_symbols=equalized_layer_symbols,
            detected_layer_symbols=detected_layer_symbols,
            rx_symbols=rx_symbols,
            equalized_symbols=equalized,
            detected_symbols=detected_symbols,
            channel_estimate=h_full,
            llrs=llrs,
            descrambled_llrs=descrambled_llrs,
            rate_recovered_llrs=rate_recovered_llrs,
            decoder_input_llrs=decoder_input_llrs,
            recovered_bits_by_codeword=recovered_bits_by_codeword,
            llrs_by_codeword=llrs_by_codeword,
            descrambled_llrs_by_codeword=descrambled_llrs_by_codeword,
            rate_recovered_llrs_by_codeword=rate_recovered_llrs_by_codeword,
            decoder_input_llrs_by_codeword=decoder_input_llrs_by_codeword,
            rate_recovered_code_blocks=rate_recovered_code_blocks,
            decoder_input_code_blocks=decoder_input_code_blocks,
            recovered_code_blocks=recovered_code_blocks,
            code_block_crc_ok=code_block_crc_ok,
            codeword_crc_ok=codeword_crc_ok,
            timing_offset=timing_offset,
            cfo_estimate_hz=cfo_estimate_hz,
            kpis=kpis,
        )
