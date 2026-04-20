from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np


def _rv_sequence(values: object) -> tuple[int, ...]:
    if isinstance(values, str):
        parts = [part.strip() for part in values.split(",") if part.strip()]
    else:
        parts = list(values or [0, 2, 3, 1])
    sequence = tuple(int(value) for value in parts)
    return sequence or (0, 2, 3, 1)


@dataclass(slots=True)
class HarqProcessState:
    process_id: int
    rv_sequence: tuple[int, ...]
    max_retransmissions: int
    payload_bits: np.ndarray | None = None
    ndi: int = 0
    attempt_index: int = 0
    rv_index: int = 0
    soft_buffers: tuple[np.ndarray, ...] = field(default_factory=tuple)
    last_ack: bool | None = None

    @property
    def active(self) -> bool:
        return self.payload_bits is not None

    @property
    def redundancy_version(self) -> int:
        return int(self.rv_sequence[self.rv_index % len(self.rv_sequence)])

    def start_new_data(self, payload_bits: np.ndarray, *, ndi: int | None = None) -> None:
        self.payload_bits = np.asarray(payload_bits, dtype=np.uint8).copy()
        self.ndi = int(ndi) & 1 if ndi is not None else 1 - int(self.ndi)
        self.attempt_index = 0
        self.rv_index = 0
        self.soft_buffers = ()
        self.last_ack = None

    def set_redundancy_version(self, rv: int) -> None:
        rv = int(rv)
        if rv in self.rv_sequence:
            self.rv_index = self.rv_sequence.index(rv)
            return
        self.rv_sequence = (rv, *tuple(value for value in self.rv_sequence if value != rv))
        self.rv_index = 0

    def combine(self, rate_recovered_by_codeword: tuple[np.ndarray, ...], *, soft_combining: bool) -> tuple[np.ndarray, ...]:
        current = tuple(np.asarray(block, dtype=np.float64).copy() for block in rate_recovered_by_codeword)
        if not soft_combining or not self.soft_buffers:
            self.soft_buffers = current
            return tuple(block.copy() for block in self.soft_buffers)

        combined: list[np.ndarray] = []
        for index, block in enumerate(current):
            previous = self.soft_buffers[index] if index < len(self.soft_buffers) else np.zeros_like(block)
            length = min(previous.size, block.size)
            merged = block.copy()
            if length:
                merged[:length] = previous[:length] + block[:length]
            combined.append(merged)
        self.soft_buffers = tuple(combined)
        return tuple(block.copy() for block in self.soft_buffers)

    def complete_attempt(self, ack: bool) -> None:
        self.last_ack = bool(ack)
        if ack or self.attempt_index >= self.max_retransmissions:
            self.payload_bits = None
            self.attempt_index = 0
            self.rv_index = 0
            self.soft_buffers = ()
            return
        self.attempt_index += 1
        self.rv_index = (self.rv_index + 1) % len(self.rv_sequence)


class HarqProcessManager:
    """Stop-and-wait HARQ baseline with soft-combining buffers.

    The current P3 baseline deliberately keeps scheduling simple: one active
    process is advanced through the captured slot sequence. The state object is
    process-indexed so future scheduler work can fan this out to multiple HARQ
    processes without changing the result contract.
    """

    def __init__(self, config: Mapping[str, Any] | None) -> None:
        harq_cfg = dict((config or {}).get("harq", {}))
        self.enabled = bool(harq_cfg.get("enabled", False))
        self.soft_combining = bool(harq_cfg.get("soft_combining", True))
        self.process_count = max(1, int(harq_cfg.get("process_count", 1)))
        self.max_retransmissions = max(0, int(harq_cfg.get("max_retransmissions", 3)))
        self.rv_sequence = _rv_sequence(harq_cfg.get("rv_sequence", [0, 2, 3, 1]))
        self.processes = tuple(
            HarqProcessState(
                process_id=index,
                rv_sequence=self.rv_sequence,
                max_retransmissions=self.max_retransmissions,
            )
            for index in range(self.process_count)
        )

    def process_for_slot(self, timeline_index: int, harq_process_id: int | None = None) -> HarqProcessState:
        if harq_process_id is not None:
            return self.processes[int(harq_process_id) % self.process_count]
        return self.processes[int(timeline_index) % self.process_count]

    def prepare_payload(
        self,
        *,
        timeline_index: int,
        payload_bits: np.ndarray | None,
        payload_size_bits: int,
        rng: np.random.Generator,
        harq_process_id: int | None = None,
        grant_ndi: int | None = None,
        grant_rv: int | None = None,
    ) -> tuple[HarqProcessState, np.ndarray, dict[str, object]]:
        process = self.process_for_slot(timeline_index, harq_process_id=harq_process_id)
        if not self.enabled:
            if payload_bits is not None:
                payload = np.asarray(payload_bits, dtype=np.uint8).copy()
            else:
                payload = rng.integers(0, 2, int(payload_size_bits), dtype=np.uint8)
            return process, payload, {
                "enabled": False,
                "process_id": int(process.process_id),
                "attempt_index": 0,
                "rv": 0,
                "ndi": int(process.ndi),
                "new_data": True,
                "grant_controlled": bool(harq_process_id is not None or grant_ndi is not None or grant_rv is not None),
            }

        desired_ndi = int(grant_ndi) & 1 if grant_ndi is not None else None
        ndi_toggled = bool(process.active and desired_ndi is not None and desired_ndi != int(process.ndi))
        new_data = bool(not process.active or ndi_toggled)
        if new_data:
            payload = (
                np.asarray(payload_bits, dtype=np.uint8).copy()
                if payload_bits is not None
                else rng.integers(0, 2, int(payload_size_bits), dtype=np.uint8)
            )
            process.start_new_data(payload, ndi=desired_ndi)
        elif desired_ndi is not None:
            process.ndi = desired_ndi

        if grant_rv is not None:
            process.set_redundancy_version(int(grant_rv))

        assert process.payload_bits is not None
        return process, process.payload_bits.copy(), {
            "enabled": True,
            "process_id": int(process.process_id),
            "attempt_index": int(process.attempt_index),
            "rv": int(process.redundancy_version),
            "ndi": int(process.ndi),
            "new_data": bool(new_data),
            "soft_combining": bool(self.soft_combining),
            "grant_controlled": bool(harq_process_id is not None or grant_ndi is not None or grant_rv is not None),
        }
