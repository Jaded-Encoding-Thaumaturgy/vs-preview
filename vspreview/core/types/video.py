from __future__ import annotations

import ctypes
import itertools
import os
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, cast

from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColorSpace, QImage, QPainter, QPixmap
from vstools import ColorRange, DependencyNotFoundError, FramesLengthError, core, video_heuristics, vs

from ..abstracts import AbstractYAMLObject, main_window, try_load
from .dataclasses import CroppingInfo, VideoOutputNode
from .units import Frame, Time


class PackingTypeInfo:
    _getid = itertools.count()

    def __init__(
        self, vs_format: vs.PresetFormat | vs.VideoFormat, qt_format: QImage.Format, shuffle: bool
    ):
        self.id = next(self._getid)
        self.vs_format = core.get_video_format(vs_format)
        self.qt_format = qt_format
        self.shuffle = shuffle

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackingTypeInfo):
            raise NotImplementedError
        return self.id == other.id

    def __hash__(self) -> int:
        return int(self.id)


class PackingType(PackingTypeInfo):
    libp2p_8bit = PackingTypeInfo(vs.RGB24, QImage.Format.Format_RGB32, False)
    libp2p_10bit = PackingTypeInfo(vs.RGB30, QImage.Format.Format_BGR30, True)
    akarin_8bit = PackingTypeInfo(vs.RGB24, QImage.Format.Format_BGR30, True)
    akarin_10bit = PackingTypeInfo(vs.RGB30, QImage.Format.Format_BGR30, True)


if not hasattr(core, 'akarin') and not hasattr(core, 'libp2p'):
    raise ImportError(
        "\n\tLibP2P and Akarin plugin are missing, one is required to prepare output clips correctly!\n"
        "\t  You can get them here: \n"
        "\t  https://github.com/DJATOM/LibP2P-Vapoursynth\n\t  https://github.com/AkarinVS/vapoursynth-plugin"
    )

PACKING_TYPE: PackingType = None  # type: ignore


class VideoOutput(AbstractYAMLObject):
    storable_attrs = (
        'title', 'last_showed_frame', 'play_fps', 'crop_values'
    )

    __slots__ = (
        *storable_attrs, 'index', 'width', 'height', 'fps_num', 'fps_den',
        'total_frames', 'total_time', 'graphics_scene_item',
        'end_frame', 'fps', 'source', 'prepared',
        'main', 'checkerboard', 'props', '_stateset'
    )

    source: VideoOutputNode
    prepared: VideoOutputNode
    title: str | None
    last_showed_frame: Frame
    crop_values: CroppingInfo
    _stateset: bool

    def clear(self) -> None:
        self.source = self.prepared = None

    def __init__(
        self, vs_output: vs.VideoOutputTuple | VideoOutputNode, index: int, new_storage: bool = False
    ) -> None:
        self.setValue(vs_output, index, new_storage)

    def setValue(
        self, vs_output: vs.VideoOutputTuple | VideoOutputNode, index: int, new_storage: bool = False
    ) -> None:
        from ..custom import GraphicsImageItem

        self._stateset = not new_storage

        self.main = main_window()
        self.set_fmt_values()

        # runtime attributes
        self.source = VideoOutputNode(vs_output.clip, vs_output.alpha)
        self.prepared = VideoOutputNode(vs_output.clip, vs_output.alpha)

        if self.source.alpha is not None:
            self.prepared.alpha = self.prepare_vs_output(self.source.alpha, True).std.CopyFrameProps(self.source.alpha)

        self.index = index

        self.prepared.clip = self.prepare_vs_output(self.source.clip).std.CopyFrameProps(self.source.clip)
        self.width = self.prepared.clip.width
        self.height = self.prepared.clip.height
        self.fps_num = self.prepared.clip.fps.numerator
        self.fps_den = self.prepared.clip.fps.denominator
        self.fps = self.fps_num / self.fps_den
        self.total_frames = Frame(self.prepared.clip.num_frames)
        self.title = None
        if self.main.outputs and vs_output in (vs_outputs := list(vs.get_outputs().values())):
            self.title = self.main.user_output_names[vs.VideoNode].get(vs_outputs.index(vs_output))
            self.main.outputs.setData(self.main.outputs.index(index), self.title)
        self.props = cast(vs.FrameProps, {})

        if self.source.alpha:
            self.checkerboard = self._generate_checkerboard()

        if not hasattr(self, 'last_showed_frame') or not (0 <= self.last_showed_frame < self.total_frames):
            self.last_showed_frame = Frame(0)

        self.graphics_scene_item: GraphicsImageItem

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

            self.play_fps = float(play_fps)

            if timecodes:
                if not isinstance(timecodes, list):
                    try:
                        from vsdeinterlace import get_timecodes, normalize_range_timecodes, normalize_timecodes

                        if isinstance(timecodes, (str, Path)):
                            timecodes = get_timecodes(self.source.clip, timecodes, tden, 'set_timecodes')
                            timecodes = normalize_timecodes(timecodes)
                        vsdeint_available = True
                    except Exception:
                        vsdeint_available = False
                        raise DependencyNotFoundError('set_timecodes', 'vsdeinterlace')

                if isinstance(timecodes, dict):
                    if not vsdeint_available:
                        raise DependencyNotFoundError('set_timecodes', 'vsdeinterlace')
                    norm_timecodes = normalize_range_timecodes(timecodes, self.source.clip.num_frames, play_fps)
                else:
                    norm_timecodes = timecodes.copy()

                if len(norm_timecodes) != self.source.clip.num_frames:
                    raise FramesLengthError(
                        'set_timecodes', '', 'timecodes file length mismatch with clip\'s length!',
                        reason=dict(timecodes=len(norm_timecodes), clip=self.source.clip.num_frames)
                    )

                self.main.norm_timecodes[index] = norm_timecodes
                self.play_fps = float(norm_timecodes[self.last_showed_frame])
        elif not hasattr(self, 'play_fps'):
            if self.fps_num == 0 and self._stateset:
                self.play_fps = self.main.toolbars.playback.get_true_fps(
                    self.last_showed_frame.value, self.props
                )
            else:
                self.play_fps = self.fps_num / self.fps_den

        if index in self.main.norm_timecodes:
            norm_timecodes = self.main.norm_timecodes[index]

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
            self.total_time = self.to_time(self.total_frames - Frame(1))

        if not hasattr(self, 'crop_values'):
            self.crop_values = CroppingInfo(0, 0, self.width, self.height, False, False)

    def set_fmt_values(self) -> None:
        global PACKING_TYPE

        _default_10bits = os.name != 'nt' and QPixmap.defaultDepth() == 30

        # From fastest to slowest
        if hasattr(core, 'akarin'):
            PACKING_TYPE = PackingType.akarin_10bit if _default_10bits else PackingType.akarin_8bit
        elif hasattr(core, 'libp2p'):
            PACKING_TYPE = PackingType.libp2p_10bit if _default_10bits else PackingType.libp2p_8bit

        self._NORML_FMT = PACKING_TYPE.vs_format
        self._ALPHA_FMT = core.get_video_format(vs.GRAY8)

        nbps, abps = self._NORML_FMT.bits_per_sample, self._ALPHA_FMT.bytes_per_sample
        self._FRAME_CONV_INFO = {
            False: (nbps, ctypes.c_char * nbps, PACKING_TYPE.qt_format),
            True: (abps, ctypes.c_char * abps, QImage.Format.Format_Alpha8)
        }

    @property
    def name(self) -> str:
        placeholder = 'Video Node %d' % self.index
        if not hasattr(self, 'title') or self.title in {None, placeholder}:
            if 'Name' in self.props:
                self.title = cast(bytes, self.props['Name']).decode('utf-8')
            elif not self.title:
                self.title = placeholder

        return self.title or placeholder

    @name.setter
    def name(self, newname: str) -> None:
        self.title = newname

    def prepare_vs_output(self, clip: vs.VideoNode, is_alpha: bool = False) -> vs.VideoNode:
        assert clip.format

        is_subsampled = (clip.format.subsampling_w != 0 or clip.format.subsampling_h != 0)

        resizer = core.resize.Bicubic if is_subsampled else core.resize.Point

        heuristics = video_heuristics(clip, None)

        resizer_kwargs = {
            'format': self._NORML_FMT.id,
            'matrix_in': self.main.VS_OUTPUT_MATRIX,
            'transfer_in': self.main.VS_OUTPUT_TRANSFER,
            'primaries_in': self.main.VS_OUTPUT_PRIMARIES,
            'range_in': self.main.VS_OUTPUT_RANGE,
            'chromaloc_in': self.main.VS_OUTPUT_CHROMALOC
        } | heuristics | {
            'dither_type': self.main.toolbars.playback.settings.dither_type
        }

        if clip.format.color_family == vs.RGB:
            del resizer_kwargs['matrix_in']
        elif clip.format.color_family == vs.GRAY:
            clip = clip.std.RemoveFrameProps('_Matrix')

        if isinstance(resizer_kwargs['range_in'], ColorRange):
            resizer_kwargs['range_in'] = resizer_kwargs['range_in'].value_zimg

        assert clip.format

        if is_alpha:
            if clip.format.id == self._ALPHA_FMT.id:
                return clip
            resizer_kwargs['format'] = self._ALPHA_FMT.id

        clip = resizer(clip, **resizer_kwargs)

        if is_alpha:
            return clip

        return self.pack_rgb_clip(clip)

    def pack_rgb_clip(self, clip: vs.VideoNode) -> vs.VideoNode:
        if PACKING_TYPE.shuffle:
            clip = clip.std.ShufflePlanes([2, 1, 0], vs.RGB)

        if PACKING_TYPE in {PackingType.libp2p_8bit, PackingType.libp2p_10bit}:
            return core.libp2p.Pack(clip)

        if PACKING_TYPE in {PackingType.akarin_8bit, PackingType.akarin_10bit}:
            # x, y, z => b, g, r
            # we want a contiguous array, so we put in 0, 10 bits the R, 11 to 20 the G and 21 to 30 the B
            # R stays like it is + shift if it's 8 bits (gets applied to all clips), then G gets shifted
            # by 10 bits, (we multiply by 2 ** 10) and same for B but by 20 bits and it all gets summed
            return core.akarin.Expr(
                clip.std.SplitPlanes(),
                f'{2 ** (10 - PACKING_TYPE.vs_format.bits_per_sample)} s! x s@ 0x100000 * * '
                'y s@ 0x400 * * + z s@ * + 0xc0000000 +', vs.GRAY32, True
            )

        return clip

    def frame_to_qimage(self, frame: vs.VideoFrame, is_alpha: bool = False) -> QImage:
        width, height = frame.width, frame.height
        mod, point_size, qt_format = self._FRAME_CONV_INFO[is_alpha]

        stride = frame.get_stride(0)
        memory_bug_fix = False

        ctype_pointer = ctypes.POINTER(point_size * stride)

        if width % mod or is_alpha:
            self._curr_pointer = cast(
                sip.voidptr, ctypes.cast(
                    frame.get_read_ptr(0), ctype_pointer
                ).contents
            )
            memory_bug_fix = True
        else:
            self._curr_pointer = cast(sip.voidptr, frame[0])

        image = QImage(self._curr_pointer, width, height, stride, qt_format)

        return image.copy() if memory_bug_fix else image

    def update_graphic_item(
        self, pixmap: QPixmap | None = None, crop_values: CroppingInfo | None | bool = None
    ) -> QPixmap | None:
        if isinstance(crop_values, bool):
            self.crop_values.active = crop_values
        elif crop_values is not None:
            self.crop_values = crop_values

        if hasattr(self, 'graphics_scene_item'):
            self.graphics_scene_item.setPixmap(pixmap, self.crop_values)
        return pixmap

    def render_frame(
        self, frame: Frame | None, vs_frame: vs.VideoFrame | None = None,
        vs_alpha_frame: vs.VideoFrame | None = None, do_painting: bool = True,
        output_colorspace: QColorSpace | None = None
    ) -> QPixmap:
        if frame is None or not self._stateset:
            return QPixmap()

        frame = min(max(frame, Frame(0)), self.total_frames - 1)

        vs_frame = vs_frame or self.prepared.clip.get_frame(frame.value)

        self.props = cast(vs.FrameProps, vs_frame.props.copy())

        frame_image = self.frame_to_qimage(vs_frame, False)

        if output_colorspace is not None:
            frame_image.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
            frame_image.convertToColorSpace(output_colorspace)

        if not vs_frame.closed:
            vs_frame.close()
            del vs_frame

        if self.prepared.alpha is None:
            qpixmap = QPixmap.fromImage(frame_image, Qt.ImageConversionFlag.NoFormatConversion)

            if do_painting:
                self.update_graphic_item(qpixmap)

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
            self.update_graphic_item(qpixmap)

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
                li := self._timecodes_frame_to_time[low] > seconds
            ) or (
                hi := self._timecodes_frame_to_time[high] < seconds
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

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'title', str, self.__setattr__)
        try_load(state, 'last_showed_frame', Frame, self.__setattr__)
        try_load(state, 'play_fps', float, self.__setattr__)
        try_load(state, 'crop_values', CroppingInfo, self.__setattr__)

        self._stateset = True
