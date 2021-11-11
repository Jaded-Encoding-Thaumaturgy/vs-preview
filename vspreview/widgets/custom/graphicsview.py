from __future__ import annotations

import logging
from typing import cast, Optional

from PyQt5 import Qt


class GraphicsView(Qt.QGraphicsView):
    WHEEL_STEP = 15 * 8  # degrees

    __slots__ = (
        'app', 'angleRemainder',
    )

    mouseMoved = Qt.pyqtSignal(Qt.QMouseEvent)
    mousePressed = Qt.pyqtSignal(Qt.QMouseEvent)
    mouseReleased = Qt.pyqtSignal(Qt.QMouseEvent)
    wheelScrolled = Qt.pyqtSignal(int)

    def __init__(self, parent: Optional[Qt.QWidget] = None) -> None:
        super().__init__(parent)

        self.app = Qt.QApplication.instance()
        self.angleRemainder = 0

    def setZoom(self, value: int) -> None:
        transform = Qt.QTransform()
        transform.scale(value, value)
        self.setTransform(transform)

    def wheelEvent(self, event: Qt.QWheelEvent) -> None:
        modifiers = self.app.keyboardModifiers()
        if modifiers == Qt.Qt.ControlModifier:
            angleDelta = event.angleDelta().y()

            # check if wheel wasn't rotated the other way since last rotation
            if self.angleRemainder * angleDelta < 0:
                self.angleRemainder = 0

            self.angleRemainder += angleDelta
            if abs(self.angleRemainder) >= self.WHEEL_STEP:
                self.wheelScrolled.emit(self.angleRemainder // self.WHEEL_STEP)
                self.angleRemainder %= self.WHEEL_STEP
            return
        elif modifiers == Qt.Qt.NoModifier:
            self.  verticalScrollBar().setValue(
                self.  verticalScrollBar().value() - event.angleDelta().y())
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - event.angleDelta().x())
            return
        elif modifiers == Qt.Qt.ShiftModifier:
            self.  verticalScrollBar().setValue(
                self.  verticalScrollBar().value() - event.angleDelta().x())
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - event.angleDelta().y())
            return

        event.ignore()

    def mouseMoveEvent(self, event: Qt.QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if self.hasMouseTracking():
            self.mouseMoved.emit(event)

    def mousePressEvent(self, event: Qt.QMouseEvent) -> None:
        if event.button() == Qt.Qt.LeftButton:
            self.drag_mode = self.dragMode()
            self.setDragMode(Qt.QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)
        self.mousePressed.emit(event)

    def mouseReleaseEvent(self, event: Qt.QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if event.button() == Qt.Qt.LeftButton:
            self.setDragMode(self.drag_mode)
        self.mouseReleased.emit(event)


class GraphicsImageItem:
    __slots__ = (
        '_image', '_graphics_item'
    )

    def __init__(self, graphics_item: Qt.QGraphicsItem, image: Qt.QImage) -> None:
        self._graphics_item = graphics_item
        self._image = image

    def contains(self, point: Qt.QPointF) -> bool:
        return self._graphics_item.contains(point)

    def hide(self) -> None:
        self._graphics_item.hide()

    def image(self) -> Qt.QImage:
        return self._image

    def pixmap(self) -> Qt.QPixmap:
        return cast(Qt.QPixmap, self._graphics_item.pixmap())

    def setImage(self, value: Qt.QImage) -> None:
        self._image = value
        self._graphics_item.setPixmap(Qt.QPixmap.fromImage(self._image, Qt.Qt.NoFormatConversion))

    def show(self) -> None:
        self._graphics_item.show()
