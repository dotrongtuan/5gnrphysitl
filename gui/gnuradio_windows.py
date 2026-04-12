from __future__ import annotations

import numpy as np
from PyQt5.QtWidgets import QDialog, QTabWidget, QVBoxLayout, QWidget

try:  # pragma: no cover - depends on PyQt installation details
    from PyQt5 import sip
except ImportError:  # pragma: no cover
    import sip  # type: ignore

try:  # pragma: no cover - depends on GNU Radio runtime
    from gnuradio import blocks, gr, qtgui
    from gnuradio.fft import window

    HAVE_GNURADIO = True
except ImportError:  # pragma: no cover - graceful fallback
    HAVE_GNURADIO = False


def _wrap_qwidget(qtgui_sink: object) -> QWidget:
    return sip.wrapinstance(int(qtgui_sink.qwidget()), QWidget)


class _BaseSinkWindow(QDialog):
    def __init__(self, title: str, waveform: np.ndarray, sample_rate: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not HAVE_GNURADIO:
            raise RuntimeError("GNU Radio QT sinks are not available in this environment.")
        self.setWindowTitle(title)
        self.resize(1200, 820)

        self.tb = gr.top_block(title)
        self._started = False
        self.source = blocks.vector_source_c(waveform.astype(np.complex64).tolist(), False, 1, [])
        self.throttle = blocks.throttle(gr.sizeof_gr_complex, sample_rate, True)
        self.tabs = QTabWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self.tb.connect(self.source, self.throttle)

    def showEvent(self, event) -> None:  # pragma: no cover - GUI path
        if not self._started:
            self.tb.start()
            self._started = True
        super().showEvent(event)

    def closeEvent(self, event) -> None:  # pragma: no cover - GUI path
        try:
            if self._started:
                self.tb.stop()
                self.tb.wait()
                self._started = False
        finally:
            super().closeEvent(event)


class TxSinkWindow(_BaseSinkWindow):
    def __init__(self, waveform: np.ndarray, sample_rate: float, parent: QWidget | None = None) -> None:
        super().__init__("GNU Radio TX Instrumentation", waveform=waveform, sample_rate=sample_rate, parent=parent)
        self.time_sink = qtgui.time_sink_c(2048, sample_rate, "TX Waveform", 1)
        self.freq_sink = qtgui.freq_sink_c(4096, window.WIN_BLACKMAN_hARRIS, 0, sample_rate, "TX Spectrum", 1)
        self.waterfall_sink = qtgui.waterfall_sink_c(
            2048,
            window.WIN_BLACKMAN_hARRIS,
            0,
            sample_rate,
            "TX Waterfall",
            1,
        )
        self.tb.connect(self.throttle, self.time_sink)
        self.tb.connect(self.throttle, self.freq_sink)
        self.tb.connect(self.throttle, self.waterfall_sink)
        self.tabs.addTab(_wrap_qwidget(self.time_sink), "Time")
        self.tabs.addTab(_wrap_qwidget(self.freq_sink), "Spectrum")
        self.tabs.addTab(_wrap_qwidget(self.waterfall_sink), "Waterfall")


class RxSinkWindow(_BaseSinkWindow):
    def __init__(self, waveform: np.ndarray, sample_rate: float, parent: QWidget | None = None) -> None:
        super().__init__("GNU Radio RX Instrumentation", waveform=waveform, sample_rate=sample_rate, parent=parent)
        self.time_sink = qtgui.time_sink_c(2048, sample_rate, "RX Waveform", 1)
        self.constellation_sink = qtgui.const_sink_c(1024, "RX Constellation", 1)
        self.freq_sink = qtgui.freq_sink_c(4096, window.WIN_BLACKMAN_hARRIS, 0, sample_rate, "RX Spectrum", 1)
        self.waterfall_sink = qtgui.waterfall_sink_c(
            2048,
            window.WIN_BLACKMAN_hARRIS,
            0,
            sample_rate,
            "RX Waterfall",
            1,
        )
        self.tb.connect(self.throttle, self.time_sink)
        self.tb.connect(self.throttle, self.constellation_sink)
        self.tb.connect(self.throttle, self.freq_sink)
        self.tb.connect(self.throttle, self.waterfall_sink)
        self.tabs.addTab(_wrap_qwidget(self.time_sink), "Time")
        self.tabs.addTab(_wrap_qwidget(self.constellation_sink), "Constellation")
        self.tabs.addTab(_wrap_qwidget(self.freq_sink), "Spectrum")
        self.tabs.addTab(_wrap_qwidget(self.waterfall_sink), "Waterfall")
