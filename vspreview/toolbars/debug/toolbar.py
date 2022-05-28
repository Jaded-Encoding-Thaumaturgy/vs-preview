from __future__ import annotations

import logging

from ...core import AbstractMainWindow, AbstractToolbar, LineEdit, PushButton
from ...utils import debug, vs_clear_cache
from .settings import DebugSettings


class DebugToolbar(AbstractToolbar):
    _no_visibility_choice = True

    __slots__ = ('exec_lineedit', )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, DebugSettings())

        self.setup_ui()

        if self.settings.DEBUG_TOOLBAR_BUTTONS_PRINT_STATE:
            self.filter = debug.EventFilter(main)
            self.main.toolbars.main.widget.installEventFilter(self.filter)
            for toolbar in self.main.toolbars:
                toolbar.widget.installEventFilter(self.filter)

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.exec_lineedit = LineEdit(
            self, editingFinished=self.exec_button_clicked,
            placeholderText='Python statement in context of DebugToolbar.exec_button_clicked()'
        )

        self.hlayout.addWidgets([
            PushButton('Test', self, clicked=self.test_button_clicked),
            PushButton('Break', self),
            self.exec_lineedit,
            PushButton('Exec', self, clicked=self.exec_button_clicked)
        ])

        self.hlayout.addStretch()

    def test_button_clicked(self, checked: bool | None = None) -> None:
        vs_clear_cache()

    def exec_button_clicked(self, checked: bool | None = None) -> None:
        try:
            exec(self.exec_lineedit.text())
        except BaseException as e:
            logging.error(e)

    def break_button_clicked(self, checked: bool | None = None) -> None:
        breakpoint()
