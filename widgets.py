from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSlider


class TimelineSlider(QSlider):
    markerClicked = Signal(int)

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.markers = []
        self.selected_marker = None
        self.setMinimum(0)
        self.setMaximum(0)
        self.setMouseTracking(True)

    def set_markers(self, markers, selected_marker=None):
        self.markers = list(markers)
        self.selected_marker = selected_marker
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.maximum() <= self.minimum():
            return

        painter = QPainter(self)
        groove = self._groove_rect()
        for marker in self.markers:
            ratio = (marker - self.minimum()) / (self.maximum() - self.minimum())
            x = groove.left() + int(ratio * groove.width())
            color = QColor("#e03131") if marker == self.selected_marker else QColor("#1971c2")
            painter.setPen(QPen(color, 3))
            painter.drawLine(x, groove.top() - 6, x, groove.bottom() + 6)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.markers:
            nearest = self._nearest_marker(event.position().x())
            if nearest is not None:
                marker, distance = nearest
                if distance <= 8:
                    self.selected_marker = marker
                    self.update()
                    self.markerClicked.emit(marker)
                    return
        super().mousePressEvent(event)

    def _nearest_marker(self, mouse_x):
        groove = self._groove_rect()
        if groove.width() <= 0 or self.maximum() <= self.minimum():
            return None

        result = None
        for marker in self.markers:
            ratio = (marker - self.minimum()) / (self.maximum() - self.minimum())
            x = groove.left() + ratio * groove.width()
            distance = abs(x - mouse_x)
            if result is None or distance < result[1]:
                result = (marker, distance)
        return result

    def _groove_rect(self):
        margin = 12
        return QRect(margin, self.height() // 2 - 4, max(1, self.width() - margin * 2), 8)
