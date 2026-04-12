from __future__ import annotations

from copy import deepcopy
from typing import Dict

import numpy as np

from channel.awgn_channel import AWGNChannel
from channel.doppler import apply_doppler_rotation
from channel.fading_channel import FadingChannel
from channel.impairments import apply_impairments
from phy.receiver import NrReceiver
from phy.transmitter import NrTransmitter


def _reference_channel_grid(tx_metadata, frequency_response: np.ndarray) -> np.ndarray:
    grid = np.ones_like(tx_metadata.tx_grid)
    center = tx_metadata.numerology.fft_size // 2
    left = tx_metadata.numerology.active_subcarriers // 2
    right = tx_metadata.numerology.active_subcarriers - left
    active = np.concatenate(
        [
            frequency_response[center - left : center],
            frequency_response[center + 1 : center + 1 + right],
        ]
    )
    grid[:] = active[None, :]
    return grid


def simulate_link(config: Dict, channel_type: str | None = None) -> Dict:
    config = deepcopy(config)
    transmitter = NrTransmitter(config)
    tx_result = transmitter.transmit(channel_type=channel_type or config.get("link", {}).get("channel_type", "data"))

    simulation_seed = int(config.get("simulation", {}).get("seed", 0))
    rng = np.random.default_rng(simulation_seed + 99)

    waveform = tx_result.waveform.copy()
    impairment_config = deepcopy(config)
    if bool(config.get("simulation", {}).get("use_gnuradio", False)):
        impairment_config.setdefault("channel", {})["cfo_hz"] = 0.0
    waveform = apply_impairments(waveform, config=impairment_config, sample_rate=tx_result.metadata.sample_rate, rng=rng)

    fading_model = str(config.get("channel", {}).get("model", "awgn")).lower()
    use_gnuradio = bool(config.get("simulation", {}).get("use_gnuradio", False))
    fading_channel = FadingChannel(
        config=config,
        sample_rate=tx_result.metadata.sample_rate,
        fft_size=tx_result.metadata.numerology.fft_size,
        seed=simulation_seed + 7,
    )

    if fading_model in {"awgn", "none"}:
        fading_response = np.ones(tx_result.metadata.numerology.fft_size, dtype=np.complex128)
        impulse_response = np.array([1.0 + 0j], dtype=np.complex128)
    else:
        impulse_response = fading_channel.build_impulse_response()
        fading_response = fading_channel.frequency_response_from_impulse(impulse_response)

    awgn = AWGNChannel(
        snr_db=float(config.get("channel", {}).get("snr_db", 20.0)),
        seed=simulation_seed + 123,
    )

    gnuradio_requested = use_gnuradio
    gnuradio_error: str | None = None
    if use_gnuradio:
        try:
            from grc.end_to_end_flowgraph import EndToEndFlowgraph

            noise_variance = awgn.apply(waveform).noise_variance
            gr_flowgraph = EndToEndFlowgraph(
                waveform=waveform,
                sample_rate=tx_result.metadata.sample_rate,
                noise_variance=noise_variance,
                frequency_offset_hz=float(config.get("channel", {}).get("cfo_hz", 0.0)),
                taps=impulse_response,
            )
            rx_waveform = gr_flowgraph.run_and_collect()
            rx_waveform = apply_doppler_rotation(
                rx_waveform,
                doppler_hz=float(config.get("channel", {}).get("doppler_hz", 0.0)),
                sample_rate=tx_result.metadata.sample_rate,
            )
            awgn_result = type("AwgnProxy", (), {"noise_variance": noise_variance})()
        except Exception as exc:
            gnuradio_error = str(exc)
            use_gnuradio = False

    if not use_gnuradio:
        if fading_model not in {"awgn", "none"}:
            fading_result = fading_channel.apply(waveform)
            waveform = fading_result.waveform
            fading_response = fading_result.frequency_response
            impulse_response = fading_result.impulse_response
        awgn_result = awgn.apply(waveform)
        rx_waveform = awgn_result.waveform

    receiver = NrReceiver(config)
    channel_state = {
        "noise_variance": awgn_result.noise_variance,
        "cfo_hz": float(config.get("channel", {}).get("cfo_hz", 0.0)),
        "sto_samples": int(config.get("channel", {}).get("sto_samples", 0)),
        "reference_channel_grid": _reference_channel_grid(tx_result.metadata, fading_response),
        "impulse_response": impulse_response,
        "fading_model": fading_model,
        "gnu_radio_requested": gnuradio_requested,
        "gnu_radio_used": use_gnuradio,
        "gnu_radio_error": gnuradio_error,
    }
    rx_result = receiver.receive(rx_waveform, tx_result.metadata, channel_state=channel_state)
    return {
        "config": config,
        "tx": tx_result,
        "rx": rx_result,
        "kpis": rx_result.kpis,
        "channel_state": channel_state,
        "rx_waveform": rx_waveform,
    }
