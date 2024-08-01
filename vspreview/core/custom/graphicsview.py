from __future__ import annotations

from enum import IntEnum, auto
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, Qt, pyqtSignal, QRectF
from PyQt6.QtGui import (
    QColor, QMouseEvent, QNativeGestureEvent, QPainter, QPalette, QPixmap, QResizeEvent, QTransform, QWheelEvent
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QSizePolicy, QWidget
)

if TYPE_CHECKING:
    from ...main import MainWindow
    from ..types import ArInfo, CroppingInfo


__all__ = [
    'DragEventType',
    'GraphicsView',
    'GraphicsImageItem',
    'MainVideoOutputGraphicsView'
]


class DragEventType(IntEnum):
    start = auto()
    stop = auto()
    move = auto()
    repaint = auto()


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

    def setPixmap(
        self, new_pixmap: QPixmap | None,
        crop_values: CroppingInfo | None = None,
        ar_values: ArInfo | None = None
    ) -> None:

        sizes = (self._pixmap.width(), self._pixmap.height())

        if new_pixmap is None:
            new_pixmap = self._pixmap
        else:
            self._pixmap = new_pixmap

        if ar_values is not None and ar_values.active:
            new_pixmap = self._set_ar(new_pixmap, ar_values)

        if crop_values is not None and crop_values.active:
            new_pixmap = self._set_crop(new_pixmap, crop_values)

        self._graphics_item.setPixmap(new_pixmap)

        if sizes != (new_pixmap.width(), new_pixmap.height()):
            from ...core import main_window

            main_window().refresh_graphics_views()

    def show(self) -> None:
        self._graphics_item.show()

    def _set_ar(self, pixmap: QPixmap, ar_values: ArInfo) -> QPixmap:
        if ar_values.sarnum == ar_values.sarden:
            return pixmap

        new_width = pixmap.width()
        new_height = pixmap.height()

        ar_hz = pixmap.width() * ar_values.sarnum / ar_values.sarden
        ar_vt = pixmap.height() * ar_values.sarden / ar_values.sarnum

        if ar_hz >= pixmap.width():
            new_width = int(ar_hz)
        else:
            new_height = int(ar_vt)

        stretched = QPixmap(new_width, new_height)
        painter = QPainter(stretched)

        # TODO: Somehow allow the user to define the scaler used (using vskernels as ref)
        painter.drawPixmap(
            QPoint(0, 0), pixmap.scaled(
                new_width, new_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ),
            QRect(0, 0, new_width, new_height)
        )

        painter.end()

        return stretched

    def _set_crop(self, pixmap: QPixmap, crop_values: CroppingInfo) -> QPixmap:
        padded = QPixmap(pixmap.width(), pixmap.height())
        padded.fill(QColor(0, 0, 0, 0))

        painter = QPainter(padded)
        painter.drawPixmap(
            QPoint(crop_values.left, crop_values.top), pixmap,
            QRect(crop_values.left, crop_values.top, crop_values.width, crop_values.height)
        )

        painter.end()

        return padded


class GraphicsScene(QGraphicsScene):
    def __init__(self, view: GraphicsView) -> None:
        self.view = view
        self.main = self.view.main

        self.graphics_items = list[GraphicsImageItem]()

        super().__init__(self.main)

    def init_scenes(self) -> None:
        self.clear()
        self.graphics_items.clear()

        for _ in range(len(self.main.outputs)):
            raw_frame_item = self.addPixmap(QPixmap())
            raw_frame_item.hide()

            self.graphics_items.append(GraphicsImageItem(raw_frame_item))

    @property
    def current_scene(self) -> GraphicsImageItem:
        return self.graphics_items[self.main.current_output.index]


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

    _autofit = False
    main: MainWindow

    def __init__(self, main: MainWindow, parent: QWidget | None = None) -> None:
        from ...core import CheckBox, HBoxLayout
        from .combobox import ComboBox

        super().__init__(parent)

        self.main = main

        self.app = QApplication.instance()
        self.angleRemainder = 0
        self.zoomValue = 0.0
        self.currentZoom = 0.0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.drag_mode = self.dragMode()

        self.main.reload_stylesheet_signal.connect(
            lambda: self.setBackgroundBrush(self.main.palette().brush(QPalette.ColorRole.Window))
        )

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        if self.main.settings.opengl_rendering_enabled:
            from PyQt6.QtOpenGLWidgets import QOpenGLWidget
            self.setViewport(QOpenGLWidget())

        self.wheelScrolled.connect(self.on_wheel_scrolled)
        self.main.reload_before_signal.connect(self.beforeReload)
        self.main.reload_after_signal.connect(self.afterReload)

        self.graphics_scene = GraphicsScene(self)
        self.setScene(self.graphics_scene)

        self.zoom_combobox = ComboBox[float](self, minimumContentsLength=4)

        self.auto_fit_button = CheckBox('Auto-fit', self, clicked=self.auto_fit_button_clicked)

        self.controls = QFrame()
        HBoxLayout(self.controls, [self.zoom_combobox, self.auto_fit_button])

        self.main.register_graphic_view(self)

        self.dragEvent.connect(self.propagate_move_event)

    def auto_fit_button_clicked(self, checked: bool) -> None:
        self.autofit = checked

    @property
    def current_scene(self) -> GraphicsImageItem:
        return self.graphics_scene.current_scene

    @property
    def autofit(self) -> bool:
        return self._autofit

    @autofit.setter
    def autofit(self, new_state: bool) -> None:
        self.zoom_combobox.setEnabled(not new_state)

        self._autofit = new_state

        if new_state:
            self.setZoom(None)
        else:
            self.setZoom(self.zoom_combobox.currentData())

    def setup_view(self) -> None:
        for item in self.graphics_scene.graphics_items:
            item.hide()

        self.current_scene.show()
        self.graphics_scene.setSceneRect(QRectF(self.current_scene.pixmap().rect()))

    def bind_to(self, other_view: GraphicsView, *, mutual: bool = True) -> None:
        self.main.bound_graphics_views[other_view].add(self)

        if mutual:
            self.main.bound_graphics_views[self].add(other_view)

    def on_wheel_scrolled(self, steps: int) -> None:
        new_index = self.zoom_combobox.currentIndex() + steps

        if new_index < 0:
            new_index = 0
        elif new_index >= len(self.main.settings.zoom_levels):
            new_index = len(self.main.settings.zoom_levels) - 1

        self.zoom_combobox.setCurrentIndex(new_index)

    def setZoom(self, value: float | None) -> None:
        for view in self.main.bound_graphics_views[self]:
            view._setZoom(value)

    def _setZoom(self, value: float | None) -> None:
        if self.underReload or value == 0:
            return

        if value is None:
            if not self.autofit:
                return

            viewport = self.viewport()
            value = min(viewport.width() / self.content_width, viewport.height() / self.content_height)

        self.currentZoom = value / self.devicePixelRatio()

        self.setTransform(QTransform().scale(self.currentZoom, self.currentZoom))
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

        modifier = event.modifiers()
        mouse = event.buttons()

        self.propagate_move_event()

        if modifier == Qt.KeyboardModifier.ControlModifier or mouse in {
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
        elif modifier == Qt.KeyboardModifier.NoModifier:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - event.angleDelta().y())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().x())
            return
        elif modifier == Qt.KeyboardModifier.ShiftModifier:
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

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.setZoom(None)

    def propagate_move_event(self, _: Any = None) -> None:
        scrollbarW, scrollbarH = self.horizontalScrollBar(), self.verticalScrollBar()

        if not any({scrollbarW.isVisible(), scrollbarH.isVisible()}):
            return

        widthMax, heightMax = scrollbarW.maximum(), scrollbarH.maximum()

        for view in self.main.bound_graphics_views[self] - {self}:
            if view.isVisible():
                wBar, hBar = view.horizontalScrollBar(), view.verticalScrollBar()

                if widthMax:
                    wBar.setValue(int(scrollbarW.value() * wBar.maximum() / widthMax))

                if heightMax:
                    hBar.setValue(int(scrollbarH.value() * hBar.maximum() / heightMax))

    @property
    def content_width(self) -> int:
        raise NotImplementedError

    @property
    def content_height(self) -> int:
        raise NotImplementedError


class MainVideoOutputGraphicsView(GraphicsView):
    @property
    def content_width(self) -> int:
        return self.main.current_output.width

    @property
    def content_height(self) -> int:
        return self.main.current_output.height
