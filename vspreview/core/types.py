from __future__ import annotations

import ctypes
import logging
from PyQt5 import Qt
import vapoursynth as vs
from yaml import YAMLObject
from datetime import timedelta
from dataclasses import dataclass
from typing import Any, Mapping, Optional, overload, TypeVar, Union, cast


core = vs.core


# TODO: consider making FrameInterval non-negative
# TODO: consider storing assosiated Output in Frame and others


@dataclass
class VideoOutputNode():
    clip: vs.VideoNode
    alpha: vs.VideoNode | None


class YAMLObjectWrapper(YAMLObject):
    value: Any

    def __int__(self) -> int:
        return int(self.value)

    def __float__(self) -> float:
        return float(self.value)

    def __index__(self) -> int:
        return int(self)

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: YAMLObjectWrapper) -> bool:  # type: ignore
        return self.value == other.value  # type: ignore

    def __gt__(self, other: YAMLObjectWrapper) -> bool:
        return self.value > other.value  # type: ignore

    def __ne__(self, other: YAMLObjectWrapper) -> bool:  # type: ignore
        return not self.__eq__(other)

    def __le__(self, other: YAMLObjectWrapper) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: YAMLObjectWrapper) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: YAMLObjectWrapper) -> bool:
        return not self.__ge__(other)

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }


class Frame(YAMLObjectWrapper):
    yaml_tag = '!Frame'

    __slots__ = ('value',)

    def __init__(self, init_value: Union[Frame, int, Time]) -> None:
        from vspreview.utils import main_window

        if isinstance(init_value, int):
            if init_value < 0:
                raise ValueError
            self.value = init_value
        elif isinstance(init_value, Frame):
            self.value = init_value.value
        elif isinstance(init_value, Time):
            self.value = main_window().current_output.to_frame(init_value).value
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

    def __sub__(self, other: Frame | FrameInterval) -> Union[Frame, FrameInterval]:
        if isinstance(other, Frame):
            return FrameInterval(self.value - other.value)
        if isinstance(other, FrameInterval):
            return Frame(self.value - other.value)
        raise TypeError

    @overload
    def __isub__(self, other: FrameInterval) -> Frame: ...
    @overload
    def __isub__(self, other: Frame) -> FrameInterval: ...

    def __isub__(self, other: Frame | FrameInterval) -> Union[Frame, FrameInterval]:  # type: ignore
        self.value -= other.value
        return self

    def __repr__(self) -> str:
        return f'Frame({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        from vspreview.utils import try_load

        try_load(
            state, 'value', int, self.__init__,  # type: ignore
            'Failed to load Frame instance'
        )


class FrameInterval(YAMLObjectWrapper):
    yaml_tag = '!FrameInterval'

    __slots__ = ('value',)

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

    def __repr__(self) -> str:
        return f'FrameInterval({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        from vspreview.utils import try_load

        try_load(
            state, 'value', int, self.__init__,  # type: ignore
            'Failed to load FrameInterval instance'
        )


FrameType = TypeVar('FrameType', Frame, FrameInterval)


class Time(YAMLObjectWrapper):
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

    def __sub__(self, other: Time | TimeInterval) -> Union[Time, TimeInterval]:
        if isinstance(other, Time):
            return TimeInterval(self.value - other.value)
        if isinstance(other, TimeInterval):
            return Time(self.value - other.value)
        raise TypeError

    @overload
    def __isub__(self, other: TimeInterval) -> Time: ...
    @overload
    def __isub__(self, other: Time) -> TimeInterval: ...

    def __isub__(self, other: Time | TimeInterval) -> Union[Time, TimeInterval]:  # type: ignore
        self.value -= other.value
        return self

    def __str__(self) -> str:
        from vspreview.utils import strfdelta

        return strfdelta(self, '%h:%M:%S.%Z')

    def __float__(self) -> float:
        return self.value.total_seconds()  # type: ignore

    def __repr__(self) -> str:
        return f'Time({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        from vspreview.utils import try_load

        try_load(
            state, 'value', timedelta, self.__init__,  # type: ignore
            'Failed to load Time instance'
        )


class TimeInterval(YAMLObjectWrapper):
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
            self.value = main_window().current_output.to_time_interval(init_value).value
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
        return self.value.total_seconds()  # type: ignore

    def __repr__(self) -> str:
        return f'TimeInterval({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        from vspreview.utils import try_load

        try_load(
            state, 'value', timedelta, self.__init__,  # type: ignore
            'Failed to load TimeInterval instance'
        )


TimeType = TypeVar('TimeType', Time, TimeInterval)


class Scene(YAMLObjectWrapper):
    yaml_tag = '!Scene'

    __slots__ = (
        'start', 'end', 'label'
    )

    def __init__(self, start: Optional[Frame] = None, end: Optional[Frame] = None, label: str = '') -> None:
        if start is not None and end is not None:
            self.start = start
            self.end = end
        elif start is not None:
            self.start = start
            self.end = start
        elif end is not None:
            self.start = end
            self.end = end
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

    def __gt__(self, other: Scene) -> bool:  # type: ignore
        if self.start != other.start:
            return self.start > other.start
        else:
            return self.end > other.end

    def duration(self) -> FrameInterval:
        return self.end - self.start

    def __contains__(self, frame: Frame) -> bool:
        return self.start <= frame <= self.end

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            if not isinstance(state['start'], Frame):
                raise TypeError('Start frame of Scene is not a Frame. It\'s most probably corrupted.')

            if not isinstance(state['end'], Frame):
                raise TypeError('End frame of Scene is not a Frame. It\'s most probably corrupted.')

            if not isinstance(state['label'], str):
                raise TypeError('Label of Scene is not a string. It\'s most probably corrupted.')
        except KeyError:
            raise KeyError(
                'Scene lacks one or more of its fields. It\'s most probably corrupted. Check those: {}.'
                .format(', '.join(self.__slots__))
            )

        self.__init__(state['start'], state['end'], state['label'])  # type: ignore


class Output(YAMLObject):
    yaml_tag = '!Output'

    class Resizer:
        Bilinear = core.resize.Bilinear
        Bicubic = core.resize.Bicubic
        Point = core.resize.Point
        Lanczos = core.resize.Lanczos
        Spline16 = core.resize.Spline16
        Spline36 = core.resize.Spline36

    class Matrix:
        values = {
            0: 'rgb',
            1: '709',
            2: 'unspec',
            # 3: 'reserved',
            4: 'fcc',
            5: '470bg',
            6: '170m',
            7: '240m',
            8: 'ycgco',
            9: '2020ncl',
            10: '2020cl',
            # 11: 'reserved',
            12: 'chromancl',
            13: 'chromacl',
            14: 'ictcp',
        }

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

    class Transfer:
        values = {
            # 0: 'reserved',
            1: '709',
            2: 'unspec',
            # 3: 'reserved',
            4: '470m',
            5: '470bg',
            6: '601',
            7: '240m',
            8: 'linear',
            9: 'log100',
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

    class Primaries:
        values = {
            # 0: 'reserved',
            1: '709',
            2: 'unspec',
            # 3: 'reserved',
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

    class Range:
        values = {
            0: 'full',
            1: 'limited'
        }

        LIMITED = values[1]
        FULL = values[0]

    class ChromaLoc:
        values = {
            0: 'left',
            1: 'center',
            2: 'top_left',
            3: 'top',
            4: 'bottom_left',
            5: 'bottom',
        }

        LEFT = values[0]
        CENTER = values[1]
        TOP_LEFT = values[2]
        TOP = values[3]
        BOTTOM_LEFT = values[4]
        BOTTOM = values[5]

    storable_attrs = (
        'name', 'last_showed_frame', 'play_fps',
        'frame_to_show', 'scening_lists'
    )
    __slots__ = storable_attrs + (
        'index', 'width', 'height', 'fps_num', 'fps_den',
        'total_frames', 'total_time', 'graphics_scene_item',
        'end_frame', 'end_time', 'fps', 'props', 'source', 'prepared',
        'main', 'checkerboard', '__weakref__', 'cur_frame'
        # hack to keep the reference to the current frame
    )

    source: VideoOutputNode
    prepared: VideoOutputNode
    format: vs.VideoFormat
    props: vs.FrameProps

    def clear(self) -> None:
        self.source = self.prepared = self.props = None  # type: ignore

    def __init__(self, vs_output: vs.VideoOutputTuple, index: int) -> None:
        from vspreview.models import SceningLists
        from vspreview.utils import main_window

        self.main = main_window()

        # runtime attributes
        self.source = VideoOutputNode(vs_output.clip, vs_output.alpha)
        self.prepared = VideoOutputNode(vs_output.clip, vs_output.alpha)

        if self.source.alpha is not None:
            self.prepared.alpha = self.prepare_vs_output(self.source.alpha, True)

        self.index = index
        if not hasattr(core, 'libp2p'):
            print(Warning(
                "LibP2P is missing, it is reccomended to prepare output clips correctly!\n"
                "You can get it here: https://github.com/DJATOM/LibP2P-Vapoursynth"
            ))

        self.prepared.clip = self.prepare_vs_output(self.source.clip)
        self.width = self.prepared.clip.width
        self.height = self.prepared.clip.height
        self.props = self.source.clip.get_frame(0).props
        self.fps_num = self.prepared.clip.fps.numerator
        self.fps_den = self.prepared.clip.fps.denominator
        self.fps = self.fps_num / self.fps_den
        self.total_frames = FrameInterval(self.prepared.clip.num_frames)
        self.total_time = self.to_time_interval(self.total_frames - FrameInterval(1))
        self.end_frame = Frame(int(self.total_frames) - 1)
        self.end_time = self.to_time(self.end_frame)
        self.name = 'Output ' + str(self.index)

        if self.source.alpha:
            self.checkerboard = self._generate_checkerboard()

        # set by load_script() when it prepares graphics scene item based on last showed frame
        self.graphics_scene_item: Qt.QGraphicsPixmapItem

        # storable attributes
        if 'Name' in self.props:
            self.name = 'Output %d: %s' % (index, cast(str, self.props['Name']))

        if (not hasattr(self, 'last_showed_frame') or self.last_showed_frame > self.end_frame):
            self.last_showed_frame: Frame = Frame(0)

        if not hasattr(self, 'scening_lists'):
            self.scening_lists: SceningLists = SceningLists()

        if not hasattr(self, 'play_fps'):
            self.play_fps = self.fps_num / self.fps_den

        if not hasattr(self, 'frame_to_show'):
            self.frame_to_show: Optional[Frame] = None

    def prepare_vs_output(self, clip: vs.VideoNode, is_alpha: bool = False) -> vs.VideoNode:
        assert clip.format

        resizer = self.main.VS_OUTPUT_RESIZER
        resizer_kwargs = {
            'format': vs.RGB24,
            'matrix_in_s': self.main.VS_OUTPUT_MATRIX,
            'transfer_in_s': self.main.VS_OUTPUT_TRANSFER,
            'primaries_in_s': self.main.VS_OUTPUT_PRIMARIES,
            'range_in_s': self.main.VS_OUTPUT_RANGE,
            'chromaloc_in_s': self.main.VS_OUTPUT_CHROMALOC,
        }

        is_subsampled = (clip.format.subsampling_w != 0 or clip.format.subsampling_h != 0)

        if not is_subsampled:
            resizer = self.Resizer.Point

        if clip.format.color_family == vs.RGB:
            del resizer_kwargs['matrix_in_s']

        if is_alpha:
            if clip.format.id == vs.GRAY8:
                return clip
            resizer_kwargs['format'] = vs.GRAY8

        clip = resizer(clip, **resizer_kwargs, **self.main.VS_OUTPUT_RESIZER_KWARGS)

        if not is_alpha:
            if hasattr(core, 'libp2p'):
                clip = core.libp2p.Pack(clip)  # type: ignore
            else:
                clip = core.akarin.Expr(
                    core.std.SplitPlanes(clip),
                    'x 0x100000 * y 0x400 * + z + 0xc0000000 +', vs.GRAY32, opt=1
                )

        return clip

    def render_frame(self, frame: Frame) -> Qt.QImage:
        if self.prepared.alpha:
            return self.render_raw_videoframe(
                self.prepared.clip.get_frame(int(frame)),
                self.prepared.alpha.get_frame(int(frame))
            )
        else:
            return self.render_raw_videoframe(
                self.prepared.clip.get_frame(int(frame))
            )

    def render_raw_videoframe(
        self, vs_frame: vs.VideoFrame, vs_frame_alpha: Optional[vs.VideoFrame] = None
    ) -> Qt.QImage:
        self.cur_frame = (vs_frame, vs_frame_alpha)  # keep a reference to the current frame

        stride_length = vs_frame.format.bytes_per_sample * vs_frame.width * vs_frame.height

        # powerful spell. do not touch
        frame_data_pointer = ctypes.cast(vs_frame.get_read_ptr(0), ctypes.POINTER(ctypes.c_char * stride_length))
        frame_image = Qt.QImage(
            frame_data_pointer.contents, vs_frame.width, vs_frame.height,
            vs_frame.get_stride(0), Qt.QImage.Format_RGB30
        )

        if vs_frame_alpha is None:
            return frame_image

        stride_length = vs_frame_alpha.format.bytes_per_sample * vs_frame_alpha.width * vs_frame_alpha.height

        alpha_data_pointer = ctypes.cast(vs_frame_alpha.get_read_ptr(0), ctypes.POINTER(ctypes.c_char * stride_length))

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
        tile_size = self.main.CHECKERBOARD_TILE_SIZE
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
        return frame_num / (self.fps or 1)

    def to_frame(self, time: Time) -> Frame:
        return Frame(self._calculate_frame(float(time)))

    def to_time(self, frame: Frame) -> Time:
        return Time(seconds=self._calculate_seconds(int(frame)))

    def to_frame_interval(self, time_interval: TimeInterval) -> FrameInterval:
        return FrameInterval(self._calculate_frame(float(time_interval)))

    def to_time_interval(self, frame_interval: FrameInterval) -> TimeInterval:
        return TimeInterval(seconds=self._calculate_seconds(int(frame_interval)))

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self.storable_attrs
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        from vspreview.models import SceningLists
        from vspreview.utils import try_load

        self.name = ''
        try_load(
            state, 'name', str, self.__setattr__,
            'Storage loading: Output: failed to parse name.'
        )

        self.last_showed_frame = Frame(0)
        try:
            try_load(
                state, 'last_showed_frame', Frame, self.__setattr__,
                'Storage loading: Output: failed to parse last showed frame.'
            )
        except IndexError:
            logging.warning('Storage loading: Output: last showed frame is out of range.')

        self.scening_lists = SceningLists()
        try_load(
            state, 'scening_lists', SceningLists, self.__setattr__,
            'Storage loading: Output: scening lists weren\'t parsed successfully.'
        )

        try:
            play_fps = state['play_fps']
            if not isinstance(play_fps, float):
                raise TypeError
            if play_fps > 0:
                self.play_fps = play_fps
        except (KeyError, TypeError):
            logging.warning('Storage loading: Output: play fps weren\'t parsed successfully.')
