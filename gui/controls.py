from __future__ import annotations

from typing import Dict

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ControlPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.widgets: Dict[str, object] = {}
        self.buttons: Dict[str, QPushButton] = {}
        self.path_buttons: Dict[str, QPushButton] = {}
        self.setMinimumWidth(270)
        self.setMaximumWidth(340)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._build_ui()

    def _combo(self, values: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(values)
        return combo

    def _spin(self, minimum: int, maximum: int, value: int, step: int = 1) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        widget.setSingleStep(step)
        return widget

    def _dspin(self, minimum: float, maximum: float, value: float, step: float = 0.1, decimals: int = 3) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setDecimals(decimals)
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        widget.setSingleStep(step)
        return widget

    def _path_selector(self, *, key: str, browse_label: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        line_edit = QLineEdit()
        line_edit.setPlaceholderText("Optional")
        browse_button = QPushButton(browse_label)
        browse_button.setMinimumWidth(42)
        row.addWidget(line_edit, stretch=1)
        row.addWidget(browse_button)
        self.widgets[key] = line_edit
        self.path_buttons[key] = browse_button
        return container

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        mode_box = QGroupBox("Configuration")
        form = QFormLayout(mode_box)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)

        self.widgets["mode"] = self._combo(["data", "control", "compare"])
        self.widgets["modulation"] = self._combo(["QPSK", "16QAM", "64QAM", "256QAM"])
        self.widgets["mcs"] = self._spin(0, 27, 9)
        self.widgets["capture_slots"] = self._spin(1, 200, 1)
        self.widgets["batch_experiment"] = self._combo(
            [
                "ber_vs_snr",
                "bler_vs_snr",
                "evm_vs_snr",
                "control_vs_data",
                "fading_sweep",
                "doppler_sweep",
                "impairment_sweep",
                "file_transfer_sweep",
                "sample_file_transfer_sweep",
            ]
        )
        self.widgets["scs_khz"] = self._combo(["15", "30", "60"])
        self.widgets["fft_size"] = self._combo(["256", "512", "1024"])
        self.widgets["n_rb"] = self._spin(6, 80, 24)
        self.widgets["target_rate"] = self._dspin(0.05, 0.95, 0.50, 0.05, 2)
        self.widgets["channel_model"] = self._combo(["awgn", "rayleigh", "rician"])
        self.widgets["channel_profile"] = self._combo(
            ["static_near", "cell_edge", "pedestrian", "vehicular", "indoor", "urban_los", "urban_nlos", "severe_fading"]
        )
        self.widgets["snr_db"] = self._dspin(-10.0, 40.0, 18.0, 1.0, 1)
        self.widgets["doppler_hz"] = self._dspin(0.0, 1000.0, 5.0, 5.0, 1)
        self.widgets["delay_spread_s"] = self._dspin(0.0, 1e-4, 7.1e-7, 1e-7, 7)
        self.widgets["path_loss_db"] = self._dspin(0.0, 180.0, 0.0, 1.0, 1)
        self.widgets["k_factor_db"] = self._dspin(0.0, 20.0, 8.0, 0.5, 1)
        self.widgets["cfo_hz"] = self._dspin(0.0, 1000.0, 30.0, 5.0, 1)
        self.widgets["sto_samples"] = self._spin(0, 256, 4)
        self.widgets["phase_noise_std"] = self._dspin(0.0, 0.1, 5e-4, 1e-4, 5)
        self.widgets["iq_imbalance_db"] = self._dspin(0.0, 6.0, 0.0, 0.1, 2)
        self.widgets["perfect_sync"] = QCheckBox()
        self.widgets["perfect_channel_estimation"] = QCheckBox()
        self.widgets["use_gnuradio"] = QCheckBox("Use GNU Radio loopback")
        tx_file_selector = self._path_selector(key="tx_file_path", browse_label="...")
        rx_dir_selector = self._path_selector(key="rx_output_dir", browse_label="...")

        form.addRow("Mode", self.widgets["mode"])
        form.addRow("Modulation", self.widgets["modulation"])
        form.addRow("MCS", self.widgets["mcs"])
        form.addRow("Capture slots", self.widgets["capture_slots"])
        form.addRow("Batch experiment", self.widgets["batch_experiment"])
        form.addRow("SCS (kHz)", self.widgets["scs_khz"])
        form.addRow("FFT", self.widgets["fft_size"])
        form.addRow("RB", self.widgets["n_rb"])
        form.addRow("Code rate", self.widgets["target_rate"])
        form.addRow("Channel model", self.widgets["channel_model"])
        form.addRow("Channel profile", self.widgets["channel_profile"])
        form.addRow("SNR (dB)", self.widgets["snr_db"])
        form.addRow("Doppler (Hz)", self.widgets["doppler_hz"])
        form.addRow("Delay spread (s)", self.widgets["delay_spread_s"])
        form.addRow("Path loss (dB)", self.widgets["path_loss_db"])
        form.addRow("K-factor (dB)", self.widgets["k_factor_db"])
        form.addRow("CFO (Hz)", self.widgets["cfo_hz"])
        form.addRow("STO (samples)", self.widgets["sto_samples"])
        form.addRow("Phase noise", self.widgets["phase_noise_std"])
        form.addRow("IQ imbalance", self.widgets["iq_imbalance_db"])
        form.addRow("Perfect sync", self.widgets["perfect_sync"])
        form.addRow("Perfect CE", self.widgets["perfect_channel_estimation"])
        form.addRow("TX file", tx_file_selector)
        form.addRow("RX output", rx_dir_selector)
        form.addRow("", self.widgets["use_gnuradio"])

        layout.addWidget(mode_box)

        primary_button_layout = QGridLayout()
        primary_button_layout.setHorizontalSpacing(6)
        primary_button_layout.setVerticalSpacing(6)
        for key, label in [
            ("run", "Run"),
            ("step_mode", "Step Mode"),
            ("stop", "Stop"),
            ("reset", "Reset"),
            ("save", "Save"),
            ("load", "Load"),
            ("batch", "Batch"),
        ]:
            button = QPushButton(label)
            button.setMinimumHeight(32)
            self.buttons[key] = button
            index = len(self.buttons) - 1
            row = index // 3
            column = index % 3
            primary_button_layout.addWidget(button, row, column)
        layout.addLayout(primary_button_layout)

        tooling_button_layout = QGridLayout()
        tooling_button_layout.setHorizontalSpacing(6)
        tooling_button_layout.setVerticalSpacing(6)
        tooling_start_index = len(self.buttons)
        for key, label in [
            ("tx_sink", "TX sink"),
            ("rx_sink", "RX sink"),
            ("dash", "Open Dash"),
        ]:
            button = QPushButton(label)
            button.setMinimumHeight(32)
            self.buttons[key] = button
            index = len(self.buttons) - tooling_start_index - 1
            tooling_button_layout.addWidget(button, 0, index)
        layout.addLayout(tooling_button_layout)
        layout.addStretch(1)

    def apply_config(self, config: dict) -> None:
        self.widgets["mode"].setCurrentText(config.get("link", {}).get("channel_type", "data"))
        self.widgets["modulation"].setCurrentText(config.get("modulation", {}).get("scheme", "QPSK"))
        self.widgets["batch_experiment"].setCurrentText(
            str(config.get("experiments", {}).get("default_batch_experiment", "ber_vs_snr"))
        )
        self.widgets["capture_slots"].setValue(int(config.get("simulation", {}).get("capture_slots", 1)))
        self.widgets["scs_khz"].setCurrentText(str(int(config.get("numerology", {}).get("scs_khz", 30))))
        self.widgets["fft_size"].setCurrentText(str(int(config.get("numerology", {}).get("fft_size", 512))))
        self.widgets["n_rb"].setValue(int(config.get("numerology", {}).get("n_rb", 24)))
        self.widgets["target_rate"].setValue(float(config.get("coding", {}).get("target_rate", 0.5)))
        self.widgets["channel_model"].setCurrentText(str(config.get("channel", {}).get("model", "rayleigh")))
        self.widgets["channel_profile"].setCurrentText(str(config.get("channel", {}).get("profile", "pedestrian")))
        self.widgets["snr_db"].setValue(float(config.get("channel", {}).get("snr_db", 18.0)))
        self.widgets["doppler_hz"].setValue(float(config.get("channel", {}).get("doppler_hz", 5.0)))
        self.widgets["delay_spread_s"].setValue(float(config.get("channel", {}).get("delay_spread_s", 0.0)))
        self.widgets["path_loss_db"].setValue(float(config.get("channel", {}).get("path_loss_db", 0.0)))
        self.widgets["k_factor_db"].setValue(float(config.get("channel", {}).get("k_factor_db", 8.0)))
        self.widgets["cfo_hz"].setValue(float(config.get("channel", {}).get("cfo_hz", 0.0)))
        self.widgets["sto_samples"].setValue(int(config.get("channel", {}).get("sto_samples", 0)))
        self.widgets["phase_noise_std"].setValue(float(config.get("channel", {}).get("phase_noise_std", 0.0)))
        self.widgets["iq_imbalance_db"].setValue(float(config.get("channel", {}).get("iq_imbalance_db", 0.0)))
        self.widgets["perfect_sync"].setChecked(bool(config.get("receiver", {}).get("perfect_sync", False)))
        self.widgets["perfect_channel_estimation"].setChecked(
            bool(config.get("receiver", {}).get("perfect_channel_estimation", False))
        )
        self.widgets["tx_file_path"].setText(str(config.get("payload_io", {}).get("tx_file_path", "")))
        self.widgets["rx_output_dir"].setText(str(config.get("payload_io", {}).get("rx_output_dir", "")))
        self.widgets["use_gnuradio"].setChecked(bool(config.get("simulation", {}).get("use_gnuradio", False)))

    def build_patch(self) -> dict:
        mode = self.widgets["mode"].currentText()
        return {
            "link": {"channel_type": "data" if mode == "compare" else mode},
            "modulation": {"scheme": self.widgets["modulation"].currentText()},
            "coding": {"target_rate": float(self.widgets["target_rate"].value())},
            "numerology": {
                "scs_khz": float(self.widgets["scs_khz"].currentText()),
                "fft_size": int(self.widgets["fft_size"].currentText()),
                "n_rb": int(self.widgets["n_rb"].value()),
            },
            "channel": {
                "model": self.widgets["channel_model"].currentText(),
                "fading_type": self.widgets["channel_model"].currentText(),
                "profile": self.widgets["channel_profile"].currentText(),
                "snr_db": float(self.widgets["snr_db"].value()),
                "doppler_hz": float(self.widgets["doppler_hz"].value()),
                "delay_spread_s": float(self.widgets["delay_spread_s"].value()),
                "path_loss_db": float(self.widgets["path_loss_db"].value()),
                "k_factor_db": float(self.widgets["k_factor_db"].value()),
                "cfo_hz": float(self.widgets["cfo_hz"].value()),
                "sto_samples": int(self.widgets["sto_samples"].value()),
                "phase_noise_std": float(self.widgets["phase_noise_std"].value()),
                "iq_imbalance_db": float(self.widgets["iq_imbalance_db"].value()),
            },
            "payload_io": {
                "tx_file_path": self.widgets["tx_file_path"].text().strip(),
                "rx_output_dir": self.widgets["rx_output_dir"].text().strip(),
            },
            "receiver": {
                "perfect_sync": self.widgets["perfect_sync"].isChecked(),
                "perfect_channel_estimation": self.widgets["perfect_channel_estimation"].isChecked(),
            },
            "simulation": {
                "use_gnuradio": self.widgets["use_gnuradio"].isChecked(),
                "capture_slots": int(self.widgets["capture_slots"].value()),
            },
            "experiments": {"default_batch_experiment": self.widgets["batch_experiment"].currentText()},
        }

    def selected_batch_experiment(self) -> str:
        return str(self.widgets["batch_experiment"].currentText())
