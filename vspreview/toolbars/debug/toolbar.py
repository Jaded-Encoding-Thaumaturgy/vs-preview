from __future__ import annotations
from typing import TYPE_CHECKING

from ...core import AbstractToolbar, LineEdit, PushButton
from .settings import DebugSettings

if TYPE_CHECKING:
    from ...main import MainWindow


__all__ = [
    'DebugToolbar'
]


class DebugToolbar(AbstractToolbar):
    __slots__ = ('exec_lineedit', )

    _no_visibility_choice = True

    settings: DebugSettings

    def __init__(self, main: MainWindow) -> None:
        from ...utils import debug

        super().__init__(main, DebugSettings(self))

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

    def test_button_clicked(self, checked: bool | None = None) -> None:
        from vstools.utils.vs_proxy import clear_cache
        clear_cache()

    def exec_button_clicked(self, checked: bool | None = None) -> None:
        try:
            exec(self.exec_lineedit.text())
        except BaseException as e:
            import logging

            logging.error(e)

    def break_button_clicked(self, checked: bool | None = None) -> None:
        breakpoint()
