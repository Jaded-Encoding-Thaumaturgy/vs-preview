from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Mapping, cast, overload

from ..core import AbstractYAMLObjectSingleton, Frame, storage_err_msg
from .abstract import AbstractPlugin

if TYPE_CHECKING:
    from ..main import MainWindow


__all__ = [
    'Plugins'
]


class Plugins(AbstractYAMLObjectSingleton):
    __slots__ = ()

    _closure = {**globals()}

    @classmethod
    def file_to_plugin(cls, name: str) -> type[AbstractPlugin]:
        exec(f'from . import {name} as _inner_tb_{name}', cls._closure)
        module = cls._closure[f'_inner_tb_{name}']
        return object.__getattribute__(module, module.__all__[0])  # type: ignore # noqa

    def __init__(self, main: MainWindow) -> None:
        main.plugins = self

        self.main = main
        self.plugins_tab = main.plugins_tab
        self.main.main_split.setSizes([0, 0])

        # tab idx, clip idx, frame
        self.last_render = (-1, -1, -1)

        self.plugin_names = [
            file.stem for file in Path(__file__).parent.glob('*.py')
            if file.stem not in {'__init__', 'abstract'}
        ]

        self.plugins = dict[str, AbstractPlugin]({
            name: self.file_to_plugin(name)(main)
            for name in self.plugin_names
        })

        for name, plugin in self.plugins.items():
            plugin.setObjectName(f'Plugins.{name}')

            self.plugins_tab.addTab(plugin, plugin._plugin_name)

    def on_current_frame_changed(self, frame: Frame) -> None:
        tab_idx = self.plugins_tab.currentIndex()

        curr_render = (tab_idx, self.main.current_output.index, int(frame))

        if self.main.main_split.current_position and self.last_render != curr_render:
            self[tab_idx].on_current_frame_changed(frame)

            self.last_render = curr_render

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        tab_idx = self.plugins_tab.currentIndex()

        curr_render = (tab_idx, index, self.main.current_output.last_showed_frame)

        if self.main.main_split.current_position and self.last_render != curr_render:
            self[tab_idx].on_current_output_changed(index, prev_index)

            self.last_render = curr_render

    def update(self, frame: Frame | None = None, index: int | None = None, prev_index: int | None = None) -> None:
        from vstools import fallback

        if not self.main.current_output:
            return

        self.on_current_frame_changed(
            fallback(frame, self.main.current_output.last_showed_frame)
        )
        self.on_current_output_changed(
            fallback(index, self.main.current_output.index),
            fallback(prev_index, self.main.current_output.index),
        )

    @overload
    def __getitem__(self, _sub: str | int) -> AbstractPlugin:
        ...

    @overload
    def __getitem__(self, _sub: slice) -> list[AbstractPlugin]:
        ...

    def __getitem__(self, _sub: str | int | slice) -> AbstractPlugin | list[AbstractPlugin]:
        length = len(self.plugins)
        if isinstance(_sub, slice):
            return [self[i] for i in range(*_sub.indices(length))]

        if isinstance(_sub, int):
            if _sub < 0:
                _sub += length
            if _sub < 0 or _sub >= length:
                raise IndexError

            _sub = list(self.plugins.keys())[_sub]

        return cast(AbstractPlugin, self.plugins[_sub])

    def __len__(self) -> int:
        return len(self.plugins)

    if TYPE_CHECKING:
        # https://github.com/python/mypy/issues/2220
        def __iter__(self) -> Iterator[AbstractPlugin]:
            ...

    def __getstate__(self) -> Mapping[str, Mapping[str, Any]]:
        return {
            toolbar_name: getattr(self, toolbar_name).__getstate__()
            for toolbar_name in self.plugins
        }

    def __setstate__(self, state: Mapping[str, Mapping[str, Any]]) -> None:
        for toolbar_name in self.plugins:
            try:
                storage = state[toolbar_name]
                if not isinstance(storage, Mapping):
                    raise TypeError
                getattr(self, toolbar_name).__setstate__(storage)
            except (KeyError, TypeError) as e:
                logging.error(e)
                logging.warning(storage_err_msg(toolbar_name))
