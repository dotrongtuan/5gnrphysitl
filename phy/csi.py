from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np

from .precoding import build_precoder_matrix, build_type1_single_panel_codebook


@dataclass(slots=True, frozen=True)
class CsiFeedback:
    cqi: int
    pmi: str
    ri: int
    modulation: str
    target_rate: float
    rank_scores: np.ndarray
    codebook_scores: dict[str, float]
    singular_values: np.ndarray
    estimated_snr_db: float
    capacity_proxy_bps_hz: float

    def as_dict(self) -> dict[str, object]:
        return {
            "cqi": int(self.cqi),
            "pmi": str(self.pmi),
            "ri": int(self.ri),
            "modulation": str(self.modulation),
            "target_rate": float(self.target_rate),
            "rank_scores": [float(value) for value in np.asarray(self.rank_scores, dtype=float).tolist()],
            "codebook_scores": {str(key): float(value) for key, value in self.codebook_scores.items()},
            "singular_values": [float(value) for value in np.asarray(self.singular_values, dtype=float).tolist()],
            "estimated_snr_db": float(self.estimated_snr_db),
            "capacity_proxy_bps_hz": float(self.capacity_proxy_bps_hz),
        }


def _candidate_modes(config: Mapping[str, Any] | None) -> list[str]:
    csi_cfg = dict(config.get("csi", {})) if config else {}
    candidate_modes = csi_cfg.get("candidate_precoders", ["identity", "dft"])
    if isinstance(candidate_modes, str):
        candidate_modes = [candidate_modes]
    normalized = [str(mode).lower() for mode in candidate_modes if str(mode).strip()]
    return normalized or ["identity", "dft"]


def _capacity_proxy(channel_matrix: np.ndarray, noise_variance: float, layers: int) -> float:
    effective = np.asarray(channel_matrix, dtype=np.complex128)
    gram = np.conjugate(effective.T) @ effective
    snr_linear = 1.0 / max(float(noise_variance), 1e-9)
    identity = np.eye(gram.shape[0], dtype=np.complex128)
    metric = identity + (snr_linear / max(int(layers), 1)) * gram
    sign, logdet = np.linalg.slogdet(metric)
    if sign <= 0:
        return float("-inf")
    return float(np.real(logdet) / np.log(2.0))


CQI_TO_MCS = [
    ("QPSK", 0.12),
    ("QPSK", 0.19),
    ("QPSK", 0.30),
    ("QPSK", 0.44),
    ("QPSK", 0.59),
    ("16QAM", 0.37),
    ("16QAM", 0.48),
    ("16QAM", 0.60),
    ("64QAM", 0.45),
    ("64QAM", 0.55),
    ("64QAM", 0.65),
    ("64QAM", 0.75),
    ("256QAM", 0.65),
    ("256QAM", 0.72),
    ("256QAM", 0.80),
    ("256QAM", 0.89),
]


def _cqi_from_snr(estimated_snr_db: float, offset_db: float = 0.0) -> int:
    adjusted = float(estimated_snr_db) + float(offset_db)
    thresholds = np.array([-6.0, -4.0, -2.0, 0.0, 1.5, 3.0, 4.5, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0], dtype=float)
    return int(np.clip(np.searchsorted(thresholds, adjusted, side="right"), 0, 15))


def _expand_candidate_precoders(modes: Iterable[str], num_ports: int, rank: int) -> list[tuple[str, np.ndarray]]:
    candidates: list[tuple[str, np.ndarray]] = []
    for mode in modes:
        resolved = str(mode).lower()
        if resolved == "type1_sp":
            codebook = build_type1_single_panel_codebook(num_ports=num_ports, num_layers=rank)
            candidates.extend((label, matrix.copy()) for label, matrix in codebook.items())
        else:
            candidates.append((resolved, build_precoder_matrix(resolved, num_ports=num_ports, num_layers=rank)))
    return candidates


def report_csi(
    *,
    channel_tensor: np.ndarray,
    noise_variance: float,
    max_rank: int,
    candidate_precoders: Iterable[str],
    cqi_snr_offset_db: float = 0.0,
) -> CsiFeedback:
    tensor = np.asarray(channel_tensor, dtype=np.complex128)
    if tensor.ndim != 4:
        raise ValueError("channel_tensor must have shape (rx_ant, port, symbol, subcarrier).")

    average_channel = np.mean(tensor, axis=(2, 3))
    singular_values = np.linalg.svd(average_channel, compute_uv=False)
    rank_limit = max(1, min(int(max_rank), average_channel.shape[0], average_channel.shape[1]))
    modes = [str(mode).lower() for mode in candidate_precoders]
    best_mode = modes[0] if modes else "identity"
    best_rank = 1
    best_capacity = float("-inf")
    rank_scores = np.full(rank_limit, float("-inf"), dtype=float)
    codebook_scores: dict[str, float] = {}

    for rank in range(1, rank_limit + 1):
        rank_best = float("-inf")
        for label, precoder in _expand_candidate_precoders(modes, num_ports=average_channel.shape[1], rank=rank):
            projected_channel = average_channel @ precoder
            capacity = _capacity_proxy(projected_channel, noise_variance=noise_variance, layers=rank)
            if rank == 1 or capacity > codebook_scores.get(label, float("-inf")):
                codebook_scores[label] = capacity
            if capacity > rank_best:
                rank_best = capacity
            if capacity > best_capacity:
                best_capacity = capacity
                best_mode = label
                best_rank = rank
        rank_scores[rank - 1] = rank_best

    snr_linear = 1.0 / max(float(noise_variance), 1e-9)
    estimated_snr_db = float(10.0 * np.log10(max(snr_linear, 1e-9)))
    cqi = _cqi_from_snr(estimated_snr_db, offset_db=cqi_snr_offset_db)
    modulation, target_rate = CQI_TO_MCS[cqi]
    return CsiFeedback(
        cqi=cqi,
        pmi=best_mode,
        ri=best_rank,
        modulation=modulation,
        target_rate=float(target_rate),
        rank_scores=rank_scores,
        codebook_scores=codebook_scores,
        singular_values=np.asarray(singular_values, dtype=float),
        estimated_snr_db=estimated_snr_db,
        capacity_proxy_bps_hz=float(best_capacity),
    )
