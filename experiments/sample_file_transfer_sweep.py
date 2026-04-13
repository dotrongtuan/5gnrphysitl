from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

from experiments.file_transfer_sweep import run_experiment as run_file_transfer_sweep


def run_experiment(config: dict, output_dir: str | Path) -> pd.DataFrame:
    project_root = Path(__file__).resolve().parent.parent
    trial_config = deepcopy(config)
    trial_config.setdefault("payload_io", {})
    trial_config["payload_io"]["sweep_files"] = [
        "input/sample_message.txt",
        "input/sample_image.png",
    ]
    trial_config["payload_io"].setdefault("rx_output_dir", str(project_root / "outputs" / "rx_files"))
    return run_file_transfer_sweep(trial_config, output_dir=Path(output_dir) / "sample_inputs")
