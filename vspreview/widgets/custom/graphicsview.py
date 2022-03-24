from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QPointF
from PyQt5.QtWidgets import QWidget, QGraphicsView, QApplication, QGraphicsPixmapItem
from PyQt5.QtGui import QMouseEvent, QNativeGestureEvent, QTransform, QWheelEvent, QPixmap


class GraphicsView(QGraphicsView):
    WHEEL_STEP = 15 * 8  # degrees

    __slots__ = (
        'app', 'angleRemainder', 'zoomValue',
    )

    mouseMoved = pyqtSignal(QMouseEvent)
    mousePressed = pyqtSignal(QMouseEvent)
    mouseReleased = pyqtSignal(QMouseEvent)
    wheelScrolled = pyqtSignal(int)
    drag_mode: QGraphicsView.DragMode

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.app = QApplication.instance()
        self.angleRemainder = 0
        self.zoomValue = 0.0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def setZoom(self, value: int) -> None:
        transform = QTransform()
        transform.scale(value, value)
        self.setTransform(transform)

    def event(self, event: QEvent) -> bool:
        if isinstance(event, QNativeGestureEvent):
            typ = event.gestureType()
            if typ == Qt.BeginNativeGesture:
                self.zoomValue = 0.0
            elif typ == Qt.ZoomNativeGesture:
                self.zoomValue += event.value()
            if typ == Qt.EndNativeGesture:
                self.wheelScrolled.emit(-1 if self.zoomValue < 0 else 1)
        return super().event(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        assert self.app

        modifiers = self.app.keyboardModifiers()
        mouse = event.buttons()

        if modifiers == Qt.ControlModifier or mouse in map(Qt.MouseButtons, {Qt.RightButton, Qt.MiddleButton}):
            angleDelta = event.angleDelta().y()

            # check if wheel wasn't rotated the other way since last rotation
            if self.angleRemainder * angleDelta < 0:
                self.angleRemainder = 0

            self.angleRemainder += angleDelta

            if abs(self.angleRemainder) >= self.WHEEL_STEP:
                self.wheelScrolled.emit(self.angleRemainder // self.WHEEL_STEP)
                self.angleRemainder %= self.WHEEL_STEP
            return
        elif modifiers == Qt.NoModifier:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - event.angleDelta().y())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().x())
            return
        elif modifiers == Qt.ShiftModifier:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - event.angleDelta().x())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().y())
            return

        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if self.hasMouseTracking():
            self.mouseMoved.emit(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)
        self.mousePressed.emit(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.setDragMode(self.drag_mode)
        self.mouseReleased.emit(event)


class GraphicsImageItem:
    __slots__ = ('_graphics_item',)

    def __init__(self, graphics_item: QGraphicsPixmapItem) -> None:
        self._graphics_item = graphics_item

    def contains(self, point: QPointF) -> bool:
        return self._graphics_item.contains(point)

    def hide(self) -> None:
        self._graphics_item.hide()

    def pixmap(self) -> QPixmap:
        return self._graphics_item.pixmap()

    def setPixmap(self, value: QPixmap) -> None:
        self._graphics_item.setPixmap(value)

    def show(self) -> None:
        self._graphics_item.show()
