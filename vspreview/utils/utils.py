from __future__ import annotations

import sys
import logging
import vapoursynth as vs
from string import Template
from platform import python_version
from functools import partial, wraps
from pkg_resources import get_distribution
from asyncio import get_running_loop, get_event_loop_policy
from typing import Any, Callable, TypeVar, Tuple, cast, overload

from PyQt5.QtCore import QSignalBlocker
from PyQt5.QtWidgets import QApplication

from ..core import main_window, Frame, Time

T = TypeVar('T')
F_SL = TypeVar('F_SL', bound=Callable)


# it is a BuiltinMethodType at the same time
def qt_silent_call(qt_method: F_SL, *args: Any, **kwargs: Any) -> T:
    # https://github.com/python/typing/issues/213
    qobject = qt_method.__self__  # type: ignore
    block = QSignalBlocker(qobject)
    ret = qt_method(*args, **kwargs)
    del block
    return cast(T, ret)


class DeltaTemplate(Template):
    delimiter = '%'


def strfdelta(time: Time, output_format: str) -> str:
    seconds = time.value.seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    milliseconds = time.value.microseconds // 1000

    template = DeltaTemplate(output_format)

    return template.substitute(
        D='{:d}'.format(time.value.days),
        H='{:02d}'.format(hours),
        M='{:02d}'.format(minutes),
        S='{:02d}'.format(seconds),
        Z='{:03d}'.format(milliseconds),
        h='{:d}'.format(hours),
        m='{:2d}'.format(minutes),
        s='{:2d}'.format(seconds)
    )


def fire_and_forget(f: F_SL) -> F_SL:
    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = get_event_loop_policy().get_event_loop()
        return loop.run_in_executor(None, partial(f, *args, **kwargs))
    return wrapped


def set_status_label(label: str) -> Callable[[F_SL], F_SL]:
    def _decorator(func: Callable[..., T]) -> Any:
        @wraps(func)
        def _wrapped(*args: Any, **kwargs: Any) -> T:
            main = main_window()

            main.statusbar.label.setText(label)

            ret = func(*args, **kwargs)

            main.statusbar.label.setText('Ready')

            return ret
        return _wrapped

    return cast(Callable[[...], F_SL], _decorator)


def vs_clear_cache() -> None:
    cache_size = vs.core.max_cache_size
    vs.core.max_cache_size = 1
    for output in list(vs.get_outputs().values()):
        if isinstance(output, vs.VideoOutputTuple):
            output.clip.get_frame(int(main_window().current_output.last_showed_frame or Frame(0)))
            break
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

    if vs.core.version_number() < 57:
        logging.warning(
            'VSPreview is not tested on VapourSynth versions prior to 57, but you have {}. Use at your own risk.'
            .format(vs.core.version_number())
        )
        return False

    return True


def get_temp_screen_resolution() -> Tuple[int, int]:
    app = QApplication(sys.argv)

    geometry = app.desktop().screenGeometry()
    return (geometry.width(), geometry.height())
