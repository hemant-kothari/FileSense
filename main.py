"""
FolderScribe — entry point.
Run: python main.py
"""
import sys
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import QApplication, QFileSystemModel
from PySide6.QtCore import Qt
from ui.main_window import MainWindow
from ui.styles import STYLESHEET

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FolderScribe")
    app.setApplicationVersion("1.0.0")
    # Use a clean system font
    font = QFont("Segoe UI", 12)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
