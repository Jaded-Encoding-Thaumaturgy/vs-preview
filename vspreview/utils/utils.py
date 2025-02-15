from __future__ import annotations

import sys
from functools import partial, wraps
from string import Template
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import QSignalBlocker, QTime

if TYPE_CHECKING:
    from jetpytools import F, P, R, T

from ..core.types import Time

__all__ = [
    'exit_func',

    'strfdelta',

    'qt_silent_call',
    'fire_and_forget',

    'set_status_label',

    'to_qtime',
    'from_qtime'
]


def exit_func(ret_code: int, no_exit: bool) -> int:
    if not no_exit:
        sys.exit(ret_code)

    return ret_code


# it is a BuiltinMethodType at the same time
def qt_silent_call(qt_method: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    block = QSignalBlocker(qt_method.__self__)  # type: ignore
    ret = qt_method(*args, **kwargs)
    del block
    return ret


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


def fire_and_forget(f: F) -> F:
    from asyncio import new_event_loop, get_running_loop

    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = new_event_loop()
        return loop.run_in_executor(None, partial(f, *args, **kwargs))

    return wrapped  # type: ignore


def set_status_label(label_before: str, label_after: str = 'Ready') -> Callable[[F], F]:
    from ..core import main_window

    def _decorator(func: Callable[..., T]) -> Any:
        @wraps(func)
        def _wrapped(*args: Any, **kwargs: Any) -> T:
            main = main_window()

            main.show_message(label_before)

            ret = func(*args, **kwargs)

            main.show_message(label_after)

            return ret
        return _wrapped

    return _decorator


def to_qtime(time: Time) -> QTime:
    seconds = time.value.seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    milliseconds = time.value.microseconds // 1000
    return QTime(hours, minutes, seconds, milliseconds)


def from_qtime(qtime: QTime, t: type[Time]) -> Time:
    return t(milliseconds=qtime.msecsSinceStartOfDay())
