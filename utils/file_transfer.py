from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import mimetypes
from pathlib import Path
import struct
from typing import Any

import numpy as np


PACKAGE_MAGIC = b"5GNRFILE"
PACKAGE_VERSION = 1


@dataclass(slots=True)
class FilePayloadPackage:
    source_path: Path
    filename: str
    media_kind: str
    mime_type: str
    payload_bytes: bytes
    payload_sha256: str
    header: dict[str, Any]
    header_bytes: bytes
    package_bytes: bytes
    package_bits: np.ndarray


@dataclass(slots=True)
class PayloadChunk:
    index: int
    total: int
    valid_bits: int
    bits: np.ndarray


@dataclass(slots=True)
class RestoredFileResult:
    destination_path: Path
    filename: str
    received_timestamp_label: str
    media_kind: str
    mime_type: str
    payload_bytes: bytes
    payload_sha256: str
    sha256_match: bool


def bytes_to_bits(payload: bytes) -> np.ndarray:
    byte_array = np.frombuffer(payload, dtype=np.uint8)
    if byte_array.size == 0:
        return np.array([], dtype=np.uint8)
    return np.unpackbits(byte_array).astype(np.uint8)


def bits_to_bytes(bits: np.ndarray, *, valid_bits: int | None = None) -> bytes:
    view = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if valid_bits is not None:
        view = view[:valid_bits]
    if view.size == 0:
        return b""
    packed = np.packbits(view)
    return packed.tobytes()


def classify_media_kind(path: str | Path, mime_type: str | None = None) -> str:
    mime = (mime_type or "").lower()
    suffix = Path(path).suffix.lower()
    if mime.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}:
        return "image"
    if mime.startswith("text/") or suffix in {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml"}:
        return "text"
    return "binary"


def build_file_payload_package(source_path: str | Path) -> FilePayloadPackage:
    source = Path(source_path).expanduser().resolve()
    payload_bytes = source.read_bytes()
    mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    media_kind = classify_media_kind(source, mime_type)
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    header = {
        "filename": source.name,
        "suffix": source.suffix,
        "media_kind": media_kind,
        "mime_type": mime_type,
        "payload_size_bytes": len(payload_bytes),
        "payload_sha256": payload_sha256,
    }
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    package_bytes = b"".join(
        [
            PACKAGE_MAGIC,
            struct.pack(">B", PACKAGE_VERSION),
            struct.pack(">I", len(header_bytes)),
            header_bytes,
            payload_bytes,
        ]
    )
    return FilePayloadPackage(
        source_path=source,
        filename=source.name,
        media_kind=media_kind,
        mime_type=mime_type,
        payload_bytes=payload_bytes,
        payload_sha256=payload_sha256,
        header=header,
        header_bytes=header_bytes,
        package_bytes=package_bytes,
        package_bits=bytes_to_bits(package_bytes),
    )


def parse_file_payload_package(package_bytes: bytes) -> tuple[dict[str, Any], bytes]:
    if len(package_bytes) < len(PACKAGE_MAGIC) + 5:
        raise ValueError("The received package is too short to contain a valid file header.")
    if package_bytes[: len(PACKAGE_MAGIC)] != PACKAGE_MAGIC:
        raise ValueError("The received package does not match the expected file-transfer magic header.")
    cursor = len(PACKAGE_MAGIC)
    version = package_bytes[cursor]
    cursor += 1
    if version != PACKAGE_VERSION:
        raise ValueError(f"Unsupported file-transfer package version: {version}.")
    header_length = struct.unpack(">I", package_bytes[cursor : cursor + 4])[0]
    cursor += 4
    header_bytes = package_bytes[cursor : cursor + header_length]
    cursor += header_length
    header = json.loads(header_bytes.decode("utf-8"))
    payload_bytes = package_bytes[cursor : cursor + int(header["payload_size_bytes"])]
    return header, payload_bytes


def chunk_bitstream(bitstream: np.ndarray, payload_bits_per_chunk: int) -> list[PayloadChunk]:
    if payload_bits_per_chunk <= 0:
        raise ValueError("payload_bits_per_chunk must be positive.")
    source = np.asarray(bitstream, dtype=np.uint8).reshape(-1)
    total = max(1, int(np.ceil(source.size / payload_bits_per_chunk)))
    chunks: list[PayloadChunk] = []
    for index in range(total):
        start = index * payload_bits_per_chunk
        stop = min(start + payload_bits_per_chunk, source.size)
        valid_bits = max(0, stop - start)
        chunk_bits = np.zeros(payload_bits_per_chunk, dtype=np.uint8)
        if valid_bits:
            chunk_bits[:valid_bits] = source[start:stop]
        chunks.append(PayloadChunk(index=index, total=total, valid_bits=valid_bits, bits=chunk_bits))
    return chunks


def join_valid_chunks(chunks: list[PayloadChunk], recovered_chunks: list[np.ndarray]) -> np.ndarray:
    if len(chunks) != len(recovered_chunks):
        raise ValueError("Chunk metadata and recovered chunks must have the same length.")
    valid_views: list[np.ndarray] = []
    for metadata, recovered in zip(chunks, recovered_chunks):
        recovered_bits = np.asarray(recovered, dtype=np.uint8).reshape(-1)
        valid_views.append(recovered_bits[: metadata.valid_bits])
    if not valid_views:
        return np.array([], dtype=np.uint8)
    return np.concatenate(valid_views).astype(np.uint8)


def file_preview_text(media_kind: str, payload_bytes: bytes, *, max_chars: int = 240) -> str:
    if media_kind == "text":
        return payload_bytes.decode("utf-8", errors="replace")[:max_chars]
    view = payload_bytes[: min(len(payload_bytes), 96)]
    hex_body = " ".join(f"{value:02x}" for value in view)
    suffix = " ..." if len(payload_bytes) > len(view) else ""
    return f"{hex_body}{suffix}"


def restore_file_from_package_bits(
    package_bits: np.ndarray,
    *,
    output_dir: str | Path,
    preserve_filename: bool = True,
) -> RestoredFileResult:
    package_bytes = bits_to_bytes(package_bits)
    header, payload_bytes = parse_file_payload_package(package_bytes)
    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    original_name = str(header.get("filename", "received_payload.bin"))
    timestamp_label = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    original_path = Path(original_name)
    if preserve_filename:
        destination = output_root / f"{original_path.stem}__rx_{timestamp_label}{original_path.suffix}"
    else:
        destination = output_root / f"{original_path.stem}__rx_{timestamp_label}{original_path.suffix}"

    collision_index = 1
    while destination.exists():
        destination = output_root / f"{original_path.stem}__rx_{timestamp_label}_{collision_index}{original_path.suffix}"
        collision_index += 1

    destination.write_bytes(payload_bytes)
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    return RestoredFileResult(
        destination_path=destination,
        filename=original_name,
        received_timestamp_label=timestamp_label,
        media_kind=str(header.get("media_kind", "binary")),
        mime_type=str(header.get("mime_type", "application/octet-stream")),
        payload_bytes=payload_bytes,
        payload_sha256=payload_sha256,
        sha256_match=payload_sha256 == str(header.get("payload_sha256", "")),
    )
