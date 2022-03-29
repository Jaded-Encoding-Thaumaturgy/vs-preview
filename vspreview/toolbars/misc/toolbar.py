from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Any, Mapping

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QFileDialog

from ...core.types import VideoOutput
from ...utils import add_shortcut, set_qobject_names
from ...core import AbstractMainWindow, AbstractToolbar, Time, try_load, PushButton, LineEdit, CheckBox

from .settings import MiscSettings


class MiscToolbar(AbstractToolbar):
    __slots__ = (
        'autosave_timer', 'reload_script_button',
        'save_button', 'autosave_checkbox',
        'keep_on_top_checkbox', 'save_template_lineedit',
        'show_debug_checkbox', 'save_frame_as_button',
        'toggle_button', 'save_file_types', 'copy_frame_button'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, MiscSettings())

        self.setup_ui()

        self.autosave_timer = QTimer(timeout=self.main.dump_storage_async)

        self.save_file_types = {'Single Image (*.png)': self.save_as_png}

        self.main.reload_signal.connect(self.autosave_timer.stop)
        self.main.settings.autosave_control.valueChanged.connect(self.on_autosave_interval_changed)

        self.add_shortcuts()

        set_qobject_names(self)

    def setup_ui(self) -> None:
        super().setup_ui()

        self.reload_script_button = PushButton('Reload Script', self, clicked=self.main.reload_script)

        self.save_button = PushButton('Save', self, clicked=partial(self.main.dump_storage_async, manually=True))

        self.autosave_checkbox = CheckBox('Autosave', self, checked=True)

        self.keep_on_top_checkbox = CheckBox('Keep on Top', self, clicked=self.on_keep_on_top_changed)

        self.copy_frame_button = PushButton('Copy Frame', self, clicked=self.copy_frame_to_clipboard)

        self.save_frame_as_button = PushButton('Save Frame as', self, clicked=self.on_save_frame_as_clicked)

        self.save_template_lineedit = LineEdit(
            self.main.SAVE_TEMPLATE, self, tooltip=(
                r'Available placeholders: {format}, {fps_den}, {fps_num}, {frame},\n'
                r' {height}, {index}, {matrix}, {primaries}, {range},\n'
                r' {script_name}, {total_frames}, {transfer}, {width}.\n'
                r' Frame props can be accessed as well using their names.\n'
            )
        )
        self.hlayout.addWidgets([
            self.reload_script_button,
            self.save_button, self.autosave_checkbox, self.keep_on_top_checkbox,
            self.copy_frame_button, self.save_frame_as_button,
            QLabel('Save file name template:'), self.save_template_lineedit
        ])

        self.hlayout.addStretch()

        self.show_debug_checkbox = CheckBox('Show Debug Toolbar', self, stateChanged=self.on_show_debug_changed)

        self.hlayout.addWidget(self.show_debug_checkbox)

    def add_shortcuts(self) -> None:
        add_shortcut(Qt.CTRL + Qt.Key_R, self.main.reload_script)
        add_shortcut(Qt.ALT + Qt.Key_S, self.save_button.click)
        add_shortcut(Qt.CTRL + Qt.Key_S, self.copy_frame_button.click)
        add_shortcut(Qt.CTRL + Qt.SHIFT + Qt.Key_S, self.save_frame_as_button.click)

    def copy_frame_to_clipboard(self) -> None:
        self.main.clipboard.setPixmap(
            self.main.current_output.graphics_scene_item.pixmap()
        )
        self.main.show_message('Current frame successfully copied to clipboard')

    def on_autosave_interval_changed(self, new_value: Time | None) -> None:
        if new_value is None:
            return
        if new_value == Time(seconds=0):
            self.autosave_timer.stop()
        else:
            self.autosave_timer.start(round(float(new_value) * 1000))

    def on_keep_on_top_changed(self, state: Qt.CheckState) -> None:
        # if state == Qt.Checked:
        #     self.main.setWindowFlag(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint, True)
        # elif state == Qt.Unchecked:
        #     self.main.setWindowFlag(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint, False)
        ...

    def on_save_frame_as_clicked(self, checked: bool | None = None) -> None:
        fmt = self.main.current_output.source.clip.format
        assert fmt

        filter_str = ''.join([file_type + ';;' for file_type in self.save_file_types.keys()])[0:-2]

        template = self.main.toolbars.misc.save_template_lineedit.text()

        frame_props = self.main.current_output.props
        substitutions = {
            **frame_props,
            'format': fmt.name,
            'fps_den': self.main.current_output.fps_den,
            'fps_num': self.main.current_output.fps_num,
            'frame': self.main.current_frame,
            'height': self.main.current_output.height,
            'index': self.main.current_output.index,
            'matrix': VideoOutput.Matrix.values[int(str(frame_props['_Matrix']))],
            'primaries': VideoOutput.Primaries.values[int(str(frame_props['_Primaries']))],
            'range': VideoOutput.Range.values[int(str(frame_props['_ColorRange']))],
            'script_name': self.main.script_path.stem,
            'total_frames': self.main.current_output.total_frames,
            'transfer': VideoOutput.Transfer.values[int(str(frame_props['_Transfer']))],
            'width': self.main.current_output.width,
        }
        try:
            suggested_path_str = template.format(**substitutions)
        except ValueError:
            suggested_path_str = self.main.SAVE_TEMPLATE.format(**substitutions)
            self.main.show_message('Save name template is invalid')

        save_path_str, file_type = QFileDialog.getSaveFileName(
            self.main, 'Save as', suggested_path_str, filter_str
        )
        try:
            self.save_file_types[file_type](Path(save_path_str))
        except KeyError:
            pass

    def on_show_debug_changed(self, state: Qt.CheckState) -> None:
        if state == Qt.Checked:
            self.main.toolbars.debug.toggle_button.setVisible(True)
        elif state == Qt.Unchecked:
            if self.main.toolbars.debug.toggle_button.isChecked():
                self.main.toolbars.debug.toggle_button.click()
            self.main.toolbars.debug.toggle_button.setVisible(False)

    def save_as_png(self, path: Path) -> None:
        self.main.current_output.graphics_scene_item.pixmap().save(
            str(path), 'PNG', self.main.settings.png_compression_level
        )

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'save_file_name_template': self.save_template_lineedit.text(),
            'show_debug': self.show_debug_checkbox.isChecked()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'save_file_name_template', str, self.save_template_lineedit.setText)
        try_load(state, 'show_debug', bool, self.show_debug_checkbox.setChecked)
        super().__setstate__(state)
