from __future__ import annotations

import ctypes
import itertools
import logging
import os
import sys
from typing import Any, List, Mapping, Tuple, cast

import vapoursynth as vs
from PyQt5 import sip
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPainter, QPixmap

from ..abstracts import AbstractYAMLObject, main_window, try_load
from ..vsenv import __name__ as _venv  # noqa: F401
from .dataclasses import CroppingInfo, NumpyVideoPHelp, VideoOutputNode
from .units import Frame, Time

core = vs.core


class PackingTypeInfo():
    _getid = itertools.count()

    def __init__(
        self, vs_format: vs.PresetFormat | vs.VideoFormat, qt_format: QImage.Format, shuffle: bool
    ):
        self.id = next(self._getid)
        self.vs_format = core.get_format(vs_format)
        self.qt_format = qt_format
        self.shuffle = shuffle

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackingTypeInfo):
            raise NotImplementedError
        return self.id == other.id

    def __hash__(self) -> int:
        return int(self.id)


_iled = (sys.byteorder == 'little')
_default_10bits = os.name != 'nt' and QPixmap.defaultDepth() == 30


class PackingType(PackingTypeInfo):
    libp2p_8bit = PackingTypeInfo(vs.RGB24, QImage.Format_RGB32, False)
    libp2p_10bit = PackingTypeInfo(vs.RGB30, QImage.Format_BGR30, True)
    akarin_8bit = PackingTypeInfo(vs.RGB24, QImage.Format_BGR30, True)
    akarin_10bit = PackingTypeInfo(vs.RGB30, QImage.Format_BGR30, True)
    numpy_8bit = PackingTypeInfo(vs.RGB24, QImage.Format_RGB32, False)
    numpy_10bit = PackingTypeInfo(vs.RGB30, QImage.Format_BGR30, True)
    NONE_numpy_8bit = PackingTypeInfo(vs.RGB24, QImage.Format_RGB32, False)
    NONE_numpy_10bit = PackingTypeInfo(vs.RGB30, QImage.Format_RGB30, False)


# From fastest to slowest
if hasattr(core, 'libp2p'):
    PACKING_TYPE = PackingType.libp2p_10bit if _default_10bits else PackingType.libp2p_8bit
elif hasattr(core, 'akarin'):
    PACKING_TYPE = PackingType.akarin_10bit if _default_10bits else PackingType.akarin_8bit
else:
    logging.warning(Warning(
        "\n\tLibP2P and Akarin plugin are missing, they're recommended to prepare output clips correctly!\n"
        "\t  You can get them here: \n"
        "\t  https://github.com/DJATOM/LibP2P-Vapoursynth\n\t  https://github.com/AkarinVS/vapoursynth-plugin"
    ))

    try:
        import numpy  # noqa

        # temp forced defaults until I have all the settings sorted out
        if _default_10bits:
            PACKING_TYPE = PackingType.NONE_numpy_10bit if True else PackingType.numpy_10bit
        else:
            PACKING_TYPE = PackingType.NONE_numpy_8bit if True else PackingType.numpy_8bit
    except ImportError:
        logging.error(RuntimeError("Numpy isn't installed either. Exiting..."))
        exit(1)


class VideoOutput(AbstractYAMLObject):
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
        'title', 'last_showed_frame', 'play_fps', 'crop_values'
    )

    __slots__ = (
        *storable_attrs, 'index', 'width', 'height', 'fps_num', 'fps_den',
        'total_frames', 'total_time', 'graphics_scene_item',
        'end_frame', 'end_time', 'fps', 'source', 'prepared',
        'main', 'checkerboard', 'props', '_stateset'
    )

    source: VideoOutputNode
    prepared: VideoOutputNode
    format: vs.VideoFormat
    title: str | None
    curr_rendered_frame: Tuple[vs.VideoFrame, vs.VideoFrame | None]
    last_showed_frame: Frame
    crop_values: CroppingInfo
    _stateset: bool

    def clear(self) -> None:
        self.source = self.prepared = None  # type: ignore

    def __init__(self, vs_output: vs.VideoOutputTuple, index: int, new_storage: bool = False) -> None:
        self.setValue(vs_output, index, new_storage)

    def setValue(self, vs_output: vs.VideoOutputTuple, index: int, new_storage: bool = False) -> None:
        from ..custom import GraphicsImageItem

        self._stateset = not new_storage

        self.main = main_window()

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
        self.total_time = self.to_time(self.total_frames - Frame(1))
        self.end_frame = Frame(int(self.total_frames) - 1)
        self.end_time = self.to_time(self.end_frame)
        self.title = None
        self.props = cast(vs.FrameProps, {})

        if self.source.alpha:
            self.checkerboard = self._generate_checkerboard()

        if not hasattr(self, 'last_showed_frame') or 0 > self.last_showed_frame > self.end_frame:
            self.last_showed_frame = Frame(0)

        self.graphics_scene_item: GraphicsImageItem

        if not hasattr(self, 'play_fps'):
            if self.fps_num == 0 and self._stateset:
                self.play_fps = self.main.toolbars.playback.get_true_fps(self.props)
                if not self.main.toolbars.playback.fps_variable_checkbox.isChecked():
                    self.main.toolbars.playback.fps_variable_checkbox.setChecked(True)
            else:
                self.play_fps = self.fps_num / self.fps_den

        if not hasattr(self, 'crop_values'):
            self.crop_values = CroppingInfo(0, 0, self.width, self.height, False, False)

    @property
    def name(self) -> str:
        if 'Name' in self.props:
            self.title = cast(bytes, self.props['Name']).decode('utf-8')
        else:
            self.title = 'Video Node %d' % self.index

        return self.title

    @name.setter
    def name(self, newname: str) -> None:
        self.title = newname

    _NORML_FMT = PACKING_TYPE.vs_format
    _ALPHA_FMT = core.get_format(vs.GRAY8)
    _FRAME_CONV_INFO = {
        False: (_NORML_FMT.bits_per_sample, ctypes.c_char * _NORML_FMT.bytes_per_sample, PACKING_TYPE.qt_format),
        True: (_ALPHA_FMT.bits_per_sample, ctypes.c_char * _NORML_FMT.bytes_per_sample, QImage.Format_Alpha8)
    }

    _curr_pointers = NumpyVideoPHelp()

    def prepare_vs_output(self, clip: vs.VideoNode, is_alpha: bool = False) -> vs.VideoNode:
        assert clip.format

        resizer = self.main.VS_OUTPUT_RESIZER
        resizer_kwargs = {
            'format': self._NORML_FMT.id,
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
        elif clip.format.color_family == vs.GRAY:
            clip = clip.std.RemoveFrameProps('_Matrix')

        assert clip.format

        if is_alpha:
            if clip.format.id == self._ALPHA_FMT.id:
                return clip
            resizer_kwargs['format'] = self._ALPHA_FMT.id

        clip = resizer(clip, **resizer_kwargs, **self.main.VS_OUTPUT_RESIZER_KWARGS)

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

        if PACKING_TYPE in {PackingType.numpy_8bit, PackingType.numpy_10bit}:
            import numpy as np

            bits = PACKING_TYPE.vs_format.bits_per_sample

            def _numpack(n: int, f: List[vs.VideoFrame]) -> vs.VideoFrame:
                dst_frame = f[1].copy()

                rgb_data = np.asarray(f[0], np.uint32)

                packed = np.einsum(
                    'kji,k->ji', rgb_data, np.array(
                        [2 ** (bits * 2), 2 ** bits, 1], np.uint32
                    ), optimize='greedy'
                )

                np.copyto(np.asarray(dst_frame[0]), packed)

                return dst_frame

            contiguous_clip = core.std.BlankClip(clip, format=vs.GRAY32)

            return contiguous_clip.std.ModifyFrame([clip, contiguous_clip], _numpack)

        return clip

    def frame_to_qimage(self, frame: vs.VideoFrame, is_alpha: bool = False) -> QImage:
        width, height = frame.width, frame.height
        mod, point_size, qt_format = self._FRAME_CONV_INFO[is_alpha]

        stride = frame.get_stride(0)
        memory_bug_fix = False
        ctype_pointer = ctypes.POINTER(point_size * stride)

        if PACKING_TYPE in {PackingType.NONE_numpy_8bit, PackingType.NONE_numpy_10bit}:
            import numpy as np

            if not self._curr_pointers.data:
                bytesps = PACKING_TYPE.vs_format.bytes_per_sample
                self._curr_pointers.data = np.empty(
                    (height, width * 4 // bytesps), dtype=[np.uint8, np.uint16][bytesps - 1]
                )
                self._curr_pointers.stride = self._curr_pointers.data.ctypes.strides[0]

            stride = self._curr_pointers.stride

        ctype_pointer = ctypes.POINTER(point_size * stride)

        if PACKING_TYPE in {PackingType.NONE_numpy_8bit, PackingType.NONE_numpy_10bit}:
            if PACKING_TYPE.vs_format.bits_per_sample == 8:
                for i in range(1, 4):
                    self._curr_pointers.data[:, (3 - i) if _iled else i::4] = np.ctypeslib.as_array(frame[i - 1])
            else:
                rPlane = np.ctypeslib.as_array(frame[0]).view(np.uint16)
                gPlane = np.ctypeslib.as_array(frame[1]).view(np.uint16)
                bPlane = np.ctypeslib.as_array(frame[2]).view(np.uint16)

                if _iled:
                    self._curr_pointers.data[:, 1::2] = 0xc000 | ((rPlane & 0x3ff) << 4) | ((gPlane & 0x3ff) >> 6)
                    self._curr_pointers.data[:, 0::2] = ((gPlane & 0x3ff) << 10) | (bPlane & 0x3ff)
                else:
                    self._curr_pointers.data[:, 0::2] = ((bPlane & 0x3ff) << 6) | ((gPlane & 0x3ff) >> 4)
                    self._curr_pointers.data[:, 1::2] = 0x0003 | ((rPlane & 0x3ff) << 2) | ((gPlane & 0x3ff) << 12)

            self._curr_pointers.pointer = cast(
                sip.voidptr, self._curr_pointers.data.ctypes.data_as(ctype_pointer).contents
            )
        else:
            if width % mod:
                self._curr_pointers.pointer = cast(
                    sip.voidptr, ctypes.cast(
                        frame.get_read_ptr(0), ctype_pointer
                    ).contents
                )
                memory_bug_fix = True
            else:
                self._curr_pointers.pointer = cast(sip.voidptr, frame[0])

        image = QImage(self._curr_pointers.pointer, width, height, stride, qt_format)

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
        vs_alpha_frame: vs.VideoFrame | None = None, do_painting: bool = True
    ) -> QPixmap:
        if frame is None or not self._stateset:
            return QPixmap()

        frame = min(max(frame, Frame(0)), self.end_frame)

        vs_frame = vs_frame or self.prepared.clip.get_frame(frame.value)

        self.props = cast(vs.FrameProps, vs_frame.props.copy())

        frame_image = self.frame_to_qimage(vs_frame, False)

        if not vs_frame.closed:
            vs_frame.close()
            del vs_frame

        if self.prepared.alpha is None:
            qpixmap = QPixmap.fromImage(frame_image, Qt.NoFormatConversion)

            if do_painting:
                self.update_graphic_item(qpixmap)

            return qpixmap

        alpha_image = self.frame_to_qimage(
            vs_alpha_frame or self.prepared.alpha.get_frame(frame.value), True
        )

        result_image = QImage(frame_image.size(), QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(result_image)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawImage(0, 0, frame_image)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, alpha_image)

        if self.main.toolbars.playback.settings.CHECKERBOARD_ENABLED:
            painter.setCompositionMode(QPainter.CompositionMode_DestinationOver)
            painter.drawImage(0, 0, self.checkerboard)

        painter.end()

        qpixmap = QPixmap.fromImage(result_image, Qt.NoFormatConversion)

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

        result_image = QImage(self.width, self.height, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(result_image)
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

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'title', str, self.__setattr__)
        try_load(state, 'last_showed_frame', Frame, self.__setattr__)
        try_load(state, 'play_fps', float, self.__setattr__)
        try_load(state, 'crop_values', CroppingInfo, self.__setattr__)

        self._stateset = True
