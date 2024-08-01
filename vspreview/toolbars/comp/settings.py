from __future__ import annotations

from typing import Any, Mapping

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, CheckBox, ComboBox, HBoxLayout, LineEdit, VBoxLayout, try_load
from ...models import GeneralModel

__all__ = [
    'CompSettings'
]


class CompSettings(AbstractToolbarSettings):
    __slots__ = ('delete_cache_checkbox', 'frame_type_checkbox', 'login_browser_id_edit', 'login_session_edit', 'tmdb_apikey_edit')

    DEFAULT_COLLECTION_NAME = 'Unknown'

    def setup_ui(self) -> None:
        super().setup_ui()

        self.delete_cache_checkbox = CheckBox('Delete images cache after upload')

        self.frame_type_checkbox = CheckBox('Include frametype in image name')

        self.login_browser_id_edit = LineEdit('Browser ID')
        self.login_session_edit = LineEdit('Session ID')

        self.compression_combobox = ComboBox[str](model=GeneralModel[str](['fast', 'slow', 'uncompressed']))

        self.tmdb_apikey_edit = LineEdit('API Key')

        label = QLabel(
            'To get this info: Open Dev console in browser, go to network tab, upload a comparison,'
            'click request called "comparison" Copy browserId from payload, copy session token from '
            'SLP-SESSION cookie from cookies'
        )
        label.setMaximumHeight(50)
        label.setMinimumWidth(400)
        label.setWordWrap(True)

        HBoxLayout(
            self.vlayout, [
                VBoxLayout([
                    self.delete_cache_checkbox,
                    self.frame_type_checkbox
                ]),
                self.get_separator(),
                VBoxLayout([
                    QLabel("Compression Type:"),
                    self.compression_combobox
                ])
            ]
        )

        HBoxLayout(
            self.vlayout,
            VBoxLayout([
                HBoxLayout([QLabel("TMDB API Key"), self.tmdb_apikey_edit]),
                label,
                HBoxLayout([QLabel("Browser ID"), self.login_browser_id_edit]),
                HBoxLayout([QLabel("Session ID"), self.login_session_edit]),
            ])
        )

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
    def browser_id(self) -> str:
        return self.login_browser_id_edit.text()

    @property
    def session_id(self) -> str:
        return self.login_session_edit.text()

    @property
    def tmdb_apikey(self) -> str:
        return self.tmdb_apikey_edit.text()

    @property
    def compression(self) -> int:
        return self.compression_combobox.currentIndex()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'delete_cache_enabled': self.delete_cache_enabled,
            'frame_type_enabled': self.frame_type_enabled,
            'browser_id': self.browser_id,
            'session_id': self.session_id,
            'tmdb_apikey': self.tmdb_apikey,
            'compression': self.compression
        }

    def _setstate_(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'delete_cache_enabled', bool, self.delete_cache_checkbox.setChecked)
        try_load(state, 'frame_type_enabled', bool, self.frame_type_checkbox.setChecked)
        try_load(state, 'browser_id', str, self.login_browser_id_edit.setText)
        try_load(state, 'session_id', str, self.login_session_edit.setText)
        try_load(state, 'tmdb_apikey', str, self.tmdb_apikey_edit.setText)
        try_load(state, 'compression', int, self.compression_combobox.setCurrentIndex)
