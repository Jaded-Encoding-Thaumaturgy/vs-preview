from __future__ import annotations

from typing import Any, Iterator, Sequence
from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex


class ZoomLevels(QAbstractListModel):
    __slots__ = (
        'levels',
    )

    def __init__(self, init_seq: Sequence[float]) -> None:
        super().__init__()
        self.levels = list(init_seq)

    def __getitem__(self, i: int) -> float:
        return self.levels[i]

    def __len__(self) -> int:
        return len(self.levels)

    def __getiter__(self) -> Iterator[float]:
        return iter(self.levels)

    def index_of(self, item: float) -> int:
        return self.levels.index(item)

    def data(self, index: QModelIndex, role: int = Qt.UserRole) -> Any:
        if (not index.isValid() or index.row() >= len(self.levels)):
            return None

        if role == Qt.DisplayRole:
            return '{}%'.format(round(self.levels[index.row()] * 100))
        if role == Qt.UserRole:
            return self.levels[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.levels)
