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

from phy.artifacts import normalize_pipeline_stage, pipeline_stage, stage_artifact
from phy.coding import _polar_transform, attach_crc
from phy.layer_mapping import expand_positions_for_layers


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
        self.active_result: dict[str, Any] | None = None
        self.stages: list[dict[str, Any]] = []
        self.slot_history: list[dict[str, Any]] = []
        self.current_slot_record: dict[str, Any] | None = None
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
            "Bits -> TB CRC -> Segmentation + CB CRC -> Coding -> Rate Matching -> Scrambling -> QAM Mapping -> Codeword Split -> Layer Mapping -> Precoding / Port Mapping -> (Optional UL Transform Precoding) -> Resource Grid + DMRS -> "
            "OFDM/IFFT + CP -> Channel/Impairments -> Sync -> FFT -> Channel Estimation -> Equalization -> "
            "(Optional UL Inverse Transform) -> Demapping -> Decoding -> CRC Check<br>"
            "PRACH baseline: Preamble ID -> Zadoff-Chu preamble -> PRACH occasion -> OFDM -> Channel -> Correlation detector -> Preamble decision"
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
        self.frame_slider.valueChanged.connect(self._on_frame_changed)
        self.slot_slider.valueChanged.connect(self._on_slot_changed)
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
        self.active_result = None
        self.slot_history = self._extract_slot_history(result)
        if not self.slot_history:
            self.stages = []
            self._rebuild_flow()
            self._clear_view("No PHY stages available.")
            return
        frame_indices = [int(entry["frame_index"]) for entry in self.slot_history]
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(min(frame_indices), max(frame_indices))
        self.frame_slider.setValue(int(self.slot_history[0]["frame_index"]))
        self.frame_slider.blockSignals(False)
        self._select_frame(
            frame_index=int(self.slot_history[0]["frame_index"]),
            requested_slot=int(self.slot_history[0]["slot_index"]),
            preserve_stage=False,
        )

    def set_pipeline(self, pipeline: list[dict[str, Any]]) -> None:
        self.result = None
        self.active_result = None
        self.slot_history = []
        self.current_slot_record = None
        self.stages = [
            normalize_pipeline_stage(
                pipeline_stage(
                    key=f"pipeline_{index}",
                    section=str(stage.get("section", "Other")),
                    flow_label=str(stage.get("stage", f"Stage {index + 1}")),
                    title=str(stage.get("stage", f"Stage {index + 1}")),
                    description=str(stage.get("description", "")),
                    metrics={
                        "Domain": str(stage.get("domain", "n/a")),
                        "Artifact type": str(stage.get("artifact_type", stage.get("preview_kind", "n/a"))),
                        "Input shape": stage.get("input_shape", "n/a"),
                        "Output shape": stage.get("output_shape", "n/a"),
                    },
                    artifacts=[
                        stage_artifact(
                            name="Primary view",
                            artifact_type=str(stage.get("artifact_type", stage.get("preview_kind", "text"))),
                            payload=stage.get("data", np.array([])),
                            description=str(stage.get("description", "")),
                            input_shape=stage.get("input_shape"),
                            output_shape=stage.get("output_shape"),
                            notes=str(stage.get("notes", "")),
                        )
                    ],
                    input_shape=stage.get("input_shape"),
                    output_shape=stage.get("output_shape"),
                    notes=str(stage.get("notes", "")),
                )
            )
            for index, stage in enumerate(pipeline)
        ]
        self._rebuild_flow()
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.slot_slider.blockSignals(True)
        self.slot_slider.setRange(0, 0)
        self.slot_slider.setValue(0)
        self.slot_slider.blockSignals(False)
        self.symbol_slider.blockSignals(True)
        self.symbol_slider.setRange(0, 0)
        self.symbol_slider.setValue(0)
        self.symbol_slider.blockSignals(False)
        self.stage_slider.setRange(0, max(len(self.stages) - 1, 0))
        if self.stages:
            self._set_current_stage(0)
        else:
            self._clear_view("No pipeline data is available.")

    def _extract_slot_history(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        slot_history = result.get("slot_history")
        if slot_history:
            normalized = []
            for entry in slot_history:
                slot_result = entry.get("result", result)
                normalized.append(
                    {
                        "timeline_index": int(entry.get("timeline_index", 0)),
                        "frame_index": int(entry.get("frame_index", 0)),
                        "slot_index": int(entry.get("slot_index", 0)),
                        "slot_label": str(entry.get("slot_label", "Frame 0 / Slot 0")),
                        "result": slot_result,
                    }
                )
            normalized.sort(key=lambda entry: int(entry["timeline_index"]))
            return normalized
        slot_context = result.get("slot_context", {})
        return [
            {
                "timeline_index": int(slot_context.get("timeline_index", 0)),
                "frame_index": int(slot_context.get("frame_index", 0)),
                "slot_index": int(slot_context.get("slot_index", 0)),
                "slot_label": str(slot_context.get("slot_label", "Frame 0 / Slot 0")),
                "result": result,
            }
        ]

    def _slot_records_for_frame(self, frame_index: int) -> list[dict[str, Any]]:
        return [entry for entry in self.slot_history if int(entry["frame_index"]) == int(frame_index)]

    def _select_frame(self, frame_index: int, requested_slot: int | None = None, preserve_stage: bool = True) -> None:
        slots_in_frame = self._slot_records_for_frame(frame_index)
        self.frame_value_label.setText(f"Frame {frame_index}")
        if not slots_in_frame:
            self.slot_slider.blockSignals(True)
            self.slot_slider.setRange(0, 0)
            self.slot_slider.setValue(0)
            self.slot_slider.blockSignals(False)
            self.slot_value_label.setText("Slot 0")
            self.stages = []
            self._rebuild_flow()
            self._clear_view("No captured slot exists for the selected frame.")
            return

        available_slots = sorted({int(entry["slot_index"]) for entry in slots_in_frame})
        target_slot = available_slots[0] if requested_slot not in available_slots else int(requested_slot)
        self.slot_slider.blockSignals(True)
        self.slot_slider.setRange(min(available_slots), max(available_slots))
        self.slot_slider.setValue(target_slot)
        self.slot_slider.blockSignals(False)
        self.slot_value_label.setText(f"Slot {target_slot}")

        slot_record = next(entry for entry in slots_in_frame if int(entry["slot_index"]) == target_slot)
        self._activate_slot_record(slot_record, preserve_stage=preserve_stage)

    def _activate_slot_record(self, slot_record: dict[str, Any], preserve_stage: bool = True) -> None:
        previous_stage_key = None
        if preserve_stage and 0 <= self.current_stage_index < len(self.stages):
            previous_stage_key = self.stages[self.current_stage_index].get("key")

        self.current_slot_record = slot_record
        self.active_result = slot_record["result"]
        self.stages = self._build_stage_models(self.active_result)
        self._rebuild_flow()

        numerology = self.active_result["tx"].metadata.numerology
        next_symbol = min(self.symbol_slider.value(), max(numerology.symbols_per_slot - 1, 0))
        self.symbol_slider.blockSignals(True)
        self.symbol_slider.setRange(0, max(numerology.symbols_per_slot - 1, 0))
        self.symbol_slider.setValue(next_symbol)
        self.symbol_slider.blockSignals(False)
        self.symbol_value_label.setText(f"Symbol {next_symbol}")

        next_stage_index = 0
        if previous_stage_key is not None:
            for index, stage in enumerate(self.stages):
                if stage.get("key") == previous_stage_key:
                    next_stage_index = index
                    break
        self.stage_slider.blockSignals(True)
        self.stage_slider.setRange(0, max(len(self.stages) - 1, 0))
        self.stage_slider.setValue(next_stage_index if self.stages else 0)
        self.stage_slider.blockSignals(False)

        if self.stages:
            self._set_current_stage(next_stage_index)
        else:
            self._clear_view("No PHY stages available for the selected slot.")

    def _current_slot_history_index(self) -> int:
        if self.current_slot_record is None:
            return -1
        current_timeline_index = int(self.current_slot_record.get("timeline_index", -1))
        for index, record in enumerate(self.slot_history):
            if int(record.get("timeline_index", -1)) == current_timeline_index:
                return index
        return -1

    def _move_to_slot_history_index(self, history_index: int, *, stage_index: int = 0) -> bool:
        if not (0 <= history_index < len(self.slot_history)):
            return False
        slot_record = self.slot_history[history_index]
        frame_index = int(slot_record["frame_index"])
        slot_index = int(slot_record["slot_index"])

        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(frame_index)
        self.frame_slider.blockSignals(False)
        self._select_frame(frame_index, requested_slot=slot_index, preserve_stage=False)

        if self.stages:
            bounded_stage_index = max(0, min(int(stage_index), len(self.stages) - 1))
            if bounded_stage_index != self.current_stage_index:
                self._set_current_stage(bounded_stage_index)
        return True

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
        self.play_state_label.setText("Auto-play is running through the PHY stages and captured slots.")

    def pause_playback(self) -> None:
        self.play_timer.stop()
        self.play_state_label.setText("Step-by-step playback is paused.")

    def reset_playback(self) -> None:
        self.pause_playback()
        if self.slot_history:
            self._move_to_slot_history_index(0, stage_index=0)
            self.play_state_label.setText("Playback reset to the first captured slot and first PHY stage.")

    def step_forward(self) -> None:
        if not self.stages:
            return
        if self.current_stage_index < len(self.stages) - 1:
            next_index = self.current_stage_index + 1
            self._set_current_stage(next_index)
            self.play_state_label.setText(f"Step mode moved to stage {next_index + 1}/{len(self.stages)}.")
            return

        next_slot_history_index = self._current_slot_history_index() + 1
        if self._move_to_slot_history_index(next_slot_history_index, stage_index=0):
            slot_label = self.current_slot_record.get("slot_label", "next slot") if self.current_slot_record else "next slot"
            self.play_state_label.setText(f"Step mode moved to {slot_label}, stage 1/{len(self.stages)}.")
            return

        self.play_state_label.setText("Step mode is already at the last captured slot and final PHY stage.")

    def step_backward(self) -> None:
        if not self.stages:
            return
        if self.current_stage_index > 0:
            next_index = self.current_stage_index - 1
            self._set_current_stage(next_index)
            self.play_state_label.setText(f"Step mode moved back to stage {next_index + 1}/{len(self.stages)}.")
            return

        previous_slot_history_index = self._current_slot_history_index() - 1
        if 0 <= previous_slot_history_index < len(self.slot_history):
            self._move_to_slot_history_index(previous_slot_history_index, stage_index=10**9)
            slot_label = self.current_slot_record.get("slot_label", "previous slot") if self.current_slot_record else "previous slot"
            self.play_state_label.setText(f"Step mode moved back to {slot_label}, final stage.")
            return

        self.play_state_label.setText("Step mode is already at the first captured slot and first PHY stage.")

    def _advance_animation(self) -> None:
        if self.current_stage_index < len(self.stages) - 1:
            self._set_current_stage(self.current_stage_index + 1)
            return

        next_slot_history_index = self._current_slot_history_index() + 1
        if self._move_to_slot_history_index(next_slot_history_index, stage_index=0):
            slot_label = self.current_slot_record.get("slot_label", "next slot") if self.current_slot_record else "next slot"
            self.play_state_label.setText(f"Auto-play advanced to {slot_label}.")
            return

        self.pause_playback()
        self.play_state_label.setText("Auto-play reached the last captured slot and CRC check stage.")

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
        summary = str(stage["description"])
        notes = str(stage.get("notes", "")).strip()
        if notes:
            summary = f"{summary}\n\nNotes: {notes}"
        self.stage_summary.setPlainText(summary)
        metrics = dict(stage["metrics"])
        metrics.setdefault("Artifact type", stage.get("artifact_type", "n/a"))
        metrics.setdefault("Input shape", stage.get("input_shape", "n/a"))
        metrics.setdefault("Output shape", stage.get("output_shape", "n/a"))
        self._update_metrics(metrics)
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
        caption = str(artifact.get("description", ""))
        artifact_notes = str(artifact.get("notes", "")).strip()
        if artifact_notes:
            caption = f"{caption}\nNotes: {artifact_notes}"
        self.artifact_caption.setText(caption)
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
                arrow = QLabel("->")
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
                arrow.setText("=>")
            elif index < self.current_stage_index:
                arrow.setStyleSheet("color: #34d399;")
                arrow.setText("=>")
            else:
                arrow.setStyleSheet("color: #475569;")
                arrow.setText("->")

    def _on_stage_slider_changed(self, value: int) -> None:
        self._set_current_stage(value)

    def _on_frame_changed(self, value: int) -> None:
        self._select_frame(value, requested_slot=self.slot_slider.value(), preserve_stage=True)

    def _on_slot_changed(self, value: int) -> None:
        self.slot_value_label.setText(f"Slot {value}")
        self._select_frame(self.frame_slider.value(), requested_slot=value, preserve_stage=True)

    def _render_stage(self) -> None:
        if not (0 <= self.current_stage_index < len(self.stages)):
            self._clear_view("No PHY stage selected.")
            return
        stage = self.stages[self.current_stage_index]
        frame_index = int(self.current_slot_record["frame_index"]) if self.current_slot_record else 0
        slot_index = int(self.current_slot_record["slot_index"]) if self.current_slot_record else 0
        self.stage_title.setText(
            f"<b>{stage['section']}</b> | <b>{stage['title']}</b> | Frame {frame_index} / Slot {slot_index} / Symbol {self.symbol_slider.value()}"
        )
        summary = str(stage["description"])
        notes = str(stage.get("notes", "")).strip()
        if notes:
            summary = f"{summary}\n\nNotes: {notes}"
        self.stage_summary.setPlainText(summary)
        metrics = dict(stage["metrics"])
        metrics.setdefault("Artifact type", stage.get("artifact_type", "n/a"))
        metrics.setdefault("Input shape", stage.get("input_shape", "n/a"))
        metrics.setdefault("Output shape", stage.get("output_shape", "n/a"))
        self._update_metrics(metrics)
        self.artifact_selector.blockSignals(True)
        self.artifact_selector.clear()
        for artifact in stage["artifacts"]:
            self.artifact_selector.addItem(str(artifact["name"]))
        self.artifact_selector.blockSignals(False)
        if stage["artifacts"]:
            self.artifact_selector.setCurrentIndex(0)
        self._render_current_artifact()

    def _build_stage_models(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        tx = result["tx"]
        rx = result["rx"]
        config = result["config"]
        channel_state = result["channel_state"]
        tx_meta = tx.metadata
        if str(tx_meta.channel_type).lower() == "prach":
            return self._pipeline_contract_stages(result)
        coding_meta = tx_meta.coding_metadata
        direction = str(getattr(tx_meta, "direction", "downlink")).lower()
        transform_precoding_enabled = bool(getattr(tx_meta, "transform_precoding_enabled", False))
        if direction == "uplink":
            mapping_label = "PUCCH-style" if tx_meta.channel_type in {"control", "pucch"} else "PUSCH-style"
        else:
            if tx_meta.channel_type in {"control", "pdcch"}:
                mapping_label = "PDCCH/CORESET-style"
            elif tx_meta.channel_type in {"pbch", "broadcast"}:
                mapping_label = "SSB/PBCH-style"
            else:
                mapping_label = "PDSCH-style"
        numerology = tx_meta.numerology
        positions = tx_meta.mapping.positions
        repeated_positions = expand_positions_for_layers(
            positions,
            tx_meta.spatial_layout.num_layers,
            total_symbols=tx_meta.modulation_symbols.size,
        )
        payload_with_crc = self._payload_with_crc_bits(tx_meta)
        code_blocks_with_crc = self._code_blocks_with_crc_bits(tx_meta)
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
        descrambled_llr_histogram = self._histogram_payload(rx.descrambled_llrs)
        decoder_input_llr_histogram = self._histogram_payload(rx.decoder_input_llrs)
        bit_error_mask = self._bit_error_mask(tx_meta.payload_bits, rx.recovered_bits)
        kpis = rx.kpis.as_dict()
        reference_symbols = tx_meta.modulation_symbols
        pre_eq_symbols = rx.rx_symbols
        post_eq_symbols = rx.detected_symbols
        mapping_table = self._mapping_table_text(tx_meta.mapper)
        code_rate = tx_meta.payload_bits.size / max(coding_meta.rate_matched_length, 1)
        code_stage = "Control small-block coder" if tx_meta.channel_type in {"control", "pdcch", "pbch", "pucch"} else "LDPC-inspired coder"
        data_re_mask = (allocation_map == 2.0).astype(np.float32)
        layer_symbol_counts = [
            int(np.count_nonzero(np.abs(tx_meta.tx_layer_symbols[layer_index]) > 1e-12))
            for layer_index in range(tx_meta.tx_layer_symbols.shape[0])
        ] if getattr(tx_meta, "tx_layer_symbols", np.zeros((1, 0))).ndim == 2 else [int(tx_meta.modulation_symbols.size)]
        codeword_payload_lengths = [
            int(np.asarray(block, dtype=np.uint8).size)
            for block in (getattr(tx_meta, "codeword_payload_bits", ()) or (tx_meta.payload_bits,))
        ]
        codeword_symbol_counts = [
            int(np.asarray(block, dtype=np.complex128).size)
            for block in (getattr(tx_meta, "codeword_modulation_symbols", ()) or (tx_meta.modulation_symbols,))
        ]
        codeword_layer_ranges = [
            (int(start), int(end))
            for start, end in (getattr(tx_meta, "codeword_layer_ranges", ()) or ((0, int(tx_meta.spatial_layout.num_layers)),))
        ]
        codeword_crc_status = [
            bool(value) for value in (getattr(rx, "codeword_crc_ok", ()) or (bool(rx.crc_ok),))
        ]
        port_symbol_counts = [
            int(np.count_nonzero(np.abs(tx_meta.tx_port_symbols[port_index]) > 1e-12))
            for port_index in range(tx_meta.tx_port_symbols.shape[0])
        ] if getattr(tx_meta, "tx_port_symbols", np.zeros((1, 0))).ndim == 2 else [int(tx_meta.modulation_symbols.size)]
        port_powers = [
            float(np.mean(np.abs(tx_meta.tx_port_symbols[port_index][: port_symbol_counts[port_index]]) ** 2))
            if port_symbol_counts[port_index] > 0
            else 0.0
            for port_index in range(len(port_symbol_counts))
        ]
        effective_channel_matrix = (
            np.mean(rx.effective_channel_tensor, axis=(2, 3))
            if getattr(rx, "effective_channel_tensor", np.zeros((0, 0, 0, 0))).size
            else np.zeros_like(np.asarray(tx_meta.precoder_matrix, dtype=np.complex128))
        )
        csi_feedback = dict(result.get("csi_feedback", {}))
        scheduler_harq_stages = self._scheduler_harq_stage_models(result)

        stages = self._stage_definitions(
            result=result,
            payload_with_crc=payload_with_crc,
            code_blocks_with_crc=code_blocks_with_crc,
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
            descrambled_llr_histogram=descrambled_llr_histogram,
            decoder_input_llr_histogram=decoder_input_llr_histogram,
            bit_error_mask=bit_error_mask,
            kpis=kpis,
            reference_symbols=reference_symbols,
            pre_eq_symbols=pre_eq_symbols,
            post_eq_symbols=post_eq_symbols,
            mapping_table=mapping_table,
            code_rate=code_rate,
            code_stage=code_stage,
            direction=direction,
            mapping_label=mapping_label,
            transform_precoding_enabled=transform_precoding_enabled,
            positions=positions,
            repeated_positions=repeated_positions,
            data_re_mask=data_re_mask,
            codeword_payload_lengths=codeword_payload_lengths,
            codeword_symbol_counts=codeword_symbol_counts,
            codeword_layer_ranges=codeword_layer_ranges,
            codeword_crc_status=codeword_crc_status,
            layer_symbol_counts=layer_symbol_counts,
            port_symbol_counts=port_symbol_counts,
            port_powers=port_powers,
            effective_channel_matrix=effective_channel_matrix,
            csi_feedback=csi_feedback,
        )
        if direction == "downlink" and tx_meta.channel_type in {"control", "pdcch"}:
            from phy.resource_grid import ResourceGrid

            helper = ResourceGrid(
                numerology,
                tx_meta.allocation,
                spatial_layout=tx_meta.spatial_layout,
                slot_index=int(getattr(tx_meta, "slot_index", 0)),
            )
            coreset_mask = helper.coreset_re_mask().astype(np.float32)
            search_space_mask = np.zeros_like(coreset_mask)
            if tx_meta.mapping.positions.size:
                search_space_mask[tx_meta.mapping.positions[:, 0], tx_meta.mapping.positions[:, 1]] = 1.0
            insertion_index = next(
                (index for index, stage in enumerate(stages) if stage.get("key") == "resource_grid_dmrs"),
                len(stages),
            )
            stages.insert(
                insertion_index,
                {
                    "key": "coreset_searchspace",
                    "section": "TX",
                    "flow_label": "CORESET",
                    "title": "CORESET / SearchSpace Selection",
                    "description": "Downlink control baseline constrains PDCCH mapping to a configurable CORESET and monitored SearchSpace subset before RE mapping.",
                    "metrics": {
                        "CORESET start symbol": int(tx_meta.allocation.coreset_start_symbol),
                        "CORESET symbol count": int(tx_meta.allocation.coreset_symbol_count),
                        "CORESET subcarriers": int(tx_meta.allocation.coreset_subcarriers),
                        "CORESET subcarrier offset": int(tx_meta.allocation.coreset_subcarrier_offset),
                        "SearchSpace stride": int(tx_meta.allocation.search_space_stride),
                        "SearchSpace offset": int(tx_meta.allocation.search_space_offset),
                        "SearchSpace periodicity (slots)": int(tx_meta.allocation.search_space_period_slots),
                        "SearchSpace slot offset": int(tx_meta.allocation.search_space_slot_offset),
                        "Monitored RE count": int(np.sum(search_space_mask)),
                    },
                    "artifacts": [
                        {"name": "CORESET mask", "kind": "grid", "payload": {"image": coreset_mask, "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of the configured CORESET region."},
                        {"name": "SearchSpace mask", "kind": "grid", "payload": {"image": search_space_mask, "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of monitored SearchSpace REs inside the CORESET."},
                    ],
                },
            )
        elif direction == "downlink" and tx_meta.channel_type in {"pbch", "broadcast"}:
            from phy.resource_grid import ResourceGrid

            helper = ResourceGrid(
                numerology,
                tx_meta.allocation,
                spatial_layout=tx_meta.spatial_layout,
                slot_index=int(getattr(tx_meta, "slot_index", 0)),
                physical_cell_id=int(tx_meta.ssb.get("physical_cell_id", 0)),
                ssb_block_index=int(tx_meta.ssb.get("ssb_block_index", 0)),
            )
            ssb_mask = np.zeros(helper.shape, dtype=np.float32)
            helper_ssb_positions = helper.ssb_positions(force_active=True)
            if helper_ssb_positions.size:
                ssb_mask[helper_ssb_positions[:, 0], helper_ssb_positions[:, 1]] = 1.0
            insertion_index = next(
                (index for index, stage in enumerate(stages) if stage.get("key") == "resource_grid_dmrs"),
                len(stages),
            )
            stages.insert(
                insertion_index,
                {
                    "key": "ssb_pbch_layout",
                    "section": "TX",
                    "flow_label": "SSB",
                    "title": "SSB / PBCH Broadcast Layout",
                    "description": "PBCH payload is mapped inside a dedicated SSB region with reserved PSS, SSS, and PBCH-DMRS resources.",
                    "metrics": {
                        "SSB start symbol": int(tx_meta.allocation.ssb_start_symbol),
                        "SSB symbol count": int(tx_meta.allocation.ssb_symbol_count),
                        "SSB subcarriers": int(tx_meta.allocation.ssb_subcarriers),
                        "SSB subcarrier offset": int(tx_meta.allocation.ssb_subcarrier_offset),
                        "SSB periodicity (slots)": int(tx_meta.allocation.ssb_period_slots),
                        "SSB slot offset": int(tx_meta.allocation.ssb_slot_offset),
                        "PBCH payload RE count": int(tx_meta.mapping.positions.shape[0]),
                    },
                    "artifacts": [
                        {"name": "SSB mask", "kind": "grid", "payload": {"image": ssb_mask, "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of the configured SSB region."},
                    ],
                },
            )
        transfer = result.get("file_transfer")
        if transfer:
            stages = [*self._file_transfer_entry_stages(result), *stages, *self._file_transfer_exit_stages(result)]
        if scheduler_harq_stages:
            stages = [*scheduler_harq_stages, *stages]
        return [normalize_pipeline_stage(stage) for stage in stages]

    def _sequence_summary_for_active_result(self, result: dict[str, Any]) -> dict[str, Any]:
        root_result = self.result if isinstance(self.result, dict) else result
        return dict(root_result.get("sequence_summary", result.get("sequence_summary", {})))

    @staticmethod
    def _current_trace_entry(trace: list[dict[str, Any]], timeline_index: int) -> dict[str, Any]:
        for entry in trace:
            if int(entry.get("timeline_index", -1)) == int(timeline_index):
                return dict(entry)
        return dict(trace[0]) if trace else {}

    @staticmethod
    def _modulation_order(modulation: str) -> int:
        return {"QPSK": 2, "16QAM": 4, "64QAM": 6, "256QAM": 8}.get(str(modulation).upper(), 0)

    @staticmethod
    def _trace_table_text(trace: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
        if not trace:
            return "No timeline entries are available."
        header = " | ".join(label for label, _ in columns)
        separator = " | ".join("---" for _ in columns)
        rows = []
        for entry in trace:
            rows.append(" | ".join(str(entry.get(key, "n/a")) for _, key in columns))
        return "\n".join([header, separator, *rows])

    def _scheduler_harq_stage_models(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        summary = self._sequence_summary_for_active_result(result)
        schedule_trace = [dict(entry) for entry in summary.get("schedule_trace", [])]
        harq_trace = [dict(entry) for entry in summary.get("harq_trace", [])]
        scheduler_active = bool(summary.get("scheduler_enabled", False))
        harq_active = bool(summary.get("harq_enabled", False))
        slot_context = result.get("slot_context", {})
        timeline_index = int(slot_context.get("timeline_index", result.get("scheduled_grant", {}).get("timeline_index", 0)))
        stages: list[dict[str, Any]] = []

        current_grant = dict(result.get("scheduled_grant", {}) or self._current_trace_entry(schedule_trace, timeline_index))
        if (scheduler_active or harq_active) and (schedule_trace or current_grant):
            if not schedule_trace and current_grant:
                schedule_trace = [current_grant]
            x_axis = np.asarray([int(entry.get("timeline_index", index)) for index, entry in enumerate(schedule_trace)], dtype=float)
            layers = np.asarray([int(entry.get("scheduled_layers", entry.get("num_layers", 1))) for entry in schedule_trace], dtype=float)
            mod_orders = np.asarray(
                [self._modulation_order(str(entry.get("scheduled_modulation", entry.get("modulation", "QPSK")))) for entry in schedule_trace],
                dtype=float,
            )
            rv_values = np.asarray([int(entry.get("harq_redundancy_version", entry.get("rv", 0))) for entry in schedule_trace], dtype=float)
            grant_table = self._trace_table_text(
                schedule_trace,
                [
                    ("slot", "timeline_index"),
                    ("grant", "grant_id"),
                    ("ch", "channel_type"),
                    ("mod", "scheduled_modulation"),
                    ("layers", "scheduled_layers"),
                    ("precoder", "scheduled_precoding_mode"),
                    ("rv", "harq_redundancy_version"),
                    ("ndi", "harq_ndi"),
                ],
            )
            stages.append(
                {
                    "key": "scheduler_timeline",
                    "section": "Control",
                    "flow_label": "Grant",
                    "title": "DCI-like Grant Timeline",
                    "description": "Configured or synthesized scheduling grants are replayed across captured slots so the PHY can be inspected as a scheduled transmission sequence rather than isolated slots.",
                    "metrics": {
                        "Scheduler enabled": bool(summary.get("scheduler_enabled", current_grant.get("grant_source") == "configured")),
                        "Current grant": current_grant.get("grant_id", "n/a"),
                        "Current channel": current_grant.get("channel_type", "n/a"),
                        "Current modulation": current_grant.get("scheduled_modulation", current_grant.get("modulation", "n/a")),
                        "Current layers": current_grant.get("scheduled_layers", current_grant.get("num_layers", "n/a")),
                        "Current RV": current_grant.get("harq_redundancy_version", current_grant.get("rv", "n/a")),
                    },
                    "artifacts": [
                        {
                            "name": "Current grant",
                            "kind": "text",
                            "payload": "\n".join(f"{key}: {value}" for key, value in current_grant.items()) or "No current grant.",
                            "description": "Full grant fields for the selected slot.",
                        },
                        {
                            "name": "Grant replay table",
                            "kind": "text",
                            "payload": grant_table,
                            "description": "Compact table of scheduled grants across captured slots.",
                        },
                        {
                            "name": "Grant timeline",
                            "kind": "multi_line",
                            "payload": {
                                "x_label": "Timeline slot",
                                "y_label": "Value",
                                "series": [
                                    {"x": x_axis, "y": layers, "color": "#38bdf8"},
                                    {"x": x_axis, "y": mod_orders, "color": "#f59e0b"},
                                    {"x": x_axis, "y": rv_values, "color": "#a78bfa"},
                                ],
                            },
                            "description": "Layer count, modulation order in bits/symbol, and RV across the scheduled sequence.",
                        },
                    ],
                }
            )

        if harq_trace:
            x_axis = np.asarray([int(entry.get("timeline_index", index)) for index, entry in enumerate(harq_trace)], dtype=float)
            rv_values = np.asarray([int(entry.get("rv", 0)) for entry in harq_trace], dtype=float)
            ack_values = np.asarray([1.0 if bool(entry.get("ack", False)) else 0.0 for entry in harq_trace], dtype=float)
            observations = np.asarray([int(entry.get("soft_observations", 1)) for entry in harq_trace], dtype=float)
            energy = np.asarray([float(entry.get("combined_llr_energy", 0.0)) for entry in harq_trace], dtype=float)
            current_harq = self._current_trace_entry(harq_trace, timeline_index)
            harq_table = self._trace_table_text(
                harq_trace,
                [
                    ("slot", "timeline_index"),
                    ("pid", "process_id"),
                    ("rv", "rv"),
                    ("ndi", "ndi"),
                    ("new", "new_data"),
                    ("obs", "soft_observations"),
                    ("ack", "ack"),
                ],
            )
            stages.append(
                {
                    "key": "harq_timeline",
                    "section": "Control",
                    "flow_label": "HARQ",
                    "title": "HARQ Process Timeline",
                    "description": "HARQ process state, RV cycling, ACK/NACK, and soft-buffer accumulation are shown across captured slots.",
                    "metrics": {
                        "HARQ enabled": bool(summary.get("harq_enabled", True)),
                        "Current process": current_harq.get("process_id", "n/a"),
                        "Current RV": current_harq.get("rv", "n/a"),
                        "Current ACK": current_harq.get("ack", "n/a"),
                        "Soft observations": current_harq.get("soft_observations", "n/a"),
                        "ACK count": summary.get("harq_ack_count", int(np.sum(ack_values))),
                        "NACK count": summary.get("harq_nack_count", int(ack_values.size - np.sum(ack_values))),
                    },
                    "artifacts": [
                        {
                            "name": "HARQ table",
                            "kind": "text",
                            "payload": harq_table,
                            "description": "Per-slot HARQ process summary.",
                        },
                        {
                            "name": "RV / ACK / soft observations",
                            "kind": "multi_line",
                            "payload": {
                                "x_label": "Timeline slot",
                                "y_label": "Value",
                                "series": [
                                    {"x": x_axis, "y": rv_values, "color": "#a78bfa"},
                                    {"x": x_axis, "y": ack_values, "color": "#34d399"},
                                    {"x": x_axis, "y": observations, "color": "#f59e0b"},
                                ],
                            },
                            "description": "RV sequence, ACK/NACK decisions, and number of accumulated soft observations.",
                        },
                        {
                            "name": "Soft-buffer energy",
                            "kind": "line",
                            "payload": {
                                "x": x_axis,
                                "y": energy,
                                "x_label": "Timeline slot",
                                "y_label": "Mean |combined LLR|",
                            },
                            "description": "Mean absolute value of the combined soft-buffer LLRs after each HARQ attempt.",
                        },
                    ],
                }
            )

        return stages

    def _pipeline_contract_stages(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        slot_context = result.get("slot_context", {})
        frame_index = int(slot_context.get("frame_index", 0))
        slot_index = int(slot_context.get("slot_index", 0))
        stages: list[dict[str, Any]] = []
        for index, stage in enumerate(result.get("pipeline", [])):
            normalized = normalize_pipeline_stage(stage)
            metrics = dict(normalized.get("metrics", {}))
            metrics.setdefault("Frame", frame_index)
            metrics.setdefault("Slot", slot_index)
            stages.append(
                {
                    "key": str(normalized.get("key", f"pipeline_{index}")),
                    "section": str(normalized.get("section", "Other")),
                    "flow_label": str(normalized.get("flow_label", normalized.get("stage", f"Stage {index + 1}"))),
                    "title": str(normalized.get("title", normalized.get("stage", f"Stage {index + 1}"))),
                    "description": str(normalized.get("description", "")),
                    "metrics": metrics,
                    "artifacts": normalized.get("artifacts", []),
                    "artifact_type": normalized.get("artifact_type", "text"),
                    "input_shape": normalized.get("input_shape"),
                    "output_shape": normalized.get("output_shape"),
                    "notes": str(normalized.get("notes", "")),
                }
            )
        return stages

    def _stage_definitions(
        self,
        *,
        result: dict[str, Any],
        payload_with_crc: np.ndarray,
        code_blocks_with_crc: np.ndarray,
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
        descrambled_llr_histogram: dict[str, Any],
        decoder_input_llr_histogram: dict[str, Any],
        bit_error_mask: np.ndarray,
        kpis: dict[str, Any],
        reference_symbols: np.ndarray,
        pre_eq_symbols: np.ndarray,
        post_eq_symbols: np.ndarray,
        mapping_table: str,
        code_rate: float,
        code_stage: str,
        direction: str,
        mapping_label: str,
        transform_precoding_enabled: bool,
        positions: np.ndarray,
        repeated_positions: np.ndarray,
        data_re_mask: np.ndarray,
        codeword_payload_lengths: list[int],
        codeword_symbol_counts: list[int],
        codeword_layer_ranges: list[tuple[int, int]],
        codeword_crc_status: list[bool],
        layer_symbol_counts: list[int],
        port_symbol_counts: list[int],
        port_powers: list[float],
        effective_channel_matrix: np.ndarray,
        csi_feedback: dict[str, Any],
    ) -> list[dict[str, Any]]:
        tx = result["tx"]
        rx = result["rx"]
        config = result["config"]
        channel_state = result["channel_state"]
        slot_context = result.get("slot_context", {})
        frame_index = int(slot_context.get("frame_index", 0))
        slot_index = int(slot_context.get("slot_index", 0))
        tx_meta = tx.metadata
        coding_meta = tx_meta.coding_metadata
        numerology = tx_meta.numerology
        stages = [
            {
                "key": "bits",
                "section": "TX",
                "flow_label": "Bits",
                "title": "Bits",
                "description": "Original transport block or control payload before any protection or scrambling.",
                "metrics": {
                    "Bitstream length": tx_meta.payload_bits.size,
                    "Channel type": tx_meta.channel_type,
                    "Frame": frame_index,
                    "Slot": slot_index,
                },
                "artifacts": [{"name": "Payload bits", "kind": "bits", "payload": tx_meta.payload_bits, "description": "Payload bits entering the PHY chain."}],
            },
            {
                "key": "crc_attach",
                "section": "TX",
                "flow_label": "TB CRC",
                "title": "Transport-Block CRC Attachment",
                "description": "Transport-block CRC is appended before segmentation and channel coding to enable end-to-end error detection.",
                "metrics": {
                    "TB CRC type": coding_meta.crc_type,
                    "Payload bits": tx_meta.payload_bits.size,
                    "Transport block + CRC": payload_with_crc.size,
                    "CRC bits added": payload_with_crc.size - tx_meta.payload_bits.size,
                },
                "artifacts": [{"name": "Transport block + CRC", "kind": "bits", "payload": payload_with_crc, "description": "Bitstream after transport-block CRC attachment."}],
            },
            {
                "key": "segmentation",
                "section": "TX",
                "flow_label": "Segment",
                "title": "Code Block Segmentation + CB CRC",
                "description": "The protected transport block is segmented into code blocks. When more than one block is required, each block receives its own CRC before coding.",
                "metrics": {
                    "Code block count": coding_meta.code_block_count,
                    "CB CRC type": coding_meta.code_block_crc_type or "not applied",
                    "Block payload lengths": ", ".join(str(int(length)) for length in coding_meta.code_block_payload_lengths) or "n/a",
                    "Block + CB CRC lengths": ", ".join(str(int(length)) for length in coding_meta.code_block_with_crc_lengths) or "n/a",
                },
                "artifacts": [
                    {
                        "name": "Code block summary",
                        "kind": "text",
                        "payload": self._code_block_summary_text(tx_meta),
                        "description": "Block-by-block summary after segmentation and code-block CRC attachment.",
                    },
                    {
                        "name": "Code blocks with CRC",
                        "kind": "bits",
                        "payload": code_blocks_with_crc,
                        "description": "Concatenated code blocks after per-block CRC attachment.",
                    },
                ],
            },
            {
                "key": "coding",
                "section": "TX",
                "flow_label": "Coding",
                "title": "Channel Coding",
                "description": "Simplified NR-inspired channel coding expands each code block into one mother-codeword segment.",
                "metrics": {
                    "Coder": code_stage,
                    "Mother length": coding_meta.mother_length,
                    "Code blocks": coding_meta.code_block_count,
                    "Mother block lengths": ", ".join(str(int(length)) for length in coding_meta.mother_block_lengths) or "n/a",
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
                    "Mapped symbols": tx_meta.modulation_symbols.size,
                    "Constellation order": 2 ** tx_meta.mapper.bits_per_symbol,
                },
                "artifacts": [
                    {
                        "name": "Mapping constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {"name": "Mapping table", "points": tx_meta.mapper.constellation, "color": "#f94144"},
                                {"name": "TX symbols", "points": tx_meta.modulation_symbols, "color": "#38bdf8", "symbol_indices": repeated_positions[: tx_meta.modulation_symbols.size, 0]},
                            ]
                        },
                        "description": "Constellation table and actual TX symbols before the channel.",
                    },
                    {
                        "name": "Before/after channel constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {"name": "Reference", "points": reference_symbols, "color": "#f94144", "symbol_indices": repeated_positions[: reference_symbols.size, 0]},
                                {"name": "Pre-EQ", "points": pre_eq_symbols, "color": "#ffffff", "symbol_indices": repeated_positions[: pre_eq_symbols.size, 0]},
                                {"name": "Post-EQ", "points": post_eq_symbols, "color": "#38bdf8", "symbol_indices": repeated_positions[: post_eq_symbols.size, 0]},
                            ]
                        },
                        "description": "Constellation before channel, after channel extraction, and after equalization.",
                    },
                    {"name": "Mapping table", "kind": "text", "payload": mapping_table, "description": "Gray-labeled mapping table for the selected modulation order."},
                ],
            },
            {
                "key": "codeword_split",
                "section": "TX",
                "flow_label": "Codeword",
                "title": "Codeword Split",
                "description": "The scheduled payload is divided into one or two independently encoded codewords before their symbol streams are assigned onto layers.",
                "metrics": {
                    "Codewords": int(tx_meta.spatial_layout.num_codewords),
                    "Payload bits / codeword": ", ".join(str(value) for value in codeword_payload_lengths) or "n/a",
                    "Symbols / codeword": ", ".join(str(value) for value in codeword_symbol_counts) or "n/a",
                    "Layer ranges": ", ".join(
                        f"CW{index}: L{start}-L{end - 1}"
                        for index, (start, end) in enumerate(codeword_layer_ranges)
                    ) or "n/a",
                    "RX CRC / codeword": ", ".join(
                        f"CW{index}: {'OK' if status else 'FAIL'}"
                        for index, status in enumerate(codeword_crc_status)
                    ) or "n/a",
                },
                "artifacts": [
                    {
                        "name": "Per-codeword constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {
                                    "name": f"Codeword {codeword_index}",
                                    "points": np.asarray(symbols, dtype=np.complex128),
                                    "color": color,
                                }
                                for codeword_index, (symbols, color) in enumerate(
                                    zip(
                                        getattr(tx_meta, "codeword_modulation_symbols", ()) or (tx_meta.modulation_symbols,),
                                        ["#38bdf8", "#f59e0b"],
                                    )
                                )
                            ]
                        },
                        "description": "Constellation-domain symbol streams for each codeword before layer mapping.",
                    },
                    {
                        "name": "Codeword summary",
                        "kind": "text",
                        "payload": "\n".join(
                            f"CW{index}: payload_bits={codeword_payload_lengths[index]}, symbols={codeword_symbol_counts[index]}, "
                            f"layers={codeword_layer_ranges[index][0]}-{codeword_layer_ranges[index][1] - 1}, "
                            f"rx_crc={'OK' if codeword_crc_status[min(index, len(codeword_crc_status) - 1)] else 'FAIL'}"
                            for index in range(len(codeword_payload_lengths))
                        ),
                        "description": "Codeword-to-layer allocation summary for the current slot.",
                    },
                ],
            },
            {
                "key": "layer_mapping",
                "section": "TX",
                "flow_label": "Layers",
                "title": "Layer Mapping",
                "description": "Codeword-domain symbol streams are distributed across the configured transmission layers before port mapping. In the current baseline, contiguous layer ranges are assigned to each codeword.",
                "metrics": {
                    "Codewords": int(tx_meta.spatial_layout.num_codewords),
                    "Layers": int(tx_meta.spatial_layout.num_layers),
                    "Ports": int(tx_meta.spatial_layout.num_ports),
                    "TX antennas": int(tx_meta.spatial_layout.num_tx_antennas),
                    "RX antennas": int(tx_meta.spatial_layout.num_rx_antennas),
                    "Symbols / layer": ", ".join(str(count) for count in layer_symbol_counts) or "n/a",
                },
                "artifacts": [
                    {
                        "name": "Per-layer constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {
                                    "name": f"Layer {layer_index}",
                                    "points": tx_meta.tx_layer_symbols[layer_index][: layer_symbol_counts[layer_index]],
                                    "color": color,
                                }
                                for layer_index, color in enumerate(["#38bdf8", "#f59e0b", "#34d399", "#f472b6"][: tx_meta.tx_layer_symbols.shape[0]])
                            ]
                        },
                        "description": "Layer-domain symbol streams after NR-style layer mapping.",
                    },
                    *[
                        {
                            "name": f"Layer {layer_index} occupancy",
                            "kind": "grid",
                            "payload": {"image": np.abs(tx_meta.tx_layer_grid[layer_index]), "lookup": "viridis"},
                            "description": f"Resource occupancy for layer {layer_index} before port mapping.",
                        }
                        for layer_index in range(tx_meta.tx_layer_grid.shape[0])
                    ],
                ],
            },
            {
                "key": "precoding_port_mapping",
                "section": "TX",
                "flow_label": "Precode",
                "title": "Precoding / Port Mapping",
                "description": "Layer-domain streams are converted to port-domain streams through the configured linear precoder before port-grid occupancy is generated.",
                "metrics": {
                    "Precoding mode": getattr(tx_meta, "precoding_mode", "identity"),
                    "Precoder shape": f"{tx_meta.precoder_matrix.shape[0]} x {tx_meta.precoder_matrix.shape[1]}",
                    "Symbols / port": ", ".join(str(count) for count in port_symbol_counts) or "n/a",
                    "Port powers": ", ".join(f"{power:.3f}" for power in port_powers) or "n/a",
                },
                "artifacts": [
                    {
                        "name": "Precoder matrix magnitude",
                        "kind": "grid",
                        "payload": {"image": np.abs(tx_meta.precoder_matrix), "lookup": "cividis"},
                        "description": "Magnitude of the configured layer-to-port precoder matrix.",
                    },
                    {
                        "name": "Per-port constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {
                                    "name": f"Port {port_index}",
                                    "points": tx_meta.tx_port_symbols[port_index][: port_symbol_counts[port_index]],
                                    "color": color,
                                }
                                for port_index, color in enumerate(["#38bdf8", "#f59e0b", "#34d399", "#f472b6"][: tx_meta.tx_port_symbols.shape[0]])
                            ]
                        },
                        "description": "Port-domain symbol streams after precoding.",
                    },
                    {
                        "name": "Per-port power",
                        "kind": "bar",
                        "payload": {
                            "categories": [f"Port {index}" for index in range(len(port_powers))],
                            "values": port_powers,
                        },
                        "description": "Average power of each port-domain symbol stream.",
                    },
                    *[
                        {
                            "name": f"Port {port_index} occupancy",
                            "kind": "grid",
                            "payload": {"image": np.abs(tx_meta.tx_port_grid[port_index]), "lookup": "viridis"},
                            "description": f"Resource occupancy for port {port_index} after precoding.",
                        }
                        for port_index in range(tx_meta.tx_port_grid.shape[0])
                    ],
                ],
            },
            {
                "key": "resource_grid_dmrs",
                "section": "TX",
                "flow_label": "Grid + DMRS",
                "title": "Resource Grid + RS",
                "description": (
                    "Mapped "
                    f"{mapping_label} symbols are placed onto the NR-like resource grid. "
                    + (
                        "PBCH-DMRS and SSB reference signals are reserved inside the broadcast region."
                        if tx_meta.channel_type in {"pbch", "broadcast"}
                        else "DMRS is inserted on configured OFDM symbols for channel estimation."
                    )
                ),
                "metrics": {
                    "CORESET RE count": int(np.sum(allocation_map == 1)),
                    "SearchSpace / mapped control RE count": int(np.sum(allocation_map == 2)) if tx_meta.channel_type in {"control", "pdcch"} and direction == "downlink" else 0,
                    "SSB reserved RE count": int(np.sum(allocation_map == 1)) if tx_meta.channel_type in {"pbch", "broadcast"} and direction == "downlink" else 0,
                    "Grid shape": f"{tx_meta.tx_grid.shape[0]} x {tx_meta.tx_grid.shape[1]}",
                    "Control RE count": int(np.sum(allocation_map == 1)),
                    "Data RE count": int(np.sum(allocation_map == 2)),
                    "DMRS RE count": int(np.sum(allocation_map == 3)),
                    "CSI-RS RE count": int(np.sum(allocation_map == 4)),
                    "SRS RE count": int(np.sum(allocation_map == 5)),
                    "PT-RS RE count": int(np.sum(allocation_map == 6)),
                },
                "artifacts": [
                    {"name": "Allocation map", "kind": "grid", "payload": {"image": allocation_map, "lookup": "allocation", "levels": (0.0, 6.0)}, "description": "Heatmap showing CORESET or SSB, scheduled payload/control REs, DMRS/PBCH-DMRS, CSI-RS, SRS, and PT-RS placement."},
                    {"name": "TX grid magnitude", "kind": "grid", "payload": {"image": np.abs(tx_meta.tx_grid), "lookup": "viridis"}, "description": "Magnitude of the populated resource grid after DMRS insertion."},
                    {"name": "DMRS mask", "kind": "grid", "payload": {"image": dmrs_mask, "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of DMRS RE locations."},
                    {"name": "CSI-RS mask", "kind": "grid", "payload": {"image": (allocation_map == 4.0).astype(np.float32), "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of CSI-RS RE locations."},
                    {"name": "SRS mask", "kind": "grid", "payload": {"image": (allocation_map == 5.0).astype(np.float32), "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of SRS RE locations."},
                    {"name": "PT-RS mask", "kind": "grid", "payload": {"image": (allocation_map == 6.0).astype(np.float32), "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of PT-RS RE locations."},
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
                "key": "remove_cp",
                "section": "RX",
                "flow_label": "Remove CP",
                "title": "Cyclic Prefix Removal",
                "description": "After synchronization, the cyclic prefix is stripped from each OFDM symbol so that FFT is applied only to the useful symbol interval.",
                "metrics": {
                    "CP length": numerology.cp_length,
                    "Useful FFT samples": numerology.fft_size,
                    "CP-removed tensor": f"{rx.cp_removed_tensor.shape[0]} x {rx.cp_removed_tensor.shape[1]} x {rx.cp_removed_tensor.shape[2]}",
                },
                "artifacts": [
                    {"name": "CP-removed symbol matrix", "kind": "grid", "payload": {"image": np.abs(rx.cp_removed_tensor[0]), "lookup": "viridis"}, "description": "Magnitude of each CP-removed OFDM symbol before FFT."},
                    {"name": "Corrected waveform", "kind": "waveform", "payload": {"waveform": corrected_waveform, "symbol_length": numerology.fft_size + numerology.cp_length, "x_label": "Sample", "y_label": "Amplitude"}, "description": "Time-domain waveform from which cyclic prefixes are removed."},
                ],
            },
            {
                "key": "fft",
                "section": "RX",
                "flow_label": "FFT",
                "title": "FFT",
                "description": "FFT converts each CP-removed OFDM symbol into the frequency domain before active-subcarrier extraction.",
                "metrics": {
                    "FFT bins tensor": f"{rx.fft_bins_tensor.shape[0]} x {rx.fft_bins_tensor.shape[1]} x {rx.fft_bins_tensor.shape[2]}",
                    "Symbols / slot": numerology.symbols_per_slot,
                    "FFT size": numerology.fft_size,
                    "RX spectrum bins": rx_spectrum["x"].size,
                },
                "artifacts": [
                    {"name": "FFT magnitude", "kind": "grid", "payload": {"image": np.abs(rx.fft_bins_tensor[0]), "lookup": "magma"}, "description": "Magnitude of the full FFT bins before active-subcarrier extraction."},
                    {"name": "RX spectrum", "kind": "spectrum", "payload": rx_spectrum, "description": "Spectrum of the received waveform before equalization."},
                ],
            },
            {
                "key": "re_extraction",
                "section": "RX",
                "flow_label": "RE Extract",
                "title": "Resource Element Extraction",
                "description": "Active REs are separated into payload REs and DMRS REs before channel estimation and data detection.",
                "metrics": {
                    "Data RE count": rx.re_data_positions.shape[0],
                    "DMRS RE count": rx.re_dmrs_positions.shape[0],
                    "CSI-RS RE count": rx.re_csi_rs_positions.shape[0],
                    "SRS RE count": rx.re_srs_positions.shape[0],
                    "PT-RS RE count": rx.re_ptrs_positions.shape[0],
                    "SSB RE count": rx.re_ssb_positions.shape[0],
                    "RX grid shape": f"{rx.rx_grid.shape[0]} x {rx.rx_grid.shape[1]}",
                },
                "artifacts": [
                    {"name": "Data RE mask", "kind": "grid", "payload": {"image": data_re_mask, "lookup": "plasma", "levels": (0.0, 1.0)}, "description": "Binary mask of extracted payload RE locations."},
                    {"name": "Extracted data constellation", "kind": "constellation_compare", "payload": {"series": [{"name": "Data RE", "points": rx.re_data_symbols, "color": "#38bdf8", "symbol_indices": rx.re_data_positions[: rx.re_data_symbols.size, 0]}]}, "description": "Payload RE observations extracted from the RX grid before equalization."},
                    {"name": "Extracted DMRS symbols", "kind": "constellation_compare", "payload": {"series": [{"name": "DMRS RE", "points": rx.re_dmrs_symbols, "color": "#f59e0b", "symbol_indices": rx.re_dmrs_positions[: rx.re_dmrs_symbols.size, 0] if rx.re_dmrs_positions.size else np.array([], dtype=int)}]}, "description": "DMRS observations extracted from the RX grid."},
                    {"name": "Extracted CSI-RS symbols", "kind": "constellation_compare", "payload": {"series": [{"name": "CSI-RS RE", "points": rx.re_csi_rs_symbols, "color": "#a855f7", "symbol_indices": rx.re_csi_rs_positions[: rx.re_csi_rs_symbols.size, 0] if rx.re_csi_rs_positions.size else np.array([], dtype=int)}]}, "description": "CSI-RS observations extracted from the RX grid."},
                    {"name": "Extracted SRS symbols", "kind": "constellation_compare", "payload": {"series": [{"name": "SRS RE", "points": rx.re_srs_symbols, "color": "#10b981", "symbol_indices": rx.re_srs_positions[: rx.re_srs_symbols.size, 0] if rx.re_srs_positions.size else np.array([], dtype=int)}]}, "description": "SRS observations extracted from the RX grid."},
                    {"name": "Extracted PT-RS symbols", "kind": "constellation_compare", "payload": {"series": [{"name": "PT-RS RE", "points": rx.re_ptrs_symbols, "color": "#f472b6", "symbol_indices": rx.re_ptrs_positions[: rx.re_ptrs_symbols.size, 0] if rx.re_ptrs_positions.size else np.array([], dtype=int)}]}, "description": "PT-RS observations extracted from the RX grid."},
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
                    {"name": "Pre/post equalization constellation", "kind": "constellation_compare", "payload": {"series": [{"name": "Reference", "points": reference_symbols, "color": "#f94144", "symbol_indices": repeated_positions[: reference_symbols.size, 0]}, {"name": "Pre-EQ", "points": pre_eq_symbols, "color": "#ffffff", "symbol_indices": repeated_positions[: pre_eq_symbols.size, 0]}, {"name": "Post-EQ", "points": post_eq_symbols, "color": "#38bdf8", "symbol_indices": repeated_positions[: post_eq_symbols.size, 0]}]}, "description": "Constellation before equalization and after equalization."},
                    {"name": "Equalizer gain", "kind": "line", "payload": {"x": np.arange(equalizer_gain.size), "y": 20.0 * np.log10(equalizer_gain + 1e-9), "x_label": "Subcarrier", "y_label": "Gain (dB)"}, "description": "Approximate equalizer gain magnitude derived from the estimated channel response."},
                ],
            },
            {
                "key": "mimo_detection",
                "section": "RX",
                "flow_label": "Detector",
                "title": "MIMO Detection",
                "description": "Per-RE receive-antenna observations are processed with the configured SU-MIMO detector to recover port-domain symbols under the estimated channel tensor.",
                "metrics": {
                    "Detected ports": int(rx.equalized_port_symbols.shape[0]),
                    "Observed ports": int(rx.equalized_port_symbols.shape[0]),
                    "Detector": str(config.get("receiver", {}).get("mimo_detector", config.get("receiver", {}).get("equalizer", "mmse"))).lower(),
                    "Effective channel shape": f"{effective_channel_matrix.shape[0]} x {effective_channel_matrix.shape[1]}",
                },
                "artifacts": [
                    {
                        "name": "Port-domain constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {
                                    "name": f"Port {port_index}",
                                    "points": rx.equalized_port_symbols[port_index],
                                    "color": color,
                                }
                                for port_index, color in enumerate(["#38bdf8", "#f59e0b", "#34d399", "#f472b6"][: rx.equalized_port_symbols.shape[0]])
                            ]
                        },
                        "description": "Equalized port-domain constellations before layer recovery.",
                    },
                    {
                        "name": "Effective channel magnitude",
                        "kind": "grid",
                        "payload": {"image": np.abs(effective_channel_matrix), "lookup": "cividis"},
                        "description": "Approximate effective layer-to-port channel magnitude under the current baseline.",
                    },
                ],
            },
            {
                "key": "layer_recovery",
                "section": "RX",
                "flow_label": "De-Precode",
                "title": "Layer Recovery / De-precoding",
                "description": "Detected port-domain symbols are projected back into the layer domain using the pseudo-inverse of the configured precoder.",
                "metrics": {
                    "Recovered layers": int(rx.equalized_layer_symbols.shape[0]),
                    "Precoder condition": f"{float(np.linalg.cond(tx_meta.precoder_matrix)):.4g}",
                    "Layer symbols": int(rx.equalized_layer_symbols.shape[1]) if rx.equalized_layer_symbols.ndim == 2 else 0,
                },
                "artifacts": [
                    {
                        "name": "Recovered per-layer constellation",
                        "kind": "constellation_compare",
                        "payload": {
                            "series": [
                                {
                                    "name": f"Layer {layer_index}",
                                    "points": rx.equalized_layer_symbols[layer_index],
                                    "color": color,
                                }
                                for layer_index, color in enumerate(["#38bdf8", "#f59e0b", "#34d399", "#f472b6"][: rx.equalized_layer_symbols.shape[0]])
                            ]
                        },
                        "description": "Recovered layer-domain constellations after de-precoding.",
                    },
                ],
            },
            {
                "key": "csi_feedback",
                "section": "RX",
                "flow_label": "CSI",
                "title": "CSI Feedback",
                "description": "CQI, PMI, and RI are derived from the effective channel tensor and detector noise estimate, producing a baseline CSI loop for later slot scheduling.",
                "metrics": {
                    "CQI": int(csi_feedback.get("cqi", 0)),
                    "PMI": str(csi_feedback.get("pmi", getattr(tx_meta, "precoding_mode", "identity"))),
                    "RI": int(csi_feedback.get("ri", tx_meta.spatial_layout.num_layers)),
                    "Suggested modulation": str(csi_feedback.get("modulation", tx_meta.modulation)),
                    "Suggested target rate": f"{float(csi_feedback.get('target_rate', code_rate)):.3f}",
                    "Capacity proxy": f"{float(csi_feedback.get('capacity_proxy_bps_hz', 0.0)):.4g} b/s/Hz",
                },
                "artifacts": [
                    {
                        "name": "Singular value spectrum",
                        "kind": "bar",
                        "payload": {
                            "categories": [f"s{index + 1}" for index in range(len(csi_feedback.get("singular_values", [])))],
                            "values": np.asarray(csi_feedback.get("singular_values", []), dtype=float),
                        },
                        "description": "Singular values of the average effective MIMO channel used to derive RI.",
                    },
                    {
                        "name": "Rank score",
                        "kind": "bar",
                        "payload": {
                            "categories": [f"RI {index + 1}" for index in range(len(csi_feedback.get("rank_scores", [])))],
                            "values": np.asarray(csi_feedback.get("rank_scores", []), dtype=float),
                        },
                        "description": "Capacity proxy used to choose the recommended rank.",
                    },
                    {
                        "name": "Codebook score",
                        "kind": "bar",
                        "payload": {
                            "categories": list(csi_feedback.get("codebook_scores", {}).keys()),
                            "values": np.asarray(list(csi_feedback.get("codebook_scores", {}).values()), dtype=float),
                        },
                        "description": "Relative score of each candidate precoder mode under the current channel estimate.",
                    },
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
                "key": "descrambling",
                "section": "RX",
                "flow_label": "Descramble",
                "title": "Descrambling",
                "description": "The demapper output is de-whitened with the same pseudo-random sequence used at the transmitter.",
                "metrics": {
                    "Descrambled LLR count": rx.descrambled_llrs.size,
                    "Mean |LLR|": f"{float(np.mean(np.abs(rx.descrambled_llrs))):.4g}",
                    "Sequence length": tx_meta.scrambling_sequence.size,
                },
                "artifacts": [
                    {"name": "Descrambled LLR trace", "kind": "line", "payload": {"x": np.arange(min(rx.descrambled_llrs.size, 256)), "y": rx.descrambled_llrs[:256], "x_label": "LLR index", "y_label": "Descrambled LLR"}, "description": "First descrambled LLR values delivered to rate recovery."},
                    {"name": "Descrambled LLR histogram", "kind": "histogram", "payload": descrambled_llr_histogram, "description": "Histogram of descrambled soft decisions."},
                ],
            },
            {
                "key": "rate_recovery",
                "section": "RX",
                "flow_label": "Rate Recover",
                "title": "Rate Recovery",
                "description": "Rate recovery expands the descrambled LLR stream back onto the mother-codeword domain before decoding.",
                "metrics": {
                    "Rate-matched length": coding_meta.rate_matched_length,
                    "Mother length": coding_meta.mother_length,
                    "Redundancy version": coding_meta.redundancy_version,
                    "Recovered LLR count": rx.rate_recovered_llrs.size,
                    "Recovered blocks": len(rx.rate_recovered_code_blocks),
                },
                "artifacts": [
                    {"name": "Rate-recovered LLR trace", "kind": "line", "payload": {"x": np.arange(min(rx.rate_recovered_llrs.size, 256)), "y": rx.rate_recovered_llrs[:256], "x_label": "Mother-code index", "y_label": "Recovered LLR"}, "description": "LLRs after inverse rate matching."},
                    {"name": "Rate-recovered block summary", "kind": "text", "payload": self._llr_block_summary_text(rx.rate_recovered_code_blocks, "Rate-recovered blocks"), "description": "Per-code-block LLR sizes after inverse rate matching."},
                ],
            },
            {
                "key": "soft_llr",
                "section": "RX",
                "flow_label": "Soft LLR",
                "title": "Soft LLR Before Decoding",
                "description": "This is the decoder input after descrambling and rate recovery. It is the soft-information interface between front-end detection and channel decoding.",
                "metrics": {
                    "Decoder-input LLR count": rx.decoder_input_llrs.size,
                    "Mean |LLR|": f"{float(np.mean(np.abs(rx.decoder_input_llrs))):.4g}",
                    "Min LLR": f"{float(np.min(rx.decoder_input_llrs)):.4g}",
                    "Max LLR": f"{float(np.max(rx.decoder_input_llrs)):.4g}",
                    "Decoder-input blocks": len(rx.decoder_input_code_blocks),
                },
                "artifacts": [
                    {"name": "Decoder-input LLR trace", "kind": "line", "payload": {"x": np.arange(min(rx.decoder_input_llrs.size, 256)), "y": rx.decoder_input_llrs[:256], "x_label": "Decoder input index", "y_label": "LLR"}, "description": "Soft LLR sequence consumed by the channel decoder."},
                    {"name": "Decoder-input LLR histogram", "kind": "histogram", "payload": decoder_input_llr_histogram, "description": "Histogram of the decoder-input soft LLRs."},
                    {"name": "Decoder-input block summary", "kind": "text", "payload": self._llr_block_summary_text(rx.decoder_input_code_blocks, "Decoder-input blocks"), "description": "Per-code-block LLR sizes before hard decoding."},
                ],
            },
            {
                "key": "decoding",
                "section": "RX",
                "flow_label": "Decode",
                "title": "Decoding",
                "description": "The channel decoder reconstructs the protected payload bits from the rate-recovered decoder-input LLR stream.",
                "metrics": {
                    "Recovered bits": rx.recovered_bits.size,
                    "Bit errors": int(np.sum(bit_error_mask)),
                    "BER": f"{rx.kpis.ber:.4g}",
                    "BLER": f"{rx.kpis.bler:.4g}",
                    "CB CRC pass count": f"{sum(bool(value) for value in rx.code_block_crc_ok)} / {len(rx.code_block_crc_ok) or 1}",
                },
                "artifacts": [
                    {"name": "Recovered bits", "kind": "bits", "payload": rx.recovered_bits, "description": "Recovered payload bits after channel decoding."},
                    {"name": "Bit error mask", "kind": "bits", "payload": bit_error_mask, "description": "Error mask against the transmitted payload bits. A '1' marks a bit error."},
                    {"name": "Code block CRC summary", "kind": "text", "payload": self._code_block_crc_status_text(rx.code_block_crc_ok), "description": "Per-code-block CRC decisions during decoding."},
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

        if transform_precoding_enabled:
            stages.insert(
                7,
                {
                    "key": "transform_precoding",
                    "section": "TX",
                    "flow_label": "DFT Spread",
                    "title": "Transform Precoding",
                    "description": "DFT-based transform precoding is applied before uplink resource mapping, producing a DFT-s-OFDM style PUSCH baseline.",
                    "metrics": {
                        "Direction": direction,
                        "Input symbols": tx_meta.modulation_symbols.size,
                        "Output symbols": tx_meta.tx_symbols.size,
                    },
                    "artifacts": [
                        {
                            "name": "Pre/post transform constellation",
                            "kind": "constellation_compare",
                            "payload": {
                                "series": [
                                    {"name": "Mapped QAM", "points": tx_meta.modulation_symbols, "color": "#f94144"},
                                    {"name": "Transform-precoded", "points": tx_meta.tx_symbols, "color": "#38bdf8"},
                                ]
                            },
                            "description": "Constellation before and after DFT spreading.",
                        }
                    ],
                },
            )
            equalization_index = next(index for index, stage in enumerate(stages) if stage["key"] == "equalization")
            stages.insert(
                equalization_index + 1,
                {
                    "key": "inverse_transform_precoding",
                    "section": "RX",
                    "flow_label": "IDFT",
                    "title": "Inverse Transform Precoding",
                    "description": "The equalized uplink sequence is de-spread by the inverse DFT before soft demapping.",
                    "metrics": {
                        "Input symbols": rx.equalized_symbols.size,
                        "Output symbols": rx.detected_symbols.size,
                    },
                    "artifacts": [
                        {
                            "name": "Pre/post inverse transform constellation",
                            "kind": "constellation_compare",
                            "payload": {
                                "series": [
                                    {"name": "Equalized", "points": rx.equalized_symbols, "color": "#ffffff"},
                                    {"name": "After inverse transform", "points": rx.detected_symbols, "color": "#38bdf8"},
                                ]
                            },
                            "description": "Equalized PUSCH symbols before and after inverse DFT de-spreading.",
                        }
                    ],
                },
            )

        return stages

    def _file_transfer_entry_stages(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        transfer = result["file_transfer"]
        source_package_bits = np.asarray(result.get("source_package_bits", np.array([], dtype=np.uint8)), dtype=np.uint8)
        summary_text = (
            f"Source file: {transfer['source_filename']}\n"
            f"Source path: {transfer['source_path']}\n"
            f"Media kind: {transfer['media_kind']}\n"
            f"MIME type: {transfer['mime_type']}\n"
            f"Source bytes: {transfer['source_size_bytes']}\n"
            f"Package bytes: {transfer['package_size_bytes']}\n"
            f"Payload bits/chunk: {transfer['payload_bits_per_chunk']}\n"
            f"Total chunks: {transfer['total_chunks']}\n"
            f"Source preview:\n{transfer['source_preview']}"
        )
        return [
            {
                "key": "file_source",
                "section": "TX",
                "flow_label": "File Src",
                "title": "File Source + Packaging",
                "description": "The TX-side file is read from disk, serialized into a package with metadata, converted to bits, and segmented into transport blocks before entering the PHY chain.",
                "metrics": {
                    "Filename": transfer["source_filename"],
                    "Media kind": transfer["media_kind"],
                    "Source bytes": transfer["source_size_bytes"],
                    "Chunks": transfer["total_chunks"],
                },
                "artifacts": [
                    {"name": "Transfer summary", "kind": "text", "payload": summary_text, "description": "High-level metadata for the selected TX-side file and its PHY chunking."},
                    {"name": "Packaged bitstream", "kind": "bits", "payload": source_package_bits, "description": "Serialized file package before chunking into transport blocks."},
                ],
            }
        ]

    def _file_transfer_exit_stages(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        transfer = result["file_transfer"]
        recovered_bits = np.asarray(result.get("recovered_package_bits", np.array([], dtype=np.uint8)), dtype=np.uint8)
        summary_text = (
            f"Transfer success: {transfer['success']}\n"
            f"Chunk status: {transfer['chunks_passed']} passed / {transfer['total_chunks']} total\n"
            f"SHA-256 match: {transfer['sha256_match']}\n"
            f"Restored file path: {transfer.get('restored_file_path') or 'not written'}\n"
            f"Restored size (bytes): {transfer.get('restored_size_bytes', 0)}\n"
            f"Transfer error: {transfer.get('error') or 'none'}\n"
            f"RX preview:\n{transfer['restored_preview']}"
        )
        return [
            {
                "key": "file_rx",
                "section": "RX",
                "flow_label": "File RX",
                "title": "File Reassembly + Write",
                "description": "Recovered chunk payloads are concatenated, parsed back into the original file package, and written to disk at the RX side if all required transport blocks survive PHY decoding.",
                "metrics": {
                    "Transfer success": bool(transfer["success"]),
                    "Chunks passed": transfer["chunks_passed"],
                    "Chunks failed": transfer["chunks_failed"],
                    "SHA-256 match": bool(transfer["sha256_match"]),
                },
                "artifacts": [
                    {"name": "Reassembly summary", "kind": "text", "payload": summary_text, "description": "End-to-end file recovery status after PHY transport."},
                    {"name": "Recovered package bits", "kind": "bits", "payload": recovered_bits, "description": "Recovered serialized file package after chunk reassembly."},
                ],
            }
        ]

    @staticmethod
    def _codeword_coding_metadatas(tx_meta) -> tuple[Any, ...]:
        metadatas = tuple(getattr(tx_meta, "codeword_coding_metadata", ()) or ())
        return metadatas or (tx_meta.coding_metadata,)

    @classmethod
    def _payload_with_crc_bits(cls, tx_meta) -> np.ndarray:
        blocks: list[np.ndarray] = []
        for index, coding_meta in enumerate(cls._codeword_coding_metadatas(tx_meta)):
            if coding_meta.transport_block_with_crc is not None:
                blocks.append(np.asarray(coding_meta.transport_block_with_crc, dtype=np.uint8))
            else:
                payloads = getattr(tx_meta, "codeword_payload_bits", ()) or (tx_meta.payload_bits,)
                payload = np.asarray(payloads[min(index, len(payloads) - 1)], dtype=np.uint8)
                blocks.append(attach_crc(payload, coding_meta.crc_type))
        return np.concatenate(blocks).astype(np.uint8) if blocks else np.array([], dtype=np.uint8)

    @classmethod
    def _code_blocks_with_crc_bits(cls, tx_meta) -> np.ndarray:
        blocks: list[np.ndarray] = []
        for coding_meta in cls._codeword_coding_metadatas(tx_meta):
            if coding_meta.code_blocks_with_crc:
                blocks.extend(np.asarray(block, dtype=np.uint8) for block in coding_meta.code_blocks_with_crc)
            elif coding_meta.transport_block_with_crc is not None:
                blocks.append(np.asarray(coding_meta.transport_block_with_crc, dtype=np.uint8))
        return np.concatenate(blocks).astype(np.uint8) if blocks else np.array([], dtype=np.uint8)

    @staticmethod
    def _mother_bits(tx_meta) -> np.ndarray:
        mother_blocks: list[np.ndarray] = []
        metadatas = getattr(tx_meta, "codeword_coding_metadata", ()) or (tx_meta.coding_metadata,)
        payloads = getattr(tx_meta, "codeword_payload_bits", ()) or (tx_meta.payload_bits,)
        for index, coding_meta in enumerate(metadatas):
            if coding_meta.mother_code_blocks:
                mother_blocks.extend(np.asarray(block, dtype=np.uint8) for block in coding_meta.mother_code_blocks)
                continue
            payload = (
                np.asarray(coding_meta.transport_block_with_crc, dtype=np.uint8)
                if coding_meta.transport_block_with_crc is not None
                else attach_crc(np.asarray(payloads[min(index, len(payloads) - 1)], dtype=np.uint8), coding_meta.crc_type)
            )
            if tx_meta.channel_type in {"control", "pdcch", "pbch"}:
                polar_length = int(coding_meta.polar_length or payload.size)
                info_positions = np.asarray(coding_meta.info_positions)
                u = np.zeros(polar_length, dtype=np.uint8)
                if info_positions.size:
                    u[info_positions] = payload
                mother_blocks.append(_polar_transform(u))
                continue
            mother = np.tile(payload, int(coding_meta.repetition_factor))
            if coding_meta.interleaver is not None:
                mother = mother[np.asarray(coding_meta.interleaver)]
            mother_blocks.append(mother.astype(np.uint8))
        return np.concatenate(mother_blocks).astype(np.uint8) if mother_blocks else np.array([], dtype=np.uint8)

    @classmethod
    def _code_block_summary_text(cls, tx_meta) -> str:
        lines = [f"Codewords: {int(tx_meta.spatial_layout.num_codewords)}"]
        for codeword_index, coding_meta in enumerate(cls._codeword_coding_metadatas(tx_meta)):
            lines.extend(
                [
                    f"CW{codeword_index}: code_blocks={int(coding_meta.code_block_count)}",
                    f"CW{codeword_index}: TB CRC type={coding_meta.crc_type}",
                    f"CW{codeword_index}: CB CRC type={coding_meta.code_block_crc_type or 'not applied'}",
                ]
            )
            for block_index in range(int(coding_meta.code_block_count)):
                payload_length = int(coding_meta.code_block_payload_lengths[block_index]) if block_index < len(coding_meta.code_block_payload_lengths) else 0
                with_crc_length = int(coding_meta.code_block_with_crc_lengths[block_index]) if block_index < len(coding_meta.code_block_with_crc_lengths) else payload_length
                mother_length = int(coding_meta.mother_block_lengths[block_index]) if block_index < len(coding_meta.mother_block_lengths) else with_crc_length
                lines.append(
                    f"CW{codeword_index}.CB{block_index}: payload={payload_length} bits, with_crc={with_crc_length} bits, mother={mother_length} bits"
                )
        return "\n".join(lines)

    @staticmethod
    def _llr_block_summary_text(blocks: tuple[np.ndarray, ...], title: str) -> str:
        if not blocks:
            return f"{title}: no block structure available"
        lines = [title]
        for index, block in enumerate(blocks):
            view = np.asarray(block)
            mean_abs = float(np.mean(np.abs(view))) if view.size else 0.0
            lines.append(f"CB{index}: length={view.size}, mean|LLR|={mean_abs:.4g}")
        return "\n".join(lines)

    @staticmethod
    def _code_block_crc_status_text(statuses: tuple[bool, ...]) -> str:
        if not statuses:
            return "Single code block path: no separate CB CRC decisions."
        return "\n".join(f"CB{index}: {'PASS' if bool(status) else 'FAIL'}" for index, status in enumerate(statuses))

    @staticmethod
    def _allocation_maps(result: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        tx_meta = result["tx"].metadata
        numerology = tx_meta.numerology
        allocation_map = np.zeros((numerology.symbols_per_slot, numerology.active_subcarriers), dtype=np.float32)
        channel_type = str(getattr(tx_meta, "channel_type", "data")).lower()
        if str(getattr(tx_meta, "direction", "downlink")).lower() == "downlink" and channel_type in {"control", "pdcch"}:
            from phy.resource_grid import ResourceGrid

            helper = ResourceGrid(
                numerology,
                tx_meta.allocation,
                spatial_layout=tx_meta.spatial_layout,
                slot_index=int(getattr(tx_meta, "slot_index", 0)),
                physical_cell_id=int(tx_meta.ssb.get("physical_cell_id", 0)),
                ssb_block_index=int(tx_meta.ssb.get("ssb_block_index", 0)),
            )
            coreset_positions = helper.coreset_positions()
            if coreset_positions.size:
                allocation_map[coreset_positions[:, 0], coreset_positions[:, 1]] = 1.0
        elif str(getattr(tx_meta, "direction", "downlink")).lower() == "downlink" and channel_type in {"pbch", "broadcast"}:
            from phy.resource_grid import ResourceGrid

            helper = ResourceGrid(
                numerology,
                tx_meta.allocation,
                spatial_layout=tx_meta.spatial_layout,
                slot_index=int(getattr(tx_meta, "slot_index", 0)),
                physical_cell_id=int(tx_meta.ssb.get("physical_cell_id", 0)),
                ssb_block_index=int(tx_meta.ssb.get("ssb_block_index", 0)),
            )
            ssb_positions = helper.ssb_positions(force_active=True)
            if ssb_positions.size:
                allocation_map[ssb_positions[:, 0], ssb_positions[:, 1]] = 1.0
        positions = tx_meta.mapping.positions
        if positions.size:
            allocation_map[positions[:, 0], positions[:, 1]] = 2.0
        dmrs_positions = tx_meta.dmrs["positions"]
        dmrs_mask = np.zeros_like(allocation_map)
        if dmrs_positions.size:
            allocation_map[dmrs_positions[:, 0], dmrs_positions[:, 1]] = 3.0
            dmrs_mask[dmrs_positions[:, 0], dmrs_positions[:, 1]] = 1.0
        pbch_dmrs_positions = np.asarray(tx_meta.ssb.get("pbch_dmrs_positions", np.zeros((0, 2), dtype=int)), dtype=int)
        if pbch_dmrs_positions.size:
            allocation_map[pbch_dmrs_positions[:, 0], pbch_dmrs_positions[:, 1]] = 3.0
            dmrs_mask[pbch_dmrs_positions[:, 0], pbch_dmrs_positions[:, 1]] = 1.0
        csi_rs_positions = tx_meta.csi_rs["positions"]
        if csi_rs_positions.size:
            allocation_map[csi_rs_positions[:, 0], csi_rs_positions[:, 1]] = 4.0
        srs_positions = tx_meta.srs["positions"]
        if srs_positions.size:
            allocation_map[srs_positions[:, 0], srs_positions[:, 1]] = 5.0
        ptrs_positions = tx_meta.ptrs["positions"]
        if ptrs_positions.size:
            allocation_map[ptrs_positions[:, 0], ptrs_positions[:, 1]] = 6.0
        return allocation_map, dmrs_mask

    @staticmethod
    def _spectrum_payload(waveform: np.ndarray, sample_rate: float, nfft: int = 4096) -> dict[str, Any]:
        view = np.asarray(waveform).reshape(-1)[:nfft]
        spectrum = np.zeros(nfft, dtype=np.complex128) if view.size == 0 else np.fft.fftshift(np.fft.fft(view, n=nfft))
        freqs = np.linspace(-sample_rate / 2.0, sample_rate / 2.0, spectrum.size) / 1e6
        return {"x": freqs, "y": 20.0 * np.log10(np.abs(spectrum) + 1e-9), "x_label": "Frequency (MHz)", "y_label": "Magnitude (dB)"}

    @staticmethod
    def _timing_metric_payload(waveform: np.ndarray, fft_size: int, cp_length: int, search_window: int) -> dict[str, Any]:
        view = np.asarray(waveform, dtype=np.complex128)
        if view.ndim > 1:
            view = view[0]
        symbol_length = fft_size + cp_length
        offsets = []
        metrics = []
        for offset in range(max(search_window, 1)):
            if offset + symbol_length >= view.size:
                break
            metric = 0.0
            valid_symbols = 0
            for symbol_index in range(4):
                start = offset + symbol_index * symbol_length
                if start + symbol_length > view.size:
                    break
                cp = view[start : start + cp_length]
                tail = view[start + fft_size : start + fft_size + cp_length]
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
        view = np.asarray(waveform, dtype=np.complex128)
        if view.ndim > 1:
            view = view[0]
        symbol_length = fft_size + cp_length
        phases = []
        magnitudes = []
        symbol_indices = []
        for symbol_index in range(symbols_to_average):
            start = symbol_index * symbol_length
            end = start + symbol_length
            if end > view.size:
                break
            cp = view[start : start + cp_length]
            tail = view[start + fft_size : start + fft_size + cp_length]
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
                    [14, 165, 233, 255],
                    [251, 191, 36, 255],
                    [56, 189, 248, 255],
                    [244, 114, 182, 255],
                    [168, 85, 247, 255],
                    [16, 185, 129, 255],
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
