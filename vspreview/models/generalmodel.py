from __future__ import annotations

from typing import Any, Iterator, Sequence, TypeVar, Type
from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex


T = TypeVar('T', float, str)


class GeneralModel(QAbstractListModel):
    __slots__ = ('items',)

    def __class_getitem__(cls, content_type: Type[T]) -> Type:
        return {
            float: _GeneralModel_float,
            int: _GeneralModel_int,
            str: _GeneralModel_string,
        }[content_type]

    content_type: Type[T]

    def __init__(self, init_seq: Sequence[content_type]) -> None:
        super().__init__()
        self.items = list(init_seq)

    def __getitem__(self, i: int) -> content_type:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[content_type]:
        return iter(self.items)

    def index_of(self, item: content_type) -> int:
        return self.items.index(item)

    def data(self, index: QModelIndex, role: int = Qt.UserRole) -> Any:
        if (not index.isValid() or index.row() >= len(self.items)):
            return None

        if role == Qt.DisplayRole:
            return self._displayValue(self.items[index.row()])
        if role == Qt.UserRole:
            return self.items[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    def _displayValue(self, value: content_type) -> str:
        raise NotImplementedError


class _GeneralModel_float(GeneralModel):
    content_type = float

    def _displayValue(self, value: content_type) -> str:
        return str(round(value * 100)) + '%'


class _GeneralModel_int(GeneralModel):
    content_type = int

    def _displayValue(self, value: content_type) -> str:
        return str(value)


class _GeneralModel_string(GeneralModel):
    content_type = str

    def _displayValue(self, value: content_type) -> str:
        return value.title()
