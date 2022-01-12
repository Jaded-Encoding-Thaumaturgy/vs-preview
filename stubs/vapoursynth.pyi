from __future__ import annotations

from concurrent.futures import Future
from ctypes             import c_void_p
from enum               import Enum
from fractions          import Fraction
from inspect            import Signature
from typing             import (
    Any, BinaryIO, Callable, Dict, Optional, overload, Union,
)

# pylint: skip-file

# TODO : annotate return type of array methods
# FIXME: Format == PresetFormat doesn't pass mypy's strict equality check
# TODO : check signature of message handler callback


class ColorFamily:
    pass


RGB   : ColorFamily
YUV   : ColorFamily
GRAY  : ColorFamily
YCOCG : ColorFamily
COMPAT: ColorFamily


class SampleType:
    pass


INTEGER: SampleType
FLOAT  : SampleType


class Format:
    id: int
    name: str
    color_family: ColorFamily
    sample_type: SampleType
    bits_per_sample: int
    bytes_per_sample: int
    subsampling_w: int
    subsampling_h: int
    num_planes: int

    def replace(self, core: Optional[Core] = None, **kwargs: Any) -> None: ...


class PresetFormat(Enum):
    GRAY8 : int
    GRAY16: int
    GRAYH : int
    GRAYS : int

    YUV420P8: int
    YUV422P8: int
    YUV444P8: int
    YUV410P8: int
    YUV411P8: int
    YUV440P8: int

    YUV420P9: int
    YUV422P9: int
    YUV444P9: int

    YUV420P10: int
    YUV422P10: int
    YUV444P10: int

    YUV420P12: int
    YUV422P12: int
    YUV444P12: int

    YUV420P14: int
    YUV422P14: int
    YUV444P14: int

    YUV420P16: int
    YUV422P16: int
    YUV444P16: int

    YUV444PH: int
    YUV444PS: int

    RGB24: int
    RGB27: int
    RGB30: int
    RGB48: int

    RGBH: int
    RGBS: int

    COMPATBGR32: int
    COMPATYUY2: int


GRAY8 : PresetFormat
GRAY16: PresetFormat
GRAYH : PresetFormat
GRAYS : PresetFormat

YUV420P8: PresetFormat
YUV422P8: PresetFormat
YUV444P8: PresetFormat
YUV410P8: PresetFormat
YUV411P8: PresetFormat
YUV440P8: PresetFormat

YUV420P9: PresetFormat
YUV422P9: PresetFormat
YUV444P9: PresetFormat

YUV420P10: PresetFormat
YUV422P10: PresetFormat
YUV444P10: PresetFormat

YUV420P12: PresetFormat
YUV422P12: PresetFormat
YUV444P12: PresetFormat

YUV420P14: PresetFormat
YUV422P14: PresetFormat
YUV444P14: PresetFormat

YUV420P16: PresetFormat
YUV422P16: PresetFormat
YUV444P16: PresetFormat

YUV444PH: PresetFormat
YUV444PS: PresetFormat

RGB24: PresetFormat
RGB27: PresetFormat
RGB30: PresetFormat
RGB48: PresetFormat

RGBH: PresetFormat
RGBS: PresetFormat

COMPATBGR32: PresetFormat
COMPATYUY2 : PresetFormat


class VideoFrame:
    format: Format
    width: int
    height: int
    readonly: bool
    props: VideoProps

    def copy(self) -> VideoFrame: ...
    def get_read_ptr(self, plane: int) -> c_void_p: ...
    def get_read_array(self, plane: int) -> Any: ...
    def get_write_ptr(self, plane: int) -> c_void_p: ...
    def get_write_array(self, plane: int) -> Any: ...
    def get_stride(self, plane: int) -> int: ...


class VideoNode:
    format: Format
    width: int
    height: int
    num_frames: int
    fps: Fraction
    fps_num: int
    fps_den: int
    flags: int

    def get_frame(self, n: int) -> VideoFrame: ...
    def get_frame_async(self, n: int) -> Future: ...
    @overload
    def get_frame_async_raw(self, n: int, cb: Callable[[Union[VideoFrame, Error]], None]) -> None: ...
    @overload
    def get_frame_async_raw(self, n: int, cb: Future, wrapper: Optional[Callable] = None) -> None: ...
    def set_output(self, i: int, alpha: Optional[VideoNode] = None) -> None: ...
    def output(self, fileobj: BinaryIO, y4m: bool = False, prefetch: int = 0, progress_update: Optional[bool] = None) -> None: ...


class AlphaOutputTuple:
    clip: VideoNode
    alpha: VideoNode


class VideoProps(dict):
    pass


class Function:
    name: str
    plugin: Plugin
    signature: str
    def __call__(self, *args: Any, **kwargs: Any) -> VideoNode: ...


class Plugin:
    name: str
    def get_functions(self) -> Dict[str, str]: ...
    def list_functions(self) -> str: ...
    def __getattr__(self, name: str) -> Function: ...


class Core:
    num_threads: int
    add_cache: bool
    max_cache_size: int

    def set_max_cache_size(self, mb: int) -> None: ...
    def get_plugins(self) -> Dict[str, Union[str, Dict[str, str]]]: ...
    def list_functions(self) -> str: ...
    def register_format(self, color_family: ColorFamily, sample_type: SampleType, bits_per_sample: int, subsampling_w: int, subsampling_h: int) -> Format: ...
    def get_format(self, id: int) -> Format: ...
    def version(self) -> str: ...
    def version_number(self) -> int: ...
    def __getattr__(self, name: str) -> Plugin: ...


core: Core
def get_core(threads: int = 0, add_cache: bool = True) -> Core: ...
def set_message_handler(handler_func: Callable[[int, str], None]) -> None: ...
def get_outputs() -> Dict[int, Union[VideoNode, AlphaOutputTuple]]: ...
def get_output(index: int = 0) -> Union[VideoNode, AlphaOutputTuple]: ...
def clear_output(index: int = 0) -> None: ...
def clear_outputs() -> None: ...
def construct_signature(signature: str, injected: Optional[Any] = None) -> Signature: ...


class Environment:
    env_id: int
    single: bool
    alive: bool

    def is_single(self) -> bool: ...


def vpy_current_environment() -> Environment: ...


class Error(Exception):
    pass
