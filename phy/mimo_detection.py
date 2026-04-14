from __future__ import annotations

import numpy as np


def zf_detect(y: np.ndarray, h: np.ndarray) -> np.ndarray:
    return np.linalg.pinv(h) @ y


def mmse_detect(y: np.ndarray, h: np.ndarray, noise_variance: float) -> np.ndarray:
    h_hermitian = np.conjugate(h.T)
    regularized = h_hermitian @ h + max(float(noise_variance), 1e-9) * np.eye(h.shape[1], dtype=np.complex128)
    return np.linalg.solve(regularized, h_hermitian @ y)


def osic_detect(y: np.ndarray, h: np.ndarray, noise_variance: float) -> np.ndarray:
    residual = np.asarray(y, dtype=np.complex128).copy()
    remaining = list(range(h.shape[1]))
    remaining_h = np.asarray(h, dtype=np.complex128).copy()
    estimate = np.zeros(h.shape[1], dtype=np.complex128)

    while remaining:
        norms = np.sum(np.abs(remaining_h) ** 2, axis=0)
        strongest_local = int(np.argmax(norms))
        strongest_global = remaining[strongest_local]
        local_estimate = mmse_detect(residual, remaining_h, noise_variance)
        symbol = local_estimate[strongest_local]
        estimate[strongest_global] = symbol
        residual = residual - remaining_h[:, strongest_local] * symbol
        remaining_h = np.delete(remaining_h, strongest_local, axis=1)
        remaining.pop(strongest_local)
    return estimate


def detect_layers(y: np.ndarray, h: np.ndarray, noise_variance: float, mode: str) -> np.ndarray:
    detector = str(mode).lower()
    if detector == "zf":
        return zf_detect(y, h)
    if detector == "osic":
        return osic_detect(y, h, noise_variance)
    return mmse_detect(y, h, noise_variance)
