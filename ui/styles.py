"""
FileSense dark theme — slate charcoal with amber accents.
"""

STYLESHEET = """
/* ── Global ──────────────────────────────────────────────────────────── */
QWidget {
    background-color: #13141a;
    color: #cdd3e8;
    font-family: "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}

QMainWindow {
    background-color: #0e0f14;
}

/* ── Toolbar ─────────────────────────────────────────────────────────── */
QToolBar {
    background-color: #1a1b24;
    border-bottom: 1px solid #2a2b3a;
    padding: 4px 8px;
    spacing: 4px;
}

QToolBar QToolButton {
    background: transparent;
    color: #9aa3bf;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}

QToolBar QToolButton:hover {
    background: #21222d;
    color: #e8a84c;
    border-color: #2e2f3e;
}

QToolBar QToolButton:pressed {
    background: #2a2b3a;
    color: #f0c070;
}

QToolBar::separator {
    background: #2a2b3a;
    width: 1px;
    margin: 6px 4px;
}

/* ── Splitter ────────────────────────────────────────────────────────── */
QSplitter::handle {
    background: #2a2b3a;
    width: 1px;
}

/* ── Tree View ───────────────────────────────────────────────────────── */
QTreeView {
    background-color: #16172000;
    alternate-background-color: #1c1d28;
    border-right: 1px solid #2a2b3a;
    padding: 4px 0;
    show-decoration-selected: 1;
}

QTreeView::item {
    height: 28px;
    padding-left: 4px;
    border-radius: 4px;
    margin: 1px 4px;
}

QTreeView::item:hover {
    background: #21222d;
    color: #cdd3e8;
}

QTreeView::item:selected {
    background: #2a2d42;
    color: #e8a84c;
}

QTreeView::branch {
    background: transparent;
}

QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {
    image: none;
    border: none;
}

/* ── List Widget ─────────────────────────────────────────────────────── */
QListWidget {
    background-color: #1e2030;
    border-right: 1px solid #2a2b3a;
    padding: 4px;
}

QListWidget::item {
    border-radius: 6px;
    padding: 6px 8px;
    margin: 2px;
    border: 1px solid transparent;
}

QListWidget::item:hover {
    background: #21222d;
    border-color: #2e2f3e;
}

QListWidget::item:selected {
    background: #232538;
    border-color: #e8a84c;
    color: #f0d080;
}

/* ── Scroll Bars ─────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #2e3042;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #e8a84c;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
}

QScrollBar::handle:horizontal {
    background: #2e3042;
    border-radius: 4px;
    min-width: 24px;
}

/* ── Description Panel ───────────────────────────────────────────────── */
#descPanel {
    background-color: #1a1b26;
    border-left: 1px solid #2a2b3a;
}

#descTitle {
    font-size: 14px;
    font-weight: 600;
    color: #e8e8f0;
    padding: 4px 0;
}

#descSubtitle {
    font-size: 11px;
    color: #6b7390;
}

#descShortBox {
    background: #1e1f2c;
    border: 1px solid #2e2f42;
    border-radius: 8px;
    padding: 10px 12px;
    color: #cdd3e8;
    font-size: 13px;
    line-height: 1.5;
}

#descLongBox {
    background: #1e1f2c;
    border: 1px solid #2e2f42;
    border-radius: 8px;
    padding: 10px 12px;
    color: #aab0c8;
    font-size: 12px;
    line-height: 1.6;
}

#sectionLabel {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: #4a5070;
    text-transform: uppercase;
}

#sensitiveTag {
    background: #3a1a1e;
    border: 1px solid #6b2030;
    border-radius: 4px;
    color: #e0605a;
    font-size: 11px;
    padding: 3px 8px;
}

#manualTag {
    background: #1a2e3a;
    border: 1px solid #1e5070;
    border-radius: 4px;
    color: #50a8d0;
    font-size: 11px;
    padding: 3px 8px;
}

#timestampLabel {
    color: #3e4258;
    font-size: 10px;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
QPushButton {
    background: #21222d;
    color: #9aa3bf;
    border: 1px solid #2e2f42;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
}

QPushButton:hover {
    background: #2a2b3e;
    color: #cdd3e8;
    border-color: #404260;
}

QPushButton:pressed {
    background: #1e1f2c;
}

QPushButton#btnPrimary {
    background: #2a2010;
    color: #e8a84c;
    border-color: #5a4018;
}

QPushButton#btnPrimary:hover {
    background: #362810;
    color: #f0c060;
    border-color: #7a5820;
}

QPushButton#btnAI {
    background: #1a2838;
    color: #50a8d0;
    border-color: #1e4060;
}

QPushButton#btnAI:hover {
    background: #1e3048;
    color: #70c8f0;
    border-color: #2a5880;
}

QPushButton#btnDanger {
    background: #2a1218;
    color: #e06060;
    border-color: #5a2030;
}

/* ── Input fields ────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background: #1c1d28;
    color: #cdd3e8;
    border: 1px solid #2e2f42;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #3a3d60;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #e8a84c;
}

/* ── Labels ──────────────────────────────────────────────────────────── */
QLabel {
    color: #cdd3e8;
    background: transparent;
}

/* ── Dialogs ─────────────────────────────────────────────────────────── */
QDialog {
    background: #1a1b26;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* ── Status Bar ──────────────────────────────────────────────────────── */
QStatusBar {
    background: #13141a;
    color: #4a5070;
    border-top: 1px solid #1e1f2c;
    font-size: 11px;
}

QStatusBar::item {
    border: none;
}

/* ── ComboBox ────────────────────────────────────────────────────────── */
QComboBox {
    background: #1c1d28;
    color: #cdd3e8;
    border: 1px solid #2e2f42;
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #404260;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background: #1e1f2c;
    border: 1px solid #2e2f42;
    selection-background-color: #2a2d42;
    selection-color: #e8a84c;
    outline: none;
}

/* ── Spinbox ─────────────────────────────────────────────────────────── */
QSpinBox {
    background: #1c1d28;
    color: #cdd3e8;
    border: 1px solid #2e2f42;
    border-radius: 6px;
    padding: 5px 10px;
}

QSpinBox::up-button, QSpinBox::down-button {
    background: #21222d;
    border: none;
    width: 18px;
}

/* ── Progress Bar ────────────────────────────────────────────────────── */
QProgressBar {
    background: #1c1d28;
    border: 1px solid #2e2f42;
    border-radius: 4px;
    height: 4px;
    text-align: center;
}

QProgressBar::chunk {
    background: #e8a84c;
    border-radius: 4px;
}

/* ── Checkbox ────────────────────────────────────────────────────────── */
QCheckBox {
    spacing: 8px;
    color: #9aa3bf;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #2e2f42;
    border-radius: 4px;
    background: #1c1d28;
}

QCheckBox::indicator:checked {
    background: #e8a84c;
    border-color: #e8a84c;
}

/* ── Group Box ───────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #2e2f42;
    border-radius: 8px;
    margin-top: 12px;
    padding: 8px;
    font-weight: 600;
    color: #6b7390;
    font-size: 11px;
    letter-spacing: 0.8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background: #1a1b26;
}

/* ── Tooltip ─────────────────────────────────────────────────────────── */
QToolTip {
    background: #21222d;
    color: #cdd3e8;
    border: 1px solid #3a3c50;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
"""
