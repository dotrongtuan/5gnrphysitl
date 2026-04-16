from __future__ import annotations

import numpy as np


def comb_positions(
    num_subcarriers: int,
    *,
    symbols: list[int],
    comb: int = 4,
    offset: int = 0,
) -> np.ndarray:
    step = max(1, int(comb))
    start = int(offset) % step
    positions = []
    for symbol in symbols:
        for subcarrier in range(start, int(num_subcarriers), step):
            positions.append((int(symbol), int(subcarrier)))
    return np.asarray(positions, dtype=int) if positions else np.zeros((0, 2), dtype=int)


def qpsk_reference_sequence(
    length: int,
    *,
    slot: int,
    symbol: int,
    seed: int,
) -> np.ndarray:
    size = max(int(length), 0)
    if size == 0:
        return np.array([], dtype=np.complex128)
    rng = np.random.default_rng(int(seed) + 257 * int(slot) + 17 * int(symbol))
    bits = rng.integers(0, 2, size=(size, 2), dtype=np.uint8)
    i = 1.0 - 2.0 * bits[:, 0].astype(np.float64)
    q = 1.0 - 2.0 * bits[:, 1].astype(np.float64)
    return ((i + 1j * q) / np.sqrt(2.0)).astype(np.complex128)


def nr_cell_id_components(physical_cell_id: int) -> tuple[int, int]:
    cell_id = int(physical_cell_id) % 1008
    return cell_id // 3, cell_id % 3


def _m_sequence(length: int, *, taps: tuple[int, int], init: tuple[int, ...]) -> np.ndarray:
    state = [int(bit) & 1 for bit in init]
    size = max(int(length), len(state))
    sequence = np.zeros(size, dtype=np.uint8)
    sequence[: len(state)] = np.asarray(state, dtype=np.uint8)
    for index in range(size - len(state)):
        sequence[index + len(state)] = (sequence[index + taps[0]] + sequence[index + taps[1]]) % 2
    return sequence


def nr_pss_sequence(n_id_2: int) -> np.ndarray:
    """Generate the NR PSS sequence of length 127 for N_ID^(2) in {0,1,2}."""
    n_id_2 = int(n_id_2) % 3
    x = _m_sequence(127, taps=(0, 4), init=(0, 1, 1, 0, 1, 1, 1))
    sequence = 1.0 - 2.0 * x[(np.arange(127) + 43 * n_id_2) % 127].astype(np.float64)
    return sequence.astype(np.complex128)


def nr_sss_sequence(physical_cell_id: int) -> np.ndarray:
    """Generate the NR SSS sequence of length 127 for N_ID^cell in [0,1007]."""
    n_id_1, n_id_2 = nr_cell_id_components(physical_cell_id)
    x0 = _m_sequence(127, taps=(0, 4), init=(1, 0, 0, 0, 0, 0, 0))
    x1 = _m_sequence(127, taps=(0, 1), init=(1, 0, 0, 0, 0, 0, 0))
    m0 = 15 * (n_id_1 // 112) + 5 * n_id_2
    m1 = n_id_1 % 112
    sequence = (1.0 - 2.0 * x0[(np.arange(127) + m0) % 127].astype(np.float64)) * (
        1.0 - 2.0 * x1[(np.arange(127) + m1) % 127].astype(np.float64)
    )
    return sequence.astype(np.complex128)


def detect_nr_pss(received_symbols: np.ndarray) -> tuple[int, np.ndarray]:
    symbols = np.asarray(received_symbols, dtype=np.complex128).reshape(-1)
    metrics = np.zeros(3, dtype=np.float64)
    norm = np.linalg.norm(symbols) + 1e-12
    if symbols.size != 127:
        return 0, metrics
    for n_id_2 in range(3):
        candidate = nr_pss_sequence(n_id_2)
        metrics[n_id_2] = float(np.abs(np.vdot(candidate, symbols)) / ((np.linalg.norm(candidate) * norm) + 1e-12))
    return int(np.argmax(metrics)), metrics


def detect_nr_sss(received_symbols: np.ndarray, n_id_2: int) -> tuple[int, int, np.ndarray]:
    symbols = np.asarray(received_symbols, dtype=np.complex128).reshape(-1)
    metrics = np.zeros(336, dtype=np.float64)
    norm = np.linalg.norm(symbols) + 1e-12
    if symbols.size != 127:
        return 0, int(n_id_2) % 3, metrics
    n_id_2 = int(n_id_2) % 3
    for n_id_1 in range(336):
        cell_id = 3 * n_id_1 + n_id_2
        candidate = nr_sss_sequence(cell_id)
        metrics[n_id_1] = float(np.abs(np.vdot(candidate, symbols)) / ((np.linalg.norm(candidate) * norm) + 1e-12))
    detected_n_id_1 = int(np.argmax(metrics))
    return detected_n_id_1, n_id_2, metrics
