from __future__ import annotations

from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

__all__ = [
    'ColorView'
]


class ColorView(QWidget):
    __slots__ = ('_color', )

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self._color = QColor(0, 0, 0, 255)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.fillRect(event.rect(), self.color)

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor) -> None:
        if self._color == value:
            return
        self._color = value
        self.update()
