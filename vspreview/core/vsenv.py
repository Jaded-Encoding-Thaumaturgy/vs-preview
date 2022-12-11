from __future__ import annotations

import atexit
from threading import Lock
from typing import Any, Callable, TypeVar, Dict
from concurrent.futures import Future
from PyQt5.QtCore import QObject, QThreadPool, QRunnable, pyqtSignal
import runpy

from vsengine.policy import Policy, GlobalStore, ManagedEnvironment
from vsengine.loops import EventLoop, set_loop

_monkey_runpy_dicts = {}

orig_runpy_run_code = runpy._run_code


def _monkey_runpy_func(*args, **kwargs):
    glob_dict = orig_runpy_run_code(*args, **kwargs)
    if '_monkey_runpy' in glob_dict:
        _monkey_runpy_dicts[glob_dict['_monkey_runpy']] = glob_dict
    return glob_dict


runpy._run_code = _monkey_runpy_func

T = TypeVar("T")


class Runner(QRunnable):

    def __init__(self, wrapper: Callable[[], None]) -> None:
        super().__init__()
        self.wrapper = wrapper

    def run(self):
        self.wrapper()


class PyQTLoop(QObject, EventLoop):
    move = pyqtSignal(int)

    def attach(self) -> None:
        self._signal_lock = Lock()
        self._signal_counter = 0
        self._signallers: Dict[int, Callable[[], None]] = {}

        self._slot = self._receive_task
        self.move.connect(self._slot)

    def detach(self) -> None:
        self.move.disconnect(self._slot)
        self._signallers = {}

    def _receive_task(self, number: int):
        self._signallers.get(number, lambda: None)()

    def from_thread(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        fut = Future()

        with self._signal_lock:
            my_counter = self._signal_counter
            self._signal_counter += 1

        def wrapper():
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
        fut = Future()

        def wrapper():
            if not fut.set_running_or_notify_cancel():
                return

            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                fut.set_exception(e)
            else:
                fut.set_result(result)

        pool: QThreadPool = QThreadPool.globalInstance()
        pool.start(Runner(wrapper))
        return fut


def set_vsengine_loop():
    set_loop(PyQTLoop())


policy: Policy = Policy(GlobalStore())
policy.register()
environment: ManagedEnvironment = policy.new_environment()
environment.switch()


def get_current_environment():
    return environment


def make_environment():
    global environment
    assert policy is not None
    environment = policy.new_environment()
    environment.switch()


atexit.register(lambda: environment.dispose())
