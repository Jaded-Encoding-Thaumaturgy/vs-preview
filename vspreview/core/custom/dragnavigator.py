from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

from .graphicsview import DragEventType, GraphicsView

if TYPE_CHECKING:
    from ...main import MainWindow


__all__ = [
    'DragNavigator'
]


class DragNavigator(QWidget):
    __slots__ = ()

    is_tracking = False

    contentsH = contentsW = viewportX = viewportY = viewportH = viewportW = 0

    def __init__(self, main: MainWindow, graphics_view: GraphicsView) -> None:
        from ..abstracts import Timer

        super().__init__(graphics_view)

        self.main = main
        self.graphics_view = graphics_view
        self.graphics_view.dragEvent.connect(self.on_drag)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        rate = self.main.settings.base_ppi / 96
        self.setGeometry(round(10 * rate), round(10 * rate), round(120 * rate), round(120 * rate))
        self.repaint_timer = Timer(
            timeout=self.repaint_timeout, timerType=Qt.TimerType.PreciseTimer,
            interval=self.main.settings.dragnavigator_timeout
        )
        self.graphics_view.verticalScrollBar().valueChanged.connect(partial(self.on_drag, DragEventType.repaint))
        self.graphics_view.horizontalScrollBar().valueChanged.connect(partial(self.on_drag, DragEventType.repaint))

    def on_drag(self, event_type: DragEventType) -> None:
        # while reloading and moving mouse
        if not hasattr(self.main, 'current_output') or not self.main.current_output:
            return

        if event_type == DragEventType.repaint:
            self.repaint_timer.stop()
            self.repaint_timer.start()
        elif event_type == DragEventType.move and not self.is_tracking:
            return
        elif event_type == DragEventType.start:
            self.is_tracking = True
        elif event_type == DragEventType.stop:
            self.is_tracking = False
            self.setVisible(False)
            return

        scrollbarW = self.graphics_view.horizontalScrollBar()
        scrollbarH = self.graphics_view.verticalScrollBar()

        if not any({scrollbarW.isVisible(), scrollbarH.isVisible()}):
            return self.hide()

        self.setVisible(True)
        self.draw(
            self.main.current_output.width,
            self.main.current_output.height,
            int(scrollbarW.value() / self.graphics_view.currentZoom),
            int(scrollbarH.value() / self.graphics_view.currentZoom),
            int(self.graphics_view.width() / self.graphics_view.currentZoom),
            int(self.graphics_view.height() / self.graphics_view.currentZoom)
        )

    def draw(
        self, contentsW: int, contentsH: int, viewportX: int, viewportY: int, viewportW: int, viewportH: int
    ) -> None:
        self.contentsW = contentsW
        self.contentsH = contentsH
        self.viewportW = min(viewportW, contentsW)
        self.viewportH = min(viewportH, contentsH)
        self.viewportX = min(viewportX, contentsW)
        self.viewportY = min(viewportY, contentsH)

        self.repaint()

    def repaint_timeout(self) -> None:
        self.hide()
        self.repaint_timer.stop()

    def paintEvent(self, event: QPaintEvent) -> None:
        if (self.contentsW == 0) or (self.contentsH == 0) or (self.viewportW == 0) or \
                (self.viewportH == 0) or (self.viewportX >= self.contentsW) or (self.viewportY >= self.contentsH):
            event.ignore()
            return

        norm = 100.0 / max(self.contentsW, self.contentsH, self.viewportW, self.viewportH)

        normContentsWidth, normContentsHeight = round(self.contentsW * norm), round(self.contentsH * norm)
        normViewportWidth, normViewportHeight = round(self.viewportW * norm), round(self.viewportH * norm)
        normVieportX = min(round(self.viewportX * norm), normContentsWidth - normViewportWidth)
        normViwportY = min(round(self.viewportY * norm), normContentsHeight - normViewportHeight)

        cX1 = cY1 = 0
        cX2, cY2 = normContentsWidth - 1, normContentsHeight - 1

        vX1, vY1 = normVieportX, normViwportY
        vX2, vY2 = normVieportX + normViewportWidth - 1, normViwportY + normViewportHeight - 1

        painter = QPainter(self)

        painter.setPen(QColor(255, 0, 255))
        painter.drawLine(cX1, cY1, cX2, cY1)
        painter.drawLine(cX2, cY1, cX2, cY2)
        painter.drawLine(cX2, cY2, cX1, cY2)
        painter.drawLine(cX1, cY2, cX1, cY1)

        painter.setPen(QColor(0, 255, 0))
        painter.drawLine(vX1, vY1, vX2, vY1)
        painter.drawLine(vX2, vY1, vX2, vY2)
        painter.drawLine(vX2, vY2, vX1, vY2)
        painter.drawLine(vX1, vY2, vX1, vY1)

        event.accept()
