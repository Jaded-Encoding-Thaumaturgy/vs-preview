from __future__ import annotations

import logging
import os
from ctypes import Array
from fractions import Fraction
from itertools import count as iter_count
from typing import TYPE_CHECKING, Any, cast

import vapoursynth as vs
from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColorSpace, QImage, QPainter, QPixmap
from jetpytools import cachedproperty, classproperty, fallback

from ..abstracts import AbstractYAMLObject, main_window, try_load
from ..bases import yaml_Loader
from .misc import ArInfo, CroppingInfo, VideoOutputNode
from .units import Frame, Time

if TYPE_CHECKING:
    from vstools import VideoFormatT

    from ..custom.graphicsview import GraphicsImageItem

__all__ = [
    'PackingType',
    'VideoOutput'
]

_default_props = {}

yaml_Loader.add_constructor('tag:yaml.org,2002:python/object/apply:fractions.Fraction', lambda self, node: Fraction(*self.construct_sequence(node)))


class PackingTypeInfo:
    _getid = iter_count()

    def __init__(
        self, name: str, vs_format: VideoFormatT, qt_format: QImage.Format, shuffle: bool, can_playback: bool = True
    ):
        from ctypes import c_char

        self.id = next(self._getid)
        self.name = name
        self.vs_format = vs.core.get_video_format(vs_format)
        self.vs_alpha_format = vs.core.get_video_format(vs.GRAY8)
        self.qt_format = qt_format
        self.shuffle = shuffle
        self.can_playback = can_playback

        nbps, abps = self.vs_format.bits_per_sample, self.vs_alpha_format.bytes_per_sample
        self.conv_info: dict[bool, tuple[type[Array[c_char]], QImage.Format]] = {
            False: (c_char * nbps, self.qt_format),
            True: (c_char * abps, QImage.Format.Format_Alpha8)
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackingTypeInfo):
            raise NotImplementedError
        return self.id == other.id

    def __hash__(self) -> int:
        return int(self.id)


class PackingType(cachedproperty.baseclass, metaclass=classproperty.metaclass):
    none_8bit = PackingTypeInfo('none-8bit', vs.RGB24, QImage.Format.Format_BGR30, False, False)
    none_10bit = PackingTypeInfo('none-10bit', vs.RGB30, QImage.Format.Format_BGR30, False, False)
    numpy_8bit = PackingTypeInfo('numpy-8bit', vs.RGB24, QImage.Format.Format_BGR30, True)
    numpy_10bit = PackingTypeInfo('numpy-10bit', vs.RGB30, QImage.Format.Format_BGR30, True)
    libp2p_8bit = PackingTypeInfo('libp2p-8bit', vs.RGB24, QImage.Format.Format_RGB32, False)
    libp2p_10bit = PackingTypeInfo('libp2p-10bit', vs.RGB30, QImage.Format.Format_BGR30, True)
    akarin_8bit = PackingTypeInfo('akarin-8bit', vs.RGB24, QImage.Format.Format_BGR30, False)
    akarin_10bit = PackingTypeInfo('akarin-10bit', vs.RGB30, QImage.Format.Format_BGR30, False)

    @cachedproperty
    @classproperty
    def CURRENT(cls) -> PackingTypeInfo:
        _default_10bits = os.name != 'nt' and QPixmap.defaultDepth() == 30  # type: ignore

        # From fastest to slowest
        if hasattr(vs.core, 'akarin'):
            return PackingType.akarin_10bit if _default_10bits else PackingType.akarin_8bit

        if hasattr(vs.core, 'libp2p'):
            return PackingType.libp2p_10bit if _default_10bits else PackingType.libp2p_8bit
        else:
            try:
                import numpy  # noqa: F401

                return PackingType.numpy_10bit if _default_10bits else PackingType.numpy_8bit
            except ModuleNotFoundError:
                ...

        return PackingType.none_10bit if _default_10bits else PackingType.none_8bit


class VideoOutput(AbstractYAMLObject):
    storable_attrs = (
        'name', 'last_showed_frame', 'play_fps', 'crop_values', 'ar_values'
    )

    __slots__ = (
        *storable_attrs, 'index', 'width', 'height', 'fps_num', 'fps_den',
        'total_frames', 'total_time',
        'end_frame', 'fps', 'source', 'prepared',
        'main', 'checkerboard', 'props', '_stateset'
    )

    source: VideoOutputNode
    prepared: VideoOutputNode
    name: str
    last_showed_frame: Frame
    crop_values: CroppingInfo
    ar_values: ArInfo
    _stateset: bool
    props: vs.FrameProps | None

    def clear(self) -> None:
        if self.source:
            del self.source.clip, self.source.alpha
        if self.prepared:
            del self.prepared.clip, self.prepared.alpha
        if self.props:
            self.props.clear()
        del self.source, self.prepared, self.props
        self.source = self.prepared = self.props = None  # type: ignore

    def __init__(
        self, vs_output: vs.VideoOutputTuple, index: int, new_storage: bool = False
    ) -> None:
        self.setValue(vs_output, index, new_storage)

    def setValue(
        self, vs_output: vs.VideoOutputTuple, index: int, new_storage: bool = False
    ) -> None:
        self._stateset = not new_storage

        self.main = main_window()

        assert self.main.env

        with self.main.env:
            vs_outputs = list(x for x in vs.get_outputs().values() if isinstance(x, vs.VideoOutputTuple))

        self.vs_index = index
        self.index = vs_outputs.index(vs_output) if vs_output in vs_outputs else index

        self.info = self.main.user_output_info[vs.VideoNode].get(self.vs_index, {})

        self.cached = not not self.info.get('cache', False)

        if vs_output in vs_outputs and not hasattr(self, 'props'):
            try:
                self.props = cast(vs.FrameProps, vs_output.clip.get_frame(self.main.start_frame).props.copy())
            except Exception as e:
                raise e from None

        self.source = VideoOutputNode(vs_output.clip, vs_output.alpha, self.cached)
        self.prepared = VideoOutputNode(vs_output.clip, vs_output.alpha, self.cached)

        if self.source.alpha is not None:
            self.prepared.alpha = self.prepare_vs_output(self.source.alpha, False)

        self.prepared.clip = self.prepare_vs_output(self.source.clip, True)

        self.width = self.prepared.clip.width
        self.height = self.prepared.clip.height
        self.fps_num = self.prepared.clip.fps.numerator
        self.fps_den = self.prepared.clip.fps.denominator
        self.fps = self.fps_num / self.fps_den
        self.total_frames = Frame(self.prepared.clip.num_frames)

        self.name = self.info.get('name', 'Video Node %d' % self.vs_index)

        if self.main.outputs is not None:
            self.main.outputs.setData(self.main.outputs.index(self.vs_index), self.name)

        self.props = cast(vs.FrameProps, _default_props)

        if self.source.alpha:
            self.checkerboard = self._generate_checkerboard()

        if not hasattr(self, 'last_showed_frame') or not (0 <= self.last_showed_frame < self.total_frames):
            self.last_showed_frame = Frame(0)

        if index in self.main.timecodes:
            timecodes, tden = self.main.timecodes[index]

            if self.fps_num == 0:
                try:
                    play_fps = self.main.toolbars.playback.get_true_fps(0, self.props, True)
                except Exception:
                    if isinstance(timecodes, list):
                        play_fps = timecodes[self.last_showed_frame]
                    else:
                        play_fps = Fraction(24000, 1001)
            else:
                play_fps = Fraction(self.fps_num, self.fps_den)

            self.play_fps = play_fps

            if timecodes:
                from pathlib import Path

                from vstools import Timecodes

                if not isinstance(timecodes, list):
                    if isinstance(timecodes, (str, Path)):
                        timecodes = Timecodes.from_file(
                            timecodes, self.source.clip.num_frames, tden, func='set_timecodes'
                        ).to_fractions()

                if isinstance(timecodes, dict):
                    norm_timecodes = Timecodes.normalize_range_timecodes(
                        timecodes, self.source.clip.num_frames, play_fps  # type: ignore
                    )
                else:
                    norm_timecodes = timecodes.copy()

                if len(norm_timecodes) != self.source.clip.num_frames:
                    from vstools import FramesLengthError
                    raise FramesLengthError(
                        'set_timecodes', '', 'timecodes file length mismatch with clip\'s length!',
                        reason=dict(timecodes=len(norm_timecodes), clip=self.source.clip.num_frames)
                    )

                self.main.norm_timecodes[index] = norm_timecodes  # type: ignore
                self.play_fps = Fraction(norm_timecodes[self.last_showed_frame])
        elif not hasattr(self, 'play_fps'):
            if self.fps_num == 0 and self._stateset:
                self.play_fps = self.main.toolbars.playback.get_true_fps(
                    self.last_showed_frame.value, self.props
                )
            else:
                self.play_fps = Fraction(self.fps_num, self.fps_den)

        if self.fps_num == 0 and self._stateset:
            self.main.toolbars.playback.fps_variable_checkbox.setChecked(True)

        if index in self.main.norm_timecodes:
            norm_timecodes = self.main.norm_timecodes[index]  # type: ignore

            if (vfr := len(set(norm_timecodes)) > 1) or self.fps_num == 0:
                if not self.main.toolbars.playback.fps_variable_checkbox.isChecked():
                    self.main.toolbars.playback.fps_variable_checkbox.setChecked(True)

            self.got_timecodes = vfr
            self.timecodes = norm_timecodes
        else:
            self.got_timecodes = False

        if self.got_timecodes:
            acc = 0.0
            self._timecodes_frame_to_time = [0.0]
            for fps in self.timecodes:
                acc += round(1 / float(fps), 7)
                self._timecodes_frame_to_time.append(round(acc, 3))
            self.total_time = Time(seconds=acc)
        else:
            self.total_time = self.to_time(self.total_frames)

        if not hasattr(self, 'crop_values'):
            self.crop_values = CroppingInfo(0, 0, self.width, self.height, False, False)

        if not hasattr(self, 'ar_values'):
            self.ar_values = ArInfo(1, 1)

    def prepare_vs_output(self, clip: vs.VideoNode, pack_rgb: bool = True, fmt: vs.VideoFormat | None = None) -> vs.VideoNode:
        from jetpytools import KwargsT
        from vstools import (
            ChromaLocation, ColorRange, DitherType, Matrix, Primaries, Transfer, depth, video_heuristics
        )

        assert (src := clip).format

        heuristics, assumed_props = video_heuristics(clip, True, assumed_return=True)
        dither_type = DitherType(self.main.toolbars.playback.settings.dither_type.lower())

        assumed_values = {
            '_Matrix': heuristics.get('matrix_in'),
            '_Transfer': heuristics.get('transfer_in'),
            '_Primaries': heuristics.get('primaries_in'),
            '_ColorRange': heuristics.get('range_in'),
            '_ChromaLocation': heuristics.get('chromaloc_in'),
        }

        if self._stateset and assumed_props:
            assumed_info = [
                f'{prop}={int(value)} ({value.pretty_string})'  # type: ignore
                for prop, value in assumed_values.items()
                if prop in assumed_props
            ]

            logging.warning(
                'Video Node {0}: The following frame properties had to be assumed for previewing: '
                '<{1}>\nYou may want to set explicit frame properties instead. '
                'See https://www.vapoursynth.com/doc/apireference.html#reserved-frame-properties for more information.'
                .format(self.index, ", ".join(assumed_info))
            )

        standard_gamut = {'transfer': Transfer.BT709, 'primaries': self.main.settings.output_primaries_zimg}

        if (
            not self.main.display_profile
            or self.main.display_profile.primaries() == QColorSpace.Primaries.SRgb
        ) and heuristics['primaries_in'] in (
            Primaries.BT2020, Primaries.ST428, Primaries.ST431_2, Primaries.ST432_1
        ):
            standard_gamut = {}

        resizer_kwargs = KwargsT({
            'format': fallback(fmt, PackingType.CURRENT.vs_format if pack_rgb else PackingType.CURRENT.vs_alpha_format),
            'matrix_in': Matrix.BT709,
            'transfer_in': Transfer.BT709,
            'primaries_in': Primaries.BT709,
            'range_in': ColorRange.LIMITED,
            'chromaloc_in': ChromaLocation.LEFT
        } | heuristics | standard_gamut | {
            'filter_param_a': self.main.toolbars.playback.settings.kernel['b'],
            'filter_param_b': self.main.toolbars.playback.settings.kernel['c']
        })

        if src.format.color_family == vs.RGB:
            del resizer_kwargs['matrix_in']
        elif src.format.color_family == vs.GRAY:
            clip = clip.std.RemoveFrameProps('_Matrix')

        if resizer_kwargs['transfer_in'] == Transfer.SRGB:
            resizer_kwargs['transfer'] = resizer_kwargs['transfer_in']

        if isinstance(resizer_kwargs['range_in'], ColorRange):
            resizer_kwargs['range_in'] = resizer_kwargs['range_in'].value_zimg

        assert clip.format

        if src.format.id == vs.GRAY32:
            return clip

        to_fmt: vs.VideoFormat = resizer_kwargs.pop('format')

        if src.format.id == to_fmt:
            return clip

        if dither_type.is_fmtc:
            temp_fmt = to_fmt.replace(sample_type=src.format.sample_type, bits_per_sample=src.format.bits_per_sample)
            clip = clip.resize.Bicubic(**resizer_kwargs, format=temp_fmt.id)
            clip = depth(clip, to_fmt, dither_type=dither_type)
        else:
            clip = clip.resize.Bicubic(**resizer_kwargs, format=to_fmt, dither_type=dither_type.value)

        if not self.cached:
            clip.std.SetVideoCache(0)

        if pack_rgb:
            clip = self.pack_rgb_clip(clip)

        return clip.std.CopyFrameProps(src)

    def pack_rgb_clip(self, clip: vs.VideoNode) -> vs.VideoNode:
        if PackingType.CURRENT.shuffle:
            clip = clip.std.ShufflePlanes([2, 1, 0], vs.RGB)

        shift = 2 ** (10 - PackingType.CURRENT.vs_format.bits_per_sample)
        r_shift, g_shift, b_shift = (x * shift for x in (1, 0x400, 0x100000))
        high_bits_mask = 0xc0000000

        if PackingType.CURRENT in {
            PackingType.none_8bit, PackingType.none_10bit, PackingType.numpy_8bit, PackingType.numpy_10bit
        }:
            blank = vs.core.std.BlankClip(clip, None, None, vs.GRAY32, color=high_bits_mask, keep=True)

            if PackingType.CURRENT in {PackingType.none_8bit, PackingType.none_10bit}:
                from functools import partial
                from multiprocessing.pool import ThreadPool

                from jetpytools import ranges_product

                indices = list(ranges_product(blank.height, blank.width))

                pool = ThreadPool(self.main.settings.usable_cpus_count * 8)

                def _packing_edarray(
                    bfp: vs.video_view, src_r: vs.video_view,
                    src_g: vs.video_view, src_b: vs.video_view,
                    idx: tuple[int, int]
                ) -> None:
                    bfp[idx] += (src_r[idx] * r_shift) + (src_g[idx] * g_shift) + (src_b[idx] * b_shift)

                def _packrgb(n: int, f: list[vs.VideoFrame]) -> vs.VideoFrame:
                    bf = f[0].copy()

                    pool.map_async(partial(_packing_edarray, bf[0], f[1][0], f[1][1], f[1][2]), indices).wait()

                    return bf
            else:
                import numpy as np

                ein_shift = np.array([b_shift, g_shift, r_shift], np.uint32)

                from numpy.core._multiarray_umath import c_einsum  # type: ignore
                from numpy.core.numeric import tensordot

                self.__base_numpy_add = base_add = np.asarray(blank.get_frame(0).copy()[0]).copy()

                def _packrgb(n: int, f: list[vs.VideoFrame]) -> vs.VideoFrame:
                    bf = f[0].copy()

                    np.add(
                        c_einsum(
                            'ji->ji', tensordot(np.asarray(f[1], np.uint32), ein_shift, ((0,), (0,)))
                        ), base_add, np.asarray(bf[0])
                    )

                    return bf

            return blank.std.ModifyFrame([blank, clip], _packrgb)

        if PackingType.CURRENT in {PackingType.libp2p_8bit, PackingType.libp2p_10bit}:
            return vs.core.libp2p.Pack(clip)

        if PackingType.CURRENT in {PackingType.akarin_8bit, PackingType.akarin_10bit}:
            # x, y, z => b, g, r
            # we want a contiguous array, so we put in 0, 10 bits the R, 11 to 20 the G and 21 to 30 the B
            # R stays like it is * shift if it's 8 bits (gets applied to all planes), then G gets shifted
            # by 10 bits, (we multiply by 2 ** 10) and same for B but by 20 bits and it all gets summed
            return vs.core.akarin.Expr(
                clip.std.SplitPlanes(),
                f'z {b_shift} * y {g_shift} * x {r_shift} * + + {high_bits_mask} +', vs.GRAY32, True
            )

        return clip

    def frame_to_qimage(self, frame: vs.VideoFrame, is_alpha: bool = False) -> QImage:
        from ctypes import POINTER
        from ctypes import cast as ccast

        width, height, stride = frame.width, frame.height, frame.get_stride(0)
        point_size, qt_format = PackingType.CURRENT.conv_info[is_alpha]

        pointer = cast(
            sip.voidptr, ccast(frame.get_read_ptr(0), POINTER(point_size * stride)).contents
        )

        return QImage(pointer, width, height, stride, qt_format).copy()  # type: ignore

    @property
    def graphics_scene_item(self) -> GraphicsImageItem | None:
        if self.main.graphics_view.graphics_scene.graphics_items:
            try:
                return self.main.graphics_view.graphics_scene.graphics_items[self.index]
            except IndexError:
                ...

        return None

    def update_graphic_item(
        self, pixmap: QPixmap | None = None,
        crop_values: CroppingInfo | None | bool = None,
        ar_values: ArInfo | None | bool = None,
        graphics_scene_item: GraphicsImageItem | None = None
    ) -> QPixmap | None:
        from jetpytools import complex_hash

        old_crop = complex_hash.hash(self.crop_values)
        old_ar = complex_hash.hash(self.ar_values)

        if isinstance(crop_values, bool):
            self.crop_values.active = crop_values
        elif crop_values is not None:
            self.crop_values = crop_values

        if isinstance(ar_values, bool):
            self.ar_values.active = ar_values
        elif ar_values is not None:
            self.ar_values = ar_values

        new_crop = complex_hash.hash(self.crop_values)
        new_ar = complex_hash.hash(self.ar_values)

        if graphics_scene_item:
            graphics_scene_item.setPixmap(pixmap, self.crop_values, self.ar_values)

        if old_crop != new_crop:
            self.main.cropValuesChanged.emit(self.crop_values)

        if old_ar != new_ar:
            self.main.arValuesChanged.emit(self.ar_values)

        return pixmap

    def render_frame(
        self, frame: Frame | None, vs_frame: vs.VideoFrame | None = None,
        vs_alpha_frame: vs.VideoFrame | None = None,
        graphics_scene_item: GraphicsImageItem | None = None,
        do_painting: bool = True, output_colorspace: QColorSpace | None = None
    ) -> QPixmap:
        if frame is None or not self._stateset:
            return QPixmap()

        frame = min(max(frame, Frame(0)), self.total_frames - 1)

        if not vs_frame:
            try:
                vs_frame = self.prepared.clip.get_frame(frame.value)
            except vs.Error as e:
                self.main.handle_error(e)
                return QPixmap()

        self.props = cast(vs.FrameProps, vs_frame.props.copy())

        frame_image = self.frame_to_qimage(vs_frame, False)

        if output_colorspace is not None:
            frame_image.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
            frame_image.convertToColorSpace(output_colorspace)

        if not vs_frame.closed:
            vs_frame.close()
            del vs_frame

        if graphics_scene_item is None:
            graphics_scene_item = self.graphics_scene_item

        if self.prepared.alpha is None:
            qpixmap = QPixmap.fromImage(frame_image, Qt.ImageConversionFlag.NoFormatConversion)

            if do_painting:
                self.update_graphic_item(qpixmap, graphics_scene_item=graphics_scene_item)

            return qpixmap

        alpha_image = self.frame_to_qimage(
            vs_alpha_frame or self.prepared.alpha.get_frame(frame.value), True
        )

        result_image = QImage(frame_image.size(), QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(result_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, frame_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, alpha_image)

        if self.main.toolbars.playback.settings.CHECKERBOARD_ENABLED:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOver)
            painter.drawImage(0, 0, self.checkerboard)

        painter.end()

        qpixmap = QPixmap.fromImage(result_image, Qt.ImageConversionFlag.NoFormatConversion)

        if do_painting:
            self.update_graphic_item(qpixmap, graphics_scene_item=graphics_scene_item)

        return qpixmap

    def _generate_checkerboard(self) -> QImage:
        tile_size = self.main.toolbars.playback.settings.CHECKERBOARD_TILE_SIZE
        tile_color_1 = self.main.toolbars.playback.settings.CHECKERBOARD_TILE_COLOR_1
        tile_color_2 = self.main.toolbars.playback.settings.CHECKERBOARD_TILE_COLOR_2

        macrotile_pixmap = QPixmap(tile_size * 2, tile_size * 2)
        painter = QPainter(macrotile_pixmap)
        painter.fillRect(macrotile_pixmap.rect(), tile_color_1)
        painter.fillRect(tile_size, 0, tile_size, tile_size, tile_color_2)
        painter.fillRect(0, tile_size, tile_size, tile_size, tile_color_2)
        painter.end()

        result_image = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(result_image)
        painter.drawTiledPixmap(result_image.rect(), macrotile_pixmap)
        painter.end()

        return result_image

    def _calculate_frame(self, seconds: float) -> int:
        if self.got_timecodes:
            seconds = float(f'{round(seconds, 7):.6f}')

            ref, maxx = int(self.last_showed_frame), int(self.total_frames)
            low, high = max(ref - 6, 0), min(ref + 6, maxx - 1)

            if (
                li := int(self._timecodes_frame_to_time[low] > seconds)
            ) or (
                hi := int(self._timecodes_frame_to_time[high] < seconds)
            ):
                while self._timecodes_frame_to_time[low] > seconds and low > 0:
                    low -= 6 * li
                    li += 1

                while self._timecodes_frame_to_time[high] < seconds and high < maxx:
                    high += 6 * hi
                    hi += 1

                low, high = max(low - 1, 0), min(high + 1, maxx - 1)

            for i, time in zip(range(high, low - 1, -1), reversed(self._timecodes_frame_to_time[low:high + 1])):
                if time == seconds:
                    return i

                if time < seconds:
                    return i + 1

        return round(seconds * self.fps)

    def _calculate_seconds(self, frame_num: int) -> float:
        if self.got_timecodes:
            return self._timecodes_frame_to_time[frame_num]
        return frame_num / (self.fps or 1)

    def to_frame(self, time: Time) -> Frame:
        return Frame(self._calculate_frame(float(time)))

    def to_time(self, frame: Frame) -> Time:
        return Time(seconds=self._calculate_seconds(int(frame)))

    def with_node(self, new_node: vs.VideoNode | VideoOutputNode) -> VideoOutput:
        if isinstance(new_node, vs.VideoNode):
            new_node = VideoOutputNode(new_node, None, self.cached)

        new_output = VideoOutput(new_node, self.vs_index, False)
        new_output.index = self.index

        new_output.last_showed_frame = self.last_showed_frame
        new_output.name = self.name

        return new_output

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'name', str, self.__setattr__)
        try_load(state, 'last_showed_frame', Frame, self.__setattr__)
        try_load(state, 'play_fps', Fraction, self.__setattr__)
        try_load(state, 'crop_values', CroppingInfo, self.__setattr__)
        try_load(state, 'ar_values', ArInfo, self.__setattr__)

        self._stateset = True
