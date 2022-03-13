from __future__ import annotations

import logging
from   typing  import Any, Iterator, Sequence

from PyQt5 import Qt

from vspreview.utils import debug


class ZoomLevels(Qt.QAbstractListModel):
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

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.UserRole) -> Any:
        if (not index.isValid()
                or index.row() >= len(self.levels)):
            return None

        if role == Qt.Qt.DisplayRole:
            return '{}%'.format(round(self.levels[index.row()] * 100))
        if role == Qt.Qt.UserRole:
            return self.levels[index.row()]
        return None

    def rowCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()) -> int:
        if self.levels is not None:
            return len(self.levels)
        return 0
