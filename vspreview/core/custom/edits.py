from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QTime, pyqtSignal
from PyQt6.QtWidgets import QTimeEdit, QWidget

from ...utils import from_qtime, to_qtime
from ..abstracts import SpinBox
from ..types import Frame, Time

__all__ = [
    'FrameEdit', 'TimeEdit'
]


class FrameEdit(SpinBox):
    valueChanged = pyqtSignal(Frame, Frame)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.setMinimum(Frame(0))

        self.oldValue: Frame = self.value()
        super().valueChanged.connect(self._valueChanged)

    def _valueChanged(self, newValue: int) -> None:
        self.valueChanged.emit(self.value(), self.oldValue)

    def value(self) -> Frame:  # type: ignore[override]
        return Frame(super().value())

    def setValue(self, newValue: Frame) -> None:  # type: ignore[override]
        super().setValue(int(newValue))

    def minimum(self) -> Frame:  # type: ignore[override]
        return Frame(super().minimum())

    def setMinimum(self, newValue: Frame) -> None:  # type: ignore[override]
        super().setMinimum(int(newValue))

    def maximum(self) -> Frame:  # type: ignore[override]
        return Frame(super().maximum())

    def setMaximum(self, newValue: Frame) -> None:  # type: ignore[override]
        super().setMaximum(int(newValue))


class TimeEdit(QTimeEdit):
    valueChanged = pyqtSignal(Time, Time)

    def __init__(self, parent: QWidget | None = None, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs, timeChanged=self._timeChanged)  # type: ignore

        self.setDisplayFormat('H:mm:ss.zzz')
        self.setButtonSymbols(QTimeEdit.ButtonSymbols.NoButtons)
        self.setMinimum(Time())

        self.oldValue: Time = self.value()

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
