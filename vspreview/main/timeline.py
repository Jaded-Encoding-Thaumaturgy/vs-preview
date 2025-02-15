from __future__ import annotations

from copy import deepcopy
from math import floor
from typing import Any, Iterable, Sequence, cast
from time import perf_counter_ns

from PyQt6.QtCore import QEvent, QLineF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QMoveEvent, QPainter, QPaintEvent, QPalette, QPen, QResizeEvent
from PyQt6.QtWidgets import QApplication, QToolTip, QWidget
from jetpytools import to_arr

from ..core import AbstractYAMLObject, Frame, Notch, Notches, NotchProvider, Time, main_window
from ..utils import strfdelta

__all__ = [
    'Timeline'
]


class Timeline(QWidget):
    __slots__ = (
        'app', 'main',
        'rectF', 'prevRectF',
        'totalT', 'totalF',
        'notchIntervalTargetX', 'notchHeight', 'fontHeight',
        'notchLabelInterval', 'notchScrollInterval', 'scrollHeight',
        'cursorX', 'cursorFT', 'needFullRepaint',
        'scrollRect',
    )

    class Mode(AbstractYAMLObject):
        FRAME = 'frame'
        TIME = 'time'

    clicked = pyqtSignal(Frame, Time)

    def __init__(self, parent: QWidget, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self.app = QApplication.instance()
        self.main = main_window()

        self._mode = self.Mode.TIME

        self.rect_f = QRectF()

        self.set_sizes()

        self._cursor_x: int | Frame | Time = 0

        self.notches = dict[NotchProvider, Notches]()

        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMouseTracking(True)

        self.main.reload_before_signal.connect(lambda: self.__setattr__('_after_reload', True))

        self.mousepressed = False
        self.lastpaint = perf_counter_ns()

    @property
    def cursor_x(self) -> int:
        return self.c_to_x(self._cursor_x)

    @cursor_x.setter
    def cursor_x(self, x: int | Frame | Time) -> None:
        self._cursor_x = x
        self.update()

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value == self._mode:
            return

        self._mode = value
        self.update()

    def set_sizes(self) -> None:
        self.notches_cache = _default_cache

        self.notch_interval_target_x = round(75 * self.main.display_scale)
        self.notch_height = round(6 * self.main.display_scale)
        self.font_height = round(10 * self.main.display_scale)
        self.notch_scroll_interval = round(2 * self.main.display_scale)
        self.scroll_height = round(10 * self.main.display_scale)

        self.setMinimumSize(self.notch_interval_target_x, round(33 * self.main.display_scale))

        font = self.main.font()
        font.setPixelSize(self.font_height)
        self.setFont(font)

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        self.rect_f = QRectF(event.rect())

        self.drawWidget(QPainter(self))

    def drawWidget(self, painter: QPainter) -> None:
        setup_key = (self.rect_f, self.main.current_output.index)

        curr_key, (scroll_rect, labels_notches, rects_to_draw) = self.notches_cache[self.mode]

        if setup_key != curr_key:
            lnotch_y, lnotch_x = self.rect_f.top() + self.font_height + self.notch_height + 5, self.rect_f.left()
            lnotch_top = lnotch_y - self.notch_height

            labels_notches = Notches()

            if self.mode == self.Mode.TIME:
                max_value = self.main.current_output.total_time
                notch_interval = self.calculate_notch_interval_t(self.notch_interval_target_x)
                label_format = self.generate_label_format(notch_interval, max_value)
                label_notch = Time()
            elif self.mode == self.Mode.FRAME:
                max_value = self.main.current_output.total_frames - 1  # type: ignore
                notch_interval = self.calculate_notch_interval_f(self.notch_interval_target_x)  # type: ignore
                label_notch = Frame()  # type: ignore

            while (lnotch_x < self.rect_f.right() and label_notch <= max_value):
                labels_notches.add(
                    Notch(deepcopy(label_notch), line=QLineF(lnotch_x, lnotch_y, lnotch_x, lnotch_top))
                )
                label_notch += notch_interval
                lnotch_x = self.c_to_x(label_notch)

            labels_notches.add(
                Notch(max_value, line=QLineF(self.rect_f.right() - 1, lnotch_y, self.rect_f.right() - 1, lnotch_top))
            )

            scroll_rect = QRectF(
                self.rect_f.left(), lnotch_y + self.notch_scroll_interval, self.rect_f.width(), self.scroll_height
            )

        cursor_line = QLineF(
            self.cursor_x, scroll_rect.top(), self.cursor_x, scroll_rect.top() + scroll_rect.height() - 1
        )

        for provider, notches in self.notches.items():
            if not provider.is_notches_visible:
                continue

            notches.norm_lines(self, scroll_rect)

        painter.fillRect(self.rect_f, self.palette().color(QPalette.ColorRole.Window))
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.WindowText)))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if setup_key != curr_key:
            rects_to_draw = []

            for i, notch in enumerate(labels_notches):
                anchor_rect = QRectF(notch.line.x2(), notch.line.y2(), 0, 0)

                if self.mode == self.Mode.TIME:
                    time = cast(Time, notch.data)
                    label = strfdelta(time, label_format)
                elif self.mode == self.Mode.FRAME:
                    label = str(notch.data)

                if i == 0:
                    rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, label
                    )
                    if self.mode == self.Mode.TIME:
                        rect.moveLeft(-2.5)
                elif i == (len(labels_notches) - 1):
                    rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, label
                    )
                elif i == (len(labels_notches) - 2):
                    rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, label
                    )

                    last_notch = labels_notches[-1]

                    if self.mode == self.Mode.TIME:
                        last_label = strfdelta(cast(Time, last_notch.data), label_format)
                    elif self.mode == self.Mode.FRAME:
                        last_label = str(last_notch.data)

                    anchor_rect = QRectF(last_notch.line.x2(), last_notch.line.y2(), 0, 0)
                    last_rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, last_label
                    )

                    if last_rect.left() - rect.right() < self.notch_interval_target_x / 10:
                        labels_notches.items.pop(-2)
                        rects_to_draw.append((last_rect, last_label))
                        break
                else:
                    rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, label
                    )

                rects_to_draw.append((rect, label))

                self.notches_cache[self.mode] = (setup_key, (scroll_rect, labels_notches, rects_to_draw))

        for rect, text in rects_to_draw:
            painter.drawText(rect, text)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.drawLines([notch.line for notch in labels_notches])  # type: ignore
        painter.fillRect(scroll_rect, Qt.GlobalColor.gray)

        for provider, notches in self.notches.items():
            if not provider.is_notches_visible:
                continue

            for notch in notches:
                painter.setPen(notch.color)
                painter.drawLine(notch.line)

        painter.setPen(Qt.GlobalColor.black)
        painter.drawLine(cursor_line)

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.mousepressed = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)

        self.mousepressed = True
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)

        if self.mousepressed and (
            (perf_counter_ns() - self.lastpaint) / 100000 > self.main.settings.dragtimeline_timeout
        ):
            pos = event.pos().toPointF()
            pos.setY(self.notches_cache[self.mode][1][0].top() + 1)

            if self.notches_cache[self.mode][1][0].contains(pos):
                self.cursor_x = int(pos.x())
                self.clicked.emit(self.x_to_f(self.cursor_x), self.x_to_t(self.cursor_x))
                self.lastpaint = perf_counter_ns()

        for provider, notches in self.notches.items():
            if not provider.is_notches_visible:
                continue

            for notch in notches:
                line = notch.line
                if line.x1() - 0.5 <= event.pos().x() <= line.x1() + 0.5:
                    QToolTip.showText(event.globalPosition().toPoint(), notch.label)
                    return

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update()

    def event(self, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.Polish, QEvent.Type.ApplicationPaletteChange}:
            self.setPalette(self.main.palette())
            self.update()
            return True

        return super().event(event)

    def update_notches(self, provider: NotchProvider | Sequence[NotchProvider] | None = None) -> None:
        if provider is None:
            provider = [*self.main.toolbars, *self.main.plugins]

        for t in cast(list[NotchProvider], to_arr(provider)):
            if t.is_notches_visible:
                self.notches[t] = t.get_notches()

        self.update()

    def calculate_notch_interval_t(self, target_interval_x: int) -> Time:
        notch_intervals_t = list(
            Time(seconds=n) for n in [
                1, 2, 5, 10, 15, 30, 60, 90, 120, 300, 600,
                900, 1200, 1800, 2700, 3600, 5400, 7200
            ]
        )

        margin = 1 + self.main.settings.timeline_label_notches_margin / 100
        target_interval_t = self.x_to_t(target_interval_x)

        if target_interval_t >= notch_intervals_t[-1] * margin:
            return notch_intervals_t[-1]

        for interval in notch_intervals_t:
            if target_interval_t < interval * margin:
                return interval

        raise RuntimeError

    notch_intervals_f = list(map(Frame, [
        1, 5, 10, 20, 25, 50, 75, 100, 200, 250, 500, 750, 1000,
        2000, 2500, 5000, 7500, 10000, 20000, 25000, 50000, 75000
    ]))

    def calculate_notch_interval_f(self, target_interval_x: int) -> Frame:
        margin = 1 + self.main.settings.timeline_label_notches_margin / 100

        target_interval_f = self.x_to_f(target_interval_x)

        if target_interval_f >= Frame(round(int(self.notch_intervals_f[-1]) * margin)):
            return self.notch_intervals_f[-1]

        for interval in self.notch_intervals_f:
            if target_interval_f < Frame(round(int(interval) * margin)):
                return interval

        raise RuntimeError

    def generate_label_format(self, notch_interval_t: Time, end_time: Time | Time) -> str:
        if end_time >= Time(hours=1):
            return '%h:%M:00'

        if notch_interval_t >= Time(minutes=1):
            return '%m:00'

        if end_time > Time(seconds=10):
            return '%m:%S'

        return '%s.%Z'

    def x_to_t(self, x: int) -> Time:
        return Time(seconds=(x * float(self.main.current_output.total_time) / self.rect_f.width()))

    def x_to_f(self, x: int) -> Frame:
        return Frame(round(x / self.rect_f.width() * int(self.main.current_output.total_frames)))

    def c_to_x(self, cursor: int | Frame | Time) -> int:
        if isinstance(cursor, int):
            return cursor

        try:
            if isinstance(cursor, Frame):
                return round(int(cursor) / int(self.main.current_output.total_frames) * self.rect_f.width())

            if isinstance(cursor, Time):
                return floor(float(cursor) / float(self.main.current_output.total_time) * self.rect_f.width())
        except ZeroDivisionError:
            ...

        return 0

    def cs_to_x(self, *cursors: int | Frame | Time) -> Iterable[int]:
        r_f = self.rect_f.width()
        t_d = float(self.main.current_output.total_time) * r_f
        f_d = int(self.main.current_output.total_frames) * r_f

        for c in cursors:
            if isinstance(c, int):
                yield c

            try:
                yield round(int(c) / (f_d if isinstance(c, Time) else t_d))
            except ZeroDivisionError:
                yield 0


_default_cache = {
    Timeline.Mode.FRAME: ((QRectF(), -1), (QRectF(), Notches(), list[tuple[QRectF, str]]())),
    Timeline.Mode.TIME: ((QRectF(), -1), (QRectF(), Notches(), list[tuple[QRectF, str]]()))
}
