from __future__ import annotations

import inspect

__all__ = [
    'is_preview'
]


def is_preview() -> bool:
    c_frame = [inspect.currentframe()]

    while (t := c_frame[-1] and c_frame[-1].f_back):
        c_frame.append(t)

    return c_frame and c_frame[-1].f_code.co_name != '<module>'
