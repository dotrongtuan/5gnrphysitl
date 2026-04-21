from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .numerology import NumerologyConfig


SUPPORTED_VRB_MAPPING_TYPES = {"non_interleaved", "interleaved"}


@dataclass(slots=True, frozen=True)
class VrbPrbMapping:
    """Baseline NR-style VRB-to-PRB allocation for data-channel RE mapping."""

    enabled: bool
    mapping_type: str
    bwp_start_prb: int
    bwp_size_prb: int
    start_vrb: int
    num_vrbs: int
    interleaver_size: int
    active_prb_count: int
    vrb_indices: np.ndarray
    prb_indices: np.ndarray
    subcarrier_indices: np.ndarray

    @property
    def allocated_prb_count(self) -> int:
        return int(self.prb_indices.size)

    @property
    def allocated_subcarrier_count(self) -> int:
        return int(self.subcarrier_indices.size)

    def mask(self, active_subcarriers: int) -> np.ndarray:
        mask = np.zeros(int(active_subcarriers), dtype=np.uint8)
        indices = self.subcarrier_indices
        if indices.size:
            mask[indices] = 1
        return mask

    def grid_mask(self, symbols_per_slot: int, active_subcarriers: int) -> np.ndarray:
        return np.tile(self.mask(active_subcarriers), (int(symbols_per_slot), 1)).astype(np.float32)

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "mapping_type": str(self.mapping_type),
            "bwp_start_prb": int(self.bwp_start_prb),
            "bwp_size_prb": int(self.bwp_size_prb),
            "start_vrb": int(self.start_vrb),
            "num_vrbs": int(self.num_vrbs),
            "interleaver_size": int(self.interleaver_size),
            "active_prb_count": int(self.active_prb_count),
            "allocated_prb_count": int(self.allocated_prb_count),
            "allocated_subcarrier_count": int(self.allocated_subcarrier_count),
            "vrb_indices": self.vrb_indices.astype(int).tolist(),
            "prb_indices": self.prb_indices.astype(int).tolist(),
            "subcarrier_indices": self.subcarrier_indices.astype(int).tolist(),
        }


def _normalize_mapping_type(value: object) -> str:
    mapping_type = str(value or "non_interleaved").strip().lower().replace("-", "_")
    if mapping_type in {"localized", "noninterleaved", "non_interleaved"}:
        return "non_interleaved"
    if mapping_type in {"distributed", "interleaved"}:
        return "interleaved"
    raise ValueError("vrb_mapping.mapping_type must be one of: non_interleaved, interleaved.")


def _interleaved_prb_index(vrb_index: int, bwp_size_prb: int, interleaver_size: int) -> int:
    """Teaching-friendly VRB interleaver that spreads adjacent VRBs over the BWP."""

    size = max(1, int(bwp_size_prb))
    rows = max(1, min(int(interleaver_size), size))
    columns = int(np.ceil(size / rows))
    candidate = int(vrb_index % rows) * columns + int(vrb_index // rows)
    if candidate >= size:
        ordered = [
            row * columns + column
            for column in range(columns)
            for row in range(rows)
            if row * columns + column < size
        ]
        return int(ordered[int(vrb_index) % len(ordered)])
    return candidate


def build_vrb_prb_mapping(config: Mapping[str, Any] | None, numerology: NumerologyConfig) -> VrbPrbMapping:
    cfg = dict((config or {}).get("vrb_mapping", {}))
    active_prb_count = max(1, int(numerology.active_subcarriers) // 12)
    enabled = bool(cfg.get("enabled", True))
    mapping_type = _normalize_mapping_type(cfg.get("mapping_type", cfg.get("vrb_to_prb_mapping", "non_interleaved")))
    bwp_start_prb = max(0, int(cfg.get("bwp_start_prb", 0)))
    bwp_start_prb = min(bwp_start_prb, active_prb_count - 1)
    default_bwp_size = active_prb_count - bwp_start_prb
    bwp_size_prb = int(cfg.get("bwp_size_prb", default_bwp_size) or default_bwp_size)
    bwp_size_prb = max(1, min(bwp_size_prb, active_prb_count - bwp_start_prb))
    start_vrb = max(0, int(cfg.get("start_vrb", 0)))
    start_vrb = min(start_vrb, bwp_size_prb - 1)
    default_num_vrbs = bwp_size_prb - start_vrb
    num_vrbs = int(cfg.get("num_vrbs", default_num_vrbs) or default_num_vrbs)
    num_vrbs = max(1, min(num_vrbs, bwp_size_prb - start_vrb))
    interleaver_size = max(1, int(cfg.get("interleaver_size", 2)))

    if not enabled:
        start_vrb = 0
        num_vrbs = bwp_size_prb
        mapping_type = "non_interleaved"

    vrb_indices = np.arange(start_vrb, start_vrb + num_vrbs, dtype=int)
    if mapping_type == "interleaved":
        relative_prbs = np.asarray(
            [_interleaved_prb_index(int(vrb), bwp_size_prb, interleaver_size) for vrb in vrb_indices],
            dtype=int,
        )
    else:
        relative_prbs = vrb_indices.copy()
    prb_indices = (bwp_start_prb + relative_prbs).astype(int)
    prb_indices = prb_indices[(0 <= prb_indices) & (prb_indices < active_prb_count)]
    subcarrier_indices = (
        np.concatenate([np.arange(int(prb) * 12, int(prb) * 12 + 12, dtype=int) for prb in prb_indices])
        if prb_indices.size
        else np.array([], dtype=int)
    )
    subcarrier_indices = subcarrier_indices[subcarrier_indices < int(numerology.active_subcarriers)]

    return VrbPrbMapping(
        enabled=enabled,
        mapping_type=mapping_type,
        bwp_start_prb=bwp_start_prb,
        bwp_size_prb=bwp_size_prb,
        start_vrb=start_vrb,
        num_vrbs=num_vrbs,
        interleaver_size=interleaver_size,
        active_prb_count=active_prb_count,
        vrb_indices=vrb_indices,
        prb_indices=prb_indices,
        subcarrier_indices=subcarrier_indices,
    )
