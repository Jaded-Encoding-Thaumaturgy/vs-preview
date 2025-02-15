from __future__ import annotations

from .info import is_preview

__all__ = [
    'start_preview'
]


def start_preview(path: str, *args: str) -> None:
    from ..init import main

    if is_preview():
        from jetpytools import CustomRuntimeError

        raise CustomRuntimeError('You can\'t use this function from a file getting previewed!')

    main([path, *args], True)
