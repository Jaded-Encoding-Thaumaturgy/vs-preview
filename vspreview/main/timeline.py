from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterator, cast

from PyQt6.QtCore import QEvent, QLineF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QMoveEvent, QPainter, QPaintEvent, QPalette, QPen, QResizeEvent
from PyQt6.QtWidgets import QApplication, QToolTip, QWidget

from ..core import AbstractToolbar, AbstractYAMLObject, Frame, Scene, Time, main_window, VideoOutput
from ..utils import strfdelta


class Notch:
    def __init__(
        self, data: Frame | Time, color: QColor = cast(QColor, Qt.GlobalColor.white),
        label: str = '', line: QLineF = QLineF()
    ) -> None:
        self.data = data
        self.color = color
        self.label = label
        self.line = line

    def __repr__(self) -> str:
        return '{}({}, {}, {}, {})'.format(
            type(self).__name__, repr(self.data), repr(self.color),
            repr(self.label), repr(self.line))


class Notches:
    def __init__(self, other: Notches | None = None) -> None:
        self.items = list[Notch]()

        if other is None:
            return
        self.items = other.items

    def add(
        self, data: Frame | Scene | Time | Notch,
        color: QColor = cast(QColor, Qt.GlobalColor.white),
        label: str = ''
    ) -> None:
        if isinstance(data, Notch):
            self.items.append(data)
        elif isinstance(data, Scene):
            if label == '':
                label = data.label
            self.items.append(Notch(data.start, color, label))
            if data.end != data.start:
                self.items.append(Notch(data.end, color, label))
        elif isinstance(data, (Frame, Time)):
            self.items.append(Notch(data, color, label))
        else:
            raise TypeError

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Notch:
        return self.items[index]

    def __iter__(self) -> Iterator[Notch]:
        return iter(self.items)

    def __repr__(self) -> str:
        return '{}({})'.format(type(self).__name__, repr(self.items))


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

        @classmethod
        def is_valid(cls, value: str) -> bool:
            return value in {cls.FRAME, cls.TIME}

    clicked = pyqtSignal(Frame, Time)

    def __init__(self, parent: QWidget, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self.app = QApplication.instance()
        self.main = main_window()

        self._mode = self.Mode.TIME

        self.rect_f = QRectF()

        self.end_t = Time(seconds=1)
        self.end_f = Frame(1)

        self.notch_interval_target_x = round(75 * self.main.display_scale)
        self.notch_height = round(6 * self.main.display_scale)
        self.font_height = round(10 * self.main.display_scale)
        self.notch_label_interval = round(-1 * self.main.display_scale)
        self.notch_scroll_interval = round(2 * self.main.display_scale)
        self.scroll_height = round(10 * self.main.display_scale)

        self.setMinimumSize(self.notch_interval_target_x, round(33 * self.main.display_scale))

        font = self.font()
        font.setPixelSize(self.font_height)
        self.setFont(font)

        self.cursor_x = 0
        # used as a fallback when self.rectF.width() is 0,
        # so cursorX is incorrect
        self.cursor_ftx: Frame | Time | int | None = None
        # False means that only cursor position'll be recalculated
        self.need_full_repaint = True

        self.toolbars_notches = dict[AbstractToolbar, Notches]()

        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMouseTracking(True)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        self.rect_f = QRectF(event.rect())
        # self.rectF.adjust(0, 0, -1, -1)

        if self.cursor_ftx is not None:
            self.set_position(self.cursor_ftx)
        self.cursor_ftx = None

        painter = QPainter(self)
        self.drawWidget(painter)

    def drawWidget(self, painter: QPainter) -> None:
        if self.need_full_repaint:
            labels_notches = Notches()
            label_notch_bottom = (
                self.rect_f.top() + self.font_height + self.notch_label_interval + self.notch_height + 5
            )
            label_notch_top = label_notch_bottom - self.notch_height
            label_notch_x = self.rect_f.left()

            if self.mode == self.Mode.TIME:
                notch_interval_t = self.calculate_notch_interval_t(self.notch_interval_target_x)
                label_format = self.generate_label_format(notch_interval_t, self.end_t)
                label_notch_t = Time()

                while (label_notch_x < self.rect_f.right() and label_notch_t <= self.end_t):
                    line = QLineF(label_notch_x, label_notch_bottom, label_notch_x, label_notch_top)
                    labels_notches.add(Notch(deepcopy(label_notch_t), line=line))
                    label_notch_t += notch_interval_t
                    label_notch_x = self.t_to_x(label_notch_t)

            elif self.mode == self.Mode.FRAME:
                notch_interval_f = self.calculate_notch_interval_f(self.notch_interval_target_x)
                label_notch_f = Frame(0)

                while (label_notch_x < self.rect_f.right() and label_notch_f <= self.end_f):
                    line = QLineF(label_notch_x, label_notch_bottom, label_notch_x, label_notch_top)
                    labels_notches.add(Notch(deepcopy(label_notch_f), line=line))
                    label_notch_f += notch_interval_f
                    label_notch_x = self.f_to_x(label_notch_f)

            self.scroll_rect = QRectF(
                self.rect_f.left(),
                label_notch_bottom + self.notch_scroll_interval,
                self.rect_f.width(), self.scroll_height
            )

            for toolbar, notches in self.toolbars_notches.items():
                if not toolbar.is_notches_visible():
                    continue

                for notch in notches:
                    if isinstance(notch.data, Frame):
                        x = self.f_to_x(notch.data)
                    elif isinstance(notch.data, Time):
                        x = self.t_to_x(notch.data)
                    y = self.scroll_rect.top()
                    notch.line = QLineF(x, y, x, y + self.scroll_rect.height() - 1)

        cursor_line = QLineF(
            self.cursor_x, self.scroll_rect.top(), self.cursor_x,
            self.scroll_rect.top() + self.scroll_rect.height() - 1
        )

        # drawing

        if self.need_full_repaint:
            painter.fillRect(self.rect_f, self.palette().color(QPalette.ColorRole.Window))

            painter.setPen(QPen(self.palette().color(QPalette.ColorRole.WindowText)))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.drawLines([notch.line for notch in labels_notches])
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            for i, notch in enumerate(labels_notches):
                line = notch.line
                anchor_rect = QRectF(
                    line.x2(), line.y2() - self.notch_label_interval, 0, 0)

                if self.mode == self.Mode.TIME:
                    time = cast(Time, notch.data)
                    label = strfdelta(time, label_format)
                if self.mode == self.Mode.FRAME:
                    label = str(notch.data)

                if i == 0:
                    rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, label
                    )
                    if self.mode == self.Mode.TIME:
                        rect.moveLeft(-2.5)
                elif i == (len(labels_notches) - 1):
                    rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, label
                    )
                    if rect.right() > self.rect_f.right():
                        rect = painter.boundingRect(
                            anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, label
                        )
                else:
                    rect = painter.boundingRect(
                        anchor_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                        label)
                painter.drawText(rect, label)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.scroll_rect, Qt.GlobalColor.gray)

        for toolbar, notches in self.toolbars_notches.items():
            if not toolbar.is_notches_visible():
                continue

            for notch in notches:
                painter.setPen(notch.color)
                painter.drawLine(notch.line)

        painter.setPen(Qt.GlobalColor.black)
        painter.drawLine(cursor_line)

        self.need_full_repaint = False

    def full_repaint(self) -> None:
        self.need_full_repaint = True
        self.update()

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self.full_repaint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        pos = event.pos().toPointF()
        if self.scroll_rect.contains(pos):
            self.set_position(int(pos.x()))
            self.clicked.emit(self.x_to_f(self.cursor_x, Frame), self.x_to_t(self.cursor_x, Time))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        for toolbar, notches in self.toolbars_notches.items():
            if not toolbar.is_notches_visible():
                continue
            for notch in notches:
                line = notch.line
                if line.x1() - 0.5 <= event.pos().x() <= line.x1() + 0.5:
                    QToolTip.showText(event.globalPosition(), notch.label)
                    return

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.full_repaint()

    def event(self, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.Polish, QEvent.Type.ApplicationPaletteChange}:
            self.setPalette(self.main.palette())
            self.full_repaint()
            return True

        return super().event(event)

    def update_notches(self, toolbar: AbstractToolbar | None = None) -> None:
        if toolbar is not None:
            self.toolbars_notches[toolbar] = toolbar.get_notches()
        if toolbar is None:
            for t in self.main.toolbars:
                self.toolbars_notches[t] = t.get_notches()
        self.full_repaint()

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value == self._mode:
            return

        self._mode = value
        self.full_repaint()

    notch_intervals_t = list(
        Time(seconds=n) for n in [
            1, 2, 5, 10, 15, 30, 60, 90, 120, 300, 600,
            900, 1200, 1800, 2700, 3600, 5400, 7200
        ]
    )

    def calculate_notch_interval_t(self, target_interval_x: int) -> Time:
        margin = 1 + self.main.settings.timeline_label_notches_margin / 100
        target_interval_t = self.x_to_t(target_interval_x, Time)
        if target_interval_t >= self.notch_intervals_t[-1] * margin:
            return self.notch_intervals_t[-1]
        for interval in self.notch_intervals_t:
            if target_interval_t < interval * margin:
                return interval
        raise RuntimeError

    notch_intervals_f = list(
        Frame(n) for n in [
            1, 5, 10, 20, 25, 50, 75, 100, 200, 250, 500, 750, 1000,
            2000, 2500, 5000, 7500, 10000, 20000, 25000, 50000, 75000
        ]
    )

    def calculate_notch_interval_f(self, target_interval_x: int) -> Frame:
        margin = 1 + self.main.settings.timeline_label_notches_margin / 100
        target_interval_f = self.x_to_f(target_interval_x, Frame)
        if target_interval_f >= Frame(
                round(int(self.notch_intervals_f[-1]) * margin)):
            return self.notch_intervals_f[-1]
        for interval in self.notch_intervals_f:
            if target_interval_f < Frame(
                    round(int(interval) * margin)):
                return interval
        raise RuntimeError

    def generate_label_format(self, notch_interval_t: Time, end_time: Time | Time) -> str:
        if end_time >= Time(hours=1):
            return '%h:%M:00'
        elif notch_interval_t >= Time(minutes=1):
            return '%m:00'
        else:
            return '%m:%S'

    def set_end_frame(self, node: VideoOutput) -> None:
        self.end_f = node.total_frames
        self.end_t = node.total_time
        self.full_repaint()

    def set_position(self, pos: Frame | Time | int) -> None:
        if self.rect_f.width() == 0.0:
            self.cursor_ftx = pos

        if isinstance(pos, Frame):
            self.cursor_x = self.f_to_x(pos)
        elif isinstance(pos, Time):
            self.cursor_x = self.t_to_x(pos)
        elif isinstance(pos, int):
            self.cursor_x = pos
        else:
            raise TypeError
        self.update()

    def t_to_x(self, t: Time) -> int:
        width = self.rect_f.width()
        try:
            x = round(float(t) / float(self.end_t) * width)
        except ZeroDivisionError:
            x = 0
        return x

    def x_to_t(self, x: int, ty: type[Time]) -> Time:
        width = self.rect_f.width()
        return ty(seconds=(x * float(self.end_t) / width))

    def f_to_x(self, f: Frame) -> int:
        width = self.rect_f.width()
        try:
            x = round(int(f) / int(self.end_f) * width)
        except ZeroDivisionError:
            x = 0
        return x

    def x_to_f(self, x: int, ty: type[Frame]) -> Frame:
        width = self.rect_f.width()
        value = round(x / width * int(self.end_f))
        return ty(value)
