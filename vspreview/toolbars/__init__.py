from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Iterator, Mapping, cast, overload

from ..core import AbstractToolbar, AbstractYAMLObjectSingleton, storage_err_msg
from .main import MainToolbar
from .playback import PlaybackToolbar

if TYPE_CHECKING:
    from ..main import MainWindow
    from .benchmark import BenchmarkToolbar
    from .debug import DebugToolbar
    from .misc import MiscToolbar
    from .pipette import PipetteToolbar
    from .scening import SceningToolbar


__all__ = [
    'MainToolbar',

    'Toolbars'
]


class Toolbars(AbstractYAMLObjectSingleton):
    __slots__ = ()

    main: MainToolbar
    playback: PlaybackToolbar
    scening: SceningToolbar
    pipette: PipetteToolbar
    benchmark: BenchmarkToolbar
    misc: MiscToolbar
    debug: DebugToolbar

    _closure = {**globals()}

    @classmethod
    def name_to_tooltype(cls, name: str) -> type[AbstractToolbar]:
        exec(f'from .{name} import {name.title()}Toolbar as _inner_tb_{name}', cls._closure)
        return cls._closure[f'_inner_tb_{name}']  # type: ignore # noqa

    def __init__(self, main_window: MainWindow) -> None:
        main_window.toolbars = self

        self.main = MainToolbar(main_window)
        self.playback = PlaybackToolbar(main_window)

        self.toolbar_names = [
            'debug', 'scening', 'pipette', 'benchmark', 'misc'
        ]

        self.toolbars = dict(main=self.main, playback=self.playback) | {
            name: self.name_to_tooltype(name)(main_window)
            for name in self.toolbar_names
        }

        for name, toolbar in self.toolbars.items():
            toolbar.setObjectName(f'Toolbars.{name}')

            if not hasattr(self, name):
                setattr(self, name, toolbar)

    @overload
    def __getitem__(self, _sub: str | int) -> AbstractToolbar:
        ...

    @overload
    def __getitem__(self, _sub: slice) -> list[AbstractToolbar]:
        ...

    def __getitem__(self, _sub: str | int | slice) -> AbstractToolbar | list[AbstractToolbar]:
        length = len(self.toolbars)
        if isinstance(_sub, slice):
            return [self[i] for i in range(*_sub.indices(length))]

        if isinstance(_sub, int):
            if _sub < 0:
                _sub += length
            if _sub < 0 or _sub >= length:
                raise IndexError

            _sub = list(self.toolbars.keys())[_sub]

        return cast(AbstractToolbar, getattr(self, _sub))

    def __len__(self) -> int:
        return len(self.toolbars)

    if TYPE_CHECKING:
        # https://github.com/python/mypy/issues/2220
        def __iter__(self) -> Iterator[AbstractToolbar]:
            ...

    def __getstate__(self) -> dict[str, dict[str, Any]]:
        return {
            toolbar_name: getattr(self, toolbar_name).__getstate__()
            for toolbar_name in self.toolbars
        }

    def __setstate__(self, state: dict[str, dict[str, Any]]) -> None:
        for toolbar_name in self.toolbars:
            try:
                storage = state[toolbar_name]
                if not isinstance(storage, Mapping):
                    raise TypeError
                getattr(self, toolbar_name).__setstate__(storage)
            except (KeyError, TypeError) as e:
                logging.error(e)
                logging.warning(storage_err_msg(toolbar_name))
