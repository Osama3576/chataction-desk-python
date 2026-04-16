from __future__ import annotations

DARK_STYLE = """
QWidget {
    background: #0f1220;
    color: #ecf0ff;
    font-family: "Segoe UI";
    font-size: 13px;
}
QLabel { background: transparent; }
QMainWindow { background: #0b0f1a; }
QFrame#Sidebar {
    background: #101528;
    border-right: 1px solid #1c2340;
}
QFrame#TopBar {
    background: #0f1526;
    border-bottom: 1px solid #1c2340;
}
QFrame#Card, QFrame#Panel, QFrame#MetricCard {
    background: #141b31;
    border: 1px solid #212b4b;
    border-radius: 18px;
}
QFrame#SectionCard {
    background: #131a2d;
    border: 1px solid #20294a;
    border-radius: 16px;
}
QFrame#PageFooter {
    background: #11182c;
    border: 1px solid #20294a;
    border-radius: 16px;
}
QFrame#NotificationBanner {
    background: #17223d;
    border: 1px solid #2d3a64;
    border-radius: 14px;
}
QFrame#NotificationBanner[level="success"] {
    background: #163a2b;
    border: 1px solid #2ecc71;
}
QFrame#NotificationBanner[level="warning"] {
    background: #4a3513;
    border: 1px solid #f5c04e;
}
QFrame#NotificationBanner[level="error"] {
    background: #412025;
    border: 1px solid #e74c3c;
}
QLabel#NotificationText {
    color: #f4f6ff;
    font-weight: 600;
}
QPushButton#NotificationClose {
    background: transparent;
    border: 1px solid transparent;
    color: #d5ddfb;
    padding: 6px 10px;
}
QPushButton#NotificationClose:hover {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
}
QLabel#BrandLabel {
    font-size: 18px;
    font-weight: 700;
    color: #f4f6ff;
}
QLabel#SidebarHeader {
    font-size: 11px;
    color: #7f8cb1;
    font-weight: 700;
    margin-top: 10px;
}
QLabel#SidebarSubtext, QLabel#SidebarHelper, QLabel#MetricSubtitle {
    color: #7f8cb1;
    font-size: 11px;
}
QLabel#SelectionSummary {
    color: #9fb0e6;
    font-weight: 600;
}
QLabel#PageTitle, QLabel#SectionTitle {
    color: #f4f6ff;
    font-weight: 800;
}
QLabel#PageTitle { font-size: 20px; }
QLabel#SectionTitle { font-size: 15px; }
QLabel#MetricTitle {
    color: #9fb0e6;
    font-size: 12px;
    font-weight: 600;
}
QLabel#MetricValue {
    font-size: 28px;
    font-weight: 800;
    color: #f8faff;
}
QPushButton {
    background: #1b2440;
    border: 1px solid #2b3760;
    border-radius: 12px;
    padding: 10px 14px;
    color: #eef2ff;
}
QPushButton:hover { background: #242f54; }
QPushButton:disabled {
    background: #151c30;
    border: 1px solid #242d4b;
    color: #7382a8;
}
QPushButton#PrimaryButton {
    background: #6c5ce7;
    border: 1px solid #7f72f1;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover { background: #7d6cf0; }
QPushButton#NavButton {
    text-align: left;
    padding: 12px 14px;
    border-radius: 12px;
    background: transparent;
    border: 1px solid transparent;
    color: #d5ddfb;
}
QPushButton#NavButton:hover {
    background: #19213b;
    border: 1px solid #263156;
}
QPushButton#NavButton[active="true"] {
    background: #202b4f;
    border: 1px solid #34457d;
}
QLabel#HealthBadge {
    padding: 8px 12px;
    border-radius: 12px;
    background: #1b2440;
    border: 1px solid #2b3760;
    color: #dce5ff;
}
QLabel#HealthBadge[status="online"] {
    background: #163a2b;
    border: 1px solid #2ecc71;
    color: #e8fff2;
}
QLabel#HealthBadge[status="offline"] {
    background: #412025;
    border: 1px solid #e74c3c;
    color: #ffe9ec;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit {
    background: #0f162b;
    border: 1px solid #273155;
    border-radius: 12px;
    padding: 10px 12px;
    color: #eef2ff;
    selection-background-color: #6c5ce7;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QDateEdit:disabled {
    background: #12192c;
    border: 1px solid #202848;
    color: #97a4c6;
}
QTextEdit#PreviewBox {
    background: #11182c;
    border: 1px solid #20294a;
}
QComboBox QAbstractItemView {
    background: #10182c;
    color: #eef2ff;
    border: 1px solid #273155;
    selection-background-color: #6c5ce7;
}
QTableWidget, QListWidget, QTreeWidget, QTabWidget::pane {
    background: #11182c;
    border: 1px solid #20294a;
    border-radius: 14px;
    gridline-color: #20294a;
}
QTableWidget::item:selected, QListWidget::item:selected {
    background: #202b4f;
    color: #eef2ff;
}
QHeaderView::section {
    background: #161f38;
    color: #cdd7fb;
    border: none;
    padding: 10px;
    font-weight: 700;
}
QTabBar::tab {
    background: #131a2d;
    border: 1px solid #20294a;
    padding: 10px 14px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 6px;
}
QTabBar::tab:selected { background: #202b4f; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #2a3458; border-radius: 5px; }
QMessageBox, QFileDialog { background: #101528; color: #eef2ff; }
"""

LIGHT_STYLE = """
QWidget {
    background: #f4f7fc;
    color: #172033;
    font-family: "Segoe UI";
    font-size: 13px;
}
QLabel { background: transparent; }
QMainWindow { background: #edf2fa; }
QFrame#Sidebar {
    background: #ffffff;
    border-right: 1px solid #d8e1f0;
}
QFrame#TopBar {
    background: #ffffff;
    border-bottom: 1px solid #d8e1f0;
}
QFrame#Card, QFrame#Panel, QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #dbe4f2;
    border-radius: 18px;
}
QFrame#SectionCard {
    background: #ffffff;
    border: 1px solid #dbe4f2;
    border-radius: 16px;
}
QFrame#PageFooter {
    background: #ffffff;
    border: 1px solid #dbe4f2;
    border-radius: 16px;
}
QFrame#NotificationBanner {
    background: #eef3ff;
    border: 1px solid #d5e0f8;
    border-radius: 14px;
}
QFrame#NotificationBanner[level="success"] {
    background: #e8f8ef;
    border: 1px solid #8dd4a7;
}
QFrame#NotificationBanner[level="warning"] {
    background: #fff7e1;
    border: 1px solid #f2d386;
}
QFrame#NotificationBanner[level="error"] {
    background: #fff0f1;
    border: 1px solid #f0b3bb;
}
QLabel#NotificationText {
    color: #1c2a46;
    font-weight: 600;
}
QPushButton#NotificationClose {
    background: transparent;
    border: 1px solid transparent;
    color: #4a5d7c;
    padding: 6px 10px;
}
QPushButton#NotificationClose:hover {
    background: #f4f7fd;
    border: 1px solid #d9e3f2;
}
QLabel#BrandLabel {
    font-size: 18px;
    font-weight: 700;
    color: #1a2540;
}
QLabel#SidebarHeader {
    font-size: 11px;
    color: #72819d;
    font-weight: 700;
    margin-top: 10px;
}
QLabel#SidebarSubtext, QLabel#SidebarHelper, QLabel#MetricSubtitle {
    color: #6e7f9d;
    font-size: 11px;
}
QLabel#SelectionSummary {
    color: #5b6f91;
    font-weight: 600;
}
QLabel#PageTitle, QLabel#SectionTitle {
    color: #18233c;
    font-weight: 800;
}
QLabel#PageTitle { font-size: 20px; }
QLabel#SectionTitle { font-size: 15px; }
QLabel#MetricTitle {
    color: #6d7ea0;
    font-size: 12px;
    font-weight: 600;
}
QLabel#MetricValue {
    font-size: 28px;
    font-weight: 800;
    color: #16213a;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #d0dbea;
    border-radius: 12px;
    padding: 10px 14px;
    color: #22314f;
}
QPushButton:hover { background: #f4f7fd; }
QPushButton:disabled {
    background: #f5f7fb;
    border: 1px solid #dde4f1;
    color: #8da0be;
}
QPushButton#PrimaryButton {
    background: #5b6df9;
    border: 1px solid #4e61f0;
    color: #ffffff;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover { background: #4e61f0; }
QPushButton#NavButton {
    text-align: left;
    padding: 12px 14px;
    border-radius: 12px;
    background: transparent;
    border: 1px solid transparent;
    color: #344666;
}
QPushButton#NavButton:hover {
    background: #f4f7fd;
    border: 1px solid #d9e3f2;
}
QPushButton#NavButton[active="true"] {
    background: #eef3ff;
    border: 1px solid #cfdafd;
    color: #243860;
}
QLabel#HealthBadge {
    padding: 8px 12px;
    border-radius: 12px;
    background: #eef3ff;
    border: 1px solid #d5e0f8;
    color: #29406f;
}
QLabel#HealthBadge[status="online"] {
    background: #e8f8ef;
    border: 1px solid #8dd4a7;
    color: #1c6a3d;
}
QLabel#HealthBadge[status="offline"] {
    background: #fff0f1;
    border: 1px solid #f0b3bb;
    color: #b14556;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit {
    background: #ffffff;
    border: 1px solid #d5deec;
    border-radius: 12px;
    padding: 10px 12px;
    color: #1c2a46;
    selection-background-color: #5b6df9;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QDateEdit:disabled {
    background: #f7f9fd;
    border: 1px solid #dfe6f2;
    color: #7f90aa;
}
QTextEdit#PreviewBox {
    background: #ffffff;
    border: 1px solid #dbe4f2;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1c2a46;
    border: 1px solid #d5deec;
    selection-background-color: #e8eeff;
    selection-color: #1c2a46;
}
QTableWidget, QListWidget, QTreeWidget, QTabWidget::pane {
    background: #ffffff;
    border: 1px solid #dbe4f2;
    border-radius: 14px;
    gridline-color: #e5ecf7;
}
QTableWidget::item:selected, QListWidget::item:selected {
    background: #eef3ff;
    color: #22314f;
}
QHeaderView::section {
    background: #f7f9fd;
    color: #526480;
    border: none;
    padding: 10px;
    font-weight: 700;
}
QTabBar::tab {
    background: #ffffff;
    border: 1px solid #dbe4f2;
    padding: 10px 14px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 6px;
    color: #4a5d7c;
}
QTabBar::tab:selected {
    background: #eef3ff;
    color: #22314f;
}
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #c8d3e6; border-radius: 5px; }
QMessageBox, QFileDialog { background: #ffffff; color: #1c2a46; }
"""

APP_THEMES = {
    "Dark": DARK_STYLE,
    "Light": LIGHT_STYLE,
}


def get_theme_stylesheet(theme_name: str | None) -> str:
    return APP_THEMES.get(theme_name or "Dark", DARK_STYLE)
