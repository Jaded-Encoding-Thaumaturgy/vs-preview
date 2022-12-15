from __future__ import annotations

import gc
import io
import logging
import sys
from fractions import Fraction
from itertools import count
from os.path import expanduser, expandvars
from pathlib import Path
from random import random
from traceback import TracebackException
from typing import Any, Mapping, cast

import yaml
from PyQt6.QtCore import QEvent, QRectF, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QColorSpace, QMoveEvent, QPalette, QPixmap, QShowEvent
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QLabel, QSizePolicy
from vsengine import vpy  # type: ignore[import]
from vstools import ChromaLocation, ColorRange, Matrix, Primaries, Transfer, vs

from ..core import AbstractMainWindow, ExtendedWidget, Frame, Time, VBoxLayout, VideoOutput, ViewMode, try_load
from ..core.custom import DragNavigator, GraphicsImageItem, GraphicsView, StatusBar
from ..core.vsenv import _monkey_runpy_dicts, get_current_environment, make_environment
from ..models import VideoOutputs
from ..toolbars import Toolbars
from ..utils import fire_and_forget, set_status_label
from .dialog import ScriptErrorDialog, SettingsDialog
from .settings import MainSettings, WindowSettings
from .timeline import Timeline

if sys.platform == 'win32':
    try:
        import win32gui  # type: ignore[import]
        from PIL import _imagingcms  # type: ignore[attr-defined]
    except ImportError:
        _imagingcms = None

try:
    from yaml import CDumper as yaml_Dumper
    from yaml import CLoader as yaml_Loader
except ImportError:
    from yaml import Dumper as yaml_Dumper
    from yaml import Loader as yaml_Loader


class MainWindow(AbstractMainWindow):
    VSP_DIR_NAME = '.vspreview'
    VSP_GLOBAL_DIR_NAME = Path(
        expandvars('%APPDATA%') if sys.platform == "win32" else expanduser('~/.config')
    )
    # used for formats with subsampling
    VS_OUTPUT_MATRIX = Matrix.BT709
    VS_OUTPUT_TRANSFER = Transfer.BT709
    VS_OUTPUT_PRIMARIES = Primaries.BT709
    VS_OUTPUT_RANGE = ColorRange.LIMITED
    VS_OUTPUT_CHROMALOC = ChromaLocation.LEFT
    VSP_VERSION = 3.0
    BREAKING_CHANGES_VERSIONS = list[float]()

    # status bar
    def STATUS_FRAME_PROP(self, prop: Any) -> str:
        return 'Type: %s' % (prop['_PictType'].decode('utf-8') if '_PictType' in prop else '?')

    EVENT_POLICY = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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
                from qdarkstyle import _load_stylesheet  # type: ignore[import]
            except ImportError:
                self.self.settings.dark_theme_enabled = False
            else:
                self.app.setStyleSheet(self.patch_dark_stylesheet(_load_stylesheet(qt_api='pyqt6')))
                self.ensurePolished()

        self.display_scale = self.app.primaryScreen().logicalDotsPerInch() / self.settings.base_ppi
        self.setWindowTitle('VSPreview')

        desktop_size = self.app.primaryScreen().size()

        self.move(int(desktop_size.width() * 0.15), int(desktop_size.height() * 0.075))
        self.setup_ui()
        self.storage_not_found = False
        self.timecodes = dict[
            int, dict[tuple[int | None, int | None], float | tuple[int, int] | Fraction] | list[float]
        ]()
        self.norm_timecodes = dict[int, list[float]]()

        self.user_output_names = {vs.VideoNode: {}, vs.AudioNode: {}, vs.RawNode: {}}

        # global
        self.clipboard = self.app.clipboard()
        self.external_args = list[tuple[str, str]]()
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

        # display profile
        self.display_profile: QColorSpace | None = None
        self.current_screen = 0

        # init toolbars and outputs
        self.app_settings = SettingsDialog(self)
        self.toolbars = Toolbars(self)

        for toolbar in self.toolbars:
            self.main_layout.addWidget(toolbar)
            self.toolbars.main.layout().addWidget(toolbar.toggle_button)

        self.app_settings.tab_widget.setUsesScrollButtons(False)
        self.app_settings.setMinimumWidth(
            int(len(self.toolbars) * 1.05 * self.app_settings.tab_widget.geometry().width() / 2)
        )

        self.current_viewmode = ViewMode.NORMAL

        self.set_qobject_names()
        self.setObjectName('MainWindow')

        self.env: vpy.Script | None = None

    def setup_ui(self) -> None:
        self.central_widget = ExtendedWidget(self)
        self.main_layout = VBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.graphics_view = GraphicsView(self.central_widget)
        self.graphics_view.setBackgroundBrush(self.palette().brush(QPalette.ColorRole.Window))
        self.graphics_view.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

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
        self, script_path: Path, external_args: list[tuple[str, str]] | None = None, reloading: bool = False,
        start_frame: int | None = None
    ) -> None:
        self.external_args = external_args or []

        self.toolbars.playback.stop()
        self.setWindowTitle('VSPreview: %s %s' % (script_path, self.external_args))

        self.statusbar.label.setText('Evaluating')
        self.script_path = script_path

        sys.path.append(str(self.script_path.parent))

        # Rewrite args so external args will be forwarded correctly
        argv_orig = None
        try:
            argv_orig = sys.argv
            sys.argv = [script_path.name]
        except AttributeError:
            pass

        try:
            self.env = vpy.variables(
                dict(self.external_args),
                environment=vs.get_current_environment(),
                module_name="__vspreview__"
            ).result()
            self.env.module.__dict__['_monkey_runpy'] = random()
            self.env = vpy.script(script_path, environment=self.env).result()
        except vpy.ExecutionFailed as e:
            logging.error(e.parent_error)

            te = TracebackException.from_exception(e.parent_error)
            logging.error(''.join(te.format()))

            self.script_exec_failed = True
            return self.handle_script_error(
                '\n'.join([
                    str(e), 'See console output for details.'
                ])
            )
        finally:
            if argv_orig is not None:
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

        self.change_video_viewmode(self.current_viewmode)

        self.toolbars.misc.autosave_timer.start(round(float(self.settings.autosave_interval) * 1000))

        if not reloading:
            self.switch_output(self.settings.output_index)
            if start_frame is not None:
                self.switch_frame(Frame(start_frame))

        with self.env:
            vs.register_on_destroy(self.gc_collect)

    @set_status_label('Loading...')
    def load_storage(self) -> None:
        storage_paths = [self.global_storage_path, self.current_storage_path]

        if self.storage_not_found:
            logging.info('No storage found. Using defaults.')

            if not self.global_storage_path.exists():
                return

            storage_paths = storage_paths[:1]

        storage_contents = ''
        broken_storage = False
        global_length = 0
        for i, storage_path in enumerate(storage_paths):
            try:
                with io.open(storage_path, 'r', encoding='utf-8') as storage_file:
                    version = storage_file.readline()
                    if 'Version' not in version or any({
                        version.endswith(f'@{v}') for v in self.BREAKING_CHANGES_VERSIONS
                    }):
                        raise FileNotFoundError

                    storage_contents += storage_file.read()
                    storage_contents += '\n'

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

        loader = yaml_Loader(storage_contents)
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
                        'Storage ({}) parsing failed on line {} column {}. \n({})\n Exiting...'
                        .format(
                            'Global' if isglobal else 'Local',
                            line, exc.problem_mark.column + 1,
                            str(exc).partition('in "<unicode string>"')[0].strip()
                        )
                    )
                    sys.exit(1)
            else:
                logging.warning('Storage parsing failed. Using defaults.')
        finally:
            loader.dispose()

        if self.settings.color_management:
            assert self.app
            self.current_screen = self.app.desktop().screenNumber(self)
            self.update_display_profile()

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
            'settings': data['settings'],
            'window_settings': data['window_settings']
        }

        data['_globals']['toolbars'] = data['toolbars'].__getstate__()
        gtoolbars = data['_globals']['toolbars']

        for toolbar_name in gtoolbars:
            gtoolbars[toolbar_name].clear()
            gtoolbars[toolbar_name] = getattr(data['toolbars'], toolbar_name).settings

        data['_toolbars_settings'] = [None] * (len(gtoolbars) + 1)
        for i, toolbar_name in enumerate(gtoolbars.keys()):
            data['_toolbars_settings'][i] = gtoolbars[toolbar_name]
        data['_toolbars_settings'][-1] = data['_globals']['window_settings']

        return data

    def _dump_serialize(self, data: Any) -> str:
        storage_dump = io.StringIO()

        dumper = yaml_Dumper(
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
        if not self.outputs:
            return

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

        self.timecodes.clear()
        self.norm_timecodes.clear()
        for v in self.user_output_names.values():
            v.clear()
        if self.outputs:
            self.outputs.clear()
        self.gc_collect()
        old_environment = get_current_environment()

        self.clear_monkey_runpy()
        make_environment()
        old_environment.dispose()
        self.gc_collect()

        try:
            self.load_script(self.script_path, reloading=True)
        finally:
            self.clear_monkey_runpy()

        self.reload_after_signal.emit()

        self.show_message('Reloaded successfully')

    def clear_monkey_runpy(self):
        if self.env and '_monkey_runpy' in self.env.module.__dict__:
            key = self.env.module.__dict__['_monkey_runpy']

            if key in _monkey_runpy_dicts:
                _monkey_runpy_dicts[key].clear()
                _monkey_runpy_dicts.pop(key, None)
            elif _monkey_runpy_dicts:
                for env in _monkey_runpy_dicts.items():
                    env.clear()
                _monkey_runpy_dicts.clear()

        self.gc_collect()

    def gc_collect(self) -> None:
        for i in range(3):
            gc.collect(generation=i)

        for _ in range(3):
            gc.collect()

    def switch_frame(
        self, pos: Frame | int, *, render_frame: bool | tuple[vs.VideoFrame, vs.VideoFrame | None] = True
    ) -> None:
        frame = Frame(pos)

        if (not 0 <= frame < self.current_output.total_frames):
            return

        if render_frame:
            if isinstance(render_frame, bool):
                self.current_output.render_frame(frame, output_colorspace=self.display_profile)
            else:
                self.current_output.render_frame(frame, *render_frame, output_colorspace=self.display_profile)

        self.current_output.last_showed_frame = frame

        self.timeline.set_position(frame)

        for toolbar in self.toolbars:
            toolbar.on_current_frame_changed(frame)

        self.statusbar.frame_props_label.setText(self.STATUS_FRAME_PROP(self.current_output.props))

    def switch_output(self, value: int | VideoOutput) -> None:
        if not self.outputs or len(self.outputs) == 0:
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
        self.timeline.set_end_frame(self.current_output)

        self.switch_frame(self.current_output.last_showed_frame)

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
        if not self.outputs:
            return

        self.switch_output(self.outputs.index_of(value))

    @property
    def outputs(self) -> VideoOutputs | None:
        return self.toolbars.main.outputs

    def handle_script_error(self, message: str) -> None:
        self.clear_monkey_runpy()
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

    def update_display_profile(self) -> None:
        if sys.platform == 'win32':
            if _imagingcms is None:
                print(ImportWarning(
                    'You\'re missing packages for the image csm!\n'
                    'You can install it with "pip install pywin32 Pillow"!'
                ))
                return

            assert self.app

            screen_name = self.app.screens()[self.current_screen].name()

            dc = win32gui.CreateDC(screen_name, None, None)

            logging.info(f'Changed screen: {screen_name}')

            icc_path = _imagingcms.get_display_profile_win32(dc, 1)

            if icc_path is not None:
                with open(icc_path, 'rb') as icc:
                    self.display_profile = QColorSpace.fromIccProfile(icc.read())

        if hasattr(self, 'current_output') and self.current_output is not None and self.display_profile is not None:
            self.switch_frame(self.current_output.last_showed_frame)

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

        if output.got_timecodes:
            times = sorted(set(output.timecodes), reverse=True)

            if len(times) >= 2:
                return self.statusbar.fps_label.setText(
                    f'VFR {",".join(f"{float(fps):.3f}" for fps in times)} fps '
                )

        if output.fps_den != 0:
            return self.statusbar.fps_label.setText(
                f'{output.fps_num}/{output.fps_den} = {output.fps_num / output.fps_den:.3f} fps '
            )

        self.statusbar.fps_label.setText(f'VFR {output.fps_num}/{output.fps_den} fps ')

    def update_timecodes_info(
        self, index: int, timecodes: str | dict[
            tuple[int | None, int | None], float | tuple[int, int] | Fraction
        ] | list[Fraction], den: int = None
    ) -> None:
        self.timecodes[index] = (timecodes, den)

    def set_node_name(self, node_type: type, index: int, name: str) -> None:
        self.user_output_names[node_type][index] = name

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.LayoutRequest:
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

    def moveEvent(self, _move_event: QMoveEvent) -> None:
        if self.settings.color_management:
            assert self.app
            screen_number = self.app.desktop().screenNumber(self)
            if self.current_screen != screen_number:
                self.current_screen = screen_number
                self.update_display_profile()

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'window_settings': WindowSettings(
                self.timeline.mode,
                bytes(cast(bytearray, self.saveGeometry())),
                bytes(cast(bytearray, self.saveState()))
            )
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        # toolbars is singleton, so it initialize itself right in its __setstate__()
        self.window_settings = {}

        try:
            try_load(state, 'window_settings', dict, self)
        except BaseException:
            try_load(state, 'timeline_mode', str, self.window_settings)
            try_load(state, 'window_geometry', bytes, self.window_settings)
            try_load(state, 'window_state', bytes, self.window_settings)

        self.timeline.mode = self.window_settings.timeline_mode
        self.restoreGeometry(self.window_settings.window_geometry)
        self.restoreState(self.window_settings.window_state)
