from __future__ import annotations

import logging
import requests
from typing import Any

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QToolTip

from vspreview.core import AbstractSettingsWidget, CheckBox, ComboBox, HBoxLayout, LineEdit, VBoxLayout, try_load
from vspreview.models import GeneralModel
from vspreview.plugins import AbstractPlugin

__all__ = [
    'CompSettings'
]


# Placeholders and their descriptions for collection name templates
COLLECTION_NAME_PLACEHOLDERS: dict[str, str] = {
    '{tmdb_title}': 'The official title of the movie or TV show as listed on TMDB',
    '{video_nodes}': 'The total number of video nodes being compared',
    '{tmdb_year}': 'The year the movie was released or the TV show first aired, according to TMDB'
}

# Example TMDB ID for demonstration purposes
EXAMPLE_TMDB_ID: int = 31911

# Example TMDB data structure for demonstration purposes
EXAMPLE_TMDB_DATA = {
    'name': 'Fullmetal Alchemist: Brotherhood',
    'first_air_date': '2009-04-05'
}


class CompSettings(AbstractSettingsWidget):
    """Settings widget for the Slowpics Comparison plugin."""

    __slots__ = (
        'delete_cache_checkbox', 'frame_type_checkbox',
        'login_browser_id_edit', 'login_session_edit',
        'tmdb_apikey_edit'
    )

    DEFAULT_COLLECTION_NAME = 'Unknown'

    def __init__(self, plugin: AbstractPlugin) -> None:
        """Initialize the CompSettings widget."""

        super().__init__()

        self.plugin = plugin
        self._cached_tmdb_data = None

    def setup_ui(self) -> None:
        """Set up the user interface for the settings widget."""

        super().setup_ui()

        self._create_collection_name_section()

        self.vlayout.addSpacing(20)

        self._create_upload_settings_section()
        self._create_frame_position_section()
        self._create_default_flags_section()

        self.vlayout.addSpacing(20)

        self._create_login_section()

    def _create_collection_name_section(self) -> None:
        """Create the collection name settings section."""

        self.collection_name_template_edit = LineEdit('Template')

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['Placeholder', 'Description'])
        table.verticalHeader().setVisible(False)

        for placeholder, description in COLLECTION_NAME_PLACEHOLDERS.items():
            table.insertRow(table.rowCount())
            table.setItem(table.rowCount() - 1, 0, QTableWidgetItem(placeholder))
            table.setItem(table.rowCount() - 1, 1, QTableWidgetItem(description))

        table.resizeColumnToContents(0)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.example_output = QLabel()
        self.example_output.setStyleSheet('font-weight: bold;')

        self.collection_name_template_edit.textChanged.connect(self.update_example)

        VBoxLayout(self.vlayout, [
            QLabel('Collection Name Settings'),
            self.collection_name_template_edit,
            QLabel('Available placeholders for template:'),
            table,
            HBoxLayout([
                QLabel('Example Template Output:'),
                self.collection_name_template_edit,
                self.example_output
            ])
        ])

    def update_example(self, text: str) -> None:
        """Update the example output based on the template."""

        if not hasattr(self, '_cached_tmdb_data') or self._cached_tmdb_data is None:
            self._fetch_example_tmdb_data()

        if not self._cached_tmdb_data:
            self.example_output.setText("Error: Unable to fetch TMDB data")
            return

        replacements = {
            '{tmdb_title}': self._cached_tmdb_data.get('name', 'Unknown'),
            '{tmdb_year}': self._cached_tmdb_data.get('first_air_date', '1970')[:4],
            '{video_nodes}': '2'
        }

        example = text

        for placeholder, value in replacements.items():
            example = example.replace(placeholder, value)

        self.example_output.setText(example)

    def _fetch_example_tmdb_data(self):
        """Fetch TMDB data and cache it."""

        tmdb_api_key = self.tmdb_apikey_edit.text()
        url = f"https://api.themoviedb.org/3/tv/{EXAMPLE_TMDB_ID}?api_key={tmdb_api_key}"

        try:
            response = requests.get(url)

            response.raise_for_status()

            self._cached_tmdb_data = response.json()
        except Exception as e:
            error_message = f"Error fetching or parsing TMDB data: {str(e).replace(tmdb_api_key, '[TMDB API key]')}"

            if "Invalid API key" in str(e):
                error_message += "\nPlease check if your TMDB API key is correct."

            logging.debug(error_message)

            self.example_output.setText(error_message)
            self._cached_tmdb_data = EXAMPLE_TMDB_DATA

    def _create_upload_settings_section(self) -> None:
        """Create the upload settings section."""

        self.delete_cache_checkbox = CheckBox('Delete images cache after upload')
        self.frame_type_checkbox = CheckBox('Include frametype in image name')
        self.compression_combobox = ComboBox[str](model=GeneralModel[str](['fast', 'slow', 'uncompressed']))

        VBoxLayout(
            self.vlayout, [
                QLabel('Upload Settings'),
                self.delete_cache_checkbox,
                self.frame_type_checkbox,
                HBoxLayout([
                    QLabel("Compression Type:"),
                    self.compression_combobox
                ])
            ]
        )

    def _create_frame_position_section(self) -> None:
        """Create the frame position settings section."""

        self.frame_ntype_combobox = ComboBox[str](model=GeneralModel[str]([
            'timeline', 'frame', 'time', 'both'
        ]))

        VBoxLayout(self.vlayout, [
            HBoxLayout([
                QLabel('Include frame position type:'),
                self.frame_ntype_combobox
            ])
        ])

        self.frame_ntype_combobox.setCurrentValue('both')

    def _create_default_flags_section(self) -> None:
        """Create the default flags settings section."""

        self.default_public_checkbox = CheckBox('Make comparison public by default')
        self.default_nsfw_checkbox = CheckBox('Mark comparison as NSFW by default')

        VBoxLayout(self.vlayout, [
            VBoxLayout([
                self.default_public_checkbox,
                self.default_nsfw_checkbox
            ])
        ])

    def _create_login_section(self) -> None:
        """Create the login settings section."""

        self.tmdb_apikey_edit = LineEdit('API Key', echoMode=QLineEdit.EchoMode.Password)
        self.tmdb_apikey_edit.textChanged.connect(self._on_tmdb_apikey_changed)
        self.login_browser_id_edit = LineEdit('Browser ID', echoMode=QLineEdit.EchoMode.Password)
        self.login_session_edit = LineEdit('Session ID', echoMode=QLineEdit.EchoMode.Password)

        login_info_tooltip = (
            'To get this info:\n\n'
            '1. Go to the slow.pics website\n'
            '2. Open the Dev console in your browser\n'
            '3. Go to the Network tab\n'
            '4. Upload a comparison\n'
            '5. Click the request named "comparison"\n'
            '6. In the Request Payload, find and copy the "browserId" value\n'
            '7. In the Cookies section, find "SLP-SESSION" and copy its value\n'
            '8. Paste the copied Browser ID and Session ID into their respective fields'
        )

        login_info_button = QPushButton('?')
        login_info_button.setMinimumWidth(20)
        login_info_button.setMaximumHeight(20)
        login_info_button.clicked.connect(lambda: QToolTip.showText(
            login_info_button.mapToGlobal(QPoint(0, 0)),
            login_info_tooltip,
            login_info_button
        ))

        VBoxLayout(
            self.vlayout, [
                QLabel('Login Settings'),
                HBoxLayout([QLabel("TMDB API Key"), self.tmdb_apikey_edit]),
                HBoxLayout([
                    QLabel("Browser ID"),
                    self.login_browser_id_edit,
                    login_info_button
                ]),
                HBoxLayout([QLabel("Session ID"), self.login_session_edit]),
            ]
        )

    def _on_tmdb_apikey_changed(self) -> None:
        """Reset cached TMDB data when API key changes."""

        self.update_example(self.collection_name_template_edit.text())

    def set_defaults(self) -> None:
        """Set default values for the settings."""

        self.delete_cache_checkbox.setChecked(True)
        self.frame_type_checkbox.setChecked(True)
        # https://github.com/Radarr/Radarr/blob/29ba6fe5563e737f0f87919e48f556e39284e6bb/src/NzbDrone.Common/Cloud/RadarrCloudRequestBuilder.cs#L31
        self.tmdb_apikey_edit.setText(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIxYTczNzMzMDE5NjFkMDNmOTdmODUzYTg3NmRkMTIxMiIsInN1YiI6IjU4NjRmNTkyYzNhMzY4MGFiNjAxNzUzNCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.gh1BwogCCKOda6xj9FRMgAAj_RYKMMPC3oNlcBtlmwk'  # noqa
        )

    @property
    def delete_cache_enabled(self) -> bool:
        """Get the state of the delete cache checkbox."""

        return self.delete_cache_checkbox.isChecked()

    @property
    def frame_type_enabled(self) -> bool:
        """Get the state of the frame type checkbox."""

        return self.frame_type_checkbox.isChecked()

    @property
    def browser_id(self) -> str:
        """Get the browser ID."""

        return self.login_browser_id_edit.text()

    @property
    def session_id(self) -> str:
        """Get the session ID."""

        return self.login_session_edit.text()

    @property
    def tmdb_apikey(self) -> str:
        """Get the TMDB API key."""

        return self.tmdb_apikey_edit.text()

    @property
    def compression(self) -> int:
        """Get the selected compression index."""

        return self.compression_combobox.currentIndex()

    @property
    def frame_ntype(self) -> str:
        """Get the selected frame position type."""

        return self.frame_ntype_combobox.currentValue()

    @property
    def default_public(self) -> bool:
        """Get the state of the default public checkbox."""

        return self.default_public_checkbox.isChecked()

    @property
    def default_nsfw(self) -> bool:
        """Get the state of the default NSFW checkbox."""

        return self.default_nsfw_checkbox.isChecked()

    @property
    def collection_name_template(self) -> str:
        """Get the collection name template."""

        return self.collection_name_template_edit.text()

    def __getstate__(self) -> dict[str, Any]:
        """Get the state of the settings widget."""

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
        """Set the state of the settings widget."""

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
