from __future__ import annotations

import logging
from typing import Any, cast, Iterator, List, Mapping, Optional, OrderedDict

from PyQt5 import Qt
import vapoursynth as vs

from vspreview.core import Output, QYAMLObjectSingleton
from vspreview.utils import debug


# TODO: support non-YUV outputs


class Outputs(Qt.QAbstractListModel, QYAMLObjectSingleton):
    yaml_tag = '!Outputs'

    __slots__ = (
        'items',
    )

    def __init__(self, main_window, local_storage: Optional[Mapping[str, Output]] = None) -> None:
        from vspreview.main import MainWindow
        super().__init__()
        self.items: List[Output] = []

        main_window = main_window or MainWindow()

        local_storage = local_storage if local_storage is not None else {}

        if main_window.ORDERED_OUTPUTS:
            outputs = OrderedDict(sorted(vs.get_outputs().items()))
        else:
            outputs = vs.get_outputs()

        main_window.reload_signal.connect(self.clear_outputs)

        for i, vs_output in outputs.items():
            try:
                output = local_storage[str(i)]
                output.__init__(vs_output, i)  # type: ignore
            except KeyError:
                output = Output(vs_output, i)

            self.items.append(output)

    def clear_outputs(self):
        for o in self.items:
            o.clear()

    def __getitem__(self, i: int) -> Output:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def index_of(self, item: Output) -> int:
        return self.items.index(item)

    def __getiter__(self) -> Iterator[Output]:
        return iter(self.items)

    def append(self, item: Output) -> int:
        index = len(self.items)
        self.beginInsertRows(Qt.QModelIndex(), index, index)
        self.items.append(item)
        self.endInsertRows()

        return len(self.items) - 1

    def clear(self) -> None:
        self.beginRemoveRows(Qt.QModelIndex(), 0, len(self.items))
        self.items.clear()
        self.endRemoveRows()

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.UserRole) -> Any:
        if not index.isValid():
            return None
        if index.row() >= len(self.items):
            return None

        if role == Qt.Qt.DisplayRole:
            return self.items[index.row()].name
        if role == Qt.Qt.EditRole:
            return self.items[index.row()].name
        if role == Qt.Qt.UserRole:
            return self.items[index.row()]
        return None

    def rowCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()) -> int:
        if self.items is not None:
            return len(self.items)
        else:
            return 0

    def flags(self, index: Qt.QModelIndex) -> Qt.Qt.ItemFlags:
        if not index.isValid():
            return cast(Qt.Qt.ItemFlags, Qt.Qt.ItemIsEnabled)

        return cast(Qt.Qt.ItemFlags, super().flags(index) | Qt.Qt.ItemIsEditable)

    def setData(self, index: Qt.QModelIndex, value: Any, role: int = Qt.Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        if not role == Qt.Qt.EditRole:
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
        ))

    def __setstate__(self, state: Mapping[str, Output]) -> None:
        for key, value in state.items():
            if not isinstance(key, str):
                raise TypeError(f'Storage loading: Outputs: key {key} is not a string')
            if not isinstance(value, Output):
                raise TypeError(f'Storage loading: Outputs: value of key {key} is not an Output')

        self.__init__(state)  # type: ignore
