from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel

from vspreview.core import AbstractSettingsWidget, CheckBox, ComboBox, HBoxLayout, LineEdit, VBoxLayout, try_load
from vspreview.models import GeneralModel
from vspreview.plugins import AbstractPlugin

__all__ = [
    'CompSettings'
]


class CompSettings(AbstractSettingsWidget):
    __slots__ = ('delete_cache_checkbox', 'frame_type_checkbox', 'login_browser_id_edit', 'login_session_edit', 'tmdb_apikey_edit')

    DEFAULT_COLLECTION_NAME = 'Unknown'

    def __init__(self, plugin: AbstractPlugin) -> None:
        super().__init__()

        self.plugin = plugin

    def setup_ui(self) -> None:
        super().setup_ui()

        self.collection_name_template_edit = LineEdit('Collection Name Template')

        self.delete_cache_checkbox = CheckBox('Delete images cache after upload')

        self.frame_type_checkbox = CheckBox('Include frametype in image name')

        self.default_public_checkbox = CheckBox('Default Public Flag')
        self.default_nsfw_checkbox = CheckBox('Default NSFW Flag')

        self.login_browser_id_edit = LineEdit('Browser ID')
        self.login_session_edit = LineEdit('Session ID')

        self.compression_combobox = ComboBox[str](model=GeneralModel[str](['fast', 'slow', 'uncompressed']))

        self.frame_ntype_combobox = ComboBox[str](model=GeneralModel[str](['timeline', 'frame', 'time', 'both']))
        self.frame_ntype_combobox.setCurrentValue('both')

        self.tmdb_apikey_edit = LineEdit('API Key')

        label = QLabel(
            'To get this info: Open Dev console in browser, go to network tab, upload a comparison,'
            'click request called "comparison" Copy browserId from payload, copy session token from '
            'SLP-SESSION cookie from cookies'
        )
        label.setMaximumHeight(50)
        label.setMinimumWidth(400)
        label.setWordWrap(True)

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
                    QLabel("Compression Type:"),
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
                HBoxLayout([QLabel("TMDB API Key"), self.tmdb_apikey_edit]),
                label,
                HBoxLayout([QLabel("Browser ID"), self.login_browser_id_edit]),
                HBoxLayout([QLabel("Session ID"), self.login_session_edit]),
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
            'browser_id': self.browser_id,
            'session_id': self.session_id,
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
        try_load(state, 'browser_id', str, self.login_browser_id_edit.setText)
        try_load(state, 'session_id', str, self.login_session_edit.setText)
        try_load(state, 'tmdb_apikey', str, self.tmdb_apikey_edit.setText)
        try_load(state, 'compression', int, self.compression_combobox.setCurrentIndex)
        try_load(state, 'frame_ntype', str, self.frame_ntype_combobox.setCurrentValue)
