from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Iterator, Mapping, cast, overload

from ..core import storage_err_msg
from ..core.abstracts import AbstractMainWindow, AbstractToolbar
from ..core.bases import AbstractYAMLObjectSingleton
from .benchmark import BenchmarkToolbar
from .comp import CompToolbar
from .debug import DebugToolbar
from .main import MainToolbar
from .misc import MiscToolbar
from .pipette import PipetteToolbar
from .playback import PlaybackToolbar
from .scening import SceningToolbar

all_toolbars = [
    MainToolbar, PlaybackToolbar, SceningToolbar, PipetteToolbar,
    BenchmarkToolbar, MiscToolbar, CompToolbar, DebugToolbar
]


class Toolbars(AbstractYAMLObjectSingleton):
    __slots__ = ()

    main: MainToolbar
    playback: PlaybackToolbar
    scening: SceningToolbar
    pipette: PipetteToolbar
    benchmark: BenchmarkToolbar
    misc: MiscToolbar
    comp: CompToolbar
    debug: DebugToolbar

    # 'main' should always be the first
    all_toolbars_names = ['main', 'playback', 'scening', 'pipette', 'benchmark', 'misc', 'comp', 'debug']

    def __init__(self, main_window: AbstractMainWindow) -> None:
        for name, toolbar in zip(self.all_toolbars_names, all_toolbars):
            self.__setattr__(name, toolbar(main_window))

        for name in self.all_toolbars_names:
            self.__getattribute__(name).setObjectName(f'Toolbars.{name}')

    @overload
    def __getitem__(self, _sub: int) -> AbstractToolbar:
        ...

    @overload
    def __getitem__(self, _sub: slice) -> list[AbstractToolbar]:
        ...

    def __getitem__(self, _sub: int | slice) -> AbstractToolbar | list[AbstractToolbar]:
        length = len(self.all_toolbars_names)
        if isinstance(_sub, slice):
            return [self[i] for i in range(*_sub.indices(length))]
        elif isinstance(_sub, int):
            if _sub < 0:
                _sub += length
            if _sub < 0 or _sub >= length:
                raise IndexError
            return cast(AbstractToolbar, getattr(self, self.all_toolbars_names[_sub]))

    def __len__(self) -> int:
        return len(self.all_toolbars_names)

    if TYPE_CHECKING:
        # https://github.com/python/mypy/issues/2220
        def __iter__(self) -> Iterator[AbstractToolbar]:
            ...

    def __getstate__(self) -> Mapping[str, Mapping[str, Any]]:
        return {
            toolbar_name: getattr(self, toolbar_name).__getstate__()
            for toolbar_name in self.all_toolbars_names
        }

    def __setstate__(self, state: Mapping[str, Mapping[str, Any]]) -> None:
        for toolbar_name in self.all_toolbars_names:
            try:
                storage = state[toolbar_name]
                if not isinstance(storage, Mapping):
                    raise TypeError
                getattr(self, toolbar_name).__setstate__(storage)
            except (KeyError, TypeError) as e:
                logging.error(e)
                logging.warning(storage_err_msg(toolbar_name))
