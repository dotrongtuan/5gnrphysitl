from __future__ import annotations

from typing import Dict

import numpy as np
import pyqtgraph as pg
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtWidgets import QSizePolicy, QTabWidget, QVBoxLayout, QWidget


pg.setConfigOptions(antialias=True, imageAxisOrder="row-major")


class PlotPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self._waterfall_history = np.zeros((128, 512), dtype=np.float32)

        self._build_signal_tab()
        self._build_grid_tab()
        self._build_channel_tab()
        self._build_batch_tab()

    @staticmethod
    def _style_plot(plot_item: pg.PlotItem) -> None:
        plot_item.showGrid(x=True, y=True, alpha=0.25)
        plot_item.getAxis("left").setTextPen("#94a3b8")
        plot_item.getAxis("bottom").setTextPen("#94a3b8")
        plot_item.getAxis("left").setPen(pg.mkPen("#475569"))
        plot_item.getAxis("bottom").setPen(pg.mkPen("#475569"))
        plot_item.titleLabel.item.setDefaultTextColor(pg.mkColor("#d8dee9"))

    def _build_signal_tab(self) -> None:
        self.signal_graphics = pg.GraphicsLayoutWidget()
        self.tabs.addTab(self.signal_graphics, "Signal Domain")

        self.constellation_plot = self.signal_graphics.addPlot(row=0, col=0, title="Constellation: reference / pre-EQ / post-EQ")
        self._style_plot(self.constellation_plot)
        self.constellation_plot.setLabel("bottom", "In-Phase")
        self.constellation_plot.setLabel("left", "Quadrature")
        self.constellation_plot.setAspectLocked(True)
        self.constellation_plot.addLegend(offset=(10, 10))
        self.reference_scatter = self.constellation_plot.plot(
            pen=None,
            symbol="x",
            symbolPen=pg.mkPen("#f94144", width=1.2),
            symbolSize=7,
            name="Reference",
        )
        self.pre_eq_scatter = self.constellation_plot.plot(
            pen=None,
            symbol="o",
            symbolBrush=pg.mkBrush(255, 255, 255, 50),
            symbolPen=pg.mkPen(255, 255, 255, 80),
            symbolSize=4,
            name="Pre-EQ",
        )
        self.post_eq_scatter = self.constellation_plot.plot(
            pen=None,
            symbol="o",
            symbolBrush=pg.mkBrush("#38bdf8"),
            symbolPen=pg.mkPen("#0ea5e9", width=0.8),
            symbolSize=5,
            name="Post-EQ",
        )

        self.waveform_plot = self.signal_graphics.addPlot(row=0, col=1, title="TX/RX waveform (time domain)")
        self._style_plot(self.waveform_plot)
        self.waveform_plot.setLabel("bottom", "Sample")
        self.waveform_plot.setLabel("left", "Amplitude")
        self.waveform_plot.addLegend(offset=(10, 10))
        self.tx_waveform_i_curve = self.waveform_plot.plot(
            pen=pg.mkPen("#cbd5e1", width=1.0, style=Qt.DashLine),
            name="TX I",
        )
        self.tx_waveform_q_curve = self.waveform_plot.plot(
            pen=pg.mkPen("#fcd34d", width=1.0, style=Qt.DashLine),
            name="TX Q",
        )
        self.rx_waveform_i_curve = self.waveform_plot.plot(pen=pg.mkPen("#60a5fa", width=1.3), name="RX I")
        self.rx_waveform_q_curve = self.waveform_plot.plot(pen=pg.mkPen("#f59e0b", width=1.3), name="RX Q")

        self.spectrum_plot = self.signal_graphics.addPlot(row=1, col=0, title="TX/RX spectrum")
        self._style_plot(self.spectrum_plot)
        self.spectrum_plot.setLabel("bottom", "Frequency (MHz)")
        self.spectrum_plot.setLabel("left", "Magnitude (dB)")
        self.spectrum_plot.addLegend(offset=(10, 10))
        self.tx_spectrum_curve = self.spectrum_plot.plot(
            pen=pg.mkPen("#a7f3d0", width=1.0, style=Qt.DashLine),
            name="TX",
        )
        self.rx_spectrum_curve = self.spectrum_plot.plot(pen=pg.mkPen("#34d399", width=1.4), name="RX")

        self.waterfall_plot = self.signal_graphics.addPlot(row=1, col=1, title="RX spectrum waterfall")
        self._style_plot(self.waterfall_plot)
        self.waterfall_plot.setLabel("bottom", "FFT bin")
        self.waterfall_plot.setLabel("left", "Frame history")
        self.waterfall_image = pg.ImageItem(axisOrder="row-major")
        self.waterfall_plot.addItem(self.waterfall_image)
        self.waterfall_image.setLookupTable(pg.colormap.get("inferno").getLookupTable())

    def _build_grid_tab(self) -> None:
        self.grid_graphics = pg.GraphicsLayoutWidget()
        self.tabs.addTab(self.grid_graphics, "Resource Grid")

        self.tx_allocation_plot = self.grid_graphics.addPlot(row=0, col=0, title="TX allocation map")
        self._style_plot(self.tx_allocation_plot)
        self.tx_allocation_plot.setLabel("bottom", "Subcarrier")
        self.tx_allocation_plot.setLabel("left", "OFDM symbol")
        self.tx_allocation_image = pg.ImageItem(axisOrder="row-major")
        self.tx_allocation_plot.addItem(self.tx_allocation_image)
        allocation_lut = np.array(
            [
                [15, 23, 42, 255],
                [56, 189, 248, 255],
                [251, 191, 36, 255],
            ],
            dtype=np.ubyte,
        )
        self.tx_allocation_image.setLookupTable(allocation_lut)
        self.tx_allocation_image.setLevels((0, 2))

        self.tx_grid_plot = self.grid_graphics.addPlot(row=0, col=1, title="TX grid magnitude")
        self._style_plot(self.tx_grid_plot)
        self.tx_grid_plot.setLabel("bottom", "Subcarrier")
        self.tx_grid_plot.setLabel("left", "OFDM symbol")
        self.tx_grid_image = pg.ImageItem(axisOrder="row-major")
        self.tx_grid_plot.addItem(self.tx_grid_image)
        self.tx_grid_image.setLookupTable(pg.colormap.get("viridis").getLookupTable())

        self.rx_grid_plot = self.grid_graphics.addPlot(row=1, col=0, title="RX grid magnitude")
        self._style_plot(self.rx_grid_plot)
        self.rx_grid_plot.setLabel("bottom", "Subcarrier")
        self.rx_grid_plot.setLabel("left", "OFDM symbol")
        self.rx_grid_image = pg.ImageItem(axisOrder="row-major")
        self.rx_grid_plot.addItem(self.rx_grid_image)
        self.rx_grid_image.setLookupTable(pg.colormap.get("magma").getLookupTable())

        self.channel_plot = self.grid_graphics.addPlot(row=1, col=1, title="Estimated channel magnitude")
        self._style_plot(self.channel_plot)
        self.channel_plot.setLabel("bottom", "Subcarrier")
        self.channel_plot.setLabel("left", "OFDM symbol")
        self.channel_image = pg.ImageItem(axisOrder="row-major")
        self.channel_plot.addItem(self.channel_image)
        self.channel_image.setLookupTable(pg.colormap.get("cividis").getLookupTable())

    def _build_channel_tab(self) -> None:
        self.channel_graphics = pg.GraphicsLayoutWidget()
        self.tabs.addTab(self.channel_graphics, "Channel / Sync / EQ")

        self.impulse_plot = self.channel_graphics.addPlot(row=0, col=0, title="Channel impulse response")
        self._style_plot(self.impulse_plot)
        self.impulse_plot.setLabel("bottom", "Tap")
        self.impulse_plot.setLabel("left", "Magnitude")
        self.impulse_curve = self.impulse_plot.plot(
            pen=pg.mkPen("#a78bfa", width=1.2),
            symbol="o",
            symbolBrush=pg.mkBrush("#c4b5fd"),
            symbolPen=pg.mkPen("#8b5cf6", width=0.8),
            symbolSize=6,
        )

        self.freq_response_plot = self.channel_graphics.addPlot(row=0, col=1, title="Average channel frequency response")
        self._style_plot(self.freq_response_plot)
        self.freq_response_plot.setLabel("bottom", "Subcarrier")
        self.freq_response_plot.setLabel("left", "Magnitude (dB)")
        self.freq_response_curve = self.freq_response_plot.plot(pen=pg.mkPen("#22c55e", width=1.5))

        self.equalizer_plot = self.channel_graphics.addPlot(row=1, col=0, title="Approx. equalizer gain magnitude")
        self._style_plot(self.equalizer_plot)
        self.equalizer_plot.setLabel("bottom", "Subcarrier")
        self.equalizer_plot.setLabel("left", "Gain (dB)")
        self.equalizer_curve = self.equalizer_plot.plot(pen=pg.mkPen("#f97316", width=1.5))

        self.sync_plot = self.channel_graphics.addPlot(row=1, col=1, title="Sync / EVM summary")
        self._style_plot(self.sync_plot)
        self.sync_plot.setLabel("bottom", "Metric")
        self.sync_plot.setLabel("left", "Value")
        self.sync_bar_item: pg.BarGraphItem | None = None
        self.sync_ticks = [(0, "cfg STO"), (1, "err STO"), (2, "cfg CFO"), (3, "est CFO"), (4, "EVM")]

        self.evm_symbol_plot = self.channel_graphics.addPlot(row=2, col=0, title="EVM by OFDM symbol")
        self._style_plot(self.evm_symbol_plot)
        self.evm_symbol_plot.setLabel("bottom", "OFDM symbol")
        self.evm_symbol_plot.setLabel("left", "EVM (RMS)")
        self.evm_symbol_curve = self.evm_symbol_plot.plot(
            pen=pg.mkPen("#f43f5e", width=1.4),
            symbol="o",
            symbolSize=5,
            symbolBrush=pg.mkBrush("#fb7185"),
        )

        self.evm_subcarrier_plot = self.channel_graphics.addPlot(row=2, col=1, title="Relative error by subcarrier")
        self._style_plot(self.evm_subcarrier_plot)
        self.evm_subcarrier_plot.setLabel("bottom", "Subcarrier")
        self.evm_subcarrier_plot.setLabel("left", "Relative error")
        self.evm_subcarrier_curve = self.evm_subcarrier_plot.plot(pen=pg.mkPen("#e11d48", width=1.4))

    def _build_batch_tab(self) -> None:
        self.batch_widget = QWidget()
        self.batch_figure = Figure(figsize=(10, 7), tight_layout=True)
        self.batch_canvas = FigureCanvasQTAgg(self.batch_figure)
        self.batch_axes = self.batch_figure.subplots(2, 2)
        layout = QVBoxLayout(self.batch_widget)
        layout.addWidget(self.batch_canvas)
        self.tabs.addTab(self.batch_widget, "Batch Analytics")
        self._render_batch_placeholder()

    def _render_batch_placeholder(self) -> None:
        for axis in self.batch_axes.ravel():
            axis.clear()
            axis.axis("off")
        self.batch_axes[0, 0].text(
            0.5,
            0.5,
            "Run a batch experiment or open the Dash dashboard\nto inspect parameter sweeps.",
            ha="center",
            va="center",
            fontsize=11,
        )
        self.batch_canvas.draw_idle()

    @staticmethod
    def _set_image(plot_item: pg.PlotItem, image_item: pg.ImageItem, data: np.ndarray, levels: tuple[float, float] | None = None) -> None:
        height, width = data.shape
        image_item.setImage(data, autoLevels=levels is None)
        if levels is not None:
            image_item.setLevels(levels)
        image_item.setRect(QRectF(0.0, 0.0, float(width), float(height)))
        plot_item.setXRange(0.0, float(width), padding=0.0)
        plot_item.setYRange(0.0, float(height), padding=0.0)

    @staticmethod
    def _resource_allocation_map(result: Dict) -> np.ndarray:
        tx = result["tx"]
        numerology = tx.metadata.numerology
        allocation_map = np.zeros(
            (numerology.symbols_per_slot, numerology.active_subcarriers),
            dtype=np.float32,
        )
        mapping_positions = tx.metadata.mapping.positions
        if mapping_positions.size:
            allocation_map[mapping_positions[:, 0], mapping_positions[:, 1]] = 1.0
        dmrs_positions = tx.metadata.dmrs["positions"]
        if dmrs_positions.size:
            allocation_map[dmrs_positions[:, 0], dmrs_positions[:, 1]] = 2.0
        return allocation_map

    @staticmethod
    def _reference_symbols(result: Dict) -> np.ndarray:
        tx = result["tx"]
        positions = tx.metadata.mapping.positions
        return tx.metadata.tx_grid[positions[:, 0], positions[:, 1]]

    @staticmethod
    def _pre_equalized_symbols(result: Dict) -> np.ndarray:
        tx = result["tx"]
        rx = result["rx"]
        positions = tx.metadata.mapping.positions
        return rx.rx_grid[positions[:, 0], positions[:, 1]]

    @staticmethod
    def _per_symbol_evm(result: Dict) -> tuple[np.ndarray, np.ndarray]:
        tx = result["tx"]
        rx = result["rx"]
        positions = tx.metadata.mapping.positions
        reference = tx.metadata.tx_grid[positions[:, 0], positions[:, 1]]
        equalized = rx.equalized_symbols
        values = []
        symbols = []
        for symbol in np.unique(positions[:, 0]):
            mask = positions[:, 0] == symbol
            ref = reference[mask]
            eq = equalized[mask]
            denom = np.mean(np.abs(ref) ** 2)
            evm = 0.0 if denom <= 0 else float(np.sqrt(np.mean(np.abs(eq - ref) ** 2) / denom))
            symbols.append(symbol)
            values.append(evm)
        return np.asarray(symbols, dtype=float), np.asarray(values, dtype=float)

    @staticmethod
    def _per_subcarrier_relative_error(result: Dict) -> tuple[np.ndarray, np.ndarray]:
        tx = result["tx"]
        rx = result["rx"]
        positions = tx.metadata.mapping.positions
        reference = tx.metadata.tx_grid[positions[:, 0], positions[:, 1]]
        equalized = rx.equalized_symbols
        values = []
        subcarriers = []
        for subcarrier in np.unique(positions[:, 1]):
            mask = positions[:, 1] == subcarrier
            ref = reference[mask]
            eq = equalized[mask]
            denom = np.mean(np.abs(ref) ** 2)
            error = 0.0 if denom <= 0 else float(np.sqrt(np.mean(np.abs(eq - ref) ** 2) / denom))
            subcarriers.append(subcarrier)
            values.append(error)
        return np.asarray(subcarriers, dtype=float), np.asarray(values, dtype=float)

    def _update_waterfall(self, spectrum_db: np.ndarray) -> None:
        row = spectrum_db.astype(np.float32)
        if row.size != self._waterfall_history.shape[1]:
            row = np.interp(
                np.linspace(0.0, row.size - 1, self._waterfall_history.shape[1]),
                np.arange(row.size),
                row,
            ).astype(np.float32)
        self._waterfall_history[:-1] = self._waterfall_history[1:]
        self._waterfall_history[-1] = row
        levels = (float(np.min(self._waterfall_history)), float(np.max(self._waterfall_history)))
        self._set_image(self.waterfall_plot, self.waterfall_image, self._waterfall_history, levels=levels)

    def update_from_result(self, result: Dict) -> None:
        tx = result["tx"]
        rx = result["rx"]
        tx_waveform = tx.waveform
        rx_waveform = result["rx_waveform"]
        channel_state = result["channel_state"]
        reference_symbols = self._reference_symbols(result)
        pre_equalized_symbols = self._pre_equalized_symbols(result)

        self.reference_scatter.setData(reference_symbols.real, reference_symbols.imag)
        self.pre_eq_scatter.setData(pre_equalized_symbols.real, pre_equalized_symbols.imag)
        self.post_eq_scatter.setData(rx.equalized_symbols.real, rx.equalized_symbols.imag)
        max_symbol = max(
            float(np.max(np.abs(reference_symbols))) if reference_symbols.size else 1.0,
            float(np.max(np.abs(pre_equalized_symbols))) if pre_equalized_symbols.size else 1.0,
            float(np.max(np.abs(rx.equalized_symbols))) if rx.equalized_symbols.size else 1.0,
            1.0,
        )
        self.constellation_plot.setXRange(-1.2 * max_symbol, 1.2 * max_symbol, padding=0.0)
        self.constellation_plot.setYRange(-1.2 * max_symbol, 1.2 * max_symbol, padding=0.0)

        tx_waveform_view = tx_waveform[:2048]
        rx_waveform_view = rx_waveform[:2048]
        tx_samples = np.arange(tx_waveform_view.size)
        rx_samples = np.arange(rx_waveform_view.size)
        self.tx_waveform_i_curve.setData(tx_samples, tx_waveform_view.real)
        self.tx_waveform_q_curve.setData(tx_samples, tx_waveform_view.imag)
        self.rx_waveform_i_curve.setData(rx_samples, rx_waveform_view.real)
        self.rx_waveform_q_curve.setData(rx_samples, rx_waveform_view.imag)

        tx_spectrum_view = tx_waveform[:4096]
        rx_spectrum_view = rx_waveform[:4096]
        tx_spectrum = (
            np.zeros(4096, dtype=np.complex128)
            if tx_spectrum_view.size == 0
            else np.fft.fftshift(np.fft.fft(tx_spectrum_view, n=4096))
        )
        rx_spectrum = (
            np.zeros(4096, dtype=np.complex128)
            if rx_spectrum_view.size == 0
            else np.fft.fftshift(np.fft.fft(rx_spectrum_view, n=4096))
        )
        freqs = np.linspace(-tx.metadata.sample_rate / 2, tx.metadata.sample_rate / 2, rx_spectrum.size)
        tx_spectrum_db = 20.0 * np.log10(np.abs(tx_spectrum) + 1e-9)
        rx_spectrum_db = 20.0 * np.log10(np.abs(rx_spectrum) + 1e-9)
        self.tx_spectrum_curve.setData(freqs / 1e6, tx_spectrum_db)
        self.rx_spectrum_curve.setData(freqs / 1e6, rx_spectrum_db)
        self._update_waterfall(rx_spectrum_db)

        resource_map = self._resource_allocation_map(result)
        self._set_image(self.tx_allocation_plot, self.tx_allocation_image, resource_map, levels=(0.0, 2.0))

        tx_magnitude = np.abs(tx.metadata.tx_grid).astype(np.float32)
        rx_magnitude = np.abs(rx.rx_grid).astype(np.float32)
        channel_magnitude = np.abs(rx.channel_estimate).astype(np.float32)
        self._set_image(self.tx_grid_plot, self.tx_grid_image, tx_magnitude, levels=(0.0, max(float(np.max(tx_magnitude)), 1e-6)))
        self._set_image(self.rx_grid_plot, self.rx_grid_image, rx_magnitude, levels=(0.0, max(float(np.max(rx_magnitude)), 1e-6)))
        self._set_image(self.channel_plot, self.channel_image, channel_magnitude, levels=(0.0, max(float(np.max(channel_magnitude)), 1e-6)))

        impulse = np.asarray(channel_state.get("impulse_response", np.array([1.0 + 0j])), dtype=np.complex128)
        taps = np.arange(impulse.size)
        self.impulse_curve.setData(taps, np.abs(impulse))

        avg_channel = np.mean(channel_magnitude, axis=0)
        self.freq_response_curve.setData(np.arange(avg_channel.size), 20.0 * np.log10(avg_channel + 1e-9))

        eq_gain = 1.0 / np.maximum(avg_channel, 1e-6)
        self.equalizer_curve.setData(np.arange(eq_gain.size), 20.0 * np.log10(eq_gain))

        cfg_sto = float(channel_state.get("sto_samples", 0))
        err_sto = float(rx.kpis.synchronization_error_samples or 0.0)
        cfg_cfo = float(channel_state.get("cfo_hz", 0.0))
        est_cfo = float(rx.cfo_estimate_hz)
        _, evm_by_symbol = self._per_symbol_evm(result)
        evm_mean = float(np.mean(evm_by_symbol)) if evm_by_symbol.size else float(rx.kpis.evm)
        sync_values = np.array([cfg_sto, err_sto, cfg_cfo, est_cfo, evm_mean], dtype=float)
        x_positions = np.arange(sync_values.size)
        self.sync_plot.clear()
        self._style_plot(self.sync_plot)
        self.sync_plot.setTitle("Sync / EVM summary")
        self.sync_plot.setLabel("bottom", "Metric")
        self.sync_plot.setLabel("left", "Value")
        self.sync_bar_item = pg.BarGraphItem(x=x_positions, height=sync_values, width=0.6, brush="#0ea5e9")
        self.sync_plot.addItem(self.sync_bar_item)
        self.sync_plot.getAxis("bottom").setTicks([self.sync_ticks])

        evm_symbols, evm_by_symbol = self._per_symbol_evm(result)
        self.evm_symbol_curve.setData(evm_symbols, evm_by_symbol)

        subcarriers, relative_error = self._per_subcarrier_relative_error(result)
        self.evm_subcarrier_curve.setData(subcarriers, relative_error)

    def update_batch_result(self, dataframe, experiment_name: str) -> None:
        for axis in self.batch_axes.ravel():
            axis.clear()
            axis.grid(True, alpha=0.25)

        numeric_columns = dataframe.select_dtypes(include=["number"]).columns.tolist()
        preferred_x = next(
            (name for name in ["snr_db", "doppler_hz", "cfo_hz", "delay_spread_s"] if name in dataframe.columns),
            numeric_columns[0] if numeric_columns else None,
        )
        metrics = [name for name in ["ber", "bler", "evm", "throughput_bps"] if name in dataframe.columns]
        axes = self.batch_axes.ravel()

        for index, metric in enumerate(metrics[:4]):
            axis = axes[index]
            if preferred_x and preferred_x != metric:
                axis.plot(dataframe[preferred_x], dataframe[metric], marker="o")
                axis.set_xlabel(preferred_x)
            else:
                axis.plot(np.arange(len(dataframe)), dataframe[metric], marker="o")
                axis.set_xlabel("index")
            axis.set_ylabel(metric)
            axis.set_title(f"{metric} ({experiment_name})")

        if metrics:
            summary_axis = axes[-1]
            summary_axis.clear()
            summary_axis.axis("off")
            summary_text = "\n".join(
                [
                    f"rows: {len(dataframe)}",
                    *(f"{metric}: min={dataframe[metric].min():.4g}, max={dataframe[metric].max():.4g}" for metric in metrics[:3]),
                ]
            )
            summary_axis.text(0.05, 0.95, summary_text, va="top", ha="left", fontsize=10, family="monospace")

        self.batch_figure.suptitle(f"Batch analytics: {experiment_name}")
        self.batch_canvas.draw_idle()
        self.tabs.setCurrentWidget(self.batch_widget)
