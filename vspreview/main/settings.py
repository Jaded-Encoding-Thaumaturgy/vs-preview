from __future__ import annotations

import logging
import sys
from functools import partial
from multiprocessing import cpu_count
from typing import Any, Mapping

from PyQt6.QtCore import Qt, QKeyCombination
from PyQt6.QtGui import QShortcut
from PyQt6.QtWidgets import QComboBox, QLabel

from ..core import AbstractToolbarSettings, CheckBox, HBoxLayout, PushButton, SpinBox, Time, VBoxLayout, try_load
from ..core.bases import QYAMLObjectSingleton
from ..core.custom import ComboBox, TimeEdit
from ..models import GeneralModel
from ..utils import main_window


class MainSettings(AbstractToolbarSettings):
    __slots__ = (
        'autosave_control', 'base_ppi_spinbox', 'dark_theme_checkbox',
        'opengl_rendering_checkbox', 'output_index_spinbox',
        'png_compressing_spinbox', 'statusbar_timeout_control',
        'timeline_notches_margin_spinbox', 'usable_cpus_spinbox',
        'zoom_levels_combobox', 'zoom_levels_lineedit', 'zoom_level_default_combobox',
        'azerty_keyboard_checkbox', 'dragnavigator_timeout_spinbox', 'color_management_checkbox'
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

        self.azerty_keyboard_checkbox = CheckBox('AZERTY Keyboard', self)

        self.zoom_levels_combobox = ComboBox[int](editable=True, insertPolicy=QComboBox.InsertPolicy.NoInsert)
        self.zoom_levels_lineedit = self.zoom_levels_combobox.lineEdit()

        self.zoom_levels_lineedit.returnPressed.connect(self.zoom_levels_combobox_on_add)
        QShortcut(
            QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Delete).toCombined(), self.zoom_levels_combobox,
            activated=partial(self.zoom_levels_combobox_on_remove, True)
        )

        self.zoom_level_default_combobox = ComboBox[int]()

        self.dragnavigator_timeout_spinbox = SpinBox(self, 0, 1000 * 60 * 5)

        self.color_management_checkbox = CheckBox('Color management', self)

        HBoxLayout(self.vlayout, [QLabel('Autosave interval (0 - disable)'), self.autosave_control])

        HBoxLayout(self.vlayout, [QLabel('Base PPI'), self.base_ppi_spinbox])

        HBoxLayout(self.vlayout, [
            VBoxLayout([self.dark_theme_checkbox, self.opengl_rendering_checkbox]),
            VBoxLayout([self.force_old_storages_removal_checkbox, self.azerty_keyboard_checkbox])
        ])

        HBoxLayout(self.vlayout, [QLabel('Default output index'), self.output_index_spinbox])

        HBoxLayout(self.vlayout, [QLabel('PNG compression level (0 for max)'), self.png_compressing_spinbox])

        HBoxLayout(self.vlayout, [QLabel('Status bar message timeout'), self.statusbar_timeout_control])

        HBoxLayout(self.vlayout, [
            QLabel('Timeline label notches margin', self), self.timeline_notches_margin_spinbox
        ])

        HBoxLayout(self.vlayout, [QLabel('Usable CPUs count'), self.usable_cpus_spinbox])

        HBoxLayout(self.vlayout, [
            VBoxLayout([
                QLabel('Zoom Levels'),
                HBoxLayout([
                    self.zoom_levels_combobox,
                    PushButton('❌', clicked=self.zoom_levels_combobox_on_remove, maximumWidth=18),
                    PushButton('✔️', clicked=self.zoom_levels_combobox_on_add, maximumWidth=18),
                ])
            ]),
            VBoxLayout([QLabel('Default Zoom Level'), self.zoom_level_default_combobox])
        ])

        HBoxLayout(self.vlayout, [QLabel('Drag Navigator Timeout (ms)'), self.dragnavigator_timeout_spinbox])

        if sys.platform == 'win32':
            HBoxLayout(self.vlayout, [self.color_management_checkbox])

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
        self.azerty_keyboard_checkbox.setChecked(False)
        self.usable_cpus_spinbox.setValue(self.get_usable_cpus_count())
        self.dragnavigator_timeout_spinbox.setValue(250)

        self.zoom_levels = [
            25, 50, 68, 75, 85, 100, 150, 200, 400, 600, 800, 1000, 1200, 1400, 1600, 2000, 3200
        ]
        self.zoom_level_default_combobox.setCurrentIndex(5)
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
    def force_old_storages_removal(self) -> int:
        return self.force_old_storages_removal_checkbox.isChecked()

    @property
    def azerty_keybinds(self) -> int:
        return self.azerty_keyboard_checkbox.isChecked()

    @property
    def usable_cpus_count(self) -> int:
        return self.usable_cpus_spinbox.value()

    @property
    def zoom_levels(self) -> list[float]:
        return [
            int(self.zoom_levels_combobox.itemText(i)) / 100
            for i in range(self.zoom_levels_combobox.count())
        ]

    @zoom_levels.setter
    def zoom_levels(self, new_levels: list[int]) -> None:
        new_levels = sorted(set(map(int, new_levels)))

        if len(new_levels) < 3:
            return

        old_values = [int(x * 100) for x in self.zoom_levels]

        self.zoom_levels_combobox.clear()
        self.zoom_levels_combobox.addItems(map(str, new_levels))

        old_default = self.zoom_level_default_combobox.currentData()

        self.zoom_level_default_combobox.setModel(GeneralModel[int](new_levels))

        if old_default:
            try:
                old_default_idx = new_levels.index(int(old_default))
            except ValueError:
                old_default_idx = old_values.index(int(old_default))
                old_default_idx = min(max(old_default_idx - 1, 0), old_default_idx + 1, len(new_levels) - 1)
            self.zoom_level_default_combobox.setCurrentIndex(old_default_idx)

        if hasattr((main := main_window()), 'toolbars'):
            main_zoom_comb = main.toolbars.main.zoom_combobox
            old_index = main_zoom_comb.currentIndex()
            main_zoom_comb.setModel(GeneralModel[float](self.zoom_levels))
            main_zoom_comb.setCurrentIndex(min(max(old_index, 0), len(new_levels) - 1))

        self.zoom_levels_lineedit.clear()

    @property
    def zoom_default_index(self) -> int:
        return self.zoom_level_default_combobox.currentIndex()

    @staticmethod
    def get_usable_cpus_count() -> int:
        from os import getpid
        try:
            from win32.win32api import OpenProcess  # type: ignore
            from win32.win32process import GetProcessAffinityMask  # type: ignore
            from win32con import PROCESS_QUERY_LIMITED_INFORMATION  # type: ignore
            proc_mask, _ = GetProcessAffinityMask(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, getpid()))
            cpus = [i for i in range(64) if (1 << i) & proc_mask]
            return len(cpus)
        except Exception:
            try:
                from os import sched_getaffinity
                return len(sched_getaffinity(getpid()))
            except Exception:
                return cpu_count()

    @property
    def dragnavigator_timeout(self) -> int:
        return self.dragnavigator_timeout_spinbox.value()

    def zoom_levels_combobox_on_add(self) -> None:
        try:
            new_value = int(self.zoom_levels_lineedit.text())
        except ValueError:
            return

        if not new_value:
            return

        zoom_levels = [x * 100 for x in self.zoom_levels]

        if new_value in zoom_levels:
            return

        self.zoom_levels = [*zoom_levels, new_value]

    def zoom_levels_combobox_on_remove(self, checkFocus: bool = False) -> None:
        if checkFocus and not self.zoom_levels_lineedit.hasFocus():
            return

        try:
            old_value = int(self.zoom_levels_lineedit.text())
        except ValueError:
            return

        if not old_value:
            return

        zoom_levels = [x * 100 for x in self.zoom_levels]

        if old_value not in zoom_levels:
            return

        self.zoom_levels = [x for x in zoom_levels if round(x) != round(old_value)]

    @property
    def color_management(self) -> bool:
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
            'timeline_label_notches_margin': self.timeline_label_notches_margin,
            'force_old_storages_removal': self.force_old_storages_removal,
            'zoom_levels': sorted([int(x * 100) for x in self.zoom_levels]),
            'zoom_default_index': self.zoom_default_index,
            'dragnavigator_timeout': self.dragnavigator_timeout,
            'color_management': self.color_management
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
        try_load(state, 'force_old_storages_removal', bool, self.force_old_storages_removal_checkbox.setChecked)
        try_load(state, 'zoom_levels', list, self)
        try_load(state, 'zoom_default_index', int, self.zoom_level_default_combobox.setCurrentIndex)
        try_load(state, 'dragnavigator_timeout', int, self.dragnavigator_timeout_spinbox.setValue)
        try_load(state, 'color_management', bool, self.color_management_checkbox.setChecked)


class WindowSettings(QYAMLObjectSingleton):
    __slots__ = (
        'timeline_mode', 'window_geometry', 'window_state'
    )

    def __init__(self, timeline_mode: str, window_geometry: bytes, window_state: bytes) -> None:
        self.timeline_mode = timeline_mode
        self.window_geometry = window_geometry
        self.window_state = window_state

        super().__init__()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'timeline_mode': self.timeline_mode,
            'window_geometry': self.window_geometry,
            'window_state': self.window_state
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'timeline_mode', str, self.__setattr__)
        try_load(state, 'window_geometry', bytes, self.__setattr__)
        try_load(state, 'window_state', bytes, self.__setattr__)
