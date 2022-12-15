
from __future__ import annotations

import inspect
from fractions import Fraction
from pathlib import Path

from vstools import vs

from .info import is_preview
from .timecodes import set_timecodes

__all__ = [
    'set_output'
]


def set_output(
    node: vs.RawNode, name: str | bool | None = None,
    *, timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[Fraction] | None = None, denominator: int = 1001
) -> None:
    index = len(vs.get_outputs())

    ref_id = str(id(node))

    if isinstance(node, vs.VideoNode):
        title, node_type = 'Clip', vs.VideoNode
    elif isinstance(node, vs.AudioNode):
        title, node_type = 'Audio', vs.AudioNode
    else:
        title, node_type = 'Node', vs.RawNode

    if not name or name is True:
        name = f"{title} {index}"

        current_frame = inspect.currentframe()

        assert current_frame
        assert current_frame.f_back

        for vname, val in reversed(current_frame.f_back.f_locals.items()):
            if (str(id(val)) == ref_id):
                name = vname
                break

    node.set_output(index)

    if is_preview():
        from ..core import main_window

        if isinstance(name, str):
            main_window().set_node_name(node_type, index, name.title())  # type: ignore

        if timecodes:
            set_timecodes(index, timecodes, (
                node.fps_den if (node.fps_den and node.fps_num) else 1001
            ) if denominator is None else denominator)
