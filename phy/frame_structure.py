from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .numerology import NumerologyConfig


@dataclass(slots=True)
class FrameAllocation:
    """Resource allocation abstraction for a single slot."""

    control_symbols: int
    pdsch_start_symbol: int
    pusch_start_symbol: int
    pucch_symbol_count: int
    prach_start_symbol: int
    prach_symbol_count: int
    prach_subcarriers: int
    prach_subcarrier_offset: int
    prach_period_slots: int
    prach_slot_offset: int
    csi_rs_symbols: List[int]
    srs_symbols: List[int]
    ptrs_symbols: List[int]
    rs_comb: int
    csi_rs_subcarrier_offset: int
    srs_subcarrier_offset: int
    ptrs_subcarrier_offset: int
    csi_rs_period_slots: int
    csi_rs_slot_offset: int
    srs_period_slots: int
    srs_slot_offset: int
    ptrs_period_slots: int
    ptrs_slot_offset: int
    ssb_start_symbol: int
    ssb_symbol_count: int
    ssb_subcarriers: int
    ssb_subcarrier_offset: int
    ssb_period_slots: int
    ssb_slot_offset: int
    pbch_dmrs_subcarrier_offset: int
    coreset_start_symbol: int
    coreset_symbol_count: int
    coreset_subcarriers: int
    coreset_subcarrier_offset: int
    search_space_stride: int
    search_space_offset: int
    search_space_symbols: List[int]
    search_space_period_slots: int
    search_space_slot_offset: int
    dmrs_symbols: List[int]
    control_subcarriers: int

    @property
    def pdcch_symbols(self) -> List[int]:
        start = max(0, int(self.coreset_start_symbol))
        count = max(1, int(self.coreset_symbol_count))
        return list(range(start, start + count))

    @staticmethod
    def _is_active(slot: int, period_slots: int, slot_offset: int) -> bool:
        period = max(1, int(period_slots))
        offset = int(slot_offset) % period
        return int(slot) % period == offset

    def csi_rs_active(self, slot: int = 0) -> bool:
        return self._is_active(slot, self.csi_rs_period_slots, self.csi_rs_slot_offset)

    def srs_active(self, slot: int = 0) -> bool:
        return self._is_active(slot, self.srs_period_slots, self.srs_slot_offset)

    def ptrs_active(self, slot: int = 0) -> bool:
        return self._is_active(slot, self.ptrs_period_slots, self.ptrs_slot_offset)

    def ssb_active(self, slot: int = 0) -> bool:
        return self._is_active(slot, self.ssb_period_slots, self.ssb_slot_offset)

    def prach_active(self, slot: int = 0) -> bool:
        return self._is_active(slot, self.prach_period_slots, self.prach_slot_offset)

    def search_space_active(self, slot: int = 0) -> bool:
        return self._is_active(slot, self.search_space_period_slots, self.search_space_slot_offset)

    def monitored_search_space_symbols(self, numerology: NumerologyConfig, slot: int = 0, *, force_active: bool = False) -> List[int]:
        if not force_active and not self.search_space_active(slot):
            return []
        valid_symbols = [symbol for symbol in self.pdcch_symbols if 0 <= symbol < numerology.symbols_per_slot]
        configured = [int(symbol) for symbol in self.search_space_symbols if int(symbol) in valid_symbols]
        return configured or valid_symbols

    @property
    def ssb_symbols(self) -> List[int]:
        start = max(0, int(self.ssb_start_symbol))
        count = max(1, int(self.ssb_symbol_count))
        return list(range(start, start + count))

    def pdsch_symbols(self, numerology: NumerologyConfig) -> List[int]:
        return [
            symbol
            for symbol in range(self.pdsch_start_symbol, numerology.symbols_per_slot)
            if symbol not in self.dmrs_symbols
        ]

    def pusch_symbols(self, numerology: NumerologyConfig) -> List[int]:
        return [
            symbol
            for symbol in range(self.pusch_start_symbol, numerology.symbols_per_slot)
            if symbol not in self.dmrs_symbols
        ]

    def pucch_symbols(self, numerology: NumerologyConfig) -> List[int]:
        count = max(1, min(self.pucch_symbol_count, numerology.symbols_per_slot))
        start = numerology.symbols_per_slot - count
        return [
            symbol
            for symbol in range(start, numerology.symbols_per_slot)
            if symbol not in self.dmrs_symbols
        ]

    def prach_symbols(self, numerology: NumerologyConfig) -> List[int]:
        count = max(1, min(self.prach_symbol_count, numerology.symbols_per_slot))
        start = max(0, min(int(self.prach_start_symbol), numerology.symbols_per_slot - 1))
        return [
            symbol
            for symbol in range(start, min(start + count, numerology.symbols_per_slot))
            if symbol not in self.dmrs_symbols
        ]


def build_default_allocation(numerology: NumerologyConfig, config: dict) -> FrameAllocation:
    frame_cfg = config.get("frame", {})
    reference_cfg = config.get("reference_signals", {})
    control_symbols = int(frame_cfg.get("control_symbols", 2))
    pdsch_start_symbol = int(frame_cfg.get("pdsch_start_symbol", control_symbols))
    pusch_start_symbol = int(frame_cfg.get("pusch_start_symbol", pdsch_start_symbol))
    pucch_symbol_count = int(frame_cfg.get("pucch_symbol_count", control_symbols))
    prach_start_symbol = int(frame_cfg.get("prach_start_symbol", 0))
    prach_symbol_count = int(frame_cfg.get("prach_symbol_count", 1))
    prach_period_slots = int(frame_cfg.get("prach_period_slots", 1))
    prach_slot_offset = int(frame_cfg.get("prach_slot_offset", 0))
    csi_rs_symbols = list(frame_cfg.get("csi_rs_symbols", [12])) if bool(reference_cfg.get("enable_csi_rs", True)) else []
    srs_symbols = list(frame_cfg.get("srs_symbols", [13])) if bool(reference_cfg.get("enable_srs", True)) else []
    ptrs_symbols = list(frame_cfg.get("ptrs_symbols", [6])) if bool(reference_cfg.get("enable_ptrs", True)) else []
    rs_comb = int(frame_cfg.get("rs_comb", 4))
    csi_rs_subcarrier_offset = int(frame_cfg.get("csi_rs_subcarrier_offset", 1))
    srs_subcarrier_offset = int(frame_cfg.get("srs_subcarrier_offset", 2))
    ptrs_subcarrier_offset = int(frame_cfg.get("ptrs_subcarrier_offset", 3))
    csi_rs_period_slots = int(frame_cfg.get("csi_rs_period_slots", 1))
    csi_rs_slot_offset = int(frame_cfg.get("csi_rs_slot_offset", 0))
    srs_period_slots = int(frame_cfg.get("srs_period_slots", 1))
    srs_slot_offset = int(frame_cfg.get("srs_slot_offset", 0))
    ptrs_period_slots = int(frame_cfg.get("ptrs_period_slots", 1))
    ptrs_slot_offset = int(frame_cfg.get("ptrs_slot_offset", 0))
    ssb_start_symbol = int(frame_cfg.get("ssb_start_symbol", 0))
    ssb_symbol_count = int(frame_cfg.get("ssb_symbol_count", 4))
    ssb_subcarriers = int(frame_cfg.get("ssb_subcarriers", min(240, numerology.active_subcarriers)))
    ssb_subcarrier_offset = int(frame_cfg.get("ssb_subcarrier_offset", 0))
    ssb_period_slots = int(frame_cfg.get("ssb_period_slots", 1))
    ssb_slot_offset = int(frame_cfg.get("ssb_slot_offset", 0))
    pbch_dmrs_subcarrier_offset = int(frame_cfg.get("pbch_dmrs_subcarrier_offset", 1))
    control_subcarriers = int(
        frame_cfg.get("control_subcarriers", min(72, numerology.active_subcarriers))
    )
    coreset_start_symbol = int(frame_cfg.get("coreset_start_symbol", 0))
    coreset_symbol_count = int(frame_cfg.get("coreset_symbol_count", control_symbols))
    coreset_subcarriers = int(frame_cfg.get("coreset_subcarriers", control_subcarriers))
    coreset_subcarrier_offset = int(frame_cfg.get("coreset_subcarrier_offset", 0))
    search_space_stride = int(frame_cfg.get("search_space_stride", 1))
    search_space_offset = int(frame_cfg.get("search_space_offset", 0))
    search_space_symbols = list(frame_cfg.get("search_space_symbols", []))
    search_space_period_slots = int(frame_cfg.get("search_space_period_slots", 1))
    search_space_slot_offset = int(frame_cfg.get("search_space_slot_offset", 0))
    dmrs_symbols = list(frame_cfg.get("dmrs_symbols", [2, 11]))
    prach_subcarriers = int(
        frame_cfg.get("prach_subcarriers", min(72, numerology.active_subcarriers))
    )
    prach_subcarrier_offset = int(frame_cfg.get("prach_subcarrier_offset", 0))
    return FrameAllocation(
        control_symbols=control_symbols,
        pdsch_start_symbol=pdsch_start_symbol,
        pusch_start_symbol=pusch_start_symbol,
        pucch_symbol_count=pucch_symbol_count,
        prach_start_symbol=max(0, min(prach_start_symbol, numerology.symbols_per_slot - 1)),
        prach_symbol_count=prach_symbol_count,
        prach_subcarriers=max(12, min(prach_subcarriers, numerology.active_subcarriers)),
        prach_subcarrier_offset=max(0, min(prach_subcarrier_offset, max(numerology.active_subcarriers - 12, 0))),
        prach_period_slots=max(1, prach_period_slots),
        prach_slot_offset=max(0, prach_slot_offset),
        csi_rs_symbols=[symbol for symbol in csi_rs_symbols if 0 <= symbol < numerology.symbols_per_slot],
        srs_symbols=[symbol for symbol in srs_symbols if 0 <= symbol < numerology.symbols_per_slot],
        ptrs_symbols=[symbol for symbol in ptrs_symbols if 0 <= symbol < numerology.symbols_per_slot],
        rs_comb=max(1, rs_comb),
        csi_rs_subcarrier_offset=max(0, csi_rs_subcarrier_offset),
        srs_subcarrier_offset=max(0, srs_subcarrier_offset),
        ptrs_subcarrier_offset=max(0, ptrs_subcarrier_offset),
        csi_rs_period_slots=max(1, csi_rs_period_slots),
        csi_rs_slot_offset=max(0, csi_rs_slot_offset),
        srs_period_slots=max(1, srs_period_slots),
        srs_slot_offset=max(0, srs_slot_offset),
        ptrs_period_slots=max(1, ptrs_period_slots),
        ptrs_slot_offset=max(0, ptrs_slot_offset),
        ssb_start_symbol=max(0, min(ssb_start_symbol, numerology.symbols_per_slot - 1)),
        ssb_symbol_count=max(
            1,
            min(
                ssb_symbol_count,
                numerology.symbols_per_slot - max(0, min(ssb_start_symbol, numerology.symbols_per_slot - 1)),
            ),
        ),
        ssb_subcarriers=max(12, min(ssb_subcarriers, numerology.active_subcarriers)),
        ssb_subcarrier_offset=max(0, min(ssb_subcarrier_offset, max(numerology.active_subcarriers - 12, 0))),
        ssb_period_slots=max(1, ssb_period_slots),
        ssb_slot_offset=max(0, ssb_slot_offset),
        pbch_dmrs_subcarrier_offset=max(0, pbch_dmrs_subcarrier_offset),
        coreset_start_symbol=max(0, min(coreset_start_symbol, numerology.symbols_per_slot - 1)),
        coreset_symbol_count=max(
            1,
            min(
                coreset_symbol_count,
                numerology.symbols_per_slot - max(0, min(coreset_start_symbol, numerology.symbols_per_slot - 1)),
            ),
        ),
        coreset_subcarriers=max(12, min(coreset_subcarriers, numerology.active_subcarriers)),
        coreset_subcarrier_offset=max(0, min(coreset_subcarrier_offset, max(numerology.active_subcarriers - 12, 0))),
        search_space_stride=max(1, search_space_stride),
        search_space_offset=max(0, search_space_offset),
        search_space_symbols=[symbol for symbol in search_space_symbols if 0 <= int(symbol) < numerology.symbols_per_slot],
        search_space_period_slots=max(1, search_space_period_slots),
        search_space_slot_offset=max(0, search_space_slot_offset),
        dmrs_symbols=[symbol for symbol in dmrs_symbols if 0 <= symbol < numerology.symbols_per_slot],
        control_subcarriers=max(12, min(control_subcarriers, numerology.active_subcarriers)),
    )
