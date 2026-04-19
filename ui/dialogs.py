# inline panels for FileSense — Settings, EditDesc, AIConfirm

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget, QScrollArea, QFrame, QSizePolicy,
)

from config import load_config, save_config


# Settings Panel

class SettingsPanel(QWidget):
    """Inline Settings panel — replaces the right description area."""

    saved     = Signal()
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = {}
        self._build()

    def load(self):
        """Reload from config file and refresh all controls."""
        self.config = load_config()
        self.key_edit.setText(self.config.get("groq_api_key", ""))
        idx = self.model_combo.findText(self.config.get("groq_model", ""))
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.interval_spin.setValue(self.config.get("auto_update_interval_minutes", 30))
        self.staleness_spin.setValue(self.config.get("staleness_days", 4))
        self.max_size_spin.setValue(self.config.get("max_file_size_mb", 10))
        self.max_chars_spin.setValue(self.config.get("max_text_chars", 3000))
        self.max_rows_spin.setValue(self.config.get("max_csv_rows", 20))

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar 
        title_bar = QWidget()
        title_bar.setFixedHeight(44)
        title_bar.setStyleSheet(
            "background:#1a1b26;border-bottom:1px solid #2a2b3a;"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(16, 0, 12, 0)

        title_lbl = QLabel("⚙  Settings")
        title_lbl.setStyleSheet(
            "color:#e8e8f0;font-size:13px;font-weight:700;"
        )
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#6b7390;border:none;font-size:14px;}"
            "QPushButton:hover{color:#e8e8f0;}"
        )
        close_btn.clicked.connect(self.cancelled)
        tb_layout.addWidget(close_btn)
        root.addWidget(title_bar)

        # scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # groq api
        api_group = QGroupBox("GROQ API")
        api_form  = QFormLayout(api_group)
        api_form.setSpacing(10)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("gsk_…")

        show_btn = QPushButton("Show")
        show_btn.setFixedWidth(60)
        show_btn.clicked.connect(
            lambda: self.key_edit.setEchoMode(
                QLineEdit.Normal
                if self.key_edit.echoMode() == QLineEdit.Password
                else QLineEdit.Password
            )
        )
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_edit)
        key_row.addWidget(show_btn)
        api_form.addRow("API Key:", key_row)

        self.model_combo = QComboBox()
        for m in [
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
            "qwen/qwen-3-32b",
        ]:
            self.model_combo.addItem(m)
        api_form.addRow("Text Model:", self.model_combo)
        layout.addWidget(api_group)

        # auto update
        sched_group = QGroupBox("AUTO-UPDATE")
        sched_form  = QFormLayout(sched_group)
        sched_form.setSpacing(10)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 1440)
        self.interval_spin.setSuffix(" min")
        sched_form.addRow("Check interval:", self.interval_spin)

        self.staleness_spin = QSpinBox()
        self.staleness_spin.setRange(1, 90)
        self.staleness_spin.setSuffix(" days")
        sched_form.addRow("Stop updating after:", self.staleness_spin)
        layout.addWidget(sched_group)

        # content limits
        limit_group = QGroupBox("CONTENT LIMITS")
        limit_form  = QFormLayout(limit_group)
        limit_form.setSpacing(10)

        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(1, 100)
        self.max_size_spin.setSuffix(" MB")
        limit_form.addRow("Max file size:", self.max_size_spin)

        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(500, 10000)
        self.max_chars_spin.setSuffix(" chars")
        limit_form.addRow("Text head limit:", self.max_chars_spin)

        self.max_rows_spin = QSpinBox()
        self.max_rows_spin.setRange(5, 200)
        self.max_rows_spin.setSuffix(" rows")
        limit_form.addRow("CSV preview rows:", self.max_rows_spin)
        layout.addWidget(limit_group)

        layout.addStretch()

        # Save / Cancel row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.cancelled)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("btnPrimary")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        scroll.setWidget(content)
        root.addWidget(scroll)

    def _save(self):
        self.config = load_config()
        self.config["groq_api_key"]                = self.key_edit.text().strip()
        self.config["groq_model"]                  = self.model_combo.currentText()
        self.config["auto_update_interval_minutes"] = self.interval_spin.value()
        self.config["staleness_days"]              = self.staleness_spin.value()
        self.config["max_file_size_mb"]            = self.max_size_spin.value()
        self.config["max_text_chars"]              = self.max_chars_spin.value()
        self.config["max_csv_rows"]                = self.max_rows_spin.value()
        save_config(self.config)
        self.saved.emit()


# Edit Description Panel 

class EditDescPanel(QWidget):
    """Inline edit-description panel."""

    saved     = Signal(str, str)   # (short_desc, long_desc)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def load(self, name: str, short: str, long_: str):
        """Populate fields for the given file/folder."""
        self._title_lbl.setText(f"✏  Edit — {name}")
        self.short_edit.setText(short)
        self.long_edit.setPlainText(long_)
        self._update_wc()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # title bar 
        title_bar = QWidget()
        title_bar.setFixedHeight(44)
        title_bar.setStyleSheet(
            "background:#1a1b26;border-bottom:1px solid #2a2b3a;"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(16, 0, 12, 0)

        self._title_lbl = QLabel("✏  Edit Description")
        self._title_lbl.setStyleSheet(
            "color:#e8e8f0;font-size:13px;font-weight:700;"
        )
        tb_layout.addWidget(self._title_lbl)
        tb_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#6b7390;border:none;font-size:14px;}"
            "QPushButton:hover{color:#e8e8f0;}"
        )
        close_btn.clicked.connect(self.cancelled)
        tb_layout.addWidget(close_btn)
        root.addWidget(title_bar)

        # content 
        content = QWidget()
        layout  = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        note = QLabel("✏  Saving locks this description from AI auto-updates.")
        note.setStyleSheet("color:#50a8d0;font-size:11px;")
        layout.addWidget(note)

        layout.addWidget(self._sec("SHORT DESCRIPTION  (max 20 words)"))
        self.short_edit = QLineEdit()
        self.short_edit.setPlaceholderText("One-line summary …")
        layout.addWidget(self.short_edit)

        layout.addWidget(self._sec("EXTENDED DESCRIPTION  (max 60 words)"))
        self.long_edit = QTextEdit()
        self.long_edit.setPlaceholderText("Detailed description …")
        self.long_edit.setFixedHeight(110)
        layout.addWidget(self.long_edit)

        self.wc_label = QLabel()
        self.wc_label.setStyleSheet("color:#4a5070;font-size:10px;")
        layout.addWidget(self.wc_label)

        self.short_edit.textChanged.connect(self._update_wc)
        self.long_edit.textChanged.connect(self._update_wc)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.cancelled)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("btnPrimary")
        save_btn.clicked.connect(self._emit_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        root.addWidget(content)

    @staticmethod
    def _sec(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size:10px;font-weight:700;letter-spacing:1px;color:#4a5070;"
        )
        return lbl

    def _update_wc(self):
        sw = len(self.short_edit.text().split())
        lw = len(self.long_edit.toPlainText().split())
        self.wc_label.setText(f"Short: {sw}/20 words   •   Extended: {lw}/60 words")

    def _emit_save(self):
        short = self.short_edit.text().strip()
        long_ = self.long_edit.toPlainText().strip()
        self.saved.emit(short, long_)


# AI Confirm Panel 

class AIConfirmPanel(QWidget):
    """
    Inline confirmation banner — shown inside the desc panel when the user
    clicks 'Refresh with AI' on a manually-locked description.
    """

    confirmed          = Signal()
    cancelled          = Signal()
    skip_in_future_sig = Signal()   # emitted together with confirmed when checkbox checked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._build()

    def load(self, name: str):
        self._msg.setText(
            f"<b>{name}</b> has a manually written description.<br>"
            "Replace it with an AI-generated one?"
        )
        self.dont_ask.setChecked(False)

    def _build(self):
        self.setStyleSheet(
            "background:#1e1a2e;border:1px solid #3a2a5e;border-radius:8px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._msg = QLabel()
        self._msg.setWordWrap(True)
        self._msg.setStyleSheet("color:#9aa3bf;font-size:11px;background:transparent;border:none;")
        layout.addWidget(self._msg)

        self.dont_ask = QCheckBox("Don't ask again for this file")
        self.dont_ask.setStyleSheet("color:#6b7390;font-size:10px;background:transparent;border:none;")
        layout.addWidget(self.dont_ask)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        keep_btn = QPushButton("Keep mine")
        keep_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(keep_btn)
        btn_row.addStretch()

        replace_btn = QPushButton("Replace with AI")
        replace_btn.setObjectName("btnAI")
        replace_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(replace_btn)

        layout.addLayout(btn_row)

    def _on_confirm(self):
        if self.dont_ask.isChecked():
            self.skip_in_future_sig.emit()
        self.confirmed.emit()

    def _on_cancel(self):
        self.cancelled.emit()

    def skip_in_future(self) -> bool:
        return self.dont_ask.isChecked()


# Legacy aliase

class SettingsDialog(SettingsPanel):
    """Deprecated alias — use SettingsPanel."""
    def exec(self):
        """Mimics QDialog.exec() for drop-in compatibility: always returns True."""
        self._save()
        return True


class EditDescDialog(EditDescPanel):
    """Deprecated alias — use EditDescPanel."""
    def __init__(self, name: str, short: str, long_: str, parent=None):
        super().__init__(parent)
        self.load(name, short, long_)
        self._result = None

    def exec(self):
        return False   # always declined in compat mode

    def get_values(self):
        return self.short_edit.text().strip(), self.long_edit.toPlainText().strip()


class AIUpdateDialog(AIConfirmPanel):
    """Deprecated alias — use AIConfirmPanel."""
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.load(name)

    def exec(self):
        return False
