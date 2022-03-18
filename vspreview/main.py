from __future__ import annotations

import os
import sys
import shlex
import logging
import vapoursynth as vs
from pathlib import Path
from platform import python_version
from pkg_resources import get_distribution
from typing import Any, cast, List, Mapping, Tuple

from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QEvent, QObject
from PyQt5.QtGui import QCloseEvent, QPalette, QPixmap, QShowEvent
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QWidget, QHBoxLayout, QPushButton, QApplication, QGraphicsScene,
    QOpenGLWidget, QTabWidget, QComboBox, QCheckBox, QSpinBox, QSizePolicy, QGraphicsView
)

# import vspreview.cores as early as possible:
# This is so other modules cannot accidentally
# use and lock us into a different policy.
from .core.vsenv import get_policy
from .models import VideoOutputs, Outputs
from .widgets import ComboBox, StatusBar, TimeEdit, Timeline, FrameEdit
from .utils import add_shortcut, get_usable_cpus_count, qt_silent_call, set_qobject_names, try_load
from .core import (
    AbstractMainWindow, AbstractToolbar, AbstractToolbars, AbstractAppSettings,
    Frame, FrameInterval, VideoOutput, Time, TimeInterval, QYAMLObjectSingleton,
)


class ScriptErrorDialog(QDialog):
    __slots__ = ('main', 'label', 'reload_button', 'exit_button')

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window, Qt.Dialog)
        self.main = main_window

        self.setWindowTitle('Script Loading Error')
        self.setModal(True)

        self.setup_ui()

        self.reload_button.clicked.connect(self.on_reload_clicked)
        self.exit_button.clicked.connect(self.on_exit_clicked)

        add_shortcut(Qt.CTRL + Qt.Key_R, self.reload_button.click, self)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName('ScriptErrorDialog.setup_ui.main_layout')

        self.label = QLabel()
        main_layout.addWidget(self.label)

        buttons_widget = QWidget(self)
        buttons_widget.setObjectName('ScriptErrorDialog.setup_ui.buttons_widget')
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setObjectName('ScriptErrorDialog.setup_uibuttons_layout')

        self.reload_button = QPushButton(self)
        self.reload_button.setText('Reload')
        buttons_layout.addWidget(self.reload_button)

        self.exit_button = QPushButton(self)
        self.exit_button.setText('Exit')
        buttons_layout.addWidget(self.exit_button)

        main_layout.addWidget(buttons_widget)

    def on_reload_clicked(self, clicked: bool | None = None) -> None:
        self.hide()
        self.main.reload_script()

    def on_exit_clicked(self, clicked: bool | None = None) -> None:
        self.hide()
        self.main.save_on_exit = False
        self.main.app.exit()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.on_exit_clicked()


class SettingsDialog(AbstractAppSettings):
    __slots__ = (
        'main', 'tab_widget',
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window)

        self.main = main_window
        self.setWindowTitle('Settings')

        self.setup_ui()

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setObjectName('SettingsDialog.setup_ui.layout')

        self.tab_widget = QTabWidget(self)
        layout.addWidget(self.tab_widget)

    def addTab(self, widget: QWidget, label: str) -> int:
        return self.tab_widget.addTab(widget, label)


class MainToolbar(AbstractToolbar):
    __slots__ = (
        'outputs', 'zoom_levels',
        'outputs_combobox', 'frame_control', 'copy_frame_button',
        'time_control', 'copy_timestamp_button', 'zoom_combobox',
        'switch_timeline_mode_button',
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        from vspreview.models import ZoomLevels

        super().__init__(main_window, 'Main', main_window.settings)
        self.setup_ui()

        self.outputs = VideoOutputs()

        self.outputs_combobox.setModel(self.outputs)
        self.zoom_levels = ZoomLevels([
            0.25, 0.5, 0.68, 0.75, 0.85, 1.0, 1.5, 2.0,
            4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0, 32.0
        ])
        self.zoom_combobox.setModel(self.zoom_levels)
        self.zoom_combobox.setCurrentIndex(3)

        self.outputs_combobox.currentIndexChanged.connect(self.main.switch_output)
        self.frame_control.valueChanged.connect(self.main.switch_frame)
        self.time_control.valueChanged.connect(self.main.switch_frame)
        self.copy_frame_button.clicked.connect(self.on_copy_frame_button_clicked)
        self.copy_timestamp_button.clicked.connect(self.on_copy_timestamp_button_clicked)
        self.zoom_combobox.currentTextChanged.connect(self.on_zoom_changed)
        self.switch_timeline_mode_button.clicked.connect(self.on_switch_timeline_mode_clicked)
        self.settings_button.clicked.connect(self.main.app_settings.show)

        add_shortcut(Qt.Key_1, lambda: self.main.switch_output(0))
        add_shortcut(Qt.Key_2, lambda: self.main.switch_output(1))
        add_shortcut(Qt.Key_3, lambda: self.main.switch_output(2))
        add_shortcut(Qt.Key_4, lambda: self.main.switch_output(3))
        add_shortcut(Qt.Key_5, lambda: self.main.switch_output(4))
        add_shortcut(Qt.Key_6, lambda: self.main.switch_output(5))
        add_shortcut(Qt.Key_7, lambda: self.main.switch_output(6))
        add_shortcut(Qt.Key_8, lambda: self.main.switch_output(7))
        add_shortcut(Qt.Key_9, lambda: self.main.switch_output(8))
        add_shortcut(Qt.Key_0, lambda: self.main.switch_output(9))
        add_shortcut(Qt.Key_S, self.sync_outputs_checkbox.click)
        add_shortcut(
            Qt.CTRL + Qt.Key_Tab,
            lambda: self.main.switch_output(self.outputs_combobox.currentIndex() + 1)
        )
        add_shortcut(
            Qt.CTRL + Qt.SHIFT + Qt.Key_Tab,
            lambda: self.main.switch_output(self.outputs_combobox.currentIndex() - 1)
        )
        add_shortcut(Qt.Key_V, self.on_copy_frame_button_clicked)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        self.setVisible(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.outputs_combobox = ComboBox[VideoOutput](self)
        self.outputs_combobox.setEditable(True)
        self.outputs_combobox.setInsertPolicy(QComboBox.InsertAtCurrent)
        self.outputs_combobox.setDuplicatesEnabled(True)
        self.outputs_combobox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.outputs_combobox.view().setMinimumWidth(
            self.outputs_combobox.minimumSizeHint().width()
        )
        layout.addWidget(self.outputs_combobox)

        self.frame_control = FrameEdit[Frame](self)
        layout.addWidget(self.frame_control)

        self.copy_frame_button = QPushButton(self)
        self.copy_frame_button.setText('⎘')
        layout.addWidget(self.copy_frame_button)

        self.time_control = TimeEdit[Time](self)
        layout.addWidget(self.time_control)

        self.copy_timestamp_button = QPushButton(self)
        self.copy_timestamp_button.setText('⎘')
        layout.addWidget(self.copy_timestamp_button)

        self.sync_outputs_checkbox = QCheckBox(self)
        self.sync_outputs_checkbox.setText('Sync Outputs')
        self.sync_outputs_checkbox.setChecked(self.main.SYNC_OUTPUTS)
        layout.addWidget(self.sync_outputs_checkbox)

        self.zoom_combobox = ComboBox[float](self)
        self.zoom_combobox.setMinimumContentsLength(4)
        layout.addWidget(self.zoom_combobox)

        self.switch_timeline_mode_button = QPushButton(self)
        self.switch_timeline_mode_button.setText('Switch Timeline Mode')
        layout.addWidget(self.switch_timeline_mode_button)

        self.settings_button = QPushButton(self)
        self.settings_button.setText('Settings')
        layout.addWidget(self.settings_button)

        layout.addStretch()

        self.toggle_button.setVisible(False)

    def on_current_frame_changed(self, frame: Frame) -> None:
        qt_silent_call(self.frame_control.setValue, frame)
        qt_silent_call(self.time_control.setValue, Time(frame))

        if self.sync_outputs_checkbox.isChecked():
            for output in self.main.outputs:
                output.frame_to_show = frame

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.outputs_combobox.setCurrentIndex, index)
        qt_silent_call(self.frame_control.setMaximum, self.main.current_output.end_frame)
        qt_silent_call(self.time_control.setMaximum, self.main.current_output.end_time)

    def rescan_outputs(self) -> None:
        self.outputs = VideoOutputs()
        self.main.init_outputs()
        self.outputs_combobox.setModel(self.outputs)

    def on_copy_frame_button_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(str(self.main.current_frame))
        self.main.show_message('Current frame number copied to clipboard')

    def on_copy_timestamp_button_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(self.time_control.text())
        self.main.show_message('Current timestamp copied to clipboard')

    def on_switch_timeline_mode_clicked(self, checked: bool | None = None) -> None:
        if self.main.timeline.mode == self.main.timeline.Mode.TIME:
            self.main.timeline.mode = self.main.timeline.Mode.FRAME
        elif self.main.timeline.mode == self.main.timeline.Mode.FRAME:
            self.main.timeline.mode = self.main.timeline.Mode.TIME

    def on_sync_outputs_changed(self, state: Qt.CheckState) -> None:
        if state == Qt.Checked:
            for output in self.main.outputs:
                output.frame_to_show = self.main.current_frame
        if state == Qt.Unchecked:
            for output in self.main.outputs:
                output.frame_to_show = None

    def on_zoom_changed(self, text: str | None = None) -> None:
        self.main.graphics_view.setZoom(self.zoom_combobox.currentData())

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'current_output_index': self.outputs_combobox.currentIndex(),
            'outputs': self.outputs,
            'sync_outputs': self.sync_outputs_checkbox.isChecked()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            outputs = state['outputs']
            if not isinstance(outputs, Outputs):
                raise TypeError
            self.outputs = cast(VideoOutputs, outputs)
            self.main.init_outputs()
            self.outputs_combobox.setModel(self.outputs)

        except (KeyError, TypeError):
            logging.warning('Storage loading: Main toolbar: failed to parse outputs.')

        try_load(
            state, 'current_output_index', int, self.main.switch_output,
            'Storage loading: Main toolbar: failed to parse output index.'
        )

        try_load(
            state, 'sync_outputs', bool, self.sync_outputs_checkbox.setChecked,
            'Storage loading: Main toolbar: failed to parse sync outputs.'
        )


class Toolbars(AbstractToolbars):
    yaml_tag = '!Toolbars'

    def __init__(self, main_window: AbstractMainWindow) -> None:
        from vspreview.toolbars import (
            DebugToolbar, MiscToolbar, PlaybackToolbar, SceningToolbar,
            BenchmarkToolbar, PipetteToolbar
        )

        self.main = MainToolbar(main_window)
        self.main.setObjectName('Toolbars.main')

        self.misc = MiscToolbar(main_window)
        self.playback = PlaybackToolbar(main_window)
        self.scening = SceningToolbar(main_window)
        self.pipette = PipetteToolbar(main_window)
        self.benchmark = BenchmarkToolbar(main_window)
        self.debug = DebugToolbar(main_window)

        self.misc.setObjectName('Toolbars.misc')
        self.playback.setObjectName('Toolbars.playback')
        self.scening.setObjectName('Toolbars.scening')
        self.pipette.setObjectName('Toolbars.pipette')
        self.benchmark.setObjectName('Toolbars.benchmark')
        self.debug.setObjectName('Toolbars.debug')

    def __getstate__(self) -> Mapping[str, Mapping[str, Any]]:
        return {
            toolbar_name: getattr(self, toolbar_name).__getstate__()
            for toolbar_name in self.all_toolbars_names
        }

    def __setstate__(self, state: Mapping[str, Mapping[str, Any]]) -> None:
        for toolbar_name in self.all_toolbars_names:
            try:
                storage = state[toolbar_name]
                if not isinstance(storage, Mapping):
                    raise TypeError
                getattr(self, toolbar_name).__setstate__(storage)
            except (KeyError, TypeError):
                logging.warning(f'Storage loading: failed to parse storage of {toolbar_name}.')


class MainSettings(QWidget, QYAMLObjectSingleton):
    yaml_tag = '!MainSettings'

    __slots__ = (
        'autosave_control', 'base_ppi_spinbox', 'dark_theme_checkbox',
        'opengl_rendering_checkbox', 'output_index_spinbox',
        'png_compressing_spinbox', 'statusbar_timeout_control',
        'timeline_notches_margin_spinbox',
    )

    def __init__(self) -> None:
        super().__init__()

        self.setup_ui()

        self.set_defaults()

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setObjectName('MainSettings.setup_ui.layout')

        autosave_layout = QHBoxLayout()
        autosave_layout.setObjectName('MainSettings.setup_ui.autosave_layout')
        layout.addLayout(autosave_layout)

        autosave_label = QLabel(self)
        autosave_label.setObjectName('MainSettings.setup_ui.autosave_label')
        autosave_label.setText('Autosave interval (0 - disable)')
        autosave_layout.addWidget(autosave_label)

        self.autosave_control = TimeEdit[TimeInterval](self)
        autosave_layout.addWidget(self.autosave_control)

        base_ppi_layout = QHBoxLayout()
        base_ppi_layout.setObjectName('MainSettings.setup_ui.base_ppi_layout')
        layout.addLayout(base_ppi_layout)

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
        layout.addWidget(self.dark_theme_checkbox)

        self.opengl_rendering_checkbox = QCheckBox(self)
        self.opengl_rendering_checkbox.setText('OpenGL rendering')
        self.opengl_rendering_checkbox.setEnabled(False)
        layout.addWidget(self.opengl_rendering_checkbox)

        output_index_layout = QHBoxLayout()
        output_index_layout.setObjectName(
            'MainSettings.setup_ui.output_index_layout'
        )
        layout.addLayout(output_index_layout)

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
        layout.addLayout(png_compression_layout)

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
        layout.addLayout(statusbar_timeout_layout)

        statusbar_timeout_label = QLabel(self)
        statusbar_timeout_label.setObjectName(
            'MainSettings.setup_ui.statusbar_timeout_label'
        )
        statusbar_timeout_label.setText('Status bar message timeout')
        statusbar_timeout_layout.addWidget(statusbar_timeout_label)

        self.statusbar_timeout_control = TimeEdit[TimeInterval](self)
        statusbar_timeout_layout.addWidget(self.statusbar_timeout_control)

        timeline_notches_margin_layout = QHBoxLayout()
        timeline_notches_margin_layout.setObjectName(
            'MainSettings.setup_ui.timeline_notches_margin_layout'
        )
        layout.addLayout(timeline_notches_margin_layout)

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

    def set_defaults(self) -> None:
        self.autosave_control.setValue(TimeInterval(seconds=30))
        self.base_ppi_spinbox.setValue(96)
        self.dark_theme_checkbox.setChecked(True)
        self.opengl_rendering_checkbox.setChecked(False)
        self.output_index_spinbox.setValue(0)
        self.png_compressing_spinbox.setValue(0)
        self.statusbar_timeout_control.setValue(TimeInterval(seconds=30))
        self.timeline_notches_margin_spinbox.setValue(20)

    @property
    def autosave_interval(self) -> TimeInterval:
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
    def statusbar_message_timeout(self) -> TimeInterval:
        return self.statusbar_timeout_control.value()

    @property
    def timeline_label_notches_margin(self) -> int:
        return self.timeline_notches_margin_spinbox.value()

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
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'autosave_interval', TimeInterval,
            self.autosave_control.setValue,
            ''
        )
        try_load(
            state, 'base_ppi', int,
            self.base_ppi_spinbox.setValue,
            ''
        )
        try_load(
            state, 'dark_theme', bool,
            self.dark_theme_checkbox.setChecked,
            ''
        )
        try_load(
            state, 'opengl_rendering', bool,
            self.opengl_rendering_checkbox.setChecked,
            ''
        )
        try_load(
            state, 'output_index', int,
            self.output_index_spinbox.setValue,
            ''
        )
        try_load(
            state, 'png_compression', int,
            self.png_compressing_spinbox.setValue,
            ''
        )
        try_load(
            state, 'statusbar_message_timeout', TimeInterval,
            self.statusbar_timeout_control.setValue,
            ''
        )
        try_load(
            state, 'timeline_label_notches_margin', int,
            self.timeline_notches_margin_spinbox.setValue,
            ''
        )


class MainWindow(AbstractMainWindow):
    # those are defaults that can be overriden at runtime or used as fallbacks
    AUTOSAVE_INTERVAL = 60 * 1000  # s
    CHECKERBOARD_ENABLED = True
    CHECKERBOARD_TILE_COLOR_1 = Qt.white
    CHECKERBOARD_TILE_COLOR_2 = Qt.lightGray
    CHECKERBOARD_TILE_SIZE = 8  # px
    FPS_AVERAGING_WINDOW_SIZE = FrameInterval(100)
    FPS_REFRESH_INTERVAL = 150  # ms
    LOG_LEVEL = logging.INFO
    OUTPUT_INDEX = 0
    PLAY_BUFFER_SIZE = FrameInterval(get_usable_cpus_count())
    SAVE_TEMPLATE = '{script_name}_{frame}'
    STORAGE_BACKUPS_COUNT = 2
    SYNC_OUTPUTS = True
    SEEK_STEP = 1
    # it's allowed to stretch target interval betweewn notches by N% at most
    TIMELINE_LABEL_NOTCHES_MARGIN = 20  # %
    TIMELINE_MODE = 'frame'
    VSP_DIR_NAME = '.vspreview'
    # used for formats with subsampling
    VS_OUTPUT_RESIZER = VideoOutput.Resizer.Bicubic
    VS_OUTPUT_MATRIX = VideoOutput.Matrix.BT709
    VS_OUTPUT_TRANSFER = VideoOutput.Transfer.BT709
    VS_OUTPUT_PRIMARIES = VideoOutput.Primaries.BT709
    VS_OUTPUT_RANGE = VideoOutput.Range.LIMITED
    VS_OUTPUT_CHROMALOC = VideoOutput.ChromaLoc.LEFT
    VS_OUTPUT_RESIZER_KWARGS = {
        'dither_type': 'error_diffusion',
    }

    # status bar
    def STATUS_FRAME_PROP(prop: Any) -> str:
        return 'Type: %s' % (prop['_PictType'].decode('utf-8') if '_PictType' in prop else '?')

    DEBUG_PLAY_FPS = False
    DEBUG_TOOLBAR = False
    DEBUG_TOOLBAR_BUTTONS_PRINT_STATE = False

    yaml_tag = '!MainWindow'

    storable_attrs = [
        'settings', 'toolbars',
    ]
    __slots__ = storable_attrs + [
        'app', 'display_scale', 'clipboard',
        'script_path', 'save_on_exit', 'timeline', 'main_layout',
        'graphics_scene', 'graphics_view', 'script_error_dialog',
        'central_widget', 'statusbar',
        'opengl_widget',
    ]

    # emit when about to reload a script: clear all existing references to existing clips.
    reload_signal = pyqtSignal()

    def __init__(self, config_dir: Path) -> None:
        super().__init__()

        self.settings = MainSettings()

        # logging
        logging.basicConfig(format='{asctime}: {levelname}: {message}', style='{', level=self.LOG_LEVEL)
        logging.Formatter.default_msec_format = '%s.%03d'

        self.config_dir = config_dir / self.VSP_DIR_NAME

        self.app = QApplication.instance()
        assert self.app

        if self.settings.dark_theme_enabled:
            try:
                from qdarkstyle import load_stylesheet_pyqt5
            except ImportError:
                self.self.settings.dark_theme_enabled = False
            else:
                self.app.setStyleSheet(self.patch_dark_stylesheet(load_stylesheet_pyqt5()))
                self.ensurePolished()

        self.display_scale = self.app.primaryScreen().logicalDotsPerInch() / self.settings.base_ppi
        self.setWindowTitle('VSPreview')
        self.move(400, 0)
        self.setup_ui()

        # global
        self.clipboard = self.app.clipboard()
        self.external_args: List[Tuple[str, str]] = []
        self.script_path = Path()
        self.save_on_exit = True
        self.script_exec_failed = False

        # graphics view
        self.graphics_scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.graphics_scene)
        self.opengl_widget = None

        if self.settings.opengl_rendering_enabled:
            self.opengl_widget = QOpenGLWidget()
            self.graphics_view.setViewport(self.opengl_widget)

        self.graphics_view.wheelScrolled.connect(self.on_wheel_scrolled)

        # timeline
        self.timeline.clicked.connect(self.on_timeline_clicked)

        # init toolbars and outputs
        self.app_settings = SettingsDialog(self)
        self.toolbars = Toolbars(self)
        self.main_layout.addWidget(self.toolbars.main)

        for toolbar in self.toolbars:
            self.main_layout.addWidget(toolbar)
            self.toolbars.main.layout().addWidget(toolbar.toggle_button)

        set_qobject_names(self)
        self.setObjectName('MainWindow')

    def setup_ui(self) -> None:
        from vspreview.widgets import GraphicsView

        self.central_widget = QWidget(self)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.graphics_view = GraphicsView(self.central_widget)
        self.graphics_view.setBackgroundBrush(self.palette().brush(QPalette.Window))
        self.graphics_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.main_layout.addWidget(self.graphics_view)

        self.timeline = Timeline(self.central_widget)
        self.main_layout.addWidget(self.timeline)

        # status bar

        self.statusbar = StatusBar(self.central_widget)

        self.statusbar.total_frames_label = QLabel(self.central_widget)
        self.statusbar.total_frames_label.setObjectName('MainWindow.statusbar.total_frames_label')
        self.statusbar.addWidget(self.statusbar.total_frames_label)

        self.statusbar.duration_label = QLabel(self.central_widget)
        self.statusbar.duration_label.setObjectName('MainWindow.statusbar.duration_label')
        self.statusbar.addWidget(self.statusbar.duration_label)

        self.statusbar.resolution_label = QLabel(self.central_widget)
        self.statusbar.resolution_label.setObjectName('MainWindow.statusbar.resolution_label')
        self.statusbar.addWidget(self.statusbar.resolution_label)

        self.statusbar.pixel_format_label = QLabel(self.central_widget)
        self.statusbar.pixel_format_label.setObjectName('MainWindow.statusbar.pixel_format_label')
        self.statusbar.addWidget(self.statusbar.pixel_format_label)

        self.statusbar.fps_label = QLabel(self.central_widget)
        self.statusbar.fps_label.setObjectName('MainWindow.statusbar.fps_label')
        self.statusbar.addWidget(self.statusbar.fps_label)

        self.statusbar.frame_props_label = QLabel(self.central_widget)
        self.statusbar.frame_props_label.setObjectName('MainWindow.statusbar.frame_props_label')
        self.statusbar.addWidget(self.statusbar.frame_props_label)

        self.statusbar.label = QLabel(self.central_widget)
        self.statusbar.label.setObjectName('MainWindow.statusbar.label')
        self.statusbar.addPermanentWidget(self.statusbar.label)

        self.setStatusBar(self.statusbar)

        # dialogs

        self.script_error_dialog = ScriptErrorDialog(self)

    def patch_dark_stylesheet(self, stylesheet: str) -> str:
        return stylesheet + 'QGraphicsView { border: 0px; padding: 0px; }'

    def load_script(
        self, script_path: Path, external_args: List[Tuple[str, str]] | str = [], reloading: bool = False
    ) -> None:
        from traceback import FrameSummary, TracebackException

        self.toolbars.playback.stop()
        self.setWindowTitle('VSPreview: %s %s' % (script_path, external_args))

        self.statusbar.label.setText('Evaluating')
        self.script_path = script_path
        sys.path.append(str(self.script_path.parent))

        # Rewrite args so external args will be forwarded correctly
        if isinstance(external_args, str):
            self.external_args = shlex.split(external_args)  # type: ignore
        try:
            argv_orig = sys.argv
            sys.argv = [script_path.name] + self.external_args  # type: ignore
        except AttributeError:
            pass

        try:
            exec(
                self.script_path.read_text(encoding='utf-8'), dict([('__file__', sys.argv[0])] + self.external_args)
            )
        except Exception as e:
            self.script_exec_failed = True
            logging.error(e)

            te = TracebackException.from_exception(e)
            # remove the first stack frame, which contains our exec() invocation
            del te.stack[0]

            # replace <string> with script path only for the first stack frames
            # in order to keep intact exec() invocations down the stack
            # that we're not concerned with
            for i, frame in enumerate(te.stack):
                if frame.filename == '<string>':
                    te.stack[i] = FrameSummary(str(self.script_path),
                                               frame.lineno, frame.name)
                else:
                    break
            print(''.join(te.format()))

            self.handle_script_error(
                f'''An error occured while evaluating script:
                \n{str(e)}
                \nSee console output for details.''')
            return
        finally:
            sys.argv = argv_orig
            sys.path.pop()

        self.script_exec_failed = False

        if len(vs.get_outputs()) == 0:
            logging.error('Script has no outputs set.')
            self.handle_script_error('Script has no outputs set.')
            return

        if not reloading:
            self.toolbars.main.rescan_outputs()
            self.toolbars.playback.rescan_outputs()
            self.switch_output(self.OUTPUT_INDEX)

            self.load_storage()
        else:
            self.load_storage()

    def load_storage(self) -> None:
        import yaml

        vsp_dir = self.config_dir
        storage_path = vsp_dir / (self.script_path.stem + '.yml')

        if not storage_path.exists():
            storage_path = self.script_path.with_suffix('.yml')
        if storage_path.exists():
            try:
                yaml.load(storage_path.open(), Loader=yaml.Loader)
            except yaml.YAMLError as exc:
                if isinstance(exc, yaml.MarkedYAMLError):
                    logging.warning(
                        'Storage parsing failed on line {} column {}. Using defaults.'
                        .format(exc.problem_mark.line + 1, exc.problem_mark.column + 1)
                    )
                else:
                    logging.warning('Storage parsing failed. Using defaults.')
        else:
            logging.info('No storage found. Using defaults.')

        self.statusbar.label.setText('Ready')

    def init_outputs(self) -> None:
        from vspreview.widgets import GraphicsImageItem

        self.graphics_scene.clear()
        for output in self.outputs:
            frame_image = output.render_frame(output.last_showed_frame)

            raw_frame_item = self.graphics_scene.addPixmap(frame_image)
            raw_frame_item.hide()

            output.graphics_scene_item = GraphicsImageItem(raw_frame_item)

    def reload_script(self) -> None:
        import gc

        if not self.script_exec_failed:
            self.toolbars.misc.save_sync()
        for toolbar in self.toolbars:
            if hasattr(toolbar, 'on_script_unloaded'):
                toolbar.on_script_unloaded()

        vs.clear_outputs()

        if self.settings.autosave_control.value() != TimeInterval(seconds=0):
            self.toolbars.misc.save()

        self.graphics_scene.clear()

        self.outputs.clear()
        get_policy().reload_core()
        # make sure old filter graph is freed
        gc.collect()

        vs.clear_outputs()
        self.graphics_scene.clear()
        self.load_script(self.script_path, reloading=True)

        self.show_message('Reloaded successfully')

    def render_frame(self, frame: Frame, output: VideoOutput | None = None) -> QPixmap:
        if output is None:
            output = self.current_output

        return output.render_raw_videoframe(output.prepared.clip.get_frame(int(frame)))

    def switch_frame(
        self, pos: Frame | Time | FrameInterval | TimeInterval | int | None, *, render_frame: bool | vs.VideoFrame = True
    ) -> None:
        if pos is None:
            logging.debug('switch_frame: position is None!')
            return

        frame = Frame(pos)

        if frame > self.current_output.end_frame:
            return

        self.current_output.last_showed_frame = frame

        self.timeline.set_position(frame)
        self.toolbars.main.on_current_frame_changed(frame)
        for toolbar in self.toolbars:
            if hasattr(toolbar, 'on_current_frame_changed'):
                toolbar.on_current_frame_changed(frame)

        if render_frame:
            if isinstance(render_frame, vs.VideoFrame):
                rendered_frame = self.current_output.render_raw_videoframe(render_frame)
            else:
                rendered_frame = self.render_frame(frame)

            self.current_output.graphics_scene_item.setPixmap(rendered_frame)

        self.statusbar.frame_props_label.setText(MainWindow.STATUS_FRAME_PROP(self.current_output.cur_frame[0].props))

    def switch_output(self, value: int | VideoOutput) -> None:
        if len(self.outputs) == 0:
            return
        if isinstance(value, VideoOutput):
            index = self.outputs.index_of(value)
        else:
            index = value

        if index < 0 or index >= len(self.outputs):
            return

        prev_index = self.toolbars.main.outputs_combobox.currentIndex()

        self.toolbars.playback.stop()

        # current_output relies on outputs_combobox
        self.toolbars.main.on_current_output_changed(index, prev_index)
        self.timeline.set_end_frame(self.current_output.end_frame)

        if self.current_output.frame_to_show is not None:
            self.current_frame = self.current_output.frame_to_show
        else:
            self.current_frame = self.current_output.last_showed_frame

        for output in self.outputs:
            output.graphics_scene_item.hide()

        self.current_output.graphics_scene_item.show()
        self.graphics_scene.setSceneRect(QRectF(self.current_output.graphics_scene_item.pixmap().rect()))
        self.timeline.update_notches()

        for toolbar in self.toolbars:
            if hasattr(toolbar, 'on_current_output_changed'):
                toolbar.on_current_output_changed(index, prev_index)

        self.update_statusbar_output_info()

    @property  # type: ignore
    def current_output(self) -> VideoOutput:  # type: ignore
        return cast(VideoOutput, self.toolbars.main.outputs_combobox.currentData())

    @current_output.setter
    def current_output(self, value: VideoOutput) -> None:
        self.switch_output(self.outputs.index_of(value))

    @property  # type: ignore
    def current_frame(self) -> Frame:  # type: ignore
        return self.current_output.last_showed_frame

    @current_frame.setter
    def current_frame(self, value: Frame) -> None:
        self.switch_frame(value)

    @property
    def outputs(self) -> VideoOutputs:  # type: ignore
        return self.toolbars.main.outputs  # type: ignore

    def handle_script_error(self, message: str) -> None:
        self.script_error_dialog.label.setText(message)
        self.script_error_dialog.open()

    def on_wheel_scrolled(self, steps: int) -> None:
        new_index = self.toolbars.main.zoom_combobox.currentIndex() + steps
        if new_index < 0:
            new_index = 0
        elif new_index >= len(self.toolbars.main.zoom_levels):
            new_index = len(self.toolbars.main.zoom_levels) - 1
        self.toolbars.main.zoom_combobox.setCurrentIndex(new_index)

    def on_timeline_clicked(self, start: int) -> None:
        if self.toolbars.playback.play_timer.isActive():
            self.toolbars.playback.stop()
            self.switch_frame(start)
            self.toolbars.playback.play()
        else:
            self.switch_frame(start)

    def show_message(self, message: str) -> None:
        self.statusbar.showMessage(
            message,
            round(float(self.settings.statusbar_message_timeout) * 1000)
        )

    def update_statusbar_output_info(self, output: VideoOutput | None = None) -> None:
        if output is None:
            output = self.current_output

        fmt = output.source.clip.format
        assert fmt

        self.statusbar.total_frames_label.setText('{} frames '.format(output.total_frames))
        self.statusbar.duration_label.setText('{} '.format(output.total_time))
        self.statusbar.resolution_label.setText('{}x{} '.format(output.width, output.height))
        self.statusbar.pixel_format_label.setText('{} '.format(fmt.name))
        if output.fps_den != 0:
            self.statusbar.fps_label.setText('{}/{} = {:.3f} fps '.format(output.fps_num,
                                             output.fps_den, output.fps_num / output.fps_den))
        else:
            self.statusbar.fps_label.setText('{}/{} fps '.format(output.fps_num, output.fps_den))

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.LayoutRequest:
            self.timeline.full_repaint()

        return super().event(event)

    # misc methods

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.graphics_view.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.settings.autosave_control.value() != TimeInterval(seconds=0) and self.save_on_exit:
            self.toolbars.misc.save()

        self.reload_signal.emit()

    def __getstate__(self) -> Mapping[str, Any]:
        state = {
            attr_name: getattr(self, attr_name)
            for attr_name in self.storable_attrs
        }
        state.update({
            'timeline_mode': self.timeline.mode,
            'window_geometry': self.saveGeometry(),
            'window_state': self.saveState(),
        })
        return state

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        # toolbars is singleton, so it initialize itself right in its __setstate__()

        self.timeline.mode = self.TIMELINE_MODE

        try_load(
            state, 'timeline_mode', str, self.timeline.mode,
            'Storage loading: failed to parse timeline mode. Using default.'
        )

        try_load(
            state, 'window_geometry', bytes, self.restoreGeometry,
            'Storage loading: failed to parse window geometry. Using default.'
        )

        try_load(
            state, 'window_state', bytes, self.restoreState,
            'Storage loading: failed to parse window state. Using default.'
        )


class Application(QApplication):
    def notify(self, obj: QObject, event: QEvent) -> bool:
        isex = False
        try:
            return QApplication.notify(self, obj, event)
        except Exception:
            isex = True
            logging.error('Application: unexpected error')
            print(*sys.exc_info())
            return False
        finally:
            if isex:
                self.quit()


def main() -> None:
    from argparse import ArgumentParser

    logging.basicConfig(format='{asctime}: {levelname}: {message}',
                        style='{', level=MainWindow.LOG_LEVEL)
    logging.Formatter.default_msec_format = '%s.%03d'

    check_versions()

    parser = ArgumentParser()
    parser.add_argument('script_path', help='Path to Vapoursynth script',
                        type=Path, nargs='?')
    parser.add_argument('-c', '--preserve-cwd', action='store_true',
                        help='do not chdir to script parent directory')
    parser.add_argument('-a', '--arg', type=str, action='append', metavar='key=value',
                        help='Argument to pass to the script environment')
    args = parser.parse_args()

    if args.script_path is None:
        print('Script path required.')
        sys.exit(1)

    script_path = args.script_path.resolve()
    if not script_path.exists():
        print('Script path is invalid.')
        sys.exit(1)

    if not args.preserve_cwd:
        os.chdir(script_path.parent)
    app = Application(sys.argv)
    main_window = MainWindow(Path(os.getcwd()) if args.preserve_cwd else script_path.parent)
    main_window.load_script(script_path, [
        tuple(a.split('=', maxsplit=1)) for a in args.arg or []
    ], False)
    main_window.show()

    try:
        app.exec_()
    except Exception:
        logging.error('app.exec_() exception')


def check_versions() -> bool:
    if sys.version_info < (3, 9, 0, 'final', 0):
        logging.warning(
            'VSPreview is not tested on Python versions prior to 3.9, but you have {} {}. Use at your own risk.'
            .format(python_version(), sys.version_info.releaselevel)
        )
        return False

    if get_distribution('PyQt5').version < '5.15':
        logging.warning(
            'VSPreview is not tested on PyQt5 versions prior to 5.15, but you have {}. Use at your own risk.'
            .format(get_distribution('PyQt5').version))
        return False

    if vs.core.version_number() < 53:
        logging.warning(
            'VSPreview is not tested on VapourSynth versions prior to 53, but you have {}. Use at your own risk.'
            .format(vs.core.version_number())
        )
        return False

    return True


if __name__ == '__main__':
    main()
