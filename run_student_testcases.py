from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Callable, Dict, List

import pandas as pd

from experiments.common import simulate_link
from utils.io import load_yaml, save_dataframe_csv, save_markdown_report
from utils.validators import deep_merge, validate_config


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run curated teaching-oriented 5G NR PHY testcases.")
    parser.add_argument("--config", type=str, default="configs/default.yaml")
    parser.add_argument("--override", type=str, nargs="*", default=[])
    parser.add_argument("--output-dir", type=str, default="outputs/student_testcases")
    return parser


def load_config(base_path: str, overrides: List[str]) -> dict:
    project_root = Path(__file__).resolve().parent
    config = load_yaml(project_root / base_path)
    for override in overrides:
        config = deep_merge(config, load_yaml(project_root / override))
    return validate_config(config)


def summarize_result(case_id: str, lesson: str, variant: str, result: Dict, extra: Dict | None = None) -> Dict:
    row = {
        "case_id": case_id,
        "lesson": lesson,
        "variant": variant,
    }
    row.update(result["kpis"].as_dict())
    if extra:
        row.update(extra)
    return row


def run_cases(base_config: dict) -> pd.DataFrame:
    rows: List[Dict] = []

    # Case 1: Clean baseline
    baseline = simulate_link(deepcopy(base_config), channel_type="data")
    rows.append(
        summarize_result(
            "TC1",
            "Baseline AWGN link should decode successfully with very low EVM.",
            "default_awgn_qpsk",
            baseline,
            {"snr_db": base_config["channel"]["snr_db"], "modulation": base_config["modulation"]["scheme"]},
        )
    )

    # Case 2: High-order modulation sweep
    for snr_db in [0, 5, 10, 15, 20]:
        config = deepcopy(base_config)
        config["modulation"]["scheme"] = "256QAM"
        config["coding"]["target_rate"] = 0.8
        config["channel"]["snr_db"] = snr_db
        result = simulate_link(config, channel_type="data")
        rows.append(
            summarize_result(
                "TC2",
                "Higher-order modulation needs more SNR before BLER drops to zero.",
                f"256QAM_rate0.8_snr{snr_db}",
                result,
                {"snr_db": snr_db, "modulation": "256QAM", "target_rate": 0.8},
            )
        )

    # Case 3: Channel profile comparison
    profile_variants = [
        ("static_near", "awgn", "rayleigh"),
        ("pedestrian", "rayleigh", "rayleigh"),
        ("vehicular", "rayleigh", "rayleigh"),
        ("urban_los", "rician", "rician"),
    ]
    for profile, model, fading_type in profile_variants:
        config = deepcopy(base_config)
        config["channel"]["model"] = model
        config["channel"]["profile"] = profile
        config["channel"]["fading_type"] = fading_type
        config["channel"]["snr_db"] = 20
        if profile != "static_near":
            config["receiver"]["perfect_channel_estimation"] = False
        result = simulate_link(config, channel_type="data")
        rows.append(
            summarize_result(
                "TC3",
                "Different channel profiles change effective SNR and EVM even at the same nominal SNR.",
                profile,
                result,
                {"profile": profile, "snr_db": 20, "channel_model": model},
            )
        )

    # Case 4: Vehicular stress scenario
    vehicular = deepcopy(base_config)
    vehicular["modulation"]["scheme"] = "16QAM"
    vehicular["coding"]["target_rate"] = 0.55
    vehicular["channel"].update(
        {
            "model": "rayleigh",
            "profile": "vehicular",
            "fading_type": "rayleigh",
            "snr_db": 14,
            "doppler_hz": 140,
            "delay_spread_s": 1.76e-6,
            "cfo_hz": 45,
            "sto_samples": 6,
        }
    )
    vehicular_result = simulate_link(vehicular, channel_type="data")
    rows.append(
        summarize_result(
            "TC4",
            "A harsher vehicular profile can collapse throughput even when the baseline link works.",
            "vehicular_stress",
            vehicular_result,
            {
                "profile": "vehicular",
                "snr_db": 14,
                "doppler_hz": 140,
                "cfo_hz": 45,
                "sto_samples": 6,
            },
        )
    )

    # Case 5: Control-vs-data limitation study
    for channel_type in ["control", "data"]:
        config = deepcopy(base_config)
        config["channel"]["snr_db"] = -4
        result = simulate_link(config, channel_type=channel_type)
        rows.append(
            summarize_result(
                "TC5",
                "Control/data comparison in this prototype is a model-limitation study, not a standards-accurate benchmark.",
                f"{channel_type}_snr-4",
                result,
                {"channel_type": channel_type, "snr_db": -4},
            )
        )

    return pd.DataFrame(rows)


def build_markdown_sections(dataframe: pd.DataFrame) -> List[tuple[str, str]]:
    sections = []
    for case_id, case_rows in dataframe.groupby("case_id", sort=False):
        lesson = case_rows["lesson"].iloc[0]
        table = "```\n" + case_rows.drop(columns=["lesson"]).to_string(index=False) + "\n```"
        sections.append((f"{case_id} - {lesson}", table))
    return sections


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent
    config = load_config(args.config, args.override)
    dataframe = run_cases(config)

    output_dir = project_root / args.output_dir
    save_dataframe_csv(dataframe.to_dict(orient="records"), output_dir / "student_testcases.csv")
    save_markdown_report(
        "Student Testcases",
        build_markdown_sections(dataframe),
        output_dir / "student_testcases.md",
    )
    print(dataframe.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
