# flake8: noqa

import logging
from typing import Mapping, Any


from ..core import storage_err_msg
from ..core.abstracts import AbstractToolbars, AbstractMainWindow

from .benchmark import BenchmarkToolbar
from .comp import CompToolbar
from .debug import DebugToolbar
from .main import MainToolbar
from .misc import MiscToolbar
from .pipette import PipetteToolbar
from .playback import PlaybackToolbar
from .scening import SceningToolbar


all_toolbars = [
    MainToolbar, PlaybackToolbar, SceningToolbar, PipetteToolbar,
    BenchmarkToolbar, MiscToolbar, CompToolbar, DebugToolbar
]


class Toolbars(AbstractToolbars):
    yaml_tag = '!Toolbars'

    def __init__(self, main_window: AbstractMainWindow) -> None:
        for name, toolbar in zip(self.all_toolbars_names, all_toolbars):
            self.__setattr__(name, toolbar(main_window))

        for name in self.all_toolbars_names:
            self.__getattribute__(name).setObjectName(f'Toolbars.{name}')

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
                logging.warning(storage_err_msg(toolbar_name))
