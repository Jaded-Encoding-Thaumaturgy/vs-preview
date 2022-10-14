from __future__ import annotations

from typing import Dict, Protocol, Union, overload

from vstools import vs


class CustomEnum(type):
    items: Dict[str, int]
    values: Dict[int, str]

    @overload
    def __getattribute__(cls, item: str) -> int: ...
    @overload
    def __getattribute__(cls, item: int) -> str: ...

    def __getattribute__(cls, item: str | int) -> int | str:
        return _getattribute(cls, item)

    @overload
    def __getitem__(cls, item: int) -> str: ...
    @overload
    def __getitem__(cls, item: str) -> int: ...

    def __getitem__(cls, item: int | str) -> str | int:
        return _getattribute(cls, item)


def _getattribute(cls: CustomEnum, item: str | int) -> str | int:
    if isinstance(item, str):
        cvalue = object.__getattribute__(cls, item.upper())

        items: Dict[str, int] = object.__getattribute__(cls, 'items')

        if cvalue is not None and cvalue in items:
            return int(items[cvalue])

        item = item.lower()

        if item in items:
            return int(items[item])
    else:
        values: Dict[int, str] = object.__getattribute__(cls, 'values')
        if item in values:
            return str(values[item])

    raise KeyError


_dataT = Union[str, bytes, bytearray, None]


class _ResizerType(Protocol):
    def __call__(
        self, clip: vs.VideoNode, width: int | None, height: int | None, format: int | None, matrix: int | None,
        matrix_s: _dataT, transfer: int | None, transfer_s: _dataT, primaries: int | None, primaries_s: _dataT,
        range: int | None, range_s: _dataT, chromaloc: int | None, chromaloc_s: _dataT, matrix_in: int | None,
        matrix_in_s: _dataT, transfer_in: int | None, transfer_in_s: _dataT, primaries_in: int | None,
        primaries_in_s: _dataT, range_in: int | None, range_in_s: _dataT, chromaloc_in: int | None,
        chromaloc_in_s: _dataT, filter_param_a: float | None, filter_param_b: float | None, resample_filter_uv: _dataT,
        filter_param_a_uv: float | None, filter_param_b_uv: float | None, dither_type: _dataT, cpu_type: _dataT,
        prefer_props: int | None, src_left: float | None, src_top: float | None, src_width: float | None,
        src_height: float | None, nominal_luminance: float | None
    ) -> vs.VideoNode:
        ...


class Matrix(metaclass=CustomEnum):
    values = {
        0: 'rgb',
        1: '709',
        2: 'unspec',
        3: 'reserved',
        4: 'fcc',
        5: '470bg',
        6: '170m',
        7: '240m',
        8: 'ycgco',
        9: '2020ncl',
        10: '2020cl',
        11: 'reserved',
        12: 'chromancl',
        13: 'chromacl',
        14: 'ictcp',
    }
    items = {k: v for v, k in values.items()}

    RGB = values[0]
    BT709 = values[1]
    UNSPEC = values[2]
    BT470_BG = values[5]
    ST170_M = values[6]
    ST240_M = values[7]
    FCC = values[4]
    YCGCO = values[8]
    BT2020_NCL = values[9]
    BT2020_CL = values[10]
    CHROMA_CL = values[13]
    CHROMA_NCL = values[12]
    ICTCP = values[14]


class Transfer(metaclass=CustomEnum):
    values = {
        0: 'reserved',
        1: '709',
        2: 'unspec',
        3: 'reserved',
        4: '470m',
        5: '470bg',
        6: '601',
        7: '240m',
        8: 'linear',
        9: 'log100',
        10: 'log316',
        11: 'xvycc',  # IEC 61966-2-4
        12: 'reserved',
        13: 'srgb',  # IEC 61966-2-1
        14: '2020_10',
        15: '2020_12',
        16: 'st2084',
        17: 'st428',  # not supported by zimg 2.8
        18: 'std-b67',
    }
    items = {k: v for v, k in values.items()}

    BT709 = values[1]
    UNSPEC = values[2]
    BT601 = values[6]
    LINEAR = values[8]
    BT2020_10 = values[14]
    BT2020_12 = values[15]
    ST240_M = values[7]
    BT470_M = values[4]
    BT470_BG = values[5]
    LOG_100 = values[9]
    LOG_316 = values[10]
    ST2084 = values[16]
    ARIB_B67 = values[18]
    SRGB = values[13]
    XV_YCC = values[11]
    IEC_61966_2_4 = XV_YCC
    IEC_61966_2_1 = SRGB


class Primaries(metaclass=CustomEnum):
    values = {
        0: 'reserved',
        1: '709',
        2: 'unspec',
        3: 'reserved',
        4: '470m',
        5: '470bg',
        6: '170m',
        7: '240m',
        8: 'film',
        9: '2020',
        10: 'st428',  # or 'xyz'
        11: 'st431-2',
        12: 'st431-1',
        22: 'jedec-p22',
    }
    items = {k: v for v, k in values.items()}

    BT709 = values[1]
    UNSPEC = values[2]
    ST170_M = values[6]
    ST240_M = values[7]
    BT470_M = values[4]
    BT470_BG = values[5]
    FILM = values[8]
    BT2020 = values[9]
    ST428 = values[10]
    XYZ = ST428
    ST431_2 = values[11]
    ST431_1 = values[12]
    JEDEC_P22 = values[22]
    EBU3213_E = JEDEC_P22


class ColorRange(metaclass=CustomEnum):
    values = {
        0: 'full',
        1: 'limited'
    }
    items = {k: v for v, k in values.items()}

    LIMITED = values[1]
    FULL = values[0]


class ChromaLocation(metaclass=CustomEnum):
    values = {
        0: 'left',
        1: 'center',
        2: 'top_left',
        3: 'top',
        4: 'bottom_left',
        5: 'bottom',
    }
    items = {k: v for v, k in values.items()}

    LEFT = values[0]
    CENTER = values[1]
    TOP_LEFT = values[2]
    TOP = values[3]
    BOTTOM_LEFT = values[4]
    BOTTOM = values[5]
