from __future__ import annotations

import ctypes
from   datetime import timedelta
import logging
from   typing   import (
    Any, Mapping, Optional,
    overload, TypeVar, Union,
)

from   PyQt5       import Qt
from   yaml        import YAMLObject
import vapoursynth as     vs


# pylint: disable=function-redefined

# TODO: consider making FrameInterval non-negative
# TODO: consider storing assosiated Output in Frame and others


class Frame(YAMLObject):
    yaml_tag = '!Frame'

    __slots__ = (
        'value',
    )

    def __init__(self, init_value: Union[Frame, int, Time]) -> None:
        from vspreview.utils import main_window

        if isinstance(init_value, int):
            if init_value < 0:
                raise ValueError
            self.value = init_value
        elif isinstance(init_value, Frame):
            self.value = init_value.value
        elif isinstance(init_value, Time):
            self.value = main_window().current_output.to_frame(
                init_value).value
        else:
            raise TypeError

    def __add__(self, other: FrameInterval) -> Frame:
        return Frame(self.value + other.value)

    def __iadd__(self, other: FrameInterval) -> Frame:
        self.value += other.value
        return self

    @overload
    def __sub__(self, other: FrameInterval) -> Frame: ...
    @overload
    def __sub__(self, other: Frame) -> FrameInterval: ...

    def __sub__(self, other):  # type: ignore
        if isinstance(other, Frame):
            return FrameInterval(self.value - other.value)
        if isinstance(other, FrameInterval):
            return Frame(self.value - other.value)
        raise TypeError

    def __isub__(self, other: FrameInterval) -> Frame:  # type: ignore
        self.value -= other.value
        return self

    def __int__(self) -> int:
        return self.value

    def __float__(self) -> float:
        return float(self.value)

    def __index__(self) -> int:
        return int(self)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f'Frame({self.value})'

    def __eq__(self, other: Frame) -> bool:  # type: ignore
        return self.value == other.value

    def __gt__(self, other: Frame) -> bool:
        return self.value > other.value

    def __ne__(self, other: Frame) -> bool:  # type: ignore
        return not self.__eq__(other)

    def __le__(self, other: Frame) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: Frame) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: Frame) -> bool:
        return not self.__ge__(other)


    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            value = state['value']
            if not isinstance(value, int):
                raise TypeError(
                    'Value of Frame isn\'t an integer. It\'s most probably corrupted.')
        except KeyError:
            raise KeyError(
                'Frame lacks one or more of its fields. It\'s most probably corrupted. Check those: {}.'
                .format(', '.join(self.__slots__)))

        self.__init__(value)  # type: ignore


class FrameInterval(YAMLObject):
    yaml_tag = '!FrameInterval'

    __slots__ = (
        'value',
    )

    def __init__(self, init_value: Union[FrameInterval, int, TimeInterval]) -> None:
        from vspreview.utils import main_window

        if isinstance(init_value, int):
            self.value = init_value
        elif isinstance(init_value, FrameInterval):
            self.value = init_value.value
        elif isinstance(init_value, TimeInterval):
            self.value = main_window().current_output.to_frame_interval(
                init_value).value
        else:
            raise TypeError

    def __add__(self, other: FrameInterval) -> FrameInterval:
        return FrameInterval(self.value + other.value)

    def __iadd__(self, other: FrameInterval) -> FrameInterval:
        self.value += other.value
        return self

    def __sub__(self, other: FrameInterval) -> FrameInterval:
        return FrameInterval(self.value - other.value)

    def __isub__(self, other: FrameInterval) -> FrameInterval:
        self.value -= other.value
        return self

    def __mul__(self, other: int) -> FrameInterval:
        return FrameInterval(self.value * other)

    def __imul__(self, other: int) -> FrameInterval:
        self.value *= other
        return self

    def __rmul__(self, other: int) -> FrameInterval:
        return FrameInterval(other * self.value)

    def __floordiv__(self, other: float) -> FrameInterval:
        return FrameInterval(int(self.value // other))

    def __ifloordiv__(self, other: float) -> FrameInterval:
        self.value = int(self.value // other)
        return self

    def __int__(self) -> int:
        return self.value

    def __float__(self) -> float:
        return float(self.value)

    def __index__(self) -> int:
        return int(self)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f'FrameInterval({self.value})'

    def __eq__(self, other: FrameInterval) -> bool:  # type: ignore
        return self.value == other.value

    def __gt__(self, other: FrameInterval) -> bool:
        return self.value > other.value

    def __ne__(self, other: FrameInterval) -> bool:  # type: ignore
        return not self.__eq__(other)

    def __le__(self, other: FrameInterval) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: FrameInterval) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: FrameInterval) -> bool:
        return not self.__ge__(other)


    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            value = state['value']
            if not isinstance(value, int):
                raise TypeError(
                    'Value of FrameInterval isn\'t an integer. It\'s most probably corrupted.')
        except KeyError:
            raise KeyError(
                'FrameInterval lacks one or more of its fields. It\'s most probably corrupted. Check those: {}.'
                .format(', '.join(self.__slots__)))

        self.__init__(value)  # type: ignore


FrameType = TypeVar('FrameType', Frame, FrameInterval)


class Time(YAMLObject):
    yaml_tag = '!Time'

    __slots__ = (
        'value',
    )

    def __init__(self, init_value: Optional[Union[Time, timedelta, Frame]] = None, **kwargs: Any):
        from vspreview.utils import main_window

        if isinstance(init_value, timedelta):
            self.value = init_value
        elif isinstance(init_value, Time):
            self.value = init_value.value
        elif isinstance(init_value, Frame):
            self.value = main_window().current_output.to_time(init_value).value
        elif any(kwargs):
            self.value = timedelta(**kwargs)
        elif init_value is None:
            self.value = timedelta()
        else:
            raise TypeError

    def __add__(self, other: TimeInterval) -> Time:
        return Time(self.value + other.value)

    def __iadd__(self, other: TimeInterval) -> Time:
        self.value += other.value
        return self

    @overload
    def __sub__(self, other: TimeInterval) -> Time: ...
    @overload
    def __sub__(self, other: Time) -> TimeInterval: ...

    def __sub__(self, other):  # type: ignore
        if isinstance(other, Time):
            return TimeInterval(self.value - other.value)
        if isinstance(other, TimeInterval):
            return Time(self.value - other.value)
        raise TypeError

    def __isub__(self, other: TimeInterval) -> Time:  # type: ignore
        self.value -= other.value
        return self

    def __str__(self) -> str:
        from vspreview.utils import strfdelta

        return strfdelta(self, '%h:%M:%S.%Z')

    def __float__(self) -> float:
        return self.value.total_seconds()

    def __repr__(self) -> str:
        return f'Time({self.value})'

    def __eq__(self, other: Time) -> bool:  # type: ignore
        return self.value == other.value

    def __gt__(self, other: Time) -> bool:
        return self.value > other.value

    def __ne__(self, other: Time) -> bool:  # type: ignore
        return not self.__eq__(other)

    def __le__(self, other: Time) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: Time) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: Time) -> bool:
        return not self.__ge__(other)


    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            value = state['value']
            if not isinstance(value, timedelta):
                raise TypeError(
                    'Value of Time isn\'t an timedelta. It\'s most probably corrupted.')
        except KeyError:
            raise KeyError(
                'Time lacks one or more of its fields. It\'s most probably corrupted. Check those: {}.'
                .format(', '.join(self.__slots__)))

        self.__init__(value)  # type: ignore


class TimeInterval(YAMLObject):
    yaml_tag = '!TimeInterval'

    __slots__ = (
        'value',
    )

    def __init__(self, init_value: Optional[Union[TimeInterval, timedelta, FrameInterval]] = None, **kwargs: Any):
        from vspreview.utils import main_window

        if isinstance(init_value, timedelta):
            self.value = init_value
        elif isinstance(init_value, TimeInterval):
            self.value = init_value.value
        elif isinstance(init_value, FrameInterval):
            self.value = main_window().current_output.to_time_interval(
                init_value).value
        elif any(kwargs):
            self.value = timedelta(**kwargs)
        elif init_value is None:
            self.value = timedelta()
        else:
            raise TypeError

    def __add__(self, other: TimeInterval) -> TimeInterval:
        return TimeInterval(self.value + other.value)

    def __iadd__(self, other: TimeInterval) -> TimeInterval:
        self.value += other.value
        return self

    def __sub__(self, other: TimeInterval) -> TimeInterval:
        return TimeInterval(self.value - other.value)

    def __isub__(self, other: TimeInterval) -> TimeInterval:
        self.value -= other.value
        return self

    def __mul__(self, other: int) -> TimeInterval:
        return TimeInterval(self.value * other)

    def __imul__(self, other: int) -> TimeInterval:
        self.value *= other
        return self

    def __rmul__(self, other: int) -> TimeInterval:
        return TimeInterval(other * self.value)

    def __truediv__(self, other: float) -> TimeInterval:
        return TimeInterval(self.value / other)

    def __itruediv__(self, other: float) -> TimeInterval:
        self.value /= other
        return self

    def __str__(self) -> str:
        from vspreview.utils import strfdelta

        return strfdelta(self, '%h:%M:%S.%Z')

    def __float__(self) -> float:
        return self.value.total_seconds()

    def __repr__(self) -> str:
        return f'TimeInterval({self.value})'

    def __eq__(self, other: TimeInterval) -> bool:  # type: ignore
        return self.value == other.value

    def __gt__(self, other: TimeInterval) -> bool:
        return self.value > other.value

    def __ne__(self, other: TimeInterval) -> bool:  # type: ignore
        return not self.__eq__(other)

    def __le__(self, other: TimeInterval) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: TimeInterval) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: TimeInterval) -> bool:
        return not self.__ge__(other)


    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            value = state['value']
            if not isinstance(value, timedelta):
                raise TypeError(
                    'Value of TimeInterval isn\'t an timedelta. It\'s most probably corrupted.')
        except KeyError:
            raise KeyError(
                'TimeInterval lacks one or more of its fields. It\'s most probably corrupted. Check those: {}.'
                .format(', '.join(self.__slots__)))

        self.__init__(value)  # type: ignore


TimeType = TypeVar('TimeType', Time, TimeInterval)


class Scene(YAMLObject):
    yaml_tag = '!Scene'

    __slots__ = (
        'start', 'end', 'label',
    )

    def __init__(self, start: Optional[Frame] = None, end: Optional[Frame] = None, label: str = '') -> None:
        if start is not None and end is not None:
            self.start = start
            self.end   = end
        elif start is not None:
            self.start = start
            self.end   = start
        elif end is not None:
            self.start = end
            self.end   = end
        else:
            raise ValueError

        if self.start > self.end:
            self.start, self.end = self.end, self.start

        self.label = label

    def __str__(self) -> str:
        result = ''

        if self.start == self.end:
            result = f'{self.start}'
        else:
            result = f'{self.start} - {self.end}'

        if self.label != '':
            result += f': {self.label}'

        return result

    def __repr__(self) -> str:
        return 'Scene({}, {}, \'{}\')'.format(self.start, self.end, self.label)

    def __eq__(self, other: Scene) -> bool:  # type: ignore
        return self.start == other.start and self.end == other.end

    def __gt__(self, other: Scene) -> bool:
        if self.start != other.start:
            return self.start > other.start
        else:
            return self.end   > other.end

    def __ne__(self, other: Scene) -> bool:  # type: ignore
        return not self.__eq__(other)

    def __le__(self, other: Scene) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: Scene) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: Scene) -> bool:
        return not self.__ge__(other)

    def duration(self) -> FrameInterval:
        return self.end - self.start

    def __contains__(self, frame: Frame) -> bool:
        return self.start <= frame <= self.end

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            start = state['start']
            if not isinstance(start, Frame):
                raise TypeError(
                    'Start frame of Scene is not a Frame. It\'s most probably corrupted.')

            end = state['end']
            if not isinstance(end, Frame):
                raise TypeError(
                    'End frame of Scene is not a Frame. It\'s most probably corrupted.')

            label = state['label']
            if not isinstance(label, str):
                raise TypeError(
                    'Label of Scene is not a string. It\'s most probably corrupted.')
        except KeyError:
            raise KeyError(
                'Scene lacks one or more of its fields. It\'s most probably corrupted. Check those: {}.'
                .format(', '.join(self.__slots__)))

        self.__init__(start, end, label)  # type: ignore


class Output(YAMLObject):
    yaml_tag = '!Output'

    class _Resizer:
        Bilinear = lambda self, *args,**kwargs: vs.core.resize.Bilinear(*args, **kwargs)
        Bicubic  = lambda self, *args,**kwargs: vs.core.resize.Bicubic(*args, **kwargs)
        Point    = lambda self, *args,**kwargs: vs.core.resize.Point(*args, **kwargs)
        Lanczos  = lambda self, *args,**kwargs: vs.core.resize.Lanczos(*args, **kwargs)
        Spline16 = lambda self, *args,**kwargs: vs.core.resize.Spline16(*args, **kwargs)
        Spline36 = lambda self, *args,**kwargs: vs.core.resize.Spline36(*args, **kwargs)
    Resizer = _Resizer()

    class Matrix:
        values = {
            0:  'rgb',
            1:  '709',
            2:  'unspec',
            # 3:  'reserved',
            4:  'fcc',
            5:  '470bg',
            6:  '170m',
            7:  '240m',
            8:  'ycgco',
            9:  '2020ncl',
            10: '2020cl',
            # 11: 'reserved',
            12: 'chromancl',
            13: 'chromacl',
            14: 'ictcp',
        }

        RGB        = values[ 0]
        BT709      = values[ 1]
        UNSPEC     = values[ 2]
        BT470_BG   = values[ 5]
        ST170_M    = values[ 6]
        ST240_M    = values[ 7]
        FCC        = values[ 4]
        YCGCO      = values[ 8]
        BT2020_NCL = values[ 9]
        BT2020_CL  = values[10]
        CHROMA_CL  = values[13]
        CHROMA_NCL = values[12]
        ICTCP      = values[14]

    class Transfer:
        values = {
            # 0:  'reserved',
            1:  '709',
            2:  'unspec',
            # 3:  'reserved',
            4:  '470m',
            5:  '470bg',
            6:  '601',
            7:  '240m',
            8:  'linear',
            9:  'log100',
            10: 'log316',
            11: 'xvycc',  # IEC 61966-2-4
            # 12: 'reserved',
            13: 'srgb',  # IEC 61966-2-1
            14: '2020_10',
            15: '2020_12',
            16: 'st2084',
            # 17: 'st428',  # not supported by zimg 2.8
            18: 'std-b67',
        }

        BT709         = values[ 1]
        UNSPEC        = values[ 2]
        BT601         = values[ 6]
        LINEAR        = values[ 8]
        BT2020_10     = values[14]
        BT2020_12     = values[15]
        ST240_M       = values[ 7]
        BT470_M       = values[ 4]
        BT470_BG      = values[ 5]
        LOG_100       = values[ 9]
        LOG_316       = values[10]
        ST2084        = values[16]
        ARIB_B67      = values[18]
        SRGB          = values[13]
        XV_YCC        = values[11]
        IEC_61966_2_4 = XV_YCC
        IEC_61966_2_1 = SRGB

    class Primaries:
        values = {
            # 0:  'reserved',
            1:  '709',
            2:  'unspec',
            # 3:  'reserved',
            4:  '470m',
            5:  '470bg',
            6:  '170m',
            7:  '240m',
            8:  'film',
            9:  '2020',
            10: 'st428',  # or 'xyz'
            11: 'st431-2',
            12: 'st431-1',
            22: 'jedec-p22',
        }

        BT709     = values[ 1]
        UNSPEC    = values[ 2]
        ST170_M   = values[ 6]
        ST240_M   = values[ 7]
        BT470_M   = values[ 4]
        BT470_BG  = values[ 5]
        FILM      = values[ 8]
        BT2020    = values[ 9]
        ST428     = values[10]
        XYZ       = ST428
        ST431_2   = values[11]
        ST431_1   = values[12]
        JEDEC_P22 = values[22]
        EBU3213_E = JEDEC_P22

    class Range:
        values = {
            0: 'full',
            1: 'limited'
        }

        LIMITED = values[1]
        FULL    = values[0]

    class ChromaLoc:
        values = {
            0: 'left',
            1: 'center',
            2: 'top_left',
            3: 'top',
            4: 'bottom_left',
            5: 'bottom',
        }

        LEFT        = values[0]
        CENTER      = values[1]
        TOP_LEFT    = values[2]
        TOP         = values[3]
        BOTTOM_LEFT = values[4]
        BOTTOM      = values[5]

    storable_attrs = (
        'name', 'last_showed_frame', 'play_fps',
        'frame_to_show',
    )
    __slots__ = storable_attrs + (
        'vs_output', 'index', 'width', 'height', 'fps_num', 'fps_den',
        'format', 'total_frames', 'total_time', 'graphics_scene_item',
        'end_frame', 'end_time', 'fps', 'has_alpha', 'vs_alpha',
        'format_alpha', 'props', 'source_vs_output', 'source_vs_alpha',
        'main', 'checkerboard', "__weakref__",
        "cur_frame" # hack to keep the reference to the current frame
    )

    def __init__(self, vs_output: Union[vs.VideoNode, vs.AlphaOutputTuple], index: int) -> None:
        from vspreview.models  import SceningLists
        from vspreview.utils   import main_window
        from vspreview.widgets import GraphicsImageItem

        self.main = main_window()

        # runtime attributes

        if hasattr(vs, 'AlphaOutputTuple') and isinstance(vs_output, vs.AlphaOutputTuple) or \
           hasattr(vs, 'VideoOutputTuple') and isinstance(vs_output, vs.VideoOutputTuple):
            self.source_vs_output = vs_output.clip
            self.source_vs_alpha  = vs_output.alpha

            self.has_alpha = False
            if self.source_vs_alpha:
                self.has_alpha = True
                self.vs_alpha = self.prepare_vs_output(self.source_vs_alpha,
                                                       alpha=True)
                self.format_alpha = self.source_vs_alpha.format
        else:
            self.has_alpha = False
            self.source_vs_output = vs_output

        self.index        = index

        self.vs_output    = self.prepare_vs_output(self.source_vs_output)
        self.width        = self.vs_output.width
        self.height       = self.vs_output.height
        self.format       = self.source_vs_output.format
        self.props        = self.source_vs_output.get_frame(0).props
        self.fps_num      = self.vs_output.fps.numerator
        self.fps_den      = self.vs_output.fps.denominator
        self.fps          = self.fps_num / self.fps_den
        self.total_frames = FrameInterval(self.vs_output.num_frames)
        self.total_time   = self.to_time_interval(self.total_frames
                                                  - FrameInterval(1))
        self.end_frame    = Frame(int(self.total_frames) - 1)
        self.end_time     = self.to_time(self.end_frame)

        if self.has_alpha:
            self.checkerboard = self._generate_checkerboard()

        # set by load_script() when it prepares graphics scene item
        # based on last showed frame

        self.graphics_scene_item: GraphicsImageItem

        # storable attributes
        if 'Name' in self.props:
            self.name = 'Output %d: %s' % (index, self.props['Name'].decode('utf-8'))

        if not hasattr(self, 'name'):
            self.name = 'Output ' + str(self.index)
        if (not hasattr(self, 'last_showed_frame')
                or self.last_showed_frame > self.end_frame):
            self.last_showed_frame: Frame = Frame(0)
        if not hasattr(self, 'play_fps'):
            self.play_fps = self.fps_num / self.fps_den
        if not hasattr(self, 'frame_to_show'):
            self.frame_to_show: Optional[Frame] = None

    def prepare_vs_output(self, vs_output: vs.VideoNode, alpha: bool = False) -> vs.VideoNode:
        resizer = self.main.VS_OUTPUT_RESIZER
        akarin = vs.__api_version__.api_major >= 4
        resizer_kwargs = {
            'format'        : vs.RGB30 if akarin else vs.COMPATBGR32,
            'matrix_in_s'   : self.main.VS_OUTPUT_MATRIX,
            'transfer_in_s' : self.main.VS_OUTPUT_TRANSFER,
            'primaries_in_s': self.main.VS_OUTPUT_PRIMARIES,
            'range_in_s'    : self.main.VS_OUTPUT_RANGE,
            'chromaloc_in_s': self.main.VS_OUTPUT_CHROMALOC,
            'prefer_props'  : self.main.VS_OUTPUT_PREFER_PROPS,
        }

        if not alpha and not akarin:
            vs_output = vs.core.std.FlipVertical(vs_output)

        is_subsampled = (vs_output.format.subsampling_w != 0
                         or vs_output.format.subsampling_h != 0)
        if not is_subsampled:
            resizer = self.Resizer.Point

        if vs_output.format.color_family == vs.RGB:
            del resizer_kwargs['matrix_in_s']

        if alpha:
            if vs_output.format == vs.GRAY8:  # type: ignore
                return vs_output
            resizer_kwargs['format'] = vs.GRAY8

        vs_output = resizer(vs_output, **resizer_kwargs,
                            **self.main.VS_OUTPUT_RESIZER_KWARGS)
        if alpha: return vs_output
        elif akarin:
            try:
                regfmt = vs.core.query_video_format
            except AttributeError:
                regfmt = vs.core.register_format
            #return vs.core.libp2p.Pack(vs_output)
            fmt = regfmt(vs.GRAY, vs.INTEGER, 32, 0, 0)
            # convert vs.RGB30 to non-planar Qt RGB30.
            return vs.core.akarin.Expr([ vs.core.std.ShufflePlanes(vs_output, i, vs.GRAY) for i in range(3) ], 'x 0x100000 * y 0x400 * + z + 0xc0000000 +', fmt, opt=1)

        return vs_output

    def render_frame(self, frame: Frame) -> Qt.QImage:
        if not self.has_alpha:
            return self.render_raw_videoframe(
                self.vs_output.get_frame(int(frame)))
        else:
            return self.render_raw_videoframe(
                self.vs_output.get_frame(int(frame)),
                self.vs_alpha.get_frame(int(frame)))

    def render_raw_videoframe(self, vs_frame: vs.VideoFrame, vs_frame_alpha: Optional[vs.VideoFrame] = None) -> Qt.QImage:
        self.cur_frame = (vs_frame, vs_frame_alpha) # keep a reference to the current frame
        # powerful spell. do not touch
        frame_data_pointer = ctypes.cast(
            vs_frame.get_read_ptr(0),
            ctypes.POINTER(ctypes.c_char * (
                vs_frame.format.bytes_per_sample
                * vs_frame.width * vs_frame.height))
        )
        frame_image = Qt.QImage(
            frame_data_pointer.contents, vs_frame.width, vs_frame.height,
            vs_frame.get_stride(0), Qt.QImage.Format_RGB30 if vs.__api_version__.api_major >= 4 else Qt.QImage.Format_RGB32)

        if vs_frame_alpha is None:
            return frame_image

        alpha_data_pointer = ctypes.cast(
            vs_frame_alpha.get_read_ptr(0),
            ctypes.POINTER(ctypes.c_char * (
                vs_frame_alpha.format.bytes_per_sample
                * vs_frame_alpha.width * vs_frame_alpha.height))
        )
        alpha_image = Qt.QImage(
            alpha_data_pointer.contents, vs_frame.width, vs_frame.height,
            vs_frame_alpha.get_stride(0), Qt.QImage.Format_Alpha8)

        result_image = Qt.QImage(vs_frame.width, vs_frame.height,
                                 Qt.QImage.Format_ARGB32_Premultiplied)
        painter = Qt.QPainter(result_image)
        painter.setCompositionMode(Qt.QPainter.CompositionMode_Source)
        painter.drawImage(0, 0, frame_image)
        painter.setCompositionMode(
            Qt.QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, alpha_image)
        if self.main.CHECKERBOARD_ENABLED:
            painter.setCompositionMode(Qt.QPainter.CompositionMode_DestinationOver)
            painter.drawImage(0, 0, self.checkerboard)
        painter.end()

        return result_image

    def _generate_checkerboard(self) -> Qt.QImage:
        tile_size    = self.main.CHECKERBOARD_TILE_SIZE
        tile_color_1 = self.main.CHECKERBOARD_TILE_COLOR_1
        tile_color_2 = self.main.CHECKERBOARD_TILE_COLOR_2

        macrotile_pixmap = Qt.QPixmap(tile_size * 2, tile_size * 2)
        painter = Qt.QPainter(macrotile_pixmap)
        painter.fillRect(macrotile_pixmap.rect(), tile_color_1)
        painter.fillRect(tile_size, 0, tile_size, tile_size, tile_color_2)
        painter.fillRect(0, tile_size, tile_size, tile_size, tile_color_2)
        painter.end()

        result_image = Qt.QImage(self.width, self.height,
                                 Qt.QImage.Format_ARGB32_Premultiplied)
        painter = Qt.QPainter(result_image)
        painter.drawTiledPixmap(result_image.rect(), macrotile_pixmap)
        painter.end()

        return result_image

    def _calculate_frame(self, seconds: float) -> int:
        return round(seconds * self.fps)

    def _calculate_seconds(self, frame_num: int) -> float:
        return frame_num / self.fps

    def to_frame(self, time: Time) -> Frame:
        return Frame(self._calculate_frame(float(time)))

    def to_time(self, frame: Frame) -> Time:
        return Time(seconds=self._calculate_seconds(int(frame)))

    def to_frame_interval(self, time_interval: TimeInterval) -> FrameInterval:
        return FrameInterval(self._calculate_frame(float(time_interval)))

    def to_time_interval(self, frame_interval: FrameInterval) -> TimeInterval:
        return TimeInterval(
            seconds=self._calculate_seconds(int(frame_interval)))

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self.storable_attrs
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        from vspreview.utils import main_window

        try:
            name = state['name']
            if not isinstance(name, str):
                raise TypeError
            self.name = name
        except (KeyError, TypeError):
            logging.warning(
                f'Storage loading: output {self.index}: failed to parse name.')

        try:
            self.last_showed_frame = state['last_showed_frame']
        except (KeyError, TypeError):
            logging.warning(
                f'Storage loading: Output: failed to parse last showed frame.')
        except IndexError:
            logging.warning(
                f'Storage loading: Output: last showed frame is out of range.')

        try:
            for scening_list in state['scening_lists']:
                main_window().toolbars.scening.lists.add_list(scening_list)
        except (KeyError, TypeError):
            pass

        try:
            play_fps = state['play_fps']
            if not isinstance(play_fps, float):
                raise TypeError
            if play_fps >= 1.0:
                self.play_fps = play_fps
        except (KeyError, TypeError):
            logging.warning(
                f'Storage loading: Output: play fps weren\'t parsed successfully.')

        try:
            self.frame_to_show = state['frame_to_show']
        except (KeyError, TypeError):
            logging.warning(
                f'Storage loading: Output: failed to parse frame to show.')
