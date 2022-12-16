from __future__ import annotations

from typing import Any, Generic, Iterator, Mapping, OrderedDict, TypeVar, cast

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt
from vstools import vs

from ..core import AbstractMainWindow, AudioOutput, QYAMLObject, VideoOutput, VideoOutputNode, main_window, try_load

T = TypeVar('T', VideoOutput, AudioOutput)


class Outputs(Generic[T], QAbstractListModel, QYAMLObject):
    out_type: type[T]
    _items: list[T]

    __slots__ = ('items')

    def __init__(self, main: AbstractMainWindow, local_storage: Mapping[str, T] | None = None) -> None:
        self.setValue(main, local_storage)

    def setValue(self, main: AbstractMainWindow, local_storage: Mapping[str, T] | None = None) -> None:
        super().__init__()
        self.items = list[T]()
        self.main = main

        local_storage, newstorage = (local_storage, False) if local_storage is not None else ({}, True)

        if main.storage_not_found:
            newstorage = False

        outputs = OrderedDict(sorted(vs.get_outputs().items()))

        main.reload_signal.connect(self.clear_outputs)

        for i, vs_output in outputs.items():
            if not isinstance(vs_output, self.vs_type):
                continue
            try:
                output = local_storage[str(i)]
                output.setValue(vs_output, i, newstorage)
            except KeyError:
                output = self.out_type(vs_output, i, newstorage)

            self.items.append(output)

        self._items = list(self.items)

    def clear_outputs(self) -> None:
        for o in self.items:
            o.clear()

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

    def __getstate__(self) -> Mapping[str, Any]:
        return dict(zip([str(x.index) for x in self.items], self.items), type=self.out_type.__name__)

    def __setstate__(self, state: Mapping[str, T]) -> None:
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

    _fft_spectr_items = list[VideoOutput]()

    def copy_output_props(self, new: VideoOutput, old: VideoOutput) -> None:
        new.last_showed_frame = old.last_showed_frame
        new.name = old.name

    def get_new_output(self, new_clip: vs.VideoNode, old_output: VideoOutput) -> VideoOutput:
        new_videonode = VideoOutputNode(new_clip, old_output.source.alpha)

        new_output = VideoOutput(new_videonode, old_output.index, False)

        self.copy_output_props(new_output, old_output)

        return new_output

    def switchToNormalView(self) -> None:
        for new, old in zip(self._items, self.items):
            self.copy_output_props(new, old)

        self.items = list(self._items)

    def switchToFFTSpectrumView(self, force_cache: bool = False) -> None:
        try:
            from vsdfft import FFTSpectrum
        except ModuleNotFoundError:
            raise RuntimeError(
                'vspreview: You can\'t chage to this view mode. You\'re missing the `vsdfft` package!'
            )

        if not self._fft_spectr_items or force_cache:
            max_width = max(*(x.width for x in self._items), 140)
            max_height = max(*(x.height for x in self._items), 140)

            self._fft_spectr_items = [
                self.get_new_output(
                    FFTSpectrum(old.source.clip, target_size=(max_width, max_height)), old
                ) for old in self._items
            ]
        else:
            for new, old in zip(self._fft_spectr_items, self.items):
                self.copy_output_props(new, old)

        self.items = self._fft_spectr_items


class AudioOutputs(Outputs[AudioOutput]):
    out_type = AudioOutput
    vs_type = vs.AudioNode
