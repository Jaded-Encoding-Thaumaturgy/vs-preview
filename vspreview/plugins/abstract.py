from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, NamedTuple

from PyQt6.QtWidgets import QSizePolicy

from ..core import ExtendedWidgetBase, Frame, NotchProvider

if TYPE_CHECKING:
    from ..main import MainWindow


__all__ = [
    'AbstractPlugin',
    'PluginConfig'
]


class PluginConfig(NamedTuple):
    namespace: str
    display_name: str
    visible_in_tab: bool = True


class AbstractPlugin(ExtendedWidgetBase, NotchProvider):
    _config: ClassVar[PluginConfig]

    index: int = -1

    def __init__(self, main: MainWindow) -> None:
        try:
            super().__init__(main)
            self.init_notches(main)
        except TypeError as e:
            print('\tMake sure you\'re inheriting a QWidget!\n')

            raise e

        self.main = main

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        self.setup_ui()

        self.add_shortcuts()

        self.set_qobject_names()

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
        return (not self._config.visible_in_tab) or self.index == self.main.plugins.plugins_tab.currentIndex()
