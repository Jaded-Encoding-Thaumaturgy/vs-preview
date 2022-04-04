from __future__ import annotations

import logging
from typing import Any, Mapping
from psutil import cpu_count, Process

from PyQt5.QtWidgets import QLabel

from ..core.custom import TimeEdit
from ..core import Time, AbstractToolbarSettings, try_load, VBoxLayout, HBoxLayout, SpinBox, CheckBox


class MainSettings(AbstractToolbarSettings):
    __slots__ = (
        'autosave_control', 'base_ppi_spinbox', 'dark_theme_checkbox',
        'opengl_rendering_checkbox', 'output_index_spinbox',
        'png_compressing_spinbox', 'statusbar_timeout_control',
        'timeline_notches_margin_spinbox', 'usable_cpus_spinbox'
    )

    INSTANT_FRAME_UPDATE = False
    SYNC_OUTPUTS = True
    LOG_LEVEL = logging.INFO

    def setup_ui(self) -> None:
        super().setup_ui()

        self.autosave_control = TimeEdit(self)

        self.base_ppi_spinbox = SpinBox(self, 1, 999)

        self.dark_theme_checkbox = CheckBox('Dark theme', self)

        self.opengl_rendering_checkbox = CheckBox('OpenGL rendering', self)

        self.force_old_storages_removal_checkbox = CheckBox('Remove old storages', self)

        self.output_index_spinbox = SpinBox(self, 0, 65535)

        self.png_compressing_spinbox = SpinBox(self, 0, 100)

        self.statusbar_timeout_control = TimeEdit(self)

        self.timeline_notches_margin_spinbox = SpinBox(self, 1, 9999, '%')

        self.usable_cpus_spinbox = SpinBox(self, 1, self.get_usable_cpus_count())

        HBoxLayout(self.vlayout, [QLabel('Autosave interval (0 - disable)'), self.autosave_control])

        HBoxLayout(self.vlayout, [QLabel('Base PPI'), self.base_ppi_spinbox])

        HBoxLayout(self.vlayout, [
            VBoxLayout([
                self.dark_theme_checkbox,
                self.opengl_rendering_checkbox
            ]),
            VBoxLayout([
                self.force_old_storages_removal_checkbox
            ])
        ])

        HBoxLayout(self.vlayout, [QLabel('Default output index'), self.output_index_spinbox])

        HBoxLayout(self.vlayout, [QLabel('PNG compression level (0 - max)'), self.png_compressing_spinbox])

        HBoxLayout(self.vlayout, [QLabel('Status bar message timeout'), self.statusbar_timeout_control])

        HBoxLayout(self.vlayout, [
            QLabel('Timeline label notches margin', self), self.timeline_notches_margin_spinbox
        ])

        HBoxLayout(self.vlayout, [QLabel('Usable CPUs count'), self.usable_cpus_spinbox])

    def set_defaults(self) -> None:
        self.autosave_control.setValue(Time(seconds=30))
        self.base_ppi_spinbox.setValue(96)
        self.dark_theme_checkbox.setChecked(True)
        self.opengl_rendering_checkbox.setChecked(False)
        self.output_index_spinbox.setValue(0)
        self.png_compressing_spinbox.setValue(0)
        self.statusbar_timeout_control.setValue(Time(seconds=2.5))
        self.timeline_notches_margin_spinbox.setValue(20)
        self.force_old_storages_removal_checkbox.setChecked(False)
        self.usable_cpus_spinbox.setValue(self.get_usable_cpus_count())

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
    def force_old_storages_removal(self) -> int:
        return self.force_old_storages_removal_checkbox.isChecked()

    @property
    def usable_cpus_count(self) -> int:
        return self.usable_cpus_spinbox.value()

    @staticmethod
    def get_usable_cpus_count() -> int:
        try:
            return len(Process().cpu_affinity())
        except AttributeError:
            return cpu_count()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'autosave_interval': self.autosave_interval,
            'base_ppi': self.base_ppi,
            'dark_theme': self.dark_theme_enabled,
            'opengl_rendering': self.opengl_rendering_enabled,
            'output_index': self.output_index,
            'png_compression': self.png_compression_level,
            'statusbar_message_timeout': self.statusbar_message_timeout,
            'timeline_label_notches_margin': self.timeline_label_notches_margin,
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
