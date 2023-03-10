
from __future__ import annotations

from typing import Iterator, cast

from PyQt6.QtCore import QLineF, Qt
from PyQt6.QtGui import QColor

from ..types import Frame, Scene, Time

__all__ = [
    'Notch',
    'Notches'
]


class Notch:
    def __init__(
        self, data: Frame | Time, color: QColor = cast(QColor, Qt.GlobalColor.white),
        label: str = '', line: QLineF = QLineF()
    ) -> None:
        self.data = data
        self.color = color
        self.label = label
        self.line = line

    def __repr__(self) -> str:
        return '{}({}, {}, {}, {})'.format(
            type(self).__name__, repr(self.data), repr(self.color),
            repr(self.label), repr(self.line))


class Notches:
    def __init__(self, other: Notches | None = None) -> None:
        self.items = list[Notch]()

        if other is None:
            return
        self.items = other.items

    def add(
        self, data: Frame | Scene | Time | Notch,
        color: QColor = cast(QColor, Qt.GlobalColor.white),
        label: str = ''
    ) -> None:
        if isinstance(data, Notch):
            self.items.append(data)
        elif isinstance(data, Scene):
            if label == '':
                label = data.label
            self.items.append(Notch(data.start, color, label))
            if data.end != data.start:
                self.items.append(Notch(data.end, color, label))
        elif isinstance(data, (Frame, Time)):
            self.items.append(Notch(data, color, label))
        else:
            raise TypeError

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Notch:
        return self.items[index]

    def __iter__(self) -> Iterator[Notch]:
        return iter(self.items)

    def __repr__(self) -> str:
        return '{}({})'.format(type(self).__name__, repr(self.items))
