from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


@dataclass(slots=True, frozen=True)
class DciGrant:
    grant_id: int
    timeline_index: int
    frame_index: int
    slot_index: int
    direction: str
    channel_type: str
    rnti: int
    harq_process_id: int
    ndi: int
    redundancy_version: int
    num_codewords: int
    num_layers: int
    num_ports: int
    modulation: str
    target_rate: float
    precoding_mode: str
    pmi: str
    start_symbol: int
    symbol_count: int
    vrb_mapping_type: str
    bwp_start_prb: int
    bwp_size_prb: int
    start_vrb: int
    num_vrbs: int
    allocated_prb_count: int
    allocated_re_count: int
    grant_source: str = "default"

    def as_dict(self) -> dict[str, object]:
        return {
            "grant_id": int(self.grant_id),
            "timeline_index": int(self.timeline_index),
            "frame_index": int(self.frame_index),
            "slot_index": int(self.slot_index),
            "direction": str(self.direction),
            "channel_type": str(self.channel_type),
            "rnti": int(self.rnti),
            "harq_process_id": int(self.harq_process_id),
            "ndi": int(self.ndi),
            "rv": int(self.redundancy_version),
            "num_codewords": int(self.num_codewords),
            "num_layers": int(self.num_layers),
            "num_ports": int(self.num_ports),
            "modulation": str(self.modulation),
            "target_rate": float(self.target_rate),
            "precoding_mode": str(self.precoding_mode),
            "pmi": str(self.pmi),
            "start_symbol": int(self.start_symbol),
            "symbol_count": int(self.symbol_count),
            "vrb_mapping_type": str(self.vrb_mapping_type),
            "bwp_start_prb": int(self.bwp_start_prb),
            "bwp_size_prb": int(self.bwp_size_prb),
            "start_vrb": int(self.start_vrb),
            "num_vrbs": int(self.num_vrbs),
            "allocated_prb_count": int(self.allocated_prb_count),
            "allocated_re_count": int(self.allocated_re_count),
            "grant_source": str(self.grant_source),
        }


def scheduler_enabled(config: Mapping[str, Any]) -> bool:
    return bool(dict(config.get("scheduler", {})).get("enabled", False))


def select_grant_spec(config: Mapping[str, Any], timeline_index: int) -> dict[str, object]:
    scheduler_cfg = dict(config.get("scheduler", {}))
    grants = scheduler_cfg.get("grants", [])
    if not scheduler_cfg.get("enabled", False) or not grants:
        return {}
    if not isinstance(grants, list):
        raise ValueError("scheduler.grants must be a list of grant dictionaries.")
    for grant in grants:
        if int(dict(grant).get("timeline_index", -1)) == int(timeline_index):
            return dict(grant)
    if bool(scheduler_cfg.get("repeat_grants", True)):
        return dict(grants[int(timeline_index) % len(grants)])
    return {}


def apply_grant_to_config(config: Mapping[str, Any], grant_spec: Mapping[str, Any]) -> dict[str, Any]:
    updated = deepcopy(dict(config))
    if not grant_spec:
        return updated

    if "direction" in grant_spec:
        updated.setdefault("link", {})["direction"] = str(grant_spec["direction"]).lower()
    if "channel_type" in grant_spec:
        updated.setdefault("link", {})["channel_type"] = str(grant_spec["channel_type"]).lower()
    if "modulation" in grant_spec:
        updated.setdefault("modulation", {})["scheme"] = str(grant_spec["modulation"]).upper()
    if "target_rate" in grant_spec:
        updated.setdefault("coding", {})["target_rate"] = float(grant_spec["target_rate"])
    if "rv" in grant_spec:
        updated.setdefault("coding", {})["redundancy_version"] = int(grant_spec["rv"])
    if "num_codewords" in grant_spec:
        updated.setdefault("spatial", {})["num_codewords"] = int(grant_spec["num_codewords"])
    if "num_layers" in grant_spec:
        updated.setdefault("spatial", {})["num_layers"] = int(grant_spec["num_layers"])
    if "num_ports" in grant_spec:
        updated.setdefault("spatial", {})["num_ports"] = int(grant_spec["num_ports"])
    if "num_tx_antennas" in grant_spec:
        updated.setdefault("spatial", {})["num_tx_antennas"] = int(grant_spec["num_tx_antennas"])
    if "num_rx_antennas" in grant_spec:
        updated.setdefault("spatial", {})["num_rx_antennas"] = int(grant_spec["num_rx_antennas"])
    if "precoding_mode" in grant_spec:
        updated.setdefault("precoding", {})["mode"] = str(grant_spec["precoding_mode"]).lower()
    if "pmi" in grant_spec:
        updated.setdefault("precoding", {})["pmi"] = str(grant_spec["pmi"])
    if "rnti" in grant_spec:
        updated.setdefault("scrambling", {})["rnti"] = int(grant_spec["rnti"])
    vrb_keys = {
        "mapping_type",
        "vrb_mapping_type",
        "bwp_start_prb",
        "bwp_size_prb",
        "start_vrb",
        "num_vrbs",
        "interleaver_size",
    }
    if any(key in grant_spec for key in vrb_keys):
        vrb_cfg = updated.setdefault("vrb_mapping", {})
        if "vrb_mapping_type" in grant_spec:
            vrb_cfg["mapping_type"] = str(grant_spec["vrb_mapping_type"]).lower()
        if "mapping_type" in grant_spec:
            vrb_cfg["mapping_type"] = str(grant_spec["mapping_type"]).lower()
        for key in ("bwp_start_prb", "bwp_size_prb", "start_vrb", "num_vrbs", "interleaver_size"):
            if key in grant_spec:
                vrb_cfg[key] = int(grant_spec[key])
        vrb_cfg["enabled"] = True
    return updated


def build_dci_grant(
    *,
    config: Mapping[str, Any],
    tx_metadata: Any,
    slot_context: Mapping[str, Any],
    harq_info: Mapping[str, Any] | None = None,
    grant_spec: Mapping[str, Any] | None = None,
) -> DciGrant:
    scheduler_cfg = dict(config.get("scheduler", {}))
    frame_index = int(slot_context.get("frame_index", 0))
    slot_index = int(slot_context.get("slot_index", 0))
    timeline_index = int(slot_context.get("timeline_index", 0))
    allocation = tx_metadata.allocation
    direction = str(getattr(tx_metadata, "direction", config.get("link", {}).get("direction", "downlink"))).lower()
    channel_type = str(getattr(tx_metadata, "channel_type", config.get("link", {}).get("channel_type", "data"))).lower()
    if direction == "uplink":
        start_symbol = int(getattr(allocation, "pusch_start_symbol", getattr(allocation, "pdsch_start_symbol", 0)))
    elif channel_type in {"control", "pdcch"}:
        start_symbol = int(getattr(allocation, "coreset_start_symbol", 0))
    else:
        start_symbol = int(getattr(allocation, "pdsch_start_symbol", 0))
    symbol_count = max(1, int(tx_metadata.numerology.symbols_per_slot) - start_symbol)
    positions = np.asarray(getattr(tx_metadata.mapping, "positions", np.zeros((0, 2), dtype=int)), dtype=int)
    harq_payload = dict(harq_info or {})
    spec = dict(grant_spec or {})
    vrb_mapping = getattr(tx_metadata, "vrb_mapping", getattr(tx_metadata.mapping, "vrb_mapping", None))
    return DciGrant(
        grant_id=int(spec.get("grant_id", timeline_index)),
        timeline_index=timeline_index,
        frame_index=frame_index,
        slot_index=slot_index,
        direction=direction,
        channel_type=channel_type,
        rnti=int(config.get("scrambling", {}).get("rnti", scheduler_cfg.get("rnti", 0x1234))),
        harq_process_id=int(harq_payload.get("process_id", spec.get("harq_process_id", -1))),
        ndi=int(harq_payload.get("ndi", spec.get("ndi", 0))),
        redundancy_version=int(harq_payload.get("rv", config.get("coding", {}).get("redundancy_version", spec.get("rv", 0)))),
        num_codewords=int(tx_metadata.spatial_layout.num_codewords),
        num_layers=int(tx_metadata.spatial_layout.num_layers),
        num_ports=int(tx_metadata.spatial_layout.num_ports),
        modulation=str(getattr(tx_metadata, "modulation", config.get("modulation", {}).get("scheme", "QPSK"))),
        target_rate=float(config.get("coding", {}).get("target_rate", 0.5)),
        precoding_mode=str(config.get("precoding", {}).get("mode", getattr(tx_metadata, "precoding_mode", "identity"))),
        pmi=str(config.get("precoding", {}).get("pmi", "n/a")),
        start_symbol=start_symbol,
        symbol_count=symbol_count,
        vrb_mapping_type=str(getattr(vrb_mapping, "mapping_type", "n/a")),
        bwp_start_prb=int(getattr(vrb_mapping, "bwp_start_prb", 0)),
        bwp_size_prb=int(getattr(vrb_mapping, "bwp_size_prb", 0)),
        start_vrb=int(getattr(vrb_mapping, "start_vrb", 0)),
        num_vrbs=int(getattr(vrb_mapping, "num_vrbs", 0)),
        allocated_prb_count=int(getattr(vrb_mapping, "allocated_prb_count", 0)),
        allocated_re_count=int(positions.shape[0]),
        grant_source="configured" if spec else "default",
    )
