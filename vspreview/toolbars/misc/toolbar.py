from __future__ import annotations

import yaml
from pathlib import Path
from functools import partial
from typing import Any, Mapping

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLineEdit, QHBoxLayout, QPushButton, QCheckBox, QLabel, QFileDialog

from ...core.types import VideoOutput
from ...core import AbstractMainWindow, AbstractToolbar, Time, try_load
from ...utils import add_shortcut, fire_and_forget, set_qobject_names, set_status_label

from .settings import MiscSettings


class MiscToolbar(AbstractToolbar):
    _storable_attrs = ('settings', 'visibility')

    __slots__ = (
        *_storable_attrs, 'autosave_timer', 'reload_script_button',
        'save_button', 'autosave_checkbox',
        'keep_on_top_checkbox', 'save_template_lineedit',
        'show_debug_checkbox', 'save_frame_as_button',
        'toggle_button', 'save_file_types', 'copy_frame_button'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, 'Misc', MiscSettings())
        self.setup_ui()

        self.save_template_lineedit.setText(self.main.SAVE_TEMPLATE)

        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.save)

        self.save_file_types = {'Single Image (*.png)': self.save_as_png}

        main.reload_signal.connect(self.autosave_timer.stop)

        self.reload_script_button.clicked.connect(self.main.reload_script)
        self.save_button.clicked.connect(partial(self.save, manually=True))
        self.keep_on_top_checkbox.stateChanged.connect(self.on_keep_on_top_changed)
        self.copy_frame_button.clicked.connect(self.copy_frame_to_clipboard)
        self.save_frame_as_button.clicked.connect(self.on_save_frame_as_clicked)
        self.show_debug_checkbox.stateChanged.connect(self.on_show_debug_changed)
        self.main.settings.autosave_control.valueChanged.connect(self.on_autosave_interval_changed)

        add_shortcut(Qt.CTRL + Qt.Key_R, self.main.reload_script)
        add_shortcut(Qt.ALT + Qt.Key_S, self.save_button.click)
        add_shortcut(Qt.CTRL + Qt.Key_S, self.copy_frame_button.click)
        add_shortcut(Qt.CTRL + Qt.SHIFT + Qt.Key_S, self.save_frame_as_button.click)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setObjectName('MiscToolbar.setup_ui.layout')
        layout.setContentsMargins(0, 0, 0, 0)

        self.reload_script_button = QPushButton(self)
        self.reload_script_button.setText('Reload Script')
        layout.addWidget(self.reload_script_button)

        self.save_button = QPushButton(self)
        self.save_button.setText('Save')
        layout.addWidget(self.save_button)

        self.autosave_checkbox = QCheckBox(self)
        self.autosave_checkbox.setText('Autosave')
        self.autosave_checkbox.setEnabled(True)
        self.autosave_checkbox.setChecked(True)
        layout.addWidget(self.autosave_checkbox)

        self.keep_on_top_checkbox = QCheckBox(self)
        self.keep_on_top_checkbox.setText('Keep on Top')
        self.keep_on_top_checkbox.setEnabled(False)
        layout.addWidget(self.keep_on_top_checkbox)

        self.copy_frame_button = QPushButton(self)
        self.copy_frame_button.setText('Copy Frame')
        layout.addWidget(self.copy_frame_button)

        self.save_frame_as_button = QPushButton(self)
        self.save_frame_as_button.setText('Save Frame as')
        layout.addWidget(self.save_frame_as_button)

        save_template_label = QLabel(self)
        save_template_label.setObjectName('MiscToolbar.setup_ui.save_template_label')
        save_template_label.setText('Save file name template:')
        layout.addWidget(save_template_label)

        self.save_template_lineedit = QLineEdit(self)
        self.save_template_lineedit.setToolTip(
            r'Available placeholders: {format}, {fps_den}, {fps_num}, {frame},'
            r' {height}, {index}, {matrix}, {primaries}, {range},'
            r' {script_name}, {total_frames}, {transfer}, {width}.'
            r' Frame props can be accessed as well using their names.')
        layout.addWidget(self.save_template_lineedit)

        layout.addStretch()
        layout.addStretch()

        self.show_debug_checkbox = QCheckBox(self)
        self.show_debug_checkbox.setText('Show Debug Toolbar')
        layout.addWidget(self.show_debug_checkbox)

    def copy_frame_to_clipboard(self) -> None:
        frame_pixmap = self.main.current_output.graphics_scene_item.pixmap()
        self.main.clipboard.setPixmap(frame_pixmap)
        self.main.show_message('Current frame successfully copied to clipboard')

    @fire_and_forget
    @set_status_label(label='Saving')
    def save(self, path: Path | None = None) -> None:
        self.save_sync(path)

    def save_sync(self, path: Path | None = None, manually: bool = False) -> None:
        yaml.Dumper.ignore_aliases = lambda *args: True

        if path is None:
            vsp_dir = self.main.config_dir
            vsp_dir.mkdir(exist_ok=True)
            path = vsp_dir / (self.main.script_path.stem + '.yml')

        backup_paths = [
            path.with_suffix(f'.old{i}.yml')
            for i in range(self.main.STORAGE_BACKUPS_COUNT, 0, -1)
        ] + [path]
        for dest_path, src_path in zip(backup_paths[:-1], backup_paths[1:]):
            if src_path.exists():
                src_path.replace(dest_path)

        with path.open(mode='w', newline='\n') as f:
            f.write(f'# VSPreview storage for {self.main.script_path}\n')
            yaml.dump(self.main, f, indent=4, default_flow_style=False)

        if manually:
            self.main.show_message('Saved successfully')

    def on_autosave_interval_changed(self, new_value: Time | None) -> None:
        if new_value is None:
            return
        if new_value == Time(seconds=0):
            self.autosave_timer.stop()
        else:
            self.autosave_timer.start(round(float(new_value) * 1000))

    def on_keep_on_top_changed(self, state: Qt.CheckState) -> None:
        if state == Qt.Checked:
            pass
            # self.main.setWindowFlag(Qt.X11BypassWindowManagerHint)
            # self.main.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        elif state == Qt.Unchecked:
            self.main.setWindowFlag(Qt.WindowStaysOnTopHint, False)

    def on_save_frame_as_clicked(self, checked: bool | None = None) -> None:
        fmt = self.main.current_output.source.clip.format
        assert fmt

        filter_str = ''.join(
            [file_type + ';;' for file_type in self.save_file_types.keys()]
        )
        filter_str = filter_str[0:-2]

        template = self.main.toolbars.misc.save_template_lineedit.text()
        frame_props = self.main.current_output.prepared.clip.get_frame(self.main.current_frame.value).props
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
            str(path), 'PNG', self.settings.png_compression_level
        )

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self._storable_attrs
        } | {
            'save_file_name_template': self.save_template_lineedit.text(),
            'show_debug': self.show_debug_checkbox.isChecked()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'save_file_name_template', str, self.save_template_lineedit.setText)
        try_load(state, 'show_debug', bool, self.show_debug_checkbox.setChecked)
        try_load(state, 'visibility', bool, self.on_toggle)
        try_load(state, 'settings', MiscSettings, self.__setattr__)
