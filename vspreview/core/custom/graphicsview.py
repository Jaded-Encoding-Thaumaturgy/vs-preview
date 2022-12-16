from __future__ import annotations

from enum import IntEnum, auto

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QMouseEvent, QNativeGestureEvent, QPainter, QPixmap, QResizeEvent, QTransform, QWheelEvent
)
from PyQt6.QtWidgets import QApplication, QGraphicsPixmapItem, QGraphicsView, QWidget

from ...core import AbstractMainWindow
from ..types.dataclasses import CroppingInfo


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

    underReload = False
    last_positions = (0, 0)

    autofit = False
    main: AbstractMainWindow

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.app = QApplication.instance()
        self.angleRemainder = 0
        self.zoomValue = 0.0
        self.currentZoom = 0.0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.drag_mode = self.dragMode()

    def setZoom(self, value: float | None) -> None:
        if self.underReload or value == 0:
            return

        if value is None:
            if self.autofit:
                viewport = self.viewport()
                value = min(
                    viewport.width() / self.main.current_output.width,
                    viewport.height() / self.main.current_output.height
                )
            else:
                return

        self.currentZoom = value

        self.setTransform(QTransform().scale(value, value))
        self.dragEvent.emit(DragEventType.repaint)

    def event(self, event: QEvent) -> bool:
        if self.underReload:
            event.ignore()
            return False

        if isinstance(event, QNativeGestureEvent):
            typ = event.gestureType()
            if typ == Qt.NativeGestureType.BeginNativeGesture:
                self.zoomValue = 0.0
            elif typ == Qt.NativeGestureType.ZoomNativeGesture:
                self.zoomValue += event.value()
            if typ == Qt.NativeGestureType.EndNativeGesture:
                self.wheelScrolled.emit(-1 if self.zoomValue < 0 else 1)

        return super().event(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.underReload or self.autofit:
            return event.ignore()

        assert self.app

        modifiers = self.app.keyboardModifiers()
        mouse = event.buttons()

        if modifiers == Qt.KeyboardModifier.ControlModifier or mouse in {
            Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton
        }:
            angleDelta = event.angleDelta().y()

            # check if wheel wasn't rotated the other way since last rotation
            if self.angleRemainder * angleDelta < 0:
                self.angleRemainder = 0

            self.angleRemainder += angleDelta

            if abs(self.angleRemainder) >= self.WHEEL_STEP:
                self.wheelScrolled.emit(self.angleRemainder // self.WHEEL_STEP)
                self.angleRemainder %= self.WHEEL_STEP
            return
        elif modifiers == Qt.KeyboardModifier.NoModifier:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - event.angleDelta().y())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().x())
            return
        elif modifiers == Qt.KeyboardModifier.ShiftModifier:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - event.angleDelta().x())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().y())
            return

        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.underReload or self.autofit:
            return event.ignore()

        super().mouseMoveEvent(event)

        if self.hasMouseTracking():
            self.mouseMoved.emit(event)
        self.dragEvent.emit(DragEventType.move)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.underReload or self.autofit:
            return event.ignore()

        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        super().mousePressEvent(event)

        self.mousePressed.emit(event)
        self.dragEvent.emit(DragEventType.start)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.underReload or self.autofit:
            return event.ignore()

        super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            self.setDragMode(self.drag_mode)

        self.mouseReleased.emit(event)
        self.dragEvent.emit(DragEventType.stop)

    def beforeReload(self) -> None:
        self.underReload = True
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.last_positions = (self.verticalScrollBar().value(), self.horizontalScrollBar().value())

    def afterReload(self) -> None:
        self.underReload = False
        self.verticalScrollBar().setValue(self.last_positions[0])
        self.horizontalScrollBar().setValue(self.last_positions[1])
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def registerReloadEvents(self, main: AbstractMainWindow) -> None:
        self.main = main
        self.main.reload_before_signal.connect(self.beforeReload)
        self.main.reload_after_signal.connect(self.afterReload)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.setZoom(None)


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
