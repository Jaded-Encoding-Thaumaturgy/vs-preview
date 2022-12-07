
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from vstools import CustomRuntimeError

__all__ = [
    'set_timecodes'
]


def set_timecodes(
    index: int, timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[float], den: int = 1001
) -> None:
    from ..core import main_window

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
