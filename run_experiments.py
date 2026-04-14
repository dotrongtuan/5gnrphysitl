from __future__ import annotations

import argparse
from pathlib import Path

from experiments.ber_vs_snr import run_experiment as run_ber_vs_snr
from experiments.bler_vs_snr import run_experiment as run_bler_vs_snr
from experiments.control_vs_data import run_experiment as run_control_vs_data
from experiments.csi_loop_compare import run_experiment as run_csi_loop_compare
from experiments.doppler_sweep import run_experiment as run_doppler_sweep
from experiments.evm_vs_snr import run_experiment as run_evm_vs_snr
from experiments.fading_sweep import run_experiment as run_fading_sweep
from experiments.file_transfer_sweep import run_experiment as run_file_transfer_sweep
from experiments.impairment_sweep import run_experiment as run_impairment_sweep
from experiments.sample_file_transfer_sweep import run_experiment as run_sample_file_transfer_sweep
from utils.io import load_yaml
from utils.validators import deep_merge, validate_config


EXPERIMENTS = {
    "ber_vs_snr": run_ber_vs_snr,
    "bler_vs_snr": run_bler_vs_snr,
    "evm_vs_snr": run_evm_vs_snr,
    "control_vs_data": run_control_vs_data,
    "csi_loop_compare": run_csi_loop_compare,
    "fading_sweep": run_fading_sweep,
    "doppler_sweep": run_doppler_sweep,
    "impairment_sweep": run_impairment_sweep,
    "file_transfer_sweep": run_file_transfer_sweep,
    "sample_file_transfer_sweep": run_sample_file_transfer_sweep,
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run batch experiments for the 5G NR PHY STL platform.")
    parser.add_argument("--experiment", type=str, required=True, choices=sorted(EXPERIMENTS.keys()))
    parser.add_argument("--config", type=str, default="configs/default.yaml")
    parser.add_argument("--override", type=str, nargs="*", default=[])
    parser.add_argument("--output-dir", type=str, default="outputs")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent
    config = load_yaml(project_root / args.config)
    for override in args.override:
        config = deep_merge(config, load_yaml(project_root / override))
    config = validate_config(config)
    runner = EXPERIMENTS[args.experiment]
    runner(config=config, output_dir=project_root / args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
