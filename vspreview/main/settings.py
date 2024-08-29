from __future__ import annotations

import sys
from functools import partial
from multiprocessing import cpu_count
from typing import Any, cast

from PyQt6.QtCore import QKeyCombination, Qt
from PyQt6.QtGui import QShortcut
from PyQt6.QtWidgets import QComboBox, QLabel

from ..core import (
    AbstractToolbarSettings, CheckBox, ComboBox, HBoxLayout, PushButton, QYAMLObjectSingleton, SpinBox, Time, TimeEdit,
    VBoxLayout, main_window, try_load
)
from ..models import GeneralModel

__all__ = [
    'MainSettings',
    'WindowSettings'
]


class MainSettings(AbstractToolbarSettings):
    __slots__ = (
        'autosave_control', 'base_ppi_spinbox', 'dark_theme_checkbox',
        'opengl_rendering_checkbox', 'output_index_spinbox',
        'png_compressing_spinbox', 'statusbar_timeout_control',
        'timeline_notches_margin_spinbox', 'usable_cpus_spinbox',
        'zoom_levels_combobox', 'zoom_levels_lineedit', 'zoom_level_default_combobox',
        'dragnavigator_timeout_spinbox', 'dragtimeline_timeout_spinbox',
        'color_management_checkbox', 'plugins_save_position_combobox'
    )

    INSTANT_FRAME_UPDATE = False
    SYNC_OUTPUTS = True
    STORAGE_BACKUPS_COUNT = 2

    def setup_ui(self) -> None:
        super().setup_ui()

        self.autosave_control = TimeEdit(self)

        self.base_ppi_spinbox = SpinBox(
            self, 1, 999, valueChanged=lambda: hasattr(main_window(), 'timeline') and main_window().timeline.set_sizes()
        )

        self.dark_theme_checkbox = CheckBox('Dark theme', self, clicked=lambda: main_window().apply_stylesheet())

        self.opengl_rendering_checkbox = CheckBox('OpenGL rendering', self)

        self.force_old_storages_removal_checkbox = CheckBox('Remove old storages', self)

        self.output_index_spinbox = SpinBox(self, 0, 65535)

        self.png_compressing_spinbox = SpinBox(self, 0, 100)

        self.statusbar_timeout_control = TimeEdit(self)

        self.timeline_notches_margin_spinbox = SpinBox(self, 1, 9999, '%')

        self.usable_cpus_spinbox = SpinBox(self, 1, self.get_usable_cpus_count())

        self.zoom_levels_combobox = ComboBox[int](editable=True, insertPolicy=QComboBox.InsertPolicy.NoInsert)
        self.zoom_levels_lineedit = self.zoom_levels_combobox.lineEdit()

        self.zoom_levels_lineedit.returnPressed.connect(self.zoom_levels_combobox_on_add)
        QShortcut(  # type: ignore
            QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Delete).toCombined(), self.zoom_levels_combobox,
            activated=partial(self.zoom_levels_combobox_on_remove, True)
        )

        self.zoom_level_default_combobox = ComboBox[int]()

        self.dragnavigator_timeout_spinbox = SpinBox(self, 0, 1000 * 60 * 5)
        self.dragtimeline_timeout_spinbox = SpinBox(self, 0, 500)

        self.primaries_combobox = ComboBox[str](
            model=GeneralModel[str]([
                'sRGB', 'DCI-P3'
            ], False)
        )

        self.color_management_checkbox = CheckBox('Color management', self)

        self.plugins_save_position_combobox = ComboBox[str](model=GeneralModel[str](['no', 'global', 'local']))

        HBoxLayout(self.vlayout, [QLabel('Autosave interval (0 - disable)'), self.autosave_control])

        HBoxLayout(self.vlayout, [QLabel('Base PPI'), self.base_ppi_spinbox])

        HBoxLayout(self.vlayout, [self.dark_theme_checkbox, self.force_old_storages_removal_checkbox])
        HBoxLayout(self.vlayout, [self.opengl_rendering_checkbox])

        HBoxLayout(self.vlayout, [QLabel('Default output index'), self.output_index_spinbox])

        HBoxLayout(self.vlayout, [QLabel('PNG compression level (0 (max) - 100 (min))'), self.png_compressing_spinbox])

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

        HBoxLayout(self.vlayout, [QLabel('Drag Timeline Timeout (ms)'), self.dragtimeline_timeout_spinbox])

        HBoxLayout(self.vlayout, [QLabel('Output Primaries'), self.primaries_combobox])

        HBoxLayout(self.vlayout, [QLabel('Save Plugins Bar Position'), self.plugins_save_position_combobox])

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
        self.usable_cpus_spinbox.setValue(self.get_usable_cpus_count())
        self.dragnavigator_timeout_spinbox.setValue(250)
        self.dragtimeline_timeout_spinbox.setValue(40)

        self.zoom_levels = [50 * (2 ** i) for i in range(8)]
        self.zoom_level_default_combobox.setCurrentIndex(1)
        self.color_management_checkbox.setChecked(self.color_management_checkbox.isVisible())
        self.plugins_save_position_combobox.setCurrentIndex(2)

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
        return main_window().force_storage or self.force_old_storages_removal_checkbox.isChecked()

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

        if hasattr((main := main_window()), 'graphics_view'):
            main_zoom_comb = main.graphics_view.zoom_combobox
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
                from os import sched_getaffinity  # type: ignore
                return len(sched_getaffinity(getpid()))
            except Exception:
                return cpu_count()

    @property
    def dragnavigator_timeout(self) -> int:
        return self.dragnavigator_timeout_spinbox.value()

    @property
    def dragtimeline_timeout(self) -> int:
        return self.dragtimeline_timeout_spinbox.value()

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
    def output_primaries_zimg(self) -> int:
        from vstools.enums.color import Primaries
        return Primaries([1, 12][self.primaries_combobox.currentIndex()])

    @property
    def plugins_bar_save_behaviour(self) -> int:
        return self.plugins_save_position_combobox.currentIndex()

    @property
    def color_management(self) -> bool:
        return self.color_management_checkbox.isChecked()

    def __getstate__(self) -> dict[str, Any]:
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
            'output_primaries_index': self.primaries_combobox.currentIndex(),
            'dragnavigator_timeout': self.dragnavigator_timeout,
            'dragtimeline_timeout': self.dragtimeline_timeout,
            'plugins_bar_save_behaviour_index': self.plugins_bar_save_behaviour,
            'color_management': self.color_management,
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
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
        try_load(state, 'dragtimeline_timeout', int, self.dragtimeline_timeout_spinbox.setValue)
        try_load(state, 'output_primaries_index', int, self.primaries_combobox.setCurrentIndex)
        try_load(state, 'plugins_bar_save_behaviour_index', int, self.plugins_save_position_combobox.setCurrentIndex)
        try_load(state, 'color_management', bool, self.color_management_checkbox.setChecked)


class WindowSettings(QYAMLObjectSingleton):
    __slots__ = (
        'timeline_mode', 'window_geometry', 'window_state', 'zoom_index', 'x_pos', 'y_pos'
    )

    def __getstate__(self) -> dict[str, Any]:
        main = main_window()

        return {
            'timeline_mode': main.timeline.mode,
            'window_geometry': bytes(cast(bytearray, main.saveGeometry())),
            'window_state': bytes(cast(bytearray, main.saveState())),
            'zoom_index': main.graphics_view.zoom_combobox.currentIndex(),
            'x_pos': main.graphics_view.horizontalScrollBar().value(),
            'y_pos': main.graphics_view.verticalScrollBar().value(),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'timeline_mode', str, self.__setattr__)
        try_load(state, 'window_geometry', bytes, self.__setattr__)
        try_load(state, 'window_state', bytes, self.__setattr__)
        try_load(state, 'zoom_index', int, self.__setattr__)
        try_load(state, 'x_pos', int, self.__setattr__)
        try_load(state, 'y_pos', int, self.__setattr__)

        main = main_window()

        main.timeline.mode = self.timeline_mode

        main.graphics_view.zoom_combobox.setCurrentIndex(self.zoom_index)

        main.graphics_view.horizontalScrollBar().setValue(self.x_pos)
        main.graphics_view.verticalScrollBar().setValue(self.y_pos)

        main.restoreState(self.window_state)
        main.restoreGeometry(self.window_geometry)
