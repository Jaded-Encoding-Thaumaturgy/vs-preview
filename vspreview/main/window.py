from __future__ import annotations

import io
import gc
import sys
import yaml
import logging
import vapoursynth as vs
from pathlib import Path
from itertools import count
from os.path import expandvars, expanduser
from traceback import FrameSummary, TracebackException
from typing import Any, cast, List, Mapping, Tuple, Dict

from PyQt5.QtCore import pyqtSignal, QRectF, QEvent
from PyQt5.QtGui import QCloseEvent, QPalette, QShowEvent, QPixmap
from PyQt5.QtWidgets import QLabel, QApplication, QGraphicsScene, QOpenGLWidget, QSizePolicy, QGraphicsView

from ..toolbars import Toolbars
from ..models import VideoOutputs
from ..core.vsenv import get_policy
from ..utils import fire_and_forget, set_status_label
from ..core.custom import StatusBar, GraphicsView, GraphicsImageItem, DragNavigator
from ..core import AbstractMainWindow, Frame, VideoOutput, Time, try_load, VBoxLayout, ExtendedWidget

from .timeline import Timeline
from .settings import MainSettings
from .dialog import ScriptErrorDialog, SettingsDialog


class MainWindow(AbstractMainWindow):
    VSP_DIR_NAME = '.vspreview'
    VSP_GLOBAL_DIR_NAME = Path(
        expandvars('%APPDATA%') if sys.platform == "win32" else expanduser('~/.config')
    )
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
    VSP_VERSION = 2.1
    BREAKING_CHANGES_VERSIONS: List[float] = []

    # status bar
    def STATUS_FRAME_PROP(self, prop: Any) -> str:
        return 'Type: %s' % (prop['_PictType'].decode('utf-8') if '_PictType' in prop else '?')

    EVENT_POLICY = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    storable_attrs = ('settings', 'toolbars')

    __slots__ = (
        *storable_attrs, 'app', 'display_scale', 'clipboard',
        'script_path', 'timeline', 'main_layout',
        'graphics_scene', 'graphics_view', 'script_error_dialog',
        'central_widget', 'statusbar', 'storage_not_found',
        'current_storage_path', 'opengl_widget', 'drag_navigator'
    )

    # emit when about to reload a script: clear all existing references to existing clips.
    reload_signal = pyqtSignal()
    reload_before_signal = pyqtSignal()
    reload_after_signal = pyqtSignal()
    toolbars: Toolbars

    def __init__(self, config_dir: Path) -> None:
        super().__init__()

        self.settings = MainSettings()

        # logging
        logging.basicConfig(format='{asctime}: {levelname}: {message}', style='{', level=self.settings.LOG_LEVEL)
        logging.Formatter.default_msec_format = '%s.%03d'

        self.current_config_dir = config_dir / self.VSP_DIR_NAME
        self.global_config_dir = self.VSP_GLOBAL_DIR_NAME / self.VSP_DIR_NAME
        self.global_storage_path = self.global_config_dir / '.global.yml'

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

        desktop_size = self.app.primaryScreen().size()

        self.move(int(desktop_size.width() * 0.15), int(desktop_size.height() * 0.075))
        self.setup_ui()
        self.storage_not_found = False
        self.script_globals: Dict[str, Any] = dict()

        # global
        self.clipboard = self.app.clipboard()
        self.external_args: List[Tuple[str, str]] = []
        self.script_path = Path()
        self.script_exec_failed = False
        self.current_storage_path = Path()

        # graphics view
        self.graphics_scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.graphics_scene)
        self.opengl_widget = None

        if self.settings.opengl_rendering_enabled:
            self.opengl_widget = QOpenGLWidget()
            self.graphics_view.setViewport(self.opengl_widget)

        self.graphics_view.wheelScrolled.connect(self.on_wheel_scrolled)

        self.graphics_view.registerReloadEvents(self)

        # timeline
        self.timeline.clicked.connect(self.on_timeline_clicked)

        # init toolbars and outputs
        self.app_settings = SettingsDialog(self)  # type: ignore
        self.toolbars = Toolbars(self)

        for toolbar in self.toolbars:
            self.main_layout.addWidget(toolbar)
            self.toolbars.main.layout().addWidget(toolbar.toggle_button)

        self.app_settings.tab_widget.setUsesScrollButtons(False)
        self.app_settings.setMinimumWidth(
            int(len(self.toolbars) * 1.05 * self.app_settings.tab_widget.geometry().width() / 2)
        )

        self.set_qobject_names()
        self.setObjectName('MainWindow')

    def setup_ui(self) -> None:
        self.central_widget = ExtendedWidget(self)
        self.main_layout = VBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.graphics_view = GraphicsView(self.central_widget)
        self.graphics_view.setBackgroundBrush(self.palette().brush(QPalette.Window))
        self.graphics_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)

        self.drag_navigator = DragNavigator(self, self.graphics_view)

        self.timeline = Timeline(self.central_widget)

        self.main_layout.addWidgets([self.graphics_view, self.timeline])

        # status bar
        self.statusbar = StatusBar(self.central_widget)

        for name in self.statusbar.label_names:
            self.statusbar.__setattr__(name, QLabel(self.central_widget))

        self.statusbar.addWidgets([
            getattr(self.statusbar, name) for name in self.statusbar.label_names
        ])

        self.statusbar.addPermanentWidget(self.statusbar.label)

        self.setStatusBar(self.statusbar)

        # dialogs
        self.script_error_dialog = ScriptErrorDialog(self)

    def patch_dark_stylesheet(self, stylesheet: str) -> str:
        return stylesheet + 'QGraphicsView { border: 0px; padding: 0px; }'

    def load_script(
        self, script_path: Path, external_args: List[Tuple[str, str]] | None = None, reloading: bool = False
    ) -> None:
        self.external_args = external_args or []

        self.toolbars.playback.stop()
        self.setWindowTitle('VSPreview: %s %s' % (script_path, self.external_args))

        self.statusbar.label.setText('Evaluating')
        self.script_path = script_path

        sys.path.append(str(self.script_path.parent))

        # Rewrite args so external args will be forwarded correctly
        try:
            argv_orig = sys.argv
            sys.argv = [script_path.name]
        except AttributeError:
            pass

        self.script_globals.clear()
        self.script_globals = dict([('__file__', sys.argv[0])] + self.external_args)

        try:
            ast_compiled = compile(self.script_path.read_bytes(), sys.argv[0], 'exec', optimize=2)

            exec(ast_compiled, self.script_globals)
        except BaseException as e:
            logging.error(e)

            te = TracebackException.from_exception(e)
            # remove the first stack frame, which contains our exec() invocation
            del te.stack[0]

            # replace <string> with script path only for the first stack frames
            # in order to keep intact exec() invocations down the stack
            # that we're not concerned with
            for i, frame in enumerate(te.stack):
                if frame.filename == '<string>':
                    te.stack[i] = FrameSummary(
                        str(self.script_path), frame.lineno, frame.name
                    )
                else:
                    break
            logging.error(''.join(te.format()))

            self.script_exec_failed = True
            return self.handle_script_error(
                '\n'.join([
                    'An error occured while evaluating script:',
                    str(e), 'See console output for details.'
                ])
            )
        finally:
            sys.argv = argv_orig
            sys.path.pop()

        if len(vs.get_outputs()) == 0:
            logging.error('Script has no outputs set.')
            self.script_exec_failed = True
            self.handle_script_error('Script has no outputs set.')
            return

        self.script_exec_failed = False
        self.current_storage_path = (self.current_config_dir / self.script_path.stem).with_suffix('.yml')

        self.storage_not_found = not self.current_storage_path.exists()

        if self.storage_not_found:
            self.load_storage()

        if not reloading:
            self.toolbars.main.rescan_outputs()
            self.toolbars.playback.rescan_outputs()

        if not self.storage_not_found:
            self.load_storage()

        self.toolbars.misc.autosave_timer.start(round(float(self.settings.autosave_interval) * 1000))

        if not reloading:
            self.switch_output(self.settings.output_index)

    @set_status_label('Loading...')
    def load_storage(self) -> None:
        if self.storage_not_found:
            logging.info('No storage found. Using defaults.')
            return

        storage_contents = ''
        broken_storage = False
        global_length = 0
        for i, storage_path in enumerate((self.global_storage_path, self.current_storage_path)):
            try:
                with io.open(storage_path, 'r', encoding='utf-8') as storage_file:
                    version = storage_file.readline()
                    if 'Version' not in version or any({
                        version.endswith(f'@{v}') for v in self.BREAKING_CHANGES_VERSIONS
                    }):
                        raise FileNotFoundError

                    storage_contents += storage_file.read()
                    if i == 0:
                        global_length = storage_contents.count('\n')
            except FileNotFoundError:
                if self.settings.force_old_storages_removal:
                    storage_path.unlink()
                    broken_storage = True
                else:
                    logging.warning(
                        '\n\tThe storage was created on an old version of VSPreview.'
                        '\n\tSave any scening or other important info and delete it.'
                        '\n\tIf you want the program to silently delete old storages, go into settings.'
                    )
                    sys.exit(1)

        if broken_storage:
            return

        loader = yaml.CLoader(storage_contents)
        try:
            loader.get_single_data()
        except yaml.YAMLError as exc:
            if isinstance(exc, yaml.MarkedYAMLError):
                if exc.problem_mark:
                    line = exc.problem_mark.line + 1
                    isglobal = line <= global_length
                    if not isglobal:
                        line -= global_length
                    logging.warning(
                        'Storage ({}) parsing failed on line {} column {}. Exiting...'
                        .format('Global' if isglobal else 'Local', line, exc.problem_mark.column + 1)
                    )
                    sys.exit(1)
            else:
                logging.warning('Storage parsing failed. Using defaults.')
        finally:
            loader.dispose()

    @fire_and_forget
    @set_status_label('Saving...')
    def dump_storage_async(self) -> None:
        self.dump_storage()

    def dump_storage(self, manually: bool = False) -> None:
        if self.script_exec_failed:
            return

        self.current_config_dir.mkdir(0o777, True, True)
        self.global_config_dir.mkdir(0o777, True, True)

        backup_paths = [
            self.current_storage_path.with_suffix(f'.old{i}.yml')
            for i in range(self.toolbars.misc.settings.STORAGE_BACKUPS_COUNT, 0, -1)
        ] + [self.current_storage_path]

        for src_path, dest_path in zip(backup_paths[1:], backup_paths[:-1]):
            if src_path.exists():
                src_path.replace(dest_path)

        storage_dump = self._dump_serialize(self._serialize_data()).splitlines()

        idx = next(idx for (line, idx) in zip(storage_dump[2:], count(2)) if not line.startswith(' '))

        version = f'# Version@{self.VSP_VERSION}'

        with io.open(self.global_storage_path, 'w', encoding='utf-8') as global_file:
            global_file.writelines(
                '\n'.join([version, '# Global VSPreview storage for settings'] + storage_dump[:idx])
            )

        with io.open(self.current_storage_path, 'w', encoding='utf-8') as current_file:
            current_file.writelines(
                '\n'.join([
                    version,
                    f'# VSPreview script storage for: {self.script_path}',
                    f'# Global setting saved at path: {self.global_storage_path}'
                ] + storage_dump[idx:])
            )

        if manually:
            self.show_message('Saved successfully')

    def _serialize_data(self) -> Any:
        # idk how to explain how this work,
        # but i'm referencing settings objects before in the dict
        # so the yaml serializer will reference the same objects after (in toolbars),
        # which really are the original objects, to those copied in _globals :poppo:
        data = cast(dict, self.__getstate__())
        data['_globals'] = {
            'settings': data['settings']
        }

        data['_globals']['toolbars'] = data['toolbars'].__getstate__()
        gtoolbars = data['_globals']['toolbars']

        for toolbar_name in gtoolbars:
            gtoolbars[toolbar_name].clear()
            gtoolbars[toolbar_name] = getattr(data['toolbars'], toolbar_name).settings

        data['_toolbars_settings'] = [None] * len(gtoolbars)
        for i, toolbar_name in enumerate(gtoolbars.keys()):
            data['_toolbars_settings'][i] = gtoolbars[toolbar_name]

        return data

    def _dump_serialize(self, data: Any) -> str:
        storage_dump = io.StringIO()

        dumper = yaml.CDumper(
            storage_dump, default_style=None, default_flow_style=False,
            canonical=None, indent=4, width=120, allow_unicode=True,
            line_break='\n', encoding='utf-8', version=None, tags=None,
            explicit_start=None, explicit_end=None, sort_keys=True
        )
        try:
            dumper.open()
            dumper.represent(data)
            dumper.close()
        finally:
            dumper.dispose()

        return storage_dump.getvalue()

    def init_outputs(self) -> None:
        self.graphics_scene.clear()

        for output in self.outputs:
            raw_frame_item = self.graphics_scene.addPixmap(QPixmap())
            raw_frame_item.hide()

            output.graphics_scene_item = GraphicsImageItem(raw_frame_item)

    def reload_script(self) -> None:
        self.reload_before_signal.emit()

        self.dump_storage()

        vs.clear_outputs()
        self.graphics_scene.clear()

        self.outputs.clear()
        get_policy().reload_core()
        gc.collect(generation=0)
        gc.collect(generation=1)
        gc.collect(generation=2)

        self.load_script(self.script_path, reloading=True)

        self.reload_after_signal.emit()

        self.show_message('Reloaded successfully')

    def switch_frame(
        self, pos: Frame | Time | int | None, *, render_frame: bool | Tuple[vs.VideoFrame, vs.VideoFrame | None] = True
    ) -> None:
        if pos is None:
            logging.debug('switch_frame: position is None!')
            return

        frame = Frame(min(max(0, int(Frame(pos))), int(self.current_output.total_frames)))

        if self.current_output.last_showed_frame == frame > self.current_output.end_frame:
            return

        if render_frame:
            if isinstance(render_frame, bool):
                self.current_output.render_frame(frame)
            else:
                self.current_output.render_frame(frame, *render_frame)

        self.current_output.last_showed_frame = frame

        self.timeline.set_position(frame)

        for toolbar in self.toolbars:
            toolbar.on_current_frame_changed(frame)

        self.statusbar.frame_props_label.setText(self.STATUS_FRAME_PROP(self.current_output.props))

    def switch_output(self, value: int | VideoOutput) -> None:
        if len(self.outputs) == 0:
            return

        if isinstance(value, VideoOutput):
            index = self.outputs.index_of(value)
        else:
            index = value

        if index < 0:
            index = len(self.outputs) + index

        if index < 0 or index >= len(self.outputs):
            return

        prev_index = self.toolbars.main.outputs_combobox.currentIndex()

        self.toolbars.playback.stop()

        # current_output relies on outputs_combobox
        self.toolbars.main.on_current_output_changed(index, prev_index)
        self.timeline.set_end_frame(self.current_output.end_frame)

        if self.current_output.last_showed_frame:
            self.switch_frame(self.current_output.last_showed_frame)
        else:
            self.switch_frame(0)

        for output in self.outputs:
            output.graphics_scene_item.hide()

        self.current_output.graphics_scene_item.show()
        self.graphics_scene.setSceneRect(QRectF(self.current_output.graphics_scene_item.pixmap().rect()))
        self.timeline.update_notches()

        for toolbar in self.toolbars[1:]:
            toolbar.on_current_output_changed(index, prev_index)

        self.update_statusbar_output_info()

    @property
    def current_output(self) -> VideoOutput:
        return cast(VideoOutput, self.toolbars.main.outputs_combobox.currentData())

    @current_output.setter
    def current_output(self, value: VideoOutput) -> None:
        self.switch_output(self.outputs.index_of(value))

    @property
    def outputs(self) -> VideoOutputs:
        return self.toolbars.main.outputs

    def handle_script_error(self, message: str) -> None:
        self.script_error_dialog.label.setText(message)
        self.script_error_dialog.open()

    def on_wheel_scrolled(self, steps: int) -> None:
        new_index = self.toolbars.main.zoom_combobox.currentIndex() + steps
        if new_index < 0:
            new_index = 0
        elif new_index >= len(self.settings.zoom_levels):
            new_index = len(self.settings.zoom_levels) - 1
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
            message, round(float(self.settings.statusbar_message_timeout) * 1000)
        )

    def update_statusbar_output_info(self, output: VideoOutput | None = None) -> None:
        output = output or self.current_output
        fmt = output.source.clip.format
        assert fmt

        self.statusbar.total_frames_label.setText(f'{output.total_frames} frames ')
        self.statusbar.duration_label.setText(f'{output.total_time} ')
        self.statusbar.resolution_label.setText(f'{output.width}x{output.height} ')
        self.statusbar.pixel_format_label.setText(f'{fmt.name} ')
        if output.fps_den != 0:
            self.statusbar.fps_label.setText(
                '{}/{} = {:.3f} fps '.format(output.fps_num, output.fps_den, output.fps_num / output.fps_den)
            )
        else:
            self.statusbar.fps_label.setText('{}/{} fps '.format(output.fps_num, output.fps_den))

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.LayoutRequest:
            self.timeline.full_repaint()

        return super().event(event)

    # misc methods
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.graphics_view.setSizePolicy(self.EVENT_POLICY)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.settings.autosave_control.value() != Time(seconds=0):
            self.dump_storage_async()

        self.reload_signal.emit()

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'timeline_mode': self.timeline.mode,
            'window_geometry': bytes(cast(bytearray, self.saveGeometry())),
            'window_state': bytes(cast(bytearray, self.saveState()))
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        # toolbars is singleton, so it initialize itself right in its __setstate__()
        try_load(state, 'timeline_mode', str, self.timeline.mode)
        try_load(state, 'window_geometry', bytes, self.restoreGeometry)
        try_load(state, 'window_state', bytes, self.restoreState)
