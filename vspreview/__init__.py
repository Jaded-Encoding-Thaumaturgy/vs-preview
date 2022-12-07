from __future__ import annotations

from fractions import Fraction
import inspect
from pathlib import Path

from vstools import vs, CustomRuntimeError

from .init import main  # noqa: F401


def set_timecodes(
    index: int, timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[float], den: int = 1001
) -> None:
    from .core import main_window

    if isinstance(timecodes, (str, Path)):
        file = Path(timecodes).resolve()

        version, *_timecodes = file.read_text().splitlines()

        if 'v1' in version:
            def _norm(xd: str) -> float:
                return int(float(xd) / den) / den

            assume = _norm(_timecodes[0][7:])

            timecodes = {(None, None): assume}
            for line in _timecodes[1:]:
                start, end, _fps = line.split(',')
                timecodes[(int(start), int(end))] = _norm(_fps)
        elif 'v2' in version:
            timecodes = list(map(float, _timecodes))
            timecodes = [
                int(den / float(f'{round((x - y) * 100, 4) / 100000:.08f}'[:-1])) / den
                for x, y in zip(timecodes[1:], timecodes[:-1])
            ]
        else:
            raise CustomRuntimeError('Unsupported timecodes file!')

    main_window().update_timecodes_info(index, timecodes)  # type: ignore


def set_output(
    node: vs.RawNode, name: str | None = None,
    *, timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[float] | None = None, denominator: int = 1001
) -> None:
    from .core import main_window

    index = len(vs.get_outputs())

    ref_id = str(id(node))

    if isinstance(node, vs.VideoNode):
        title, node_type = 'Clip', vs.VideoNode
    elif isinstance(node, vs.AudioNode):
        title, node_type = 'Audio', vs.AudioNode
    else:
        title, node_type = 'Node', vs.RawNode

    if not name:
        name = f"{title} {index}"

        current_frame = inspect.currentframe()

        assert current_frame
        assert current_frame.f_back

        for vname, val in reversed(current_frame.f_back.f_locals.items()):
            if (str(id(val)) == ref_id):
                name = vname
                break

    node.set_output(index)
    main_window().set_node_name(node_type, index, name.title())

    if timecodes:
        set_timecodes(index, timecodes, (
            node.fps_den if (node.fps_den and node.fps_num) else 1001
        ) if denominator is None else denominator)
