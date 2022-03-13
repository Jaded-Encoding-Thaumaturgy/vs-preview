from __future__ import annotations

from   functools import lru_cache, partial, wraps
import logging
from   string    import Template
from   typing    import (
    Any, Callable, Mapping, MutableMapping, Optional, Type, TYPE_CHECKING,
    TypeVar, Union,
)

from PyQt5 import Qt

from vspreview.core  import Time, TimeInterval, TimeType
from vspreview.utils import debug


T = TypeVar('T')


def to_qtime(time: Union[TimeType]) -> Qt.QTime:
    td = time.value
    return Qt.QTime(td.seconds      // 3600,
                    td.seconds      //   60,
                    td.seconds       %   60,
                    td.microseconds // 1000)


def from_qtime(qtime: Qt.QTime, t: Type[TimeType]) -> TimeType:
    return t(milliseconds=qtime.msecsSinceStartOfDay())


# it is a BuiltinMethodType at the same time
def qt_silent_call(qt_method: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    # https://github.com/python/typing/issues/213
    qobject = qt_method.__self__  # type: ignore
    block = Qt.QSignalBlocker(qobject)
    ret = qt_method(*args, **kwargs)
    del(block)
    return ret


class DeltaTemplate(Template):
    delimiter = '%'


def strfdelta(time: Union[TimeType], output_format: str) -> str:
    d: MutableMapping[str, str] = {}
    td = time.value
    hours        = td.seconds      // 3600
    minutes      = td.seconds      //   60
    seconds      = td.seconds       %   60
    milliseconds = td.microseconds // 1000
    d['D'] =   '{:d}'.format(td.days)
    d['H'] = '{:02d}'.format(hours)
    d['M'] = '{:02d}'.format(minutes)
    d['S'] = '{:02d}'.format(seconds)
    d['Z'] = '{:03d}'.format(milliseconds)
    d['h'] =   '{:d}'.format(hours)
    d['m'] =  '{:2d}'.format(minutes)
    d['s'] =  '{:2d}'.format(seconds)

    template = DeltaTemplate(output_format)
    return template.substitute(**d)


if TYPE_CHECKING:
    from vspreview.core import AbstractMainWindow


@lru_cache()
def main_window() -> AbstractMainWindow:
    from vspreview.core import AbstractMainWindow  # pylint: disable=redefined-outer-name

    app = Qt.QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            if isinstance(widget, AbstractMainWindow):
                return widget
    logging.critical('main_window() failed')
    app.exit()
    raise RuntimeError


def add_shortcut(key: int, handler: Callable[[], None], widget: Optional[Qt.QWidget] = None) -> None:
    if widget is None:
        widget = main_window()
    Qt.QShortcut(Qt.QKeySequence(key), widget).activated.connect(handler)  # type: ignore


def fire_and_forget(f: Callable[..., T]) -> Callable[..., T]:
    from asyncio import get_event_loop

    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        loop = get_event_loop()
        if callable(f):
            return loop.run_in_executor(None, partial(f, *args, **kwargs))
        else:
            raise TypeError('fire_and_forget(): Task must be a callable')
    return wrapped


def set_status_label(label: str) -> Callable[..., T]:
    def decorator(func: Callable[..., T]) -> Any:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> T:
            main = main_window()

            if main.statusbar.label.text() == 'Ready':
                # Qt.QMetaObject.invokeMethod(main.statusbar.label, 'setText', Qt.Qt.QueuedConnection,
                #                             Qt.Q_ARG(str, label))
                main.statusbar.label.setText(label)

            ret = func(*args, **kwargs)

            if main.statusbar.label.text() == label:
                # Qt.QMetaObject.invokeMethod(main.statusbar.label, 'setText', Qt.Qt.QueuedConnection,
                #                             Qt.Q_ARG(str, 'Ready'))
                main.statusbar.label.setText('Ready')

            return ret
        return wrapped
    return decorator


def method_dispatch(func: Callable[..., T]) -> Callable[..., T]:
    '''
    https://stackoverflow.com/a/24602374
    '''
    from functools import singledispatch, update_wrapper

    dispatcher = singledispatch(func)

    def wrapper(*args: Any, **kwargs: Any) -> T:
        return dispatcher.dispatch(args[1].__class__)(*args, **kwargs)

    wrapper.register = dispatcher.register  # type: ignore
    update_wrapper(wrapper, dispatcher)
    return wrapper


def set_qobject_names(obj: object) -> None:
    from vspreview.core import AbstractToolbar

    if not hasattr(obj, '__slots__'):
        return

    slots = list(obj.__slots__)

    if isinstance(obj, AbstractToolbar) and 'main' in slots:
        slots.remove('main')

    for attr_name in slots:
        attr = getattr(obj, attr_name)
        if not isinstance(attr, Qt.QObject):
            continue
        attr.setObjectName(type(obj).__name__ + '.' + attr_name)


def get_usable_cpus_count() -> int:
    from psutil import cpu_count, Process

    try:
        count = len(Process().cpu_affinity())
    except AttributeError:
        count = cpu_count()

    return count


def vs_clear_cache() -> None:
    import vapoursynth as vs

    cache_size = vs.core.max_cache_size
    vs.core.max_cache_size = 1
    output = list(vs.get_outputs().values())[0]
    if isinstance(output, vs.AlphaOutputTuple):
        output = output.clip
    output.get_frame(0)
    vs.core.max_cache_size = cache_size


def try_load(state: Mapping[str, Any], name: str, ty: Type[T], receiver: Union[T, Callable[[T], Any]], error_msg: str) -> None:
    try:
        value = state[name]
        if not isinstance(value, ty):
            raise TypeError
    except (KeyError, TypeError):
        logging.warning(error_msg)
    else:
        if isinstance(receiver, ty):
            receiver = value
        if callable(receiver):
            receiver(value)
