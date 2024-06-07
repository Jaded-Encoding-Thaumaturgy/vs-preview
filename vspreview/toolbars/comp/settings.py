from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, CheckBox, HBoxLayout, LineEdit, VBoxLayout, PushButton, try_load, main_window

__all__ = [
    'CompSettings'
]


class CompSettings(AbstractToolbarSettings):
    __slots__ = ('delete_cache_checkbox', 'frame_type_checkbox', 'login_username_edit', 'login_password_edit', 'tmdb_apikey_edit')

    DEFAULT_COLLECTION_NAME = 'Unknown'

    def setup_ui(self) -> None:
        super().setup_ui()

        self.main_window = main_window()

        self.delete_cache_checkbox = CheckBox('Delete images cache after upload')

        self.frame_type_checkbox = CheckBox('Include frametype in image name')

        self.login_username_edit = LineEdit('Username')
        self.login_password_edit = LineEdit('Password')

        self.tmdb_apikey_edit = LineEdit('API Key')

        self.password_submit_button = PushButton(
            'submit', self, clicked=self._store_password
        )

        label = QLabel(
            'This will store the password locally, so make sure no one gets access to the system. '
            f'The Password will be stored at {self.password_location}'
        )
        label.setMaximumHeight(50)
        label.setMinimumWidth(400)
        label.setWordWrap(True)

        self.vlayout.addWidget(self.delete_cache_checkbox)
        self.vlayout.addWidget(self.frame_type_checkbox)

        HBoxLayout(
            self.vlayout,
            VBoxLayout([
                HBoxLayout([QLabel("TMDB API Key"), self.tmdb_apikey_edit]),
                label,
                HBoxLayout([QLabel("Username"), self.login_username_edit]),
                HBoxLayout([QLabel("Password"), self.login_password_edit]),
                self.password_submit_button,
            ])
        )

    def _store_password(self) -> None:
        password = self.login_password_edit.text()

        if password:
            self.password_location.write_text(password)
            self.login_password_edit.setText("")
        else:
            self.password_location.unlink(True)

    def set_defaults(self) -> None:
        self.delete_cache_checkbox.setChecked(True)
        self.frame_type_checkbox.setChecked(True)

    @property
    def delete_cache_enabled(self) -> bool:
        return self.delete_cache_checkbox.isChecked()

    @property
    def frame_type_enabled(self) -> bool:
        return self.frame_type_checkbox.isChecked()

    @property
    def password_location(self) -> Path:
        return self.main_window.global_config_dir / "slowpic_password.txt"

    @property
    def username(self) -> str:
        return self.login_username_edit.text()

    @property
    def tmdb_apikey(self) -> str:
        return self.tmdb_apikey_edit.text()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'delete_cache_enabled': self.delete_cache_enabled,
            'frame_type_enabled': self.frame_type_enabled,
            'username': self.username,
            'tmdb_apikey': self.tmdb_apikey,
        }

    def _setstate_(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'delete_cache_enabled', bool, self.delete_cache_checkbox.setChecked)
        try_load(state, 'frame_type_enabled', bool, self.frame_type_checkbox.setChecked)
        try_load(state, 'username', str, self.login_username_edit.setText)
        try_load(state, 'tmdb_apikey', str, self.tmdb_apikey_edit.setText)
