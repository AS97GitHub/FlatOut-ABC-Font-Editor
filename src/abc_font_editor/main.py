"""Application entry point."""
import sys

from PyQt6.QtWidgets import QApplication

from .main_window import ABCFontEditor
from .utils.icons import load_app_icon


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("QToolTip { background-color: #333333; color: white; border: 1px solid #555555; }")
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    editor = ABCFontEditor()
    if icon is not None:
        editor.setWindowIcon(icon)
    editor.resize(960, 720)
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
