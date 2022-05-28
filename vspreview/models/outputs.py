from __future__ import annotations

import itertools
import multiprocessing
from functools import partial
from math import floor
from typing import Any, Callable, Dict, Generic, Iterator, List, Mapping, OrderedDict, Tuple, Type, TypeVar, cast

import numpy as np
import vapoursynth as vs
from pyfftw import FFTW, empty_aligned  # type: ignore
from PyQt5.QtCore import QAbstractListModel, QModelIndex, Qt

from ..core import AbstractMainWindow, AudioOutput, QYAMLObject, VideoOutput, VideoOutputNode, main_window, try_load

T = TypeVar('T', VideoOutput, AudioOutput)
nthread = multiprocessing.cpu_count()


class Outputs(Generic[T], QAbstractListModel, QYAMLObject):
    out_type: Type[T]
    _items: List[T]

    __slots__ = ('items')

    def __init__(self, main: AbstractMainWindow, local_storage: Mapping[str, T] | None = None) -> None:
        self.setValue(main, local_storage)

    def setValue(self, main: AbstractMainWindow, local_storage: Mapping[str, T] | None = None) -> None:
        super().__init__()
        self.items: List[T] = []

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

        return super().flags(index) | Qt.ItemIsEditable  # type: ignore

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


def _fftspectrum_vmode_modifyframe(
    f: List[vs.VideoFrame], n: int, fftw_args: Dict[str, Any],
    fastroll_copy: Callable[[np.typing.NDArray, np.typing.NDArray], None]
) -> vs.VideoFrame:
    fdst = f[1].copy()

    farr = np.asarray(f[0][0]).astype(np.complex64)

    fftexec = FFTW(farr, **fftw_args)

    fastroll_copy(fftexec().real, np.asarray(fdst[0]))

    return fdst


def _fftspectrum_vmode_fastroll_copy(
    fft: np.typing.NDArray, fdst: np.typing.NDArray, rolls_indices: List[Tuple[slice, slice]]
) -> None:
    for arr_index, res_index in rolls_indices:
        fdst[res_index] = fft[arr_index]


class VideoOutputs(Outputs[VideoOutput]):
    out_type = VideoOutput
    vs_type = vs.VideoOutputTuple
    _fft_output_cache: Dict[Tuple[int, int], Any] = {}
    _fft_spectr_items: List[VideoOutput] = []

    def copy_output_props(self, new: VideoOutput, old: VideoOutput) -> None:
        new.last_showed_frame = old.last_showed_frame
        new.title = old.title

    def switchToNormalView(self) -> None:
        for new, old in zip(self._items, self.items):
            self.copy_output_props(new, old)

        self.items = list(self._items)

    def switchToFFTSpectrumView(self) -> None:
        if not self._fft_spectr_items:
            max_width = max(*(x.width for x in self._items), 140)
            max_height = max(*(x.height for x in self._items), 140)

            fftw_kwargs = {
                'axes': (0, 1), 'flags': ['FFTW_ESTIMATE', 'FFTW_UNALIGNED'], 'threads': nthread
            }

            for out in self._items:
                assert out.source.clip.format

                src = out.source.clip.resize.Bicubic(
                    format=out.source.clip.format.replace(
                        sample_type=vs.INTEGER, bits_per_sample=8
                    ).id, dither_type='error_diffusion'
                )

                if (shape := (src.height, src.width)) not in self._fft_output_cache:
                    yh = src.height // 2
                    xh = src.width // 2

                    self._fft_output_cache[shape] = (
                        empty_aligned(shape, np.complex64), [
                            tuple(zip(*indices)) for indices in itertools.product(
                                (
                                    (slice(None, -yh, None), slice(yh, None, None)),
                                    (slice(-yh, None, None), slice(None, yh, None))
                                ),
                                (
                                    (slice(None, -xh, None), slice(xh, None, None)),
                                    (slice(-xh, None, None), slice(None, xh, None))
                                )
                            )
                        ]
                    )

                blankclip = src.std.BlankClip(format=vs.GRAYS, color=0, keep=True)

                fftclip = blankclip.std.ModifyFrame([src, blankclip], partial(
                    _fftspectrum_vmode_modifyframe, fastroll_copy=partial(
                        _fftspectrum_vmode_fastroll_copy, rolls_indices=self._fft_output_cache[shape][1],
                    ), fftw_args={**fftw_kwargs, 'output_array': self._fft_output_cache[shape][0]}
                ))

                if fftclip.width != max_width or fftclip.height != max_height:
                    w_diff, h_diff = max_width - fftclip.width, max_height - fftclip.height
                    w_pad, w_mod = (floor(w_diff / 2), w_diff % 2) if w_diff > 0 else (0, 0)
                    h_pad, h_mod = (floor(h_diff / 2), h_diff % 2) if h_diff > 0 else (0, 0)

                    fftclip = fftclip.std.AddBorders(w_pad, w_pad + w_mod, h_pad, h_pad + h_mod)

                    if w_mod or h_mod:
                        fftclip = fftclip.resize.Bicubic(src_top=h_mod / 2, src_left=w_mod / 2)

                fftresample = fftclip.akarin.Expr('x abs sqrt log abs 25.5 *', vs.GRAY8)

                fftfps = fftresample.std.AssumeFPS(src)

                fft_output = VideoOutput(VideoOutputNode(fftfps, out.source.alpha), out.index)

                self.copy_output_props(fft_output, out)

                self._fft_spectr_items.append(fft_output)
        else:
            for new, old in zip(self._fft_spectr_items, self._items):
                self.copy_output_props(new, old)

        self.items = self._fft_spectr_items


class AudioOutputs(Outputs[AudioOutput]):
    out_type = AudioOutput
    vs_type = vs.AudioNode
