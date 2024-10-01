from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbar, LineEdit, PushButton, Switch, try_load
from .settings import DebugSettings

if TYPE_CHECKING:
    from ...main import MainWindow

__all__ = [
    'DebugToolbar'
]


class DebugToolbar(AbstractToolbar):
    __slots__ = ('exec_lineedit', 'debug_logging_enabled', 'debug_logging_switch')

    _no_visibility_choice = True

    settings: DebugSettings

    def __init__(self, main: MainWindow) -> None:
        from ...utils import debug

        super().__init__(main, DebugSettings(self))

        self.debug_logging_enabled = False
        self.setup_ui()

        if self.settings.DEBUG_TOOLBAR_BUTTONS_PRINT_STATE:
            self.filter = debug.EventFilter(main)

            self.main.toolbars.main.widget.installEventFilter(self.filter)  # type: ignore

            for toolbar in self.main.toolbars:
                toolbar.widget.installEventFilter(self.filter)  # type: ignore

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.exec_lineedit = LineEdit(
            'Python statement in context of DebugToolbar.exec_button_clicked()',
            self, editingFinished=self.exec_button_clicked
        )

        self.hlayout.addWidgets([
            PushButton('Test', self, clicked=self.test_button_clicked),
            PushButton('Break', self),
            self.exec_lineedit,
            PushButton('Exec', self, clicked=self.exec_button_clicked)
        ])

        self.hlayout.addStretch()

        debug_logging_label = QLabel("Debug Logging")
        self.hlayout.addWidget(debug_logging_label)

        self.debug_logging_switch = Switch(10, 22, checked=self.debug_logging_enabled, clicked=self.toggle_debug_logging)
        self.hlayout.addWidget(self.debug_logging_switch)

    def test_button_clicked(self, checked: bool | None = None) -> None:
        from vstools.utils.vs_proxy import clear_cache
        clear_cache()

    def exec_button_clicked(self, checked: bool | None = None) -> None:
        try:
            exec(self.exec_lineedit.text())
        except BaseException as e:
            logging.error(e)

    def break_button_clicked(self, checked: bool | None = None) -> None:
        breakpoint()

    def toggle_debug_logging(self, checked: bool) -> None:
        self.debug_logging_enabled = checked

        logging.getLogger().setLevel(logging.DEBUG if checked else logging.INFO)

        logging.info(f"Debug logging {'enabled' if checked else 'disabled'}")

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            'debug_logging_enabled': self.debug_logging_enabled
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'debug_logging_enabled', bool, self.debug_logging_switch.setChecked)

        super().__setstate__(state)
