from __future__ import annotations

from abc import abstractmethod
from io import BytesIO
from math import exp, log
from pathlib import Path
from typing import TYPE_CHECKING, Sequence, cast

import matplotlib.pyplot as plt  # type: ignore
from matplotlib.backend_bases import MouseEvent as PlotMouseEvent  # type: ignore
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # type: ignore
from matplotlib.figure import Figure  # type: ignore
from matplotlib.layout_engine import ConstrainedLayoutEngine  # type: ignore
from matplotlib.lines import Line2D  # type: ignore
from matplotlib.rcsetup import cycler  # type: ignore
from PyQt6.QtCore import QEvent, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QMouseEvent, QNativeGestureEvent, QWheelEvent
from PyQt6.QtWidgets import QFileDialog, QFrame

if TYPE_CHECKING:
    from ...main import MainWindow
    from ..types import Frame

STYLE_DIR = Path(__file__).parent / 'plotting.mplstyle'


__all__ = [
    'apply_plotting_style',

    'PlottingCanvas', 'PlottingCanvasDefaultFrame',

    'PlotMouseEvent'
]


def apply_plotting_style() -> None:
    plt.style.use({
        'axes.edgecolor': '#FFFFFF3D',
        'axes.facecolor': '#FFFFFF07',
        'axes.labelcolor': '#FFFFFFD9',
        'axes.prop_cycle': cycler('color', [
            '#FF6200', '#696969', '#525199', '#60A6DA', '#D0D93C', '#A8A8A9', '#FF0000', '#349651', '#AB0066'
        ]),
        'figure.facecolor': '#19232D',
        'legend.edgecolor': '#FFFFFFD9',
        'legend.facecolor': 'inherit',
        'legend.framealpha': 0.12,
        'markers.fillstyle': 'full',
        'savefig.facecolor': '#19232D',
        'text.color': 'white',
        'xtick.color': '#FFFFFFD9',
        'ytick.color': '#FFFFFFD9'
    })


class PlottingCanvas(FigureCanvasQTAgg):
    WHEEL_STEP = 15 * 8  # degrees

    mouseMoved = pyqtSignal(QMouseEvent)
    wheelScrolled = pyqtSignal(int)

    def __init__(
        self, main: MainWindow, ylog: bool = False, xlog: bool = False, controls: bool = True,
        xpad: float | tuple[float, float] | None = None, ypad: float | tuple[float, float] | None = None,
        figsize: tuple[int, int] = (5, 4)
    ) -> None:
        from ..abstracts import HBoxLayout, PushButton
        from ..types import Stretch

        self.main = main

        self.ylog, self.xlog = ylog, xlog

        self.figure = Figure(figsize, self.main.settings.base_ppi)

        self.axes = self.figure.add_subplot(111)

        self.figure.set_layout_engine(ConstrainedLayoutEngine())

        super().__init__(self.figure)

        self.mpl_connect('motion_notify_event', self._on_mouse_moved)

        self.angleRemainder = 0
        self.zoomValue = 0.0

        self.clicked = False
        self.old_pos = QPointF(0.0, 0.0)

        self.controls = QFrame()

        self.copy_frame_button = PushButton('Copy Graph', clicked=self.copy_graph_to_clipboard)

        self.save_frame_as_button = PushButton('Save Graph as', clicked=self.on_save_graph_as_clicked)

        _controls = [self.copy_frame_button, self.save_frame_as_button, Stretch()]

        if controls:
            self.controls = HBoxLayout(_controls)
        else:
            self.controls = QFrame()
            HBoxLayout(self.controls, _controls)
            self.controls.hide()

        self.xpad = (xpad, xpad) if (not isinstance(xpad, tuple) and xpad is not None) else xpad
        self.ypad = (ypad, ypad) if (not isinstance(ypad, tuple) and ypad is not None) else ypad

    def _on_mouse_moved(self, event: PlotMouseEvent) -> None:
        if not event.inaxes or not self.axes.lines:
            return

        if event.xdata is None or event.ydata is None:
            return

        if event.xdata < self.line._xorig[0] or event.xdata > self.line._xorig[-1]:
            return

        self.on_mouse_moved(event)

    def on_mouse_moved(self, event: PlotMouseEvent) -> None:
        ...

    @classmethod
    def limits_to_range(cls, lim: tuple[int, int]) -> int:
        return lim[1] - lim[0]

    @property
    def line(self) -> Line2D:
        return cast(Line2D, self.axes.lines[0])

    @property
    def cur_lims(self) -> tuple[tuple[float, float], tuple[float, float]]:

        try:
            return (
                tuple[float, float](log(x) if self.xlog else x for x in self.axes.get_xlim()),
                tuple[float, float](log(x) if self.ylog else x for x in self.axes.get_ylim())
            )
        except ValueError:
            return (self.axes.get_xlim(), self.axes.get_ylim())

    @cur_lims.setter
    def cur_lims(self, new_lims: tuple[Sequence[float], Sequence[float]]) -> None:
        new_xlim, new_ylim = new_lims

        try:
            self.axes.set_xlim(tuple[float, float](exp(x) if self.xlog else x for x in new_xlim))
            self.axes.set_ylim(tuple[float, float](exp(x) if self.ylog else x for x in new_ylim))

            self.figure.canvas.draw_idle()
        except OverflowError:
            # zooming/panning too much
            ...

    def event(self, event: QEvent) -> bool:
        if isinstance(event, QNativeGestureEvent):
            typ = event.gestureType()

            if typ == Qt.NativeGestureType.BeginNativeGesture:
                self.zoomValue = 0.0
            elif typ == Qt.NativeGestureType.ZoomNativeGesture:
                self.zoomValue += event.value()

            if typ == Qt.NativeGestureType.EndNativeGesture:
                self.zoom_function(event, -1 if self.zoomValue < 0 else 1)

        return super().event(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked = True

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.clicked = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.mouseMoved.emit(event)

        if self.clicked:
            cur_xlim, cur_ylim = self.cur_lims

            curr_pos = event.globalPosition()

            rel_x = self.old_pos.x() - curr_pos.x()
            rel_y = self.old_pos.y() - curr_pos.y()

            width, height = self.get_width_height()
            v_width, v_height = cur_xlim[1] - cur_xlim[0], cur_ylim[1] - cur_ylim[0]

            xrate = rel_x * v_width / width
            yrate = rel_y * v_height / height

            self.cur_lims = (
                (x + xrate for x in cur_xlim),
                (x - yrate for x in cur_ylim)
            )

        self.old_pos = event.globalPosition()

        try:
            super().mouseMoveEvent(event)
        except Exception:
            event.ignore()

    def wheelEvent(self, event: QWheelEvent) -> None:
        modifier = event.modifiers()
        mouse = event.buttons()

        if modifier == Qt.KeyboardModifier.ControlModifier or mouse in {
            Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton
        }:
            angleDelta = event.angleDelta().y()

            if self.angleRemainder * angleDelta < 0:
                self.angleRemainder = 0

            self.angleRemainder += angleDelta

            if abs(self.angleRemainder) >= self.WHEEL_STEP:
                steps = self.angleRemainder // self.WHEEL_STEP
                self.zoomValue += steps
                self.zoom_function(event, steps)

                self.angleRemainder %= self.WHEEL_STEP

        event.ignore()

    def zoom_function(self, event: QWheelEvent, steps: int) -> None:
        if not steps:
            return

        scale_factor = 1
        base_scale = 1.1

        for _ in range(abs(steps)):
            if steps > 0:
                scale_factor *= base_scale
            else:
                scale_factor /= base_scale

        cur_xlim, cur_ylim = self.cur_lims

        pos = event.position()
        xdata, ydata = pos.x(), pos.y()
        width, height = self.get_width_height()

        xrate, yrate = xdata / width, ydata / height

        xabs = cur_xlim[1] * xrate + cur_xlim[0] * (1 - xrate)
        yabs = cur_ylim[0] * yrate + cur_ylim[1] * (1 - yrate)

        new_width = abs(cur_xlim[1] - cur_xlim[0]) / scale_factor
        new_height = abs(cur_ylim[1] - cur_ylim[0]) / scale_factor

        self.cur_lims = (
            (xabs - new_width * xrate, xabs + new_width * (1 - xrate)),
            (yabs - new_height * (1 - yrate), yabs + new_height * yrate)
        )

    def clear(self) -> None:
        self.axes.clear()

        if self.ylog:
            self.axes.set_yscale("log")

        if self.xlog:
            self.axes.set_xscale("log")

    def draw(self) -> None:
        if 0 not in self.figure.get_size_inches():
            super().draw()

    def copy_graph_to_clipboard(self) -> None:
        buffer = BytesIO()

        self.figure.savefig(buffer, transparent=False)

        self.main.clipboard.setImage(QImage.fromData(buffer.getvalue()))

        buffer.close()

        self.main.show_message('Graph successfully copied to clipboard')

    def on_save_graph_as_clicked(self, checked: bool | None = None) -> None:
        save_path_str, _ = QFileDialog.getSaveFileName(
            self.main, 'Save as', f'graph_{self.main.current_output.last_showed_frame}', 'Graph (*.svg)'
        )

        self.figure.savefig(save_path_str, transparent=False)

    @abstractmethod
    def _render(self, frame: Frame) -> None:
        raise NotImplementedError

    def render(self, frame: Frame, set_lims: bool = True) -> None:
        if not set_lims:
            self.zoomValue = 0.0

        lims = self.cur_lims if self.zoomValue else None

        self.clear()

        self._render(frame)

        self.axes.legend()
        self.figure.canvas.draw_idle()

        if lims:
            self.cur_lims = lims
        elif self.xpad or self.ypad:
            xlim, ylim = self.cur_lims

            line = self.line

            self.cur_lims = (
                (line._xorig[0] - self.xpad[0], line._xorig[-1] + self.xpad[1]) if self.xpad else xlim,
                (line._yorig[0] - self.ypad[0], line._yorig[-1] + self.ypad[1]) if self.ypad else ylim
            )


class PlottingCanvasDefaultFrame(PlottingCanvas):
    def render(self, frame: Frame | None = None, set_lims: bool = True) -> None:
        if not self.main.current_output:
            return

        if frame is None:
            frame = self.main.current_output.last_showed_frame

        super().render(frame, set_lims)
