from __future__ import annotations

from enum import IntEnum, auto
from dataclasses import dataclass

from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QPointF, QRect, QPoint
from PyQt5.QtWidgets import QWidget, QGraphicsView, QApplication, QGraphicsPixmapItem
from PyQt5.QtGui import QMouseEvent, QNativeGestureEvent, QTransform, QWheelEvent, QPixmap, QPainter, QColor


@dataclass
class CroppingInfo:
    top: int
    left: int
    width: int
    height: int
    active: bool = True
    is_absolute: bool = False


class DragEventType(IntEnum):
    start = auto()
    stop = auto()
    move = auto()
    repaint = auto()


class GraphicsView(QGraphicsView):
    WHEEL_STEP = 15 * 8  # degrees

    __slots__ = ('app', 'angleRemainder', 'zoomValue',)

    mouseMoved = pyqtSignal(QMouseEvent)
    mousePressed = pyqtSignal(QMouseEvent)
    mouseReleased = pyqtSignal(QMouseEvent)
    wheelScrolled = pyqtSignal(int)
    dragEvent = pyqtSignal(DragEventType)
    drag_mode: QGraphicsView.DragMode

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.app = QApplication.instance()
        self.angleRemainder = 0
        self.zoomValue = 0.0
        self.currentZoom = 0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def setZoom(self, value: int) -> None:
        self.currentZoom = value
        transform = QTransform()
        transform.scale(value, value)
        self.setTransform(transform)
        self.dragEvent.emit(DragEventType.repaint)

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
        self.dragEvent.emit(DragEventType.move)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)
        self.mousePressed.emit(event)
        self.dragEvent.emit(DragEventType.start)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.setDragMode(self.drag_mode)
        self.mouseReleased.emit(event)
        self.dragEvent.emit(DragEventType.stop)


class GraphicsImageItem:
    __slots__ = ('_graphics_item', '_pixmap')

    def __init__(self, graphics_item: QGraphicsPixmapItem) -> None:
        self._graphics_item = graphics_item
        self._pixmap = self._graphics_item.pixmap()

    def contains(self, point: QPointF) -> bool:
        return self._graphics_item.contains(point)

    def hide(self) -> None:
        self._graphics_item.hide()

    def pixmap(self) -> QPixmap:
        return self._graphics_item.pixmap()

    def setPixmap(self, new_pixmap: QPixmap | None, crop_values: CroppingInfo | None = None) -> None:
        if new_pixmap is None:
            new_pixmap = self._pixmap
        else:
            self._pixmap = new_pixmap

        if crop_values is not None and crop_values.active:
            padded = QPixmap(new_pixmap.width(), new_pixmap.height())
            padded.fill(QColor(0, 0, 0, 0))
            painter = QPainter(padded)
            painter.drawPixmap(
                QPoint(crop_values.left, crop_values.top), new_pixmap,
                QRect(crop_values.left, crop_values.top, crop_values.width, crop_values.height)
            )
            painter.end()
            new_pixmap = padded

        self._graphics_item.setPixmap(new_pixmap)

    def show(self) -> None:
        self._graphics_item.show()
