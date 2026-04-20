from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from experiments.common import simulate_link_sequence
from utils.io import load_yaml
from utils.validators import deep_merge, validate_config


def _scheduler_config() -> dict:
    root = Path(__file__).resolve().parents[1]
    base = load_yaml(root / "configs" / "default.yaml")
    override = load_yaml(root / "configs" / "scenario_scheduler_grant_replay.yaml")
    return validate_config(deep_merge(deepcopy(base), override))


def test_scheduler_replays_configured_grant_sequence() -> None:
    result = simulate_link_sequence(_scheduler_config())
    schedule = result["sequence_summary"]["schedule_trace"]

    assert result["sequence_summary"]["scheduler_enabled"] is True
    assert [entry["grant_id"] for entry in schedule] == [100, 101, 100, 101]
    assert [entry["scheduled_modulation"] for entry in schedule] == ["QPSK", "16QAM", "QPSK", "16QAM"]
    assert [entry["scheduled_layers"] for entry in schedule] == [1, 2, 1, 2]
    assert [entry["scheduled_precoding_mode"] for entry in schedule] == ["identity", "dft", "identity", "dft"]


def test_scheduler_grant_is_exposed_in_each_slot_pipeline() -> None:
    result = simulate_link_sequence(_scheduler_config())

    for history_entry in result["slot_history"]:
        slot_result = history_entry["result"]
        assert slot_result["scheduled_grant"]["grant_source"] == "configured"
        assert slot_result["pipeline"][0]["stage"] == "DCI-like scheduling grant"
