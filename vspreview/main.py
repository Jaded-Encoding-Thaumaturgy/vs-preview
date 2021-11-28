from __future__ import annotations

import logging
import os
from   pathlib  import Path
import sys
from   typing   import Any, cast, List, Mapping, Optional, Union

from   PyQt5       import Qt
import vapoursynth as     vs

from vspreview.core import (
    AbstractMainWindow, AbstractToolbar, AbstractToolbars,
    Frame, FrameInterval, Output, Time, TimeInterval,
)
from vspreview.models import Outputs
from vspreview.utils import (
    add_shortcut, debug, get_usable_cpus_count, qt_silent_call,
    set_qobject_names,
)
from vspreview.widgets import (
    ComboBox, StatusBar, TimeEdit, Timeline, FrameEdit,
)


# TODO: design settings
# TODO: deisgn keyboard layout
# TODO: VFR support
# TODO: move to pyside2, but it lacks single Qt namespace
#       with everything imported and it isn't type annotated.
#       See https://bugreports.qt.io/browse/PYSIDE-735
# TODO: get rid of magical constants related to 'pixel' sizes
#       (their actual units are yet to be discovered)
# TODO: move from QGraphicsView to QLabel
# TODO: utilize Qt's signals
# TODO: save window position
# TODO: make use of alpha channel of outputs
# TODO: properly mark protected members with underscore


class ScriptErrorDialog(Qt.QDialog):
    __slots__ = (
        'main', 'label', 'reload_button', 'exit_button',
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window, Qt.Qt.Dialog)
        self.main = main_window

        self.setWindowTitle('Script Loading Error')
        self.setModal(True)

        self.setup_ui()

        self.reload_button.clicked.connect(self.on_reload_clicked)
        self.exit_button  .clicked.connect(self.on_exit_clicked)

        add_shortcut(Qt.Qt.CTRL + Qt.Qt.Key_R, self.reload_button.click, self)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        main_layout = Qt.QVBoxLayout(self)
        main_layout.setObjectName('ScriptErrorDialog.setup_ui.main_layout')

        self.label = Qt.QLabel()
        main_layout.addWidget(self.label)

        buttons_widget = Qt.QWidget(self)
        buttons_widget.setObjectName(
            'ScriptErrorDialog.setup_ui.buttons_widget')
        buttons_layout = Qt.QHBoxLayout(buttons_widget)
        buttons_layout.setObjectName(
            'ScriptErrorDialog.setup_uibuttons_layout')

        self.reload_button = Qt.QPushButton(self)
        self.reload_button.setText('Reload')
        buttons_layout.addWidget(self.reload_button)

        self.exit_button = Qt.QPushButton(self)
        self.exit_button.setText('Exit')
        buttons_layout.addWidget(self.exit_button)

        main_layout.addWidget(buttons_widget)

    def on_reload_clicked(self, clicked: Optional[bool] = None) -> None:
        self.hide()
        self.main.reload_script()

    def on_exit_clicked(self, clicked: Optional[bool] = None) -> None:
        self.hide()
        self.main.save_on_exit = False
        self.main.app.exit()

    def closeEvent(self, event: Qt.QCloseEvent) -> None:
        self.on_exit_clicked()


class MainToolbar(AbstractToolbar):
    __slots__ = (
        'outputs', 'zoom_levels',
        'outputs_combobox', 'frame_control', 'time_control',
        'zoom_combobox', 'switch_timeline_mode_button',
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        from vspreview.models import ZoomLevels

        super().__init__(main_window, 'Main')
        self.setup_ui()

        self.outputs = Outputs()
        self.outputs_combobox.setModel(self.outputs)

        self.zoom_levels = ZoomLevels([
            #0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0
            0.5, 1.0, 2.0, 4.0, 8.0, 16.0
        ])
        self.zoom_combobox.setModel(self.zoom_levels)
        self.zoom_combobox.setCurrentIndex(1)

        self.outputs_combobox.currentIndexChanged.connect(self.main.switch_output)
        self.frame_control          .valueChanged.connect(self.main.switch_frame)
        self.time_control           .valueChanged.connect(self.main.switch_frame)
        self.frame_control       .editingFinished.connect(self.frame_control.clearFocus)  # type: ignore
        self.time_control        .editingFinished.connect(self.time_control.clearFocus)  # type: ignore
        self.sync_outputs_checkbox  .stateChanged.connect(self.on_sync_outputs_changed)
        self.zoom_combobox    .currentTextChanged.connect(self.on_zoom_changed)
        self.switch_timeline_mode_button .clicked.connect(self.on_switch_timeline_mode_clicked)

        add_shortcut(Qt.Qt.Key_1, lambda: self.main.switch_output(0))
        add_shortcut(Qt.Qt.Key_2, lambda: self.main.switch_output(1))
        add_shortcut(Qt.Qt.Key_3, lambda: self.main.switch_output(2))
        add_shortcut(Qt.Qt.Key_4, lambda: self.main.switch_output(3))
        add_shortcut(Qt.Qt.Key_5, lambda: self.main.switch_output(4))
        add_shortcut(Qt.Qt.Key_6, lambda: self.main.switch_output(5))
        add_shortcut(Qt.Qt.Key_7, lambda: self.main.switch_output(6))
        add_shortcut(Qt.Qt.Key_8, lambda: self.main.switch_output(7))
        add_shortcut(Qt.Qt.Key_9, lambda: self.main.switch_output(8))
        add_shortcut(Qt.Qt.Key_0, lambda: self.main.switch_output(9))
        add_shortcut(Qt.Qt.Key_S,         self.sync_outputs_checkbox.click)
        add_shortcut(Qt.Qt.CTRL               + Qt.Qt.Key_Tab, lambda: self.main.switch_output(self.outputs_combobox.currentIndex() + 1))
        add_shortcut(Qt.Qt.CTRL + Qt.Qt.SHIFT + Qt.Qt.Key_Tab, lambda: self.main.switch_output(self.outputs_combobox.currentIndex() - 1))

        set_qobject_names(self)

    def setup_ui(self) -> None:
        self.setVisible(True)
        layout = Qt.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.outputs_combobox = ComboBox[Output](self)
        self.outputs_combobox.setEditable(True)
        self.outputs_combobox.setInsertPolicy(Qt.QComboBox.InsertAtCurrent)
        self.outputs_combobox.setDuplicatesEnabled(True)
        self.outputs_combobox.setSizeAdjustPolicy(
            Qt.QComboBox.AdjustToContents)
        layout.addWidget(self.outputs_combobox)

        self.frame_control = FrameEdit[Frame](self)
        self.frame_control.setKeyboardTracking(False)
        layout.addWidget(self.frame_control)

        self.time_control = TimeEdit[Time](self)
        self.time_control.setKeyboardTracking(False)
        layout.addWidget(self.time_control)

        self.sync_outputs_checkbox = Qt.QCheckBox(self)
        self.sync_outputs_checkbox.setText('Sync Outputs')
        self.sync_outputs_checkbox.setChecked(self.main.SYNC_OUTPUTS)
        layout.addWidget(self.sync_outputs_checkbox)

        self.zoom_combobox = ComboBox[float](self)
        self.zoom_combobox.setMinimumContentsLength(4)
        layout.addWidget(self.zoom_combobox)

        self.switch_timeline_mode_button = Qt.QPushButton(self)
        self.switch_timeline_mode_button.setText('Timeline: Time')
        layout.addWidget(self.switch_timeline_mode_button)

        layout.addStretch()

        self.toggle_button.setVisible(False)

    def on_current_frame_changed(self, frame: Frame, time: Time) -> None:
        qt_silent_call(self.frame_control.setValue, frame)
        qt_silent_call(self. time_control.setValue,  time)

        if self.sync_outputs_checkbox.isChecked():
            for output in self.main.outputs:
                output.frame_to_show = frame

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.outputs_combobox.setCurrentIndex, index)
        qt_silent_call(self.frame_control.setMaximum,
                       self.main.current_output.end_frame)
        qt_silent_call(self. time_control.setMaximum,
                       self.main.current_output.end_time)


    def rescan_outputs(self) -> None:
        self.outputs = Outputs()
        self.main.init_outputs()
        self.outputs_combobox.setModel(self.outputs)

    def on_sync_outputs_changed(self, state: Qt.Qt.CheckState) -> None:
        if state == Qt.Qt.Checked:
            for output in self.main.outputs:
                output.frame_to_show = self.main.current_frame
        if state == Qt.Qt.Unchecked:
            for output in self.main.outputs:
                output.frame_to_show = None

    def on_switch_timeline_mode_clicked(self, checked: Optional[bool] = None) -> None:
        if self.main.timeline.mode == self.main.timeline.Mode.TIME:
            self.main.timeline.mode = self.main.timeline.Mode.FRAME
            self.switch_timeline_mode_button.setText('Timeline: Frame')
        elif self.main.timeline.mode == self.main.timeline.Mode.FRAME:
            self.main.timeline.mode = self.main.timeline.Mode.TIME
            self.switch_timeline_mode_button.setText('Timeline: Time')

    def on_zoom_changed(self, text: Optional[str] = None) -> None:
        self.main.graphics_view.setZoom(self.zoom_combobox.currentData())

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'current_output_index': self.outputs_combobox.currentIndex(),
            'outputs'             : self.outputs,
            'sync_outputs'        : self.sync_outputs_checkbox.isChecked()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            self.outputs = state['outputs']
            self.main.init_outputs()
            self.outputs_combobox.setModel(self.outputs)
        except KeyError:
            logging.warning(
                'Storage loading: Main toolbar: failed to parse outputs.')

        try:
            self.main.switch_output(state['current_output_index'])
            if self.outputs_combobox.currentIndex() == -1:
                raise ValueError
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: Main toolbar: failed to parse output index.')
            self.main.switch_output(self.main.OUTPUT_INDEX)
        except ValueError:
            logging.warning(
                'Storage loading: Main toolbar: stored output index is not valid.')
            self.main.switch_output(self.main.OUTPUT_INDEX)

        try:
            sync_outputs = state['sync_outputs']
            if not isinstance(sync_outputs, bool):
                raise TypeError
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: Main toolbar: failed to parse sync outputs.')
            sync_outputs = self.main.SYNC_OUTPUTS

        self.sync_outputs_checkbox.setChecked(sync_outputs)


class Toolbars(AbstractToolbars):
    yaml_tag = '!Toolbars'

    def __init__(self, main_window: AbstractMainWindow) -> None:
        from vspreview.toolbars import (
            DebugToolbar, MiscToolbar, PlaybackToolbar, SceningToolbar,
            BenchmarkToolbar, PipetteToolbar,
        )

        self.main      =      MainToolbar(main_window)
        self.main.setObjectName('Toolbars.main')

        self.misc      =      MiscToolbar(main_window)
        self.playback  =  PlaybackToolbar(main_window)
        self.scening   =   SceningToolbar(main_window)
        self.pipette   =   PipetteToolbar(main_window)
        self.benchmark = BenchmarkToolbar(main_window)
        self.debug     =     DebugToolbar(main_window)

        self.misc     .setObjectName('Toolbars.misc')
        self.playback .setObjectName('Toolbars.playback')
        self.scening  .setObjectName('Toolbars.scening')
        self.pipette  .setObjectName('Toolbars.pipette')
        self.benchmark.setObjectName('Toolbars.benchmark')
        self.debug    .setObjectName('Toolbars.debug')


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
                logging.warning(
                    f'Storage loading: failed to parse storage of {toolbar_name}.')


class MainWindow(AbstractMainWindow):
    # those are defaults that can be overriden at runtime or used as fallbacks
    ALWAYS_SHOW_SCENE_MARKS   = False
    AUTOSAVE_INTERVAL         =    60 * 1000  # s
    BASE_PPI                  =    96  # PPI
    BENCHMARK_CLEAR_CACHE     = False
    BENCHMARK_REFRESH_INTERVAL =  150  # ms
    CHECKERBOARD_ENABLED      =  True
    CHECKERBOARD_TILE_COLOR_1 = Qt.Qt.white
    CHECKERBOARD_TILE_COLOR_2 = Qt.Qt.lightGray
    CHECKERBOARD_TILE_SIZE    =     8  # px
    DARK_THEME                =  True
    FPS_AVERAGING_WINDOW_SIZE = FrameInterval(100)
    FPS_REFRESH_INTERVAL      =   150  # ms
    LOG_LEVEL         = logging.DEBUG
    OPENGL_RENDERING          = False
    ORDERED_OUTPUTS           = False
    OUTPUT_INDEX              =     0
    PLAY_BUFFER_SIZE = FrameInterval(get_usable_cpus_count())
    PNG_COMPRESSION_LEVEL     =     0  # 0 - 100
    SAVE_TEMPLATE = '{script_name}_{frame}'
    SEEK_STEP                 =     1  # frames
    STATUSBAR_MESSAGE_TIMEOUT =     3 * 1000  # s
    STORAGE_BACKUPS_COUNT     =     2
    SYNC_OUTPUTS              = True
    # it's allowed to stretch target interval betweewn notches by N% at most
    TIMELINE_LABEL_NOTCHES_MARGIN = 20  # %
    TIMELINE_MODE             = 'frame'
    TOGGLE_TOOLBAR           = False
    VSP_DIR_NAME              = '.vspreview'
    # used for formats with subsampling
    VS_OUTPUT_RESIZER         = Output.Resizer.Bicubic
    VS_OUTPUT_MATRIX          = Output.Matrix.BT709
    VS_OUTPUT_TRANSFER        = Output.Transfer.BT709
    VS_OUTPUT_PRIMARIES       = Output.Primaries.BT709
    VS_OUTPUT_RANGE           = Output.Range.LIMITED
    VS_OUTPUT_CHROMALOC       = Output.ChromaLoc.LEFT
    VS_OUTPUT_PREFER_PROPS    = True
    VS_OUTPUT_RESIZER_KWARGS  = {  # type: Mapping[str, str]
        'dither_type': 'error_diffusion',
    }
    # status bar
    STATUS_FRAME_PROP = lambda prop: 'Type: %s' % (prop['_PictType'].decode('utf-8') if '_PictType' in prop else '?')

    BENCHMARK_FRAME_DATA_SHARING_FIX  =  True
    DEBUG_PLAY_FPS                    = False
    DEBUG_TOOLBAR                     = False
    DEBUG_TOOLBAR_BUTTONS_PRINT_STATE = False

    yaml_tag = '!MainWindow'

    storable_attrs = [
        'toolbars',
    ]
    __slots__ = storable_attrs + [
        'app', 'display_scale', 'clipboard',
        'script_path', 'save_on_exit', 'timeline', 'main_layout',
        'graphics_scene', 'graphics_view', 'script_error_dialog',
        'central_widget', 'statusbar',
        'opengl_widget', 'external_args',
        'script_exec_failed'
    ]

    def __init__(self, config_dir: Path) -> None:
        from qdarkstyle import load_stylesheet_pyqt5

        super().__init__()

        # logging

        # ???

        self.config_dir = config_dir / self.VSP_DIR_NAME

        self.app = Qt.QApplication.instance()
        if self.DARK_THEME:
            self.app.setStyleSheet(self.patch_dark_stylesheet(load_stylesheet_pyqt5()))
            self.ensurePolished()

        self.display_scale = self.app.primaryScreen().logicalDotsPerInch() / self.BASE_PPI
        self.setWindowTitle('VSPreview')
        self.move(400, 0)
        self.setup_ui()

        # global

        self.clipboard    = self.app.clipboard()
        self.external_args: List[str] = []
        self.script_path  = Path()
        self.save_on_exit = True
        self.script_exec_failed = False

        # graphics view

        self.graphics_scene = Qt.QGraphicsScene(self)
        self.graphics_view.setScene(self.graphics_scene)
        self.opengl_widget = None
        if self.OPENGL_RENDERING:
            self.opengl_widget = Qt.QOpenGLWidget()
            self.graphics_view.setViewport(self.opengl_widget)

        self.graphics_view.wheelScrolled.connect(self.on_wheel_scrolled)

        # timeline

        self.timeline.clicked.connect(self.switch_frame)

        # init toolbars and outputs

        self.toolbars = Toolbars(self)
        self.main_layout.addWidget(self.toolbars.main)
        for toolbar in self.toolbars:
            self.main_layout.addWidget(toolbar)
            self.toolbars.main.layout().addWidget(toolbar.toggle_button)

        set_qobject_names(self)
        self.setObjectName('MainWindow')

    def setup_ui(self) -> None:
        from vspreview.widgets import GraphicsView

        # mainWindow.resize(1300, 808)

        self.central_widget = Qt.QWidget(self)
        self.main_layout = Qt.QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.graphics_view = GraphicsView(self.central_widget)
        self.graphics_view.setBackgroundBrush(
            self.palette().brush(Qt.QPalette.Window))
        self.graphics_view.setSizePolicy(Qt.QSizePolicy.Fixed,
                                         Qt.QSizePolicy.Fixed)
        self.graphics_view.setDragMode(Qt.QGraphicsView.ScrollHandDrag)
        self.graphics_view.setTransformationAnchor(
            GraphicsView.AnchorUnderMouse)
        self.main_layout.addWidget(self.graphics_view)

        self.timeline = Timeline(self.central_widget)
        self.main_layout.addWidget(self.timeline)

        # status bar

        self.statusbar = StatusBar(self.central_widget)

        self.statusbar.total_frames_label = Qt.QLabel(self.central_widget)
        self.statusbar.total_frames_label.setObjectName(
            'MainWindow.statusbar.total_frames_label')
        self.statusbar.addWidget(self.statusbar.total_frames_label)

        self.statusbar.duration_label = Qt.QLabel(self.central_widget)
        self.statusbar.duration_label.setObjectName(
            'MainWindow.statusbar.duration_label')
        self.statusbar.addWidget(self.statusbar.duration_label)

        self.statusbar.resolution_label = Qt.QLabel(self.central_widget)
        self.statusbar.resolution_label.setObjectName(
            'MainWindow.statusbar.resolution_label')
        self.statusbar.addWidget(self.statusbar.resolution_label)

        self.statusbar.pixel_format_label = Qt.QLabel(self.central_widget)
        self.statusbar.pixel_format_label.setObjectName(
            'MainWindow.statusbar.pixel_format_label')
        self.statusbar.addWidget(self.statusbar.pixel_format_label)

        self.statusbar.fps_label = Qt.QLabel(self.central_widget)
        self.statusbar.fps_label.setObjectName('MainWindow.statusbar.fps_label')
        self.statusbar.addWidget(self.statusbar.fps_label)

        self.statusbar.frame_props_label = Qt.QLabel(self.central_widget)
        self.statusbar.frame_props_label.setObjectName('MainWindow.statusbar.frame_props_label')
        self.statusbar.addWidget(self.statusbar.frame_props_label)

        self.statusbar.label = Qt.QLabel(self.central_widget)
        self.statusbar.label.setObjectName('MainWindow.statusbar.label')
        self.statusbar.addPermanentWidget(self.statusbar.label)

        self.setStatusBar(self.statusbar)

        # dialogs

        self.script_error_dialog = ScriptErrorDialog(self)

    def patch_dark_stylesheet(self, stylesheet: str) -> str:
        return stylesheet \
            + ' QGraphicsView { border: 0px; padding: 0px; }' \
            + ' QToolButton { padding: 0px; }'

    def load_script(self, script_path: Path, external_args: List[tuple[str, str]] = None, reloading = False) -> None:
        from traceback import FrameSummary, TracebackException

        self.toolbars.playback.stop()
        self.setWindowTitle('VSPreview: %s %s' % (script_path, external_args))

        self.statusbar.label.setText('Evaluating')
        self.script_path = script_path
        sys.path.append(str(self.script_path.parent))

        # Rewrite args so external args will be forwarded correctly
        if external_args:
            self.external_args = external_args
        argv_orig = sys.argv
        sys.argv = [script_path.name]

        try:
            # pylint: disable=exec-used
            exec(self.script_path.read_text(encoding='utf-8'),
                dict([('__file__', sys.argv[0])] + self.external_args))
        except Exception as e:  # pylint: disable=broad-except
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

        if not reloading :
            self.toolbars.main.rescan_outputs()
            for toolbar in self.toolbars:
                toolbar.on_script_loaded()
            self.switch_output(self.OUTPUT_INDEX)

            self.load_storage()
        else:
            self.load_storage()
            for toolbar in self.toolbars:
                toolbar.on_script_loaded()

    def load_storage(self) -> None:
        import yaml

        vsp_dir = self.config_dir
        storage_path = vsp_dir / (self.script_path.stem + '.yml')

        if not storage_path.exists():
            storage_path = self.script_path.with_suffix('.yml')

        if storage_path.exists():
            try:
                with storage_path.open() as storage_file: 
                    yaml.load(storage_file, Loader=yaml.Loader)
            except yaml.YAMLError as exc:
                if isinstance(exc, yaml.MarkedYAMLError):
                    logging.warning(
                        'Storage parsing failed at line {}:{} ({} {}).'
                        'Using defaults.'
                        .format(exc.problem_mark.line + 1,
                                exc.problem_mark.column + 1,
                                exc.problem,
                                exc.context))  # pylint: disable=no-member
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

            raw_frame_item = self.graphics_scene.addPixmap(Qt.QPixmap.fromImage(frame_image))
            raw_frame_item.hide()

            frame_item = GraphicsImageItem(raw_frame_item, frame_image)
            output.graphics_scene_item = frame_item

    def reload_script(self) -> None:
        import gc

        if not self.script_exec_failed:
            self.toolbars.misc.save_sync()
        for toolbar in self.toolbars:
            toolbar.on_script_unloaded()
            
        vs.clear_outputs()
        self.graphics_scene.clear()
        self.outputs.clear()
        # make sure old filter graph is freed
        gc.collect()

        self.load_script(self.script_path, reloading=True)

        self.show_message('Reloaded successfully')

    def render_frame(self, frame: Frame, output: Optional[Output] = None) -> Qt.QImage:
        return self.current_output.render_frame(frame)

    def switch_frame(self, pos: Union[Frame, Time], *, render_frame: bool = True) -> None:
        if isinstance(pos, Frame):
            frame = pos
            time = Time(frame)
        elif isinstance(pos, Time):
            frame = Frame(pos)
            time = pos
        else:
            logging.debug('switch_frame(): position is neither Frame nor Time')
            return
        if frame > self.current_output.end_frame:
            return

        self.current_output.last_showed_frame = frame

        self.timeline.set_position(frame)
        self.toolbars.main.on_current_frame_changed(frame, time)
        for toolbar in self.toolbars:
            toolbar.on_current_frame_changed(frame, time)

        if render_frame:
            self.current_output.graphics_scene_item.setImage(self.render_frame(frame))

        self.statusbar.frame_props_label.setText(MainWindow.STATUS_FRAME_PROP(self.current_output.cur_frame[0].props))

    def switch_output(self, value: Union[int, Output]) -> None:
        if len(self.outputs) == 0:
            return
        if isinstance(value, Output):
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
        self.graphics_scene.setSceneRect(
            Qt.QRectF(self.current_output.graphics_scene_item.pixmap().rect()))
        self.timeline.update_notches()
        for toolbar in self.toolbars:
            toolbar.on_current_output_changed(index, prev_index)
        self.update_statusbar_output_info()

    @property  # type: ignore
    def current_output(self) -> Output:  # type: ignore
        output = cast(Output,
                      self.toolbars.main.outputs_combobox.currentData())
        return output

    @current_output.setter
    def current_output(self, value: Output) -> None:
        self.switch_output(self.outputs.index_of(value))

    @property  # type: ignore
    def current_frame(self) -> Frame:  # type: ignore
        return self.current_output.last_showed_frame

    @current_frame.setter
    def current_frame(self, value: Frame) -> None:
        self.switch_frame(value)

    @property  # type: ignore
    def current_time(self) -> Time:  # type: ignore
        return Time(self.current_output.last_showed_frame)

    @current_time.setter
    def current_time(self, value: Time) -> None:
        self.switch_frame(value)

    @property
    def outputs(self) -> Outputs:  # type: ignore
        return cast(Outputs, self.toolbars.main.outputs)


    def handle_script_error(self, message: str) -> None:
        # logging.error(message)
        self.script_error_dialog.label.setText(message)
        self.script_error_dialog.open()

    def on_wheel_scrolled(self, steps: int) -> None:
        new_index = self.toolbars.main.zoom_combobox.currentIndex() + steps
        if new_index < 0:
            new_index = 0
        elif new_index >= len(self.toolbars.main.zoom_levels):
            new_index = len(self.toolbars.main.zoom_levels) - 1
        self.toolbars.main.zoom_combobox.setCurrentIndex(new_index)

    def show_message(self, message: str, timeout: Optional[int] = None) -> None:
        if timeout is None:
            timeout = self.STATUSBAR_MESSAGE_TIMEOUT
        self.statusbar.showMessage(message, timeout)

    def update_statusbar_output_info(self, output: Optional[Output] = None) -> None:
        if output is None:
            output = self.current_output

        self.statusbar.total_frames_label.setText(
            '{} frames'.format(output.total_frames))
        self.statusbar.duration_label.setText(
            # Display duration without -1 offset to match other video tools
            '{}'.format(TimeInterval(self.current_output.total_frames)))
        self.statusbar.resolution_label.setText(
            '{}x{}'.format(output.width, output.height))
        if not output.has_alpha:
            self.statusbar.pixel_format_label.setText(
                '{}'.format(output.format.name))
        else:
            self.statusbar.pixel_format_label.setText(
                'Clip: {}, Alpha: {}'.format(output.format.name,
                                             output.format_alpha.name))
        if output.fps_den != 0:
            self.statusbar.fps_label.setText(
                '{}/{} = {:.3f} fps'.format(output.fps_num, output.fps_den,
                                            output.fps_num / output.fps_den))
        else:
            self.statusbar.fps_label.setText(
                '{}/{} fps'.format(output.fps_num, output.fps_den))

    def event(self, event: Qt.QEvent) -> bool:
        if event.type() == Qt.QEvent.LayoutRequest:
            self.timeline.full_repaint()

        return super().event(event)

    # misc methods

    def showEvent(self, event: Qt.QShowEvent) -> None:
        super().showEvent(event)
        self.graphics_view.setSizePolicy(
            Qt.QSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding))

    def closeEvent(self, event: Qt.QCloseEvent) -> None:
        if self.save_on_exit:
            self.toolbars.misc.save()

    def __getstate__(self) -> Mapping[str, Any]:
        state = {
            attr_name: getattr(self, attr_name)
            for attr_name in self.storable_attrs
        }
        state.update({
            'timeline_mode': self.timeline.mode,
            'window_geometry': bytes(self.saveGeometry()),
            'window_state': bytes(self.saveState()),
        })
        return state

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        # toolbars is singleton,
        # so it initialize itself right in its __setstate__()

        try:
            timeline_mode = state['timeline_mode']
            if not Timeline.Mode.is_valid(timeline_mode):
                raise TypeError
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: failed to parse timeline mode.'
                ' Using default.')
            timeline_mode = self.TIMELINE_MODE
        self.timeline.mode = timeline_mode

        try:
            window_geometry = state['window_geometry']
            if not isinstance(window_geometry, bytes):
                raise TypeError
            self.restoreGeometry(window_geometry)
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: failed to parse window geometry.'
                ' Using default.')

        try:
            window_state = state['window_state']
            if not isinstance(window_state, bytes):
                raise TypeError
            self.restoreState(window_state)
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: failed to parse window state.'
                ' Using default.')

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
    app = Qt.QApplication(sys.argv)
    main_window = MainWindow(Path(os.getcwd()) if args.preserve_cwd else script_path.parent)
    ext_args = [ tuple(a.split('=', maxsplit=1)) for a in args.arg or [] ]
    main_window.load_script(script_path, external_args=ext_args)
    main_window.show()

    try:
        app.exec_()
    except Exception:  # pylint: disable=broad-except
        logging.error('app.exec_() exception')


def check_versions() -> bool:
    from pkg_resources import get_distribution
    from platform import python_version

    failed = False

    if sys.version_info < (3, 9, 0, 'final', 0):
        logging.warning('VSPreview is not tested on Python versions prior to 3.9, but you have {} {}. Use at your own risk.'
                        .format(python_version(), sys.version_info.releaselevel))
        failed = True

    if get_distribution('PyQt5').version < '5.15':
        logging.warning('VSPreview is not tested on PyQt5 versions prior to 5.15, but you have {}. Use at your own risk.'
                        .format(get_distribution('PyQt5').version))
        failed = True

    if vs.core.version_number() < 53:
        logging.warning('VSPreview is not tested on VapourSynth versions prior to 53, but you have {}. Use at your own risk.'
                        .format(vs.core.version_number()))
        failed = True

    return not failed


if __name__ == '__main__':
    main()
