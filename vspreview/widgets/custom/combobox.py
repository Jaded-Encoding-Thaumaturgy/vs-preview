from __future__ import annotations

from typing import cast, Generic, Mapping, Optional, Type, TYPE_CHECKING, TypeVar

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QComboBox

from ...core import VideoOutput, AudioOutput
from ...models import SceningList

T = TypeVar('T', VideoOutput, AudioOutput, SceningList, float)


class ComboBox(QComboBox, Generic[T]):
    def __class_getitem__(cls, content_type: Type[T]) -> Type:
        type_specializations: Mapping[Type, Type] = {
            VideoOutput: _ComboBox_Output,
            AudioOutput: _ComboBox_AudioOutput,
            SceningList: _ComboBox_SceningList,
            float: _ComboBox_float,
        }

        try:
            return type_specializations[content_type]
        except KeyError:
            raise TypeError

    indexChanged = pyqtSignal(int, int)
    content_type: Type[T]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

        self.oldValue = self.currentData()
        self.oldIndex = self.currentIndex()
        self.currentIndexChanged.connect(self._currentIndexChanged)

    def _currentIndexChanged(self, newIndex: int) -> None:
        newValue = self.currentData()
        if newValue is None:
            return
        self.valueChanged.emit(newValue, self.oldValue)
        self.indexChanged.emit(newIndex, self.oldIndex)
        self.oldValue = newValue
        self.oldIndex = newIndex

    def currentValue(self) -> T:
        return cast(T, self.currentData())

    def setCurrentValue(self, newValue: T) -> None:
        i = self.model().index_of(newValue)
        self.setCurrentIndex(i)


class _ComboBox_Output(ComboBox):
    content_type = VideoOutput
    T = VideoOutput
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, Optional[content_type])
    else:
        valueChanged = pyqtSignal(content_type, object)


class _ComboBox_AudioOutput(ComboBox):
    content_type = AudioOutput
    T = AudioOutput
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, Optional[content_type])
    else:
        valueChanged = pyqtSignal(object, object)


class _ComboBox_SceningList(ComboBox):
    content_type = SceningList
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, Optional[content_type])
    else:
        valueChanged = pyqtSignal(content_type, object)


class _ComboBox_float(ComboBox):
    content_type = float
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, Optional[content_type])
    else:
        valueChanged = pyqtSignal(content_type, object)
