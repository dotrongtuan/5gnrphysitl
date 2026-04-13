from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from experiments.common import simulate_file_transfer
from utils.io import save_dataframe_csv, save_markdown_report


def _resolve_input_files(config: dict) -> list[Path]:
    project_root = Path(__file__).resolve().parent.parent
    payload_io = config.get("payload_io", {})
    configured_files = list(payload_io.get("sweep_files", []) or [])
    if not configured_files:
        tx_file = str(payload_io.get("tx_file_path", "")).strip()
        if tx_file:
            configured_files = [tx_file]

    resolved: list[Path] = []
    for item in configured_files:
        path = Path(item)
        if not path.is_absolute():
            path = project_root / path
        if path.exists() and path.is_file():
            resolved.append(path.resolve())

    if resolved:
        return resolved

    input_dir = project_root / "input"
    if input_dir.exists():
        resolved = sorted(
            path.resolve()
            for path in input_dir.iterdir()
            if path.is_file() and path.name.lower() != "readme.md"
        )
    if not resolved:
        raise ValueError(
            "No input files were found for file_transfer_sweep. Set payload_io.tx_file_path or payload_io.sweep_files."
        )
    return resolved


def _plot_grouped_metric(
    dataframe: pd.DataFrame,
    *,
    y_column: str,
    title: str,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for filename, group in dataframe.groupby("source_filename"):
        ordered = group.sort_values("snr_db")
        axis.plot(ordered["snr_db"], ordered[y_column], marker="o", label=filename)
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
    output_dir = Path(output_dir) / "file_transfer_sweep"
    snr_values = config.get("experiments", {}).get(
        "file_transfer_snr_sweep_db",
        config.get("experiments", {}).get("snr_sweep_db", [0, 2, 4, 6, 8]),
    )
    source_files = _resolve_input_files(config)

    records: list[dict] = []
    for source_path in source_files:
        for snr in snr_values:
            trial_cfg = deepcopy(config)
            trial_cfg.setdefault("channel", {})["snr_db"] = float(snr)
            result = simulate_file_transfer(trial_cfg, source_path=str(source_path), output_dir=output_dir / "rx_outputs")
            transfer = result["file_transfer"]
            row = result["kpis"].as_dict()
            row.update(
                {
                    "source_filename": source_path.name,
                    "source_path": str(source_path),
                    "media_kind": transfer["media_kind"],
                    "snr_db": float(snr),
                    "success": bool(transfer["success"]),
                    "success_flag": 1.0 if transfer["success"] else 0.0,
                    "chunks_total": int(transfer["total_chunks"]),
                    "chunks_failed": int(transfer["chunks_failed"]),
                    "package_size_bytes": int(transfer["package_size_bytes"]),
                    "restored_file_path": transfer.get("restored_file_path"),
                    "received_snr_label": transfer.get("received_snr_label", ""),
                    "modulation": trial_cfg.get("modulation", {}).get("scheme", "QPSK"),
                    "channel_model": trial_cfg.get("channel", {}).get("model", "awgn"),
                    "channel_profile": trial_cfg.get("channel", {}).get("profile", "static_near"),
                    "perfect_sync": bool(trial_cfg.get("receiver", {}).get("perfect_sync", False)),
                    "perfect_channel_estimation": bool(
                        trial_cfg.get("receiver", {}).get("perfect_channel_estimation", False)
                    ),
                }
            )
            records.append(row)

    dataframe = pd.DataFrame(records)
    save_dataframe_csv(records, output_dir / "file_transfer_sweep.csv")
    _plot_grouped_metric(
        dataframe,
        y_column="success_flag",
        title="File transfer success vs SNR",
        output_path=output_dir / "file_transfer_success_vs_snr.png",
    )
    _plot_grouped_metric(
        dataframe,
        y_column="chunks_failed",
        title="File transfer chunks failed vs SNR",
        output_path=output_dir / "file_transfer_chunks_failed_vs_snr.png",
    )
    save_markdown_report(
        "File Transfer Sweep vs SNR",
        [
            (
                "Configuration",
                f"Files: {', '.join(path.name for path in source_files)}\n\n"
                f"Perfect sync: {bool(config.get('receiver', {}).get('perfect_sync', False))}\n\n"
                f"Perfect channel estimation: {bool(config.get('receiver', {}).get('perfect_channel_estimation', False))}",
            ),
            ("Summary", "```\n" + dataframe.to_string(index=False) + "\n```"),
        ],
        output_dir / "summary.md",
    )
    return dataframe
