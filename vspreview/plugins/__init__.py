from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Mapping, cast, overload

from ..core import AbstractYAMLObjectSingleton, Frame, storage_err_msg
from . import utils
from .abstract import AbstractPlugin, PluginConfig
from .utils import *  # noqa: F401,F403

if TYPE_CHECKING:
    from ..main import MainWindow


__all__ = [
    'AbstractPlugin', 'PluginConfig',
    *utils.__all__
]


class Plugins(AbstractYAMLObjectSingleton):
    __slots__ = ()

    _closure = {**globals()}

    # tab idx, clip idx, frame
    last_frame_change: tuple[int, int, int]

    # tab idx, clip idx
    last_output_change: tuple[int, int]

    @classmethod
    def file_to_plugins(cls, path: Path) -> Iterable[type[AbstractPlugin]]:
        from importlib.util import module_from_spec, spec_from_file_location
        if True:
            # has to be imported after the main
            from importlib._bootstrap_external import SOURCE_SUFFIXES  # type: ignore
            SOURCE_SUFFIXES.append('.ppy')

        spec = spec_from_file_location(path.stem, path)
        module = module_from_spec(spec)

        spec.loader.exec_module(module)

        try:
            module_all = object.__getattribute__(module, '__all__')
        except AttributeError:
            print(ImportWarning(f'The plugin "{path.stem}" has no __all__ defined and thus can\'t be imported!'))
            return

        for export in cast(tuple[str, ...], module_all):
            exp_obj = object.__getattribute__(module, export)

            if not isinstance(exp_obj, type):
                continue

            if not issubclass(exp_obj, AbstractPlugin):
                continue

            if not hasattr(exp_obj, '_config'):
                print(ImportWarning(
                    f'The plugin "{exp_obj.__name__}" has no config set up and thus can\'t be imported!'
                ))
                continue

            yield exp_obj

    def __init__(self, main: MainWindow) -> None:
        main.plugins = self

        self.main = main
        self.plugins_tab = main.plugins_tab
        self.main.main_split.setSizes([0, 0])
        self.main.reload_before_signal.connect(self.reset_last_reload)

        self.reset_last_reload()

        self.plugins = dict[str, AbstractPlugin]()

        plugin_files = list[Path]()

        def _find_files(folder: Path, ignore_path: bool = False) -> None:
            files = list(folder.glob('*.ppy'))

            if files:
                if not ignore_path:
                    sys.path.append(str(folder))

                plugin_files.extend(files)

        def _check_folder(folder: str | Path, ignore_path: bool = False) -> None:
            if not folder:
                return

            if isinstance(folder, str):
                folder = folder.strip()

                if folder.startswith(';'):
                    return

                folder = Path(folder)

            if not folder.is_dir():
                return

            _find_files(folder, ignore_path)

            for folder in (f for f in folder.glob('*') if f.is_dir()):
                _find_files(folder, ignore_path)

        _check_folder(Path(__file__).parent, True)
        _check_folder(self.main.global_plugins_dir)

        for paths_file in self.main.global_plugins_dir.glob('*.pth'):
            for path in paths_file.read_text('utf8').splitlines():
                _check_folder(path)

        for plugin_file in plugin_files:
            for plugin in self.file_to_plugins(plugin_file):
                if plugin._config.namespace in self.plugins:
                    print(UserWarning(
                        f'Tried to register plugin "{plugin._config.display_name} '
                        f'({plugin._config.namespace})" twice!'
                    ))

                self.plugins[plugin._config.namespace] = plugin(self.main)

        i = 0
        for name, plugin in self.plugins.items():
            plugin.setObjectName(f'Plugins.{name}')

            if not plugin._config.visible_in_tab:
                try:
                    plugin.hide()
                except Exception:
                    ...

                continue

            plugin.index = i

            self.plugins_tab.addTab(plugin, plugin._config.display_name)
            i += 1

    def reset_last_reload(self) -> None:
        self.last_frame_change = (-1, -1, -1)

        self.last_output_change = (-1, -1)

    def init_outputs(self) -> None:
        for plugin in self:
            plugin.init_outputs()

    def on_current_frame_changed(self, frame: Frame) -> None:
        tab_idx = self.plugins_tab.currentIndex()

        curr_render = (tab_idx, self.main.current_output.index, int(frame))

        if self.main.main_split.current_position and self.last_frame_change != curr_render:
            self[tab_idx].on_current_frame_changed(frame)

            self.last_frame_change = curr_render

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        tab_idx = self.plugins_tab.currentIndex()

        curr_output = (tab_idx, index)

        if self.main.main_split.current_position and self.last_output_change != curr_output:
            self[tab_idx].on_current_output_changed(index, prev_index)

            self.last_output_change = curr_output

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

        sizel, sizer = self.main.main_split.sizes()

        self.main.main_split.setSizes([sizel, sizer - 1])
        self.main.main_split.setSizes([sizel, sizer])

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
