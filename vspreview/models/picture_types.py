from __future__ import annotations

from typing import Any, Iterator, cast

from PyQt5.QtCore import QAbstractListModel, QModelIndex, Qt

from ..core import PictureType


class PictureTypes(QAbstractListModel):
    __slots__ = ('items',)

    def __init__(self) -> None:
        super().__init__()
        self.items = PictureType.list()

    def __getitem__(self, i: int) -> PictureType:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[PictureType]:
        return iter(self.items)

    def index_of(self, item: PictureType) -> int:
        return self.items.index(item)

    def data(self, index: QModelIndex, role: int = Qt.UserRole) -> Any:
        if (not index.isValid() or index.row() >= len(self.items)):
            return None

        if role == Qt.DisplayRole or role == Qt.EditRole:
            return str(self.items[index.row()])
        if role == Qt.UserRole:
            return self.items[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return cast(Qt.ItemFlags, Qt.ItemIsEnabled)

        return super().flags(index) | Qt.ItemIsEditable
