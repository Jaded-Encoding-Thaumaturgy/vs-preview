from __future__ import annotations

import inspect

__all__ = [
    'is_preview'
]


def is_preview() -> bool:
    c_frame = [inspect.currentframe()]

    while (t := c_frame[-1] and c_frame[-1].f_back):
        c_frame.append(t)

        if t and '__name__' in t.f_locals:
            if t.f_locals['__name__'] == '__vspreview__':
                c_frame.clear()
                return True

    c_frame.clear()
    return False
