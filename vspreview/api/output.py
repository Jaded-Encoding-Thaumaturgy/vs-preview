
from __future__ import annotations

import inspect
import logging

from fractions import Fraction
from os import PathLike
from types import FrameType
from typing import Any, Iterable, Sequence, overload
from jetpytools import KwargsT, to_arr

from vstools import Keyframes, flatten, vs

from .info import is_preview
from .nodes import set_scening, set_timecodes, update_node_info

__all__ = [
    'set_output'
]

TimecodesT = str | PathLike[str] | dict[tuple[int | None, int | None], float | tuple[int, int] | Fraction] | list[Fraction] | None
ScenesT = Keyframes | list[tuple[int, int]] | list[Keyframes | list[tuple[int, int]]] | None


# VideoNode signature
@overload
def set_output(
    node: vs.VideoNode,
    index: int = ...,
    /,
    *,
    alpha: vs.VideoNode | None = ...,
    timecodes: TimecodesT = None, denominator: int = 1001, scenes: ScenesT = None,
    **kwargs: Any
) -> None:
    ...


@overload
def set_output(
    node: vs.VideoNode,
    name: str | bool | None = ...,
    /,
    *,
    alpha: vs.VideoNode | None = ...,
    timecodes: TimecodesT = None, denominator: int = 1001, scenes: ScenesT = None,
    **kwargs: Any
) -> None:
    ...


@overload
def set_output(
    node: vs.VideoNode,
    index: int = ..., name: str | bool | None = ...,
    /,
    alpha: vs.VideoNode | None = ...,
    *,
    timecodes: TimecodesT = None, denominator: int = 1001, scenes: ScenesT = None,
    **kwargs: Any
) -> None:
    ...


# AudioNode signature
@overload
def set_output(
    node: vs.AudioNode,
    index: int = ...,
    /,
    **kwargs: Any
) -> None:
    ...

@overload
def set_output(
    node: vs.AudioNode,
    name: str | bool | None = ...,
    /,
    **kwargs: Any
) -> None:
    ...

@overload
def set_output(
    node: vs.AudioNode,
    index: int = ..., name: str | bool | None = ...,
    /,
    **kwargs: Any
) -> None:
    ...


# Iterable of VideoNode signature
@overload
def set_output(
    node: Iterable[vs.VideoNode | Iterable[vs.VideoNode | Iterable[vs.VideoNode]]],
    index: int | Sequence[int] = ...,
    /,
    **kwargs: Any
) -> None:
    ...


@overload
def set_output(
    node: Iterable[vs.VideoNode | Iterable[vs.VideoNode | Iterable[vs.VideoNode]]],
    name: str | bool | None = ...,
    /,
    **kwargs: Any
) -> None:
    ...


@overload
def set_output(
    node: Iterable[vs.VideoNode | Iterable[vs.VideoNode | Iterable[vs.VideoNode]]],
    index: int | Sequence[int] = ..., name: str | bool | None = ...,
    /,
    **kwargs: Any
) -> None:
    ...

# Iterable of AudioNode signature
@overload
def set_output(
    node: Iterable[vs.AudioNode | Iterable[vs.AudioNode | Iterable[vs.AudioNode]]],
    index: int | Sequence[int] = ...,
    /,
    **kwargs: Any
) -> None:
    ...


@overload
def set_output(
    node: Iterable[vs.AudioNode | Iterable[vs.AudioNode | Iterable[vs.AudioNode]]],
    name: str | bool | None = ...,
    /,
    **kwargs: Any
) -> None:
    ...


@overload
def set_output(
    node: Iterable[vs.AudioNode | Iterable[vs.AudioNode | Iterable[vs.AudioNode]]],
    index: int | Sequence[int] = ..., name: str | bool | None = ...,
    /,
    **kwargs: Any
) -> None:
    ...


# General
@overload
def set_output(
    node: vs.RawNode | Iterable[vs.RawNode | Iterable[vs.RawNode | Iterable[vs.RawNode]]],
    index: int | Sequence[int] = ..., name: str | bool | None = ...,
    /,
    **kwargs: Any
) -> None:
    ...


def set_output(
    node: vs.RawNode | Iterable[vs.RawNode | Iterable[vs.RawNode | Iterable[vs.RawNode]]],
    index_or_name: int | Sequence[int] | str | bool | None = None, name: str | bool | None = None,
    /,
    alpha: vs.VideoNode | None = None,
    *,
    timecodes: TimecodesT = None, denominator: int = 1001, scenes: ScenesT = None,
    **kwargs: Any
) -> None:
    if not is_preview() and not kwargs.get("force_preview", False):
        return None

    if isinstance(index_or_name, (str, bool)):
        index = None
        # Backward compatible with older api
        if isinstance(name, vs.VideoNode):
            alpha = name  # type: ignore[unreachable]
        name = index_or_name
    else:
        index = index_or_name

    ouputs = vs.get_outputs()
    nodes = list(flatten(node))

    index = to_arr(index) if index is not None else [max(ouputs, default=-1) + 1]

    def _get_frame_type(frame: FrameType) -> FrameType:
        f_back: int = kwargs.pop("f_back", 1)

        for _ in range(f_back):
            assert frame.f_back
            frame = frame.f_back

        return frame

    while len(index) < len(nodes):
        index.append(index[-1] + 1)

    for i, n in zip(index[:len(nodes)], nodes):
        if i in ouputs:
            logging.warning(f"Index n° {i} has been already used!")
        if isinstance(n, vs.VideoNode):
            n.set_output(i, alpha)
            title = 'Clip'
        else:
            n.set_output(i)
            title = 'Audio' if isinstance(n, vs.AudioNode) else 'Node'

        if (not name and name is not False) or name is True:
            name = f"{title} {i}"

            current_frame = inspect.currentframe()
            assert current_frame

            frame_type = _get_frame_type(current_frame)

            ref_id = str(id(n))
            for vname, val in reversed(frame_type.f_locals.items()):
                if (str(id(val)) == ref_id):
                    name = vname
                    break

            del frame_type
            del current_frame

        update_node_info(
            type(n), i,
            **KwargsT(cache=True, disable_comp=False) | (KwargsT(name=name) if name else {}) | kwargs
        )

        if isinstance(n, vs.VideoNode):
            if timecodes:
                timecodes = str(timecodes) if not isinstance(timecodes, (dict, list)) else timecodes
                set_timecodes(i, timecodes, n, denominator)

            if scenes:
                set_scening(scenes, n, name or f'Clip {i}')
