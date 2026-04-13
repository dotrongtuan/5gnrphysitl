from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from experiments.sample_file_transfer_sweep import run_experiment
from utils.io import load_yaml
from utils.validators import validate_config


def test_sample_file_transfer_sweep_runs_and_exports(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    config = validate_config(load_yaml(root / "configs" / "default.yaml"))
    config = deepcopy(config)
    config["payload_io"] = {"rx_output_dir": str(tmp_path / "rx")}
    config["experiments"]["file_transfer_snr_sweep_db"] = [0, 4]

    dataframe = run_experiment(config=config, output_dir=tmp_path / "outputs")

    assert len(dataframe) == 4
    assert set(dataframe["source_filename"]) == {"sample_message.txt", "sample_image.png"}
    assert set(["source_filename", "snr_db", "success_flag", "chunks_failed"]).issubset(dataframe.columns)

    output_root = tmp_path / "outputs" / "sample_inputs" / "file_transfer_sweep"
    assert (output_root / "file_transfer_sweep.csv").exists()
    assert (output_root / "file_transfer_success_vs_snr.png").exists()
    assert (output_root / "file_transfer_chunks_failed_vs_snr.png").exists()
    assert (output_root / "summary.md").exists()
