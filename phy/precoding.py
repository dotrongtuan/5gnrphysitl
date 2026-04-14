from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .types import SpatialLayout


@dataclass(slots=True, frozen=True)
class PrecoderSpec:
    mode: str
    matrix: np.ndarray


def build_type1_single_panel_codebook(num_ports: int, num_layers: int) -> dict[str, np.ndarray]:
    port_count = int(num_ports)
    layer_count = int(num_layers)
    if port_count < 1 or layer_count < 1:
        raise ValueError("num_ports and num_layers must be at least 1 for Type-I codebooks.")

    dft = build_precoder_matrix("dft", num_ports=port_count, num_layers=port_count)
    entries: dict[str, np.ndarray] = {}

    if port_count == 2 and layer_count == 1:
        entries["type1sp-r1-p0"] = (np.array([[1.0], [1.0]], dtype=np.complex128) / np.sqrt(2.0))
        entries["type1sp-r1-p1"] = (np.array([[1.0], [-1.0]], dtype=np.complex128) / np.sqrt(2.0))
        return entries

    if port_count == 2 and layer_count == 2:
        entries["type1sp-r2-p0"] = np.eye(2, dtype=np.complex128)
        entries["type1sp-r2-p1"] = dft[:, :2]
        return entries

    if port_count == 4:
        for shift in range(port_count):
            indices = [(shift + layer_index) % port_count for layer_index in range(layer_count)]
            entries[f"type1sp-r{layer_count}-p{shift}"] = dft[:, indices]
        return entries

    entries[f"type1sp-r{layer_count}-p0"] = build_precoder_matrix("dft", num_ports=port_count, num_layers=layer_count)
    return entries


def build_precoder_matrix(mode: str, num_ports: int, num_layers: int) -> np.ndarray:
    resolved_mode = str(mode).lower()
    port_count = int(num_ports)
    layer_count = int(num_layers)

    if resolved_mode == "identity":
        matrix = np.zeros((port_count, layer_count), dtype=np.complex128)
        diagonal = min(port_count, layer_count)
        matrix[np.arange(diagonal), np.arange(diagonal)] = 1.0 + 0.0j
        return matrix

    if resolved_mode == "dft":
        row_index = np.arange(port_count, dtype=np.float64)[:, None]
        col_index = np.arange(layer_count, dtype=np.float64)[None, :]
        matrix = np.exp(-1j * 2.0 * np.pi * row_index * col_index / max(port_count, 1))
        matrix /= np.sqrt(max(layer_count, 1))
        return matrix.astype(np.complex128)

    if resolved_mode == "type1_sp":
        codebook = build_type1_single_panel_codebook(port_count, layer_count)
        return next(iter(codebook.values())).copy()

    raise ValueError(f"Unsupported precoding.mode: {resolved_mode}")


def build_precoder(config: Mapping[str, Any] | None, spatial_layout: SpatialLayout) -> PrecoderSpec:
    precoding_cfg = dict(config.get("precoding", {})) if config else {}
    mode = str(precoding_cfg.get("mode", "identity")).lower()
    num_layers = int(spatial_layout.num_layers)
    num_ports = int(spatial_layout.num_ports)
    if mode == "type1_sp":
        codebook = build_type1_single_panel_codebook(num_ports=num_ports, num_layers=num_layers)
        pmi = str(precoding_cfg.get("pmi", next(iter(codebook.keys()))))
        if pmi not in codebook:
            raise ValueError(f"Unsupported precoding.pmi for type1_sp: {pmi}")
        return PrecoderSpec(mode=f"type1_sp:{pmi}", matrix=codebook[pmi].copy())
    return PrecoderSpec(mode=mode, matrix=build_precoder_matrix(mode, num_ports=num_ports, num_layers=num_layers))


def apply_precoder(layer_symbols: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    layer_view = np.asarray(layer_symbols, dtype=np.complex128)
    precoder = np.asarray(matrix, dtype=np.complex128)
    if layer_view.ndim != 2:
        raise ValueError("layer_symbols must have shape (layer, symbol_index).")
    if precoder.ndim != 2:
        raise ValueError("precoder matrix must be 2-D.")
    if layer_view.shape[0] != precoder.shape[1]:
        raise ValueError("layer_symbols and precoder matrix have incompatible layer dimensions.")
    return precoder @ layer_view


def recover_layers_from_ports(port_symbols: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    port_view = np.asarray(port_symbols, dtype=np.complex128)
    precoder = np.asarray(matrix, dtype=np.complex128)
    if port_view.ndim != 2:
        raise ValueError("port_symbols must have shape (port, symbol_index).")
    if precoder.ndim != 2:
        raise ValueError("precoder matrix must be 2-D.")
    if port_view.shape[0] != precoder.shape[0]:
        raise ValueError("port_symbols and precoder matrix have incompatible port dimensions.")
    recovery = np.linalg.pinv(precoder)
    return recovery @ port_view
