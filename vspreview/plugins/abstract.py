from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from PyQt6.QtWidgets import QSizePolicy

from ..core import ExtendedWidgetBase, Frame, NotchProvider

if TYPE_CHECKING:
    from ..main import MainWindow


__all__ = [
    'AbstractPlugin'
]


class AbstractPlugin(ExtendedWidgetBase, NotchProvider):
    _plugin_name: ClassVar[str]
    _visible_in_tab: ClassVar[bool] = True

    def __init__(self, main: MainWindow, index: int) -> None:
        try:
            super().__init__(main)
            self.init_notches(main)
        except TypeError as e:
            print('\tMake sure you\'re inheriting a QWidget!\n')

            raise e

        self.main = main
        self.index = index

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        self.setup_ui()

        self.add_shortcuts()

        self.set_qobject_names()

    def add_shortcuts(self) -> None:
        ...

    def on_current_frame_changed(self, frame: Frame) -> None:
        ...

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        ...
