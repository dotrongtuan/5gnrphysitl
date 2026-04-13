from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from experiments.file_transfer_sweep import run_experiment
from utils.io import load_yaml
from utils.validators import validate_config


def test_file_transfer_sweep_runs_and_exports(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "message.txt"
    source.write_text("PHY pipeline file transfer demo.\n" * 40, encoding="utf-8")

    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["payload_io"] = {"tx_file_path": str(source), "rx_output_dir": str(tmp_path / "rx")}
    config["experiments"]["file_transfer_snr_sweep_db"] = [0, 4]

    dataframe = run_experiment(config=config, output_dir=tmp_path / "outputs")

    assert len(dataframe) == 2
    assert set(["source_filename", "snr_db", "success_flag", "chunks_failed", "perfect_sync", "perfect_channel_estimation"]).issubset(
        dataframe.columns
    )
    assert dataframe["source_filename"].nunique() == 1
    assert float(dataframe.loc[dataframe["snr_db"] == 0, "success_flag"].iloc[0]) == 0.0
    assert float(dataframe.loc[dataframe["snr_db"] == 4, "success_flag"].iloc[0]) == 1.0

    output_root = tmp_path / "outputs" / "file_transfer_sweep"
    assert (output_root / "file_transfer_sweep.csv").exists()
    assert (output_root / "file_transfer_success_vs_snr.png").exists()
    assert (output_root / "file_transfer_chunks_failed_vs_snr.png").exists()
    assert (output_root / "summary.md").exists()
