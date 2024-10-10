from __future__ import annotations

import logging
import re

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QLabel

from ...core import (
    AbstractToolbar, CheckBox, ComboBox, Frame, HBoxLayout, LineEdit, Notches, PushButton, Time,
    try_load
)
from ...models import SceningList, SceningLists
from ...utils import fire_and_forget, set_status_label
from .dialog import SceningListDialog
from .import_files import supported_file_types
from .settings import SceningSettings

if TYPE_CHECKING:
    from ...main import MainWindow


__all__ = [
    'SceningToolbar'
]


class SceningToolbar(AbstractToolbar):
    storable_attrs = ('current_list_index', 'lists', 'first_frame', 'second_frame')

    __slots__ = (
        *storable_attrs[1:],
        'export_template_pattern', 'export_template_scenes_pattern',
        'scening_list_dialog',
        'add_list_button', 'remove_list_button', 'view_list_button',
        'toggle_first_frame_button', 'toggle_second_frame_button',
        'add_single_frame_button',
        'add_to_list_button', 'remove_last_from_list_button',
        'export_button', 'export_template_lineedit',
        'always_show_scene_marks_checkbox',
        'status_label', 'import_file_button', 'items_combobox',
        'remove_at_current_frame_button',
        'seek_to_next_button', 'seek_to_prev_button'
    )

    settings: SceningSettings
    scening_list_dialog: SceningListDialog

    def __init__(self, main: MainWindow) -> None:
        super().__init__(main, SceningSettings(self))
        self.setup_ui()

        self.lists = SceningLists()

        self.first_frame: Frame | None = None
        self.second_frame: Frame | None = None
        self.export_template_pattern = re.compile(r'.*(?:{start}|{end}|{label}).*')
        self.export_template_scenes_pattern = re.compile(r'.+')

        self.items_combobox.setModel(self.lists)
        self.scening_update_status_label()
        self.scening_list_dialog = SceningListDialog(self.main)

        self.items_combobox.valueChanged.connect(self.on_current_list_changed)
        self.add_list_button.clicked.connect(self.on_add_list_clicked)
        self.remove_list_button.clicked.connect(self.on_remove_list_clicked)
        self.view_list_button.clicked.connect(self.on_view_list_clicked)
        self.import_file_button.clicked.connect(self.on_import_file_clicked)
        self.seek_to_prev_button.clicked.connect(self.on_seek_to_prev_clicked)
        self.seek_to_next_button.clicked.connect(self.on_seek_to_next_clicked)

        self.add_single_frame_button.clicked.connect(self.on_add_single_frame_clicked)
        self.toggle_first_frame_button.clicked.connect(self.on_first_frame_clicked)
        self.toggle_second_frame_button.clicked.connect(self.on_second_frame_clicked)
        self.add_to_list_button.clicked.connect(self.on_add_to_list_clicked)
        self.remove_last_from_list_button.clicked.connect(self.on_remove_last_from_list_clicked)
        self.remove_at_current_frame_button.clicked.connect(self.on_remove_at_current_frame_clicked)
        self.export_template_lineedit.textChanged.connect(self.check_remove_export_possibility)
        self.export_button.clicked.connect(self.export)

        # FIXME: get rid of workaround
        self._on_list_items_changed = lambda *arg: self.on_list_items_changed(*arg)

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.items_combobox = ComboBox[SceningList](duplicatesEnabled=True, minimumContentsLength=4)

        self.add_list_button = PushButton('Add List')

        self.remove_list_button = PushButton('Remove List', enabled=False)

        self.view_list_button = PushButton('View List', enabled=False)

        self.import_file_button = PushButton('Import List')

        self.seek_to_prev_button = PushButton('⏪', enabled=False)

        self.seek_to_next_button = PushButton('⏩', enabled=False)

        self.always_show_scene_marks_checkbox = CheckBox(
            'Always show scene marks in the timeline',
            checked=self.settings.always_show_scene_marks
        )

        self.add_single_frame_button = PushButton('🆎', tooltip='Add Single Frame Scene')

        self.toggle_first_frame_button = PushButton('🅰️', tooltip='Toggle Start of New Scene', checkable=True)

        self.toggle_second_frame_button = PushButton('🅱️', tooltip='Toggle End of New Scene', checkable=True)

        self.label_lineedit = LineEdit('New Scene Label')

        self.add_to_list_button = PushButton('Add to List', enabled=False)

        self.remove_last_from_list_button = PushButton('Remove Last', enabled=False)

        self.remove_at_current_frame_button = PushButton('Remove at Current Frame', enabled=False)

        self.export_template_lineedit = LineEdit(
            'Export Template',
            text=self.settings.default_export_template,
            tooltip=(
                r'Use {start} and {end} as placeholders.'
                r'Both are valid for single frame scenes. '
                r'{label} is available, too. '
            )
        )

        self.export_button = PushButton('Export', enabled=False)

        HBoxLayout(self.vlayout, [
            self.items_combobox,
            self.add_list_button,
            self.remove_list_button,
            self.view_list_button,
            self.import_file_button,
            self.get_separator(),
            self.seek_to_prev_button,
            self.seek_to_next_button,
            self.always_show_scene_marks_checkbox
        ]).addStretch()

        HBoxLayout(self.vlayout, [
            self.add_single_frame_button,
            self.toggle_first_frame_button,
            self.toggle_second_frame_button,
            self.label_lineedit,
            self.add_to_list_button,
            self.remove_last_from_list_button,
            self.remove_at_current_frame_button,
            self.get_separator(),
            self.export_template_lineedit,
            self.export_button
        ]).addStretch(2)

        self.status_label = QLabel(self)
        self.status_label.setVisible(False)
        self.main.statusbar.addPermanentWidget(self.status_label)

    def on_toggle(self, new_state: bool) -> None:
        if new_state is True:
            self.check_add_to_list_possibility()
            self.check_remove_export_possibility()

        self.status_label.setVisible(self.is_notches_visible)

        super().on_toggle(new_state)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        self.scening_list_dialog.on_current_output_changed(index, prev_index)

    def on_current_frame_changed(self, frame: Frame) -> None:
        self.check_remove_export_possibility()
        self.scening_list_dialog.on_current_frame_changed(frame, Time(frame))

    def get_notches(self) -> Notches:
        marks = Notches()

        if self.current_list is None:
            return marks

        for scene in self.current_list:
            marks.add(scene, cast(QColor, Qt.GlobalColor.green))

        return marks

    @property
    def current_list(self) -> SceningList | None:
        return self.items_combobox.currentValue()

    @property
    def current_list_index(self) -> int:
        return self.items_combobox.currentIndex()

    @current_list_index.setter
    def current_list_index(self, index: int) -> None:
        if (0 <= index < len(self.lists)):
            return self.items_combobox.setCurrentIndex(index)
        raise IndexError

    @property
    def is_notches_visible(self) -> bool:
        return self.always_show_scene_marks_checkbox.isChecked() or self.toggle_button.isChecked()

    def on_add_list_clicked(self, checked: bool | None = None) -> None:
        _, self.current_list_index = self.lists.add()

    def on_current_list_changed(self, new_value: SceningList | None, old_value: SceningList) -> None:
        if new_value is not None:
            self.remove_list_button.setEnabled(True)
            self.view_list_button.setEnabled(True)
            new_value.rowsInserted.connect(self._on_list_items_changed)
            new_value.rowsRemoved.connect(self._on_list_items_changed)
            new_value.dataChanged.connect(self._on_list_items_changed)
            self.scening_list_dialog.on_current_list_changed(new_value)
        else:
            self.remove_list_button.setEnabled(False)
            self.view_list_button.setEnabled(False)

        self.scening_list_dialog.adjustSize()

        if old_value is not None:
            try:
                old_value.rowsInserted.disconnect(self._on_list_items_changed)
                old_value.rowsRemoved.disconnect(self._on_list_items_changed)
                old_value.dataChanged.disconnect(self._on_list_items_changed)
            except (IndexError, TypeError):
                pass

        self.check_add_to_list_possibility()
        self.check_remove_export_possibility()
        self.notches_changed.emit(self)

    def on_list_items_changed(self, parent: QModelIndex, first: int, last: int) -> None:
        self.notches_changed.emit(self)

    def on_remove_list_clicked(self, checked: bool | None = None) -> None:
        self.lists.remove(self.current_list_index)

        if len(self.lists) == 0:
            self.remove_list_button.setEnabled(False)
            self.view_list_button.setEnabled(False)

    def on_view_list_clicked(self, checked: bool | None = None) -> None:
        self.scening_list_dialog.adjustSize()
        self.scening_list_dialog.show()

    def switch_list(self, index: int) -> None:
        try:
            self.current_list_index = index
        except IndexError:
            pass

    def on_seek_to_prev_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        new_pos = self.current_list.get_prev_frame(self.main.current_output.last_showed_frame)
        if new_pos is None:
            return
        self.main.switch_frame(new_pos)

    def on_seek_to_next_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        new_pos = self.current_list.get_next_frame(self.main.current_output.last_showed_frame)
        if new_pos is None:
            return
        self.main.switch_frame(new_pos)

    def on_add_single_frame_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            self.on_add_list_clicked()

        assert self.current_list is not None

        self.current_list.add(self.main.current_output.last_showed_frame, label=self.label_lineedit.text())

        self.check_remove_export_possibility()

    def on_add_to_list_clicked(self, checked: bool | None = None) -> None:
        self.current_list.add(self.first_frame, self.second_frame, self.label_lineedit.text())  # type: ignore

        if self.toggle_first_frame_button.isChecked():
            self.toggle_first_frame_button.click()
        if self.toggle_second_frame_button.isChecked():
            self.toggle_second_frame_button.click()
        self.add_to_list_button.setEnabled(False)
        self.label_lineedit.setText('')

        self.check_remove_export_possibility()

    def on_first_frame_clicked(self, checked: bool, frame: Frame | None = None) -> None:
        if frame is None:
            frame = self.main.current_output.last_showed_frame

        if checked:
            self.first_frame = frame
        else:
            self.first_frame = None
        self.scening_update_status_label()
        self.check_add_to_list_possibility()

    def on_remove_at_current_frame_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        curr = self.main.current_output.last_showed_frame

        for scene in self.current_list:
            if (scene.start == curr or scene.end == curr):
                self.current_list.remove(scene)

        self.remove_at_current_frame_button.clearFocus()
        self.check_remove_export_possibility()

    def on_remove_last_from_list_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        self.current_list.remove(self.current_list[-1])
        self.remove_last_from_list_button.clearFocus()
        self.check_remove_export_possibility()

    def on_second_frame_clicked(self, checked: bool, frame: Frame | None = None) -> None:
        if frame is None:
            frame = self.main.current_output.last_showed_frame

        if checked:
            self.second_frame = frame
        else:
            self.second_frame = None
        self.scening_update_status_label()
        self.check_add_to_list_possibility()

    def on_toggle_single_frame(self) -> None:
        if self.add_single_frame_button.isEnabled():
            self.add_single_frame_button.click()
        elif self.remove_at_current_frame_button.isEnabled():
            self.remove_at_current_frame_button.click()

    def on_import_file_clicked(self, checked: bool | None = None) -> None:
        filter_str = ';;'.join(supported_file_types.keys())
        path_strs, file_type = QFileDialog.getOpenFileNames(
            self.main, caption='Open chapters file', filter=filter_str
        )

        paths = [Path(path_str) for path_str in path_strs]
        for path in paths:
            self.import_file(supported_file_types[file_type], path)

    @fire_and_forget
    @set_status_label('Importing scening list')
    def import_file(self, import_func: Callable[[Path, SceningList], int], path: Path) -> None:
        scening_list, scening_list_index = self.lists.add(path.stem)

        out_of_range_count = import_func(path, scening_list)

        if out_of_range_count > 0:
            logging.warning(
                f'Scening import: {out_of_range_count} scenes were out of range of output, so they were dropped.')
        if len(scening_list) == 0:
            logging.warning(f"Scening import: nothing was imported from '{path.name}'.")
            self.lists.remove(scening_list_index)
        else:
            self.current_list_index = scening_list_index

    def export(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        template = self.export_template_lineedit.text()
        export_str = str()

        try:
            for scene in self.current_list:
                export_str += template.format(
                    start=scene.start, end=scene.end, label=scene.label, script_name=self.main.script_path.stem
                ) + ('\n' if self.settings.export_multiline else '')
        except KeyError:
            logging.warning('Scening: export template contains invalid placeholders.')
            self.main.show_message('Export template contains invalid placeholders.')
            return

        if self.main.clipboard:
            self.main.clipboard.setText(export_str)

        self.main.show_message('Scening data exported to the clipboard')

    def check_add_to_list_possibility(self) -> None:
        self.add_to_list_button.setEnabled(False)

        if not (self.current_list_index != -1 and (self.first_frame is not None or self.second_frame is not None)):
            return

        self.add_to_list_button.setEnabled(True)

    def check_remove_export_possibility(self, checked: bool | None = None) -> None:
        is_enabled = self.current_list is not None and len(self.current_list) > 0
        self.remove_last_from_list_button.setEnabled(is_enabled)
        self.seek_to_next_button.setEnabled(is_enabled)
        self.seek_to_prev_button.setEnabled(is_enabled)

        curr = self.main.current_output.last_showed_frame

        is_enabled = self.current_list is not None and curr in self.current_list
        self.add_single_frame_button.setEnabled(not is_enabled)
        self.remove_at_current_frame_button.setEnabled(is_enabled)

        is_enabled = self.export_template_pattern.fullmatch(self.export_template_lineedit.text()) is not None
        self.export_button.setEnabled(is_enabled)

    def scening_update_status_label(self) -> None:
        first_frame_text = str(self.first_frame) if self.first_frame is not None else ''
        second_frame_text = str(self.second_frame) if self.second_frame is not None else ''
        self.status_label.setText(f'Scening: {first_frame_text} - {second_frame_text} ')

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            'label': self.label_lineedit.text(),
            'scening_export_template': self.export_template_lineedit.text(),
            'always_show_scene_marks': self.always_show_scene_marks_checkbox.isChecked(),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'lists', SceningLists, self.__setattr__)
        try_load(state, 'current_list_index', int, self.current_list_index)
        try_load(state, 'first_frame', Frame, self.__setattr__, nullable=True)
        try_load(state, 'second_frame', Frame, self.__setattr__, nullable=True)

        if self.first_frame is not None:
            self.toggle_first_frame_button.setChecked(True)

        if self.second_frame is not None:
            self.toggle_second_frame_button.setChecked(True)

        self.scening_update_status_label()
        self.check_add_to_list_possibility()

        try_load(state, 'label', str, self.label_lineedit.setText)
        self.items_combobox.setModel(self.lists)

        try_load(state, 'scening_export_template', str, self.export_template_lineedit.setText)
        try_load(state, 'always_show_scene_marks', bool, self.always_show_scene_marks_checkbox.setChecked)

        self.status_label.setVisible(self.always_show_scene_marks_checkbox.isChecked())

        super().__setstate__(state)
