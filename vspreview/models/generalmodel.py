from __future__ import annotations

from typing import Any, Generic, Iterator, Sequence, TypeVar

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

T = TypeVar('T')


__all__ = [
    'GeneralModel'
]


class GeneralModel(QAbstractListModel, Generic[T]):
    __slots__ = ('items',)

    def __class_getitem__(cls, _content_type: type[T]) -> type[GeneralModel[T]]:

        if _content_type is float:
            return _GeneralModel_float
        elif _content_type is int:
            return _GeneralModel_int
        elif _content_type is str:
            return _GeneralModel_string

        class _GenericModel_inner(GeneralModel):  # type: ignore
            content_type = _content_type

        return _GenericModel_inner

    content_type: type[T]
    to_title: bool

    def __init__(self, init_seq: Sequence[T], to_title: bool = True) -> None:
        super().__init__()
        self.items = list(init_seq)
        self.to_title = to_title

    def __getitem__(self, i: int) -> T:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def index_of(self, item: T) -> int:
        return self.items.index(item)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.UserRole) -> Any:
        if (not index.isValid() or index.row() >= len(self.items)):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            value = self.items[index.row()]

            str_value = self._displayValue(value)

            if self.content_type is str and self.to_title:
                return str_value.title()

            return str_value

        if role == Qt.ItemDataRole.UserRole:
            return self.items[index.row()]

        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    def _displayValue(self, value: T) -> str:
        raise NotImplementedError


class _GeneralModel_float(GeneralModel):  # type: ignore
    content_type = float

    def _displayValue(self, value: float) -> str:
        return str(round(value * 100)) + '%'


class _GeneralModel_int(GeneralModel):  # type: ignore
    content_type = int

    def _displayValue(self, value: int) -> str:
        return str(value)


class _GeneralModel_string(GeneralModel):  # type: ignore
    content_type = str

    def _displayValue(self, value: str) -> str:
        return value
