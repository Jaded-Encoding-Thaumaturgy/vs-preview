from __future__ import annotations

from typing import Any

from jetpytools import SPath

from PyQt6.QtWidgets import QLabel

from vspreview.core import AbstractSettingsWidget, CheckBox, ComboBox, HBoxLayout, LineEdit, VBoxLayout, try_load
from vspreview.core.abstracts import PushButton
from vspreview.models import GeneralModel
from vspreview.plugins import AbstractPlugin
from .utils import do_login

__all__ = [
    'CompSettings'
]


class CompSettings(AbstractSettingsWidget):
    __slots__ = ('delete_cache_checkbox', 'frame_type_checkbox', 'login_username_edit', 'login_password_edit', 'tmdb_apikey_edit')

    DEFAULT_COLLECTION_NAME = 'Unknown'

    def __init__(self, plugin: AbstractPlugin) -> None:
        super().__init__()

        self.plugin = plugin

        self.path = plugin.main.global_plugins_dir / 'slowpics_comp'

    def setup_ui(self) -> None:
        super().setup_ui()

        self.collection_name_template_edit = LineEdit('Collection Name Template')

        self.delete_cache_checkbox = CheckBox('Delete images cache after upload')

        self.frame_type_checkbox = CheckBox('Include frametype in image name')

        self.default_public_checkbox = CheckBox('Default Public Flag')
        self.default_nsfw_checkbox = CheckBox('Default NSFW Flag')

        self.login_username_edit = LineEdit('Username')
        self.login_password_edit = LineEdit('Password')
        self.login_button = PushButton('Login', self, clicked=self.handle_login_click)

        self.compression_combobox = ComboBox[str](model=GeneralModel[str](['fast', 'slow', 'uncompressed']))

        self.frame_ntype_combobox = ComboBox[str](model=GeneralModel[str](['timeline', 'frame', 'time', 'both']))
        self.frame_ntype_combobox.setCurrentValue('both')

        self.tmdb_apikey_edit = LineEdit('API Key')

        VBoxLayout(self.vlayout, [
            self.collection_name_template_edit,
            QLabel('Available replaces: {tmdb_title}, {video_nodes}, {tmdb_year}')
        ])

        HBoxLayout(
            self.vlayout, [
                VBoxLayout([
                    self.delete_cache_checkbox,
                    self.frame_type_checkbox
                ]),
                self.get_separator(),
                VBoxLayout([
                    QLabel('Compression Type:'),
                    self.compression_combobox
                ])
            ]
        )

        HBoxLayout(self.vlayout, [
            QLabel('Include frame position type:'),
            self.frame_ntype_combobox
        ])

        HBoxLayout(
            self.vlayout,
            VBoxLayout([
                HBoxLayout([QLabel('TMDB API Key'), self.tmdb_apikey_edit]),
                self.get_separator(),
                HBoxLayout([QLabel('Username'), self.login_username_edit]),
                HBoxLayout([QLabel('Password'), self.login_password_edit]),
                self.login_button,
            ])
        )

        HBoxLayout(self.vlayout, [
            self.default_public_checkbox,
            self.default_nsfw_checkbox
        ])

    def set_defaults(self) -> None:
        self.delete_cache_checkbox.setChecked(True)
        self.frame_type_checkbox.setChecked(True)
        # https://github.com/Radarr/Radarr/blob/29ba6fe5563e737f0f87919e48f556e39284e6bb/src/NzbDrone.Common/Cloud/RadarrCloudRequestBuilder.cs#L31
        self.tmdb_apikey_edit.setText('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIxYTczNzMzMDE5NjFkMDNmOTdmODUzYTg3NmRkMTIxMiIsInN1YiI6IjU4NjRmNTkyYzNhMzY4MGFiNjAxNzUzNCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.gh1BwogCCKOda6xj9FRMgAAj_RYKMMPC3oNlcBtlmwk')  # noqa

    def handle_login_click(self) -> None:
        username = self.login_username_edit.text()
        password = self.login_password_edit.text()

        if not username or not password:
            return

        do_login(username, password, self.cookies_path)

        self.login_username_edit.setText('')
        self.login_password_edit.setText('')

    @property
    def cookies_path(self) -> SPath:
        return self.path / 'cookies.json'

    @property
    def delete_cache_enabled(self) -> bool:
        return self.delete_cache_checkbox.isChecked()

    @property
    def frame_type_enabled(self) -> bool:
        return self.frame_type_checkbox.isChecked()

    @property
    def tmdb_apikey(self) -> str:
        return self.tmdb_apikey_edit.text()

    @property
    def compression(self) -> int:
        return self.compression_combobox.currentIndex()

    @property
    def frame_ntype(self) -> str:
        return self.frame_ntype_combobox.currentValue()

    @property
    def default_public(self) -> bool:
        return self.default_public_checkbox.isChecked()

    @property
    def default_nsfw(self) -> bool:
        return self.default_nsfw_checkbox.isChecked()

    @property
    def collection_name_template(self) -> str:
        return self.collection_name_template_edit.text()

    def __getstate__(self) -> dict[str, Any]:
        return {
            'delete_cache_enabled': self.delete_cache_enabled,
            'frame_type_enabled': self.frame_type_enabled,
            'tmdb_apikey': self.tmdb_apikey,
            'compression': self.compression,
            'default_public': self.default_public,
            'default_nsfw': self.default_nsfw,
            'collection_name_template': self.collection_name_template,
            'frame_ntype': self.frame_ntype
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'delete_cache_enabled', bool, self.delete_cache_checkbox.setChecked)
        try_load(state, 'frame_type_enabled', bool, self.frame_type_checkbox.setChecked)
        try_load(state, 'default_public', bool, self.default_public_checkbox.setChecked)
        try_load(state, 'default_nsfw', bool, self.default_nsfw_checkbox.setChecked)
        try_load(state, 'collection_name_template', str, self.collection_name_template_edit.setText)
        try_load(state, 'tmdb_apikey', str, self.tmdb_apikey_edit.setText)
        try_load(state, 'compression', int, self.compression_combobox.setCurrentIndex)
        try_load(state, 'frame_ntype', str, self.frame_ntype_combobox.setCurrentValue)
