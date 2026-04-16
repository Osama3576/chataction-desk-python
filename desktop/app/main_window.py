from __future__ import annotations

import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .api_client import ApiClient
from .pages import (
    AnalyticsPage,
    ContactsPage,
    ConversationsPage,
    DashboardPage,
    ReviewQueuePage,
    RulesPage,
    SettingsPage,
    TasksPage,
)
from .theme import get_theme_stylesheet
from .widgets import NotificationBanner


PAGE_REFRESH_INTERVALS = {
    "dashboard": 6.0,
    "review": 4.0,
    "tasks": 4.0,
    "conversations": 5.0,
    "contacts": 12.0,
    "analytics": 15.0,
    "rules": 20.0,
    "settings": 20.0,
}


class AppState:
    def __init__(self):
        self.client = ApiClient()
        self.pages: dict[str, QWidget] = {}
        self.current_page_key: str | None = None
        self.dirty_pages: set[str] = set()
        self.theme_callback = None
        self.notify_callback = None
        self._page_error_cache: dict[str, str] = {}
        self._last_refresh_at: dict[str, float] = {}

    def register_page(self, key: str, page: QWidget):
        self.pages[key] = page
        self.dirty_pages.add(key)

    def set_current_page(self, key: str):
        self.current_page_key = key

    def notify(self, message: str, level: str = "info", timeout_ms: int = 3500):
        if self.notify_callback:
            self.notify_callback(message, level, timeout_ms)

    def mark_dirty(self, *page_keys: str):
        keys = page_keys or tuple(self.pages.keys())
        for key in keys:
            if key in self.pages:
                self.dirty_pages.add(key)

    def _is_refresh_due(self, key: str) -> bool:
        interval = PAGE_REFRESH_INTERVALS.get(key, 8.0)
        last = self._last_refresh_at.get(key, 0.0)
        return (time.monotonic() - last) >= interval

    def refresh_page(self, key: str, force: bool = False, silent: bool = False, allow_paused: bool = False):
        page = self.pages.get(key)
        if page is None:
            return False
        if not allow_paused and hasattr(page, "blocks_auto_refresh") and page.blocks_auto_refresh():
            return False
        if not force and key not in self.dirty_pages and not self._is_refresh_due(key):
            return False
        try:
            page.refresh()
        except Exception as exc:
            self.dirty_pages.add(key)
            message = f"{getattr(page, 'DISPLAY_NAME', key)} could not refresh. {exc}"
            if not silent and self._page_error_cache.get(key) != message:
                self.notify(message, "error", 5000)
                self._page_error_cache[key] = message
            return False
        self.dirty_pages.discard(key)
        self._page_error_cache.pop(key, None)
        self._last_refresh_at[key] = time.monotonic()
        return True

    def refresh_current_page(self, force: bool = False, silent: bool = False, allow_paused: bool = False):
        key = self.current_page_key
        if not key:
            return False
        page = self.pages.get(key)
        if page is None:
            return False
        if not force and not getattr(page, "poll_enabled", True):
            return False
        return self.refresh_page(key, force=force, silent=silent, allow_paused=allow_paused)

    def preview_theme(self, theme_name: str):
        if self.theme_callback:
            self.theme_callback(theme_name)

    def apply_theme(self, theme_name: str):
        self.client.set_appearance(theme_name)
        self.preview_theme(theme_name)


class MainWindow(QMainWindow):
    NAV_ITEMS = [
        ("dashboard", "Dashboard", DashboardPage),
        ("review", "Review Queue", ReviewQueuePage),
        ("tasks", "Tasks", TasksPage),
        ("conversations", "Conversations", ConversationsPage),
        ("contacts", "Contacts", ContactsPage),
        ("analytics", "Analytics", AnalyticsPage),
        ("rules", "AI Extraction", RulesPage),
        ("settings", "Settings", SettingsPage),
    ]

    def __init__(self):
        super().__init__()
        self.app_state = AppState()
        self.app_state.theme_callback = self.apply_theme
        self.app_state.notify_callback = self.show_notification
        self._last_health_online: bool | None = None
        self._last_health_check = 0.0

        self.setWindowTitle("ChatAction Desk")
        self.resize(1540, 940)

        root = QWidget()
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(18, 20, 18, 20)
        brand = QLabel("ChatAction Desk")
        brand.setObjectName("BrandLabel")
        sub = QLabel("Hybrid AI + manual business chat automation workspace")
        sub.setObjectName("SidebarSubtext")
        s_layout.addWidget(brand)
        s_layout.addWidget(sub)
        s_layout.addSpacing(16)
        head = QLabel("Navigate")
        head.setObjectName("SidebarHeader")
        s_layout.addWidget(head)

        self.buttons: list[QPushButton] = []
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stack.setMinimumSize(0, 0)

        self.content_host = QWidget()
        self.content_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_host.setMinimumSize(0, 0)
        content_wrap = QVBoxLayout(self.content_host)
        content_wrap.setContentsMargins(0, 0, 0, 0)
        content_wrap.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(20, 14, 20, 14)
        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("PageTitle")
        self.health = QLabel("Backend: checking...")
        self.health.setObjectName("HealthBadge")
        self.health.setProperty("status", "checking")
        refresh = QPushButton("Refresh Now")
        refresh.clicked.connect(self.manual_refresh)
        top_layout.addWidget(self.page_title)
        top_layout.addStretch()
        top_layout.addWidget(self.health)
        top_layout.addWidget(refresh)

        content_wrap.addWidget(topbar)
        content_wrap.addWidget(self.stack, 1)

        self.banner = NotificationBanner(self.content_host)
        self.banner.setMaximumWidth(520)
        self.banner.hide()

        for idx, (key, label, page_cls) in enumerate(self.NAV_ITEMS):
            page = page_cls(self.app_state)
            self.app_state.register_page(key, page)
            self.stack.addWidget(page)

            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setProperty("active", idx == 0)
            btn.clicked.connect(lambda checked=False, i=idx: self.set_page(i))
            s_layout.addWidget(btn)
            self.buttons.append(btn)

        s_layout.addStretch()
        helper = QLabel("Connector-ready\nMeta WhatsApp - Twilio WhatsApp\nHybrid detection enabled")
        helper.setObjectName("SidebarHelper")
        s_layout.addWidget(helper)

        shell.addWidget(sidebar)
        shell.addWidget(self.content_host, 1)
        self.setCentralWidget(root)
        self.setMinimumSize(1024, 680)

        self.apply_theme(self.app_state.client.appearance)
        self.set_page(0)
        self.refresh_health(silent=True, force=True)
        self.position_banner()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.periodic_refresh)
        self.timer.start(2000)

    def show_notification(self, message: str, level: str = "info", timeout_ms: int = 3500):
        self.position_banner()
        self.banner.show_message(message, level, timeout_ms)
        self.banner.raise_()

    def position_banner(self):
        if not hasattr(self, "content_host"):
            return
        max_width = min(520, max(280, self.content_host.width() - 40))
        self.banner.setFixedWidth(max_width)
        self.banner.adjustSize()
        x = max(20, self.content_host.width() - self.banner.width() - 20)
        y = 82
        self.banner.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_banner()

    def apply_theme(self, theme_name: str):
        app = QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(get_theme_stylesheet(theme_name))
        self.refresh_health(silent=True, force=True)
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)
        for btn in self.buttons:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_page(self, index: int):
        key, title, _page_cls = self.NAV_ITEMS[index]
        self.stack.setCurrentIndex(index)
        self.app_state.set_current_page(key)
        self.page_title.setText(title)
        for button_index, btn in enumerate(self.buttons):
            btn.setProperty("active", button_index == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.app_state.mark_dirty(key)
        self.app_state.refresh_page(key, force=True, silent=True)

    def refresh_health(self, silent: bool = True, force: bool = False):
        now = time.monotonic()
        if not force and (now - self._last_health_check) < 8.0:
            return
        self._last_health_check = now
        data = self.app_state.client.health()
        online = bool(data.get("ok"))
        if online:
            provider = data.get("ai_provider", "backend")
            self.health.setText(f"Backend: online · {provider}")
            self.health.setProperty("status", "online")
        else:
            self.health.setText("Backend: offline")
            self.health.setProperty("status", "offline")

        if self._last_health_online is not None and self._last_health_online != online:
            if online:
                self.show_notification("Backend connection restored.", "success", 3000)
            else:
                self.show_notification(data.get("error", "Backend is offline."), "error", 5000)
        elif not online and not silent:
            self.show_notification(data.get("error", "Backend is offline."), "error", 5000)

        self._last_health_online = online
        self.health.style().unpolish(self.health)
        self.health.style().polish(self.health)

    def manual_refresh(self):
        self.app_state.client.clear_cache()
        self.refresh_health(silent=False, force=True)
        if self.app_state.refresh_current_page(force=True, silent=False, allow_paused=True):
            self.show_notification(f"{self.page_title.text()} reloaded.", "success", 2200)

    def periodic_refresh(self):
        if not self.isVisible() or self.isMinimized():
            return
        self.app_state.refresh_current_page(force=False, silent=True)
        self.refresh_health(silent=True, force=False)


def run():
    app = QApplication(sys.argv)
    bootstrap_client = ApiClient()
    app.setStyleSheet(get_theme_stylesheet(bootstrap_client.appearance))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
