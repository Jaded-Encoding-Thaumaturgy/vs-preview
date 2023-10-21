from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Iterable, NamedTuple, TypeVar

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QSizePolicy, QWidget
from vstools import SPath

from ..core import ExtendedWidgetBase, Frame, NotchProvider

if TYPE_CHECKING:
    from ..main import MainWindow


__all__ = [
    'AbstractPlugin', 'PluginConfig',

    'FileResolverPlugin', 'FileResolvePluginConfig', 'ResolvedScript'
]


if TYPE_CHECKING:
    class _BasePluginConfig(NamedTuple):
        namespace: str
        display_name: str

    class _BasePlugin:
        _config: ClassVar[_BasePluginConfig]
else:
    T = TypeVar('T')
    _BasePlugin, _BasePluginConfig = object, Generic[T]


class PluginConfig(_BasePluginConfig, NamedTuple):  # type: ignore
    namespace: str
    display_name: str
    visible_in_tab: bool = True


class FileResolvePluginConfig(_BasePluginConfig, NamedTuple):  # type: ignore
    namespace: str
    display_name: str


class ResolvedScript(NamedTuple):
    path: Path
    display_name: str
    arguments: dict[str, Any] = {}
    reload_enabled: bool = True


class AbstractPlugin(ExtendedWidgetBase, NotchProvider):
    _config: ClassVar[PluginConfig]

    on_first_load = pyqtSignal()

    index: int = -1

    def __init__(self, main: MainWindow) -> None:
        try:
            super().__init__(main)  # type: ignore
            self.init_notches(main)

            assert isinstance(self, QWidget)
        except TypeError as e:
            print('\tMake sure you\'re inheriting a QWidget!\n')

            raise e

        self.main = main

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        self._first_load_done = False

    def first_load(self) -> None:
        if not self._first_load_done:
            self.setup_ui()

            self.add_shortcuts()

            self.set_qobject_names()

            self.on_first_load.emit()

            self._first_load_done = True

    def init_outputs(self) -> None:
        ...

    def add_shortcuts(self) -> None:
        ...

    def on_current_frame_changed(self, frame: Frame) -> None:
        ...

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        ...

    @property
    def is_notches_visible(self) -> bool:
        return (
            not self._config.visible_in_tab
        ) or self.index == self.main.plugins.plugins_tab.currentIndex()  # type: ignore


class FileResolverPlugin:
    _config: ClassVar[FileResolvePluginConfig]

    temp_handles = set[SPath]()

    def get_extensions(self) -> Iterable[str]:
        return []

    def can_run_file(self, filepath: Path) -> bool:
        raise NotImplementedError

    def resolve_path(self, filepath: Path) -> ResolvedScript:
        raise NotImplementedError

    def cleanup(self) -> None:
        for file in self.temp_handles:
            try:
                if not file.exists():
                    continue

                if file.is_dir():
                    file.rmdirs(True)
                else:
                    file.unlink(True)
            except PermissionError:
                continue

    def get_temp_path(self, is_folder: bool = False) -> SPath:
        from tempfile import mkdtemp, mkstemp

        if is_folder:
            temp = mkdtemp()
        else:
            temp = mkstemp()[1]

        temp_path = SPath(temp)

        self.temp_handles.add(temp_path)

        return temp_path


_BasePluginT = _BasePlugin | AbstractPlugin | FileResolverPlugin
