from __future__ import annotations

from array import array
from math import floor
from typing import Any, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtMultimedia import QAudioDevice, QAudioFormat, QAudioOutput, QAudioSink
from vstools import vs, CustomRuntimeError

from ..abstracts import AbstractYAMLObject, main_window, try_load
from .units import Frame, Time


class AudioOutput(AbstractYAMLObject):
    SAMPLES_PER_FRAME = 3072  # https://github.com/vapoursynth/vapoursynth/blob/master/include/VapourSynth4.h#L32

    storable_attrs = ('name', )

    __slots__ = (
        *storable_attrs, 'vs_output', 'index', 'fps_num', 'fps_den', 'format',
        'total_frames', 'total_time', 'end_frame', 'fps', 'is_mono',
        'source_vs_output', 'main', 'qformat', 'qoutput', 'iodevice', 'flags'
    )

    def __init__(self, vs_output: vs.AudioNode, index: int, new_storage: bool = False) -> None:
        self.setValue(vs_output, index, new_storage)

    def setValue(self, vs_output: vs.AudioNode, index: int, new_storage: bool = False) -> None:
        self.main = main_window()
        self.index = index
        self.source_vs_output = vs_output
        self.vs_output = self.source_vs_output
        self.is_mono = self.vs_output.num_channels == 1

        (self.arrayType, sampleTypeQ) = (
            'f', QAudioFormat.SampleFormat.Float
        ) if self.vs_output.sample_type == vs.FLOAT else (
            'I' if self.vs_output.bits_per_sample <= 16 else 'L', QAudioFormat.SampleFormat.Int16
        )

        sample_size = 8 * self.vs_output.bytes_per_sample

        self.qformat = QAudioFormat()
        self.qformat.setChannelCount(self.vs_output.num_channels)
        self.qformat.setSampleRate(self.vs_output.sample_rate)
        self.qformat.setSampleFormat(sampleTypeQ)
        # self.qformat.setSampleSize(sample_size)
        # self.qformat.setByteOrder(Qt.LittleEndian)
        # self.qformat.setCodec('audio/pcm')

        self.qoutput = QAudioOutput(self.main)

        if not self.qoutput.device().isFormatSupported(self.qformat):
            raise RuntimeError('Audio format not supported')

        self.qaudiosink = QAudioSink(self.qoutput.device(), self.qformat, self.main)
        self.qaudiosink.setBufferSize(sample_size * self.SAMPLES_PER_FRAME)

        self.iodevice = self.qaudiosink.start()

        if self.iodevice is None:
            raise CustomRuntimeError(
                'The current QT version has a bug for dll loading, you need to go into '
                'C:\\System32 and copy "mfplat.dll" into "mfplat.dll.dll".'
            )

        self.fps_num = self.vs_output.sample_rate
        self.fps_den = self.SAMPLES_PER_FRAME
        self.fps = self.fps_num / self.fps_den
        self.total_frames = Frame(self.vs_output.num_frames)
        self.total_time = self.to_time(self.total_frames - Frame(1))

        self.audio_buffer = array(self.arrayType, [0] * self.SAMPLES_PER_FRAME * (self.vs_output.bytes_per_sample // 2))

        if not hasattr(self, 'name'):
            from ...models.outputs import AudioOutputs

            if vs_output in (vs_outputs := list(vs.get_outputs().values())):
                self.name = self.main.user_output_names[vs.AudioNode].get(
                    vs_outputs.index(vs_output), 'Track ' + str(self.index)
                )
                if isinstance(self.main.toolbars.playback.audio_outputs, AudioOutputs):
                    self.main.toolbars.playback.audio_outputs.setData(
                        self.main.toolbars.playback.audio_outputs.index(index), self.name
                    )

    def clear(self) -> None:
        self.source_vs_output = self.vs_output = None  # type: ignore

    def render_audio_frame(self, frame: Frame) -> None:
        self.render_raw_audio_frame(self.vs_output.get_frame(int(frame)))

    def render_raw_audio_frame(self, vs_frame: vs.AudioFrame) -> None:
        if self.is_mono:
            self.iodevice.write(vs_frame[0].tobytes())
        else:
            self.audio_buffer[0::2] = array(self.arrayType, vs_frame[0].tobytes())
            self.audio_buffer[1::2] = array(self.arrayType, vs_frame[1].tobytes())

            self.iodevice.write(self.audio_buffer.tobytes())

    @property
    def volume(self) -> float:
        return self.qoutput.volume()

    @volume.setter
    def volume(self, newVolume: float) -> None:
        return self.qoutput.setVolume(newVolume)

    def _calculate_frame(self, seconds: float) -> int:
        return floor(seconds * self.fps)

    def _calculate_seconds(self, frame_num: int) -> float:
        return frame_num / self.fps

    def to_frame(self, time: Time) -> Frame:
        return Frame(self._calculate_frame(float(time)))

    def to_time(self, frame: Frame) -> Time:
        return Time(seconds=self._calculate_seconds(int(frame)))

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'name', str, self.__setattr__)
