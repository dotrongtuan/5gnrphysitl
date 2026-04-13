from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path

import numpy as np

from experiments.common import simulate_file_transfer
from utils.file_transfer import bits_to_bytes, build_file_payload_package, chunk_bitstream, join_valid_chunks
from utils.io import load_yaml
from utils.validators import validate_config


def _base_config(tmp_path: Path) -> dict:
    root = Path(__file__).resolve().parents[1]
    config = load_yaml(root / "configs" / "default.yaml")
    config = validate_config(config)
    config = deepcopy(config)
    config["simulation"]["output_dir"] = str(tmp_path / "outputs")
    config["payload_io"] = {"rx_output_dir": str(tmp_path / "rx")}
    config["channel"]["model"] = "awgn"
    config["channel"]["snr_db"] = 40.0
    config["receiver"]["perfect_sync"] = True
    config["receiver"]["perfect_channel_estimation"] = True
    return config


def test_file_package_round_trip_chunk_join(tmp_path: Path) -> None:
    source = tmp_path / "payload.txt"
    source.write_text("5G NR PHY file transfer payload.\n" * 8, encoding="utf-8")
    package = build_file_payload_package(source)
    chunks = chunk_bitstream(package.package_bits, payload_bits_per_chunk=128)
    recovered_bits = join_valid_chunks(chunks, [chunk.bits for chunk in chunks])
    assert np.array_equal(recovered_bits, package.package_bits)
    assert bits_to_bytes(recovered_bits) == package.package_bytes


def test_simulate_text_file_transfer_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "message.txt"
    source.write_text("PHY pipeline file transfer demo.\n" * 40, encoding="utf-8")
    config = _base_config(tmp_path)
    result = simulate_file_transfer(config, source_path=str(source), output_dir=str(tmp_path / "rx"))
    transfer = result["file_transfer"]

    assert transfer["success"] is True
    assert transfer["chunks_failed"] == 0
    assert transfer["total_chunks"] > 1
    restored = Path(transfer["restored_file_path"])
    assert restored.exists()
    assert transfer["received_snr_label"] == "snr_40dB"
    assert transfer["received_snr_label"] in restored.name
    assert "__rx_" in restored.name
    assert transfer["received_timestamp_label"] in restored.name
    assert restored.read_bytes() == source.read_bytes()


def test_simulate_image_file_transfer_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "pixel.png"
    source.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sX6pGkAAAAASUVORK5CYII="
        )
    )
    config = _base_config(tmp_path)
    result = simulate_file_transfer(config, source_path=str(source), output_dir=str(tmp_path / "rx"))
    transfer = result["file_transfer"]

    assert transfer["success"] is True
    assert transfer["media_kind"] == "image"
    restored = Path(transfer["restored_file_path"])
    assert restored.exists()
    assert transfer["received_snr_label"] == "snr_40dB"
    assert transfer["received_snr_label"] in restored.name
    assert "__rx_" in restored.name
    assert transfer["received_timestamp_label"] in restored.name
    assert restored.read_bytes() == source.read_bytes()
