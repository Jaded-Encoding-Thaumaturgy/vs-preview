from __future__ import annotations

import atexit
import runpy
import sys
from concurrent.futures import Future
from threading import Lock
from typing import Any, Callable, TypeVar

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from vapoursynth import CoreCreationFlags, LogHandle
from vsengine.loops import EventLoop, set_loop  # type: ignore[import-untyped]
from vsengine.policy import GlobalStore, ManagedEnvironment, Policy, logger  # type: ignore[import-untyped]

from .logger import get_vs_logger

__all__ = [
    'PRELOADED_MODULES',

    '_monkey_runpy_dicts',

    'set_vsengine_loop',
    'get_current_environment',
    'make_environment', 'dispose_environment'
]


PRELOADED_MODULES = set(sys.modules.values())

_monkey_runpy_dicts = {}

orig_runpy_run_code = runpy._run_code  # type: ignore


class FlagsPolicy(Policy):
    def new_environment(self) -> ManagedEnvironment:
        data = self.api.create_environment(CoreCreationFlags.ENABLE_GRAPH_INSPECTION)
        env = self.api.wrap_environment(data)
        logger.debug("Created new environment")
        return ManagedEnvironment(env, data, self)


def _monkey_runpy_func(*args: Any, **kwargs: Any) -> Any:
    glob_dict = orig_runpy_run_code(*args, **kwargs)

    if '_monkey_runpy' in glob_dict:
        _monkey_runpy_dicts[glob_dict['_monkey_runpy']] = glob_dict

    return glob_dict


runpy._run_code = _monkey_runpy_func  # type: ignore

T = TypeVar("T")


class Runner(QRunnable):
    def __init__(self, wrapper: Callable[[], None]) -> None:
        super().__init__()
        self.wrapper = wrapper

    def run(self) -> None:
        self.wrapper()


class PyQTLoop(QObject, EventLoop):
    move = pyqtSignal(int)

    def attach(self) -> None:
        self._signal_lock = Lock()
        self._signal_counter = 0
        self._signallers = dict[int, Callable[[], None]]()

        self._slot = self._receive_task
        self.move.connect(self._slot)

    def detach(self) -> None:
        self.move.disconnect(self._slot)
        self._signallers = {}

    def _receive_task(self, number: int) -> None:
        self._signallers.get(number, lambda: None)()

    def from_thread(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        fut = Future[T]()

        with self._signal_lock:
            my_counter = self._signal_counter

            self._signal_counter += 1

        def wrapper() -> None:
            nonlocal my_counter

            if not fut.set_running_or_notify_cancel():
                return

            del self._signallers[my_counter]

            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                fut.set_exception(e)
            else:
                fut.set_result(result)

        self._signallers[my_counter] = wrapper
        self.move.emit(my_counter)

        return fut

    def to_thread(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        fut = Future[T]()

        def wrapper() -> None:
            if not fut.set_running_or_notify_cancel():
                return

            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                fut.set_exception(e)
            else:
                fut.set_result(result)

        QThreadPool.globalInstance().start(Runner(wrapper))

        return fut


def set_vsengine_loop() -> None:
    set_loop(PyQTLoop())


current_log: LogHandle | None = None


def make_environment() -> None:
    global environment, current_log
    assert policy is not None

    if environment and current_log:
        environment.core.remove_log_handler(current_log)

    environment = policy.new_environment()
    current_log = environment.core.add_log_handler(get_vs_logger())
    environment.switch()


def dispose_environment(env: ManagedEnvironment) -> None:
    import logging

    if current_log:
        env.core.remove_log_handler(current_log)

    if logging.getLogger().level <= logging.DEBUG:
        from gc import get_referrers

        # There has to be the environment referencing it
        ref_count = len(get_referrers(env.core)) - 1

        if ref_count:
            logging.debug(f'Core {id(env.core)} is being held reference by {ref_count} objects!')

    env.dispose()


policy: FlagsPolicy = FlagsPolicy(GlobalStore())
policy.register()

environment: ManagedEnvironment | None = None

make_environment()


def get_current_environment() -> ManagedEnvironment:
    assert environment
    return environment


def _dispose() -> None:
    global current_log

    if environment:
        dispose_environment(environment)

    current_log = None


atexit.register(_dispose)
