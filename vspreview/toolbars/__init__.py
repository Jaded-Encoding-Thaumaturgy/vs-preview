# flake8: noqa

import logging
from typing import Mapping, Any


from ..core import storage_err_msg
from ..core.abstracts import AbstractToolbars, AbstractMainWindow

from .benchmark import BenchmarkToolbar
from .debug import DebugToolbar
from .main import MainToolbar
from .misc import MiscToolbar
from .pipette import PipetteToolbar
from .playback import PlaybackToolbar
from .scening import SceningToolbar


class Toolbars(AbstractToolbars):
    yaml_tag = '!Toolbars'

    def __init__(self, main_window: AbstractMainWindow) -> None:
        self.main = MainToolbar(main_window)
        self.main.setObjectName('Toolbars.main')

        self.misc = MiscToolbar(main_window)
        self.playback = PlaybackToolbar(main_window)
        self.scening = SceningToolbar(main_window)
        self.pipette = PipetteToolbar(main_window)
        self.benchmark = BenchmarkToolbar(main_window)
        self.debug = DebugToolbar(main_window)

        self.misc.setObjectName('Toolbars.misc')
        self.playback.setObjectName('Toolbars.playback')
        self.scening.setObjectName('Toolbars.scening')
        self.pipette.setObjectName('Toolbars.pipette')
        self.benchmark.setObjectName('Toolbars.benchmark')
        self.debug.setObjectName('Toolbars.debug')

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
