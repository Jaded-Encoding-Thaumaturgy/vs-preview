from __future__ import annotations

import sys
import traceback
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Literal, TypeVar, overload

from PyQt6.QtWidgets import QWidget
from jetpytools import KwargsT

from ..core import AbstractYAMLObjectSingleton, Frame
from . import utils
from .abstract import (
    AbstractPlugin, FileResolvePluginConfig, FileResolverPlugin, PluginConfig, PluginSettings, ResolvedScript,
    SettingsNamespace, _BasePluginT
)
from .utils import *  # noqa: F401,F403

if True:
    # has to be imported after the main
    from importlib._bootstrap_external import SOURCE_SUFFIXES  # type: ignore
    SOURCE_SUFFIXES.append('.ppy')

if TYPE_CHECKING:
    from ..main import MainWindow

PluginT = TypeVar('PluginT', bound=_BasePluginT)


__all__ = [
    'AbstractPlugin', 'PluginConfig', 'PluginSettings', 'SettingsNamespace',
    'FileResolverPlugin', 'FileResolvePluginConfig', 'ResolvedScript',
    *utils.__all__
]


class PluginImportError(ImportError):
    ...


class PluginModule:
    __all__: tuple[str, ...]

    def __new__(cls, path: Path) -> PluginModule:
        if (h := hash(path)) in _hash_module_map:
            return _hash_module_map[h]

        return super().__new__(cls)

    def __init__(self, path: Path) -> None:
        spec = spec_from_file_location(path.stem, path, submodule_search_locations=[])

        if spec is None:
            raise ImportError

        module = module_from_spec(spec)

        import_path = str(path.parent)

        sys.path.append(import_path)
        sys.modules[module.__name__] = module

        if spec.loader is None:
            sys.path.remove(import_path)
            raise PluginImportError

        spec.loader.exec_module(module)

        _hash_module_map[hash(path)] = self
        _module_proxy_map[self] = (path, module)

        try:
            module.__all__
        except AttributeError:
            sys.path.remove(import_path)
            raise PluginImportError(
                f'The plugin "{path.stem}" has no __all__ defined and thus can\'t be imported!'
            )

    def __getattr__(self, key: str) -> Any:
        return object.__getattribute__(_module_proxy_map[self][1], key)

    def __str__(self) -> str:
        return _module_proxy_map[self][0].stem


_hash_module_map = dict[int, PluginModule]()
_module_proxy_map = dict[PluginModule, tuple[Path, ModuleType | None]]()


@lru_cache
def resolve_plugins() -> Iterable[Path]:
    from ..main import MainWindow

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

    _check_folder(Path(__file__).parent / 'builtins', True)
    _check_folder(MainWindow.global_plugins_dir)

    for paths_file in MainWindow.global_plugins_dir.glob('*.pth'):
        for path in paths_file.read_text('utf8').splitlines():
            _check_folder(path)

    return plugin_files


_import_warnings = set[Path]()


def _import_warning_once(path: Path, message: str) -> None:
    if message and path not in _import_warnings:
        _import_warnings.add(path)
        print(ImportWarning(message))


def get_clean_trace() -> str:
    return traceback.format_exc().split('_call_with_frames_removed\n')[1]


def file_to_plugins(path: Path, plugin_type: type[PluginT]) -> Iterable[type[PluginT]]:
    try:
        module = PluginModule(path)
    except PluginImportError:
        return _import_warning_once(path, get_clean_trace())
    except ImportError:
        return _import_warning_once(
            path, f'The plugin at "{path}" could not be loaded because of this import error: \n{get_clean_trace()}'
        )

    for export in module.__all__:
        exp_obj = getattr(module, export)

        if not isinstance(exp_obj, type):
            continue

        if not issubclass(exp_obj, plugin_type):
            continue

        if not hasattr(exp_obj, '_config'):
            print(ImportWarning(
                f'The plugin "{exp_obj.__name__}" has no config set up and thus can\'t be imported!'
            ))
            continue

        yield exp_obj


@overload
def get_installed_plugins(
    plugin_type: type[PluginT], ret_class: Literal[False], *args: Any, **kwargs: Any
) -> dict[str, PluginT]:
    ...


@overload
def get_installed_plugins(plugin_type: type[PluginT], ret_class: Literal[True]) -> dict[str, type[PluginT]]:
    ...


def get_installed_plugins(
    plugin_type: type[PluginT], ret_class: bool, *args: Any, **kwargs: Any
) -> dict[str, PluginT] | dict[str, type[PluginT]]:
    plugins = dict[str, Any]()

    for plugin_file in resolve_plugins():
        for plugin in file_to_plugins(plugin_file, plugin_type):
            if plugin._config.namespace in plugins:
                print(UserWarning(
                    f'Tried to register plugin "{plugin._config.display_name} '
                    f'({plugin._config.namespace})" twice!'
                ))
                continue

            if ret_class:
                plugins[plugin._config.namespace] = plugin
            else:
                plugins[plugin._config.namespace] = pl = plugin(*args, **kwargs)
                pl.settings = plugin._config.settings_type(plugins[plugin._config.namespace])

    return plugins


class LocalPluginsSettings(AbstractYAMLObjectSingleton):
    def __getstate__(self) -> dict[str, dict[str, Any]]:
        return self.state | {
            plugin._config.namespace: plugin.settings.local
            for plugin in Plugins.instance[0]
        }

    def __setstate__(self, state: dict[str, dict[str, Any]]) -> None:
        if not hasattr(self, 'state'):
            self.state = {}

        self.state |= state

        for plugin in Plugins.instance[0]:
            if plugin._config.namespace in self.state:
                plugin.settings.local = self.state[plugin._config.namespace]
                plugin.settings.__setstate__(False)

        if 'gui' in self.state:
            Plugins.instance[0].gui_settings.local = self.state['gui']

        Plugins.instance[0].__setstate__(False)


class GlobalPluginsSettings(AbstractYAMLObjectSingleton):
    def __getstate__(self) -> dict[str, dict[str, Any]]:
        return self.state | {
            plugin._config.namespace: plugin.settings.globals
            for plugin in Plugins.instance[0]
        }

    def __setstate__(self, state: dict[str, dict[str, Any]]) -> None:
        if not hasattr(self, 'state'):
            self.state = {}

        self.state |= state

        for plugin in Plugins.instance[0]:
            if plugin._config.namespace in self.state:
                plugin.settings.globals = self.state[plugin._config.namespace]
                plugin.settings.__setstate__(True)

        if 'gui' in self.state:
            Plugins.instance[0].gui_settings.globals = self.state['gui']

        Plugins.instance[0].__setstate__(True)


class Plugins(AbstractYAMLObjectSingleton):
    __slots__ = ()

    _closure = {**globals()}

    # tab idx, clip idx, frame
    last_frame_change: tuple[int, int, int]

    # tab idx, clip idx
    last_output_change: tuple[int, int]

    def __init__(self, main: MainWindow) -> None:
        main.plugins = self

        self.main = main
        self.settings = SettingsNamespace()
        self.gui_settings = SettingsNamespace({'local': SettingsNamespace(), 'globals': SettingsNamespace()})
        self.plugins_tab = main.plugins_tab

        self.main.reload_before_signal.connect(self.reset_last_reload)

        self.reset_last_reload()

        self.plugins = get_installed_plugins(AbstractPlugin, False, self.main)

        i = 0
        for name, plugin in self.plugins.items():
            assert isinstance(plugin, QWidget)

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

    def setup_ui(self) -> None:
        if self.main.settings.plugins_bar_save_behaviour:
            gui = self.gui_settings[['globals', 'local'][self.main.settings.plugins_bar_save_behaviour - 1]]

            if 'sizes' in gui:
                self.main.main_split.setSizes(gui.sizes)

            if 'lastplugin' in gui:
                self.main.plugins_tab.setCurrentIndex(
                    next((plugin.index for nsp, plugin in self.plugins.items() if nsp == gui['lastplugin']), 0)
                )
        else:
            self.main.main_split.setSizes([0, 0])
            self.main.plugins_tab.setCurrentIndex(0)

    def reset_last_reload(self) -> None:
        self.last_frame_change = (-1, -1, -1)

        self.last_output_change = (-1, -1)

    def get_gui_settings(self, isglobal: bool) -> KwargsT:
        sett_global = not bool(self.main.settings.plugins_bar_save_behaviour - 1)

        if (not self.main.settings.plugins_bar_save_behaviour) or (isglobal != sett_global):
            return self.gui_settings.globals if isglobal else self.gui_settings.local

        return SettingsNamespace({
            'sizes': self.main.main_split.sizes(),
            'lastplugin': list(self.plugins.keys())[self.main.plugins_tab.currentIndex()]
        })

    def init_outputs(self) -> None:
        for plugin in self:
            if plugin._first_load_done:
                plugin.init_outputs()

    def on_current_frame_changed(self, frame: Frame) -> None:
        tab_idx = self.plugins_tab.currentIndex()

        curr_render = (tab_idx, self.main.current_output.index, int(frame))

        if self.main.main_split.current_position and (
            self.last_frame_change != curr_render or self.instant_update
        ):
            if self[tab_idx].first_load():
                self[tab_idx].init_outputs()
            self[tab_idx].on_current_frame_changed(frame)

            self.last_frame_change = curr_render

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        tab_idx = self.plugins_tab.currentIndex()

        curr_output = (tab_idx, index)

        if self.main.main_split.current_position and (
            self.last_output_change != curr_output or self.instant_update
        ):
            if self[tab_idx].first_load():
                self[tab_idx].init_outputs()
            self[tab_idx].on_current_output_changed(index, prev_index)

            self.last_output_change = curr_output

    def update(self, frame: Frame | None = None, index: int | None = None, prev_index: int | None = None) -> None:
        from jetpytools import fallback

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

    @property
    def instant_update(self) -> bool:
        if self.main.settings.plugins_bar_save_behaviour:
            gui = self.gui_settings[['globals', 'local'][self.main.settings.plugins_bar_save_behaviour - 1]]

            if 'sizes' in gui:
                return bool(gui.sizes[-1])

        return False

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

        return self.plugins[_sub]

    def __len__(self) -> int:
        return len(self.plugins)

    if TYPE_CHECKING:
        # https://github.com/python/mypy/issues/2220
        def __iter__(self) -> Iterator[AbstractPlugin]:
            ...

    def __getstate__(self) -> dict[str, dict[str, Any]]:
        GlobalPluginsSettings().state = (
            {
                k: v.globals
                for k, v in self.settings
            } | {
                plugin._config.namespace: plugin.settings.globals
                for plugin in self
            } | {
                'gui': self.get_gui_settings(True)
            }
        )

        LocalPluginsSettings().state = (
            {
                k: v.local
                for k, v in self.settings
            } | {
                plugin._config.namespace: plugin.settings.local
                for plugin in self
            } | {
                'gui': self.get_gui_settings(False)
            }
        )

        return {
            'global_settings': GlobalPluginsSettings(),
            'local_settings': LocalPluginsSettings()
        }

    def __setstate__(self, isglobal: bool) -> None:
        self.setup_ui()
