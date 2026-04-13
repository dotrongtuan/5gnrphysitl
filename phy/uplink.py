from __future__ import annotations

import numpy as np


def apply_transform_precoding(symbols: np.ndarray) -> np.ndarray:
    view = np.asarray(symbols, dtype=np.complex128).reshape(-1)
    if view.size == 0:
        return np.array([], dtype=np.complex128)
    return np.fft.fft(view) / np.sqrt(view.size)


def remove_transform_precoding(symbols: np.ndarray) -> np.ndarray:
    view = np.asarray(symbols, dtype=np.complex128).reshape(-1)
    if view.size == 0:
        return np.array([], dtype=np.complex128)
    return np.fft.ifft(view) * np.sqrt(view.size)
