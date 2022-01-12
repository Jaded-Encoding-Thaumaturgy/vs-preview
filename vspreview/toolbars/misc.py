from __future__ import annotations

import logging
from   pathlib  import Path
from   typing   import Any, Mapping, Optional

from PyQt5 import Qt

from vspreview.core  import (
    AbstractMainWindow, AbstractToolbar, Frame, Output,
)
from vspreview.utils import (
    add_shortcut, debug, fire_and_forget, set_qobject_names, set_status_label,
)


class MiscToolbar(AbstractToolbar):
    storable_attrs : Sequence[str] = []
    __slots__ = storable_attrs + [
        'autosave_timer', 'reload_script_button',
        'save_button',
        'keep_on_top_checkbox', 'save_template_lineedit',
        'show_debug_checkbox', 'save_frame_as_button',
        'toggle_button', 'save_file_types', 'copy_frame_button',
    ]

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, 'Misc')
        self.setup_ui()

        self.save_template_lineedit.setText(self.main.SAVE_TEMPLATE)

        self.autosave_timer = Qt.QTimer()
        self.autosave_timer.timeout.connect(self.save)

        self.save_file_types = {
            'Single Image (*.png)': self.save_as_png,
        }

        self.reload_script_button.     clicked.connect(lambda: self.main.reload_script())  # pylint: disable=unnecessary-lambda
        self.         save_button.     clicked.connect(lambda: self.save(manually=True))
        self.keep_on_top_checkbox.stateChanged.connect(        self.on_keep_on_top_changed)
        self.   copy_frame_button.     clicked.connect(        self.copy_frame_to_clipboard)
        self.save_frame_as_button.     clicked.connect(        self.on_save_frame_as_clicked)
        self. show_debug_checkbox.stateChanged.connect(        self.on_show_debug_changed)

        add_shortcut(Qt.Qt.CTRL + Qt.Qt.Key_R, self.reload_script_button.click)
        add_shortcut(Qt.Qt.ALT + Qt.Qt.Key_S, self.         save_button.click)
        add_shortcut(Qt.Qt.CTRL + Qt.Qt.Key_S, self.   copy_frame_button.click)
        add_shortcut(Qt.Qt.CTRL + Qt.Qt.SHIFT + Qt.Qt.Key_S,
                     self.save_frame_as_button.click)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = Qt.QHBoxLayout(self)
        layout.setObjectName('MiscToolbar.setup_ui.layout')
        layout.setContentsMargins(0, 0, 0, 0)

        self.reload_script_button = Qt.QPushButton(self)
        self.reload_script_button.setText('Reload Script')
        layout.addWidget(self.reload_script_button)

        self.save_button = Qt.QPushButton(self)
        self.save_button.setText('Save')
        layout.addWidget(self.save_button)

        self.keep_on_top_checkbox = Qt.QCheckBox(self)
        self.keep_on_top_checkbox.setText('Keep on Top')
        self.keep_on_top_checkbox.setEnabled(False)
        layout.addWidget(self.keep_on_top_checkbox)

        self.copy_frame_button = Qt.QPushButton(self)
        self.copy_frame_button.setText('Copy Frame')
        layout.addWidget(self.copy_frame_button)

        self.save_frame_as_button = Qt.QPushButton(self)
        self.save_frame_as_button.setText('Save Frame as')
        layout.addWidget(self.save_frame_as_button)

        save_template_label = Qt.QLabel(self)
        save_template_label.setObjectName(
            'MiscToolbar.setup_ui.save_template_label')
        save_template_label.setText('Save file name template:')
        layout.addWidget(save_template_label)

        self.save_template_lineedit = Qt.QLineEdit(self)
        self.save_template_lineedit.setToolTip(
            r'Available placeholders: {format}, {fps_den}, {fps_num}, {frame},'
            r' {height}, {index}, {matrix}, {primaries}, {range},'
            r' {script_name}, {total_frames}, {transfer}, {width}.'
            r' Frame props can be accessed as well using their names.')
        layout.addWidget(self.save_template_lineedit)

        layout.addStretch()
        layout.addStretch()

        self.show_debug_checkbox = Qt.QCheckBox(self)
        self.show_debug_checkbox.setText('Show Debug Toolbar')
        layout.addWidget(self.show_debug_checkbox)

    def on_script_unloaded(self) -> None:
        self.autosave_timer.stop()

    def on_script_loaded(self) -> None:
        self.autosave_timer.start(self.main.AUTOSAVE_INTERVAL)

    def copy_frame_to_clipboard(self) -> None:
        frame_image = self.main.current_output.graphics_scene_item.image()
        self.main.clipboard.setImage(frame_image)
        self.main.show_message('Current frame successfully copied to clipboard')

    @fire_and_forget
    @set_status_label(label='Saving')
    def save(self, path: Optional[Path] = None) -> None:
        self.save_sync(path)

    def save_sync(self, path: Optional[Path] = None) -> None:
        import yaml

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

    def on_keep_on_top_changed(self, state: Qt.Qt.CheckState) -> None:
        if   state == Qt.Qt.Checked:
            pass
            # self.main.setWindowFlag(Qt.Qt.X11BypassWindowManagerHint)
            # self.main.setWindowFlag(Qt.Qt.WindowStaysOnTopHint, True)
        elif state == Qt.Qt.Unchecked:
            self.main.setWindowFlag(Qt.Qt.WindowStaysOnTopHint, False)

    def on_save_frame_as_clicked(self, checked: Optional[bool] = None) -> None:
        filter_str = ''.join(
            [file_type + ';;' for file_type in self.save_file_types.keys()])
        filter_str = filter_str[0:-2]

        template = self.main.toolbars.misc.save_template_lineedit.text()
        frame_props = self.main.current_output.vs_output.get_frame(
                          self.main.current_frame).props
        builtin_substitutions = {
            'format'       : self.main.current_output.format.name,
            'fps_den'      : self.main.current_output.fps_den,
            'fps_num'      : self.main.current_output.fps_num,
            'frame'        : self.main.current_frame,
            'height'       : self.main.current_output.height,
            'index'        : self.main.current_output.index,
            'matrix'       : Output.Matrix.values[frame_props['_Matrix']],
            'primaries'    : Output.Primaries.values[frame_props['_Primaries']],
            'range'        : Output.Range.values[frame_props['_ColorRange']],
            'script_name'  : self.main.script_path.stem,
            'total_frames' : self.main.current_output.total_frames,
            'transfer'     : Output.Transfer.values[frame_props['_Transfer']],
            'width'        : self.main.current_output.width,
        }
        substitutions = dict(frame_props)
        substitutions.update(builtin_substitutions)
        try:
            suggested_path_str = template.format(**substitutions)
        except ValueError:
            suggested_path_str = self.main.SAVE_TEMPLATE.format(**substitutions)
            self.main.show_message('Save name template is invalid')

        save_path_str, file_type = Qt.QFileDialog.getSaveFileName(
            self.main, 'Save as', suggested_path_str, filter_str)
        try:
            self.save_file_types[file_type](Path(save_path_str))
        except KeyError:
            pass

    def on_show_debug_changed(self, state: Qt.Qt.CheckState) -> None:
        if   state == Qt.Qt.Checked:
            self.main.toolbars.debug.toggle_button.setVisible(True)
        elif state == Qt.Qt.Unchecked:
            if self.main.toolbars.debug.toggle_button.isChecked():
                self.main.toolbars.debug.toggle_button.click()
            self.main.toolbars.debug.toggle_button.setVisible(False)

    def save_as_png(self, path: Path) -> None:
        image = self.main.current_output.graphics_scene_item.image()
        image.save(str(path), 'PNG', self.main.PNG_COMPRESSION_LEVEL)

    def __getstate__(self) -> Mapping[str, Any]:
        state = {
            attr_name: getattr(self, attr_name)
            for attr_name in self.storable_attrs
        }
        state.update({
            'save_file_name_template': self.save_template_lineedit.text(),
            'show_debug'             : self.show_debug_checkbox.isChecked()
        })
        state.update(super().__getstate__())
        return state

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            self.save_template_lineedit.setText(
                state['save_file_name_template'])
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: failed to parse save file name template.')

        try:
            show_debug = state['show_debug']
            if not isinstance(show_debug, bool):
                raise TypeError
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: failed to parse show debug flag.')
            show_debug = self.main.DEBUG_TOOLBAR

        self.show_debug_checkbox.setChecked(show_debug)

        super().__setstate__(state)
