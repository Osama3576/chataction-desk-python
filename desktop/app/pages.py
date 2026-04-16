from __future__ import annotations

import requests
from PySide6.QtCore import QDate, QItemSelectionModel, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .widgets import (
    DetailBox,
    MetricCard,
    SectionCard,
    configure_data_table,
)

ACTION_RELATED_PAGES = (
    "dashboard",
    "review",
    "tasks",
    "conversations",
    "contacts",
    "analytics",
)


class BasePage(QWidget):
    PAGE_KEY = ""
    DISPLAY_NAME = ""
    poll_enabled = True

    def __init__(self, app_state):
        super().__init__()
        self.app_state = app_state
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(18, 18, 18, 18)
        self.root.setSpacing(16)

    def blocks_auto_refresh(self) -> bool:
        return False

    def notify(self, message: str, level: str = "info", timeout_ms: int = 3500):
        self.app_state.notify(message, level, timeout_ms)

    def confirm_action(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def run_action(
        self,
        action,
        *,
        success_message: str | None = None,
        dirty_pages: tuple[str, ...] = (),
        refresh_current: bool = True,
    ):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = action()
        except Exception as exc:
            self.notify(str(exc), "error", 5000)
            return None
        finally:
            QApplication.restoreOverrideCursor()

        if dirty_pages:
            self.app_state.mark_dirty(*dirty_pages)
        if refresh_current:
            self.app_state.refresh_current_page(force=True, silent=True, allow_paused=True)
        if success_message:
            self.notify(success_message, "success")
        return result

    def selected_row_value(self, table: QTableWidget, column: int = 0):
        selection_model = table.selectionModel()
        if selection_model is not None:
            selected_rows = selection_model.selectedRows(column)
            if selected_rows:
                row = selected_rows[0].row()
            else:
                row = table.currentRow()
        else:
            row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, column)
        return item.text() if item is not None else None

    def selected_row_values(self, table: QTableWidget, column: int = 0, cast=None):
        selection_model = table.selectionModel()
        if selection_model is None:
            return []
        values = []
        for index in selection_model.selectedRows(column):
            item = table.item(index.row(), column)
            if item is None:
                continue
            value = item.text()
            values.append(cast(value) if cast is not None else value)
        return values

    def populate_table(
        self,
        table: QTableWidget,
        items: list[dict],
        row_values,
        *,
        selected_key=None,
        selected_keys=None,
        key_getter=None,
        auto_select_first: bool = True,
    ):
        selected_rows: list[int] = []
        wanted_keys = set(selected_keys or [])
        if selected_key is not None:
            wanted_keys.add(selected_key)
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.clearContents()
            table.setRowCount(len(items))
            for row_index, item in enumerate(items):
                values = row_values(item)
                for col_index, value in enumerate(values):
                    cell = QTableWidgetItem("" if value is None else str(value))
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row_index, col_index, cell)
                if key_getter is not None and wanted_keys and key_getter(item) in wanted_keys:
                    selected_rows.append(row_index)

            table.clearSelection()
            if selected_rows:
                select_flags = QItemSelectionModel.Select | QItemSelectionModel.Rows
                for row_index in selected_rows:
                    index = table.model().index(row_index, 0)
                    table.selectionModel().select(index, select_flags)
                table.setCurrentCell(selected_rows[0], 0)
            elif items and auto_select_first:
                table.selectRow(0)
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()


class DashboardPage(BasePage):
    PAGE_KEY = "dashboard"
    DISPLAY_NAME = "Dashboard"

    def __init__(self, app_state):
        super().__init__(app_state)
        row = QHBoxLayout()
        self.review_card = MetricCard("Review Queue", "0", "Pending detections")
        self.active_card = MetricCard("Active Tasks", "0", "Needs attention")
        self.completed_card = MetricCard("Completed", "0", "Finished tasks")
        self.conversation_card = MetricCard("Conversations", "0", "Tracked threads")
        for card in [self.review_card, self.active_card, self.completed_card, self.conversation_card]:
            row.addWidget(card)
        self.root.addLayout(row)

        bottom = QHBoxLayout()
        self.recent_panel = SectionCard("Recent Detections")
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(["Type", "Title", "Confidence", "Status"])
        configure_data_table(self.recent_table)
        self.recent_panel.layout.addWidget(self.recent_table)

        self.conv_panel = SectionCard("Recent Conversations")
        self.conv_list = QListWidget()
        self.conv_panel.layout.addWidget(self.conv_list)

        bottom.addWidget(self.recent_panel, 2)
        bottom.addWidget(self.conv_panel, 1)
        self.root.addLayout(bottom, 1)

    def refresh(self):
        data = self.app_state.client.get("/api/dashboard")
        summary = data["summary"]
        self.review_card.findChildren(QLabel)[1].setText(str(summary["review_pending"]))
        self.active_card.findChildren(QLabel)[1].setText(str(summary["tasks_active"]))
        self.completed_card.findChildren(QLabel)[1].setText(str(summary["tasks_completed"]))
        self.conversation_card.findChildren(QLabel)[1].setText(str(summary["total_conversations"]))

        recent = data["recent_review"]
        self.populate_table(
            self.recent_table,
            recent,
            lambda item: [item["item_type"], item["title"], item["confidence_label"], item["status"]],
            auto_select_first=False,
        )

        self.conv_list.clear()
        for item in data["recent_conversations"]:
            self.conv_list.addItem(f"{item['contact_name']} - {item['last_message_at']}")


class ReviewQueuePage(BasePage):
    PAGE_KEY = "review"
    DISPLAY_NAME = "Review Queue"

    def __init__(self, app_state):
        super().__init__(app_state)
        self.items: list[dict] = []
        self._edit_mode = False

        filters = QHBoxLayout()
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Task", "Follow-up", "Decision", "Open Question"])
        self.conf_filter = QComboBox()
        self.conf_filter.addItems(["All", "High", "Medium", "Low"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search detections...")
        btn = QPushButton("Apply Filters")
        btn.clicked.connect(self.refresh)
        filters.addWidget(self.type_filter)
        filters.addWidget(self.conf_filter)
        filters.addWidget(self.search, 1)
        filters.addWidget(btn)
        self.root.addLayout(filters)

        splitter = QSplitter()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Type", "Title", "Contact", "Confidence", "Status"])
        configure_data_table(self.table)
        self.table.itemSelectionChanged.connect(self.show_selected)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(10)

        self.detail = DetailBox()
        self.title_edit = QLineEdit()
        self.type_edit = QComboBox()
        self.type_edit.addItems(["Task", "Follow-up", "Decision", "Open Question"])
        self.priority_edit = QComboBox()
        self.priority_edit.addItems(["Low", "Medium", "High"])
        self.due_checkbox = QCheckBox("Set due date")
        self.due_checkbox.toggled.connect(self._sync_due_edit_state)
        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDate(QDate.currentDate())
        self.notes_edit = QTextEdit()

        self.edit_button = QPushButton("Edit Details")
        self.edit_button.clicked.connect(self.begin_edit)
        self.cancel_button = QPushButton("Cancel Edit")
        self.cancel_button.clicked.connect(self.cancel_edit)
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.setObjectName("PrimaryButton")
        self.confirm_button.clicked.connect(self.confirm_selected)
        self.reject_button = QPushButton("Reject")
        self.reject_button.clicked.connect(self.reject_selected)

        right_layout.addWidget(QLabel("Detection Details"))
        right_layout.addWidget(self.detail)
        for label, widget in [
            ("Title", self.title_edit),
            ("Type", self.type_edit),
            ("Priority", self.priority_edit),
        ]:
            right_layout.addWidget(QLabel(label))
            right_layout.addWidget(widget)
        right_layout.addWidget(self.due_checkbox)
        right_layout.addWidget(self.due_edit)
        right_layout.addWidget(QLabel("Notes"))
        right_layout.addWidget(self.notes_edit)

        action_row = QHBoxLayout()
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.confirm_button)
        action_row.addWidget(self.reject_button)
        right_layout.addLayout(action_row)

        splitter.addWidget(self.table)
        splitter.addWidget(right)
        splitter.setSizes([900, 420])
        self.root.addWidget(splitter, 1)

        self._set_edit_mode(False)
        self._set_detail_available(False)

    def blocks_auto_refresh(self) -> bool:
        return self._edit_mode

    def _set_detail_available(self, available: bool):
        self.edit_button.setEnabled(available)
        self.confirm_button.setEnabled(available)
        self.reject_button.setEnabled(available)
        if not available:
            self.cancel_button.setEnabled(False)

    def _set_edit_mode(self, editable: bool):
        self._edit_mode = editable
        self.title_edit.setReadOnly(not editable)
        self.type_edit.setEnabled(editable)
        self.priority_edit.setEnabled(editable)
        self.notes_edit.setReadOnly(not editable)
        self.due_checkbox.setEnabled(editable)
        self.cancel_button.setEnabled(editable)
        self._sync_due_edit_state()

    def _sync_due_edit_state(self):
        self.due_edit.setEnabled(self._edit_mode and self.due_checkbox.isChecked())

    def filtered_items(self):
        items = self.items
        selected_type = self.type_filter.currentText()
        selected_confidence = self.conf_filter.currentText()
        query = self.search.text().strip().lower()
        if selected_type != "All":
            items = [item for item in items if item["item_type"] == selected_type]
        if selected_confidence != "All":
            items = [item for item in items if item["confidence_label"] == selected_confidence]
        if query:
            items = [
                item for item in items
                if query in item["title"].lower()
                or query in item["contact_name"].lower()
                or query in item["source_preview"].lower()
            ]
        return items

    def current_item_id(self):
        value = self.selected_row_value(self.table)
        return int(value) if value is not None else None

    def current_item(self):
        item_id = self.current_item_id()
        if item_id is None:
            return None
        for item in self.filtered_items():
            if item["id"] == item_id:
                return item
        return None

    def clear_detail(self):
        self.detail.setPlainText("Select a detection to preview it here.")
        self.title_edit.clear()
        self.type_edit.setCurrentIndex(0)
        self.priority_edit.setCurrentText("Medium")
        self.due_checkbox.setChecked(False)
        self.notes_edit.clear()
        self._set_edit_mode(False)
        self._set_detail_available(False)

    def refresh(self):
        selected_id = self.current_item_id()
        self.items = self.app_state.client.get("/api/review-items")
        items = self.filtered_items()
        self.populate_table(
            self.table,
            items,
            lambda item: [
                item["id"],
                item["item_type"],
                item["title"],
                item["contact_name"],
                item["confidence_label"],
                item["status"],
            ],
            selected_key=selected_id,
            key_getter=lambda item: item["id"],
        )
        if items:
            self.show_selected()
        else:
            self.clear_detail()

    def show_selected(self):
        item = self.current_item()
        if not item:
            self.clear_detail()
            return

        self.detail.setPlainText(
            f"Type: {item['item_type']}\n"
            f"Contact: {item['contact_name']}\n"
            f"Conversation: {item['conversation_title']}\n"
            f"Confidence: {item['confidence_label']} ({item['confidence_score']})\n"
            f"Status: {item['status']}\n"
            f"Due Date: {item.get('due_date') or '-'}\n\n"
            f"Source: {item['source_preview']}\n\n"
            f"Summary:\n{item['summary']}"
        )
        self.title_edit.setText(item["title"])
        self.type_edit.setCurrentText(item["item_type"])
        self.priority_edit.setCurrentText(item.get("priority", "Medium"))
        self.due_checkbox.setChecked(bool(item.get("due_date")))
        if item.get("due_date"):
            qdate = QDate.fromString(item["due_date"], "yyyy-MM-dd")
            if qdate.isValid():
                self.due_edit.setDate(qdate)
        else:
            self.due_edit.setDate(QDate.currentDate())
        self.notes_edit.setPlainText(item.get("notes") or "")
        self._set_edit_mode(False)
        self._set_detail_available(True)

    def begin_edit(self):
        if not self.current_item():
            self.notify("Select a detection before editing.", "warning")
            return
        self._set_edit_mode(True)
        self.notify("Edit mode enabled for the selected detection.", "info", 2500)

    def cancel_edit(self):
        self.show_selected()
        self.notify("Edit mode cancelled.", "info", 2200)

    def build_payload(self):
        item = self.current_item()
        if not item:
            return None
        title = self.title_edit.text().strip()
        if not title:
            self.notify("Title cannot be empty.", "error", 4000)
            return None
        return {
            "title": title,
            "type": self.type_edit.currentText(),
            "priority": self.priority_edit.currentText(),
            "due_date": self.due_edit.date().toString("yyyy-MM-dd") if self.due_checkbox.isChecked() else None,
            "notes": self.notes_edit.toPlainText().strip(),
        }

    def confirm_selected(self):
        item = self.current_item()
        if not item:
            self.notify("Select a detection before confirming it.", "warning")
            return
        payload = self.build_payload()
        if payload is None:
            return
        self.run_action(
            lambda: self.app_state.client.post(f"/api/review-items/{item['id']}/confirm", payload),
            success_message="Detection confirmed successfully.",
            dirty_pages=ACTION_RELATED_PAGES,
        )

    def reject_selected(self):
        item = self.current_item()
        if not item:
            self.notify("Select a detection before rejecting it.", "warning")
            return
        if not self.confirm_action("Reject Detection", "Reject the selected detection?"):
            return
        self.run_action(
            lambda: self.app_state.client.post(f"/api/review-items/{item['id']}/reject", {}),
            success_message="Detection rejected.",
            dirty_pages=ACTION_RELATED_PAGES,
        )


class TasksPage(BasePage):
    PAGE_KEY = "tasks"
    DISPLAY_NAME = "Tasks"
    FOOTER_HEIGHT = 110

    def __init__(self, app_state):
        super().__init__(app_state)
        self._suspend_action_updates = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(0, 0)

        self.content_region = QWidget()
        self.content_region.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_region.setMinimumSize(0, 0)
        content_layout = QVBoxLayout(self.content_region)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabs.setMinimumSize(0, 0)
        self.active_table = self._make_table()
        self.completed_table = self._make_table()
        self.tabs.addTab(self._wrap_table(self.active_table), "Active Tasks")
        self.tabs.addTab(self._wrap_table(self.completed_table), "Completed / Archived")
        self.tabs.currentChanged.connect(self.update_action_state)
        content_layout.addWidget(self.tabs, 1)
        self.root.addWidget(self.content_region, 1)

        self.footer = QFrame()
        self.footer.setObjectName("PageFooter")
        self.footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.footer.setFixedHeight(self.FOOTER_HEIGHT)

        self.selection_summary = QLabel("Select one or more task rows to manage them.")
        self.selection_summary.setObjectName("SelectionSummary")
        self.selection_summary.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.selection_summary.setWordWrap(False)
        self.selection_summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        footer_layout = QVBoxLayout(self.footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.setSpacing(10)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.addWidget(self.selection_summary, 1)
        footer_layout.addLayout(summary_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)
        action_row.addStretch()
        self.complete_button = QPushButton("Complete Selected")
        self.complete_button.setObjectName("PrimaryButton")
        self.complete_button.clicked.connect(self.complete_selected)
        self.reopen_button = QPushButton("Reopen Selected")
        self.reopen_button.clicked.connect(self.reopen_selected)
        self.archive_button = QPushButton("Archive Selected")
        self.archive_button.clicked.connect(self.archive_selected)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)
        for button in [self.complete_button, self.reopen_button, self.archive_button, self.delete_button]:
            button.setMinimumHeight(40)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        action_row.addWidget(self.complete_button)
        action_row.addWidget(self.reopen_button)
        action_row.addWidget(self.archive_button)
        action_row.addWidget(self.delete_button)
        footer_layout.addLayout(action_row)
        self.root.addWidget(self.footer, 0)
        self.update_action_state()

    def _make_table(self):
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(["ID", "Type", "Title", "Contact", "Due Date", "Priority", "Status", "Conversation"])
        configure_data_table(table, selection_mode=QAbstractItemView.ExtendedSelection)
        table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table.setMinimumSize(0, 0)
        table.itemSelectionChanged.connect(self.update_action_state)
        return table

    def _wrap_table(self, table: QTableWidget):
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        page.setMinimumSize(0, 0)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(table)
        return page

    def minimumSizeHint(self):
        return QSize(720, 420)

    def sizeHint(self):
        return QSize(1120, 720)

    def _selected_task_ids(self, table: QTableWidget):
        return self.selected_row_values(table, cast=int)

    def _current_table(self):
        return self.active_table if self.tabs.currentIndex() == 0 else self.completed_table

    def _has_selected_tasks(self):
        return bool(self._selected_task_ids(self.active_table) or self._selected_task_ids(self.completed_table))

    def _selection_summary_text(self, count: int, section_label: str):
        if count <= 0:
            return "Select one or more task rows to manage them."
        noun = "task" if count == 1 else "tasks"
        return f"{count} {section_label} {noun} selected."

    def blocks_auto_refresh(self) -> bool:
        return self._suspend_action_updates or self._has_selected_tasks()

    def update_action_state(self):
        if self._suspend_action_updates:
            return
        active_tab = self.tabs.currentIndex() == 0
        current_table = self._current_table()
        selected_ids = self._selected_task_ids(current_table)
        selected_count = len(selected_ids)
        section_label = "active" if active_tab else "completed"
        summary_text = self._selection_summary_text(selected_count, section_label)
        self.selection_summary.setText(summary_text)
        self.selection_summary.setToolTip(summary_text)

        self.complete_button.setEnabled(active_tab and selected_count > 0)
        self.archive_button.setEnabled(active_tab and selected_count > 0)
        self.reopen_button.setEnabled((not active_tab) and selected_count > 0)
        self.delete_button.setEnabled(selected_count > 0)

    def _run_task_batch(
        self,
        task_ids: list[int],
        action,
        *,
        success_message: str,
        dirty_pages: tuple[str, ...] = ("dashboard", "tasks", "conversations", "contacts", "analytics"),
    ):
        if not task_ids:
            return

        def do_action():
            for task_id in task_ids:
                action(task_id)

        self.run_action(
            do_action,
            success_message=success_message,
            dirty_pages=dirty_pages,
        )

    def _selected_count_label(self, count: int):
        return "1 task" if count == 1 else f"{count} tasks"

    def _populate_task_table(self, table: QTableWidget, items: list[dict], selected_keys: list[int]):
        vertical_scroll = table.verticalScrollBar().value()
        horizontal_scroll = table.horizontalScrollBar().value()
        self.populate_table(
            table,
            items,
            lambda item: [
                item["id"],
                item["item_type"],
                item["title"],
                item["contact_name"],
                item.get("due_date") or "-",
                item["priority"],
                item["status"],
                item["conversation_title"],
            ],
            selected_keys=selected_keys,
            key_getter=lambda item: item["id"],
            auto_select_first=False,
        )
        table.verticalScrollBar().setValue(vertical_scroll)
        table.horizontalScrollBar().setValue(horizontal_scroll)

    def refresh(self):
        tasks = self.app_state.client.get("/api/tasks")
        active = [task for task in tasks if task["status"] in ("Pending", "In Progress")]
        completed = [task for task in tasks if task["status"] in ("Completed", "Archived")]
        active_selected = self._selected_task_ids(self.active_table)
        completed_selected = self._selected_task_ids(self.completed_table)
        self._suspend_action_updates = True
        try:
            self._populate_task_table(self.active_table, active, active_selected)
            self._populate_task_table(self.completed_table, completed, completed_selected)
        finally:
            self._suspend_action_updates = False
        self.update_action_state()

    def complete_selected(self):
        task_ids = self._selected_task_ids(self.active_table)
        if not task_ids:
            self.notify("Select one or more active tasks first.", "warning")
            return
        label = self._selected_count_label(len(task_ids))
        self._run_task_batch(
            task_ids,
            lambda task_id: self.app_state.client.post(f"/api/tasks/{task_id}/complete", {}),
            success_message=f"{label} marked as completed.",
        )

    def reopen_selected(self):
        task_ids = self._selected_task_ids(self.completed_table)
        if not task_ids:
            self.notify("Select one or more completed tasks first.", "warning")
            return
        label = self._selected_count_label(len(task_ids))
        self._run_task_batch(
            task_ids,
            lambda task_id: self.app_state.client.post(f"/api/tasks/{task_id}/reopen", {}),
            success_message=f"{label} reopened.",
        )

    def archive_selected(self):
        task_ids = self._selected_task_ids(self.active_table)
        if not task_ids:
            self.notify("Select one or more active tasks before archiving them.", "warning")
            return
        label = self._selected_count_label(len(task_ids))
        if not self.confirm_action("Archive Tasks", f"Archive {label}?"):
            return
        self._run_task_batch(
            task_ids,
            lambda task_id: self.app_state.client.post(f"/api/tasks/{task_id}/archive", {}),
            success_message=f"{label} archived.",
        )

    def delete_selected(self):
        current_table = self._current_table()
        task_ids = self._selected_task_ids(current_table)
        if not task_ids:
            self.notify("Select one or more tasks before deleting them.", "warning")
            return
        label = self._selected_count_label(len(task_ids))
        if not self.confirm_action("Delete Tasks", f"Permanently delete {label}? This cannot be undone."):
            return
        self._run_task_batch(
            task_ids,
            lambda task_id: self.app_state.client.delete(f"/api/tasks/{task_id}"),
            success_message=f"{label} deleted.",
        )


class ConversationsPage(BasePage):
    PAGE_KEY = "conversations"
    DISPLAY_NAME = "Conversations"

    def __init__(self, app_state):
        super().__init__(app_state)
        self.items = []
        self.current_detail_id = None

        splitter = QSplitter()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Contact", "Channel", "Last Activity"])
        configure_data_table(self.table)
        self.table.itemSelectionChanged.connect(self.load_selected)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.header = QLabel("Conversation detail")
        self.messages = QTextEdit()
        self.messages.setObjectName("PreviewBox")
        self.messages.setReadOnly(True)
        self.linked = QTextEdit()
        self.linked.setObjectName("PreviewBox")
        self.linked.setReadOnly(True)
        right_layout.addWidget(self.header)
        right_layout.addWidget(QLabel("Messages"))
        right_layout.addWidget(self.messages, 2)
        right_layout.addWidget(QLabel("Linked Actions"))
        right_layout.addWidget(self.linked, 1)

        splitter.addWidget(self.table)
        splitter.addWidget(right)
        splitter.setSizes([700, 680])
        self.root.addWidget(splitter, 1)

    def selected_conversation_id(self):
        value = self.selected_row_value(self.table)
        return int(value) if value is not None else None

    def clear_detail(self):
        self.current_detail_id = None
        self.header.setText("Conversation detail")
        self.messages.clear()
        self.linked.clear()

    def refresh(self):
        selected_id = self.selected_conversation_id()
        self.items = self.app_state.client.get("/api/conversations")
        self.populate_table(
            self.table,
            self.items,
            lambda item: [item["id"], item["contact_name"], item["channel"], item.get("last_message_at") or "-"],
            selected_key=selected_id,
            key_getter=lambda item: item["id"],
        )
        if self.items:
            self.load_selected(force=True)
        else:
            self.clear_detail()

    def load_selected(self, force: bool = False):
        conversation_id = self.selected_conversation_id()
        if conversation_id is None:
            self.clear_detail()
            return
        if self.current_detail_id == conversation_id and not force:
            return
        data = self.app_state.client.get(f"/api/conversations/{conversation_id}")
        conversation = data["conversation"]
        self.current_detail_id = conversation_id
        self.header.setText(f"{conversation['contact_name']} - {conversation['title']}")
        self.messages.setPlainText("\n\n".join([f"[{message['message_time']}]\n{message['body']}" for message in data["messages"]]))
        linked = []
        for item in data["review_items"]:
            linked.append(f"{item['item_type']} - {item['status']} - {item['title']}")
        for task in data["tasks"]:
            linked.append(f"TASK - {task['status']} - {task['title']}")
        self.linked.setPlainText("\n".join(linked))


class ContactsPage(BasePage):
    PAGE_KEY = "contacts"
    DISPLAY_NAME = "Contacts"

    def __init__(self, app_state):
        super().__init__(app_state)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Name", "Identifier", "Channel", "Active Tasks", "Completed", "Pending Review", "Last Activity"])
        configure_data_table(self.table)
        self.root.addWidget(self.table, 1)

    def refresh(self):
        items = self.app_state.client.get("/api/contacts")
        selected_contact_id = self.selected_row_value(self.table, 1)
        self.populate_table(
            self.table,
            items,
            lambda item: [
                item["name"],
                item["external_id"],
                item["channel"],
                item["active_tasks"],
                item["completed_tasks"],
                item["pending_reviews"],
                item.get("last_activity") or "-",
            ],
            selected_key=selected_contact_id,
            key_getter=lambda item: item["external_id"],
        )


class AnalyticsPage(BasePage):
    PAGE_KEY = "analytics"
    DISPLAY_NAME = "Analytics"

    def __init__(self, app_state):
        super().__init__(app_state)
        row = QHBoxLayout()
        self.type_card = MetricCard("Actions By Type", "-", "Detection categories")
        self.conf_card = MetricCard("Confidence", "-", "Quality mix")
        self.task_card = MetricCard("Task Status", "-", "Workflow outcome")
        self.load_card = MetricCard("Top Contact Load", "-", "Most task-heavy contact")
        for card in [self.type_card, self.conf_card, self.task_card, self.load_card]:
            row.addWidget(card)
        self.root.addLayout(row)
        self.box = QTextEdit()
        self.box.setObjectName("PreviewBox")
        self.box.setReadOnly(True)
        self.root.addWidget(self.box, 1)

    def refresh(self):
        data = self.app_state.client.get("/api/analytics")
        self.type_card.findChildren(QLabel)[1].setText(str(sum(item["total"] for item in data["actions_by_type"])))
        self.conf_card.findChildren(QLabel)[1].setText(", ".join(f"{item['label']}:{item['total']}" for item in data["confidence_distribution"][:3]) or "-")
        self.task_card.findChildren(QLabel)[1].setText(", ".join(f"{item['label']}:{item['total']}" for item in data["task_status_distribution"][:3]) or "-")
        self.load_card.findChildren(QLabel)[1].setText(data["contact_load"][0]["label"] if data["contact_load"] else "-")

        lines = []
        for key, title in [
            ("actions_by_type", "Actions By Type"),
            ("confidence_distribution", "Confidence Distribution"),
            ("task_status_distribution", "Task Status"),
            ("contact_load", "Contact Load"),
        ]:
            lines.append(title)
            for item in data[key]:
                lines.append(f"  - {item['label']}: {item['total']}")
            lines.append("")
        self.box.setPlainText("\n".join(lines))


class RulesPage(BasePage):
    PAGE_KEY = "rules"
    DISPLAY_NAME = "AI Extraction"
    poll_enabled = False

    def __init__(self, app_state):
        super().__init__(app_state)
        self._is_loading = False
        self._has_unsaved_changes = False

        intro = QLabel(
            "Gemini checks each incoming message and decides whether it contains an order, task, follow-up, decision, or open question worth tracking."
        )
        intro.setWordWrap(True)
        self.root.addWidget(intro)

        self.enabled_box = QCheckBox("Enable AI extraction")
        self.model_input = QLineEdit()
        self.threshold_input = QLineEdit()
        self.context_input = QLineEdit()
        self.status_label = QLabel("API key status: unknown")
        self.status_label.setObjectName("MetricSubtitle")
        self.prompt_box = QPlainTextEdit()
        self.prompt_box.setPlaceholderText("System instruction for Gemini...")

        form = QFormLayout()
        form.addRow("Provider", QLabel("Google Gemini"))
        form.addRow("Status", self.status_label)
        form.addRow("Enabled", self.enabled_box)
        form.addRow("Model", self.model_input)
        form.addRow("Confidence Threshold", self.threshold_input)
        form.addRow("Context Messages", self.context_input)
        form.addRow("System Instruction", self.prompt_box)
        self.root.addLayout(form)

        hint = QLabel(
            "Set your Gemini API key in backend/.env using GEMINI_API_KEY. This page controls the live AI extraction behavior without bringing back the old keyword-rule workflow."
        )
        hint.setWordWrap(True)
        self.root.addWidget(hint)

        button_row = QHBoxLayout()
        save = QPushButton("Save AI Settings")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.save_rules)
        button_row.addWidget(save)
        button_row.addStretch()
        self.root.addLayout(button_row)

        self.enabled_box.stateChanged.connect(self.mark_dirty)
        self.model_input.textEdited.connect(self.mark_dirty)
        self.threshold_input.textEdited.connect(self.mark_dirty)
        self.context_input.textEdited.connect(self.mark_dirty)
        self.prompt_box.textChanged.connect(self.mark_dirty)

    def blocks_auto_refresh(self) -> bool:
        return self._has_unsaved_changes

    def mark_dirty(self, *_args):
        if self._is_loading:
            return
        self._has_unsaved_changes = True

    def refresh(self):
        if self._has_unsaved_changes:
            return
        self._is_loading = True
        try:
            settings = self.app_state.client.get("/api/ai-settings")
            self.enabled_box.setChecked(bool(settings.get("enabled", True)))
            self.model_input.setText(settings.get("model", "gemini-2.5-flash"))
            self.threshold_input.setText(str(settings.get("confidence_threshold", 0.58)))
            self.context_input.setText(str(settings.get("context_messages", 6)))
            self.prompt_box.setPlainText(settings.get("system_instruction", ""))
            if settings.get("api_key_configured"):
                self.status_label.setText("API key status: configured")
            else:
                self.status_label.setText("API key status: missing in backend/.env")
        finally:
            self._is_loading = False

    def save_rules(self):
        try:
            payload = {
                "enabled": self.enabled_box.isChecked(),
                "model": self.model_input.text().strip() or "gemini-2.5-flash",
                "confidence_threshold": float(self.threshold_input.text().strip() or 0.58),
                "context_messages": int(self.context_input.text().strip() or 6),
                "system_instruction": self.prompt_box.toPlainText().strip(),
            }
        except ValueError:
            self.notify("Confidence threshold must be a number and context messages must be an integer.", "error", 5000)
            return

        result = self.run_action(
            lambda: self.app_state.client.post("/api/ai-settings/update", payload),
            success_message="AI extraction settings updated successfully.",
            refresh_current=False,
        )
        if result is not None:
            self._has_unsaved_changes = False

class SettingsPage(BasePage):
    PAGE_KEY = "settings"
    DISPLAY_NAME = "Settings"
    poll_enabled = False

    DEFAULT_TEST_CONTACT_NAME = "Client Business"
    DEFAULT_TEST_CONTACT_ID = "923001234567"
    DEFAULT_TEST_MESSAGE = "Please send revised milestone summary kal tak and confirm final scope."

    def __init__(self, app_state):
        super().__init__(app_state)
        self._is_loading = False
        self._has_unsaved_changes = False
        self._seeded_test_defaults = False

        self.url_input = QLineEdit()
        self.appearance_input = QComboBox()
        self.appearance_input.addItems(["Dark", "Light"])
        self.name_input = QLineEdit()
        self.id_input = QLineEdit()
        self.channel_input = QComboBox()
        self.channel_input.addItems(["manual", "meta_whatsapp", "twilio_whatsapp"])
        self.msg_input = QTextEdit()

        form = QFormLayout()
        form.addRow("Backend URL", self.url_input)
        form.addRow("Appearance", self.appearance_input)
        form.addRow("Test Contact Name", self.name_input)
        form.addRow("Test Contact ID", self.id_input)
        form.addRow("Test Channel", self.channel_input)
        form.addRow("Test Message", self.msg_input)
        self.root.addLayout(form)

        row = QHBoxLayout()
        save = QPushButton("Save Settings")
        save.clicked.connect(self.save_settings)
        send = QPushButton("Send Test Event")
        send.setObjectName("PrimaryButton")
        send.clicked.connect(self.send_test)
        export_csv = QPushButton("Export Tasks CSV")
        export_csv.clicked.connect(lambda: self.export_file("/api/export/tasks.csv", "tasks_export.csv"))
        export_json = QPushButton("Export Tasks JSON")
        export_json.clicked.connect(lambda: self.export_file("/api/export/tasks.json", "tasks_export.json"))
        export_review = QPushButton("Export Review JSON")
        export_review.clicked.connect(lambda: self.export_file("/api/export/review-items.json", "review_items_export.json"))
        for widget in [save, send, export_csv, export_json, export_review]:
            row.addWidget(widget)
        row.addStretch()
        self.root.addLayout(row)
        self.root.addStretch()

        self.url_input.textEdited.connect(self.mark_dirty)
        self.name_input.textEdited.connect(self.mark_dirty)
        self.id_input.textEdited.connect(self.mark_dirty)
        self.channel_input.currentTextChanged.connect(self.mark_dirty)
        self.msg_input.textChanged.connect(self.mark_dirty)
        self.appearance_input.currentTextChanged.connect(self.preview_appearance)

    def blocks_auto_refresh(self) -> bool:
        return self._has_unsaved_changes

    def mark_dirty(self, *_args):
        if self._is_loading:
            return
        self._has_unsaved_changes = True

    def preview_appearance(self, theme_name: str):
        if self._is_loading:
            return
        self._has_unsaved_changes = True
        self.app_state.preview_theme(theme_name)

    def refresh(self):
        if self._has_unsaved_changes:
            return
        self._is_loading = True
        try:
            self.url_input.setText(self.app_state.client.base_url)
            self.appearance_input.setCurrentText(self.app_state.client.appearance)
            if not self._seeded_test_defaults:
                self.name_input.setText(self.DEFAULT_TEST_CONTACT_NAME)
                self.id_input.setText(self.DEFAULT_TEST_CONTACT_ID)
                self.channel_input.setCurrentText("manual")
                self.msg_input.setPlainText(self.DEFAULT_TEST_MESSAGE)
                self._seeded_test_defaults = True
        finally:
            self._is_loading = False

    def save_settings(self):
        backend_url = self.url_input.text().strip()
        if not backend_url:
            self.notify("Backend URL cannot be empty.", "error", 4000)
            return
        self.app_state.client.set_base_url(backend_url)
        self.app_state.apply_theme(self.appearance_input.currentText())
        self._has_unsaved_changes = False
        self.app_state.mark_dirty(*ACTION_RELATED_PAGES)
        self.notify("Settings updated successfully.", "success")

    def send_test(self):
        message_text = self.msg_input.toPlainText().strip()
        if not message_text:
            self.notify("Enter a test message before sending.", "error", 4000)
            return
        payload = {
            "channel": self.channel_input.currentText(),
            "contact_name": self.name_input.text().strip() or self.DEFAULT_TEST_CONTACT_NAME,
            "contact_id": self.id_input.text().strip() or self.DEFAULT_TEST_CONTACT_ID,
            "message_text": message_text,
            "timestamp": "2026-04-09T11:00:00",
        }
        self.run_action(
            lambda: self.app_state.client.post("/api/simulate-message", payload),
            success_message="Test event sent successfully.",
            dirty_pages=("dashboard", "review", "conversations", "contacts", "analytics"),
            refresh_current=False,
        )

    def export_file(self, endpoint: str, default_name: str):
        path, _ = QFileDialog.getSaveFileName(self, "Save Export", default_name)
        if not path:
            return

        def do_export():
            response = requests.get(f"{self.app_state.client.base_url}{endpoint}", timeout=15)
            response.raise_for_status()
            with open(path, "wb") as handle:
                handle.write(response.content)

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            do_export()
        except requests.RequestException:
            self.notify("Export failed. Check that the backend is available.", "error", 5000)
        except OSError as exc:
            self.notify(f"Export failed. {exc}", "error", 5000)
        else:
            self.notify(f"Export saved to {path}", "success", 4500)
        finally:
            QApplication.restoreOverrideCursor()
