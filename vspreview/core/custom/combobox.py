from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QWidget

from ...core import AudioOutput, PictureType, VideoOutput
from ...models import SceningList

ComboBoxT = TypeVar(
    'ComboBoxT', type[VideoOutput], type[AudioOutput], type[SceningList], type[PictureType], type[float], type[str]
)


class ComboBox(QComboBox, Generic[ComboBoxT]):
    def __class_getitem__(cls, _content_type: ComboBoxT) -> ComboBox[ComboBoxT]:
        class _ComboBox_inner(ComboBox):  # type: ignore
            content_type = _content_type

            valueChanged = pyqtSignal(content_type, object)

        return _ComboBox_inner  # type: ignore

    indexChanged = pyqtSignal(int, int)
    content_type: type[ComboBoxT]

    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, ComboBoxT | None)  # type: ignore

    def __init__(self, parent: QWidget | None = None, **kwargs: Any) -> None:
        super().__init__(parent)

        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

        self.oldValue = self.currentData()
        self.oldIndex = self.currentIndex()
        self.currentIndexChanged.connect(self._currentIndexChanged)

        for arg in kwargs:
            getattr(self, 'set' + arg[0].upper() + arg[1:])(kwargs.get(arg))

    def _currentIndexChanged(self, newIndex: int) -> None:
        if (newValue := self.currentData()) is None:
            return

        self.valueChanged.emit(newValue, self.oldValue)
        self.indexChanged.emit(newIndex, self.oldIndex)
        self.oldValue = newValue
        self.oldIndex = newIndex

    def currentValue(self) -> ComboBoxT:
        return cast(ComboBoxT, self.currentData())

    def setCurrentValue(self, newValue: ComboBoxT) -> None:
        self.setCurrentIndex(self.model().index_of(newValue))  # type: ignore
