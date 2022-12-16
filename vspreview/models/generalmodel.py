from __future__ import annotations

from typing import Any, Iterator, Sequence, TypeVar

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

T = TypeVar('T', float, str)


class GeneralModel(QAbstractListModel):
    __slots__ = ('items',)

    def __class_getitem__(cls, content_type: type[T]) -> type:
        return {
            float: _GeneralModel_float,
            int: _GeneralModel_int,
            str: _GeneralModel_string,
        }[content_type]

    content_type: type[T]
    to_title: bool

    def __init__(self, init_seq: Sequence[content_type], to_title: bool = True) -> None:
        super().__init__()
        self.items = list(init_seq)
        self.to_title = to_title

    def __getitem__(self, i: int) -> content_type:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[content_type]:
        return iter(self.items)

    def index_of(self, item: content_type) -> int:
        return self.items.index(item)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.UserRole) -> Any:
        if (not index.isValid() or index.row() >= len(self.items)):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            value = self.items[index.row()]
            if self.content_type is str:
                return self._displayValue(value, self.to_title)
            else:
                return self._displayValue(value)
        if role == Qt.ItemDataRole.UserRole:
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

    def _displayValue(self, value: content_type, to_tile: bool) -> str:
        return value.title() if to_tile else value
