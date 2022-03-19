from __future__ import annotations

import re
import logging
from pathlib import Path
from copy import deepcopy
from typing import Any, Callable, cast, List, Mapping, Set

from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QModelIndex, QItemSelection, QItemSelectionModel
from PyQt5.QtWidgets import (
    QDialog, QPushButton, QVBoxLayout, QLineEdit, QTableView, QHBoxLayout, QFrame, QLabel, QFileDialog
)

from ..models import SceningList, SceningLists
from ..widgets import ComboBox, Notches, TimeEdit, FrameEdit
from ..utils import add_shortcut, fire_and_forget, qt_silent_call, set_qobject_names, set_status_label
from ..core import AbstractMainWindow, AbstractToolbar, Frame, Time, try_load


class SceningListDialog(QDialog):
    __slots__ = (
        'main', 'scening_list',
        'name_lineedit', 'tableview',
        'start_frame_control', 'end_frame_control',
        'start_time_control', 'end_time_control',
        'label_lineedit',
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main)

        self.main = main
        self.scening_list = SceningList()

        self.setWindowTitle('Scening List View')
        self.setup_ui()

        self.end_frame_control.valueChanged.connect(self.on_end_frame_changed)
        self.end_time_control.valueChanged.connect(self.on_end_time_changed)
        self.label_lineedit.textChanged.connect(self.on_label_changed)
        self.name_lineedit.textChanged.connect(self.on_name_changed)
        self.start_frame_control.valueChanged.connect(self.on_start_frame_changed)
        self.start_time_control.valueChanged.connect(self.on_start_time_changed)
        self.tableview.doubleClicked.connect(self.on_tableview_clicked)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setObjectName('SceningListDialog.setup_ui.layout')

        self.name_lineedit = QLineEdit(self)
        layout.addWidget(self.name_lineedit)

        self.tableview = QTableView(self)
        self.tableview.setSelectionMode(QTableView.SingleSelection)
        self.tableview.setSelectionBehavior(QTableView.SelectRows)
        self.tableview.setSizeAdjustPolicy(QTableView.AdjustToContents)
        layout.addWidget(self.tableview)

        scene_layout = QHBoxLayout()
        scene_layout.setObjectName('SceningListDialog.setup_ui.scene_layout')
        layout.addLayout(scene_layout)

        self.start_frame_control = FrameEdit(self)
        scene_layout.addWidget(self.start_frame_control)

        self.end_frame_control = FrameEdit(self)
        scene_layout.addWidget(self.end_frame_control)

        self.start_time_control = TimeEdit(self)
        scene_layout.addWidget(self.start_time_control)

        self.end_time_control = TimeEdit(self)
        scene_layout.addWidget(self.end_time_control)

        self.label_lineedit = QLineEdit(self)
        self.label_lineedit.setPlaceholderText('Label')
        scene_layout.addWidget(self.label_lineedit)

        self.add_button = QPushButton(self)
        self.add_button.setText('Add')
        self.add_button.setEnabled(False)
        scene_layout.addWidget(self.add_button)

    def on_add_clicked(self, checked: bool | None = None) -> None:
        pass

    def on_current_frame_changed(self, frame: Frame, time: Time) -> None:
        if not self.isVisible():
            return
        if self.tableview.selectionModel() is None:
            return
        selection = QItemSelection()
        for i, scene in enumerate(self.scening_list):
            if frame in scene:
                index = self.scening_list.index(i, 0)
                selection.select(index, index)
        self.tableview.selectionModel().select(
            selection,
            QItemSelectionModel.SelectionFlags(
                QItemSelectionModel.Rows + QItemSelectionModel.ClearAndSelect
            )
        )

    def on_current_list_changed(self, scening_list: SceningList | None = None) -> None:
        if scening_list is not None:
            self.scening_list = scening_list
        else:
            self.scening_list = self.main.toolbars.scening.current_list

        self.scening_list.rowsMoved.connect(self.on_tableview_rows_moved)

        self.name_lineedit.setText(self.scening_list.name)

        self.tableview.setModel(self.scening_list)
        self.tableview.resizeColumnsToContents()
        self.tableview.selectionModel().selectionChanged.connect(self.on_tableview_selection_changed)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        self.start_frame_control.setMaximum(self.main.current_output.end_frame)
        self.end_frame_control.setMaximum(self.main.current_output.end_frame)
        self.start_time_control.setMaximum(self.main.current_output.end_time)
        self.end_time_control.setMaximum(self.main.current_output.end_time)

    def on_end_frame_changed(self, value: Frame | int) -> None:
        frame = Frame(value)
        index = self.tableview.selectionModel().selectedRows()[0]
        if not index.isValid():
            return
        index = index.siblingAtColumn(SceningList.END_FRAME_COLUMN)
        if not index.isValid():
            return
        self.scening_list.setData(index, frame, Qt.UserRole)

    def on_end_time_changed(self, time: Time) -> None:
        index = self.tableview.selectionModel().selectedRows()[0]
        if not index.isValid():
            return
        index = index.siblingAtColumn(SceningList.END_TIME_COLUMN)
        if not index.isValid():
            return
        self.scening_list.setData(index, time, Qt.UserRole)

    def on_label_changed(self, text: str) -> None:
        if self.tableview.selectionModel() is None:
            return
        index = self.tableview.selectionModel().selectedRows()[0]
        if not index.isValid():
            return
        index = self.scening_list.index(index.row(), SceningList.LABEL_COLUMN)
        if not index.isValid():
            return
        self.scening_list.setData(index, text, Qt.UserRole)

    def on_name_changed(self, text: str) -> None:
        i = self.main.current_output.scening_lists.index_of(self.scening_list)
        index = self.main.current_output.scening_lists.index(i)
        self.main.current_output.scening_lists.setData(index, text, Qt.UserRole)

    def on_start_frame_changed(self, value: Frame | int) -> None:
        frame = Frame(value)
        index = self.tableview.selectionModel().selectedRows()[0]
        if not index.isValid():
            return
        index = index.siblingAtColumn(SceningList.START_FRAME_COLUMN)
        if not index.isValid():
            return
        self.scening_list.setData(index, frame, Qt.UserRole)

    def on_start_time_changed(self, time: Time) -> None:
        index = self.tableview.selectionModel().selectedRows()[0]
        if not index.isValid():
            return
        index = index.siblingAtColumn(SceningList.START_TIME_COLUMN)
        if not index.isValid():
            return
        self.scening_list.setData(index, time, Qt.UserRole)

    def on_tableview_clicked(self, index: QModelIndex) -> None:
        if index.column() in {SceningList.START_FRAME_COLUMN, SceningList.END_FRAME_COLUMN}:
            self.main.current_frame = self.scening_list.data(index)
        if index.column() == SceningList.START_TIME_COLUMN:
            self.main.current_frame = self.scening_list.data(index.siblingAtColumn(SceningList.START_FRAME_COLUMN))
        if index.column() == SceningList.END_TIME_COLUMN:
            self.main.current_frame = self.scening_list.data(index.siblingAtColumn(SceningList.END_FRAME_COLUMN))

    def on_tableview_rows_moved(
        self, parent_index: QModelIndex, start_i: int, end_i: int, dest_index: QModelIndex, dest_i: int
    ) -> None:
        index = self.scening_list.index(dest_i, 0)
        self.tableview.selectionModel().select(
            index,
            QItemSelectionModel.SelectionFlags(
                QItemSelectionModel.Rows + QItemSelectionModel.ClearAndSelect))

    def on_tableview_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        if len(selected.indexes()) == 0:
            return
        index = selected.indexes()[0]
        scene = self.scening_list[index.row()]
        qt_silent_call(self.start_frame_control.setValue, scene.start)
        qt_silent_call(self.end_frame_control.setValue, scene.end)
        qt_silent_call(self.start_time_control.setValue, Time(scene.start))
        qt_silent_call(self.end_time_control.setValue, Time(scene.end))
        qt_silent_call(self.label_lineedit.setText, scene.label)


class SceningToolbar(AbstractToolbar):
    __slots__ = (
        'first_frame', 'second_frame',
        'export_template_pattern', 'export_template_scenes_pattern',
        'scening_list_dialog', 'supported_file_types',
        'add_list_button', 'remove_list_button', 'view_list_button',
        'toggle_first_frame_button', 'toggle_second_frame_button', 'add_single_frame_button',
        'add_to_list_button', 'remove_last_from_list_button',
        'export_single_line_button', 'export_template_lineedit', 'export_multiline_button',
        'status_label', 'import_file_button', 'items_combobox', 'remove_at_current_frame_button',
        'seek_to_next_button', 'seek_to_prev_button',
        'toggle_button'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, 'Scening')
        self.setup_ui()

        self.first_frame: Frame | None = None
        self.second_frame: Frame | None = None
        self.export_template_pattern = re.compile(r'.*(?:{start}|{end}|{label}).*')
        self.export_template_scenes_pattern = re.compile(r'.+')

        self.scening_update_status_label()
        self.scening_list_dialog = SceningListDialog(self.main)

        self.supported_file_types = {
            'Matroska XML Chapters (*.xml)': self.import_matroska_xml_chapters,
            'Aegisub Project (*.ass)': self.import_ass,
            'CUE Sheet (*.cue)': self.import_cue,
            'DGIndex Project (*.dgi)': self.import_dgi,
            'L-SMASH Works Index (*.lwi)': self.import_lwi,
            'Matroska Timestamps v1 (*.txt)': self.import_matroska_timestamps_v1,
            'Matroska Timestamps v2 (*.txt)': self.import_matroska_timestamps_v2,
            'OGM Chapters (*.txt)': self.import_ogm_chapters,
            'TFM Log (*.txt)': self.import_tfm,
            'x264/x265 QP File (*.qp)': self.import_qp,
            'XviD Log (*.txt)': self.import_xvid,
            'Simple Mappings (*.txt)': self.import_simple,
        }

        self.add_list_button.clicked.connect(self.on_add_list_clicked)
        self.add_single_frame_button.clicked.connect(self.on_add_single_frame_clicked)
        self.add_to_list_button.clicked.connect(self.on_add_to_list_clicked)
        self.export_multiline_button.clicked.connect(self.export_multiline)
        self.export_single_line_button.clicked.connect(self.export_single_line)
        self.export_template_lineedit.textChanged.connect(self.check_remove_export_possibility)
        self.import_file_button.clicked.connect(self.on_import_file_clicked)
        self.items_combobox.valueChanged.connect(self.on_current_list_changed)
        self.remove_at_current_frame_button.clicked.connect(self.on_remove_at_current_frame_clicked)
        self.remove_last_from_list_button.clicked.connect(self.on_remove_last_from_list_clicked)
        self.remove_list_button.clicked.connect(self.on_remove_list_clicked)
        self.seek_to_next_button.clicked.connect(self.on_seek_to_next_clicked)
        self.seek_to_prev_button.clicked.connect(self.on_seek_to_prev_clicked)
        self.toggle_first_frame_button.clicked.connect(self.on_first_frame_clicked)
        self.toggle_second_frame_button.clicked.connect(self.on_second_frame_clicked)
        self.view_list_button.clicked.connect(self.on_view_list_clicked)

        add_shortcut(Qt.SHIFT + Qt.Key_1, lambda: self.switch_list(0))
        add_shortcut(Qt.SHIFT + Qt.Key_2, lambda: self.switch_list(1))
        add_shortcut(Qt.SHIFT + Qt.Key_3, lambda: self.switch_list(2))
        add_shortcut(Qt.SHIFT + Qt.Key_4, lambda: self.switch_list(3))
        add_shortcut(Qt.SHIFT + Qt.Key_5, lambda: self.switch_list(4))
        add_shortcut(Qt.SHIFT + Qt.Key_6, lambda: self.switch_list(5))
        add_shortcut(Qt.SHIFT + Qt.Key_7, lambda: self.switch_list(6))
        add_shortcut(Qt.SHIFT + Qt.Key_8, lambda: self.switch_list(7))
        add_shortcut(Qt.SHIFT + Qt.Key_9, lambda: self.switch_list(8))

        add_shortcut(Qt.CTRL + Qt.Key_Space, self.on_toggle_single_frame)
        add_shortcut(Qt.CTRL + Qt.Key_Left, self.seek_to_next_button.click)
        add_shortcut(Qt.CTRL + Qt.Key_Right, self.seek_to_prev_button.click)
        add_shortcut(Qt.Key_Q, self.toggle_first_frame_button.click)
        add_shortcut(Qt.Key_W, self.toggle_second_frame_button.click)
        add_shortcut(Qt.Key_E, self.add_to_list_button.click)
        add_shortcut(Qt.Key_R, self.remove_last_from_list_button.click)
        add_shortcut(
            Qt.Key_B,
            lambda: self.scening_list_dialog.label_lineedit.setText(str(self.main.current_frame))
        )

        # FIXME: get rid of workaround
        self._on_list_items_changed = lambda * arg: self.on_list_items_changed(
            *arg)  # pylint: disable=unnecessary-lambda, no-value-for-parameter

        set_qobject_names(self)

    def setup_ui(self) -> None:
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setObjectName('SceningToolbar.setup_ui.layout')
        layout.setContentsMargins(0, 0, 0, 0)

        layout_line_1 = QHBoxLayout()
        layout_line_1.setObjectName('SceningToolbar.setup_ui.layout_line_1')
        layout.addLayout(layout_line_1)

        self.items_combobox = ComboBox[SceningList](self)
        self.items_combobox.setDuplicatesEnabled(True)
        self.items_combobox.setMinimumContentsLength(4)
        layout_line_1.addWidget(self.items_combobox)

        self.add_list_button = QPushButton(self)
        self.add_list_button.setText('Add List')
        layout_line_1.addWidget(self.add_list_button)

        self.remove_list_button = QPushButton(self)
        self.remove_list_button.setText('Remove List')
        self.remove_list_button.setEnabled(False)
        layout_line_1.addWidget(self.remove_list_button)

        self.view_list_button = QPushButton(self)
        self.view_list_button.setText('View List')
        self.view_list_button.setEnabled(False)
        layout_line_1.addWidget(self.view_list_button)

        self.import_file_button = QPushButton(self)
        self.import_file_button.setText('Import List')
        layout_line_1.addWidget(self.import_file_button)

        separator_line_1 = QFrame(self)
        separator_line_1.setObjectName(
            'SceningToolbar.setup_ui.separator_line_1')
        separator_line_1.setFrameShape(QFrame.VLine)
        separator_line_1.setFrameShadow(QFrame.Sunken)
        layout_line_1.addWidget(separator_line_1)

        self.seek_to_prev_button = QPushButton(self)
        self.seek_to_prev_button.setText('⏪')
        self.seek_to_prev_button.setEnabled(False)
        layout_line_1.addWidget(self.seek_to_prev_button)

        self.seek_to_next_button = QPushButton(self)
        self.seek_to_next_button.setText('⏩')
        self.seek_to_next_button.setEnabled(False)
        layout_line_1.addWidget(self.seek_to_next_button)

        layout_line_1.addStretch()

        layout_line_2 = QHBoxLayout()
        layout_line_2.setObjectName('SceningToolbar.setup_ui.layout_line_2')
        layout.addLayout(layout_line_2)

        self.add_single_frame_button = QPushButton(self)
        # self.add_single_frame_button.setText('Add Single Frame')
        self.add_single_frame_button.setText('🆎')
        self.add_single_frame_button.setToolTip('Add Single Frame Scene')
        layout_line_2.addWidget(self.add_single_frame_button)

        self.toggle_first_frame_button = QPushButton(self)
        # self.toggle_first_frame_button.setText('Frame 1')
        self.toggle_first_frame_button.setText('🅰️')
        self.toggle_first_frame_button.setToolTip('Toggle Start of New Scene')
        self.toggle_first_frame_button.setCheckable(True)
        layout_line_2.addWidget(self.toggle_first_frame_button)

        self.toggle_second_frame_button = QPushButton(self)
        # self.toggle_second_frame_button.setText('Frame 2')
        self.toggle_second_frame_button.setText('🅱️')
        self.toggle_second_frame_button.setToolTip('Toggle End of New Scene')
        self.toggle_second_frame_button.setCheckable(True)
        layout_line_2.addWidget(self.toggle_second_frame_button)

        self.label_lineedit = QLineEdit(self)
        self.label_lineedit.setPlaceholderText('New Scene Label')
        layout_line_2.addWidget(self.label_lineedit)

        self.add_to_list_button = QPushButton(self)
        self.add_to_list_button.setText('Add to List')
        self.add_to_list_button.setEnabled(False)
        layout_line_2.addWidget(self.add_to_list_button)

        self.remove_last_from_list_button = QPushButton(self)
        self.remove_last_from_list_button.setText('Remove Last')
        self.remove_last_from_list_button.setEnabled(False)
        layout_line_2.addWidget(self.remove_last_from_list_button)

        self.remove_at_current_frame_button = QPushButton(self)
        self.remove_at_current_frame_button.setText('Remove at Current Frame')
        self.remove_at_current_frame_button.setEnabled(False)
        layout_line_2.addWidget(self.remove_at_current_frame_button)

        separator_line_2 = QFrame(self)
        separator_line_2.setObjectName(
            'SceningToolbar.setup_ui.separator_line_2')
        separator_line_2.setFrameShape(QFrame.VLine)
        separator_line_2.setFrameShadow(QFrame.Sunken)
        layout_line_2.addWidget(separator_line_2)

        self.export_template_lineedit = QLineEdit(self)
        self.export_template_lineedit.setToolTip(
            r'Use {start} and {end} as placeholders.'
            r'Both are valid for single frame scenes. '
            r'{label} is available, too. '
        )
        self.export_template_lineedit.setPlaceholderText('Export Template')
        layout_line_2.addWidget(self.export_template_lineedit)

        self.export_multiline_button = QPushButton(self)
        self.export_multiline_button.setText('Export Multiline')
        self.export_multiline_button.setEnabled(False)
        layout_line_2.addWidget(self.export_multiline_button)

        self.export_single_line_button = QPushButton(self)
        self.export_single_line_button.setText('Export Single Line')
        self.export_single_line_button.setEnabled(False)
        layout_line_2.addWidget(self.export_single_line_button)

        layout_line_2.addStretch()
        layout_line_2.addStretch()

        # statusbar label

        self.status_label = QLabel(self)
        self.status_label.setVisible(False)
        self.main.statusbar.addPermanentWidget(self.status_label)

    def on_toggle(self, new_state: bool) -> None:
        # if new_state is True:
        #     self.check_add_to_list_possibility()
        #     self.check_remove_export_possibility()

        self.status_label.setVisible(new_state)
        super().on_toggle(new_state)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        if prev_index != -1:
            for scening_list in self.main.outputs[prev_index].scening_lists:
                try:
                    scening_list.rowsInserted.disconnect(self.on_list_items_changed)
                    scening_list.rowsRemoved.disconnect(self.on_list_items_changed)
                except TypeError:
                    pass

        self.items_combobox.setModel(self.current_lists)
        self.notches_changed.emit(self)
        self.scening_list_dialog.on_current_output_changed(index, prev_index)

    def on_current_frame_changed(self, frame: Frame) -> None:
        self.check_remove_export_possibility()
        self.scening_list_dialog.on_current_frame_changed(frame, Time(frame))

    def get_notches(self) -> Notches:
        marks = Notches()
        if self.current_list is None:
            return marks
        for scene in self.current_list:
            marks.add(scene, cast(QColor, Qt.green))
        return marks

    @property
    def current_list(self) -> SceningList:
        return self.items_combobox.currentValue()

    @current_list.setter
    def current_list(self, item: SceningList) -> None:
        self.items_combobox.setCurrentValue(item)

    @property
    def current_lists(self) -> SceningLists:
        return self.main.current_output.scening_lists

    @property
    def current_list_index(self) -> int:
        return self.items_combobox.currentIndex()

    @current_list_index.setter
    def current_list_index(self, index: int) -> None:
        if not (0 <= index < len(self.current_lists)):
            raise IndexError
        self.items_combobox.setCurrentIndex(index)

    # list management

    def on_add_list_clicked(self, checked: bool | None = None) -> None:
        _, i = self.current_lists.add()
        self.current_list_index = i

    def on_current_list_changed(self, new_value: SceningList | None, old_value: SceningList) -> None:
        if new_value is not None:
            self.remove_list_button.setEnabled(True)
            self.view_list_button.setEnabled(True)
            new_value.rowsInserted.connect(self._on_list_items_changed)
            new_value.rowsRemoved.connect(self._on_list_items_changed)
            self.scening_list_dialog.on_current_list_changed(new_value)
        else:
            self.remove_list_button.setEnabled(False)
            self.view_list_button.setEnabled(False)

        if old_value is not None:
            try:
                old_value.rowsInserted.disconnect(self._on_list_items_changed)
                old_value.rowsRemoved.disconnect(self._on_list_items_changed)
            except (IndexError, TypeError):
                pass

        self.check_add_to_list_possibility()
        self.check_remove_export_possibility()
        self.notches_changed.emit(self)

    def on_list_items_changed(self, parent: QModelIndex, first: int, last: int) -> None:
        self.notches_changed.emit(self)

    def on_remove_list_clicked(self, checked: bool | None = None) -> None:
        self.current_lists.remove(self.current_list_index)

    def on_view_list_clicked(self, checked: bool | None = None) -> None:
        self.scening_list_dialog.show()

    def switch_list(self, index: int) -> None:
        try:
            self.current_list_index = index
        except IndexError:
            pass

    # seeking

    def on_seek_to_next_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        new_pos = self.current_list.get_next_frame(self.main.current_frame)
        if new_pos is None:
            return
        self.main.current_frame = new_pos

    def on_seek_to_prev_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        new_pos = self.current_list.get_prev_frame(self.main.current_frame)
        if new_pos is None:
            return
        self.main.current_frame = new_pos

    # scene management

    def on_add_single_frame_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            self.on_add_list_clicked()
        cast(SceningList, self.current_list).add(self.main.current_frame)
        self.check_remove_export_possibility()

    def on_add_to_list_clicked(self, checked: bool | None = None) -> None:
        self.current_list.add(self.first_frame, self.second_frame, self.label_lineedit.text())

        if self.toggle_first_frame_button.isChecked():
            self.toggle_first_frame_button.click()
        if self.toggle_second_frame_button.isChecked():
            self.toggle_second_frame_button.click()
        self.add_to_list_button.setEnabled(False)
        self.label_lineedit.setText('')

        self.check_remove_export_possibility()

    def on_first_frame_clicked(self, checked: bool, frame: Frame | None = None) -> None:
        if frame is None:
            frame = self.main.current_frame

        if checked:
            self.first_frame = frame
        else:
            self.first_frame = None
        self.scening_update_status_label()
        self.check_add_to_list_possibility()

    def on_remove_at_current_frame_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        for scene in self.current_list:
            if (scene.start == self.main.current_frame or scene.end == self.main.current_frame):
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
            frame = self.main.current_frame

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

    # import

    def on_import_file_clicked(self, checked: bool | None = None) -> None:
        filter_str = ';;'.join(self.supported_file_types.keys())
        path_strs, file_type = QFileDialog.getOpenFileNames(
            self.main, caption='Open chapters file', filter=filter_str)

        paths = [Path(path_str) for path_str in path_strs]
        for path in paths:
            self.import_file(self.supported_file_types[file_type], path)

    @fire_and_forget
    @set_status_label('Importing scening list')
    def import_file(self, import_func: Callable[[Path, SceningList, int], None], path: Path) -> None:
        out_of_range_count = 0
        scening_list, scening_list_index = self.current_lists.add(path.stem)

        import_func(path, scening_list, out_of_range_count)

        if out_of_range_count > 0:
            logging.warning(
                f'Scening import: {out_of_range_count} scenes were out of range of output, so they were dropped.')
        if len(scening_list) == 0:
            logging.warning(f'Scening import: nothing was imported from \'{path.name}\'.')
            self.current_lists.remove(scening_list_index)
        else:
            self.current_list_index = scening_list_index

    def import_ass(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports lines as scenes.
        Text is ignored.
        '''
        import pysubs2

        subs = pysubs2.load(str(path))
        for line in subs:
            t_start = Time(milliseconds=line.start)
            t_end = Time(milliseconds=line.end)
            try:
                scening_list.add(Frame(t_start), Frame(t_end))
            except ValueError:
                out_of_range_count += 1

    def import_cue(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports tracks as scenes.
        Uses TITLE for scene label.
        '''
        from cueparser import CueSheet

        def offset_to_time(offset: str) -> Time | None:
            pattern = re.compile(r'(\d{1,2}):(\d{1,2}):(\d{1,2})')
            match = pattern.match(offset)
            if match is None:
                return None
            return Time(
                minutes=int(match[1]),
                seconds=int(match[2]),
                milliseconds=int(match[3]) / 75 * 1000
            )

        cue_sheet = CueSheet()
        cue_sheet.setOutputFormat('')
        cue_sheet.setData(path.read_text())
        cue_sheet.parse()

        for track in cue_sheet.tracks:
            if track.offset is None:
                continue
            offset = offset_to_time(track.offset)
            if offset is None:
                logging.warning(f'Scening import: INDEX timestamp \'{track.offset}\' format isn\'t suported.')
                continue
            start = Frame(offset)

            end = None
            if track.duration is not None:
                end = Frame(offset + Time(track.duration))

            label = ''
            if track.title is not None:
                label = track.title

            try:
                scening_list.add(start, end, label)
            except ValueError:
                out_of_range_count += 1

    def import_dgi(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports IDR frames as single-frame scenes.
        '''
        pattern = re.compile(r'IDR\s\d+\n(\d+):FRM', re.RegexFlag.MULTILINE)
        for match in pattern.findall(path.read_text()):
            try:
                scening_list.add(Frame(match))
            except ValueError:
                out_of_range_count += 1

    def import_lwi(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports Key=1 frames as single-frame scenes.
        Ignores everything besides Index=0 video stream.
        '''
        AV_CODEC_ID_FIRST_AUDIO = 0x10000
        STREAM_INDEX = 0
        IS_KEY = 1

        pattern = re.compile(r'Index={}.*?Codec=(\d+).*?\n.*?Key=(\d)'.format(
            STREAM_INDEX
        ))

        frame = Frame(0)
        for match in pattern.finditer(path.read_text(), re.RegexFlag.MULTILINE):
            if int(match[1]) >= AV_CODEC_ID_FIRST_AUDIO:
                frame += Frame(1)
                continue

            if not int(match[2]) == IS_KEY:
                frame += Frame(1)
                continue

            try:
                scening_list.add(deepcopy(frame))
            except ValueError:
                out_of_range_count += 1

            frame += Frame(1)

    def import_matroska_xml_chapters(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports chapters as scenes.
        Preserve end time and text if they're present.
        '''
        from xml.etree import ElementTree

        timestamp_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}(?:\.\d{3})?)')

        try:
            root = ElementTree.parse(str(path)).getroot()
        except ElementTree.ParseError as exc:
            logging.warning(f'Scening import: error occured while parsing \'{path.name}\':')
            logging.warning(exc.msg)
            return
        for chapter in root.iter('ChapterAtom'):
            start_element = chapter.find('ChapterTimeStart')
            if start_element is None or start_element.text is None:
                continue
            match = timestamp_pattern.match(start_element.text)
            if match is None:
                continue
            start = Frame(Time(
                hours=int(match[1]),
                minutes=int(match[2]),
                seconds=float(match[3])
            ))

            end = None
            end_element = chapter.find('ChapterTimeEnd')
            if end_element is not None and end_element.text is not None:
                match = timestamp_pattern.match(end_element.text)
                if match is not None:
                    end = Frame(Time(
                        hours=int(match[1]),
                        minutes=int(match[2]),
                        seconds=float(match[3])
                    ))

            label = ''
            label_element = chapter.find('ChapterDisplay/ChapterString')
            if label_element is not None and label_element.text is not None:
                label = label_element.text

            try:
                scening_list.add(start, end, label)
            except ValueError:
                out_of_range_count += 1

    def import_ogm_chapters(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports chapters as signle-frame scenes.
        Uses NAME for scene label.
        '''
        pattern = re.compile(
            r'(CHAPTER\d+)=(\d{2}):(\d{2}):(\d{2}(?:\.\d{3})?)\n\1NAME=(.*)',
            re.RegexFlag.MULTILINE
        )
        for match in pattern.finditer(path.read_text()):
            time = Time(
                hours=int(match[2]),
                minutes=int(match[3]),
                seconds=float(match[4])
            )
            try:
                scening_list.add(Frame(time), label=match[5])
            except ValueError:
                out_of_range_count += 1

    def import_qp(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports I- and K-frames as single-frame scenes.
        '''
        pattern = re.compile(r'(\d+)\sI|K')
        for match in pattern.findall(path.read_text()):
            try:
                scening_list.add(Frame(match))
            except ValueError:
                out_of_range_count += 1

    def import_matroska_timestamps_v1(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports gaps between timestamps as scenes.
        '''
        pattern = re.compile(r'(\d+),(\d+),(\d+(?:\.\d+)?)')

        for match in pattern.finditer(path.read_text()):
            try:
                scening_list.add(
                    Frame(int(match[1])),
                    Frame(int(match[2])),
                    '{:.3f} fps'.format(float(match[3]))
                )
            except ValueError:
                out_of_range_count += 1

    def import_matroska_timestamps_v2(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports intervals of constant FPS as scenes.
        Uses FPS as scene label.
        '''
        timestamps: List[Time] = []
        for line in path.read_text().splitlines():
            try:
                timestamps.append(Time(milliseconds=float(line)))
            except ValueError:
                continue

        if len(timestamps) < 2:
            logging.warning(
                'Scening import: timestamps file contains less that 2 timestamps, so there\'s nothing to import.')
            return

        deltas = [
            timestamps[i] - timestamps[i - 1]
            for i in range(1, len(timestamps))
        ]
        scene_delta = deltas[0]
        scene_start = Frame(0)
        scene_end: Frame | None = None
        for i in range(1, len(deltas)):
            if abs(round(float(deltas[i] - scene_delta), 6)) <= 0.000_001:
                continue
            # TODO: investigate, why offset by -1 is necessary here
            scene_end = Frame(i - 1)
            try:
                scening_list.add(
                    scene_start, scene_end,
                    '{:.3f} fps'.format(1 / float(scene_delta)))
            except ValueError:
                out_of_range_count += 1
            scene_start = Frame(i)
            scene_end = None
            scene_delta = deltas[i]

        if scene_end is None:
            try:
                scening_list.add(
                    scene_start, Frame(len(timestamps) - 1),
                    '{:.3f} fps'.format(1 / float(scene_delta))
                )
            except ValueError:
                out_of_range_count += 1

    def import_tfm(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports TFM's 'OVR HELP INFORMATION'.
        Single combed frames are put into single-frame scenes.
        Frame groups are put into regular scenes.
        Combed probability is used for label.
        '''
        class TFMFrame(Frame):
            mic: int | None

        tfm_frame_pattern = re.compile(r'(\d+)\s\((\d+)\)')
        tfm_group_pattern = re.compile(r'(\d+),(\d+)\s\((\d+(?:\.\d+)%)\)')

        log = path.read_text()

        start_pos = log.find('OVR HELP INFORMATION')
        if start_pos == -1:
            logging.warning('Scening import: TFM log doesn\'t contain OVR Help Information.')
            return
        log = log[start_pos:]

        tfm_frames: Set[TFMFrame] = set()
        for match in tfm_frame_pattern.finditer(log):
            tfm_frame = TFMFrame(int(match[1]))
            tfm_frame.mic = int(match[2])
            tfm_frames.add(tfm_frame)

        for match in tfm_group_pattern.finditer(log):
            try:
                scene = scening_list.add(
                    Frame(int(match[1])),
                    Frame(int(match[2])),
                    '{} combed'.format(match[3])
                )
            except ValueError:
                out_of_range_count += 1
                continue

            tfm_frames -= set(range(int(scene.start), int(scene.end) + 1))

        for tfm_frame in tfm_frames:
            try:
                scening_list.add(tfm_frame, label=str(tfm_frame.mic))
            except ValueError:
                out_of_range_count += 1

    def import_xvid(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports I-frames as single-frames scenes.
        '''
        for i, line in enumerate(path.read_text().splitlines()):
            if not line.startswith('i'):
                continue
            try:
                scening_list.add(Frame(i - 3))
            except ValueError:
                out_of_range_count += 1

    def import_simple(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Import simple frame mappings [Start End]
        '''
        for line in path.read_text().splitlines():
            try:
                fnumbers = [int(n) for n in line.split()]
                scening_list.add(Frame(fnumbers[0]), Frame(fnumbers[1]))
            except ValueError:
                out_of_range_count += 1

    # export

    def export_multiline(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        template = self.export_template_lineedit.text()
        export_str = str()

        try:
            for scene in self.current_list:
                export_str += template.format(
                    start=scene.start, end=scene.end, label=scene.label
                ) + '\n'
        except KeyError:
            logging.warning('Scening: export template contains invalid placeholders.')
            self.main.show_message('Export template contains invalid placeholders.')
            return

        self.main.clipboard.setText(export_str)
        self.main.show_message('Scening data exported to the clipboard')

    def export_single_line(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        template = self.export_template_lineedit.text()
        export_str = str()

        try:
            for scene in self.current_list:
                export_str += template.format(
                    start=scene.start, end=scene.end, label=scene.label
                )
        except KeyError:
            logging.warning('Scening: export template contains invalid placeholders.')
            self.main.show_message('Export template contains invalid placeholders.')
            return

        self.main.clipboard.setText(export_str)
        self.main.show_message('Scening data exported to the clipboard')

    # misc
    def check_add_to_list_possibility(self) -> None:
        self.add_to_list_button.setEnabled(False)

        if not (self.current_list_index != -1 and (self.first_frame is not None or self.second_frame is not None)):
            return

        self.add_to_list_button.setEnabled(True)

    def check_remove_export_possibility(self, checked: bool | None = None) -> None:
        if self.current_list is not None and len(self.current_list) > 0:
            self.remove_last_from_list_button.setEnabled(True)
            self.seek_to_next_button.setEnabled(True)
            self.seek_to_prev_button.setEnabled(True)
        else:
            self.remove_last_from_list_button.setEnabled(False)
            self.seek_to_next_button.setEnabled(False)
            self.seek_to_prev_button.setEnabled(False)

        if self.current_list is not None and self.main.current_frame in self.current_list:
            self.add_single_frame_button.setEnabled(False)
            self.remove_at_current_frame_button.setEnabled(True)
        else:
            self.add_single_frame_button.setEnabled(True)
            self.remove_at_current_frame_button.setEnabled(False)

        if self.export_template_pattern.fullmatch(self.export_template_lineedit.text()) is not None:
            self.export_multiline_button.setEnabled(True)
            self.export_single_line_button.setEnabled(True)
        else:
            self.export_single_line_button.setEnabled(False)
            self.export_multiline_button.setEnabled(False)

    def scening_update_status_label(self) -> None:
        first_frame_text = str(self.first_frame) if self.first_frame is not None else ''
        second_frame_text = str(self.second_frame) if self.second_frame is not None else ''
        self.status_label.setText('Scening: {} - {} '.format(first_frame_text, second_frame_text))

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'first_frame': self.first_frame,
            'second_frame': self.second_frame,
            'label': self.label_lineedit.text(),
            'scening_export_template': self.export_template_lineedit.text(),
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            first_frame = state['first_frame']
            if first_frame is not None and not isinstance(first_frame, Frame):
                raise TypeError
            self.first_frame = first_frame
        except (KeyError, TypeError):
            logging.warning('Storage loading: Scening: failed to parse Frame 1.')

        if self.first_frame is not None:
            self.toggle_first_frame_button.setChecked(True)

        try:
            second_frame = state['second_frame']
            if second_frame is not None and not isinstance(second_frame, Frame):
                raise TypeError
            self.second_frame = second_frame
        except (KeyError, TypeError):
            logging.warning('Storage loading: Scening: failed to parse Frame 2.')

        if self.second_frame is not None:
            self.toggle_second_frame_button.setChecked(True)

        self.scening_update_status_label()
        self.check_add_to_list_possibility()

        try_load(
            state, 'label', str, self.label_lineedit.setText,
            'Storage loading: Scening: failed to parse label.'
        )
        try_load(
            state, 'scening_export_template', str,
            self.export_template_lineedit.setText,
            'Storage loading: Scening: failed to parse export template.'
        )
