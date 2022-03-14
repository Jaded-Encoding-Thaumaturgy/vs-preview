from __future__ import annotations

from typing import cast, Dict, Generic, Optional, Type

from PyQt5 import Qt

from vspreview.core import (
    Frame, FrameInterval, FrameType, Time, TimeInterval, TimeType,
)
from vspreview.utils import from_qtime, to_qtime


# TODO: replace specialized Edit classes with some metaclasses magic or such


class FrameEdit(Qt.QSpinBox, Generic[FrameType]):
    def __class_getitem__(cls, ty: Type[FrameType]) -> Type:
        type_specializations: Dict[Type, Type] = {
            Frame: _FrameEdit_Frame,
            FrameInterval: _FrameEdit_FrameInterval,
        }

        try:
            return type_specializations[ty]
        except KeyError:
            raise TypeError

    def __init__(self, parent: Optional[Qt.QWidget] = None) -> None:
        super().__init__(parent)

        self.ty: Type[FrameType]

        self.setMinimum(self.ty(0))

        self.oldValue: FrameType = self.value()
        super().valueChanged.connect(self._valueChanged)  # type: ignore

    def _valueChanged(self, newValue: int) -> None:
        self.valueChanged.emit(self.value(), self.oldValue)

    def value(self) -> FrameType:  # type: ignore
        return self.ty(super().value())

    def setValue(self, newValue: FrameType) -> None:  # type: ignore
        super().setValue(int(newValue))

    def minimum(self) -> FrameType:  # type: ignore
        return self.ty(super().minimum())

    def setMinimum(self, newValue: FrameType) -> None:  # type: ignore
        super().setMinimum(int(newValue))

    def maximum(self) -> FrameType:  # type: ignore
        return self.ty(super().maximum())

    def setMaximum(self, newValue: FrameType) -> None:  # type: ignore
        super().setMaximum(int(newValue))


class _FrameEdit_Frame(FrameEdit):
    ty = Frame
    valueChanged = Qt.pyqtSignal(ty, ty)  # type: ignore


class _FrameEdit_FrameInterval(FrameEdit):
    ty = FrameInterval
    valueChanged = Qt.pyqtSignal(ty, ty)  # type: ignore


class TimeEdit(Qt.QTimeEdit, Generic[TimeType]):
    def __class_getitem__(cls, ty: Type[TimeType]) -> Type:
        type_specializations: Dict[Type, Type] = {
            Time: _TimeEdit_Time,
            TimeInterval: _TimeEdit_TimeInterval,
        }

        try:
            return type_specializations[ty]
        except KeyError:
            raise TypeError

    def __init__(self, parent: Optional[Qt.QWidget] = None) -> None:
        super().__init__(parent)

        self.ty: Type[TimeType]

        self.setDisplayFormat('H:mm:ss.zzz')
        self.setButtonSymbols(Qt.QTimeEdit.NoButtons)
        self.setMinimum(self.ty())

        self.oldValue: TimeType = self.value()
        cast(Qt.pyqtSignal, self.timeChanged).connect(self._timeChanged)  # type: ignore

    def _timeChanged(self, newValue: Qt.QTime) -> None:
        self.valueChanged.emit(self.value(), self.oldValue)
        self.oldValue = self.value()

    def value(self) -> TimeType:
        return from_qtime(super().time(), self.ty)

    def setValue(self, newValue: TimeType) -> None:
        super().setTime(to_qtime(newValue))

    def minimum(self) -> TimeType:
        return from_qtime(super().minimumTime(), self.ty)

    def setMinimum(self, newValue: TimeType) -> None:
        super().setMinimumTime(to_qtime(newValue))

    def maximum(self) -> TimeType:
        return from_qtime(super().maximumTime(), self.ty)

    def setMaximum(self, newValue: TimeType) -> None:
        super().setMaximumTime(to_qtime(newValue))


class _TimeEdit_Time(TimeEdit):
    ty = Time
    valueChanged = Qt.pyqtSignal(ty, ty)


class _TimeEdit_TimeInterval(TimeEdit):
    ty = TimeInterval
    valueChanged = Qt.pyqtSignal(ty, ty)
