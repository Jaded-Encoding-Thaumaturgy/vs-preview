from __future__ import annotations

from PyQt5.QtCore import pyqtSignal, QTime
from PyQt5.QtWidgets import QWidget, QSpinBox, QTimeEdit

from ...core import Frame, Time
from ...utils import from_qtime, to_qtime


class FrameEdit(QSpinBox):
    valueChanged = pyqtSignal(Frame, Frame)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setMinimum(Frame(0))

        self.oldValue: Frame = self.value()
        super().valueChanged.connect(self._valueChanged)

    def _valueChanged(self, newValue: int) -> None:
        self.valueChanged.emit(self.value(), self.oldValue)

    def value(self) -> Frame:
        return Frame(super().value())

    def setValue(self, newValue: Frame) -> None:
        super().setValue(int(newValue))

    def minimum(self) -> Frame:
        return Frame(super().minimum())

    def setMinimum(self, newValue: Frame) -> None:
        super().setMinimum(int(newValue))

    def maximum(self) -> Frame:
        return Frame(super().maximum())

    def setMaximum(self, newValue: Frame) -> None:
        super().setMaximum(int(newValue))


class TimeEdit(QTimeEdit):
    valueChanged = pyqtSignal(Time, Time)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setDisplayFormat('H:mm:ss.zzz')
        self.setButtonSymbols(QTimeEdit.NoButtons)
        self.setMinimum(Time())

        self.oldValue: Time = self.value()
        self.timeChanged.connect(self._timeChanged)

    def _timeChanged(self, newValue: QTime) -> None:
        self.valueChanged.emit(self.value(), self.oldValue)
        self.oldValue = self.value()

    def value(self) -> Time:
        return from_qtime(super().time(), Time)

    def setValue(self, newValue: Time) -> None:
        super().setTime(to_qtime(newValue))

    def minimum(self) -> Time:
        return from_qtime(super().minimumTime(), Time)

    def setMinimum(self, newValue: Time) -> None:
        super().setMinimumTime(to_qtime(newValue))

    def maximum(self) -> Time:
        return from_qtime(super().maximumTime(), Time)

    def setMaximum(self, newValue: Time) -> None:
        super().setMaximumTime(to_qtime(newValue))
