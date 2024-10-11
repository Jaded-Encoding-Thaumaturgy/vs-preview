# ruff: noqa: F401, F403

import vapoursynth

from . import qt_patch

from .api import *
from .api import is_preview

if is_preview():
    from .init import main
