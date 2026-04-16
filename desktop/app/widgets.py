from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
)


def configure_data_table(
    table: QTableWidget,
    *,
    selection_mode: QAbstractItemView.SelectionMode = QAbstractItemView.SingleSelection,
) -> None:
    """Apply a consistent read-only table setup across the app."""
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(selection_mode)
    table.setAlternatingRowColors(False)
    table.setWordWrap(False)
    table.setCornerButtonEnabled(False)
    table.setSortingEnabled(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MetricSubtitle")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        layout.addStretch()


class SectionCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("SectionCard")
        self.layout = QVBoxLayout(self)
        header = QLabel(title)
        header.setObjectName("SectionTitle")
        self.layout.addWidget(header)


class DetailBox(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setObjectName("PreviewBox")
        self.setReadOnly(True)
        self.setMinimumHeight(180)


class NotificationBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NotificationBanner")
        self.setProperty("level", "info")
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        self.message_label = QLabel("")
        self.message_label.setObjectName("NotificationText")
        self.message_label.setWordWrap(True)

        self.close_button = QPushButton("Dismiss")
        self.close_button.setObjectName("NotificationClose")
        self.close_button.clicked.connect(self.hide)

        layout.addWidget(self.message_label, 1)
        layout.addWidget(self.close_button)
        self.hide()

    def show_message(self, message: str, level: str = "info", timeout_ms: int = 3500):
        self.message_label.setText(message)
        self.setProperty("level", level)
        self.style().unpolish(self)
        self.style().polish(self)
        self.show()
        self.raise_()
        self.hide_timer.start(timeout_ms)
