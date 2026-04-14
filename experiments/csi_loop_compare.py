from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from experiments.common import simulate_link_sequence
from utils.io import save_dataframe_csv, save_markdown_report


def _plot_metric(dataframe: pd.DataFrame, *, y_column: str, title: str, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for label, group in dataframe.groupby("loop_mode"):
        ordered = group.sort_values("snr_db")
        axis.plot(ordered["snr_db"], ordered[y_column], marker="o", label=label)
    axis.set_title(title)
    axis.set_xlabel("snr_db")
    axis.set_ylabel(y_column)
    axis.grid(True, alpha=0.3)
    axis.legend(loc="best", fontsize=8)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def run_experiment(config: dict, output_dir: str | Path) -> pd.DataFrame:
    output_dir = Path(output_dir) / "csi_loop_compare"
    snr_values = config.get("experiments", {}).get("snr_sweep_db", [0, 4, 8, 12, 16, 20])

    records: list[dict] = []
    for closed_loop in [False, True]:
        loop_label = "closed_loop" if closed_loop else "open_loop"
        for snr_db in snr_values:
            trial_cfg = deepcopy(config)
            trial_cfg.setdefault("channel", {})["snr_db"] = float(snr_db)
            trial_cfg.setdefault("csi", {})["enabled"] = True
            trial_cfg["csi"]["replay_feedback"] = bool(closed_loop)
            result = simulate_link_sequence(trial_cfg)
            row = result["kpis"].as_dict()
            latest_feedback = dict(result.get("csi_feedback", {}))
            schedule_trace = list(result.get("sequence_summary", {}).get("schedule_trace", []))
            row.update(
                {
                    "loop_mode": loop_label,
                    "closed_loop": 1.0 if closed_loop else 0.0,
                    "snr_db": float(snr_db),
                    "capture_slots": int(result.get("captured_slots", 1)),
                    "latest_cqi": int(latest_feedback.get("cqi", 0)) if latest_feedback else 0,
                    "latest_ri": int(latest_feedback.get("ri", 1)) if latest_feedback else 1,
                    "latest_pmi": str(latest_feedback.get("pmi", "n/a")) if latest_feedback else "n/a",
                    "latest_modulation": str(latest_feedback.get("modulation", trial_cfg.get("modulation", {}).get("scheme", "QPSK"))),
                    "latest_target_rate": float(latest_feedback.get("target_rate", trial_cfg.get("coding", {}).get("target_rate", 0.5))),
                    "average_scheduled_layers": float(
                        sum(int(entry.get("scheduled_layers", 1)) for entry in schedule_trace) / max(len(schedule_trace), 1)
                    ),
                    "average_scheduled_target_rate": float(
                        sum(float(entry.get("scheduled_target_rate", 0.5)) for entry in schedule_trace) / max(len(schedule_trace), 1)
                    ),
                }
            )
            records.append(row)

    dataframe = pd.DataFrame(records)
    save_dataframe_csv(records, output_dir / "csi_loop_compare.csv")
    _plot_metric(
        dataframe,
        y_column="throughput_bps",
        title="CSI loop throughput vs SNR",
        output_path=output_dir / "throughput_vs_snr.png",
    )
    _plot_metric(
        dataframe,
        y_column="bler",
        title="CSI loop BLER vs SNR",
        output_path=output_dir / "bler_vs_snr.png",
    )
    _plot_metric(
        dataframe,
        y_column="average_scheduled_target_rate",
        title="CSI loop average scheduled target rate vs SNR",
        output_path=output_dir / "target_rate_vs_snr.png",
    )
    save_markdown_report(
        "CSI Loop Compare",
        [
            (
                "Configuration",
                f"Spatial layout: {config.get('spatial', {})}\n\n"
                f"Candidate precoders: {config.get('csi', {}).get('candidate_precoders', ['identity', 'dft', 'type1_sp'])}\n\n"
                f"Capture slots: {config.get('simulation', {}).get('capture_slots', 1)}",
            ),
            ("Summary", "```\n" + dataframe.to_string(index=False) + "\n```"),
        ],
        output_dir / "summary.md",
    )
    return dataframe
