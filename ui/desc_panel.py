# right-side panel showing file/folder metadata + descriptions

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)


def _fmt_time(iso: str) -> str:
    if not iso:
        return "never"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d %b %Y  %H:%M")
    except Exception:
        return iso


class DescriptionPanel(QWidget):
    edit_requested       = Signal()
    ai_refresh_requested = Signal()
    # Signals from the inline AI-confirm banner
    ai_confirm_yes       = Signal()
    ai_confirm_no        = Signal()
    ai_confirm_skip      = Signal()   # "don't ask again"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("descPanel")
        self.setMinimumWidth(300)
        self._build()
        self.clear()

    # build UI

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # scrollable inner
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(18, 18, 18, 18)
        self._layout.setSpacing(14)
        self._layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(container)
        outer.addWidget(scroll)

        # header
        self._icon_lbl = QLabel("📄")
        self._icon_lbl.setStyleSheet("font-size: 28px;")
        self._icon_lbl.setFixedWidth(44)

        self._name_lbl = QLabel()
        self._name_lbl.setObjectName("descTitle")
        self._name_lbl.setWordWrap(True)

        self._type_lbl = QLabel()
        self._type_lbl.setObjectName("descSubtitle")

        hdr_right = QVBoxLayout()
        hdr_right.setSpacing(2)
        hdr_right.addWidget(self._name_lbl)
        hdr_right.addWidget(self._type_lbl)

        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        hdr.addWidget(self._icon_lbl, 0, Qt.AlignTop)
        hdr.addLayout(hdr_right, 1)
        self._layout.addLayout(hdr)

        # tags row 
        self._tags_row = QHBoxLayout()
        self._tags_row.setSpacing(6)
        self._sensitive_tag = self._make_tag("⚠ Contains sensitive data", "sensitiveTag")
        self._manual_tag    = self._make_tag("✏ Manually written", "manualTag")
        self._sensitive_tag.hide()
        self._manual_tag.hide()
        self._tags_row.addWidget(self._sensitive_tag)
        self._tags_row.addWidget(self._manual_tag)
        self._tags_row.addStretch()
        self._layout.addLayout(self._tags_row)

        # short description 
        self._layout.addWidget(self._section("SHORT DESCRIPTION"))
        self._short_lbl = QLabel()
        self._short_lbl.setObjectName("descShortBox")
        self._short_lbl.setWordWrap(True)
        self._short_lbl.setMinimumHeight(50)
        self._short_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._layout.addWidget(self._short_lbl)

        # long description 
        self._layout.addWidget(self._section("EXTENDED DESCRIPTION"))
        self._long_lbl = QLabel()
        self._long_lbl.setObjectName("descLongBox")
        self._long_lbl.setWordWrap(True)
        self._long_lbl.setMinimumHeight(80)
        self._long_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._layout.addWidget(self._long_lbl)

        # sensitive detail 
        self._sensitive_detail = QLabel()
        self._sensitive_detail.setStyleSheet(
            "color: #e06060; font-size: 11px; padding: 4px 0;"
        )
        self._sensitive_detail.setWordWrap(True)
        self._sensitive_detail.hide()
        self._layout.addWidget(self._sensitive_detail)

        # inline AI-confirm banner 
        self._ai_confirm = self._build_ai_confirm()
        self._ai_confirm.hide()
        self._layout.addWidget(self._ai_confirm)

        # action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._edit_btn = QPushButton("✏  Edit")
        self._edit_btn.setObjectName("btnPrimary")
        self._edit_btn.setToolTip("Manually write / edit description (locks AI updates)")
        self._edit_btn.clicked.connect(self.edit_requested)

        self._ai_btn = QPushButton("🤖  Refresh with AI")
        self._ai_btn.setObjectName("btnAI")
        self._ai_btn.setToolTip("Re-generate description using Groq AI")
        self._ai_btn.clicked.connect(self.ai_refresh_requested)

        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._ai_btn)
        btn_row.addStretch()
        self._layout.addLayout(btn_row)

        # timestamp
        self._ts_lbl = QLabel()
        self._ts_lbl.setObjectName("timestampLabel")
        self._layout.addWidget(self._ts_lbl)

        self._layout.addStretch()

    def _build_ai_confirm(self) -> QWidget:
        """Build the inline AI-confirm banner widget."""
        widget = QWidget()
        widget.setStyleSheet(
            "QWidget { background:#1e1a2e; border:1px solid #3a2a5e; border-radius:8px; }"
            "QLabel { background:transparent; border:none; }"
            "QCheckBox { background:transparent; border:none; }"
        )
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._confirm_msg = QLabel()
        self._confirm_msg.setWordWrap(True)
        self._confirm_msg.setStyleSheet(
            "color:#9aa3bf;font-size:11px;background:transparent;border:none;"
        )
        layout.addWidget(self._confirm_msg)

        from PySide6.QtWidgets import QCheckBox
        self._dont_ask = QCheckBox("Don't ask again for this file")
        self._dont_ask.setStyleSheet(
            "color:#6b7390;font-size:10px;background:transparent;border:none;"
        )
        layout.addWidget(self._dont_ask)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        keep_btn = QPushButton("Keep mine")
        keep_btn.clicked.connect(self._on_ai_cancel)
        btn_row.addWidget(keep_btn)
        btn_row.addStretch()

        replace_btn = QPushButton("Replace with AI")
        replace_btn.setObjectName("btnAI")
        replace_btn.clicked.connect(self._on_ai_confirm)
        btn_row.addWidget(replace_btn)
        layout.addLayout(btn_row)

        return widget

    # public API 

    def clear(self):
        self._icon_lbl.setText("📁")
        self._name_lbl.setText("Select a file or folder")
        self._type_lbl.setText("")
        self._short_lbl.setText("—")
        self._long_lbl.setText("—")
        self._sensitive_tag.hide()
        self._manual_tag.hide()
        self._sensitive_detail.hide()
        self._ts_lbl.setText("")
        self._edit_btn.setEnabled(False)
        self._ai_btn.setEnabled(False)
        self._ai_confirm.hide()

    def load(self, entry: dict, name: str, is_folder: bool):
        """Populate the panel from a sidecar entry dict."""
        self._ai_confirm.hide()
        icon = "📁" if is_folder else self._file_icon(name)
        self._icon_lbl.setText(icon)
        self._name_lbl.setText(name)
        self._type_lbl.setText("Folder" if is_folder else self._ext_label(name))

        short = entry.get("short_desc") or "No description yet."
        long_ = entry.get("long_desc")  or "Generate a description using the AI button."
        self._short_lbl.setText(short)
        self._long_lbl.setText(long_)

        # tags
        sensitive = entry.get("sensitive_detected", False)
        manual    = entry.get("manual_lock", False)
        self._sensitive_tag.setVisible(sensitive)
        self._manual_tag.setVisible(manual)

        if sensitive:
            stypes = entry.get("sensitive_types", [])
            detail = "Detected: " + ", ".join(stypes) if stypes else ""
            self._sensitive_detail.setText(detail)
            self._sensitive_detail.setVisible(bool(detail))
        else:
            self._sensitive_detail.hide()

        ts = entry.get("last_updated", "")
        self._ts_lbl.setText(
            f"Last updated: {_fmt_time(ts)}" if ts else "Not yet described"
        )

        self._edit_btn.setEnabled(True)
        self._ai_btn.setEnabled(True)

    def set_loading(self, msg: str = "Generating description…"):
        self._ai_confirm.hide()
        self._short_lbl.setText(f"⏳  {msg}")
        self._long_lbl.setText("")
        self._ai_btn.setEnabled(False)

    def show_ai_confirm(self, name: str):
        """Shows the inline AI-confirm banner instead of a popup dialog."""
        self._confirm_msg.setText(
            f"<b>{name}</b> has a manually written description.<br>"
            "Replace it with an AI-generated one? This will remove the manual lock."
        )
        self._dont_ask.setChecked(False)
        self._ai_confirm.show()
        self._ai_btn.setEnabled(False)

    def hide_ai_confirm(self):
        self._ai_confirm.hide()
        self._ai_btn.setEnabled(True)

    def skip_in_future(self) -> bool:
        return self._dont_ask.isChecked()

    # helpers

    def _on_ai_confirm(self):
        if self._dont_ask.isChecked():
            self.ai_confirm_skip.emit()
        self.ai_confirm_yes.emit()
        self._ai_confirm.hide()

    def _on_ai_cancel(self):
        self.ai_confirm_no.emit()
        self._ai_confirm.hide()
        self._ai_btn.setEnabled(True)

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    @staticmethod
    def _make_tag(text: str, obj_name: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName(obj_name)
        lbl.setFixedHeight(22)
        return lbl

    @staticmethod
    def _file_icon(name: str) -> str:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        icons = {
            "py": "🐍", "js": "🟨", "ts": "🔷", "jsx": "⚛", "tsx": "⚛",
            "html": "🌐", "css": "🎨", "scss": "🎨",
            "json": "📋", "yaml": "📋", "yml": "📋", "toml": "📋",
            "md": "📝", "txt": "📄", "pdf": "📕", "docx": "📘", "doc": "📘",
            "csv": "📊", "xlsx": "📊", "xls": "📊",
            "png": "🖼", "jpg": "🖼", "jpeg": "🖼", "gif": "🖼", "svg": "🖼",
            "sh": "⚙", "bash": "⚙", "zsh": "⚙", "ps1": "⚙",
            "cpp": "⚙", "c": "⚙", "h": "⚙", "java": "☕",
            "go": "🐹", "rs": "🦀", "rb": "💎", "sql": "🗃",
            "zip": "📦", "tar": "📦", "gz": "📦",
            "env": "🔐", "gitignore": "🚫",
        }
        return icons.get(ext, "📄")

    @staticmethod
    def _ext_label(name: str) -> str:
        ext = name.rsplit(".", 1)[-1].upper() if "." in name else "File"
        return f"{ext} file"
