from __future__ import annotations

from asyncio import get_event_loop_policy, get_running_loop
from functools import partial, wraps
from string import Template
from typing import Any, Callable, cast

from PyQt6.QtCore import QSignalBlocker
from vstools import F, P, R, T, vs

from ..core import Frame, Time, main_window


# it is a BuiltinMethodType at the same time
def qt_silent_call(qt_method: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    block = QSignalBlocker(qt_method.__self__)
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
    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = get_event_loop_policy().get_event_loop()
        return loop.run_in_executor(None, partial(f, *args, **kwargs))
    return cast(F, wrapped)


def set_status_label(label: str) -> Callable[[F], F]:
    def _decorator(func: Callable[..., T]) -> Any:
        @wraps(func)
        def _wrapped(*args: Any, **kwargs: Any) -> T:
            main = main_window()

            main.statusbar.label.setText(label)

            ret = func(*args, **kwargs)

            main.statusbar.label.setText('Ready')

            return ret
        return _wrapped

    return cast(Callable[[F], F], _decorator)


def vs_clear_cache() -> None:
    cache_size = vs.core.max_cache_size
    vs.core.max_cache_size = 1
    for output in list(vs.get_outputs().values()):
        if isinstance(output, vs.VideoOutputTuple):
            output.clip.get_frame(int(main_window().current_output.last_showed_frame or Frame(0)))
            break
    vs.core.max_cache_size = cache_size
