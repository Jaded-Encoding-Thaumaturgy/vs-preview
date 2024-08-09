from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Iterator, OrderedDict, TypeVar

import vapoursynth as vs
from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

from ..core import AudioOutput, QYAMLObject, VideoOutput, main_window, try_load

if TYPE_CHECKING:
    from ..main import MainWindow

T = TypeVar('T', VideoOutput, AudioOutput)


__all__ = [
    'Outputs',
    'VideoOutputs',
    'AudioOutputs'
]


class Outputs(Generic[T], QAbstractListModel, QYAMLObject):
    __slots__ = ('items', )

    out_type: type[T]
    vs_type: type[vs.VideoOutputTuple] | type[vs.AudioNode]

    items: list[T]
    _items: list[T]

    main: MainWindow

    def __init__(self, main: MainWindow, local_storage: dict[str, T] | None = None) -> None:
        self.setValue(main, local_storage)

    def setValue(self, main: MainWindow, local_storage: dict[str, T] | None = None) -> None:
        super().__init__()

        self.items = []
        self.main = main

        local_storage, newstorage = (local_storage, False) if local_storage is not None else ({}, True)

        if main.storage_not_found:
            newstorage = False

        outputs = OrderedDict(sorted(vs.get_outputs().items()))

        for i, vs_output in outputs.items():
            if not isinstance(vs_output, self.vs_type):
                continue

            try:
                output = local_storage[str(i)]
                output.setValue(vs_output, i, newstorage)  # type: ignore
            except KeyError:
                output = self.out_type(vs_output, i, newstorage)  # type: ignore

            self.items.append(output)

        self._items = list(self.items)

    def clear_outputs(self) -> None:
        for output in (*self.items, *self._items):
            output.clear()

    def __getitem__(self, i: int) -> T:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def index_of(self, item: T) -> int:
        return self.items.index(item)

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def append(self, item: T) -> int:
        index = len(self.items)
        self.beginInsertRows(QModelIndex(), index, index)
        self.items.append(item)
        self.endInsertRows()

        return len(self.items) - 1

    def clear(self) -> None:
        self.clear_outputs()
        self.beginRemoveRows(QModelIndex(), 0, len(self.items))
        self.items.clear()
        self._items.clear()
        self.endRemoveRows()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.UserRole) -> Any:
        if not index.isValid():
            return None
        if index.row() >= len(self.items):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self.items[index.row()].name
        if role == Qt.ItemDataRole.EditRole:
            return self.items[index.row()].name
        if role == Qt.ItemDataRole.UserRole:
            return self.items[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled

        return super().flags(index) | Qt.ItemFlag.ItemIsEditable

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        if not role == Qt.ItemDataRole.EditRole:
            return False
        if not isinstance(value, str):
            return False

        self.items[index.row()].name = value
        self.dataChanged.emit(index, index, [role])

        return True

    def __getstate__(self) -> dict[str, Any]:
        return dict(zip([str(x.index) for x in self.items], self.items), type=self.out_type.__name__)

    def __setstate__(self, state: dict[str, T]) -> None:
        type_string = ''
        try_load(state, 'type', str, type_string)

        for key, value in state.items():
            if key == 'type':
                continue
            if not isinstance(key, str):
                raise TypeError(f'Storage loading (Outputs): key {key} is not a string')
            if not isinstance(value, self.out_type):
                raise TypeError(f'Storage loading (Outputs): value of key {key} is not {self.out_type.__name__}')

        self.setValue(main_window(), state)


class VideoOutputs(Outputs[VideoOutput]):
    out_type = VideoOutput
    vs_type = vs.VideoOutputTuple


class AudioOutputs(Outputs[AudioOutput]):
    out_type = AudioOutput
    vs_type = vs.AudioNode  # type: ignore
