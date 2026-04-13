from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from .channel_estimation import channel_mse, ls_estimate_from_dmrs
from .coding import build_channel_coder
from .equalization import equalize
from .kpi import (
    LinkKpiSummary,
    bit_error_rate,
    block_error_rate,
    error_vector_magnitude,
    estimate_snr_db,
    spectral_efficiency_bps_hz,
    throughput_bps,
)
from .resource_grid import ResourceGrid
from .scrambling import descramble_llrs
from .synchronization import correct_cfo, estimate_cfo_from_cp, estimate_symbol_timing
from .transmitter import TxMetadata


@dataclass(slots=True)
class RxResult:
    recovered_bits: np.ndarray
    crc_ok: bool
    corrected_waveform: np.ndarray
    spatial_layout: object
    tensor_view_specs: Dict[str, Dict[str, object]]
    rx_grid_tensor: np.ndarray
    rx_grid: np.ndarray
    rx_symbols: np.ndarray
    equalized_symbols: np.ndarray
    channel_estimate: np.ndarray
    llrs: np.ndarray
    descrambled_llrs: np.ndarray
    timing_offset: int
    cfo_estimate_hz: float
    kpis: LinkKpiSummary


class NrReceiver:
    def __init__(self, config: Dict) -> None:
        self.config = config

    def _ofdm_demodulate(self, waveform: np.ndarray, tx_metadata: TxMetadata, timing_offset: int) -> np.ndarray:
        numerology = tx_metadata.numerology
        grid = ResourceGrid(numerology, tx_metadata.allocation, spatial_layout=tx_metadata.spatial_layout)
        symbol_length = numerology.fft_size + numerology.cp_length
        samples_needed = numerology.symbols_per_slot * symbol_length
        waveform_tensor = np.asarray(waveform, dtype=np.complex128)
        if waveform_tensor.ndim == 1:
            waveform_tensor = waveform_tensor[None, :]
        rx_ants = min(waveform_tensor.shape[0], tx_metadata.spatial_layout.num_rx_antennas)
        for rx_ant in range(rx_ants):
            aligned = waveform_tensor[rx_ant, timing_offset : timing_offset + samples_needed]
            if aligned.size < samples_needed:
                aligned = np.pad(aligned, (0, samples_needed - aligned.size))
            for symbol in range(numerology.symbols_per_slot):
                start = symbol * symbol_length
                block = aligned[start : start + symbol_length]
                no_cp = block[numerology.cp_length :]
                fft_bins = np.fft.fft(no_cp, n=numerology.fft_size)
                grid.rx_grid_tensor[rx_ant, symbol] = grid.ifft_bins_to_active(fft_bins)
        return grid.rx_grid_tensor

    def receive(self, waveform: np.ndarray, tx_metadata: TxMetadata, channel_state: Dict | None = None) -> RxResult:
        receiver_cfg = self.config.get("receiver", {})
        channel_state = channel_state or {}
        numerology = tx_metadata.numerology

        if bool(receiver_cfg.get("perfect_sync", False)):
            timing_offset = max(0, int(channel_state.get("sto_samples", 0)))
            cfo_estimate_hz = float(channel_state.get("cfo_hz", 0.0))
        else:
            timing_offset = estimate_symbol_timing(
                waveform,
                fft_size=numerology.fft_size,
                cp_length=numerology.cp_length,
                search_window=int(receiver_cfg.get("timing_search_window", 2 * numerology.cp_length)),
            )
            cfo_estimate_hz = estimate_cfo_from_cp(
                waveform[timing_offset:],
                fft_size=numerology.fft_size,
                cp_length=numerology.cp_length,
                sample_rate=numerology.sample_rate,
                symbols_to_average=int(receiver_cfg.get("cfo_symbols_to_average", 4)),
            )

        corrected = correct_cfo(waveform[timing_offset:], cfo_hz=cfo_estimate_hz, sample_rate=numerology.sample_rate)
        rx_grid_tensor = self._ofdm_demodulate(corrected, tx_metadata, timing_offset=0)
        rx_grid = rx_grid_tensor[0]

        if bool(receiver_cfg.get("perfect_channel_estimation", False)) and "reference_channel_grid" in channel_state:
            h_full = np.asarray(channel_state["reference_channel_grid"], dtype=np.complex128)
            channel_est_mse = 0.0
        else:
            estimate = ls_estimate_from_dmrs(
                rx_grid=rx_grid,
                dmrs_positions=tx_metadata.dmrs["positions"],
                dmrs_symbols=tx_metadata.dmrs["symbols"],
            )
            h_full = estimate["h_full"]
            reference = np.asarray(channel_state.get("reference_channel_grid", h_full), dtype=np.complex128)
            channel_est_mse = channel_mse(h_full, reference)

        positions = tx_metadata.mapping.positions
        rx_symbols = rx_grid[positions[:, 0], positions[:, 1]]
        h_symbols = h_full[positions[:, 0], positions[:, 1]]
        noise_variance = float(channel_state.get("noise_variance", 1e-3))
        equalized = equalize(
            rx_symbols=rx_symbols,
            channel_estimate=h_symbols,
            noise_variance=noise_variance,
            mode=str(receiver_cfg.get("equalizer", "mmse")),
        )
        llrs = tx_metadata.mapper.demap_llr(equalized, noise_variance=max(noise_variance, 1e-9))
        descrambled_llrs = descramble_llrs(llrs, tx_metadata.scrambling_sequence)

        coder = build_channel_coder(channel_type=tx_metadata.channel_type, config=self.config)
        recovered_bits, crc_ok = coder.decode(descrambled_llrs, tx_metadata.coding_metadata)

        reference_symbols = tx_metadata.tx_grid[positions[:, 0], positions[:, 1]]
        ber = bit_error_rate(tx_metadata.payload_bits, recovered_bits)
        evm = error_vector_magnitude(reference_symbols, equalized)
        slot_duration_s = numerology.slot_length_samples / numerology.sample_rate
        bandwidth_hz = self.config.get("carrier", {}).get(
            "bandwidth_hz", numerology.active_subcarriers * numerology.subcarrier_spacing_hz
        )
        throughput = throughput_bps(recovered_bits.size, slot_duration_s=slot_duration_s, crc_ok=crc_ok)
        spectral_efficiency = spectral_efficiency_bps_hz(throughput=throughput, bandwidth_hz=float(bandwidth_hz))
        est_snr = estimate_snr_db(reference_symbols, equalized - reference_symbols)

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
            extra={"cfo_estimate_hz": cfo_estimate_hz},
        )

        return RxResult(
            recovered_bits=recovered_bits,
            crc_ok=crc_ok,
            corrected_waveform=corrected,
            spatial_layout=tx_metadata.spatial_layout,
            tensor_view_specs={
                "rx_grid_tensor": {
                    "name": "rx_grid_tensor",
                    "axes": ["rx_ant", "symbol", "subcarrier"],
                    "shape": [int(dim) for dim in rx_grid_tensor.shape],
                    "description": "Per-receive-antenna FFT grid.",
                }
            },
            rx_grid_tensor=rx_grid_tensor,
            rx_grid=rx_grid,
            rx_symbols=rx_symbols,
            equalized_symbols=equalized,
            channel_estimate=h_full,
            llrs=llrs,
            descrambled_llrs=descrambled_llrs,
            timing_offset=timing_offset,
            cfo_estimate_hz=cfo_estimate_hz,
            kpis=kpis,
        )
