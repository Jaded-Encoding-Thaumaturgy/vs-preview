from __future__ import annotations

import sys
import logging
import vapoursynth as vs
from string import Template
from platform import python_version
from psutil import cpu_count, Process
from pkg_resources import get_distribution
from asyncio import get_running_loop, get_event_loop_policy
from typing import Any, Callable, MutableMapping, Type, TypeVar
from functools import partial, wraps, singledispatch, update_wrapper

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QWidget, QShortcut
from PyQt5.QtCore import QTime, QSignalBlocker, QObject

from ..core import main_window, Time, AbstractToolbar

T = TypeVar('T')


def to_qtime(time: Time) -> QTime:
    td = time.value
    return QTime(td.seconds // 3600, td.seconds // 60, td.seconds % 60, td.microseconds // 1000)


def from_qtime(qtime: QTime, t: Type[Time]) -> Time:
    return t(milliseconds=qtime.msecsSinceStartOfDay())


# it is a BuiltinMethodType at the same time
def qt_silent_call(qt_method: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    # https://github.com/python/typing/issues/213
    qobject = qt_method.__self__  # type: ignore
    block = QSignalBlocker(qobject)
    ret = qt_method(*args, **kwargs)
    del block
    return ret


class DeltaTemplate(Template):
    delimiter = '%'


def strfdelta(time: Time, output_format: str) -> str:
    d: MutableMapping[str, str] = {}
    td = time.value
    hours = td.seconds // 3600
    minutes = td.seconds // 60
    seconds = td.seconds % 60
    milliseconds = td.microseconds // 1000
    d['D'] = '{:d}'.format(td.days)
    d['H'] = '{:02d}'.format(hours)
    d['M'] = '{:02d}'.format(minutes)
    d['S'] = '{:02d}'.format(seconds)
    d['Z'] = '{:03d}'.format(milliseconds)
    d['h'] = '{:d}'.format(hours)
    d['m'] = '{:2d}'.format(minutes)
    d['s'] = '{:2d}'.format(seconds)

    template = DeltaTemplate(output_format)
    return template.substitute(**d)


def add_shortcut(key: int, handler: Callable[[], None], widget: QWidget | None = None) -> None:
    if widget is None:
        widget = main_window()
    QShortcut(QKeySequence(key), widget).activated.connect(handler)


def fire_and_forget(f: Callable[..., T]) -> Callable[..., T]:
    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = get_event_loop_policy().get_event_loop()
        return loop.run_in_executor(None, partial(f, *args, **kwargs))
    return wrapped


def set_status_label(label: str) -> Callable[..., T]:
    def decorator(func: Callable[..., T]) -> Any:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> T:
            main = main_window()

            if main.statusbar.label.text() == 'Ready':
                main.statusbar.label.setText(label)

            ret = func(*args, **kwargs)

            if main.statusbar.label.text() == label:
                main.statusbar.label.setText('Ready')

            return ret
        return wrapped
    return decorator


def method_dispatch(func: Callable[..., T]) -> Callable[..., T]:
    '''
    https://stackoverflow.com/a/24602374
    '''
    dispatcher = singledispatch(func)

    def wrapper(*args: Any, **kwargs: Any) -> T:
        return dispatcher.dispatch(args[1].__class__)(*args, **kwargs)

    wrapper.register = dispatcher.register  # type: ignore
    update_wrapper(wrapper, dispatcher)
    return wrapper


def set_qobject_names(obj: object) -> None:
    if not hasattr(obj, '__slots__'):
        return

    slots = list(obj.__slots__)

    if isinstance(obj, AbstractToolbar) and 'main' in slots:
        slots.remove('main')

    for attr_name in slots:
        attr = getattr(obj, attr_name)
        if not isinstance(attr, QObject):
            continue
        attr.setObjectName(type(obj).__name__ + '.' + attr_name)


def get_usable_cpus_count() -> int:
    try:
        count = len(Process().cpu_affinity())
    except AttributeError:
        count = cpu_count()

    return count


def vs_clear_cache() -> None:
    cache_size = vs.core.max_cache_size
    vs.core.max_cache_size = 1
    output = list(vs.get_outputs().values())[0]
    if isinstance(output, vs.VideoOutputTuple):
        output.clip.get_frame(0)
    vs.core.max_cache_size = cache_size


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
