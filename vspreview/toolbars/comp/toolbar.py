from __future__ import annotations

import os
import string
import random
import logging
import vapoursynth as vs
from pathlib import Path
from requests import Session
from functools import partial
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from typing import Any, Callable, Dict, Final, List, NamedTuple, Optional, Set, cast

from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QCheckBox, QPushButton, QComboBox, QProgressBar

from ...utils import set_qobject_names
from ...widgets import ComboBox, FrameEdit
from ...models import PictureTypes, VideoOutputs
from ...core import AbstractMainWindow, AbstractToolbar, PictureType, main_window

from .settings import CompSettings


_MAX_ATTEMPTS_PER_PICTURE_TYPE: Final[int] = 50


def select_frames(clip: vs.VideoNode, indices: List[int]) -> vs.VideoNode:
    return clip.std.BlankClip(length=len(indices)).std.FrameEval(lambda n: clip[indices[n]])


class WorkerConfiguration(NamedTuple):
    outputs: VideoOutputs
    collection_name: str
    public: bool
    nsfw: bool
    optimise: bool
    remove_after: Optional[int]
    frames: List[int]
    compression: int
    path: Path


class Worker(QObject):
    finished = pyqtSignal()
    progress_bar = pyqtSignal(int)
    progress_status = pyqtSignal(str, int, int)
    outputs: VideoOutputs

    is_finished = False

    def _progress_update_func(self, value: int, endvalue: int) -> None:
        if value == 0:
            self.progress_bar.emit(0)
        else:
            self.progress_bar.emit(int(100 * value / endvalue))

    def run(self, conf: WorkerConfiguration) -> None:
        self.conf = conf
        all_images: List[List[Path]] = []
        try:
            for i, output in enumerate(conf.outputs):
                if self.is_finished:
                    raise StopIteration
                self.progress_status.emit('extract', i + 1, len(conf.outputs))

                path_name = conf.path / output.name
                path_name.mkdir(parents=True)

                max_num = max(conf.frames)

                path_images = [
                    path_name / (f'{output.name}_' + f'{f}'.zfill(len("%i" % max_num)) + '.png')
                    for f in conf.frames
                ]

                def _save(n: int, f: vs.VideoFrame) -> vs.VideoFrame:
                    if self.is_finished:
                        raise StopIteration
                    QImage(cast(bytes, f[0]), f.width, f.height, QImage.Format_RGB32).save(
                        str(path_images[n]), 'PNG', conf.compression
                    )
                    return f

                decimated = select_frames(output.prepared.clip, conf.frames)
                clip = decimated.std.ModifyFrame(decimated, _save)

                with open(os.devnull, 'wb') as devnull:
                    clip.output(devnull, y4m=False, progress_update=self._progress_update_func)

                if self.is_finished:
                    raise StopIteration

                all_images.append(sorted(path_images))
        except StopIteration:
            return self.finished.emit('')

        fields: Dict[str, Any] = {}

        for i, (output, images) in enumerate(zip(conf.outputs, all_images)):
            if self.is_finished:
                return self.finished.emit('')
            for j, (image, frame) in enumerate(zip(images, conf.frames)):
                if self.is_finished:
                    return self.finished.emit('')  # type: ignore
                fields[f'comparisons[{j}].name'] = str(frame)
                fields[f'comparisons[{j}].images[{i}].name'] = output.name
                fields[f'comparisons[{j}].images[{i}].file'] = (image.name, image.read_bytes(), 'image/png')

        self.progress_status.emit('upload', 0, 0)

        with Session() as sess:
            sess.get('https://slow.pics/api/comparison')
            if self.is_finished:
                return self.finished.emit('')
            head_conf = {
                'collectionName': conf.collection_name,
                'public': str(conf.public).lower(),
                'optimizeImages': str(conf.optimise).lower(),
                'hentai': str(conf.nsfw).lower(),
            }
            if conf.remove_after is not None:
                head_conf |= {'removeAfter': str(conf.remove_after)}

            def _monitor_cb(monitor: MultipartEncoderMonitor) -> None:
                self._progress_update_func(monitor.bytes_read, monitor.len)

            files = MultipartEncoder(head_conf | fields)
            monitor = MultipartEncoderMonitor(files, _monitor_cb)

            response = sess.post(
                'https://slow.pics/api/comparison',
                monitor.to_string(),  # type: ignore
                headers={
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Content-Length": str(files.len),
                    "Content-Type": files.content_type,
                    "Origin": "https://slow.pics/",
                    "Referer": "https://slow.pics/comparison",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    ),
                    "X-XSRF-TOKEN": sess.cookies.get_dict()["XSRF-TOKEN"]  # noqa
                }
            )

        self.progress_status.emit(f'https://slow.pics/c/{response.text}', 0, 0)
        self.finished.emit()


class CompToolbar(AbstractToolbar):
    _thread_running = False

    __slots__ = (
        'random_frames_control', 'manual_frames_lineedit',
        'current_frame_checkbox', 'is_public_checkbox', 'is_nsfw_checkbox',
        'output_url_lineedit', 'output_url_copy_button', 'start_upload_button', 'stop_upload_button',
        'upload_progressbar', 'upload_status_label', 'upload_status_elements'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, CompSettings())
        self.setup_ui()

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        random_frames_label = QLabel('Num Random Frames:', self)
        layout.addWidget(random_frames_label)

        self.random_frames_control = FrameEdit(self)
        layout.addWidget(self.random_frames_control)

        manual_frames_label = QLabel('Additional Frames:', self)
        layout.addWidget(manual_frames_label)

        self.manual_frames_lineedit = QLineEdit(self)
        self.manual_frames_lineedit.setPlaceholderText('frame,frame,frame')
        layout.addWidget(self.manual_frames_lineedit)

        self.current_frame_checkbox = QCheckBox('Current Frame', self)
        self.current_frame_checkbox.setChecked(True)
        layout.addWidget(self.current_frame_checkbox)

        layout.addWidget(self.get_separator())

        picture_type_label = QLabel('Filter per Picture Type:', self)
        layout.addWidget(picture_type_label)

        self.pic_type_combox = ComboBox[PictureType](self)
        self.pic_type_combox.setModel(PictureTypes())
        self.pic_type_combox.setEditable(True)
        self.pic_type_combox.setInsertPolicy(QComboBox.InsertAtCurrent)
        self.pic_type_combox.setDuplicatesEnabled(True)
        self.pic_type_combox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.pic_type_combox.view().setMinimumWidth(self.pic_type_combox.minimumSizeHint().width())
        temp_width = self.pic_type_combox.minimumSizeHint().width()
        self.pic_type_combox.setMinimumWidth(temp_width + temp_width // 10)
        self.pic_type_combox.setCurrentIndex(0)
        layout.addWidget(self.pic_type_combox)

        layout.addWidget(self.get_separator())

        self.is_public_checkbox = QCheckBox('Public', self)
        self.is_public_checkbox.setChecked(True)
        layout.addWidget(self.is_public_checkbox)

        self.is_nsfw_checkbox = QCheckBox('NSFW', self)
        self.is_nsfw_checkbox.setChecked(False)
        layout.addWidget(self.is_nsfw_checkbox)

        layout.addWidget(self.get_separator())

        self.output_url_lineedit = QLineEdit('https://slow.pics/c/', self)
        self.output_url_lineedit.setEnabled(False)
        layout.addWidget(self.output_url_lineedit)

        self.output_url_copy_button = QPushButton(self)
        self.output_url_copy_button.clicked.connect(self.on_copy_output_url_clicked)
        self.output_url_copy_button.setText('⎘')
        layout.addWidget(self.output_url_copy_button)

        self.start_upload_button = QPushButton('Upload to slow.pics', self)
        self.start_upload_button.clicked.connect(self.on_start_upload)
        layout.addWidget(self.start_upload_button)

        self.stop_upload_button = QPushButton('Stop Uploading', self)
        self.stop_upload_button.clicked.connect(self.on_stop_upload)
        self.stop_upload_button.setVisible(False)
        layout.addWidget(self.stop_upload_button)

        upload_separator = self.get_separator()

        layout.addWidget(upload_separator)

        self.upload_progressbar = QProgressBar(self)
        self.upload_progressbar.setGeometry(200, 80, 250, 20)
        self.upload_progressbar.setValue(0)
        layout.addWidget(self.upload_progressbar)

        self.upload_status_label = QLabel(self)
        layout.addWidget(self.upload_status_label)

        self.update_status_label('extract')

        self.upload_status_elements = (
            upload_separator, self.upload_progressbar,
            self.upload_status_label
        )

        self.update_upload_status_visibility(False)

        layout.addStretch()
        layout.addStretch()

    def on_copy_output_url_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(self.output_url_lineedit.text())
        self.main.show_message('Slow.pics URL copied to clipboard')

    def update_upload_status_visibility(self, visible: bool) -> None:
        for element in self.upload_status_elements:
            element.setVisible(visible)

    def on_start_upload(self) -> None:
        if self._thread_running:
            return
        self.start_upload_button.setVisible(False)
        self.stop_upload_button.setVisible(True)
        self.upload_to_slowpics()

    def on_end_upload(self, forced: bool = False) -> None:
        self.start_upload_button.setVisible(True)
        self.stop_upload_button.setVisible(False)
        self._thread_running = False
        self.upload_thread.deleteLater()

        if forced:
            self.upload_status_label.setText("Stopped!")
        else:
            self.upload_status_label.setText("Finished!")

    def on_stop_upload(self) -> None:
        self.upload_worker.is_finished = True

        self.on_end_upload(forced=True)

    def update_status_label(self, kind: str, curr: int | None = None, total: int | None = None) -> None:
        message = ''

        moreinfo = f" {curr or '?'}/{total or '?'} " if curr or total else ''

        if kind == 'extract':
            message = 'Extracting'
        elif kind == 'upload':
            message = 'Uploading'
        elif kind == 'search':
            message = 'Searching'
        else:
            return self.output_url_lineedit.setText(kind)

        self.upload_status_label.setText(f'{message}{moreinfo}...')

    def _rand_num_frames(self, checked: Set[int], rand_func: Callable[[], int]) -> int:
        rnum = rand_func()
        while rnum in checked:
            rnum = rand_func()
        return rnum

    def _select_samples_ptypes(self, num_frames: int, k: int, picture_type: PictureType) -> List[int]:
        samples: Set[int] = set()
        _max_attempts = 0
        _rnum_checked: Set[int] = set()
        while len(samples) < k:
            _attempts = 0
            while True:
                self.update_status_label('search', _attempts, _MAX_ATTEMPTS_PER_PICTURE_TYPE)
                if len(_rnum_checked) >= num_frames:
                    raise ValueError(f'There aren\'t enough of {picture_type} in these clips')
                rnum = self._rand_num_frames(_rnum_checked, partial(random.randrange, start=0, stop=num_frames))
                _rnum_checked.add(rnum)

                if all(
                    f.props['_PictType'].decode('utf-8') == str(picture_type)[0]
                    for f in vs.core.std.Splice(
                        [select_frames(out.prepared.clip, [rnum]) for out in self.main.outputs], True
                    ).frames()
                ):
                    break

                _attempts += 1
                _max_attempts += 1

                if _attempts > _MAX_ATTEMPTS_PER_PICTURE_TYPE:
                    logging.warning(
                        f'{_MAX_ATTEMPTS_PER_PICTURE_TYPE} attempts were made for sample {len(samples)} '
                        f'and no match found for {picture_type}; stopping iteration...')
                    break

            if _max_attempts > (curr_max_att := _MAX_ATTEMPTS_PER_PICTURE_TYPE * k):
                raise RecursionError(f'Comp: attempts max of {curr_max_att} has been reached!')

            if _attempts < _MAX_ATTEMPTS_PER_PICTURE_TYPE:
                samples.add(rnum)
                self.upload_progressbar.setValue(int())
                self.upload_progressbar.setValue(int(100 * len(samples) / k))

        return list(samples)

    def get_slowpics_conf(self) -> WorkerConfiguration:
        self.update_upload_status_visibility(True)

        clips: Dict[str, vs.VideoNode]
        num = int(self.random_frames_control.value())
        frames: List[int] = list(
            map(int, filter(None, [x.strip() for x in self.manual_frames_lineedit.text().split(',')]))
        )
        picture_type = self.pic_type_combox.currentData()

        lens = set(out.prepared.clip.num_frames for out in self.main.outputs)

        if len(lens) != 1:
            logging.warning('Outputted clips don\'t all have the same length!')

        lens_n = min(lens)

        path = Path(main_window().config_dir) / ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

        path.mkdir(parents=True)

        if num:
            if picture_type is PictureType.UNSET:
                samples = random.sample(range(lens_n), num)
            else:
                logging.info('Making samples according to specified picture types...')
                samples = self._select_samples_ptypes(lens_n, num, picture_type)
        else:
            samples = []

        if len(frames):
            samples.extend(frames)

        if self.current_frame_checkbox.isChecked():
            samples.append(int(self.main.current_frame))

        return WorkerConfiguration(
            self.main.outputs, 'Function Test',
            self.is_public_checkbox.isChecked(), self.is_nsfw_checkbox.isChecked(),
            True, None, sorted(set(samples)), -1, path
        )

    def upload_to_slowpics(self) -> None:
        self.upload_thread = QThread()

        self.upload_worker = Worker()

        self.upload_worker.moveToThread(self.upload_thread)

        self.upload_thread.started.connect(
            partial(self.upload_worker.run, conf=self.get_slowpics_conf())
        )
        self.upload_worker.finished.connect(self.upload_thread.quit)
        self.upload_worker.finished.connect(self.upload_worker.deleteLater)
        self.upload_thread.finished.connect(self.on_end_upload)
        self.upload_worker.progress_bar.connect(self.upload_progressbar.setValue)
        self.upload_worker.progress_status.connect(self.update_status_label)

        self.upload_thread.start()
        self._thread_running = True
