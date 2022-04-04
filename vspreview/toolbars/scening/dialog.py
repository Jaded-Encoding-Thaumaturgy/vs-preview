from __future__ import annotations

from PyQt5.QtWidgets import QTableView
from PyQt5.QtCore import Qt, QModelIndex, QItemSelection, QItemSelectionModel

from ...models import SceningList
from ...utils import qt_silent_call
from ...core.custom import TimeEdit, FrameEdit
from ...core import AbstractMainWindow, Frame, Time, VBoxLayout, HBoxLayout, PushButton, LineEdit, ExtendedDialog


class SceningListDialog(ExtendedDialog):
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

        self.set_qobject_names()

    def setup_ui(self) -> None:

        self.name_lineedit = LineEdit(self, textChanged=self.on_name_changed)

        self.tableview = QTableView(self, doubleClicked=self.on_tableview_clicked)
        self.tableview.setSelectionMode(QTableView.SingleSelection)
        self.tableview.setSelectionBehavior(QTableView.SelectRows)
        self.tableview.setSizeAdjustPolicy(QTableView.AdjustToContents)

        self.start_frame_control = FrameEdit(self, valueChanged=self.on_start_frame_changed)

        self.end_frame_control = FrameEdit(self, valueChanged=self.on_end_frame_changed)

        self.start_time_control = TimeEdit(self, valueChanged=self.on_start_time_changed)

        self.end_time_control = TimeEdit(self, valueChanged=self.on_end_time_changed)

        self.label_lineedit = LineEdit(self, placeholder='Label', textChanged=self.on_label_changed)

        self.add_button = PushButton('Add', self, enabled=False)

        VBoxLayout(self, [
            self.name_lineedit, self.tableview
        ]).addLayout(
            HBoxLayout([
                self.start_frame_control,
                self.end_frame_control,
                self.start_time_control,
                self.end_time_control,
                self.label_lineedit,
                self.add_button
            ])
        )

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
            self.main.switch_frame(self.scening_list.data(index))
        if index.column() == SceningList.START_TIME_COLUMN:
            self.main.switch_frame(self.scening_list.data(index.siblingAtColumn(SceningList.START_FRAME_COLUMN)))
        if index.column() == SceningList.END_TIME_COLUMN:
            self.main.switch_frame(self.scening_list.data(index.siblingAtColumn(SceningList.END_FRAME_COLUMN)))

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
