from __future__ import annotations

import vapoursynth as vs
from functools import partial
from yaml import YAMLObjectMetaclass
from typing import Any, cast, Iterator, List, Mapping, Type, TypeVar, OrderedDict, TYPE_CHECKING

from vspreview.core import QYAMLObject, Output, AudioOutput

from PyQt5.QtCore import Qt, QModelIndex, QAbstractListModel


T = TypeVar('T', Output, AudioOutput)


class Outputs(QAbstractListModel, QYAMLObject):
    yaml_tag = '!Outputs'

    __slots__ = (
        'items', 'T',
    )

    supported_types = {Output: 'video', AudioOutput: 'audio'}

    def __class_getitem__(self, ty: Type[T]) -> partial[Outputs]:
        return partial(Outputs, ty)

    def __init__(self, ty: Type[T], local_storage: Mapping[str, T] | None = None) -> None:
        from vspreview.utils import main_window

        super().__init__()
        self.T: YAMLObjectMetaclass = ty
        self.items: List[T] = []

        local_storage = local_storage if local_storage is not None else {}

        outputs = OrderedDict(sorted(vs.get_outputs().items()))

        main_window().reload_signal.connect(self.clear_outputs)

        for i, vs_output in outputs.items():
            if not isinstance(vs_output, ty.vs_type):
                continue
            try:
                output = local_storage[str(i)]
                output.__init__(vs_output, i)
            except KeyError:
                output = ty(vs_output, i)

            self.items.append(output)

    def clear_outputs(self) -> None:
        for o in self.items:
            o.clear()

    def __getitem__(self, i: int) -> T:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def index_of(self, item: T) -> int:
        return self.items.index(item)

    def __getiter__(self) -> Iterator[T]:
        return iter(self.items)

    def append(self, item: T) -> int:
        index = len(self.items)
        self.beginInsertRows(QModelIndex(), index, index)
        self.items.append(item)
        self.endInsertRows()

        return len(self.items) - 1

    def clear(self) -> None:
        self.beginRemoveRows(QModelIndex(), 0, len(self.items))
        self.items.clear()
        self.endRemoveRows()

    def data(self, index: QModelIndex, role: int = Qt.UserRole) -> Any:
        if not index.isValid():
            return None
        if index.row() >= len(self.items):
            return None

        if role == Qt.DisplayRole:
            return self.items[index.row()].name
        if role == Qt.EditRole:
            return self.items[index.row()].name
        if role == Qt.UserRole:
            return self.items[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return cast(Qt.ItemFlags, Qt.ItemIsEnabled)

        return cast(Qt.ItemFlags, super().flags(index) | Qt.ItemIsEditable)  # type: ignore

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        if not role == Qt.EditRole:
            return False
        if not isinstance(value, str):
            return False

        self.items[index.row()].name = value
        self.dataChanged.emit(index, index, [role])
        return True

    def __getstate__(self) -> Mapping[str, Any]:
        return dict(zip([
            str(output.index) for output in self.items],
            [output for output in self.items]
        ), type=self.supported_types[self.T])

    def __setstate__(self, state: Mapping[str, Output | str]) -> None:
        try:
            type_string = state['type']
            if not isinstance(type_string, str):
                raise TypeError(
                    'Storage loading: Outputs: value of key "type" is not a string')

        except KeyError:
            raise KeyError('Storage loading: Outputs: key "type" is missing') from KeyError

        ty = dict(zip(self.supported_types.values(), self.supported_types.keys()))[type_string]

        for key, value in state.items():
            if key == 'type':
                continue
            if not isinstance(key, str):
                raise TypeError(f'Storage loading: Outputs: key {key} is not a string')
            if not isinstance(value, ty):
                raise TypeError(f'Storage loading: Outputs: value of key {key} is not an Output')

        self.__init__(ty, state)  # type: ignore

    if TYPE_CHECKING:
        # https://github.com/python/mypy/issues/2220
        def __iter__(self) -> Iterator[T]: ...
