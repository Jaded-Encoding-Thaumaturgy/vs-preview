from __future__ import annotations

import sys
from typing import Any, Mapping

from PyQt5.QtWidgets import QLabel, QHBoxLayout, QCheckBox, QSpinBox

from ..widgets import TimeEdit
from ..core import Time, AbstractToolbarSettings, try_load


class MainSettings(AbstractToolbarSettings):
    __slots__ = (
        'autosave_control', 'base_ppi_spinbox', 'dark_theme_checkbox',
        'opengl_rendering_checkbox', 'output_index_spinbox',
        'png_compressing_spinbox', 'statusbar_timeout_control',
        'timeline_notches_margin_spinbox', 'color_management_checkbox'
    )

    def setup_ui(self) -> None:
        super().setup_ui()

        autosave_layout = QHBoxLayout()
        autosave_layout.setObjectName('MainSettings.setup_ui.autosave_layout')
        self.vlayout.addLayout(autosave_layout)

        autosave_label = QLabel(self)
        autosave_label.setObjectName('MainSettings.setup_ui.autosave_label')
        autosave_label.setText('Autosave interval (0 - disable)')
        autosave_layout.addWidget(autosave_label)

        self.autosave_control = TimeEdit(self)
        autosave_layout.addWidget(self.autosave_control)

        base_ppi_layout = QHBoxLayout()
        base_ppi_layout.setObjectName('MainSettings.setup_ui.base_ppi_layout')
        self.vlayout.addLayout(base_ppi_layout)

        base_ppi_label = QLabel(self)
        base_ppi_label.setObjectName('MainSettings.setup_ui.base_ppi_label')
        base_ppi_label.setText('Base PPI')
        base_ppi_layout.addWidget(base_ppi_label)

        self.base_ppi_spinbox = QSpinBox(self)
        self.base_ppi_spinbox.setMinimum(1)
        self.base_ppi_spinbox.setMaximum(9999)
        self.base_ppi_spinbox.setEnabled(False)
        base_ppi_layout.addWidget(self.base_ppi_spinbox)

        self.dark_theme_checkbox = QCheckBox(self)
        self.dark_theme_checkbox.setText('Dark theme')
        self.dark_theme_checkbox.setEnabled(False)
        self.vlayout.addWidget(self.dark_theme_checkbox)

        self.opengl_rendering_checkbox = QCheckBox(self)
        self.opengl_rendering_checkbox.setText('OpenGL rendering')
        self.opengl_rendering_checkbox.setEnabled(False)
        self.vlayout.addWidget(self.opengl_rendering_checkbox)

        output_index_layout = QHBoxLayout()
        output_index_layout.setObjectName(
            'MainSettings.setup_ui.output_index_layout'
        )
        self.vlayout.addLayout(output_index_layout)

        output_index_label = QLabel(self)
        output_index_label.setObjectName(
            'MainSettings.setup_ui.output_index_label'
        )
        output_index_label.setText('Default output index')
        output_index_layout.addWidget(output_index_label)

        self.output_index_spinbox = QSpinBox(self)
        self.output_index_spinbox.setMinimum(0)
        self.output_index_spinbox.setMaximum(65535)
        output_index_layout.addWidget(self.output_index_spinbox)

        png_compression_layout = QHBoxLayout()
        png_compression_layout.setObjectName(
            'MainSettings.setup_ui.png_compression_layout'
        )
        self.vlayout.addLayout(png_compression_layout)

        png_compression_label = QLabel(self)
        png_compression_label.setObjectName(
            'MainSettings.setup_ui.png_compression_label'
        )
        png_compression_label.setText('PNG compression level (0 - max)')
        png_compression_layout.addWidget(png_compression_label)

        self.png_compressing_spinbox = QSpinBox(self)
        self.png_compressing_spinbox.setMinimum(0)
        self.png_compressing_spinbox.setMaximum(100)
        png_compression_layout.addWidget(self.png_compressing_spinbox)

        statusbar_timeout_layout = QHBoxLayout()
        statusbar_timeout_layout.setObjectName(
            'MainSettings.setup_ui.statusbar_timeout_layout'
        )
        self.vlayout.addLayout(statusbar_timeout_layout)

        statusbar_timeout_label = QLabel(self)
        statusbar_timeout_label.setObjectName(
            'MainSettings.setup_ui.statusbar_timeout_label'
        )
        statusbar_timeout_label.setText('Status bar message timeout')
        statusbar_timeout_layout.addWidget(statusbar_timeout_label)

        self.statusbar_timeout_control = TimeEdit(self)
        statusbar_timeout_layout.addWidget(self.statusbar_timeout_control)

        timeline_notches_margin_layout = QHBoxLayout()
        timeline_notches_margin_layout.setObjectName(
            'MainSettings.setup_ui.timeline_notches_margin_layout'
        )
        self.vlayout.addLayout(timeline_notches_margin_layout)

        timeline_notches_margin_label = QLabel(self)
        timeline_notches_margin_label.setObjectName(
            'MainSettings.setup_ui.timeline_notches_margin_label'
        )
        timeline_notches_margin_label.setText('Timeline label notches margin')
        timeline_notches_margin_layout.addWidget(timeline_notches_margin_label)

        self.timeline_notches_margin_spinbox = QSpinBox(self)
        self.timeline_notches_margin_spinbox.setMinimum(1)
        self.timeline_notches_margin_spinbox.setMaximum(9999)
        self.timeline_notches_margin_spinbox.setSuffix('%')
        timeline_notches_margin_layout.addWidget(
            self.timeline_notches_margin_spinbox
        )

        self.color_management_checkbox = QCheckBox(self)
        self.color_management_checkbox.setText('Color management')

        if sys.platform == 'win32':
            self.vlayout.addWidget(self.color_management_checkbox)

    def set_defaults(self) -> None:
        self.autosave_control.setValue(Time(seconds=30))
        self.base_ppi_spinbox.setValue(96)
        self.dark_theme_checkbox.setChecked(True)
        self.opengl_rendering_checkbox.setChecked(False)
        self.output_index_spinbox.setValue(0)
        self.png_compressing_spinbox.setValue(0)
        self.statusbar_timeout_control.setValue(Time(seconds=2.5))
        self.timeline_notches_margin_spinbox.setValue(20)
        self.color_management_checkbox.setChecked(False)

    @property
    def autosave_interval(self) -> Time:
        return self.autosave_control.value()

    @property
    def base_ppi(self) -> int:
        return self.base_ppi_spinbox.value()

    @property
    def dark_theme_enabled(self) -> bool:
        return self.dark_theme_checkbox.isChecked()

    @property
    def opengl_rendering_enabled(self) -> bool:
        return self.opengl_rendering_checkbox.isChecked()

    @property
    def output_index(self) -> int:
        return self.output_index_spinbox.value()

    @property
    def png_compression_level(self) -> int:
        return self.png_compressing_spinbox.value()

    @property
    def statusbar_message_timeout(self) -> Time:
        return self.statusbar_timeout_control.value()

    @property
    def timeline_label_notches_margin(self) -> int:
        return self.timeline_notches_margin_spinbox.value()

    @property
    def color_management_enabled(self) -> bool:
        return self.color_management_checkbox.isChecked()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'autosave_interval': self.autosave_interval,
            'base_ppi': self.base_ppi,
            'dark_theme': self.dark_theme_enabled,
            'opengl_rendering': self.opengl_rendering_enabled,
            'output_index': self.output_index,
            'png_compression': self.png_compression_level,
            'statusbar_message_timeout': self.statusbar_message_timeout,
            'timeline_label_notches_margin':
            self.timeline_label_notches_margin,
            'color_management': self.color_management_enabled,
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'autosave_interval', Time, self.autosave_control.setValue)
        try_load(state, 'base_ppi', int, self.base_ppi_spinbox.setValue)
        try_load(state, 'dark_theme', bool, self.dark_theme_checkbox.setChecked)
        try_load(state, 'opengl_rendering', bool, self.opengl_rendering_checkbox.setChecked)
        try_load(state, 'output_index', int, self.output_index_spinbox.setValue)
        try_load(state, 'png_compression', int, self.png_compressing_spinbox.setValue)
        try_load(state, 'statusbar_message_timeout', Time, self.statusbar_timeout_control.setValue)
        try_load(state, 'timeline_label_notches_margin', int, self.timeline_notches_margin_spinbox.setValue)
        try_load(state, 'color_management', bool, self.color_management_checkbox.setChecked)
