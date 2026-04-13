from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import numpy as np

from channel.awgn_channel import AWGNChannel
from channel.doppler import apply_doppler_rotation
from channel.fading_channel import FadingChannel
from channel.impairments import apply_impairments
from phy.artifacts import normalize_pipeline_stage
from phy.context import SlotContext
from phy.kpi import LinkKpiSummary, bit_error_rate, spectral_efficiency_bps_hz
from phy.receiver import NrReceiver
from phy.transmitter import NrTransmitter
from utils.file_transfer import (
    build_file_payload_package,
    chunk_bitstream,
    file_preview_text,
    join_valid_chunks,
    restore_file_from_package_bits,
)


def _reference_channel_grid(tx_metadata, frequency_response: np.ndarray) -> np.ndarray:
    grid = np.ones_like(tx_metadata.tx_grid)
    center = tx_metadata.numerology.fft_size // 2
    left = tx_metadata.numerology.active_subcarriers // 2
    right = tx_metadata.numerology.active_subcarriers - left
    active = np.concatenate(
        [
            frequency_response[center - left : center],
            frequency_response[center + 1 : center + 1 + right],
        ]
    )
    grid[:] = active[None, :]
    return grid


def _payload_size_bits_for_channel(config: Dict, channel_type: str) -> int:
    if channel_type.lower() in {"control", "pdcch"}:
        return int(config.get("control_channel", {}).get("payload_bits", 128))
    return int(config.get("transport_block", {}).get("size_bits", 1024))


def _slot_context(numerology, timeline_index: int) -> Dict[str, int | str]:
    slots_per_frame = max(int(getattr(numerology, "slots_per_frame", 1)), 1)
    return SlotContext(
        timeline_index=int(timeline_index),
        frame_index=int(timeline_index) // slots_per_frame,
        slot_index=int(timeline_index) % slots_per_frame,
        slots_per_frame=slots_per_frame,
    ).as_dict()


def _annotate_result_slot(result: Dict[str, Any], timeline_index: int) -> Dict[str, Any]:
    result["slot_context"] = _slot_context(result["tx"].metadata.numerology, timeline_index)
    return result


def _normalize_pipeline(pipeline: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return [normalize_pipeline_stage(stage) for stage in pipeline]


def _aggregate_slot_sequence_kpis(slot_results: list[Dict[str, Any]]) -> LinkKpiSummary:
    if not slot_results:
        raise ValueError("slot_results must contain at least one slot result.")

    kpi_dicts = [entry["rx"].kpis.as_dict() for entry in slot_results]
    mean_metric = lambda key: float(np.mean([float(metrics[key]) for metrics in kpi_dicts if key in metrics]))
    extra_keys = sorted({key for metrics in kpi_dicts for key in metrics.keys()})
    extra = {
        key: mean_metric(key)
        for key in extra_keys
        if key
        not in {
            "ber",
            "bler",
            "evm",
            "throughput_bps",
            "spectral_efficiency_bps_hz",
            "estimated_snr_db",
            "crc_ok",
            "channel_estimation_mse",
            "synchronization_error_samples",
        }
    }
    extra["captured_slots"] = float(len(slot_results))
    extra["slots_crc_passed"] = float(sum(1 for entry in slot_results if entry["rx"].crc_ok))
    return LinkKpiSummary(
        ber=mean_metric("ber"),
        bler=mean_metric("bler"),
        evm=mean_metric("evm"),
        throughput_bps=mean_metric("throughput_bps"),
        spectral_efficiency_bps_hz=mean_metric("spectral_efficiency_bps_hz"),
        estimated_snr_db=mean_metric("estimated_snr_db"),
        crc_ok=all(entry["rx"].crc_ok for entry in slot_results),
        channel_estimation_mse=mean_metric("channel_estimation_mse") if any("channel_estimation_mse" in metrics for metrics in kpi_dicts) else None,
        synchronization_error_samples=mean_metric("synchronization_error_samples")
        if any("synchronization_error_samples" in metrics for metrics in kpi_dicts)
        else None,
        extra=extra,
    )


def _aggregate_file_transfer_kpis(
    *,
    config: Dict,
    reference_bits: np.ndarray,
    recovered_bits: np.ndarray,
    chunk_results: list[Dict],
    chunk_valid_bits: list[int],
    transfer_success: bool,
    sha256_match: bool,
) -> LinkKpiSummary:
    rx_results = [entry["rx"] for entry in chunk_results]
    tx_meta = chunk_results[0]["tx"].metadata
    numerology = tx_meta.numerology
    slot_duration_s = numerology.slot_length_samples / numerology.sample_rate
    total_time_s = max(slot_duration_s * len(chunk_results), slot_duration_s)
    delivered_bits = float(sum(valid_bits for valid_bits, entry in zip(chunk_valid_bits, rx_results) if entry.crc_ok))
    throughput = delivered_bits / total_time_s if transfer_success else 0.0
    bandwidth_hz = float(
        config.get("carrier", {}).get("bandwidth_hz", numerology.active_subcarriers * numerology.subcarrier_spacing_hz)
    )
    return LinkKpiSummary(
        ber=bit_error_rate(reference_bits, recovered_bits),
        bler=float(np.mean([0.0 if result.crc_ok else 1.0 for result in rx_results])),
        evm=float(np.mean([result.kpis.evm for result in rx_results])),
        throughput_bps=throughput,
        spectral_efficiency_bps_hz=spectral_efficiency_bps_hz(throughput=throughput, bandwidth_hz=bandwidth_hz),
        estimated_snr_db=float(np.mean([result.kpis.estimated_snr_db for result in rx_results])),
        crc_ok=transfer_success,
        channel_estimation_mse=float(np.mean([result.kpis.channel_estimation_mse or 0.0 for result in rx_results])),
        synchronization_error_samples=float(
            np.mean([result.kpis.synchronization_error_samples or 0.0 for result in rx_results])
        ),
        extra={
            "file_transfer_success": 1.0 if transfer_success else 0.0,
            "sha256_match": 1.0 if sha256_match else 0.0,
            "chunks_total": float(len(chunk_results)),
            "chunks_failed": float(sum(not result.crc_ok for result in rx_results)),
            "package_size_bytes": float(len(reference_bits) // 8),
        },
    )


def _file_transfer_pipeline_stages(
    *,
    package,
    transfer_summary: Dict,
) -> tuple[Dict, Dict]:
    tx_stage = {
        "section": "TX",
        "stage": "File source + packaging",
        "domain": "bits",
        "preview_kind": "text",
        "description": "Selected source file is serialized into a binary package, converted to a bitstream, and segmented into transport blocks.",
        "data": (
            f"Source file: {package.filename}\n"
            f"Media kind: {package.media_kind}\n"
            f"MIME type: {package.mime_type}\n"
            f"Source bytes: {len(package.payload_bytes)}\n"
            f"Package bytes: {len(package.package_bytes)}\n"
            f"Total chunks: {transfer_summary['total_chunks']}\n"
            f"TX preview:\n{file_preview_text(package.media_kind, package.payload_bytes)}"
        ),
    }
    rx_stage = {
        "section": "RX",
        "stage": "File reassembly + write",
        "domain": "bits",
        "preview_kind": "text",
        "description": "Recovered chunk payloads are concatenated, parsed back into the original file package, and written to disk at the RX side.",
        "data": (
            f"Transfer success: {transfer_summary['success']}\n"
            f"CRC-passing chunks: {transfer_summary['chunks_passed']} / {transfer_summary['total_chunks']}\n"
            f"SHA-256 match: {transfer_summary['sha256_match']}\n"
            f"Restored path: {transfer_summary.get('restored_file_path', 'n/a')}\n"
            f"RX preview:\n{transfer_summary.get('restored_preview', 'n/a')}"
        ),
    }
    normalized = _normalize_pipeline([tx_stage, rx_stage])
    return normalized[0], normalized[1]


def _build_pipeline_trace(
    tx_result,
    rx_result,
    *,
    impaired_waveform: np.ndarray,
    channel_output_waveform: np.ndarray,
    rx_waveform: np.ndarray,
    channel_state: Dict,
) -> list[Dict]:
    tx_meta = tx_result.metadata
    rx_meta = rx_result
    direction = str(getattr(tx_meta, "direction", "downlink")).lower()
    direction_label = "uplink" if direction == "uplink" else "downlink"
    data_channel_label = "PUSCH-style" if direction == "uplink" else "PDSCH-style"
    coding_meta = tx_meta.coding_metadata
    transport_with_crc = (
        np.asarray(coding_meta.transport_block_with_crc, dtype=np.uint8)
        if coding_meta.transport_block_with_crc is not None
        else tx_meta.coded_bits
    )
    code_blocks_with_crc = (
        np.concatenate(coding_meta.code_blocks_with_crc)
        if coding_meta.code_blocks_with_crc
        else transport_with_crc
    )
    mother_bits = (
        np.concatenate(coding_meta.mother_code_blocks)
        if coding_meta.mother_code_blocks
        else tx_meta.coded_bits
    )

    gnuradio_used = bool(channel_state.get("gnu_radio_used", False))
    channel_stage_name = "GNU Radio loopback output" if gnuradio_used else "Fading / path loss / Doppler output"
    channel_stage_description = (
        "Waveform after GNU Radio loopback processing."
        if gnuradio_used
        else "Waveform after channel convolution, Doppler rotation, and large-scale loss."
    )

    stages = [
        {
            "section": "TX",
            "stage": "Traffic / transport block",
            "domain": "bits",
            "description": "Payload bits generated by the transmitter before CRC and channel coding.",
            "preview_kind": "bits",
            "data": tx_meta.payload_bits,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.payload_bits).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.payload_bits).shape],
            "notes": "Current runtime maps all content to codeword 0, layer 0, port 0.",
        },
        {
            "section": "TX",
            "stage": "TB CRC attachment",
            "domain": "bits",
            "description": "Transport-block CRC is appended before segmentation and channel coding.",
            "preview_kind": "bits",
            "data": transport_with_crc,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.payload_bits).shape],
            "output_shape": [int(dim) for dim in np.asarray(transport_with_crc).shape],
        },
        {
            "section": "TX",
            "stage": "Code block segmentation + CB CRC",
            "domain": "bits",
            "description": "The transport block is segmented into code blocks, and each block receives its own CRC when multiple blocks are present.",
            "preview_kind": "bits",
            "data": code_blocks_with_crc,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(transport_with_crc).shape],
            "output_shape": [int(dim) for dim in np.asarray(code_blocks_with_crc).shape],
        },
        {
            "section": "TX",
            "stage": "Channel coding",
            "domain": "bits",
            "description": "Simplified NR-inspired coding expands each code block into a mother-codeword segment.",
            "preview_kind": "bits",
            "data": mother_bits,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(code_blocks_with_crc).shape],
            "output_shape": [int(dim) for dim in np.asarray(mother_bits).shape],
        },
        {
            "section": "TX",
            "stage": "Rate matching",
            "domain": "bits",
            "description": "Mother-codeword segments are rate-matched onto the scheduled RE capacity.",
            "preview_kind": "bits",
            "data": tx_meta.coded_bits,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(mother_bits).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.coded_bits).shape],
        },
        {
            "section": "TX",
            "stage": "Scrambling",
            "domain": "bits",
            "description": "Scrambled bits ready for modulation mapping.",
            "preview_kind": "bits",
            "data": tx_meta.scrambled_bits,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.coded_bits).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.scrambled_bits).shape],
        },
        {
            "section": "TX",
            "stage": "Modulation mapping",
            "domain": "symbols",
            "description": f"Mapped {tx_meta.modulation} symbols before {direction_label} resource mapping.",
            "preview_kind": "constellation",
            "data": tx_meta.modulation_symbols,
            "artifact_type": "constellation",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.scrambled_bits).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.modulation_symbols).shape],
        },
        {
            "section": "TX",
            "stage": "Resource grid mapping",
            "domain": "grid",
            "description": f"Mapped {data_channel_label} symbols on the active NR-like resource grid before DMRS insertion.",
            "preview_kind": "grid",
            "data": tx_meta.tx_grid_data,
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_symbols).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid_data).shape],
        },
        {
            "section": "TX",
            "stage": "DMRS insertion",
            "domain": "grid",
            "description": "Resource grid after DMRS insertion on configured OFDM symbols.",
            "preview_kind": "grid",
            "data": tx_meta.tx_grid,
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid_data).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid).shape],
        },
        {
            "section": "TX",
            "stage": "OFDM modulation + CP",
            "domain": "waveform",
            "description": "Baseband transmit waveform after OFDM modulation and cyclic-prefix insertion.",
            "preview_kind": "waveform",
            "data": tx_result.waveform,
            "artifact_type": "waveform",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_result.waveform).shape],
        },
        {
            "section": "Channel",
            "stage": "RF/baseband impairments",
            "domain": "waveform",
            "description": "Waveform after STO, CFO, phase noise, and IQ imbalance.",
            "preview_kind": "waveform",
            "data": impaired_waveform,
            "artifact_type": "waveform",
            "input_shape": [int(dim) for dim in np.asarray(tx_result.waveform).shape],
            "output_shape": [int(dim) for dim in np.asarray(impaired_waveform).shape],
        },
        {
            "section": "Channel",
            "stage": channel_stage_name,
            "domain": "waveform",
            "description": channel_stage_description,
            "preview_kind": "waveform",
            "data": channel_output_waveform,
            "artifact_type": "waveform",
            "input_shape": [int(dim) for dim in np.asarray(impaired_waveform).shape],
            "output_shape": [int(dim) for dim in np.asarray(channel_output_waveform).shape],
        },
        {
            "section": "Channel",
            "stage": "AWGN / received waveform",
            "domain": "waveform",
            "description": "Final received waveform at the UE front-end before synchronization.",
            "preview_kind": "waveform",
            "data": rx_waveform,
            "artifact_type": "waveform",
            "input_shape": [int(dim) for dim in np.asarray(channel_output_waveform).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_waveform).shape],
        },
        {
            "section": "RX",
            "stage": "Timing / CFO correction",
            "domain": "waveform",
            "description": "Waveform after estimated timing alignment and CFO correction.",
            "preview_kind": "waveform",
            "data": rx_meta.corrected_waveform,
            "artifact_type": "waveform",
            "input_shape": [int(dim) for dim in np.asarray(rx_waveform).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.corrected_waveform).shape],
        },
        {
            "section": "RX",
            "stage": "Remove CP",
            "domain": "grid",
            "description": "Cyclic prefix removed from each corrected OFDM symbol before FFT.",
            "preview_kind": "grid",
            "data": np.abs(rx_meta.cp_removed_tensor[0]),
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.corrected_waveform).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.cp_removed_tensor[0]).shape],
        },
        {
            "section": "RX",
            "stage": "FFT",
            "domain": "grid",
            "description": "Per-symbol FFT bins before active-subcarrier extraction.",
            "preview_kind": "grid",
            "data": np.abs(rx_meta.fft_bins_tensor[0]),
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.cp_removed_tensor[0]).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.fft_bins_tensor[0]).shape],
        },
        {
            "section": "RX",
            "stage": "Resource element extraction",
            "domain": "symbols",
            "description": "Payload REs and DMRS REs extracted from the received active-subcarrier grid.",
            "preview_kind": "constellation",
            "data": rx_meta.re_data_symbols,
            "artifact_type": "constellation",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.rx_grid).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.re_data_symbols).shape],
        },
        {
            "section": "RX",
            "stage": "Channel estimation",
            "domain": "grid",
            "description": "Full-grid channel estimate derived from DMRS or injected reference channel state.",
            "preview_kind": "grid",
            "data": rx_meta.channel_estimate,
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.rx_grid).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.channel_estimate).shape],
        },
        {
            "section": "RX",
            "stage": "Pre-equalization symbol extraction",
            "domain": "symbols",
            "description": "Received data/control symbols extracted from scheduled resource elements before equalization.",
            "preview_kind": "constellation",
            "data": rx_meta.rx_symbols,
            "artifact_type": "constellation",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.rx_grid).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.rx_symbols).shape],
        },
        {
            "section": "RX",
            "stage": "Equalization",
            "domain": "symbols",
            "description": "Equalized symbols after MMSE/ZF equalization.",
            "preview_kind": "constellation",
            "data": rx_meta.equalized_symbols,
            "artifact_type": "constellation",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.rx_symbols).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.equalized_symbols).shape],
        },
        {
            "section": "RX",
            "stage": "Soft demapping",
            "domain": "llr",
            "description": "Soft demapper output in log-likelihood ratio form before descrambling.",
            "preview_kind": "llr",
            "data": rx_meta.llrs,
            "artifact_type": "llr",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.detected_symbols).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.llrs).shape],
        },
        {
            "section": "RX",
            "stage": "Descrambling",
            "domain": "llr",
            "description": "Descrambled LLR sequence passed into the channel decoder.",
            "preview_kind": "llr",
            "data": rx_meta.descrambled_llrs,
            "artifact_type": "llr",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.llrs).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.descrambled_llrs).shape],
        },
        {
            "section": "RX",
            "stage": "Rate recovery",
            "domain": "llr",
            "description": "Inverse rate matching reconstructs the mother-codeword-domain LLR stream.",
            "preview_kind": "llr",
            "data": rx_meta.rate_recovered_llrs,
            "artifact_type": "llr",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.descrambled_llrs).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.rate_recovered_llrs).shape],
        },
        {
            "section": "RX",
            "stage": "Soft LLR before decoding",
            "domain": "llr",
            "description": "Decoder-input LLR stream after descrambling and rate recovery.",
            "preview_kind": "llr",
            "data": rx_meta.decoder_input_llrs,
            "artifact_type": "llr",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.rate_recovered_llrs).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.decoder_input_llrs).shape],
        },
        {
            "section": "RX",
            "stage": "Decoding + CRC",
            "domain": "bits",
            "description": f"Recovered payload bits after decoding. CRC status: {'OK' if rx_meta.crc_ok else 'FAIL'}.",
            "preview_kind": "bits",
            "data": rx_meta.recovered_bits,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.decoder_input_llrs).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.recovered_bits).shape],
        },
    ]

    if bool(getattr(tx_meta, "transform_precoding_enabled", False)):
        stages.insert(
            7,
            {
                "section": "TX",
                "stage": "Transform precoding",
                "domain": "symbols",
                "description": "DFT-based transform precoding is applied before uplink resource mapping.",
                "preview_kind": "constellation",
                "data": tx_meta.tx_symbols,
                "artifact_type": "constellation",
                "input_shape": [int(dim) for dim in np.asarray(tx_meta.modulation_symbols).shape],
                "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_symbols).shape],
            },
        )
        equalization_index = next(
            index for index, stage in enumerate(stages) if stage["stage"] == "Equalization"
        )
        stages.insert(
            equalization_index + 1,
            {
                "section": "RX",
                "stage": "Inverse transform precoding",
                "domain": "symbols",
                "description": "The equalized PUSCH sequence is de-spread with the inverse DFT before demapping.",
                "preview_kind": "constellation",
                "data": rx_meta.detected_symbols,
                "artifact_type": "constellation",
                "input_shape": [int(dim) for dim in np.asarray(rx_meta.equalized_symbols).shape],
                "output_shape": [int(dim) for dim in np.asarray(rx_meta.detected_symbols).shape],
            },
        )

    return _normalize_pipeline(stages)


def simulate_link(
    config: Dict,
    channel_type: str | None = None,
    payload_bits: np.ndarray | None = None,
    seed_offset: int = 0,
) -> Dict:
    config = deepcopy(config)
    if seed_offset:
        config.setdefault("simulation", {})
        config["simulation"]["seed"] = int(config.get("simulation", {}).get("seed", 0)) + int(seed_offset)
    transmitter = NrTransmitter(config)
    tx_result = transmitter.transmit(
        channel_type=channel_type or config.get("link", {}).get("channel_type", "data"),
        payload_bits=payload_bits,
    )

    simulation_seed = int(config.get("simulation", {}).get("seed", 0))
    rng = np.random.default_rng(simulation_seed + 99)

    waveform = tx_result.waveform.copy()
    impairment_config = deepcopy(config)
    if bool(config.get("simulation", {}).get("use_gnuradio", False)):
        impairment_config.setdefault("channel", {})["cfo_hz"] = 0.0
    impaired_waveform = apply_impairments(waveform, config=impairment_config, sample_rate=tx_result.metadata.sample_rate, rng=rng)
    waveform = impaired_waveform.copy()

    fading_model = str(config.get("channel", {}).get("model", "awgn")).lower()
    use_gnuradio = bool(config.get("simulation", {}).get("use_gnuradio", False))
    fading_channel = FadingChannel(
        config=config,
        sample_rate=tx_result.metadata.sample_rate,
        fft_size=tx_result.metadata.numerology.fft_size,
        seed=simulation_seed + 7,
    )

    if fading_model in {"awgn", "none"}:
        fading_response = np.ones(tx_result.metadata.numerology.fft_size, dtype=np.complex128)
        impulse_response = np.array([1.0 + 0j], dtype=np.complex128)
    else:
        impulse_response = fading_channel.build_impulse_response()
        fading_response = fading_channel.frequency_response_from_impulse(impulse_response)

    awgn = AWGNChannel(
        snr_db=float(config.get("channel", {}).get("snr_db", 20.0)),
        seed=simulation_seed + 123,
    )

    gnuradio_requested = use_gnuradio
    gnuradio_error: str | None = None
    if use_gnuradio:
        try:
            from grc.end_to_end_flowgraph import EndToEndFlowgraph

            noise_variance = awgn.apply(waveform).noise_variance
            gr_flowgraph = EndToEndFlowgraph(
                waveform=waveform,
                sample_rate=tx_result.metadata.sample_rate,
                noise_variance=noise_variance,
                frequency_offset_hz=float(config.get("channel", {}).get("cfo_hz", 0.0)),
                taps=impulse_response,
            )
            rx_waveform = gr_flowgraph.run_and_collect()
            rx_waveform = apply_doppler_rotation(
                rx_waveform,
                doppler_hz=float(config.get("channel", {}).get("doppler_hz", 0.0)),
                sample_rate=tx_result.metadata.sample_rate,
            )
            channel_output_waveform = rx_waveform.copy()
            awgn_result = type("AwgnProxy", (), {"noise_variance": noise_variance})()
        except Exception as exc:
            gnuradio_error = str(exc)
            use_gnuradio = False

    if not use_gnuradio:
        if fading_model not in {"awgn", "none"}:
            fading_result = fading_channel.apply(waveform)
            waveform = fading_result.waveform
            fading_response = fading_result.frequency_response
            impulse_response = fading_result.impulse_response
        channel_output_waveform = waveform.copy()
        awgn_result = awgn.apply(waveform)
        rx_waveform = awgn_result.waveform
    else:
        channel_output_waveform = channel_output_waveform.copy()

    receiver = NrReceiver(config)
    channel_state = {
        "noise_variance": awgn_result.noise_variance,
        "cfo_hz": float(config.get("channel", {}).get("cfo_hz", 0.0)),
        "sto_samples": int(config.get("channel", {}).get("sto_samples", 0)),
        "reference_channel_grid": _reference_channel_grid(tx_result.metadata, fading_response),
        "impulse_response": impulse_response,
        "fading_model": fading_model,
        "gnu_radio_requested": gnuradio_requested,
        "gnu_radio_used": use_gnuradio,
        "gnu_radio_error": gnuradio_error,
    }
    rx_result = receiver.receive(rx_waveform, tx_result.metadata, channel_state=channel_state)
    pipeline = _build_pipeline_trace(
        tx_result,
        rx_result,
        impaired_waveform=impaired_waveform,
        channel_output_waveform=channel_output_waveform,
        rx_waveform=rx_waveform,
        channel_state=channel_state,
    )
    result = {
        "config": config,
        "tx": tx_result,
        "rx": rx_result,
        "kpis": rx_result.kpis,
        "pipeline_contract_version": 1,
        "channel_state": channel_state,
        "pipeline": pipeline,
        "impaired_waveform": impaired_waveform,
        "channel_output_waveform": channel_output_waveform,
        "rx_waveform": rx_waveform,
    }
    return _annotate_result_slot(result, seed_offset)


def simulate_link_sequence(
    config: Dict,
    *,
    channel_type: str | None = None,
    payload_bits: np.ndarray | None = None,
    num_slots: int | None = None,
) -> Dict[str, Any]:
    capture_slots = max(1, int(num_slots or config.get("simulation", {}).get("capture_slots", 1)))
    slot_results = [
        simulate_link(
            config=config,
            channel_type=channel_type,
            payload_bits=payload_bits,
            seed_offset=timeline_index,
        )
        for timeline_index in range(capture_slots)
    ]

    representative = deepcopy(slot_results[0])
    representative["slot_history"] = [
        {
            **entry["slot_context"],
            "result": entry,
        }
        for entry in slot_results
    ]
    representative["captured_slots"] = capture_slots
    representative["kpis"] = _aggregate_slot_sequence_kpis(slot_results)
    representative["sequence_summary"] = {
        "captured_slots": capture_slots,
        "frames_covered": int(max(history["frame_index"] for history in representative["slot_history"]) + 1),
        "slots_crc_passed": int(sum(entry["rx"].crc_ok for entry in slot_results)),
        "slots_crc_failed": int(sum(not entry["rx"].crc_ok for entry in slot_results)),
    }
    return representative


def simulate_file_transfer(
    config: Dict,
    *,
    source_path: str,
    output_dir: str | None = None,
    channel_type: str | None = None,
) -> Dict:
    config = deepcopy(config)
    active_channel_type = channel_type or config.get("link", {}).get("channel_type", "data")
    package = build_file_payload_package(source_path)
    payload_bits_per_chunk = _payload_size_bits_for_channel(config, active_channel_type)
    chunks = chunk_bitstream(package.package_bits, payload_bits_per_chunk)

    chunk_results: list[Dict] = []
    recovered_chunks: list[np.ndarray] = []
    for chunk in chunks:
        result = simulate_link(
            config=config,
            channel_type=active_channel_type,
            payload_bits=chunk.bits,
            seed_offset=chunk.index,
        )
        result["transfer_chunk"] = {
            "index": chunk.index,
            "total": chunk.total,
            "valid_bits": chunk.valid_bits,
        }
        chunk_results.append(result)
        recovered_chunks.append(result["rx"].recovered_bits[: chunk.valid_bits])

    recovered_package_bits = join_valid_chunks(chunks, recovered_chunks)
    output_root = output_dir or str(Path(config.get("simulation", {}).get("output_dir", "outputs")) / "rx_files")
    restored_file_path = None
    restored_snr_label = ""
    restored_timestamp_label = ""
    restored_preview = "n/a"
    restored_size_bytes = 0
    restored_media_kind = package.media_kind
    sha256_match = False
    transfer_success = False
    transfer_error = ""

    if all(entry["rx"].crc_ok for entry in chunk_results):
        try:
            restored = restore_file_from_package_bits(
                recovered_package_bits,
                output_dir=output_root,
                snr_db=config.get("channel", {}).get("snr_db"),
            )
            restored_file_path = str(restored.destination_path)
            restored_snr_label = restored.snr_label
            restored_timestamp_label = restored.received_timestamp_label
            restored_preview = file_preview_text(restored.media_kind, restored.payload_bytes)
            restored_size_bytes = len(restored.payload_bytes)
            restored_media_kind = restored.media_kind
            sha256_match = restored.sha256_match
            transfer_success = restored.sha256_match
            if not transfer_success:
                transfer_error = "PHY chunk CRCs passed, but the reconstructed file hash does not match the source."
        except Exception as exc:
            transfer_error = str(exc)
    else:
        transfer_error = "One or more PHY transport blocks failed CRC, so the RX file was not written."

    aggregate_kpis = _aggregate_file_transfer_kpis(
        config=config,
        reference_bits=package.package_bits,
        recovered_bits=recovered_package_bits,
        chunk_results=chunk_results,
        chunk_valid_bits=[chunk.valid_bits for chunk in chunks],
        transfer_success=transfer_success,
        sha256_match=sha256_match,
    )

    representative = deepcopy(chunk_results[0])
    transfer_summary = {
        "mode": "file",
        "source_path": str(package.source_path),
        "source_filename": package.filename,
        "media_kind": package.media_kind,
        "mime_type": package.mime_type,
        "source_size_bytes": len(package.payload_bytes),
        "package_size_bytes": len(package.package_bytes),
        "payload_bits_per_chunk": payload_bits_per_chunk,
        "total_chunks": len(chunks),
        "chunks_passed": int(sum(entry["rx"].crc_ok for entry in chunk_results)),
        "chunks_failed": int(sum(not entry["rx"].crc_ok for entry in chunk_results)),
        "success": transfer_success,
        "sha256_match": sha256_match,
        "restored_file_path": restored_file_path,
        "received_snr_label": restored_snr_label,
        "received_timestamp_label": restored_timestamp_label,
        "restored_size_bytes": restored_size_bytes,
        "restored_media_kind": restored_media_kind,
        "source_preview": file_preview_text(package.media_kind, package.payload_bytes),
        "restored_preview": restored_preview,
        "error": transfer_error,
        "chunk_status": [bool(entry["rx"].crc_ok) for entry in chunk_results],
    }

    for entry in chunk_results:
        entry["file_transfer"] = transfer_summary

    tx_stage, rx_stage = _file_transfer_pipeline_stages(package=package, transfer_summary=transfer_summary)
    representative["pipeline"] = _normalize_pipeline([tx_stage, *representative["pipeline"], rx_stage])
    representative["kpis"] = aggregate_kpis
    representative["file_transfer"] = transfer_summary
    representative["slot_history"] = [
        {
            **entry["slot_context"],
            "result": entry,
        }
        for entry in chunk_results
    ]
    representative["captured_slots"] = len(chunk_results)
    representative["sequence_summary"] = {
        "captured_slots": len(chunk_results),
        "frames_covered": int(max(history["frame_index"] for history in representative["slot_history"]) + 1),
        "slots_crc_passed": transfer_summary["chunks_passed"],
        "slots_crc_failed": transfer_summary["chunks_failed"],
    }
    representative["file_transfer_chunks"] = [
        {
            "index": chunk.index,
            "valid_bits": chunk.valid_bits,
            "crc_ok": bool(result["rx"].crc_ok),
            "ber": float(result["rx"].kpis.ber),
            "evm": float(result["rx"].kpis.evm),
        }
        for chunk, result in zip(chunks, chunk_results)
    ]
    representative["recovered_package_bits"] = recovered_package_bits
    representative["source_package_bits"] = package.package_bits
    return representative
