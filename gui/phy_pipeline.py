from __future__ import annotations

from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from phy.coding import _polar_transform, attach_crc


pg.setConfigOptions(antialias=True, imageAxisOrder="row-major")


class PhyPipelinePanel(QWidget):
    PLAYBACK_INTERVALS_MS = {
        "0.5x": 1400,
        "1x": 900,
        "2x": 550,
        "4x": 250,
    }

    SECTION_COLORS = {
        "TX": "#38bdf8",
        "Channel": "#f59e0b",
        "RX": "#34d399",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result: dict[str, Any] | None = None
        self.stages: list[dict[str, Any]] = []
        self.current_stage_index = -1
        self.stage_buttons: list[QPushButton] = []
        self.arrow_labels: list[QLabel] = []
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_animation)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        self.overview_label = QLabel()
        self.overview_label.setWordWrap(True)
        self.overview_label.setTextFormat(Qt.RichText)
        self.overview_label.setText(
            "<b>Interactive PHY Flow Explorer</b><br>"
            "Bits -> CRC -> Coding -> Rate Matching -> Scrambling -> QAM Mapping -> Resource Grid + DMRS -> "
            "OFDM/IFFT + CP -> Channel/Impairments -> Sync -> FFT -> Channel Estimation -> Equalization -> "
            "Demapping -> Decoding -> CRC Check"
        )
        layout.addWidget(self.overview_label)

        flow_group = QGroupBox("PHY Pipeline Flow")
        flow_layout = QVBoxLayout(flow_group)
        flow_layout.setContentsMargins(8, 8, 8, 8)
        flow_layout.setSpacing(8)

        self.flow_scroll = QScrollArea()
        self.flow_scroll.setWidgetResizable(True)
        self.flow_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.flow_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.flow_container = QWidget()
        self.flow_row = QHBoxLayout(self.flow_container)
        self.flow_row.setContentsMargins(6, 6, 6, 6)
        self.flow_row.setSpacing(8)
        self.flow_row.addStretch(1)
        self.flow_scroll.setWidget(self.flow_container)
        flow_layout.addWidget(self.flow_scroll)

        playback_row = QHBoxLayout()
        playback_row.setSpacing(6)
        self.prev_button = QPushButton("Prev")
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.next_button = QPushButton("Next")
        self.reset_button = QPushButton("Reset")
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(list(self.PLAYBACK_INTERVALS_MS.keys()))
        self.speed_combo.setCurrentText("1x")
        self.play_state_label = QLabel("Step-by-step playback is idle.")
        for button in [self.prev_button, self.play_button, self.pause_button, self.next_button, self.reset_button]:
            button.setMinimumHeight(30)
        playback_row.addWidget(self.prev_button)
        playback_row.addWidget(self.play_button)
        playback_row.addWidget(self.pause_button)
        playback_row.addWidget(self.next_button)
        playback_row.addWidget(self.reset_button)
        playback_row.addWidget(QLabel("Speed"))
        playback_row.addWidget(self.speed_combo)
        playback_row.addStretch(1)
        playback_row.addWidget(self.play_state_label)
        flow_layout.addLayout(playback_row)

        timeline_grid = QGridLayout()
        timeline_grid.setHorizontalSpacing(8)
        timeline_grid.setVerticalSpacing(6)

        self.stage_slider = QSlider(Qt.Horizontal)
        self.frame_slider = QSlider(Qt.Horizontal)
        self.slot_slider = QSlider(Qt.Horizontal)
        self.symbol_slider = QSlider(Qt.Horizontal)
        self.stage_value_label = QLabel("Stage 0/0")
        self.frame_value_label = QLabel("Frame 0")
        self.slot_value_label = QLabel("Slot 0")
        self.symbol_value_label = QLabel("Symbol 0")

        for slider in [self.stage_slider, self.frame_slider, self.slot_slider, self.symbol_slider]:
            slider.setRange(0, 0)

        timeline_grid.addWidget(QLabel("Stage timeline"), 0, 0)
        timeline_grid.addWidget(self.stage_slider, 0, 1)
        timeline_grid.addWidget(self.stage_value_label, 0, 2)
        timeline_grid.addWidget(QLabel("Frame"), 1, 0)
        timeline_grid.addWidget(self.frame_slider, 1, 1)
        timeline_grid.addWidget(self.frame_value_label, 1, 2)
        timeline_grid.addWidget(QLabel("Slot"), 2, 0)
        timeline_grid.addWidget(self.slot_slider, 2, 1)
        timeline_grid.addWidget(self.slot_value_label, 2, 2)
        timeline_grid.addWidget(QLabel("Symbol"), 3, 0)
        timeline_grid.addWidget(self.symbol_slider, 3, 1)
        timeline_grid.addWidget(self.symbol_value_label, 3, 2)
        flow_layout.addLayout(timeline_grid)

        layout.addWidget(flow_group, stretch=0)

        details_splitter = QSplitter(Qt.Horizontal)
        details_splitter.setChildrenCollapsible(False)
        details_splitter.setHandleWidth(8)
        layout.addWidget(details_splitter, stretch=1)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)

        self.stage_title = QLabel("Run a simulation, then inspect each PHY block.")
        self.stage_title.setWordWrap(True)
        self.stage_title.setTextFormat(Qt.RichText)
        info_layout.addWidget(self.stage_title)

        self.stage_summary = QPlainTextEdit()
        self.stage_summary.setReadOnly(True)
        self.stage_summary.setMaximumBlockCount(400)
        info_layout.addWidget(self.stage_summary, stretch=1)

        self.metrics_table = QTableWidget(0, 2)
        self.metrics_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.metrics_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.metrics_table.setWordWrap(True)
        info_layout.addWidget(self.metrics_table, stretch=1)

        artifact_row = QHBoxLayout()
        artifact_row.addWidget(QLabel("Artifact"))
        self.artifact_selector = QComboBox()
        artifact_row.addWidget(self.artifact_selector, stretch=1)
        info_layout.addLayout(artifact_row)

        self.artifact_caption = QLabel("Stage artifacts will appear here.")
        self.artifact_caption.setWordWrap(True)
        info_layout.addWidget(self.artifact_caption)

        details_splitter.addWidget(info_widget)

        visual_widget = QWidget()
        visual_layout = QVBoxLayout(visual_widget)
        visual_layout.setContentsMargins(0, 0, 0, 0)
        visual_layout.setSpacing(6)

        self.primary_plot = pg.PlotWidget()
        self.secondary_plot = pg.PlotWidget()
        self.primary_plot.setMinimumHeight(280)
        self.secondary_plot.setMinimumHeight(200)
        self._style_plot(self.primary_plot)
        self._style_plot(self.secondary_plot)
        visual_layout.addWidget(self.primary_plot, stretch=3)
        visual_layout.addWidget(self.secondary_plot, stretch=2)

        self.data_excerpt = QPlainTextEdit()
        self.data_excerpt.setReadOnly(True)
        self.data_excerpt.setMaximumBlockCount(600)
        visual_layout.addWidget(self.data_excerpt, stretch=1)

        details_splitter.addWidget(visual_widget)
        details_splitter.setSizes([380, 980])

        self.prev_button.clicked.connect(self.step_backward)
        self.play_button.clicked.connect(self.start_playback)
        self.pause_button.clicked.connect(self.pause_playback)
        self.next_button.clicked.connect(self.step_forward)
        self.reset_button.clicked.connect(self.reset_playback)
        self.stage_slider.valueChanged.connect(self._on_stage_slider_changed)
        self.frame_slider.valueChanged.connect(lambda value: self.frame_value_label.setText(f"Frame {value}"))
        self.slot_slider.valueChanged.connect(lambda value: self.slot_value_label.setText(f"Slot {value}"))
        self.symbol_slider.valueChanged.connect(self._on_symbol_changed)
        self.artifact_selector.currentIndexChanged.connect(self._render_current_artifact)

    @staticmethod
    def _style_plot(plot_widget: pg.PlotWidget) -> None:
        plot_item = plot_widget.getPlotItem()
        plot_item.showGrid(x=True, y=True, alpha=0.25)
        plot_item.getAxis("left").setTextPen("#94a3b8")
        plot_item.getAxis("bottom").setTextPen("#94a3b8")
        plot_item.getAxis("left").setPen(pg.mkPen("#475569"))
        plot_item.getAxis("bottom").setPen(pg.mkPen("#475569"))
        plot_item.titleLabel.item.setDefaultTextColor(pg.mkColor("#d8dee9"))

    def set_result(self, result: dict[str, Any]) -> None:
        self.result = result
        self.stages = self._build_stage_models(result)
        self._rebuild_flow()
        numerology = result["tx"].metadata.numerology
        self.frame_slider.setRange(0, 0)
        self.slot_slider.setRange(0, 0)
        self.symbol_slider.setRange(0, max(numerology.symbols_per_slot - 1, 0))
        self.stage_slider.setRange(0, max(len(self.stages) - 1, 0))
        if self.stages:
            self._set_current_stage(0)
        else:
            self._clear_view("No PHY stages available.")

    def set_pipeline(self, pipeline: list[dict[str, Any]]) -> None:
        self.result = None
        self.stages = [
            {
                "key": f"pipeline_{index}",
                "section": str(stage.get("section", "Other")),
                "flow_label": str(stage.get("stage", f"Stage {index + 1}")),
                "title": str(stage.get("stage", f"Stage {index + 1}")),
                "description": str(stage.get("description", "")),
                "metrics": {
                    "Domain": str(stage.get("domain", "n/a")),
                    "Preview": str(stage.get("preview_kind", "n/a")),
                },
                "artifacts": [
                    {
                        "name": "Primary view",
                        "kind": str(stage.get("preview_kind", "text")),
                        "payload": stage.get("data", np.array([])),
                        "description": str(stage.get("description", "")),
                    }
                ],
            }
            for index, stage in enumerate(pipeline)
        ]
        self._rebuild_flow()
        self.stage_slider.setRange(0, max(len(self.stages) - 1, 0))
        if self.stages:
            self._set_current_stage(0)
        else:
            self._clear_view("No pipeline data is available.")

    def _rebuild_flow(self) -> None:
        while self.flow_row.count():
            item = self.flow_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.stage_buttons = []
        self.arrow_labels = []

        if not self.stages:
            placeholder = QLabel("Run a single-link simulation to populate the PHY flow.")
            placeholder.setAlignment(Qt.AlignCenter)
            self.flow_row.addWidget(placeholder)
            self.flow_row.addStretch(1)
            return

        for index, stage in enumerate(self.stages):
            button = QPushButton(stage["flow_label"])
            button.setCheckable(True)
            button.setMinimumSize(145, 64)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, idx=index: self._set_current_stage(idx))
            self.stage_buttons.append(button)
            self.flow_row.addWidget(button)
            if index < len(self.stages) - 1:
                arrow = QLabel("→")
                arrow.setAlignment(Qt.AlignCenter)
                arrow.setMinimumWidth(28)
                arrow_font = arrow.font()
                arrow_font.setPointSize(18)
                arrow_font.setBold(True)
                arrow.setFont(arrow_font)
                self.arrow_labels.append(arrow)
                self.flow_row.addWidget(arrow)
        self.flow_row.addStretch(1)
        self._update_flow_styles()

    def _set_current_stage(self, index: int) -> None:
        if not (0 <= index < len(self.stages)):
            return
        self.current_stage_index = index
        if self.stage_slider.value() != index:
            self.stage_slider.blockSignals(True)
            self.stage_slider.setValue(index)
            self.stage_slider.blockSignals(False)
        self.stage_value_label.setText(f"Stage {index + 1}/{len(self.stages)}")
        self._update_flow_styles()
        self._render_stage()

    def _update_flow_styles(self) -> None:
        for index, button in enumerate(self.stage_buttons):
            stage = self.stages[index]
            section = stage.get("section", "Other")
            color = self.SECTION_COLORS.get(section, "#94a3b8")
            if index == self.current_stage_index:
                button.setChecked(True)
                button.setStyleSheet(
                    f"QPushButton {{ background-color: {color}; color: #0f172a; border: 2px solid {color}; "
                    "border-radius: 10px; font-weight: 700; padding: 8px; }}"
                )
            elif index < self.current_stage_index:
                button.setChecked(False)
                button.setStyleSheet(
                    f"QPushButton {{ background-color: #0f172a; color: {color}; border: 1px solid {color}; "
                    "border-radius: 10px; padding: 8px; }}"
                )
            else:
                button.setChecked(False)
                button.setStyleSheet(
                    "QPushButton { background-color: #111827; color: #e5e7eb; border: 1px solid #374151; "
                    "border-radius: 10px; padding: 8px; }"
                )

        for index, arrow in enumerate(self.arrow_labels):
            if index == self.current_stage_index:
                arrow.setStyleSheet("color: #facc15;")
                arrow.setText("➜")
            elif index < self.current_stage_index:
                arrow.setStyleSheet("color: #34d399;")
                arrow.setText("➜")
            else:
                arrow.setStyleSheet("color: #475569;")
                arrow.setText("→")

    def start_playback(self) -> None:
        if not self.stages:
            return
        self.play_timer.start(self.PLAYBACK_INTERVALS_MS[self.speed_combo.currentText()])
        self.play_state_label.setText("Auto-play is running through the PHY stages.")

    def pause_playback(self) -> None:
        self.play_timer.stop()
        self.play_state_label.setText("Step-by-step playback is paused.")

    def reset_playback(self) -> None:
        self.pause_playback()
        if self.stages:
            self._set_current_stage(0)

    def step_forward(self) -> None:
        if not self.stages:
            return
        next_index = min(self.current_stage_index + 1, len(self.stages) - 1)
        self._set_current_stage(next_index)
        self.play_state_label.setText(f"Step mode moved to stage {next_index + 1}/{len(self.stages)}.")

    def step_backward(self) -> None:
        if not self.stages:
            return
        next_index = max(self.current_stage_index - 1, 0)
        self._set_current_stage(next_index)
        self.play_state_label.setText(f"Step mode moved back to stage {next_index + 1}/{len(self.stages)}.")

    def _advance_animation(self) -> None:
        if self.current_stage_index >= len(self.stages) - 1:
            self.pause_playback()
            self.play_state_label.setText("Auto-play reached the CRC check stage.")
            return
        self._set_current_stage(self.current_stage_index + 1)

    def _on_stage_slider_changed(self, value: int) -> None:
        self._set_current_stage(value)

    def _on_symbol_changed(self, value: int) -> None:
        self.symbol_value_label.setText(f"Symbol {value}")
        self._render_current_artifact()

    def _render_stage(self) -> None:
        if not (0 <= self.current_stage_index < len(self.stages)):
            self._clear_view("No PHY stage selected.")
            return
        stage = self.stages[self.current_stage_index]
        self.stage_title.setText(
            f"<b>{stage['section']}</b> | <b>{stage['title']}</b> | Frame 0 / Slot 0 / Symbol {self.symbol_slider.value()}"
        )
        self.stage_summary.setPlainText(stage["description"])
        self._update_metrics(stage["metrics"])
        self.artifact_selector.blockSignals(True)
        self.artifact_selector.clear()
        for artifact in stage["artifacts"]:
            self.artifact_selector.addItem(str(artifact["name"]))
        self.artifact_selector.blockSignals(False)
        if stage["artifacts"]:
            self.artifact_selector.setCurrentIndex(0)
        self._render_current_artifact()

    def _update_metrics(self, metrics: dict[str, Any]) -> None:
        self.metrics_table.setRowCount(len(metrics))
        for row, (key, value) in enumerate(metrics.items()):
            self.metrics_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.metrics_table.setItem(row, 1, QTableWidgetItem(str(value)))

    def _render_current_artifact(self) -> None:
        if not (0 <= self.current_stage_index < len(self.stages)):
            self._clear_view("No artifact is available.")
            return
        stage = self.stages[self.current_stage_index]
        artifacts = stage["artifacts"]
        if not artifacts:
            self._clear_view("This stage does not expose an artifact.")
            return
        artifact = artifacts[self.artifact_selector.currentIndex()]
        self.artifact_caption.setText(str(artifact.get("description", "")))
        self._render_primary_artifact(artifact)
        self._render_secondary_artifact(artifact)
        excerpt = artifact.get("excerpt")
        if excerpt is None:
            excerpt = self._artifact_excerpt(artifact)
        self.data_excerpt.setPlainText(excerpt)

    def _clear_view(self, message: str) -> None:
        self.stage_title.setText(message)
        self.stage_summary.setPlainText(message)
        self.metrics_table.setRowCount(0)
        self.artifact_caption.setText(message)
        self._reset_plot(self.primary_plot, "Artifact preview")
        self._reset_plot(self.secondary_plot, "Frame / slot / symbol view")
        self.data_excerpt.setPlainText(message)

    def _reset_plot(self, plot_widget: pg.PlotWidget, title: str) -> None:
        plot_widget.clear()
        plot_item = plot_widget.getPlotItem()
        plot_item.setTitle(title)
        plot_item.showGrid(x=True, y=True, alpha=0.25)
        plot_item.setLabel("bottom", "")
        plot_item.setLabel("left", "")
        if getattr(plot_item, "legend", None) is not None:
            plot_item.legend.scene().removeItem(plot_item.legend)
            plot_item.legend = None

    def _render_primary_artifact(self, artifact: dict[str, Any]) -> None:
        kind = str(artifact.get("kind", "text"))
        payload = artifact.get("payload")
        title = f"{self.stages[self.current_stage_index]['title']} | {artifact['name']}"
        self._reset_plot(self.primary_plot, title)
        plot_item = self.primary_plot.getPlotItem()
        if kind == "bits":
            self._plot_bits(plot_item, np.asarray(payload))
        elif kind == "waveform":
            self._plot_waveform(plot_item, payload)
        elif kind == "spectrum":
            self._plot_line(plot_item, payload)
        elif kind == "grid":
            self._plot_grid(plot_item, payload)
        elif kind == "line":
            self._plot_line(plot_item, payload)
        elif kind == "multi_line":
            self._plot_multi_line(plot_item, payload)
        elif kind == "constellation_compare":
            self._plot_constellation_compare(plot_item, payload)
        elif kind == "histogram":
            self._plot_histogram(plot_item, payload)
        elif kind == "bar":
            self._plot_bar(plot_item, payload)
        else:
            self._plot_text(plot_item, str(payload))

    def _render_secondary_artifact(self, artifact: dict[str, Any]) -> None:
        kind = str(artifact.get("kind", "text"))
        payload = artifact.get("payload")
        selected_symbol = self.symbol_slider.value()
        title = f"Selected symbol view: {selected_symbol}"
        self._reset_plot(self.secondary_plot, title)
        plot_item = self.secondary_plot.getPlotItem()

        if kind == "waveform":
            waveform = np.asarray(payload.get("waveform", np.array([])), dtype=np.complex128)
            symbol_length = int(payload.get("symbol_length", 0))
            if symbol_length <= 0 or waveform.size == 0:
                self._plot_text(plot_item, "No symbol-level waveform segment is available.")
                return
            start = selected_symbol * symbol_length
            end = min(start + symbol_length, waveform.size)
            segment = waveform[start:end]
            self._plot_waveform(
                plot_item,
                {
                    "waveform": segment,
                    "x_label": "Sample in OFDM symbol",
                    "y_label": "Amplitude",
                },
            )
            return

        if kind == "grid":
            image = np.asarray(payload.get("image", np.array([])))
            if image.ndim != 2 or image.size == 0:
                self._plot_text(plot_item, "No symbol-level grid view is available.")
                return
            selected_symbol = min(selected_symbol, image.shape[0] - 1)
            row = np.asarray(image[selected_symbol], dtype=float)
            self._plot_line(
                plot_item,
                {
                    "x": np.arange(row.size),
                    "y": row,
                    "x_label": "Subcarrier",
                    "y_label": "Selected symbol value",
                },
            )
            return

        if kind == "constellation_compare":
            series = []
            for item in payload.get("series", []):
                symbol_indices = item.get("symbol_indices")
                points = np.asarray(item.get("points", np.array([])))
                if symbol_indices is not None:
                    symbol_indices = np.asarray(symbol_indices)
                    mask = symbol_indices[: points.size] == selected_symbol
                    points = points[: mask.size][mask]
                series.append(
                    {
                        "name": item.get("name", ""),
                        "points": points,
                        "color": item.get("color", "#38bdf8"),
                    }
                )
            self._plot_constellation_compare(plot_item, {"series": series})
            return

        if kind == "bits":
            bits = np.asarray(payload).reshape(-1)
            window = 64
            start = (selected_symbol * window) % max(bits.size, 1)
            segment = bits[start : start + window]
            self._plot_bits(plot_item, segment)
            return

        if kind in {"line", "multi_line", "spectrum", "histogram", "bar"}:
            self._plot_text(plot_item, "The selected symbol mainly affects grid, waveform, and constellation artifacts.")
            return

        self._plot_text(plot_item, "No symbol-level artifact is defined for this stage.")

    def _build_stage_models(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        tx = result["tx"]
        rx = result["rx"]
        config = result["config"]
        channel_state = result["channel_state"]
        tx_meta = tx.metadata
        coding_meta = tx_meta.coding_metadata
        numerology = tx_meta.numerology
        positions = tx_meta.mapping.positions
        payload_with_crc = attach_crc(tx_meta.payload_bits, coding_meta.crc_type)
        mother_bits = self._mother_bits(tx_meta)
        allocation_map, dmrs_mask = self._allocation_maps(result)
        tx_spectrum = self._spectrum_payload(tx.waveform, tx_meta.sample_rate)
        rx_spectrum = self._spectrum_payload(result["rx_waveform"], tx_meta.sample_rate)
        channel_waveform = result.get("channel_output_waveform", result["rx_waveform"])
        corrected_waveform = rx.corrected_waveform
        timing_trace = self._timing_metric_payload(
            result["rx_waveform"],
            fft_size=numerology.fft_size,
            cp_length=numerology.cp_length,
            search_window=int(config.get("receiver", {}).get("timing_search_window", 2 * numerology.cp_length)),
        )
        cfo_trace = self._cfo_trace_payload(
            result["rx_waveform"],
            fft_size=numerology.fft_size,
            cp_length=numerology.cp_length,
        )
        avg_channel = np.mean(np.abs(rx.channel_estimate), axis=0)
        equalizer_gain = 1.0 / np.maximum(avg_channel, 1e-6)
        llr_histogram = self._histogram_payload(rx.llrs)
        bit_error_mask = self._bit_error_mask(tx_meta.payload_bits, rx.recovered_bits)
        kpis = rx.kpis.as_dict()
        reference_symbols = tx_meta.tx_symbols
        pre_eq_symbols = rx.rx_symbols
        post_eq_symbols = rx.equalized_symbols
        mapping_table = self._mapping_table_text(tx_meta.mapper)
        code_rate = tx_meta.payload_bits.size / max(coding_meta.rate_matched_length, 1)
        code_stage = "Polar-like control coder" if tx_meta.channel_type in {"control", "pdcch", "pbch"} else "LDPC-inspired coder"

        return self._stage_definitions(
            result=result,
            payload_with_crc=payload_with_crc,
            mother_bits=mother_bits,
            allocation_map=allocation_map,
            dmrs_mask=dmrs_mask,
            tx_spectrum=tx_spectrum,
            rx_spectrum=rx_spectrum,
            channel_waveform=channel_waveform,
            corrected_waveform=corrected_waveform,
            timing_trace=timing_trace,
            cfo_trace=cfo_trace,
            avg_channel=avg_channel,
            equalizer_gain=equalizer_gain,
            llr_histogram=llr_histogram,
            bit_error_mask=bit_error_mask,
            kpis=kpis,
            reference_symbols=reference_symbols,
            pre_eq_symbols=pre_eq_symbols,
            post_eq_symbols=post_eq_symbols,
            mapping_table=mapping_table,
            code_rate=code_rate,
            code_stage=code_stage,
            positions=positions,
        )

    def _stage_definitions(
        self,
        *,
        result: dict[str, Any],
        payload_with_crc: np.ndarray,
        mother_bits: np.ndarray,
        allocation_map: np.ndarray,
        dmrs_mask: np.ndarray,
        tx_spectrum: dict[str, Any],
        rx_spectrum: dict[str, Any],
        channel_waveform: np.ndarray,
        corrected_waveform: np.ndarray,
        timing_trace: dict[str, Any],
        cfo_trace: dict[str, Any],
        avg_channel: np.ndarray,
        equalizer_gain: np.ndarray,
        llr_histogram: dict[str, Any],
        bit_error_mask: np.ndarray,
        kpis: dict[str, Any],
        reference_symbols: np.ndarray,
        pre_eq_symbols: np.ndarray,
        post_eq_symbols: np.ndarray,
        mapping_table: str,
        code_rate: float,
        code_stage: str,
        positions: np.ndarray,
    ) -> list[dict[str, Any]]:
        tx = result["tx"]
        rx = result["rx"]
        config = result["config"]
        channel_state = result["channel_state"]
        tx_meta = tx.metadata
        coding_meta = tx_meta.coding_metadata
        numerology = tx_meta.numerology

        return [
            {
                "key": "bits",
                "section": "TX",
                "flow_label": "Bits",
                "title": "Bits",
                "description": "Original transport block or control payload before any protection or scrambling.",
                "metrics": {"Bitstream length": tx_meta.payload_bits.size, "Channel type": tx_meta.channel_type, "Frame": 0, "Slot": 0},
                "artifacts": [{"name": "Payload bits", "kind": "bits", "payload": tx_meta.payload_bits, "description": "Payload bits entering the PHY chain."}],
            },
            {
                "key": "crc_attach",
                "section": "TX",
                "flow_label": "CRC",
                "title": "CRC Attachment",
                "description": "CRC is appended to the payload before channel coding to enable block-level error detection.",
                "metrics": {
                    "CRC type": coding_meta.crc_type,
                    "Payload bits": tx_meta.payload_bits.size,
                    "Payload + CRC": payload_with_crc.size,
                    "CRC bits added": payload_with_crc.size - tx_meta.payload_bits.size,
                },
                "artifacts": [{"name": "Payload + CRC", "kind": "bits", "payload": payload_with_crc, "description": "Bitstream after CRC attachment."}],
            },
            {
                "key": "coding",
                "section": "TX",
                "flow_label": "Coding",
                "title": "Channel Coding",
                "description": "Simplified NR-inspired channel coding expands the protected bitstream into a mother codeword.",
                "metrics": {
                    "Coder": code_stage,
                    "Mother length": coding_meta.mother_length,
                    "Payload + CRC": payload_with_crc.size,
                    "Repetition factor": coding_meta.repetition_factor,
                },
                "artifacts": [{"name": "Mother codeword", "kind": "bits", "payload": mother_bits, "description": "Mother codeword before rate matching."}],
            },
            {
                "key": "rate_matching",
                "section": "TX",
                "flow_label": "Rate Match",
                "title": "Rate Matching",
                "description": "Rate matching adapts the mother codeword to the exact RE capacity offered by the scheduled resource allocation.",
                "metrics": {
                    "Rate-matched length": coding_meta.rate_matched_length,
                    "Mother length": coding_meta.mother_length,
                    "Redundancy version": coding_meta.redundancy_version,
                    "Effective code rate": f"{code_rate:.3f}",
                },
                "artifacts": [{"name": "Rate-matched bits", "kind": "bits", "payload": tx_meta.coded_bits, "description": "Bitstream after rate matching."}],
            },
            {
                "key": "scrambling",
                "section": "TX",
                "flow_label": "Scramble",
                "title": "Scrambling",
                "description": "Pseudo-random scrambling whitens the code bits and avoids deterministic spectral structure.",
                "metrics": {
                    "Scrambled length": tx_meta.scrambled_bits.size,
                    "Sequence length": tx_meta.scrambling_sequence.size,
                    "NID": int(config.get("scrambling", {}).get("nid", 1)),
                    "RNTI": int(config.get("scrambling", {}).get("rnti", 0x1234)),
                },
                "artifacts": [
                    {"name": "Scrambled bits", "kind": "bits", "payload": tx_meta.scrambled_bits, "description": "Scrambled bitstream ready for QAM mapping."},
                    {"name": "Scrambling sequence", "kind": "bits", "payload": tx_meta.scrambling_sequence, "description": "Pseudo-random scrambling sequence applied to the code bits."},
                ],
            },
            {
                "key": "qam_mapping",
                "section": "TX",
                "flow_label": "QAM",
                "title": "QAM Mapping",
                "description": "Bits are grouped and mapped onto a Gray-labeled QPSK/QAM constellation. The stage also exposes how symbols look before and after the channel.",
                "metrics": {
                    "Modulation": tx_meta.modulation,
                    "Bits / symbol": tx_meta.mapper.bits_per_symbol,
                    "Mapped symbols": tx_meta.tx_symbols.size,
                    "Constellation order": 2 ** tx_meta.mapper.bits_per_symbol,
                },
                "artifacts": [
                    {
                        "name": "Mapping constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {"name": "Mapping table", "points": tx_meta.mapper.constellation, "color": "#f94144"},
                                {"name": "TX symbols", "points": tx_meta.tx_symbols, "color": "#38bdf8", "symbol_indices": positions[: tx_meta.tx_symbols.size, 0]},
                            ]
                        },
                        "description": "Constellation table and actual TX symbols before the channel.",
                    },
                    {
                        "name": "Before/after channel constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {"name": "Reference", "points": reference_symbols, "color": "#f94144", "symbol_indices": positions[: reference_symbols.size, 0]},
                                {"name": "Pre-EQ", "points": pre_eq_symbols, "color": "#ffffff", "symbol_indices": positions[: pre_eq_symbols.size, 0]},
                                {"name": "Post-EQ", "points": post_eq_symbols, "color": "#38bdf8", "symbol_indices": positions[: post_eq_symbols.size, 0]},
                            ]
                        },
                        "description": "Constellation before channel, after channel extraction, and after equalization.",
                    },
                    {"name": "Mapping table", "kind": "text", "payload": mapping_table, "description": "Gray-labeled mapping table for the selected modulation order."},
                ],
            },
            {
                "key": "resource_grid_dmrs",
                "section": "TX",
                "flow_label": "Grid + DMRS",
                "title": "Resource Grid + DMRS",
                "description": "Mapped symbols are placed onto the NR-like resource grid. DMRS is inserted on configured OFDM symbols for channel estimation.",
                "metrics": {
                    "Grid shape": f"{tx_meta.tx_grid.shape[0]} x {tx_meta.tx_grid.shape[1]}",
                    "Control RE count": int(np.sum(allocation_map == 1)),
                    "Data RE count": int(np.sum(allocation_map == 2)),
                    "DMRS RE count": int(np.sum(allocation_map == 3)),
                },
                "artifacts": [
                    {"name": "Allocation map", "kind": "grid", "payload": {"image": allocation_map, "lookup": "allocation", "levels": (0.0, 3.0)}, "description": "Heatmap showing control region, payload REs, and DMRS placement."},
                    {"name": "TX grid magnitude", "kind": "grid", "payload": {"image": np.abs(tx_meta.tx_grid), "lookup": "viridis"}, "description": "Magnitude of the populated resource grid after DMRS insertion."},
                    {"name": "DMRS mask", "kind": "grid", "payload": {"image": dmrs_mask, "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of DMRS RE locations."},
                ],
            },
            {
                "key": "ofdm_ifft_cp",
                "section": "TX",
                "flow_label": "OFDM / IFFT",
                "title": "OFDM / IFFT + CP",
                "description": "The populated grid is converted to a time-domain waveform through IFFT and cyclic-prefix insertion.",
                "metrics": {
                    "FFT size": numerology.fft_size,
                    "CP length": numerology.cp_length,
                    "Sample rate (Hz)": f"{tx_meta.sample_rate:.0f}",
                    "Waveform samples": tx.waveform.size,
                },
                "artifacts": [
                    {"name": "TX waveform", "kind": "waveform", "payload": {"waveform": tx.waveform, "symbol_length": numerology.fft_size + numerology.cp_length, "x_label": "Sample", "y_label": "Amplitude"}, "description": "Time-domain transmit waveform after OFDM modulation."},
                    {"name": "TX spectrum", "kind": "spectrum", "payload": tx_spectrum, "description": "Power spectral density estimate of the OFDM transmit waveform."},
                ],
            },
            {
                "key": "channel_impairments",
                "section": "Channel",
                "flow_label": "Channel",
                "title": "Channel / Impairments",
                "description": "The waveform traverses impairments, fading, path loss, Doppler, and AWGN before it reaches the UE receiver.",
                "metrics": {
                    "Model": channel_state.get("fading_model", config.get("channel", {}).get("model", "awgn")),
                    "Profile": config.get("channel", {}).get("profile", "static_near"),
                    "Doppler (Hz)": config.get("channel", {}).get("doppler_hz", 0.0),
                    "CFO (Hz)": channel_state.get("cfo_hz", 0.0),
                    "STO (samples)": channel_state.get("sto_samples", 0),
                    "Path loss (dB)": config.get("channel", {}).get("path_loss_db", 0.0),
                },
                "artifacts": [
                    {"name": "Channel output waveform", "kind": "waveform", "payload": {"waveform": channel_waveform, "symbol_length": numerology.fft_size + numerology.cp_length, "x_label": "Sample", "y_label": "Amplitude"}, "description": "Waveform after channel and impairment processing."},
                    {"name": "Impulse response", "kind": "line", "payload": {"x": np.arange(np.asarray(channel_state.get("impulse_response", np.array([1.0]))).size), "y": np.abs(np.asarray(channel_state.get("impulse_response", np.array([1.0])))), "x_label": "Tap", "y_label": "Magnitude"}, "description": "Discrete-time channel impulse response used by the simulator."},
                    {"name": "Frequency response", "kind": "line", "payload": {"x": np.arange(avg_channel.size), "y": 20.0 * np.log10(avg_channel + 1e-9), "x_label": "Subcarrier", "y_label": "Magnitude (dB)"}, "description": "Average channel frequency response magnitude across the grid."},
                ],
            },
            {
                "key": "sync",
                "section": "RX",
                "flow_label": "Sync",
                "title": "Synchronization",
                "description": "The receiver searches for timing alignment and estimates the CFO before FFT demodulation.",
                "metrics": {
                    "Timing estimate": rx.timing_offset,
                    "Timing error": f"{rx.kpis.synchronization_error_samples:.3f}",
                    "Configured CFO (Hz)": channel_state.get("cfo_hz", 0.0),
                    "Estimated CFO (Hz)": f"{rx.cfo_estimate_hz:.3f}",
                },
                "artifacts": [
                    {"name": "Timing correlation", "kind": "line", "payload": timing_trace, "description": "Correlation metric used to detect the best OFDM symbol boundary."},
                    {"name": "CFO estimation trace", "kind": "multi_line", "payload": cfo_trace, "description": "Per-symbol CFO phase and correlation magnitude derived from the cyclic prefix."},
                    {"name": "Corrected waveform", "kind": "waveform", "payload": {"waveform": corrected_waveform, "symbol_length": numerology.fft_size + numerology.cp_length, "x_label": "Sample", "y_label": "Amplitude"}, "description": "Waveform after timing alignment and CFO correction."},
                ],
            },
            {
                "key": "fft",
                "section": "RX",
                "flow_label": "FFT",
                "title": "FFT / OFDM Demodulation",
                "description": "The corrected waveform is segmented symbol by symbol, CP is removed, and FFT reconstructs the received grid.",
                "metrics": {
                    "RX grid shape": f"{rx.rx_grid.shape[0]} x {rx.rx_grid.shape[1]}",
                    "Symbols / slot": numerology.symbols_per_slot,
                    "Active subcarriers": numerology.active_subcarriers,
                    "RX spectrum bins": rx_spectrum["x"].size,
                },
                "artifacts": [
                    {"name": "RX grid magnitude", "kind": "grid", "payload": {"image": np.abs(rx.rx_grid), "lookup": "magma"}, "description": "Magnitude of the received resource grid after FFT."},
                    {"name": "RX spectrum", "kind": "spectrum", "payload": rx_spectrum, "description": "Spectrum of the received waveform before equalization."},
                ],
            },
            {
                "key": "channel_estimation",
                "section": "RX",
                "flow_label": "Ch. Est.",
                "title": "Channel Estimation",
                "description": "DMRS observations are turned into a full-grid channel estimate used by the equalizer.",
                "metrics": {
                    "DMRS RE count": int(tx_meta.dmrs["positions"].shape[0]),
                    "Channel-estimation MSE": f"{rx.kpis.channel_estimation_mse:.4g}",
                    "Perfect CE": bool(config.get("receiver", {}).get("perfect_channel_estimation", False)),
                    "Grid shape": f"{rx.channel_estimate.shape[0]} x {rx.channel_estimate.shape[1]}",
                },
                "artifacts": [
                    {"name": "Estimated channel grid", "kind": "grid", "payload": {"image": np.abs(rx.channel_estimate), "lookup": "cividis"}, "description": "Full-grid channel estimate magnitude."},
                    {"name": "Average response", "kind": "line", "payload": {"x": np.arange(avg_channel.size), "y": 20.0 * np.log10(avg_channel + 1e-9), "x_label": "Subcarrier", "y_label": "Magnitude (dB)"}, "description": "Average magnitude of the estimated channel response across OFDM symbols."},
                ],
            },
            {
                "key": "equalization",
                "section": "RX",
                "flow_label": "Equalize",
                "title": "Equalization",
                "description": "Estimated channel coefficients are used to compensate amplitude and phase distortion on scheduled REs.",
                "metrics": {
                    "Equalizer": config.get("receiver", {}).get("equalizer", "mmse"),
                    "Noise variance": f"{channel_state.get('noise_variance', 0.0):.4g}",
                    "Equalized symbols": post_eq_symbols.size,
                    "EVM": f"{rx.kpis.evm:.4g}",
                },
                "artifacts": [
                    {"name": "Pre/post equalization constellation", "kind": "constellation_compare", "payload": {"series": [{"name": "Reference", "points": reference_symbols, "color": "#f94144", "symbol_indices": positions[: reference_symbols.size, 0]}, {"name": "Pre-EQ", "points": pre_eq_symbols, "color": "#ffffff", "symbol_indices": positions[: pre_eq_symbols.size, 0]}, {"name": "Post-EQ", "points": post_eq_symbols, "color": "#38bdf8", "symbol_indices": positions[: post_eq_symbols.size, 0]}]}, "description": "Constellation before equalization and after equalization."},
                    {"name": "Equalizer gain", "kind": "line", "payload": {"x": np.arange(equalizer_gain.size), "y": 20.0 * np.log10(equalizer_gain + 1e-9), "x_label": "Subcarrier", "y_label": "Gain (dB)"}, "description": "Approximate equalizer gain magnitude derived from the estimated channel response."},
                ],
            },
            {
                "key": "demapping",
                "section": "RX",
                "flow_label": "Demap",
                "title": "Soft Demapping",
                "description": "Equalized symbols are converted to soft bit metrics (LLRs) for the channel decoder.",
                "metrics": {
                    "LLR count": rx.llrs.size,
                    "Mean |LLR|": f"{float(np.mean(np.abs(rx.llrs))):.4g}",
                    "Min LLR": f"{float(np.min(rx.llrs)):.4g}",
                    "Max LLR": f"{float(np.max(rx.llrs)):.4g}",
                },
                "artifacts": [
                    {"name": "LLR trace", "kind": "line", "payload": {"x": np.arange(min(rx.llrs.size, 256)), "y": rx.llrs[:256], "x_label": "LLR index", "y_label": "LLR"}, "description": "First LLR values emitted by the soft demapper."},
                    {"name": "LLR histogram", "kind": "histogram", "payload": llr_histogram, "description": "Histogram of soft decisions delivered to the decoder."},
                ],
            },
            {
                "key": "decoding",
                "section": "RX",
                "flow_label": "Decode",
                "title": "Decoding",
                "description": "The channel decoder reconstructs the protected payload bits from the descrambled LLR stream.",
                "metrics": {
                    "Recovered bits": rx.recovered_bits.size,
                    "Bit errors": int(np.sum(bit_error_mask)),
                    "BER": f"{rx.kpis.ber:.4g}",
                    "BLER": f"{rx.kpis.bler:.4g}",
                },
                "artifacts": [
                    {"name": "Recovered bits", "kind": "bits", "payload": rx.recovered_bits, "description": "Recovered payload bits after channel decoding."},
                    {"name": "Bit error mask", "kind": "bits", "payload": bit_error_mask, "description": "Error mask against the transmitted payload bits. A '1' marks a bit error."},
                ],
            },
            {
                "key": "crc_check",
                "section": "RX",
                "flow_label": "CRC Check",
                "title": "CRC Check",
                "description": "The recovered payload is validated by CRC, and link KPIs are consolidated here.",
                "metrics": {
                    "CRC status": "PASS" if rx.crc_ok else "FAIL",
                    "Estimated SNR (dB)": f"{rx.kpis.estimated_snr_db:.4g}",
                    "Throughput (Mbps)": f"{rx.kpis.throughput_bps / 1e6:.4g}",
                    "Spectral efficiency": f"{rx.kpis.spectral_efficiency_bps_hz:.4g}",
                },
                "artifacts": [
                    {"name": "KPI summary", "kind": "bar", "payload": {"categories": ["BER", "BLER", "EVM", "Thr (Mbps)"], "values": [float(kpis["ber"]), float(kpis["bler"]), float(kpis["evm"]), float(kpis["throughput_bps"]) / 1e6]}, "description": "Final KPI snapshot after CRC validation."},
                    {"name": "CRC decision", "kind": "text", "payload": f"CRC status: {'PASS' if rx.crc_ok else 'FAIL'}\nCRC type: {coding_meta.crc_type}", "description": "Final CRC decision for the received block."},
                ],
            },
        ]

    @staticmethod
    def _mother_bits(tx_meta) -> np.ndarray:
        coding_meta = tx_meta.coding_metadata
        payload_with_crc = attach_crc(tx_meta.payload_bits, coding_meta.crc_type)
        if tx_meta.channel_type in {"control", "pdcch", "pbch"}:
            polar_length = int(coding_meta.polar_length or payload_with_crc.size)
            info_positions = np.asarray(coding_meta.info_positions)
            u = np.zeros(polar_length, dtype=np.uint8)
            if info_positions.size:
                u[info_positions] = payload_with_crc
            return _polar_transform(u)
        mother = np.tile(payload_with_crc, int(coding_meta.repetition_factor))
        if coding_meta.interleaver is not None:
            mother = mother[np.asarray(coding_meta.interleaver)]
        return mother.astype(np.uint8)

    @staticmethod
    def _allocation_maps(result: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        tx_meta = result["tx"].metadata
        numerology = tx_meta.numerology
        allocation_map = np.zeros((numerology.symbols_per_slot, numerology.active_subcarriers), dtype=np.float32)
        allocation = tx_meta.allocation
        for symbol in allocation.pdcch_symbols:
            allocation_map[symbol, : allocation.control_subcarriers] = 1.0
        positions = tx_meta.mapping.positions
        if positions.size:
            allocation_map[positions[:, 0], positions[:, 1]] = 2.0
        dmrs_positions = tx_meta.dmrs["positions"]
        dmrs_mask = np.zeros_like(allocation_map)
        if dmrs_positions.size:
            allocation_map[dmrs_positions[:, 0], dmrs_positions[:, 1]] = 3.0
            dmrs_mask[dmrs_positions[:, 0], dmrs_positions[:, 1]] = 1.0
        return allocation_map, dmrs_mask

    @staticmethod
    def _spectrum_payload(waveform: np.ndarray, sample_rate: float, nfft: int = 4096) -> dict[str, Any]:
        view = np.asarray(waveform).reshape(-1)[:nfft]
        spectrum = np.zeros(nfft, dtype=np.complex128) if view.size == 0 else np.fft.fftshift(np.fft.fft(view, n=nfft))
        freqs = np.linspace(-sample_rate / 2.0, sample_rate / 2.0, spectrum.size) / 1e6
        return {"x": freqs, "y": 20.0 * np.log10(np.abs(spectrum) + 1e-9), "x_label": "Frequency (MHz)", "y_label": "Magnitude (dB)"}

    @staticmethod
    def _timing_metric_payload(waveform: np.ndarray, fft_size: int, cp_length: int, search_window: int) -> dict[str, Any]:
        symbol_length = fft_size + cp_length
        offsets = []
        metrics = []
        for offset in range(max(search_window, 1)):
            if offset + symbol_length >= waveform.size:
                break
            metric = 0.0
            valid_symbols = 0
            for symbol_index in range(4):
                start = offset + symbol_index * symbol_length
                if start + symbol_length > waveform.size:
                    break
                cp = waveform[start : start + cp_length]
                tail = waveform[start + fft_size : start + fft_size + cp_length]
                numerator = np.abs(np.vdot(cp, tail))
                denominator = np.sqrt(np.vdot(cp, cp).real * np.vdot(tail, tail).real) + 1e-12
                metric += numerator / denominator
                valid_symbols += 1
            if valid_symbols:
                metric /= valid_symbols
            offsets.append(offset)
            metrics.append(metric)
        return {"x": np.asarray(offsets), "y": np.asarray(metrics), "x_label": "Timing offset (samples)", "y_label": "Correlation metric"}

    @staticmethod
    def _cfo_trace_payload(waveform: np.ndarray, fft_size: int, cp_length: int, symbols_to_average: int = 6) -> dict[str, Any]:
        symbol_length = fft_size + cp_length
        phases = []
        magnitudes = []
        symbol_indices = []
        for symbol_index in range(symbols_to_average):
            start = symbol_index * symbol_length
            end = start + symbol_length
            if end > waveform.size:
                break
            cp = waveform[start : start + cp_length]
            tail = waveform[start + fft_size : start + fft_size + cp_length]
            correlation = np.vdot(cp, tail)
            phases.append(np.angle(correlation))
            magnitudes.append(np.abs(correlation))
            symbol_indices.append(symbol_index)
        return {
            "series": [
                {"name": "Phase", "x": np.asarray(symbol_indices), "y": np.asarray(phases), "color": "#38bdf8"},
                {"name": "Correlation magnitude", "x": np.asarray(symbol_indices), "y": np.asarray(magnitudes), "color": "#f59e0b"},
            ],
            "x_label": "OFDM symbol",
            "y_label": "Value",
        }

    @staticmethod
    def _histogram_payload(values: np.ndarray, bins: int = 32) -> dict[str, Any]:
        histogram, edges = np.histogram(np.asarray(values).reshape(-1), bins=bins)
        centers = 0.5 * (edges[:-1] + edges[1:])
        return {"x": centers, "y": histogram, "x_label": "Value", "y_label": "Count"}

    @staticmethod
    def _bit_error_mask(reference_bits: np.ndarray, recovered_bits: np.ndarray) -> np.ndarray:
        count = min(reference_bits.size, recovered_bits.size)
        mask = np.zeros(max(reference_bits.size, recovered_bits.size), dtype=np.uint8)
        mask[:count] = (reference_bits[:count] != recovered_bits[:count]).astype(np.uint8)
        if reference_bits.size != recovered_bits.size:
            mask[count:] = 1
        return mask

    @staticmethod
    def _mapping_table_text(mapper) -> str:
        lines = ["Bits -> Constellation point"]
        for label, symbol in zip(mapper.labels, mapper.constellation):
            bits = "".join(str(int(bit)) for bit in label.tolist())
            lines.append(f"{bits} -> {symbol.real:.4f}{symbol.imag:+.4f}j")
        return "\n".join(lines)

    @staticmethod
    def _artifact_excerpt(artifact: dict[str, Any]) -> str:
        payload = artifact.get("payload")
        if artifact.get("kind") == "text":
            return str(payload)
        if isinstance(payload, dict):
            summary_lines = [f"Artifact: {artifact.get('name', 'n/a')}"]
            for key, value in payload.items():
                if isinstance(value, np.ndarray):
                    summary_lines.append(f"{key}: shape={value.shape}, dtype={value.dtype}")
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    summary_lines.append(f"{key}: {len(value)} series")
                else:
                    summary_lines.append(f"{key}: {value}")
            return "\n".join(summary_lines)
        array = np.asarray(payload)
        if array.ndim == 0:
            return str(array.item())
        flat = array.reshape(-1)[:96]
        if np.iscomplexobj(flat):
            body = " ".join(f"{value.real:.4g}{value.imag:+.4g}j" for value in flat)
        elif np.issubdtype(flat.dtype, np.integer):
            body = " ".join(str(int(value)) for value in flat)
        else:
            body = " ".join(f"{float(value):.4g}" for value in flat)
        if array.size > flat.size:
            body += " ..."
        return body

    @staticmethod
    def _plot_bits(plot_item: pg.PlotItem, bits: np.ndarray) -> None:
        view = np.asarray(bits).reshape(-1)[:256].astype(float)
        if view.size == 0:
            plot_item.addItem(pg.TextItem("No bits", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        x_axis = np.arange(view.size + 1, dtype=float) - 0.5
        plot_item.setLabel("bottom", "Bit index")
        plot_item.setLabel("left", "Bit value")
        plot_item.plot(x_axis, view, pen=pg.mkPen("#38bdf8", width=1.4), stepMode="center")
        plot_item.setYRange(-0.2, 1.2, padding=0.0)

    @staticmethod
    def _plot_waveform(plot_item: pg.PlotItem, payload: dict[str, Any]) -> None:
        waveform = np.asarray(payload.get("waveform", np.array([])), dtype=np.complex128).reshape(-1)[:2048]
        if waveform.size == 0:
            plot_item.addItem(pg.TextItem("No waveform", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        x_axis = np.arange(waveform.size)
        plot_item.setLabel("bottom", payload.get("x_label", "Sample"))
        plot_item.setLabel("left", payload.get("y_label", "Amplitude"))
        plot_item.plot(x_axis, waveform.real, pen=pg.mkPen("#60a5fa", width=1.2))
        plot_item.plot(x_axis, waveform.imag, pen=pg.mkPen("#f59e0b", width=1.2))

    @staticmethod
    def _plot_line(plot_item: pg.PlotItem, payload: dict[str, Any]) -> None:
        x_axis = np.asarray(payload.get("x", np.arange(len(payload.get("y", [])))))
        y_axis = np.asarray(payload.get("y", np.array([])))
        if y_axis.size == 0:
            plot_item.addItem(pg.TextItem("No line data", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        plot_item.setLabel("bottom", payload.get("x_label", "x"))
        plot_item.setLabel("left", payload.get("y_label", "y"))
        plot_item.plot(x_axis, y_axis, pen=pg.mkPen("#38bdf8", width=1.5))

    @staticmethod
    def _plot_multi_line(plot_item: pg.PlotItem, payload: dict[str, Any]) -> None:
        series = payload.get("series", [])
        if not series:
            plot_item.addItem(pg.TextItem("No line series", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        plot_item.setLabel("bottom", payload.get("x_label", "x"))
        plot_item.setLabel("left", payload.get("y_label", "y"))
        for item in series:
            plot_item.plot(
                np.asarray(item.get("x", np.arange(len(item.get("y", []))))),
                np.asarray(item.get("y", np.array([]))),
                pen=pg.mkPen(item.get("color", "#38bdf8"), width=1.4),
            )

    @staticmethod
    def _plot_grid(plot_item: pg.PlotItem, payload: dict[str, Any]) -> None:
        image = np.asarray(payload.get("image", np.array([])), dtype=float)
        if image.ndim != 2 or image.size == 0:
            plot_item.addItem(pg.TextItem("No grid data", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        image_item = pg.ImageItem(axisOrder="row-major")
        image_item.setImage(image, autoLevels="levels" not in payload)
        lookup = payload.get("lookup", "viridis")
        if lookup == "allocation":
            lut = np.array(
                [
                    [15, 23, 42, 255],
                    [251, 191, 36, 255],
                    [56, 189, 248, 255],
                    [244, 114, 182, 255],
                ],
                dtype=np.ubyte,
            )
            image_item.setLookupTable(lut)
        else:
            image_item.setLookupTable(pg.colormap.get(str(lookup)).getLookupTable())
        if "levels" in payload:
            image_item.setLevels(payload["levels"])
        height, width = image.shape
        image_item.setRect(pg.QtCore.QRectF(0.0, 0.0, float(width), float(height)))
        plot_item.addItem(image_item)
        plot_item.setLabel("bottom", "Subcarrier")
        plot_item.setLabel("left", "OFDM symbol")
        plot_item.setXRange(0.0, float(width), padding=0.0)
        plot_item.setYRange(0.0, float(height), padding=0.0)

    @staticmethod
    def _plot_constellation_compare(plot_item: pg.PlotItem, payload: dict[str, Any]) -> None:
        series = payload.get("series", [])
        if not series:
            plot_item.addItem(pg.TextItem("No constellation data", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        plot_item.setLabel("bottom", "In-Phase")
        plot_item.setLabel("left", "Quadrature")
        plot_item.setAspectLocked(True)
        max_symbol = 1.0
        for item in series:
            points = np.asarray(item.get("points", np.array([])), dtype=np.complex128).reshape(-1)[:1024]
            if points.size == 0:
                continue
            color = pg.mkColor(item.get("color", "#38bdf8"))
            scatter = pg.ScatterPlotItem(
                x=points.real,
                y=points.imag,
                pen=pg.mkPen(color, width=0.9),
                brush=pg.mkBrush(color.red(), color.green(), color.blue(), 90),
                size=6,
            )
            plot_item.addItem(scatter)
            max_symbol = max(max_symbol, float(np.max(np.abs(points))))
        plot_item.setXRange(-1.2 * max_symbol, 1.2 * max_symbol, padding=0.0)
        plot_item.setYRange(-1.2 * max_symbol, 1.2 * max_symbol, padding=0.0)

    @staticmethod
    def _plot_histogram(plot_item: pg.PlotItem, payload: dict[str, Any]) -> None:
        x_axis = np.asarray(payload.get("x", np.array([])))
        y_axis = np.asarray(payload.get("y", np.array([])))
        if x_axis.size == 0 or y_axis.size == 0:
            plot_item.addItem(pg.TextItem("No histogram data", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        width = float(np.mean(np.diff(x_axis))) if x_axis.size > 1 else 1.0
        plot_item.setLabel("bottom", payload.get("x_label", "Value"))
        plot_item.setLabel("left", payload.get("y_label", "Count"))
        plot_item.addItem(pg.BarGraphItem(x=x_axis, height=y_axis, width=0.9 * width, brush="#38bdf8"))

    @staticmethod
    def _plot_bar(plot_item: pg.PlotItem, payload: dict[str, Any]) -> None:
        categories = payload.get("categories", [])
        values = np.asarray(payload.get("values", np.array([])), dtype=float)
        if not categories or values.size == 0:
            plot_item.addItem(pg.TextItem("No KPI bar data", color="#d8dee9", anchor=(0.5, 0.5)))
            return
        x_positions = np.arange(values.size)
        plot_item.setLabel("bottom", "Metric")
        plot_item.setLabel("left", "Value")
        plot_item.addItem(pg.BarGraphItem(x=x_positions, height=values, width=0.65, brush="#34d399"))
        ticks = [(float(index), str(label)) for index, label in enumerate(categories)]
        plot_item.getAxis("bottom").setTicks([ticks])

    @staticmethod
    def _plot_text(plot_item: pg.PlotItem, text: str) -> None:
        text_item = pg.TextItem(text, color="#d8dee9", anchor=(0.5, 0.5))
        plot_item.addItem(text_item)
        text_item.setPos(0.5, 0.5)
