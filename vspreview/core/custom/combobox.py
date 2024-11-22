from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QWidget

T = TypeVar('T')


__all__ = [
    'ComboBox'
]


class ComboBox(QComboBox, Generic[T]):
    def __class_getitem__(cls, _content_type: type[T]) -> type[ComboBox[T]]:
        class _ComboBox_inner(ComboBox):  # type: ignore
            content_type = _content_type

            valueChanged = pyqtSignal(content_type, object)

        return _ComboBox_inner

    indexChanged = pyqtSignal(int, int)
    content_type: type[T]

    if TYPE_CHECKING:
        valueChanged = pyqtSignal(content_type, T | None)  # noqa

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

    def currentValue(self) -> T:
        return cast(T, self.currentData())

    def setCurrentValue(self, newValue: T) -> None:
        self.setCurrentIndex(self.model().index_of(newValue))  # type: ignore
