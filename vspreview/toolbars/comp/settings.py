from __future__ import annotations

from typing import Any, Mapping

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, CheckBox, HBoxLayout, LineEdit, VBoxLayout, try_load

__all__ = [
    'CompSettings'
]


class CompSettings(AbstractToolbarSettings):
    __slots__ = ('delete_cache_checkbox', 'login_browser_id', 'login_session')

    DEFAULT_COLLECTION_NAME = 'Unknown'

    def setup_ui(self) -> None:
        super().setup_ui()

        self.delete_cache_checkbox = CheckBox('Delete images cache after upload')

        self.login_browser_id = LineEdit('Browser ID')
        self.login_session = LineEdit('Session ID')

        label = QLabel(
            'To get this info: Open Dev console in browser, go to network tab, upload a comparison,'
            'click request called "comparison" Copy browserId from payload, copy session token from '
            'SLPSESSION cookie from cookies'
        )
        label.setMaximumHeight(50)
        label.setMinimumWidth(400)
        label.setWordWrap(True)

        self.vlayout.addWidget(self.delete_cache_checkbox)

        HBoxLayout(
            self.vlayout,
            VBoxLayout([
                label,
                HBoxLayout([QLabel("Browser ID"), self.login_browser_id]),
                HBoxLayout([QLabel("Session ID"), self.login_session])
            ])
        )

    def set_defaults(self) -> None:
        self.delete_cache_checkbox.setChecked(True)

    @property
    def delete_cache_enabled(self) -> bool:
        return self.delete_cache_checkbox.isChecked()

    @property
    def browser_id(self) -> str:
        return self.login_browser_id.text()

    @property
    def session_id(self) -> str:
        return self.login_session.text()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'delete_cache_enabled': self.delete_cache_enabled,
            'browser_id': self.browser_id,
            'session_id': self.session_id,
        }

    def _setstate_(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'delete_cache_enabled', bool, self.delete_cache_checkbox.setChecked)
        try_load(state, 'browser_id', str, self.login_browser_id.setText)
        try_load(state, 'session_id', str, self.login_session.setText)
