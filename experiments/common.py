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
from phy.csi import report_csi
from phy.coding import build_channel_coder
from phy.context import SlotContext
from phy.harq import HarqProcessManager
from phy.kpi import LinkKpiSummary, bit_error_rate, block_error_rate, spectral_efficiency_bps_hz, throughput_bps
from phy.receiver import NrReceiver
from phy.resource_grid import ResourceGrid
from phy.scheduler import apply_grant_to_config, build_dci_grant, scheduler_enabled, select_grant_spec
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


def _active_frequency_response(tx_metadata, frequency_response: np.ndarray) -> np.ndarray:
    center = tx_metadata.numerology.fft_size // 2
    left = tx_metadata.numerology.active_subcarriers // 2
    right = tx_metadata.numerology.active_subcarriers - left
    return np.concatenate(
        [
            frequency_response[center - left : center],
            frequency_response[center + 1 : center + 1 + right],
        ]
    )


def _reference_channel_tensor(tx_metadata, frequency_response: np.ndarray, spatial_matrix: np.ndarray) -> np.ndarray:
    active = _active_frequency_response(tx_metadata, frequency_response)
    symbols = int(tx_metadata.numerology.symbols_per_slot)
    tensor = spatial_matrix[:, :, None, None] * active[None, None, None, :]
    return np.broadcast_to(
        tensor,
        (
            spatial_matrix.shape[0],
            spatial_matrix.shape[1],
            symbols,
            active.size,
        ),
    ).astype(np.complex128, copy=True)


def _spatial_channel_matrix(config: Dict, tx_metadata, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    num_rx = int(tx_metadata.spatial_layout.num_rx_antennas)
    num_tx = max(int(tx_metadata.spatial_layout.num_ports), 1)
    if num_rx == 1 and num_tx == 1:
        return np.ones((1, 1), dtype=np.complex128)
    profile = str(config.get("channel", {}).get("profile", "static_near")).lower()
    base = (
        rng.standard_normal((num_rx, num_tx)) + 1j * rng.standard_normal((num_rx, num_tx))
    ) / np.sqrt(2.0 * max(num_tx, 1))
    if "near" in profile or "los" in profile:
        identity = np.eye(num_rx, num_tx, dtype=np.complex128)
        base = 0.65 * identity + 0.35 * base
    return base.astype(np.complex128)


def _csi_feedback_for_result(result: Dict[str, Any]) -> dict[str, object] | None:
    csi_cfg = dict(result["config"].get("csi", {}))
    if not bool(csi_cfg.get("enabled", True)):
        return None
    channel_tensor = np.asarray(getattr(result["rx"], "effective_channel_tensor", np.zeros((0, 0, 0, 0))), dtype=np.complex128)
    if channel_tensor.size == 0:
        channel_tensor = np.asarray(getattr(result["rx"], "channel_tensor", np.zeros((0, 0, 0, 0))), dtype=np.complex128)
    if channel_tensor.size == 0:
        return None
    feedback = report_csi(
        channel_tensor=channel_tensor,
        noise_variance=float(result["channel_state"].get("noise_variance", 1e-3)),
        max_rank=int(csi_cfg.get("max_rank", 4)),
        candidate_precoders=csi_cfg.get("candidate_precoders", ["identity", "dft"]),
        cqi_snr_offset_db=float(csi_cfg.get("cqi_snr_offset_db", 0.0)),
    )
    payload = feedback.as_dict()
    payload["tx_precoding_mode"] = str(getattr(result["tx"].metadata, "precoding_mode", "identity"))
    payload["tx_layers"] = int(result["tx"].metadata.spatial_layout.num_layers)
    return payload


def _csi_replay_supported(channel_type: str) -> bool:
    return str(channel_type).lower() not in {"prach", "pbch", "broadcast"}


def _harq_supported(channel_type: str) -> bool:
    return str(channel_type).lower() in {"data", "pdsch", "pusch"}


def _apply_csi_feedback_to_config(config: Dict[str, Any], feedback: dict[str, object], *, allow_rank_update: bool) -> Dict[str, Any]:
    updated = deepcopy(config)
    updated.setdefault("precoding", {})
    updated.setdefault("spatial", {})
    selected_pmi = str(feedback.get("pmi", updated["precoding"].get("mode", "identity"))).lower()
    if selected_pmi.startswith("type1sp-"):
        updated["precoding"]["mode"] = "type1_sp"
        updated["precoding"]["pmi"] = selected_pmi
    else:
        updated["precoding"]["mode"] = selected_pmi
        updated["precoding"].pop("pmi", None)
    if allow_rank_update:
        rank = int(feedback.get("ri", updated["spatial"].get("num_layers", 1)))
        max_rank = min(
            int(updated["spatial"].get("num_ports", rank)),
            int(updated["spatial"].get("num_rx_antennas", rank)),
            int(updated["csi"].get("max_rank", rank)) if "csi" in updated else rank,
        )
        updated["spatial"]["num_layers"] = max(1, min(rank, max_rank))
    updated.setdefault("modulation", {})
    updated.setdefault("coding", {})
    updated["modulation"]["scheme"] = str(feedback.get("modulation", updated["modulation"].get("scheme", "QPSK"))).upper()
    updated["coding"]["target_rate"] = float(feedback.get("target_rate", updated["coding"].get("target_rate", 0.5)))
    return updated


def _decode_rate_recovered_codewords(
    *,
    config: Dict[str, Any],
    tx_metadata,
    combined_by_codeword: tuple[np.ndarray, ...],
) -> dict[str, object]:
    coder = build_channel_coder(channel_type=tx_metadata.channel_type, config=config)
    codeword_coding_metadata = tuple(getattr(tx_metadata, "codeword_coding_metadata", ()) or (tx_metadata.coding_metadata,))

    recovered_bits_by_codeword: list[np.ndarray] = []
    rate_recovered_llrs_by_codeword: list[np.ndarray] = []
    decoder_input_llrs_by_codeword: list[np.ndarray] = []
    codeword_crc_ok: list[bool] = []
    rate_recovered_code_blocks: list[np.ndarray] = []
    decoder_input_code_blocks: list[np.ndarray] = []
    recovered_code_blocks: list[np.ndarray] = []
    code_block_crc_ok: list[bool] = []

    for codeword_index, combined_llrs in enumerate(combined_by_codeword):
        coding_metadata = codeword_coding_metadata[min(codeword_index, len(codeword_coding_metadata) - 1)]
        if hasattr(coder, "decode_rate_recovered_with_trace"):
            recovered_bits, crc_ok, decode_trace = coder.decode_rate_recovered_with_trace(combined_llrs, coding_metadata)
        else:  # pragma: no cover
            recovered_bits, crc_ok, decode_trace = coder.decode(combined_llrs, coding_metadata), False, None

        recovered_bits_by_codeword.append(np.asarray(recovered_bits, dtype=np.uint8).copy())
        rate_recovered_llrs_by_codeword.append(np.asarray(combined_llrs, dtype=np.float64).copy())
        codeword_crc_ok.append(bool(crc_ok))
        if decode_trace is not None:
            decoder_input = (
                np.concatenate(decode_trace.decoder_input_blocks)
                if decode_trace.decoder_input_blocks
                else np.array([], dtype=np.float64)
            )
            decoder_input_llrs_by_codeword.append(decoder_input.copy())
            rate_recovered_code_blocks.extend(block.copy() for block in decode_trace.rate_recovered_blocks)
            decoder_input_code_blocks.extend(block.copy() for block in decode_trace.decoder_input_blocks)
            recovered_code_blocks.extend(block.copy() for block in decode_trace.recovered_code_blocks)
            code_block_crc_ok.extend(bool(value) for value in decode_trace.code_block_crc_ok)
        else:
            decoder_input_llrs_by_codeword.append(np.asarray(combined_llrs, dtype=np.float64).copy())

    concat_float = lambda values: np.concatenate(values) if values else np.array([], dtype=np.float64)
    concat_bits = lambda values: np.concatenate(values) if values else np.array([], dtype=np.uint8)
    recovered_bits = concat_bits(recovered_bits_by_codeword)
    return {
        "recovered_bits": recovered_bits,
        "crc_ok": bool(all(codeword_crc_ok)),
        "recovered_bits_by_codeword": tuple(block.copy() for block in recovered_bits_by_codeword),
        "rate_recovered_llrs": concat_float(rate_recovered_llrs_by_codeword),
        "rate_recovered_llrs_by_codeword": tuple(block.copy() for block in rate_recovered_llrs_by_codeword),
        "decoder_input_llrs": concat_float(decoder_input_llrs_by_codeword),
        "decoder_input_llrs_by_codeword": tuple(block.copy() for block in decoder_input_llrs_by_codeword),
        "rate_recovered_code_blocks": tuple(block.copy() for block in rate_recovered_code_blocks),
        "decoder_input_code_blocks": tuple(block.copy() for block in decoder_input_code_blocks),
        "recovered_code_blocks": tuple(block.copy() for block in recovered_code_blocks),
        "code_block_crc_ok": tuple(code_block_crc_ok),
        "codeword_crc_ok": tuple(codeword_crc_ok),
    }


def _apply_harq_soft_combining(
    *,
    result: Dict[str, Any],
    process,
    harq_info: dict[str, object],
    config: Dict[str, Any],
) -> dict[str, object]:
    rx = result["rx"]
    tx = result["tx"]
    combined = process.combine(
        tuple(np.asarray(block, dtype=np.float64) for block in rx.rate_recovered_llrs_by_codeword),
        soft_combining=bool(harq_info.get("soft_combining", True)),
    )
    decoded = _decode_rate_recovered_codewords(
        config=config,
        tx_metadata=tx.metadata,
        combined_by_codeword=combined,
    )

    rx.rate_recovered_llrs = np.asarray(decoded["rate_recovered_llrs"], dtype=np.float64)
    rx.rate_recovered_llrs_by_codeword = tuple(decoded["rate_recovered_llrs_by_codeword"])
    rx.decoder_input_llrs = np.asarray(decoded["decoder_input_llrs"], dtype=np.float64)
    rx.decoder_input_llrs_by_codeword = tuple(decoded["decoder_input_llrs_by_codeword"])
    rx.recovered_bits = np.asarray(decoded["recovered_bits"], dtype=np.uint8)
    rx.recovered_bits_by_codeword = tuple(decoded["recovered_bits_by_codeword"])
    rx.rate_recovered_code_blocks = tuple(decoded["rate_recovered_code_blocks"])
    rx.decoder_input_code_blocks = tuple(decoded["decoder_input_code_blocks"])
    rx.recovered_code_blocks = tuple(decoded["recovered_code_blocks"])
    rx.code_block_crc_ok = tuple(decoded["code_block_crc_ok"])
    rx.codeword_crc_ok = tuple(decoded["codeword_crc_ok"])
    rx.crc_ok = bool(decoded["crc_ok"])

    slot_duration_s = tx.metadata.numerology.slot_length_samples / tx.metadata.numerology.sample_rate
    bandwidth_hz = float(config.get("carrier", {}).get("bandwidth_hz", tx.metadata.numerology.active_subcarriers * tx.metadata.numerology.subcarrier_spacing_hz))
    rx.kpis.ber = bit_error_rate(tx.metadata.payload_bits, rx.recovered_bits)
    rx.kpis.bler = block_error_rate(rx.crc_ok)
    rx.kpis.crc_ok = bool(rx.crc_ok)
    rx.kpis.throughput_bps = throughput_bps(rx.recovered_bits.size, slot_duration_s=slot_duration_s, crc_ok=rx.crc_ok)
    rx.kpis.spectral_efficiency_bps_hz = spectral_efficiency_bps_hz(rx.kpis.throughput_bps, bandwidth_hz)
    rx.kpis.extra.update(
        {
            "harq_enabled": 1.0,
            "harq_process_id": float(harq_info.get("process_id", 0)),
            "harq_attempt_index": float(harq_info.get("attempt_index", 0)),
            "harq_redundancy_version": float(harq_info.get("rv", 0)),
            "harq_soft_observations": float(max(len(combined), 1) and int(harq_info.get("soft_observations", 1))),
        }
    )
    result["kpis"] = rx.kpis
    result["harq_feedback"] = {
        **harq_info,
        "ack": bool(rx.crc_ok),
        "soft_observations": int(harq_info.get("soft_observations", 1)),
        "combined_llr_energy": float(sum(float(np.mean(np.abs(block))) for block in combined if block.size)),
    }
    return result["harq_feedback"]


def _insert_harq_pipeline_stage(result: Dict[str, Any], harq_feedback: dict[str, object]) -> None:
    rx = result["rx"]
    pipeline = list(result.get("pipeline", []))
    insertion_index = next(
        (index + 1 for index, stage in enumerate(pipeline) if stage.get("stage") == "Rate recovery"),
        len(pipeline),
    )
    pipeline.insert(
        insertion_index,
        {
            "section": "RX",
            "stage": "HARQ soft combining",
            "domain": "llr",
            "description": "Rate-recovered LLRs are accumulated in a HARQ soft buffer before decoding retransmitted transport blocks.",
            "preview_kind": "llr",
            "data": rx.rate_recovered_llrs,
            "artifact_type": "llr",
            "input_shape": [int(dim) for dim in np.asarray(rx.rate_recovered_llrs).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx.decoder_input_llrs).shape],
            "notes": (
                f"Process {int(harq_feedback.get('process_id', 0))} | "
                f"Attempt {int(harq_feedback.get('attempt_index', 0))} | "
                f"RV {int(harq_feedback.get('rv', 0))} | "
                f"ACK={bool(harq_feedback.get('ack', False))}"
            ),
        },
    )
    result["pipeline"] = _normalize_pipeline(pipeline)


def _insert_scheduling_pipeline_stage(result: Dict[str, Any], grant_payload: dict[str, object]) -> None:
    pipeline = list(result.get("pipeline", []))
    pipeline.insert(
        0,
        {
            "section": "Control",
            "stage": "DCI-like scheduling grant",
            "domain": "control",
            "description": "A minimal scheduler-facing grant selects the slot transmission parameters: channel type, MCS, spatial layers, precoder, HARQ process, NDI, RV, and resource allocation summary.",
            "preview_kind": "text",
            "data": grant_payload,
            "artifact_type": "text",
            "input_shape": [1],
            "output_shape": [int(grant_payload.get("allocated_re_count", 0))],
            "notes": (
                f"Grant {int(grant_payload.get('grant_id', 0))} | "
                f"{grant_payload.get('channel_type', 'data')} | "
                f"{grant_payload.get('modulation', 'QPSK')} | "
                f"layers={int(grant_payload.get('num_layers', 1))} | "
                f"RV={int(grant_payload.get('rv', 0))}"
            ),
        },
    )
    result["pipeline"] = _normalize_pipeline(pipeline)


def _payload_size_bits_for_channel(config: Dict, channel_type: str) -> int:
    if channel_type.lower() == "prach":
        return int(config.get("prach", {}).get("preamble_id_bits", 6))
    if channel_type.lower() in {"control", "pdcch", "pucch", "pbch"}:
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
    numeric_metric = lambda value: isinstance(value, (int, float, np.integer, np.floating, bool))
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
          and all(numeric_metric(metrics[key]) for metrics in kpi_dicts if key in metrics)
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
    if str(tx_meta.channel_type).lower() == "prach":
        return _build_prach_pipeline_trace(
            tx_result,
            rx_result,
            impaired_waveform=impaired_waveform,
            channel_output_waveform=channel_output_waveform,
            rx_waveform=rx_waveform,
            channel_state=channel_state,
        )
    direction = str(getattr(tx_meta, "direction", "downlink")).lower()
    direction_label = "uplink" if direction == "uplink" else "downlink"
    if direction == "uplink":
        mapping_label = "PUCCH-style" if tx_meta.channel_type in {"control", "pucch"} else "PUSCH-style"
    else:
        if tx_meta.channel_type in {"control", "pdcch"}:
            mapping_label = "PDCCH/CORESET-style"
        elif tx_meta.channel_type in {"pbch", "broadcast"}:
            mapping_label = "SSB/PBCH-style"
        else:
            mapping_label = "PDSCH-style"
    coding_metadatas = tuple(getattr(tx_meta, "codeword_coding_metadata", ()) or (tx_meta.coding_metadata,))
    transport_with_crc_parts = [
        np.asarray(coding_meta.transport_block_with_crc, dtype=np.uint8)
        if coding_meta.transport_block_with_crc is not None
        else np.array([], dtype=np.uint8)
        for coding_meta in coding_metadatas
    ]
    transport_with_crc = (
        np.concatenate([part for part in transport_with_crc_parts if part.size]).astype(np.uint8)
        if any(part.size for part in transport_with_crc_parts)
        else tx_meta.coded_bits
    )
    code_blocks_with_crc_parts = [
        np.concatenate(coding_meta.code_blocks_with_crc).astype(np.uint8)
        if coding_meta.code_blocks_with_crc
        else np.asarray(coding_meta.transport_block_with_crc, dtype=np.uint8)
        if coding_meta.transport_block_with_crc is not None
        else np.array([], dtype=np.uint8)
        for coding_meta in coding_metadatas
    ]
    code_blocks_with_crc = (
        np.concatenate([part for part in code_blocks_with_crc_parts if part.size]).astype(np.uint8)
        if any(part.size for part in code_blocks_with_crc_parts)
        else transport_with_crc
    )
    mother_bits_parts = [
        np.concatenate(coding_meta.mother_code_blocks).astype(np.uint8)
        if coding_meta.mother_code_blocks
        else np.array([], dtype=np.uint8)
        for coding_meta in coding_metadatas
    ]
    mother_bits = (
        np.concatenate([part for part in mother_bits_parts if part.size]).astype(np.uint8)
        if any(part.size for part in mother_bits_parts)
        else tx_meta.coded_bits
    )

    gnuradio_used = bool(channel_state.get("gnu_radio_used", False))
    channel_stage_name = "GNU Radio loopback output" if gnuradio_used else "Fading / path loss / Doppler output"
    channel_stage_description = (
        "Waveform after GNU Radio loopback processing."
        if gnuradio_used
        else "Waveform after channel convolution, Doppler rotation, and large-scale loss."
    )
    vrb_mapping = getattr(tx_meta, "vrb_mapping", getattr(tx_meta.mapping, "vrb_mapping", None))
    vrb_mask = (
        vrb_mapping.grid_mask(tx_meta.numerology.symbols_per_slot, tx_meta.numerology.active_subcarriers)
        if vrb_mapping is not None
        else np.ones_like(tx_meta.tx_grid_data, dtype=np.float32)
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
            "notes": (
                f"Codewords: {int(tx_meta.spatial_layout.num_codewords)} | "
                f"Layers: {int(tx_meta.spatial_layout.num_layers)} | "
                f"Ports: {int(tx_meta.spatial_layout.num_ports)}"
            ),
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
            "stage": "Codeword partitioning",
            "domain": "symbols",
            "description": "One or two codewords are independently encoded and mapped before their symbol streams are assigned onto transmission layers.",
            "preview_kind": "constellation",
            "data": np.asarray(
                tx_meta.codeword_modulation_symbols[0]
                if getattr(tx_meta, "codeword_modulation_symbols", ())
                else tx_meta.modulation_symbols,
                dtype=np.complex128,
            ),
            "artifact_type": "constellation",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.modulation_symbols).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_symbols).shape],
            "notes": " | ".join(
                f"CW{index}: layers {start}-{end - 1}, payload={int(np.asarray(tx_meta.codeword_payload_bits[index]).size)} bits, symbols={int(np.asarray(tx_meta.codeword_modulation_symbols[index]).size)}"
                for index, (start, end) in enumerate(getattr(tx_meta, "codeword_layer_ranges", ()) or ((0, int(tx_meta.spatial_layout.num_layers)),))
            ),
        },
        {
            "section": "TX",
            "stage": "Layer mapping",
            "domain": "grid",
            "description": "The codeword-domain modulation stream is distributed across the configured transmission layers before port mapping.",
            "preview_kind": "grid",
            "data": np.abs(tx_meta.tx_layer_grid[0]) if tx_meta.tx_layer_grid.size else np.zeros((0, 0), dtype=np.float64),
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_symbols).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_layer_grid).shape],
            "notes": (
                f"Layers: {int(tx_meta.spatial_layout.num_layers)} | "
                f"Ports: {int(tx_meta.spatial_layout.num_ports)} | "
                f"Precoding mode: {getattr(tx_meta, 'precoding_mode', 'identity')}"
            ),
        },
        {
            "section": "TX",
            "stage": "Precoding / port mapping",
            "domain": "grid",
            "description": "Layer-domain symbols are transformed into port-domain signals through the configured linear precoder before OFDM modulation.",
            "preview_kind": "grid",
            "data": np.abs(tx_meta.tx_port_grid[0]) if tx_meta.tx_port_grid.size else np.zeros((0, 0), dtype=np.float64),
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_layer_grid).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_port_grid).shape],
            "notes": (
                f"Precoding mode: {getattr(tx_meta, 'precoding_mode', 'identity')} | "
                f"Matrix shape: {list(np.asarray(getattr(tx_meta, 'precoder_matrix', np.eye(1))).shape)}"
            ),
        },
        {
            "section": "TX",
            "stage": "VRB-to-PRB mapping",
            "domain": "grid",
            "description": "Scheduled virtual resource blocks are mapped to physical resource blocks before data REs are placed in the resource grid.",
            "preview_kind": "grid",
            "data": vrb_mask,
            "artifact_type": "grid",
            "input_shape": [int(getattr(vrb_mapping, "num_vrbs", 0))],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid_data).shape],
            "notes": (
                f"type={getattr(vrb_mapping, 'mapping_type', 'n/a')} | "
                f"BWP={getattr(vrb_mapping, 'bwp_start_prb', 0)}+{getattr(vrb_mapping, 'bwp_size_prb', 0)} PRB | "
                f"VRB={getattr(vrb_mapping, 'start_vrb', 0)}+{getattr(vrb_mapping, 'num_vrbs', 0)} | "
                f"allocated PRB={getattr(vrb_mapping, 'allocated_prb_count', 0)}"
            ),
        },
        {
            "section": "TX",
            "stage": "Resource grid mapping",
            "domain": "grid",
            "description": f"Mapped {mapping_label} symbols on the active NR-like resource grid before DMRS insertion.",
            "preview_kind": "grid",
            "data": tx_meta.tx_grid_data,
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_symbols).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid_data).shape],
        },
        {
            "section": "TX",
            "stage": "DMRS insertion" if tx_meta.channel_type not in {"pbch", "broadcast"} else "PBCH-DMRS / SSB insertion",
            "domain": "grid",
            "description": (
                "Resource grid after DMRS insertion on configured OFDM symbols."
                if tx_meta.channel_type not in {"pbch", "broadcast"}
                else "Resource grid after PBCH-DMRS, PSS, and SSS insertion inside the SSB broadcast region."
            ),
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
            "stage": "Layer recovery / de-precoding",
            "domain": "symbols",
            "description": "Equalized port-domain symbols are projected back into the layer domain through the pseudo-inverse of the configured precoder.",
            "preview_kind": "constellation",
            "data": rx_meta.equalized_symbols,
            "artifact_type": "constellation",
            "input_shape": [int(dim) for dim in np.asarray(rx_meta.equalized_port_symbols).shape],
            "output_shape": [int(dim) for dim in np.asarray(rx_meta.equalized_layer_symbols).shape],
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

    if direction == "downlink" and tx_meta.channel_type in {"control", "pdcch"}:
        helper = ResourceGrid(
            tx_meta.numerology,
            tx_meta.allocation,
            spatial_layout=tx_meta.spatial_layout,
            slot_index=int(getattr(tx_meta, "slot_index", 0)),
            physical_cell_id=int(tx_meta.ssb.get("physical_cell_id", 0)),
            ssb_block_index=int(tx_meta.ssb.get("ssb_block_index", 0)),
        )
        coreset_mask = helper.coreset_re_mask().astype(np.float32)
        search_space_mask = np.zeros_like(coreset_mask)
        if tx_meta.mapping.positions.size:
            search_space_mask[tx_meta.mapping.positions[:, 0], tx_meta.mapping.positions[:, 1]] = 1.0
        stages.insert(
            6,
            {
                "section": "TX",
                "stage": "CORESET / SearchSpace selection",
                "domain": "grid",
                "description": "PDCCH mapping is constrained to a configurable CORESET and monitored SearchSpace subset.",
                "preview_kind": "grid",
                "data": search_space_mask,
                "artifact_type": "grid",
                "input_shape": [int(dim) for dim in np.asarray(tx_meta.scrambled_bits).shape],
                "output_shape": [int(dim) for dim in np.asarray(search_space_mask).shape],
                "notes": (
                    f"CORESET RE count: {int(np.sum(coreset_mask))} | "
                    f"SearchSpace RE count: {int(np.sum(search_space_mask))} | "
                    f"Active: {bool(getattr(tx_meta, 'procedure_state', {}).get('search_space_active', True))} | "
                    f"Symbols: {getattr(tx_meta, 'procedure_state', {}).get('search_space_symbols', [])}"
                ),
            },
        )
    if direction == "downlink" and tx_meta.channel_type in {"pbch", "broadcast"}:
        helper = ResourceGrid(
            tx_meta.numerology,
            tx_meta.allocation,
            spatial_layout=tx_meta.spatial_layout,
            slot_index=int(getattr(tx_meta, "slot_index", 0)),
            physical_cell_id=int(tx_meta.ssb.get("physical_cell_id", 0)),
            ssb_block_index=int(tx_meta.ssb.get("ssb_block_index", 0)),
        )
        ssb_mask = np.zeros(helper.shape, dtype=np.float32)
        helper_ssb_positions = helper.ssb_positions(force_active=True)
        if helper_ssb_positions.size:
            ssb_mask[helper_ssb_positions[:, 0], helper_ssb_positions[:, 1]] = 1.0
        stages.insert(
            6,
            {
                "section": "TX",
                "stage": "SSB / PBCH broadcast layout",
                "domain": "grid",
                "description": "PBCH payload is constrained to the dedicated SSB broadcast region, with reserved PSS, SSS, and PBCH-DMRS resources.",
                "preview_kind": "grid",
                "data": ssb_mask,
                "artifact_type": "grid",
                "input_shape": [int(dim) for dim in np.asarray(tx_meta.scrambled_bits).shape],
                "output_shape": [int(dim) for dim in np.asarray(ssb_mask).shape],
                "notes": (
                    f"SSB RE count: {int(np.sum(ssb_mask))} | "
                    f"PBCH payload RE count: {int(tx_meta.mapping.positions.shape[0])} | "
                    f"Active: {bool(getattr(tx_meta, 'procedure_state', {}).get('ssb_active', True))}"
                ),
            },
        )
        stages.insert(
            next((index for index, stage in enumerate(stages) if stage["stage"] == "Channel estimation"), len(stages)),
            {
                "section": "RX",
                "stage": "PSS / SSS cell search",
                "domain": "text",
                "description": "The receiver correlates the received PSS and SSS against NR candidates to infer N_ID^(2), N_ID^(1), and the physical cell ID before interpreting PBCH broadcast context.",
                "preview_kind": "text",
                "data": {
                    "expected_cell_id": int(tx_meta.ssb.get("physical_cell_id", -1)),
                    "detected_cell_id": int(rx_meta.detected_cell_id) if rx_meta.detected_cell_id is not None else None,
                    "detected_n_id_1": int(rx_meta.detected_n_id_1) if rx_meta.detected_n_id_1 is not None else None,
                    "detected_n_id_2": int(rx_meta.detected_n_id_2) if rx_meta.detected_n_id_2 is not None else None,
                    "pss_peak": float(np.max(rx_meta.pss_candidate_metrics)) if rx_meta.pss_candidate_metrics.size else 0.0,
                    "sss_peak": float(np.max(rx_meta.sss_candidate_metrics)) if rx_meta.sss_candidate_metrics.size else 0.0,
                },
                "artifact_type": "text",
                "input_shape": [127],
                "output_shape": [3],
                "notes": (
                    f"Expected cell ID: {int(tx_meta.ssb.get('physical_cell_id', -1))} | "
                    f"Detected cell ID: {int(rx_meta.detected_cell_id) if rx_meta.detected_cell_id is not None else 'n/a'}"
                ),
            },
        )
        stages.insert(
            next((index for index, stage in enumerate(stages) if stage["stage"] == "Decoding + CRC"), len(stages)) + 1,
            {
                "section": "RX",
                "stage": "PBCH / MIB semantic decode",
                "domain": "text",
                "description": "Recovered PBCH bits are interpreted as a semantic MIB-aware baseline payload, exposing broadcast system information fields that are useful for teaching and GUI introspection.",
                "preview_kind": "text",
                "data": {
                    "tx_broadcast_fields": dict(getattr(tx_meta, "broadcast_payload_fields", {})),
                    "rx_broadcast_fields": dict(getattr(rx_meta, "decoded_broadcast_payload", {}) or {}),
                },
                "artifact_type": "text",
                "input_shape": [int(dim) for dim in np.asarray(rx_meta.recovered_bits).shape],
                "output_shape": [32],
                "notes": (
                    f"SFN: {getattr(rx_meta, 'decoded_broadcast_payload', {}).get('system_frame_number', 'n/a')} | "
                    f"kSSB: {getattr(rx_meta, 'decoded_broadcast_payload', {}).get('k_ssb', 'n/a')} | "
                    f"SCS common: {getattr(rx_meta, 'decoded_broadcast_payload', {}).get('subcarrier_spacing_common', 'n/a')}"
                ),
            },
        )

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

    if np.asarray(tx_meta.csi_rs["positions"]).size:
        dmrs_stage_index = next(index for index, stage in enumerate(stages) if "DMRS" in stage["stage"])
        stages.insert(
            dmrs_stage_index + 1,
            {
                "section": "TX",
                "stage": "CSI-RS insertion",
                "domain": "grid",
                "description": "Downlink CSI-RS baseline is inserted on a comb-based set of REs for channel sounding and future CSI feedback studies.",
                "preview_kind": "grid",
                "data": tx_meta.tx_grid,
                "artifact_type": "grid",
                "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid_data).shape],
                "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid).shape],
                "notes": (
                    f"CSI-RS RE count: {int(np.asarray(tx_meta.csi_rs['positions']).shape[0])} | "
                    f"Active: {bool(getattr(tx_meta, 'procedure_state', {}).get('csi_rs_active', True))}"
                ),
            },
        )
    if np.asarray(tx_meta.ptrs["positions"]).size:
        dmrs_stage_index = next(index for index, stage in enumerate(stages) if "DMRS" in stage["stage"])
        stages.insert(
            dmrs_stage_index + 1,
            {
                "section": "TX",
                "stage": "PT-RS insertion",
                "domain": "grid",
                "description": "PT-RS baseline is inserted on scheduled data REs to expose phase-tracking reference occupancy on the transmit grid.",
                "preview_kind": "grid",
                "data": tx_meta.tx_grid,
                "artifact_type": "grid",
                "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid_data).shape],
                "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid).shape],
                "notes": (
                    f"PT-RS RE count: {int(np.asarray(tx_meta.ptrs['positions']).shape[0])} | "
                    f"Active: {bool(getattr(tx_meta, 'procedure_state', {}).get('ptrs_active', True))}"
                ),
            },
        )
    if np.asarray(tx_meta.srs["positions"]).size:
        dmrs_stage_index = next(index for index, stage in enumerate(stages) if "DMRS" in stage["stage"])
        stages.insert(
            dmrs_stage_index + 1,
            {
                "section": "TX",
                "stage": "SRS insertion",
                "domain": "grid",
                "description": "Uplink SRS baseline is inserted on a comb-based set of REs to expose sounding-reference occupancy for future CSI and beam management work.",
                "preview_kind": "grid",
                "data": tx_meta.tx_grid,
                "artifact_type": "grid",
                "input_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid_data).shape],
                "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid).shape],
                "notes": (
                    f"SRS RE count: {int(np.asarray(tx_meta.srs['positions']).shape[0])} | "
                    f"Active: {bool(getattr(tx_meta, 'procedure_state', {}).get('srs_active', True))}"
                ),
            },
        )
    if np.asarray(rx_meta.re_csi_rs_positions).size:
        extraction_index = next(index for index, stage in enumerate(stages) if stage["stage"] == "Resource element extraction")
        stages.insert(
            extraction_index + 1,
            {
                "section": "RX",
                "stage": "CSI-RS extraction",
                "domain": "symbols",
                "description": "CSI-RS observations extracted from the received grid for sounding and future CSI estimation workflows.",
                "preview_kind": "constellation",
                "data": rx_meta.re_csi_rs_symbols,
                "artifact_type": "constellation",
                "input_shape": [int(dim) for dim in np.asarray(rx_meta.rx_grid).shape],
                "output_shape": [int(dim) for dim in np.asarray(rx_meta.re_csi_rs_symbols).shape],
            },
        )
    if np.asarray(rx_meta.re_ptrs_positions).size:
        extraction_index = next(index for index, stage in enumerate(stages) if stage["stage"] == "Resource element extraction")
        stages.insert(
            extraction_index + 1,
            {
                "section": "RX",
                "stage": "PT-RS extraction",
                "domain": "symbols",
                "description": "PT-RS observations extracted from the received grid for phase-tracking observability and future common-phase-error studies.",
                "preview_kind": "constellation",
                "data": rx_meta.re_ptrs_symbols,
                "artifact_type": "constellation",
                "input_shape": [int(dim) for dim in np.asarray(rx_meta.rx_grid).shape],
                "output_shape": [int(dim) for dim in np.asarray(rx_meta.re_ptrs_symbols).shape],
            },
        )
    if np.asarray(rx_meta.re_srs_positions).size:
        extraction_index = next(index for index, stage in enumerate(stages) if stage["stage"] == "Resource element extraction")
        stages.insert(
            extraction_index + 1,
            {
                "section": "RX",
                "stage": "SRS extraction",
                "domain": "symbols",
                "description": "SRS observations extracted from the received grid for uplink sounding and future reciprocity studies.",
                "preview_kind": "constellation",
                "data": rx_meta.re_srs_symbols,
                "artifact_type": "constellation",
                "input_shape": [int(dim) for dim in np.asarray(rx_meta.rx_grid).shape],
                "output_shape": [int(dim) for dim in np.asarray(rx_meta.re_srs_symbols).shape],
            },
        )

    return _normalize_pipeline(stages)


def _build_prach_pipeline_trace(
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
    detected_id = int(rx_meta.detected_preamble_id or 0)
    expected_id = int(tx_meta.prach_preamble_id or 0)
    sequence = (
        np.asarray(tx_meta.prach_sequence, dtype=np.complex128)
        if tx_meta.prach_sequence is not None
        else tx_meta.modulation_symbols
    )
    stages = [
        {
            "section": "TX",
            "stage": "PRACH preamble identity",
            "domain": "bits",
            "description": "Random-access preamble identifier encoded as a compact bit label for GUI and KPI tracing.",
            "preview_kind": "bits",
            "data": tx_meta.payload_bits,
            "artifact_type": "bits",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.payload_bits).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.payload_bits).shape],
            "notes": f"Expected preamble ID: {expected_id}",
        },
        {
            "section": "TX",
            "stage": "PRACH preamble generation",
            "domain": "symbols",
            "description": "A Zadoff-Chu-derived PRACH preamble sequence is generated for the selected preamble index and cyclic shift.",
            "preview_kind": "constellation",
            "data": sequence,
            "artifact_type": "constellation",
            "input_shape": [int(dim) for dim in np.asarray(tx_meta.payload_bits).shape],
            "output_shape": [int(dim) for dim in np.asarray(sequence).shape],
            "notes": (
                f"Root sequence index: {int(tx_meta.prach_root_sequence_index or 25)} | "
                f"Cyclic shift: {int(tx_meta.prach_cyclic_shift or 13)}"
            ),
        },
        {
            "section": "TX",
            "stage": "PRACH occasion mapping",
            "domain": "grid",
            "description": "The PRACH preamble is mapped onto a simplified PRACH occasion occupying dedicated OFDM symbol(s) and subcarriers.",
            "preview_kind": "grid",
            "data": tx_meta.tx_grid,
            "artifact_type": "grid",
            "input_shape": [int(dim) for dim in np.asarray(sequence).shape],
            "output_shape": [int(dim) for dim in np.asarray(tx_meta.tx_grid).shape],
        },
        {
            "section": "TX",
            "stage": "OFDM modulation + CP",
            "domain": "waveform",
            "description": "Baseband PRACH waveform after OFDM modulation and cyclic-prefix insertion.",
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
            "description": "PRACH waveform after STO, CFO, phase noise, and IQ imbalance.",
            "preview_kind": "waveform",
            "data": impaired_waveform,
            "artifact_type": "waveform",
        },
        {
            "section": "Channel",
            "stage": "Fading / path loss / Doppler output" if not channel_state.get("gnu_radio_used", False) else "GNU Radio loopback output",
            "domain": "waveform",
            "description": "Waveform after channel propagation or GNU Radio loopback processing.",
            "preview_kind": "waveform",
            "data": channel_output_waveform,
            "artifact_type": "waveform",
        },
        {
            "section": "Channel",
            "stage": "AWGN / received waveform",
            "domain": "waveform",
            "description": "Final received PRACH waveform before timing and frequency correction.",
            "preview_kind": "waveform",
            "data": rx_waveform,
            "artifact_type": "waveform",
        },
        {
            "section": "RX",
            "stage": "Timing / CFO correction",
            "domain": "waveform",
            "description": "Waveform after coarse timing alignment and CFO correction.",
            "preview_kind": "waveform",
            "data": rx_meta.corrected_waveform,
            "artifact_type": "waveform",
        },
        {
            "section": "RX",
            "stage": "Remove CP",
            "domain": "grid",
            "description": "Cyclic prefix removed from the received PRACH OFDM symbols.",
            "preview_kind": "grid",
            "data": np.abs(rx_meta.cp_removed_tensor[0]),
            "artifact_type": "grid",
        },
        {
            "section": "RX",
            "stage": "FFT",
            "domain": "grid",
            "description": "FFT bins before active-subcarrier extraction for the PRACH occasion.",
            "preview_kind": "grid",
            "data": np.abs(rx_meta.fft_bins_tensor[0]),
            "artifact_type": "grid",
        },
        {
            "section": "RX",
            "stage": "PRACH resource extraction",
            "domain": "symbols",
            "description": "Extracted PRACH resource elements feeding the correlation detector.",
            "preview_kind": "constellation",
            "data": rx_meta.equalized_symbols,
            "artifact_type": "constellation",
            "notes": f"Extracted RE count: {int(rx_meta.re_data_symbols.size)}",
        },
        {
            "section": "RX",
            "stage": "PRACH correlation detector",
            "domain": "llr",
            "description": "Matched filtering across candidate preamble indices produces a normalized detection metric for each PRACH hypothesis.",
            "preview_kind": "llr",
            "data": np.asarray(rx_meta.prach_candidate_metrics if rx_meta.prach_candidate_metrics is not None else np.array([], dtype=np.float64)),
            "artifact_type": "llr",
            "notes": f"Peak metric: {float(rx_meta.prach_detection_metric or 0.0):.4f}",
        },
        {
            "section": "RX",
            "stage": "PRACH decision",
            "domain": "bits",
            "description": f"Detected PRACH preamble ID {detected_id}. Decision status: {'OK' if rx_meta.crc_ok else 'FAIL'}.",
            "preview_kind": "bits",
            "data": rx_meta.recovered_bits,
            "artifact_type": "bits",
            "notes": f"Expected ID: {expected_id} | Detected ID: {detected_id}",
        },
    ]
    return _normalize_pipeline(stages)


def simulate_link(
    config: Dict,
    channel_type: str | None = None,
    payload_bits: np.ndarray | None = None,
    seed_offset: int = 0,
    timeline_index: int = 0,
) -> Dict:
    config = deepcopy(config)
    if seed_offset:
        config.setdefault("simulation", {})
        config["simulation"]["seed"] = int(config.get("simulation", {}).get("seed", 0)) + int(seed_offset)
    transmitter = NrTransmitter(config)
    tx_result = transmitter.transmit(
        channel_type=channel_type or config.get("link", {}).get("channel_type", "data"),
        payload_bits=payload_bits,
        slot_index=int(timeline_index),
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
    if np.asarray(waveform).ndim > 1 and use_gnuradio:
        use_gnuradio = False
        gnuradio_requested = True
        gnuradio_error = "GNU Radio loopback is currently limited to single-port waveform runs."
    else:
        gnuradio_requested = use_gnuradio
        gnuradio_error: str | None = None

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
    spatial_matrix = _spatial_channel_matrix(config, tx_result.metadata, seed=simulation_seed + 17)
    spatial_tensor = _reference_channel_tensor(tx_result.metadata, fading_response, spatial_matrix)

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
            spatial_tensor = _reference_channel_tensor(tx_result.metadata, fading_response, spatial_matrix)
        waveform_tensor = np.asarray(waveform, dtype=np.complex128)
        if waveform_tensor.ndim == 1:
            waveform_tensor = waveform_tensor[None, :]
        if waveform_tensor.shape[0] > 1 or tx_result.metadata.spatial_layout.num_rx_antennas > 1:
            channel_output_waveform = spatial_matrix @ waveform_tensor
        else:
            channel_output_waveform = waveform_tensor.copy()
        awgn_result = awgn.apply(channel_output_waveform)
        rx_waveform = awgn_result.waveform
    else:
        channel_output_waveform = channel_output_waveform.copy()

    receiver = NrReceiver(config)
    channel_state = {
        "noise_variance": awgn_result.noise_variance,
        "cfo_hz": float(config.get("channel", {}).get("cfo_hz", 0.0)),
        "sto_samples": int(config.get("channel", {}).get("sto_samples", 0)),
        "reference_channel_grid": (
            np.mean(spatial_tensor, axis=(0, 1))
            if spatial_tensor.shape[0] > 1 or spatial_tensor.shape[1] > 1
            else _reference_channel_grid(tx_result.metadata, fading_response)
        ),
        "reference_channel_tensor": spatial_tensor,
        "spatial_channel_matrix": spatial_matrix,
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
    csi_feedback = _csi_feedback_for_result(result)
    if csi_feedback is not None:
        result["csi_feedback"] = csi_feedback
        result["pipeline"].insert(
            next((index for index, stage in enumerate(result["pipeline"]) if stage["stage"] == "Soft demapping"), len(result["pipeline"])),
            {
                "section": "RX",
                "stage": "CSI feedback",
                "domain": "control",
                "description": "CQI, PMI, and RI feedback are derived from the effective MIMO channel and current noise estimate for future scheduling and precoding decisions.",
                "preview_kind": "text",
                "data": csi_feedback,
                "artifact_type": "text",
                "input_shape": [int(dim) for dim in np.asarray(rx_result.effective_channel_tensor).shape],
                "output_shape": [3],
                "notes": (
                    f"CQI={int(csi_feedback['cqi'])} | PMI={csi_feedback['pmi']} | "
                    f"RI={int(csi_feedback['ri'])} | Capacity={float(csi_feedback['capacity_proxy_bps_hz']):.3f} b/s/Hz"
                ),
            },
        )
    return _annotate_result_slot(result, seed_offset)


def simulate_link_sequence(
    config: Dict,
    *,
    channel_type: str | None = None,
    payload_bits: np.ndarray | None = None,
    num_slots: int | None = None,
) -> Dict[str, Any]:
    capture_slots = max(1, int(num_slots or config.get("simulation", {}).get("capture_slots", 1)))
    active_channel_type = channel_type or config.get("link", {}).get("channel_type", "data")
    sequence_config = deepcopy(config)
    slot_results: list[Dict[str, Any]] = []
    csi_trace: list[dict[str, object]] = []
    schedule_trace: list[dict[str, object]] = []
    harq_trace: list[dict[str, object]] = []
    replay_enabled = bool(sequence_config.get("csi", {}).get("replay_feedback", False)) and _csi_replay_supported(active_channel_type)
    harq_manager = HarqProcessManager(sequence_config)
    scheduler_active = scheduler_enabled(sequence_config)
    harq_enabled = bool(harq_manager.enabled)
    payload_rng = np.random.default_rng(int(sequence_config.get("simulation", {}).get("seed", 0)) + 911)
    for timeline_index in range(capture_slots):
        grant_spec = select_grant_spec(sequence_config, timeline_index) if scheduler_active else {}
        slot_config = apply_grant_to_config(sequence_config, grant_spec) if grant_spec else sequence_config
        scheduled_channel_type = slot_config.get("link", {}).get("channel_type", active_channel_type)
        slot_payload_bits = payload_bits
        harq_info: dict[str, object] | None = None
        harq_process = None
        slot_harq_enabled = bool(harq_enabled and _harq_supported(scheduled_channel_type))
        if slot_harq_enabled:
            harq_process, slot_payload_bits, harq_info = harq_manager.prepare_payload(
                timeline_index=timeline_index,
                payload_bits=payload_bits,
                payload_size_bits=_payload_size_bits_for_channel(slot_config, scheduled_channel_type),
                rng=payload_rng,
                harq_process_id=int(grant_spec["harq_process_id"]) if "harq_process_id" in grant_spec else None,
                grant_ndi=int(grant_spec["ndi"]) if "ndi" in grant_spec else None,
                grant_rv=int(grant_spec["rv"]) if "rv" in grant_spec else None,
            )
            slot_config = deepcopy(sequence_config)
            if grant_spec:
                slot_config = apply_grant_to_config(slot_config, grant_spec)
            slot_config.setdefault("coding", {})
            slot_config["coding"]["redundancy_version"] = int(harq_info["rv"])

        slot_result = simulate_link(
            config=slot_config,
            channel_type=scheduled_channel_type,
            payload_bits=slot_payload_bits,
            seed_offset=timeline_index,
            timeline_index=timeline_index,
        )
        if slot_harq_enabled and harq_info is not None and harq_process is not None:
            harq_info["soft_observations"] = int(harq_process.attempt_index + 1)
            harq_feedback = _apply_harq_soft_combining(
                result=slot_result,
                process=harq_process,
                harq_info=harq_info,
                config=slot_config,
            )
            _insert_harq_pipeline_stage(slot_result, harq_feedback)
            harq_trace.append({"timeline_index": int(timeline_index), **dict(harq_feedback)})
            harq_process.complete_attempt(bool(slot_result["rx"].crc_ok))
        slot_grant = build_dci_grant(
            config=slot_config,
            tx_metadata=slot_result["tx"].metadata,
            slot_context=slot_result["slot_context"],
            harq_info=harq_info,
            grant_spec=grant_spec,
        )
        grant_payload = slot_grant.as_dict()
        slot_result["scheduled_grant"] = grant_payload
        if scheduler_active or slot_harq_enabled:
            _insert_scheduling_pipeline_stage(slot_result, grant_payload)
        slot_results.append(slot_result)
        schedule_trace.append(
            {
                **grant_payload,
                "scheduled_layers": int(grant_payload["num_layers"]),
                "scheduled_precoding_mode": str(grant_payload["precoding_mode"]),
                "scheduled_pmi": str(grant_payload["pmi"]),
                "scheduled_modulation": str(grant_payload["modulation"]),
                "scheduled_target_rate": float(grant_payload["target_rate"]),
                "harq_redundancy_version": int(grant_payload["rv"]),
                "harq_ndi": int(grant_payload["ndi"]),
            }
        )
        if slot_result.get("csi_feedback") is not None:
            csi_entry = {"timeline_index": int(timeline_index), **dict(slot_result["csi_feedback"])}
            csi_trace.append(csi_entry)
            harq_retx_pending = bool(slot_harq_enabled and harq_process is not None and harq_process.active)
            if replay_enabled and timeline_index < capture_slots - 1 and not harq_retx_pending:
                sequence_config = _apply_csi_feedback_to_config(
                    sequence_config,
                    slot_result["csi_feedback"],
                    allow_rank_update=payload_bits is None,
                )

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
        "csi_replay_enabled": replay_enabled,
        "scheduler_enabled": scheduler_active,
        "csi_trace": csi_trace,
        "schedule_trace": schedule_trace,
        "harq_enabled": bool(harq_trace),
        "harq_trace": harq_trace,
        "harq_ack_count": int(sum(1 for entry in harq_trace if bool(entry.get("ack", False)))),
        "harq_nack_count": int(sum(1 for entry in harq_trace if not bool(entry.get("ack", False)))),
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
    if str(active_channel_type).lower() in {"prach", "pbch", "broadcast"}:
        raise ValueError("File transfer is not supported over the PRACH/PBCH baseline.")
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
            timeline_index=chunk.index,
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
