from __future__ import annotations

import ctypes
from math import floor
from array import array
import vapoursynth as vs
from yaml import YAMLObject
from typing import Any, Mapping

from ..abstracts import main_window, try_load
from .units import Frame, Time

from PyQt5.QtMultimedia import QAudioFormat, QAudioOutput, QAudioDeviceInfo


core = vs.core


class AudioOutput(YAMLObject):
    SAMPLES_PER_FRAME = 3000

    storable_attrs = (
        'name',
    )
    __slots__ = storable_attrs + (
        'vs_output', 'index', 'fps_num', 'fps_den', 'format', 'total_frames',
        'total_time', 'end_frame', 'end_time', 'fps', 'source_vs_output',
        'main', 'qformat', 'qoutput', 'iodevice', 'flags',
    )

    def __init__(self, vs_output: vs.AudioNode, index: int, new_storage: bool = False) -> None:
        self.main = main_window()
        self.index = index
        self.source_vs_output = vs_output
        self.vs_output = self.source_vs_output

        class AudioFormat:
            sample_type: vs.SampleType
            bits_per_sample: int
            bytes_per_sample: int
            channel_layout: int
            num_channels: int
            sample_rate: int
            num_samples: int
            samples_per_frame: int

        self.format = AudioFormat()
        self.format.num_samples = self.vs_output.num_samples
        self.format.sample_rate = self.vs_output.sample_rate
        self.format.samples_per_frame = self.SAMPLES_PER_FRAME
        self.format.bits_per_sample = self.vs_output.bits_per_sample
        self.format.bytes_per_sample = self.vs_output.bytes_per_sample
        self.format.num_channels = self.vs_output.num_channels
        self.format.sample_type = self.vs_output.sample_type
        self.format.channel_layout = self.vs_output.channel_layout

        if self.format.num_channels != 2:
            raise RuntimeError('Non-2-channel audio is not supported')

        self.qformat = QAudioFormat()
        self.qformat.setChannelCount(self.format.num_channels)
        self.qformat.setSampleRate(self.format.sample_rate)
        self.qformat.setSampleType(QAudioFormat.Float)
        self.qformat.setSampleSize(self.format.bits_per_sample)
        self.qformat.setByteOrder(QAudioFormat.LittleEndian)
        self.qformat.setCodec('audio/pcm')

        if not QAudioDeviceInfo(QAudioDeviceInfo.defaultOutputDevice()).isFormatSupported(self.qformat):
            raise RuntimeError('Audio format not supported')

        self.qoutput = QAudioOutput(self.qformat, self.main)
        self.qoutput.setBufferSize(self.format.bytes_per_sample * self.format.samples_per_frame * 5)
        self.iodevice = self.qoutput.start()

        self.fps_num = self.format.sample_rate
        self.fps_den = self.format.samples_per_frame
        self.fps = self.fps_num / self.fps_den
        self.total_frames = Frame(self.vs_output.num_frames)
        self.total_time = self.to_time(self.total_frames - Frame(1))
        self.end_frame = Frame(int(self.total_frames) - 1)
        self.end_time = self.to_time(self.end_frame)

        if not hasattr(self, 'name'):
            self.name = 'Audio Node ' + str(self.index)

    def clear(self) -> None:
        self.source_vs_output = self.vs_output = self.format = None  # type: ignore

    def render_audio_frame(self, frame: Frame) -> None:
        self.render_raw_audio_frame(self.vs_output.get_frame(int(frame)))  # R58

    def render_raw_audio_frame(self, vs_frame: vs.AudioFrame) -> None:
        ptr_type = ctypes.POINTER(ctypes.c_float * self.format.samples_per_frame)

        barray_l = bytes(ctypes.cast(vs_frame.get_read_ptr(0), ptr_type).contents)
        barray_r = bytes(ctypes.cast(vs_frame.get_read_ptr(1), ptr_type).contents)

        array_l = array('f', barray_l)
        array_r = array('f', barray_r)
        array_lr = array('f', array_l + array_r)

        array_lr[::2] = array_l
        array_lr[1::2] = array_r

        barray = bytes(array_lr.tobytes())

        self.iodevice.write(barray)

    def _calculate_frame(self, seconds: float) -> int:
        return floor(seconds * self.fps)

    def _calculate_seconds(self, frame_num: int) -> float:
        return frame_num / self.fps

    def to_frame(self, time: Time) -> Frame:
        return Frame(self._calculate_frame(float(time)))

    def to_time(self, frame: Frame) -> Time:
        return Time(seconds=self._calculate_seconds(int(frame)))

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self.storable_attrs
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'name', str, self.__setattr__)
