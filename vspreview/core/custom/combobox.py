from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QWidget

from ...core import AudioOutput, PictureType, VideoOutput
from ...models import SceningList

ComboBoxT = TypeVar('ComboBoxT', VideoOutput, AudioOutput, SceningList, PictureType, float, str)


class ComboBox(QComboBox, Generic[ComboBoxT]):
    def __class_getitem__(cls, content_type: type[ComboBoxT]) -> type:
        return {
            VideoOutput: _ComboBox_Output,
            AudioOutput: _ComboBox_AudioOutput,
            SceningList: _ComboBox_SceningList,
            PictureType: _ComboBox_PictureType,
            float: _ComboBox_float,
            int: _ComboBox_int,
            str: _ComboBox_string
        }[content_type]

    indexChanged = pyqtSignal(int, int)
    content_type: type[ComboBoxT]

    def __init__(self, parent: QWidget | None = None, **kwargs: Any) -> None:
        super().__init__(parent)

        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

        self.oldValue = self.currentData()
        self.oldIndex = self.currentIndex()
        self.currentIndexChanged.connect(self._currentIndexChanged)

        for arg in kwargs:
            getattr(self, 'set' + arg[0].upper() + arg[1:])(kwargs.get(arg))

    def _currentIndexChanged(self, newIndex: int) -> None:
        newValue = self.currentData()
        if newValue is None:
            return
        self.valueChanged.emit(newValue, self.oldValue)
        self.indexChanged.emit(newIndex, self.oldIndex)
        self.oldValue = newValue
        self.oldIndex = newIndex

    def currentValue(self) -> ComboBoxT:
        return cast(ComboBoxT, self.currentData())

    def setCurrentValue(self, newValue: ComboBoxT) -> None:
        i = self.model().index_of(newValue)
        self.setCurrentIndex(i)


class _ComboBox_Output(ComboBox):
    content_type = VideoOutput
    T = VideoOutput
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, content_type | None)
    else:
        valueChanged = pyqtSignal(content_type, object)


class _ComboBox_AudioOutput(ComboBox):
    content_type = AudioOutput
    T = AudioOutput
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, content_type | None)
    else:
        valueChanged = pyqtSignal(object, object)


class _ComboBox_SceningList(ComboBox):
    content_type = SceningList
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, content_type | None)
    else:
        valueChanged = pyqtSignal(content_type, object)


class _ComboBox_PictureType(ComboBox):
    content_type = PictureType
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, content_type | None)
    else:
        valueChanged = pyqtSignal(content_type, object)


class _ComboBox_float(ComboBox):
    content_type = float
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, content_type | None)
    else:
        valueChanged = pyqtSignal(content_type, object)


class _ComboBox_int(ComboBox):
    content_type = int
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, content_type | None)
    else:
        valueChanged = pyqtSignal(content_type, object)


class _ComboBox_string(ComboBox):
    content_type = str
    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, content_type | None)
    else:
        valueChanged = pyqtSignal(content_type, object)
