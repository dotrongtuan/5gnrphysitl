from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys
import webbrowser

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QSplitter, QWidget

from experiments.ber_vs_snr import run_experiment as run_ber_vs_snr
from experiments.bler_vs_snr import run_experiment as run_bler_vs_snr
from experiments.common import simulate_file_transfer, simulate_link_sequence
from experiments.control_vs_data import run_experiment as run_control_vs_data
from experiments.doppler_sweep import run_experiment as run_doppler_sweep
from experiments.evm_vs_snr import run_experiment as run_evm_vs_snr
from experiments.fading_sweep import run_experiment as run_fading_sweep
from experiments.file_transfer_sweep import run_experiment as run_file_transfer_sweep
from experiments.impairment_sweep import run_experiment as run_impairment_sweep
from experiments.sample_file_transfer_sweep import run_experiment as run_sample_file_transfer_sweep
from gui.config_editor import load_config_dialog, save_config_dialog
from gui.controls import ControlPanel
from gui.dashboard import DashboardPanel
from gui.gnuradio_windows import GNURADIO_IMPORT_ERROR, HAVE_GNURADIO, RxSinkWindow, TxSinkWindow
from gui.plots import PlotPanel
from utils.io import save_dataframe_csv
from utils.validators import deep_merge


BATCH_EXPERIMENTS = {
    "ber_vs_snr": run_ber_vs_snr,
    "bler_vs_snr": run_bler_vs_snr,
    "evm_vs_snr": run_evm_vs_snr,
    "control_vs_data": run_control_vs_data,
    "fading_sweep": run_fading_sweep,
    "doppler_sweep": run_doppler_sweep,
    "impairment_sweep": run_impairment_sweep,
    "file_transfer_sweep": run_file_transfer_sweep,
    "sample_file_transfer_sweep": run_sample_file_transfer_sweep,
}


class SimulationWorker(QObject):
    finished = pyqtSignal()
    result_ready = pyqtSignal(object)
    log_message = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, config: dict, batch: bool = False, experiment_name: str = "ber_vs_snr") -> None:
        super().__init__()
        self.config = config
        self.batch = batch
        self.experiment_name = experiment_name

    def run(self) -> None:
        try:
            if self.batch:
                self.log_message.emit(f"Running batch experiment: {self.experiment_name}.")
                output_dir = Path(self.config.get("simulation", {}).get("output_dir", "outputs"))
                runner = BATCH_EXPERIMENTS[self.experiment_name]
                dataframe = runner(self.config, output_dir=output_dir)
                self.result_ready.emit({"dataframe": dataframe, "experiment_name": self.experiment_name})
            else:
                tx_file_path = str(self.config.get("payload_io", {}).get("tx_file_path", "")).strip()
                if tx_file_path:
                    self.log_message.emit(f"Running file-transfer simulation for {Path(tx_file_path).name}.")
                    result = simulate_file_transfer(
                        self.config,
                        source_path=tx_file_path,
                        output_dir=str(self.config.get("payload_io", {}).get("rx_output_dir", "")).strip() or None,
                    )
                else:
                    self.log_message.emit("Running single-link simulation.")
                    result = simulate_link_sequence(self.config)
                self.result_ready.emit(result)
        except Exception as exc:  # pragma: no cover - GUI path
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class NrPhyResearchApp(QMainWindow):
    def __init__(self, base_config: dict) -> None:
        super().__init__()
        self.setWindowTitle("5G NR PHY STL Research Dashboard")
        self.resize(1600, 900)
        self.base_config = deepcopy(base_config)
        self.current_config = deepcopy(base_config)
        self.thread: QThread | None = None
        self.worker: SimulationWorker | None = None
        self.last_result: dict | None = None
        self.last_batch_dataframe = None
        self.last_batch_csv: Path | None = None
        self.dash_process: subprocess.Popen | None = None
        self.gr_windows: list[QWidget] = []
        self.step_mode_requested = False

        self.controls = ControlPanel()
        self.controls.apply_config(self.current_config)
        self.plots = PlotPanel()
        self.dashboard = DashboardPanel()

        self._build_ui()
        self._connect_signals()
        self._configure_optional_tool_buttons()
        self._update_notes()
        self.dashboard.append_log("Dashboard initialized.")

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        self.splitter.addWidget(self.controls)
        self.splitter.addWidget(self.plots)
        self.splitter.addWidget(self.dashboard)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([290, 1080, 270])
        layout.addWidget(self.splitter)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.controls.buttons["run"].clicked.connect(self.run_single)
        self.controls.buttons["step_mode"].clicked.connect(self.run_step_mode)
        self.controls.buttons["batch"].clicked.connect(self.run_batch)
        self.controls.buttons["reset"].clicked.connect(self.reset_config)
        self.controls.buttons["save"].clicked.connect(self.save_config)
        self.controls.buttons["load"].clicked.connect(self.load_config)
        self.controls.buttons["stop"].clicked.connect(self.stop_worker)
        self.controls.buttons["tx_sink"].clicked.connect(self.open_tx_sink)
        self.controls.buttons["rx_sink"].clicked.connect(self.open_rx_sink)
        self.controls.buttons["dash"].clicked.connect(self.open_dash_dashboard)
        self.controls.path_buttons["tx_file_path"].clicked.connect(self.choose_tx_file)
        self.controls.path_buttons["rx_output_dir"].clicked.connect(self.choose_rx_output_dir)

    def _configure_optional_tool_buttons(self) -> None:
        if not HAVE_GNURADIO:
            self.controls.buttons["tx_sink"].setEnabled(False)
            self.controls.buttons["rx_sink"].setEnabled(False)
            reason = GNURADIO_IMPORT_ERROR or "GNU Radio is unavailable in the active interpreter."
            self.controls.buttons["tx_sink"].setToolTip(f"Disabled: {reason}")
            self.controls.buttons["rx_sink"].setToolTip(f"Disabled: {reason}")
        self.controls.buttons["dash"].setToolTip("Launch a browser-based dashboard for the latest batch CSV.")

    def _build_runtime_config(self) -> dict:
        self.current_config = deep_merge(self.base_config, self.controls.build_patch())
        self._update_notes()
        return deepcopy(self.current_config)

    @staticmethod
    def _dash_available() -> bool:
        return importlib.util.find_spec("dash") is not None and importlib.util.find_spec("plotly") is not None

    def _update_status_panel(self, result: dict | None = None) -> None:
        status = {
            "Python executable": sys.executable,
            "GNU Radio bindings": "Available" if HAVE_GNURADIO else "Unavailable",
            "TX sink button": "Enabled" if self.controls.buttons["tx_sink"].isEnabled() else "Disabled",
            "RX sink button": "Enabled" if self.controls.buttons["rx_sink"].isEnabled() else "Disabled",
            "Dash / Plotly": "Available" if self._dash_available() else "Unavailable",
            "Link direction": str(self.current_config.get("link", {}).get("direction", "downlink")),
            "GNU Radio loopback requested": "Yes" if bool(self.current_config.get("simulation", {}).get("use_gnuradio", False)) else "No",
            "Capture slots": int(self.current_config.get("simulation", {}).get("capture_slots", 1)),
            "Perfect sync": "Yes" if bool(self.current_config.get("receiver", {}).get("perfect_sync", False)) else "No",
            "Perfect channel estimation": "Yes" if bool(self.current_config.get("receiver", {}).get("perfect_channel_estimation", False)) else "No",
            "Transform precoding": "Yes" if bool(self.current_config.get("uplink", {}).get("transform_precoding", False)) else "No",
        }
        tx_file = str(self.current_config.get("payload_io", {}).get("tx_file_path", "")).strip()
        if tx_file:
            status["TX file"] = tx_file
            status["RX output dir"] = str(self.current_config.get("payload_io", {}).get("rx_output_dir", "")).strip() or "outputs/rx_files"
        if not HAVE_GNURADIO:
            status["GNU Radio reason"] = GNURADIO_IMPORT_ERROR or "GNU Radio import failed."
            status["How to enable sinks"] = "Run the GUI from a Conda env with Python 3.10 + GNU Radio 3.10+ installed."
        if result is not None:
            if result.get("captured_slots"):
                status["Captured slot results"] = int(result.get("captured_slots", 1))
            channel_state = result.get("channel_state", {})
            if channel_state.get("gnu_radio_requested"):
                status["GNU Radio loopback used"] = "Yes" if channel_state.get("gnu_radio_used") else "No"
                if channel_state.get("gnu_radio_error"):
                    status["Loopback fallback reason"] = channel_state["gnu_radio_error"]
            file_transfer = result.get("file_transfer")
            if file_transfer:
                status["Transfer mode"] = "File"
                status["Transfer success"] = "Yes" if file_transfer.get("success") else "No"
                status["File chunks"] = f"{file_transfer['chunks_passed']} / {file_transfer['total_chunks']} passed"
                if file_transfer.get("received_snr_label"):
                    status["RX SNR label"] = file_transfer["received_snr_label"]
                status["RX restored file"] = file_transfer.get("restored_file_path") or "not written"
        self.dashboard.update_status(status)

    def _update_notes(self, result: dict | None = None) -> None:
        config = self.current_config
        link = config.get("link", {})
        modulation = config.get("modulation", {})
        numerology = config.get("numerology", {})
        channel = config.get("channel", {})
        receiver = config.get("receiver", {})
        simulation = config.get("simulation", {})

        notes = [
            f"Direction: {link.get('direction', 'downlink')} | Mode: {link.get('channel_type', 'data')} | Modulation: {modulation.get('scheme', 'QPSK')} | "
            f"SCS: {numerology.get('scs_khz', 30)} kHz | FFT: {numerology.get('fft_size', 512)}",
            f"Channel: {channel.get('model', 'awgn')} / {channel.get('profile', 'static_near')} | "
            f"SNR: {channel.get('snr_db', 0.0)} dB | Doppler: {channel.get('doppler_hz', 0.0)} Hz",
            f"Captured slots per run: {simulation.get('capture_slots', 1)}",
            "Use the PHY Pipeline tab to inspect each stage from transport bits through coding, OFDM, channel impairments, synchronization, equalization, and decoding.",
            "Use Step Mode to run once and then replay the chain block-by-block with the pipeline timeline and playback controls.",
        ]

        if bool(receiver.get("perfect_sync", False)):
            notes.append("Perfect synchronization is enabled. This is a teaching simplification.")
        if bool(receiver.get("perfect_channel_estimation", False)):
            notes.append("Perfect channel estimation is enabled. DMRS estimation plots remain useful, but KPI values are optimistic.")
        if str(link.get("direction", "downlink")).lower() == "uplink":
            if bool(config.get("uplink", {}).get("transform_precoding", False)):
                notes.append("Uplink baseline is active with transform precoding enabled. The PHY Pipeline includes transform precoding and inverse transform stages.")
            else:
                notes.append("Uplink baseline is active in CP-OFDM mode. Enable transform precoding to inspect a DFT-s-OFDM style PUSCH path.")
        if bool(simulation.get("use_gnuradio", False)):
            if HAVE_GNURADIO:
                notes.append("GNU Radio loopback is requested and QT sinks can be launched from the GUI.")
            else:
                notes.append("GNU Radio loopback is requested, but GNU Radio is not installed in the active Python environment.")
        if self.controls.widgets["mode"].currentText() == "compare":
            notes.append("Compare mode currently reuses the data path in single-run mode. Use batch experiments for explicit comparisons.")
        tx_file = str(self.current_config.get("payload_io", {}).get("tx_file_path", "")).strip()
        if tx_file:
            rx_output_dir = str(self.current_config.get("payload_io", {}).get("rx_output_dir", "")).strip() or "outputs/rx_files"
            notes.append(f"File-transfer mode is active. TX file: {tx_file}")
            notes.append(f"Recovered files are written under: {rx_output_dir}")
            notes.append(
                "File transfer is byte-perfect and all-or-nothing at the application level: "
                "if all PHY chunks pass CRC, the RX file matches exactly; if any chunk fails, no RX file is written."
            )
            notes.append(
                "Larger files are more sensitive because file success requires every transport block to survive the PHY chain."
            )

        if result is not None:
            if result.get("sequence_summary"):
                summary = result["sequence_summary"]
                notes.append(
                    f"Multi-slot capture summary: {summary.get('captured_slots', 1)} slots across {summary.get('frames_covered', 1)} frame(s)."
                )
            channel_state = result.get("channel_state", {})
            if channel_state.get("gnu_radio_requested") and not channel_state.get("gnu_radio_used"):
                notes.append("GNU Radio loopback request fell back to the Python-only channel path at runtime.")
                error_message = channel_state.get("gnu_radio_error")
                if error_message:
                    notes.append(f"GNU Radio fallback reason: {error_message}")
            if result.get("file_transfer"):
                transfer = result["file_transfer"]
                notes.append(
                    f"File transfer used {transfer['total_chunks']} transport blocks. "
                    f"Chunk pass count: {transfer['chunks_passed']} / {transfer['total_chunks']}."
                )
                if transfer.get("received_snr_label"):
                    notes.append(f"RX file label includes SNR tag: {transfer['received_snr_label']}.")
                if transfer.get("error"):
                    notes.append(f"File transfer note: {transfer['error']}")

        notes.append("Signal-domain sync summary mixes samples, Hz, and linear EVM for quick diagnostics.")
        self.dashboard.set_notes(notes)
        self._update_status_panel(result)

    def _start_worker(self, config: dict, batch: bool, experiment_name: str = "ber_vs_snr") -> None:
        if self.thread is not None:
            self.dashboard.append_log("Worker already running.")
            return
        self.thread = QThread()
        self.worker = SimulationWorker(config=config, batch=batch, experiment_name=experiment_name)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log_message.connect(self.dashboard.append_log)
        self.worker.result_ready.connect(self.handle_result)
        self.worker.error.connect(self.handle_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_worker)
        self.thread.start()

    def _clear_worker(self) -> None:
        self.thread = None
        self.worker = None
        self.dashboard.append_log("Worker finished.")

    def run_single(self) -> None:
        config = self._build_runtime_config()
        self.step_mode_requested = False
        self.dashboard.append_log("Preparing single-link run.")
        self._start_worker(config=config, batch=False)

    def run_step_mode(self) -> None:
        config = self._build_runtime_config()
        self.step_mode_requested = True
        self.dashboard.append_log("Preparing single-link run for step-by-step PHY playback.")
        self._start_worker(config=config, batch=False)

    def run_batch(self) -> None:
        config = self._build_runtime_config()
        experiment_name = self.controls.selected_batch_experiment()
        self.dashboard.append_log(f"Preparing batch experiment: {experiment_name}.")
        self._start_worker(config=config, batch=True, experiment_name=experiment_name)

    def stop_worker(self) -> None:
        if self.thread is None:
            self.dashboard.append_log("No worker is active.")
            return
        self.thread.requestInterruption()
        self.dashboard.append_log("Stop requested. The current batch will end at the next safe point.")

    def reset_config(self) -> None:
        self.current_config = deepcopy(self.base_config)
        self.controls.apply_config(self.current_config)
        self._update_notes()
        self.dashboard.append_log("Configuration reset to defaults.")

    def save_config(self) -> None:
        config = self._build_runtime_config()
        path = save_config_dialog(self, config)
        if path:
            self.dashboard.append_log(f"Configuration saved to {path}")

    def load_config(self) -> None:
        config = load_config_dialog(self)
        if config is None:
            return
        self.current_config = deep_merge(self.base_config, config)
        self.controls.apply_config(self.current_config)
        self._update_notes()
        self.dashboard.append_log("Configuration loaded from YAML.")

    def choose_tx_file(self) -> None:
        start_dir = str(Path(self.current_config.get("payload_io", {}).get("tx_file_path", "")).expanduser().resolve().parent) if str(self.current_config.get("payload_io", {}).get("tx_file_path", "")).strip() else str(Path.cwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select TX-side file",
            start_dir,
            "Supported files (*.txt *.png *.jpg *.jpeg *.bmp *.gif *.json *.csv *.md);;All files (*.*)",
        )
        if not path:
            return
        self.controls.widgets["tx_file_path"].setText(path)
        self.dashboard.append_log(f"Selected TX file: {path}")
        self._build_runtime_config()

    def choose_rx_output_dir(self) -> None:
        start_dir = str(Path(self.current_config.get("payload_io", {}).get("rx_output_dir", "")).expanduser()) if str(self.current_config.get("payload_io", {}).get("rx_output_dir", "")).strip() else str(Path.cwd())
        path = QFileDialog.getExistingDirectory(self, "Select RX output directory", start_dir)
        if not path:
            return
        self.controls.widgets["rx_output_dir"].setText(path)
        self.dashboard.append_log(f"Selected RX output directory: {path}")
        self._build_runtime_config()

    def _persist_batch_dataframe(self, dataframe, experiment_name: str) -> Path:
        output_dir = Path(self.current_config.get("simulation", {}).get("output_dir", "outputs")) / "gui_batch"
        csv_path = output_dir / f"{experiment_name}_latest.csv"
        save_dataframe_csv(dataframe.to_dict(orient="records"), csv_path)
        self.last_batch_csv = csv_path
        return csv_path

    def _ensure_last_result(self) -> dict | None:
        if self.last_result is not None:
            return self.last_result
        self.dashboard.append_log("No cached single-link result. Running one simulation synchronously for instrumentation.")
        try:
            config = self._build_runtime_config()
            tx_file_path = str(config.get("payload_io", {}).get("tx_file_path", "")).strip()
            if tx_file_path:
                result = simulate_file_transfer(
                    config,
                    source_path=tx_file_path,
                    output_dir=str(config.get("payload_io", {}).get("rx_output_dir", "")).strip() or None,
                )
            else:
                result = simulate_link_sequence(config)
        except Exception as exc:  # pragma: no cover - GUI path
            self.handle_error(str(exc))
            return None
        self.last_result = result
        self.plots.update_from_result(result)
        self.dashboard.update_kpis(result["kpis"].as_dict())
        self._update_notes(result)
        return result

    def _latest_csv_for_dash(self) -> Path | None:
        if self.last_batch_csv and self.last_batch_csv.exists():
            return self.last_batch_csv
        output_dir = Path(self.current_config.get("simulation", {}).get("output_dir", "outputs"))
        csv_files = sorted(output_dir.rglob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
        return csv_files[0] if csv_files else None

    def open_tx_sink(self) -> None:
        result = self._ensure_last_result()
        if result is None:
            return
        if not HAVE_GNURADIO:
            self.handle_error("GNU Radio QT sinks are not available in the current environment.")
            return
        window = TxSinkWindow(result["tx"].waveform, result["tx"].metadata.sample_rate, parent=self)
        window.show()
        self.gr_windows.append(window)
        self.dashboard.append_log("Opened GNU Radio TX sink window.")

    def open_rx_sink(self) -> None:
        result = self._ensure_last_result()
        if result is None:
            return
        if not HAVE_GNURADIO:
            self.handle_error("GNU Radio QT sinks are not available in the current environment.")
            return
        window = RxSinkWindow(result["rx_waveform"], result["tx"].metadata.sample_rate, parent=self)
        window.show()
        self.gr_windows.append(window)
        self.dashboard.append_log("Opened GNU Radio RX sink window.")

    def open_dash_dashboard(self) -> None:
        if not self._dash_available():
            self.handle_error("Dash and Plotly are not installed in the active Python environment.")
            return
        csv_path = self._latest_csv_for_dash()
        if csv_path is None:
            self.handle_error("No batch CSV is available. Run a batch experiment first.")
            return
        if self.dash_process and self.dash_process.poll() is None:
            webbrowser.open("http://127.0.0.1:8050", new=2)
            self.dashboard.append_log("Dash server is already running. Opened browser.")
            return
        command = [
            sys.executable,
            "-m",
            "gui.dash_app",
            "--csv",
            str(csv_path.resolve()),
            "--title",
            "5G NR PHY STL Batch Dashboard",
            "--open-browser",
        ]
        self.dash_process = subprocess.Popen(command, cwd=str(Path(__file__).resolve().parent.parent))
        self.dashboard.append_log(f"Started Dash dashboard for {csv_path.name}.")

    def handle_result(self, result: object) -> None:
        if isinstance(result, dict) and "tx" in result:
            self.last_result = result
            self.plots.update_from_result(result)
            self.dashboard.update_kpis(result["kpis"].as_dict())
            self._update_notes(result)
            if self.step_mode_requested:
                self.plots.tabs.setCurrentWidget(self.plots.pipeline_panel)
                self.plots.pipeline_panel.reset_playback()
                self.dashboard.append_log("Step mode is ready in the PHY Pipeline tab.")
            self.step_mode_requested = False
            channel_state = result.get("channel_state", {})
            if channel_state.get("gnu_radio_requested") and not channel_state.get("gnu_radio_used"):
                self.dashboard.append_log("GNU Radio loopback request fell back to the Python-only channel path.")
            if result.get("file_transfer"):
                transfer = result["file_transfer"]
                if transfer.get("success"):
                    self.dashboard.append_log(f"File transfer completed. RX file: {transfer.get('restored_file_path')}")
                else:
                    self.dashboard.append_log(f"File transfer completed with errors: {transfer.get('error')}")
            else:
                self.dashboard.append_log("Single-link simulation completed.")
        elif isinstance(result, dict) and "dataframe" in result:
            self.step_mode_requested = False
            dataframe = result["dataframe"]
            experiment_name = str(result.get("experiment_name", "batch"))
            self.last_batch_dataframe = dataframe
            csv_path = self._persist_batch_dataframe(dataframe, experiment_name=experiment_name)
            self.plots.update_batch_result(dataframe, experiment_name)
            self._update_notes()
            self.dashboard.append_log(f"Batch experiment completed with {len(dataframe)} points. CSV saved to {csv_path}.")
            summary = {"rows": len(dataframe)}
            for metric in ["ber", "bler", "evm", "throughput_bps"]:
                if metric in dataframe.columns:
                    summary[f"min_{metric}"] = float(dataframe[metric].min())
                    summary[f"max_{metric}"] = float(dataframe[metric].max())
            self.dashboard.update_kpis(summary)

    def handle_error(self, message: str) -> None:
        self.step_mode_requested = False
        self.dashboard.append_log(f"Error: {message}")
        QMessageBox.critical(self, "Simulation error", message)

    def closeEvent(self, event) -> None:  # pragma: no cover - GUI path
        for window in list(self.gr_windows):
            try:
                window.close()
            except Exception:
                pass
        self.gr_windows.clear()
        if self.dash_process and self.dash_process.poll() is None:
            self.dash_process.terminate()
            try:
                self.dash_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.dash_process.kill()
        super().closeEvent(event)


def launch_app(config: dict) -> None:
    app = QApplication.instance() or QApplication([])
    window = NrPhyResearchApp(config)
    window.show()
    app.exec_()
