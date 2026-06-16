import os
import sys

from PySide6.QtWidgets import QApplication

from app import VideoCutter


def main():
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = VideoCutter()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
