"""Entry point: python -m sfasst.gui"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from sfasst.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("starfield-assistant")
    app.setOrganizationName("starfield-assistant")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
