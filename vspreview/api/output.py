
from __future__ import annotations

import inspect
from fractions import Fraction
from pathlib import Path
from typing import Any

from vapoursynth import AudioNode, RawNode, VideoNode, get_outputs

from .nodes import set_timecodes, update_node_info

__all__ = [
    'set_output'
]


def set_output(
    node: RawNode, name: str | bool | None = None,
    *, cache: bool = True, disable_comp: bool = False,
    timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[Fraction] | None = None, denominator: int = 1001,
    **kwargs: Any
) -> None:
    index = len(get_outputs())

    ref_id = str(id(node))

    if isinstance(node, VideoNode):
        title, node_type = 'Clip', VideoNode
    elif isinstance(node, AudioNode):
        title, node_type = 'Audio', AudioNode
    else:
        title, node_type = 'Node', RawNode

    if (not name and name is not False) or name is True:
        name = f"{title} {index}"

        current_frame = inspect.currentframe()

        assert current_frame
        assert current_frame.f_back

        for vname, val in reversed(current_frame.f_back.f_locals.items()):
            if (str(id(val)) == ref_id):
                name = vname
                break

    node.set_output(index)

    update_node_info(node_type, index, cache=cache, disable_comp=disable_comp, **kwargs)

    if name:
        update_node_info(node_type, index, name=name)

    if timecodes:
        set_timecodes(index, timecodes, node, denominator)
