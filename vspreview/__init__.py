# ruff: noqa: F401, F403

import vapoursynth

from . import qt_patch

from .api import *
from .api import is_preview

if is_preview():
    from .init import main

__version__: str
__version_tuple__: tuple[int | str, ...]


try:
    from ._version import __version__, __version_tuple__
except ImportError:
    __version__ = "0.0.0+unknown"
    __version_tuple__ = (0, 0, 0, "+unknown")
