
from __future__ import annotations

import inspect
import logging

from fractions import Fraction
from os import PathLike
from typing import Any, Iterable, Sequence, overload

from vstools import Keyframes, KwargsT, flatten, to_arr, vs

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


def set_output(
    node: vs.RawNode | Iterable[vs.RawNode | Iterable[vs.RawNode | Iterable[vs.RawNode]]],
    index_or_name: int | Sequence[int] | str | bool | None = None, name: str | bool | None = None,
    /,
    alpha: vs.VideoNode | None = None,
    *,
    timecodes: TimecodesT = None, denominator: int = 1001, scenes: ScenesT = None,
    **kwargs: Any
) -> None:
    if not is_preview():
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

    while len(index) < len(nodes):
        index.append(index[-1] + 1)

    for i, n in zip(index[:len(nodes)], nodes):
        if i in ouputs:
            logging.warn(f"Index n° {i} has been already used!")
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
            assert current_frame.f_back

            ref_id = str(id(n))
            for vname, val in reversed(current_frame.f_back.f_locals.items()):
                if (str(id(val)) == ref_id):
                    name = vname
                    break

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
