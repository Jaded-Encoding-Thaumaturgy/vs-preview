from __future__ import annotations

from   abc      import abstractmethod
import logging
from   pathlib  import Path
from   typing   import (
    Any, cast, Iterator, Mapping, Optional,
    TYPE_CHECKING, Union,
)

from   PyQt5       import Qt
from .bases import (
    AbstractYAMLObjectSingleton, QABC, QAbstractYAMLObjectSingleton,
)
from .better_abc import abstract_attribute
from .types      import Frame, Output, Time


class AbstractMainWindow(Qt.QMainWindow, QAbstractYAMLObjectSingleton):
    if TYPE_CHECKING:
        from vspreview.models  import Outputs
        from vspreview.widgets import Timeline

    __slots__ = ()

    @abstractmethod
    def load_script(self, script_path: Path, external_args: str = "") -> None:
        raise NotImplementedError

    @abstractmethod
    def reload_script(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def init_outputs(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def switch_output(self, value: Union[int, Output]) -> None:
        raise NotImplementedError()

    @abstractmethod
    def switch_frame(self, frame: Optional[Frame] = None, time: Optional[Time] = None, *, render_frame: bool = True) -> None:
        raise NotImplementedError()

    @abstractmethod
    def show_message(self, message: str, timeout: Optional[int] = None) -> None:
        raise NotImplementedError

    central_widget: Qt.QWidget        = abstract_attribute()
    clipboard     : Qt.QClipboard     = abstract_attribute()
    current_frame : Frame             = abstract_attribute()
    current_time  : Time              = abstract_attribute()
    current_output: Output            = abstract_attribute()
    display_scale : float             = abstract_attribute()
    graphics_scene: Qt.QGraphicsScene = abstract_attribute()
    graphics_view : Qt.QGraphicsView  = abstract_attribute()
    outputs       : Outputs           = abstract_attribute()
    timeline      : Timeline          = abstract_attribute()
    toolbars      : AbstractToolbars  = abstract_attribute()  # pylint: disable=used-before-assignment
    save_on_exit  : bool              = abstract_attribute()
    script_path   : Path              = abstract_attribute()
    statusbar     : Qt.QStatusBar     = abstract_attribute()


class AbstractToolbar(Qt.QWidget, QABC):
    if TYPE_CHECKING:
        from vspreview.widgets import Notches

    __slots__ = (
        'main', 'toggle_button',
    )

    if TYPE_CHECKING:
        notches_changed = Qt.pyqtSignal(AbstractToolbar)  # pylint: disable=undefined-variable
    else:
        notches_changed = Qt.pyqtSignal(object)

    def __init__(self, main: AbstractMainWindow, name: str) -> None:
        super().__init__(main.central_widget)
        self.main = main

        self.setFocusPolicy(Qt.Qt.ClickFocus)

        self.notches_changed.connect(self.main.timeline.update_notches)

        self.toggle_button = Qt.QToolButton(self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setText(name)
        self.toggle_button.clicked.connect(self.on_toggle)

        self.setVisible(False)


    def on_toggle(self, new_state: bool) -> None:
        # invoking order matters
        self.setVisible(new_state)
        self.resize_main_window(new_state)

    def on_current_frame_changed(self, frame: Frame, time: Time) -> None:
        pass

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        pass

    def on_script_unloaded(self) -> None:
        pass

    def on_script_loaded(self) -> None:
        pass

    def get_notches(self) -> Notches:
        from vspreview.widgets import Notches

        return Notches()

    def is_notches_visible(self) -> bool:
        return self.isVisible()

    def resize_main_window(self, expanding: bool) -> None:
        if self.main.windowState() in (Qt.Qt.WindowMaximized,
                                       Qt.Qt.WindowFullScreen):
            return

        if expanding:
            self.main.resize(
                self.main.width(),
                self.main.height() + self.height() + round(6 * self.main.display_scale))
        if not expanding:
            self.main.resize(
                self.main.width(),
                self.main.height() - self.height() - round(6 * self.main.display_scale))
            self.main.timeline.full_repaint()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'toggle': self.toggle_button.isChecked()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            toggle = state['toggle']
            if not isinstance(toggle, bool):
                raise TypeError
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: Toolbar: failed to parse toggle')
            toggle = self.main.TOGGLE_TOOLBAR

        if self.toggle_button.isChecked() != toggle:
            self.toggle_button.click()


class AbstractToolbars(AbstractYAMLObjectSingleton):
    yaml_tag: str = abstract_attribute()

    __slots__ = ()

    # special toolbar ignored by len()
    # and not accessible via subscription and 'in' operator
    main     : AbstractToolbar = abstract_attribute()

    playback : AbstractToolbar = abstract_attribute()
    scening  : AbstractToolbar = abstract_attribute()
    pipette  : AbstractToolbar = abstract_attribute()
    benchmark: AbstractToolbar = abstract_attribute()
    misc     : AbstractToolbar = abstract_attribute()
    debug    : AbstractToolbar = abstract_attribute()

    toolbars_names = ('playback', 'scening', 'pipette', 'benchmark', 'misc', 'debug')
    # 'main' should be the first
    all_toolbars_names = ['main'] + list(toolbars_names)

    def __getitem__(self, index: int) -> AbstractToolbar:
        if index >= len(self.toolbars_names):
            raise IndexError
        return cast(AbstractToolbar, getattr(self, self.toolbars_names[index]))

    def __len__(self) -> int:
        return len(self.toolbars_names)

    @abstractmethod
    def __getstate__(self) -> Mapping[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def __setstate__(self, state: Mapping[str, Any]) -> None:
        raise NotImplementedError

    if TYPE_CHECKING:
        # https://github.com/python/mypy/issues/2220
        def __iter__(self) -> Iterator[AbstractToolbar]: ...
