from __future__ import annotations

import io
import logging
import sys
from fractions import Fraction
from functools import partial
from importlib import reload as reload_module
from pathlib import Path
from time import time
from typing import Any, Iterable, Mapping, cast

import vapoursynth as vs
from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, QKeyCombination, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QColorSpace, QKeySequence, QMoveEvent, QShortcut, QShowEvent
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QSizePolicy, QSplitter, QTabWidget
from vsengine import vpy  # type: ignore

from ..core import (
    PRELOADED_MODULES, AbstractQItem, CroppingInfo, DragNavigator, ExtendedWidget, Frame, GraphicsImageItem,
    GraphicsView, HBoxLayout, MainVideoOutputGraphicsView, QAbstractYAMLObjectSingleton, StatusBar, Time, Timer,
    VBoxLayout, VideoOutput, _monkey_runpy_dicts, dispose_environment, get_current_environment, make_environment
)
from ..models import GeneralModel, VideoOutputs
from ..plugins import Plugins
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

    from os.path import expandvars
else:
    from os.path import expanduser

try:
    from yaml import CDumper as yaml_Dumper
    from yaml import CLoader as yaml_Loader
except ImportError:
    from yaml import Dumper as yaml_Dumper  # type: ignore
    from yaml import Loader as yaml_Loader  # type: ignore

from yaml import MarkedYAMLError, YAMLError

__all__ = [
    'MainWindow'
]


class CentralSplitter(QSplitter):
    def __init__(self, main_window: MainWindow, orientation: QtCore.Qt.Orientation) -> None:
        super().__init__(orientation)

        self.main_window = main_window

        self.splitterMoved.connect(self.on_splitter_moved)

        self.previous_position = 0

    @property
    def current_position(self) -> int:
        return self.sizes()[-1]

    def on_splitter_moved(self) -> None:
        if self.previous_position == 0 and self.current_position:
            self.main_window.plugins.update()

        self.previous_position = self.current_position


class MainWindow(AbstractQItem, QMainWindow, QAbstractYAMLObjectSingleton):
    VSP_DIR_NAME = '.vspreview'
    VSP_GLOBAL_DIR_NAME = Path(
        expandvars('%APPDATA%') if sys.platform == "win32" else expanduser('~/.config')  # type: ignore
    )

    global_config_dir = VSP_GLOBAL_DIR_NAME / VSP_DIR_NAME
    global_storage_path = global_config_dir / '.global.yml'
    global_plugins_dir = global_config_dir / 'plugins'

    VSP_VERSION = 3.2
    BREAKING_CHANGES_VERSIONS = list[str](['3.0', '3.1'])

    # status bar
    def STATUS_FRAME_PROP(self, prop: Any) -> str:
        return 'Type: %s' % (prop['_PictType'].decode('utf-8') if '_PictType' in prop else '?')

    EVENT_POLICY = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    storable_attrs = ('settings', 'toolbars')

    __slots__ = (
        *storable_attrs, 'app', 'display_scale', 'clipboard',
        'script_path', 'timeline', 'main_layout', 'autosave_timer',
        'graphics_view', 'script_error_dialog',
        'central_widget', 'statusbar', 'storage_not_found',
        'current_storage_path'
    )

    # emit when about to reload a script: clear all existing references to existing clips.
    reload_signal = pyqtSignal()
    reload_before_signal = pyqtSignal()
    reload_after_signal = pyqtSignal()
    cropValuesChanged = pyqtSignal(CroppingInfo)

    toolbars: Toolbars
    plugins: Plugins
    app_settings: SettingsDialog
    window_settings = WindowSettings()

    autosave_timer: Timer

    def __init__(self, config_dir: Path, no_exit: bool) -> None:
        from ..toolbars import MainToolbar

        super().__init__()

        self.no_exit = no_exit

        self.settings = MainSettings(MainToolbar)

        self.current_config_dir = config_dir / self.VSP_DIR_NAME
        self.global_plugins_dir.mkdir(parents=True, exist_ok=True)

        self.app = cast(QApplication, QApplication.instance())
        assert self.app

        self.last_reload_time = time()

        self.bound_graphics_views = dict[GraphicsView, set[GraphicsView]]()

        if self.settings.dark_theme_enabled:
            from ..core import apply_plotting_style

            try:
                from qdarkstyle import _load_stylesheet  # type: ignore[import]
            except ImportError:
                self.settings.dark_theme_enabled = False
            else:
                apply_plotting_style()
                self.app.setStyleSheet(self.patch_dark_stylesheet(_load_stylesheet(qt_api='pyqt6')))

        self.ensurePolished()

        self.display_scale = self.app.primaryScreen().logicalDotsPerInch() / self.settings.base_ppi
        self.setWindowTitle('VSPreview')

        desktop_size = self.app.primaryScreen().size()

        self.move(int(desktop_size.width() * 0.15), int(desktop_size.height() * 0.075))
        self.setup_ui()
        self.storage_not_found = False
        self.timecodes = dict[
            int, tuple[str | Path | dict[
                tuple[int | None, int | None], float | tuple[int, int] | Fraction
            ] | list[Fraction], int | None]
        ]()
        self.norm_timecodes = dict[int, list[float]]()

        self.user_output_info = {
            vs.VideoNode: dict[int, dict[str, Any]](),
            vs.AudioNode: dict[int, dict[str, Any]](),
            vs.RawNode: dict[int, dict[str, Any]]()
        }

        # global
        self.clipboard = self.app.clipboard()
        self.external_args = list[tuple[str, str]]()
        self.script_path = Path()
        self.script_exec_failed = False
        self.current_storage_path = Path()

        # timeline
        self.timeline.clicked.connect(self.on_timeline_clicked)

        # display profile
        self.display_profile: QColorSpace | None = None
        self.current_screen = self.app.primaryScreen()

        # init toolbars and outputs
        self.app_settings = SettingsDialog(self)

        Toolbars(self)

        for toolbar in self.toolbars:
            self.main_layout.addWidget(toolbar)
            self.toolbars.main.layout().addWidget(toolbar.toggle_button)

        Plugins(self)

        self.app_settings.tab_widget.setUsesScrollButtons(False)
        self.app_settings.setMinimumWidth(
            int(len(self.toolbars) * 1.05 * self.app_settings.tab_widget.geometry().width() / 2)
        )

        self.set_qobject_names()
        self.setObjectName('MainWindow')

        self.env: vpy.Script | None = None

    def setup_ui(self) -> None:
        self.central_widget = ExtendedWidget(self)
        self.main_layout = VBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.graphics_view = MainVideoOutputGraphicsView(self, self.central_widget)

        DragNavigator(self, self.graphics_view)

        self.timeline = Timeline(self.central_widget)

        self.plugins_tab = QTabWidget(self.central_widget)
        self.plugins_tab.currentChanged.connect(lambda x: self.plugins.update())

        self.main_split = CentralSplitter(self, QtCore.Qt.Orientation.Horizontal)
        self.main_split.addWidget(self.graphics_view)
        self.main_split.addWidget(self.plugins_tab)
        self.main_split.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        HBoxLayout(self.main_layout, [self.main_split])
        self.main_layout.addWidget(self.timeline)

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

        self.autosave_timer = Timer(timeout=self.dump_storage_async)
        self.reload_signal.connect(self.autosave_timer.stop)

        QShortcut(
            QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_A).toCombined()),
            self, activated=self.auto_fit_keyswitch
        )

    def auto_fit_keyswitch(self) -> None:
        for view in self.graphics_views:
            if view.underMouse():
                view.autofit = not view.autofit
                break

    def patch_dark_stylesheet(self, stylesheet: str) -> str:
        return stylesheet + 'QGraphicsView { border: 0px; padding: 0px; }'

    def load_script(
        self, script_path: Path, external_args: list[tuple[str, str]] | None = None, reloading: bool = False,
        start_frame: int | None = None
    ) -> None:
        from random import random

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
            if reloading:
                std_path_lib = Path(logging.__file__).parent.parent
                std_path_dlls = std_path_lib.parent / 'DLLs'

                check_reloaded = set[str]()

                for module in set(sys.modules.values()) - PRELOADED_MODULES:
                    if not hasattr(module, '__file__') or module.__file__ is None:
                        continue

                    main_mod = module.__name__.split('.')[0]

                    if main_mod in check_reloaded:
                        continue

                    mod_file = Path(module.__file__)

                    if 'vspreview' in mod_file.parts:
                        continue

                    if std_path_lib in mod_file.parents or std_path_dlls in mod_file.parents:
                        continue

                    if not mod_file.exists() or not mod_file.is_file():
                        continue

                    check_reloaded.add(main_mod)

                for module in check_reloaded:
                    all_submodules = sorted([
                        k for k in sys.modules.keys()
                        if k == module or k.startswith(f'{module}.')
                    ])

                    for mod_name in all_submodules:
                        try:
                            if Path(sys.modules[mod_name].__file__).stat().st_mtime > self.last_reload_time:
                                break
                        except Exception:
                            ...
                    else:
                        continue

                    try:
                        logging.info(f'Hot reloaded Python Package: "{module}"')
                        for mod_name in reversed(all_submodules):
                            sys.modules[mod_name] = reload_module(sys.modules[mod_name])
                    except Exception as e:
                        logging.error(e)

            self.env = vpy.variables(
                dict(self.external_args),
                environment=vs.get_current_environment(),
                module_name="__vspreview__"
            ).result()
            self.env.module.__dict__['_monkey_runpy'] = random()
            self.env = vpy.script(self.script_path, environment=self.env).result()
        except vpy.ExecutionFailed as e:
            from traceback import TracebackException

            logging.error(e.parent_error)

            te = TracebackException.from_exception(e.parent_error)
            logging.error(''.join(te.format()))

            self.script_exec_failed = True
            return self.handle_script_error(
                '\n'.join([
                    str(e), 'See console output for details.'
                ]), True
            )
        finally:
            if argv_orig is not None:
                sys.argv = argv_orig
            sys.path.pop()
            self.last_reload_time = time()

        if len(vs.get_outputs()) == 0:
            logging.error('Script has no outputs set.')
            self.script_exec_failed = True
            self.handle_script_error('Script has no outputs set.', True)
            return

        reload_from_error = self.script_exec_failed and reloading
        self.script_exec_failed = False
        self.current_storage_path = (self.current_config_dir / self.script_path.stem).with_suffix('.yml')

        self.storage_not_found = not (
            self.current_storage_path.exists() and self.current_storage_path.read_text('utf8').strip()
        )

        load_error = None

        try:
            if self.storage_not_found or reload_from_error:
                self.load_storage()

            if not reloading:
                self.toolbars.main.rescan_outputs()
                self.toolbars.playback.rescan_outputs()

            if not self.storage_not_found:
                self.load_storage()
        except Exception as e:
            load_error = e

        with self.env:
            vs.register_on_destroy(self.gc_collect)

        if load_error is None:
            self.autosave_timer.start(round(float(self.settings.autosave_interval) * 1000))

            if not reloading:
                self.switch_output(self.settings.output_index)
                if start_frame is not None:
                    self.switch_frame(Frame(start_frame))
        else:
            error_string = "There was an error while loading the script!\n"

            logging.error(error_string + vpy.textwrap.indent(vpy.ExecutionFailed.extract_traceback(load_error), '| '))

            self.script_exec_failed = True

            return self.handle_script_error(
                f'{error_string}{vpy.textwrap.indent(str(load_error), " | ")}\nSee console output for details.', False
            )

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
                        version.strip().endswith(f'@{v}') for v in self.BREAKING_CHANGES_VERSIONS
                    }):
                        raise FileNotFoundError

                    storage_contents += storage_file.read()
                    storage_contents += '\n'

                    if i == 0:
                        global_length = storage_contents.count('\n')
            except FileNotFoundError:
                if self.settings.force_old_storages_removal or i == 0:
                    if storage_path.exists():
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
        except YAMLError as exc:
            if isinstance(exc, MarkedYAMLError):
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
            self.current_screen = self.app.primaryScreen()
            self.update_display_profile()

    @fire_and_forget
    @set_status_label('Saving...')
    def dump_storage_async(self) -> None:
        self.dump_storage()

    def dump_storage(self, manually: bool = False) -> None:
        from itertools import count

        if self.script_exec_failed:
            return

        self.current_config_dir.mkdir(0o777, True, True)
        self.global_config_dir.mkdir(0o777, True, True)

        backup_paths = [
            self.current_storage_path.with_suffix(f'.old{i}.yml')
            for i in range(self.settings.STORAGE_BACKUPS_COUNT, 0, -1)
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
                    f'# VSPreview local storage for script: {self.script_path}',
                    f'# Global setting (storage/plugins) saved at path: {self.global_config_dir}'
                ] + storage_dump[idx:])
            )

        if manually:
            self.show_message('Saved successfully')

    def _serialize_data(self) -> Any:
        # idk how to explain how this work,
        # but i'm referencing settings objects before in the dict
        # so the yaml serializer will reference the same objects after (in toolbars),
        # which really are the original objects, to those copied in _globals :poppo:
        data = cast(dict[str, Any], self.__getstate__())
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

        self.plugins.init_outputs()

        for graphics_view in self.graphics_views:
            graphics_view.graphics_scene.init_scenes()

    def clean_core_references(self) -> None:
        from vstools.utils.vs_proxy import clear_cache

        for graphics_view in self.graphics_views:
            graphics_view.graphics_scene.clear()

        self.timecodes.clear()
        self.norm_timecodes.clear()

        self.toolbars.pipette._curr_frame_cache.clear()
        self.toolbars.pipette._curr_alphaframe_cache.clear()
        self.toolbars.pipette.outputs.clear()

        for v in self.user_output_info.values():
            for k in v.values():
                k.clear()
            v.clear()

        try:
            with self.env:
                clear_cache()
        except Exception:
            ...

        vs.clear_outputs()

        if self.outputs:
            self.outputs.clear()

        self.gc_collect()

    def reload_script(self) -> None:
        self.reload_before_signal.emit()

        self.dump_storage()

        self.clean_core_references()

        old_environment = get_current_environment()

        self.clear_monkey_runpy()
        make_environment()
        dispose_environment(old_environment)
        self.gc_collect()

        try:
            self.load_script(self.script_path, reloading=True)
        finally:
            self.clear_monkey_runpy()

        self.reload_after_signal.emit()

        self.show_message('Reloaded successfully')

    def clear_monkey_runpy(self) -> None:
        if self.env and '_monkey_runpy' in self.env.module.__dict__:
            key = self.env.module.__dict__['_monkey_runpy']

            if key in _monkey_runpy_dicts:
                _monkey_runpy_dicts[key].clear()
                _monkey_runpy_dicts.pop(key, None)
            elif _monkey_runpy_dicts:
                for env in _monkey_runpy_dicts.values():
                    env.clear()
                _monkey_runpy_dicts.clear()

        self.gc_collect()

    def gc_collect(self) -> None:
        import gc

        for i in range(3):
            gc.collect(generation=i)

        for _ in range(3):
            gc.collect()

    def switch_frame(
        self, pos: Frame | int, *, render_frame: bool | Iterable[vs.VideoFrame | None] = True
    ) -> None:
        frame = Frame(pos)

        if (not 0 <= frame < self.current_output.total_frames):
            return

        if render_frame:
            if isinstance(render_frame, bool):
                self.current_output.render_frame(frame, output_colorspace=self.display_profile)
            else:
                self.current_output.render_frame(
                    frame, *render_frame, output_colorspace=self.display_profile  # type: ignore
                )

        self.current_output.last_showed_frame = frame

        self.timeline.set_position(frame)

        for toolbar in self.toolbars:
            toolbar.on_current_frame_changed(frame)

        self.plugins.on_current_frame_changed(frame)

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

        for graphics_view in self.graphics_views:
            for item in graphics_view.graphics_scene.graphics_items:
                item.hide()

            graphics_view.current_scene.show()
            graphics_view.graphics_scene.setSceneRect(
                QRectF(graphics_view.current_scene.pixmap().rect())
            )

        self.timeline.update_notches()

        for toolbar in self.toolbars[1:]:
            toolbar.on_current_output_changed(index, prev_index)

        self.plugins.on_current_output_changed(index, prev_index)

        self.update_statusbar_output_info()

    @property
    def current_output(self) -> VideoOutput:
        return cast(VideoOutput, self.toolbars.main.outputs_combobox.currentData())

    @property
    def outputs(self) -> VideoOutputs | None:
        return self.toolbars.main.outputs

    @property
    def current_scene(self) -> GraphicsImageItem:
        return self.graphics_view.current_scene

    @property
    def graphics_views(self) -> list[GraphicsView]:
        return list(self.bound_graphics_views.keys())

    def register_graphic_view(self, view: GraphicsView) -> None:
        self.bound_graphics_views[view] = {view}

        view.zoom_combobox.currentTextChanged.connect(partial(self.on_zoom_changed, bound_view=view))

        view.zoom_combobox.setModel(GeneralModel[float](self.settings.zoom_levels))
        view.zoom_combobox.setCurrentIndex(self.settings.zoom_default_index)

    def on_zoom_changed(self, text: str | None = None, bound_view: GraphicsView | None = None) -> None:
        if not bound_view:
            return

        for view in self.bound_graphics_views[bound_view]:
            view.setZoom(bound_view.zoom_combobox.currentData())

    def handle_script_error(self, message: str, script: bool = False) -> None:
        self.clear_monkey_runpy()
        self.script_error_dialog.label.setText(message)
        self.script_error_dialog.setWindowTitle('Script Loading Error' if script else 'Program Error')
        self.script_error_dialog.open()

    def on_timeline_clicked(self, start: int) -> None:
        if self.toolbars.playback.play_timer.isActive():
            self.toolbars.playback.stop()
            self.switch_frame(start)
            self.toolbars.playback.play()
        else:
            self.switch_frame(start)

    def update_display_profile(self) -> None:
        if sys.platform == 'win32':
            assert self.app and _imagingcms

            screen_name = self.current_screen.name()

            dc = win32gui.CreateDC('DISPLAY', screen_name, None)

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
        self, index: int, timecodes: str | Path | dict[
            tuple[int | None, int | None], float | tuple[int, int] | Fraction
        ] | list[Fraction], den: int | None = None
    ) -> None:
        self.timecodes[index] = (timecodes, den)

    def set_node_info(self, node_type: type, index: int, **kwargs: Any) -> None:
        base = self.user_output_info[node_type]

        if index not in base:
            base[index] = {**kwargs}
        else:
            base[index] |= kwargs

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.LayoutRequest:
            self.timeline.full_repaint()

        return super().event(event)

    # misc methods
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        for graphics_view in self.graphics_views:
            graphics_view.setSizePolicy(self.EVENT_POLICY)

        self.main_split.setSizePolicy(self.EVENT_POLICY)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.settings.autosave_control.value() != Time(seconds=0):
            self.dump_storage_async()

        self.reload_signal.emit()

    def moveEvent(self, _move_event: QMoveEvent) -> None:
        if self.settings.color_management:
            assert self.app
            screen_number = self.app.primaryScreen()
            if self.current_screen != screen_number:
                self.current_screen = screen_number
                self.update_display_profile()

    def refresh_video_outputs(self) -> None:
        if not self.outputs:
            return

        playback_active = self.toolbars.playback.play_timer.isActive()

        if playback_active:
            self.toolbars.playback.stop()

        self.init_outputs()

        self.switch_output(self.toolbars.main.outputs_combobox.currentIndex())

        if playback_active:
            self.toolbars.playback.play()

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'window_settings': self.window_settings
        }
