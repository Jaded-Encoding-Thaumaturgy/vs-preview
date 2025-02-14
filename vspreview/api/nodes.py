
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from jetpytools import ndigits
from vapoursynth import AudioNode, RawNode, VideoNode
from vstools import Keyframes

from .info import is_preview

__all__ = [
    'set_timecodes',

    'set_scening',

    'update_node_info'
]


def set_timecodes(
    index: int, timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[Fraction], node: VideoNode | None = None, den: int = 1001
) -> None:
    if not is_preview():
        return

    from ..core import main_window

    if isinstance(node, VideoNode) and node.fps_den and node.fps_num:
        den = node.fps_den

    main_window().update_timecodes_info(index, timecodes, den)


def set_scening(
    scenes: Keyframes | list[tuple[int, int]] | list[Keyframes | list[tuple[int, int]]], node: VideoNode, name: str
) -> None:
    if not is_preview():
        return

    from ..core import main_window
    from ..models.scening import Scene, SceningList, Frame

    if isinstance(scenes, Keyframes) or all(isinstance(s, tuple) for s in scenes):
        scenes = [scenes]

    sscenes = [
        [
            (max(r.start, 0), min(r.stop, node.num_frames) - 1)
            for r in scene.scenes.values()
        ] if isinstance(scene, Keyframes) else [scene]
        for scene in cast(list[Keyframes | list[tuple[int, int]]], scenes)
    ]

    mapped_scenes = [
        [
            Scene(Frame(start), Frame(end), f'Scene #{i:0{ndigits(len(scene))}}') for i, (start, end) in enumerate(scene)
        ] for scene in sscenes
    ]

    main_window().set_temporary_scenes([
        SceningList(
            ('Keyframes' if isinstance(scenes[i], Keyframes) else 'Temporary Scene') + f' - {name}',
            node.num_frames, scene, temporary=True
        ) for i, scene in enumerate(mapped_scenes)
    ])


def update_node_info(node_type: type[RawNode] | type[VideoNode] | type[AudioNode], index: int, **kwargs: Any) -> None:
    if not is_preview():
        return

    from ..core import main_window
    main_window().set_node_info(node_type, index, **kwargs)
