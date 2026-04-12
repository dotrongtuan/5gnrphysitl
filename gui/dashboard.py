from __future__ import annotations

from PyQt5.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DashboardPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kpi_table = QTableWidget(0, 2)
        self.kpi_table.setHorizontalHeaderLabels(["KPI", "Value"])
        self.kpi_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.note_view = QPlainTextEdit()
        self.note_view.setReadOnly(True)

        layout = QVBoxLayout(self)
        kpi_group = QGroupBox("KPI")
        kpi_layout = QVBoxLayout(kpi_group)
        kpi_layout.addWidget(self.kpi_table)

        notes_group = QGroupBox("Warnings / Assumptions")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.addWidget(QLabel("Runtime notes for simplified models and environment constraints."))
        notes_layout.addWidget(self.note_view)

        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_view)

        layout.addWidget(kpi_group, stretch=2)
        layout.addWidget(notes_group, stretch=2)
        layout.addWidget(log_group, stretch=3)

    def update_kpis(self, kpis: dict) -> None:
        self.kpi_table.setRowCount(len(kpis))
        for row, (key, value) in enumerate(kpis.items()):
            self.kpi_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.kpi_table.setItem(row, 1, QTableWidgetItem(f"{value:.6g}" if isinstance(value, (int, float)) else str(value)))

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def set_notes(self, notes: list[str]) -> None:
        self.note_view.setPlainText("\n".join(notes))
