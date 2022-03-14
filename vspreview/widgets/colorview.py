from PyQt5 import Qt


class ColorView(Qt.QWidget):
    __slots__ = (
        '_color',
    )

    def __init__(self, parent: Qt.QWidget) -> None:
        super().__init__(parent)

        self._color = Qt.QColor(0, 0, 0, 255)

    def paintEvent(self, event: Qt.QPaintEvent) -> None:
        super().paintEvent(event)

        painter = Qt.QPainter(self)
        painter.fillRect(event.rect(), self.color)

    @property
    def color(self) -> Qt.QColor:
        return self._color

    @color.setter
    def color(self, value: Qt.QColor) -> None:
        if self._color == value:
            return
        self._color = value
        self.update()
