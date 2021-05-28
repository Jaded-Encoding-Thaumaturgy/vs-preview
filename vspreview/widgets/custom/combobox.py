from __future__ import annotations

import logging
from typing import cast, Dict, Generic, Optional, Type, TYPE_CHECKING, TypeVar

from PyQt5 import Qt

from vspreview.core import Output
from vspreview.models import SceningList

T = TypeVar('T', Output, SceningList, float)


class ComboBox(Qt.QComboBox, Generic[T]):
    def __class_getitem__(cls, ty: Type[T]) -> Type:
        type_specializations: Dict[Type, Type] = {
            Output     : _ComboBox_Output,
            SceningList: _ComboBox_SceningList,
            float      : _ComboBox_float,
        }

        try:
            return type_specializations[ty]
        except KeyError:
            raise TypeError

    indexChanged = Qt.pyqtSignal(int, int)

    def __init__(self, parent: Optional[Qt.QWidget] = None) -> None:
        super().__init__(parent)

        self.ty: Type[T]

        self.setSizeAdjustPolicy(
            Qt.QComboBox.AdjustToMinimumContentsLengthWithIcon)

        self.oldValue = self.currentData()
        self.oldIndex = self.currentIndex()
        self.currentIndexChanged.connect(self._currentIndexChanged)

    def _currentIndexChanged(self, newIndex: int) -> None:
        newValue = self.currentData()
        self.valueChanged.emit(newValue, self.oldValue)
        self.indexChanged.emit(newIndex, self.oldIndex)
        self.oldValue = newValue
        self.oldIndex = newIndex

    def currentValue(self) -> Optional[T]:
        return cast(Optional[T], self.currentData())

    def setCurrentValue(self, newValue: T) -> None:
        i = self.model().index_of(newValue)
        self.setCurrentIndex(i)


class _ComboBox_Output(ComboBox):
    ty = Output
    if TYPE_CHECKING:
        valueChanged = Qt.pyqtSignal(Optional[ty], Optional[ty])
    else:
        valueChanged = Qt.pyqtSignal(object, object)


class _ComboBox_SceningList(ComboBox):
    ty = SceningList
    if TYPE_CHECKING:
        valueChanged = Qt.pyqtSignal(ty, Optional[ty])
    else:
        valueChanged = Qt.pyqtSignal(ty, object)


class _ComboBox_float(ComboBox):
    ty = float
    if TYPE_CHECKING:
        valueChanged = Qt.pyqtSignal(ty, Optional[ty])
    else:
        valueChanged = Qt.pyqtSignal(ty, object)
