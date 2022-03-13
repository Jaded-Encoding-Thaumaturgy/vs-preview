from __future__ import annotations

from PyQt5 import Qt
import vapoursynth as vs
from typing import Any, cast, Iterator, List, Mapping, Optional, OrderedDict


from vspreview.core import Output, QYAMLObjectSingleton


# TODO: support non-YUV outputs


class Outputs(Qt.QAbstractListModel, QYAMLObjectSingleton):
    yaml_tag = '!Outputs'

    __slots__ = ('items',)

    def __init__(self, local_storage: Optional[Mapping[str, Output]] = None) -> None:
        from vspreview.utils import main_window
        super().__init__()
        self.items: List[Output] = []

        local_storage = local_storage if local_storage is not None else {}

        outputs = OrderedDict(sorted(vs.get_outputs().items()))

        main_window().reload_signal.connect(self.clear_outputs)

        for i, vs_output in outputs.items():
            try:
                output = local_storage[str(i)]
                output.__init__(vs_output, i)  # type: ignore
            except KeyError:
                output = Output(vs_output, i)  # type: ignore

            self.items.append(output)

    def clear_outputs(self) -> None:
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
        return len(self.items)

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
        self.dataChanged.emit(index, index, [role])  # type: ignore
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
