from __future__ import annotations

import inspect
import logging

from fractions import Fraction
from os import PathLike
from types import FrameType
from typing import Any, Sequence, overload
from jetpytools import normalize_seq, to_arr, KwargsNotNone

from vstools import Keyframes, flatten, vs, VideoNodeIterable, AudioNodeIterable, RawNodeIterable

from .nodes import set_scening, set_timecodes, update_node_info

__all__ = ["set_output"]

TimecodesT = (
    str
    | PathLike[str]
    | dict[tuple[int | None, int | None], float | tuple[int, int] | Fraction]
    | list[Fraction]
    | None
)
ScenesT = Keyframes | list[tuple[int, int]] | list[Keyframes | list[tuple[int, int]]] | None


# VideoNode signature
@overload
def set_output(
    node: vs.VideoNode,
    index: int = ...,
    /,
    *,
    alpha: vs.VideoNode | None = ...,
    timecodes: TimecodesT = None,
    denominator: int = 1001,
    scenes: ScenesT = None,
    **kwargs: Any,
) -> None: ...


@overload
def set_output(
    node: vs.VideoNode,
    name: str | bool | None = ...,
    /,
    *,
    alpha: vs.VideoNode | None = ...,
    timecodes: TimecodesT = None,
    denominator: int = 1001,
    scenes: ScenesT = None,
    **kwargs: Any,
) -> None: ...


@overload
def set_output(
    node: vs.VideoNode,
    index: int = ...,
    name: str | bool | None = ...,
    /,
    alpha: vs.VideoNode | None = ...,
    *,
    timecodes: TimecodesT = None,
    denominator: int = 1001,
    scenes: ScenesT = None,
    **kwargs: Any,
) -> None: ...


@overload
def set_output(
    node: VideoNodeIterable | AudioNodeIterable | RawNodeIterable, index: int | Sequence[int] = ..., /, **kwargs: Any
) -> None: ...


@overload
def set_output(
    node: VideoNodeIterable | AudioNodeIterable | RawNodeIterable, name: str | bool | None = ..., /, **kwargs: Any
) -> None: ...


@overload
def set_output(
    node: VideoNodeIterable | AudioNodeIterable | RawNodeIterable,
    index: int | Sequence[int] = ...,
    name: str | bool | None = ...,
    /,
    **kwargs: Any,
) -> None: ...


def set_output(
    node: vs.VideoNode | VideoNodeIterable | AudioNodeIterable | RawNodeIterable,
    index_or_name: int | Sequence[int] | str | bool | None = None,
    name: str | bool | None = None,
    /,
    alpha: vs.VideoNode | None = None,
    *,
    timecodes: TimecodesT = None,
    denominator: int = 1001,
    scenes: ScenesT = None,
    **kwargs: Any,
) -> None:
    if isinstance(index_or_name, (str, bool)):
        index = None
        name = index_or_name
    else:
        index = index_or_name

    outputs = vs.get_outputs()
    nodes = list(flatten(node))

    indices = to_arr(index) if index is not None else [max(outputs, default=-1) + 1]
    indices = normalize_seq(indices, len(nodes))

    frame_depth = kwargs.pop("frame_depth", 1) + 1

    for i, n in zip(indices, nodes):
        if i in outputs:
            logging.warning(f"Output index {i} already in use; overwriting.")

        match n:
            case vs.VideoNode():
                n.set_output(i, alpha)
                title = "Clip"
            case vs.AudioNode():
                n.set_output(i)
                title = "Audio"
            case _:
                n.set_output(i)
                title = "Node"

        effective_name: str | None
        match name:
            case True | None:
                effective_name = _resolve_var_name(n, frame_depth=frame_depth) or f"{title} {i}"
            case False:
                effective_name = None
            case str() as s:
                effective_name = s

        update_node_info(
            type(n), i, **KwargsNotNone({"cache": True, "disable_comp": False, "name": effective_name}) | kwargs
        )

        if isinstance(n, vs.VideoNode):
            if timecodes:
                timecodes = str(timecodes) if not isinstance(timecodes, (dict, list)) else timecodes
                set_timecodes(i, timecodes, n, denominator)

            if scenes:
                set_scening(scenes, n, effective_name or f"{title} {i}")


def _resolve_var_name(obj: Any, *, frame_depth: int = 1) -> str | None:
    frame = inspect.currentframe()
    frames = list[FrameType]()
    locals_copy = {}

    try:
        for _ in range(frame_depth):
            if not frame or not frame.f_back:
                return None

            frames.append(frame)
            frame = frame.f_back

        locals_copy = frame.f_locals.copy() if frame else {}

        obj_id = id(obj)

        return next((var_name for var_name, value in reversed(locals_copy.items()) if id(value) == obj_id), None)

    finally:
        for fr in frames:
            del fr
        del frame
        del frames
        del locals_copy
