from __future__ import annotations

import logging
import os
import random
import re
import shutil
import string
import unicodedata
from functools import partial
from pathlib import Path
from typing import Any, Callable, Final, NamedTuple, cast

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLabel
from vstools import vs

from ...core import (
    AbstractMainWindow, AbstractToolbar, CheckBox, LineEdit, PictureType, ProgressBar, PushButton, main_window
)
from ...core.custom import ComboBox, FrameEdit
from ...models import PictureTypes, VideoOutputs
from .settings import CompSettings

_MAX_ATTEMPTS_PER_PICTURE_TYPE: Final[int] = 50


def select_frames(clip: vs.VideoNode, indices: list[int]) -> vs.VideoNode:
    return clip.std.BlankClip(length=len(indices)).std.FrameEval(lambda n: clip[indices[n]])


def clear_filename(filename: str) -> str:
    blacklist = ['\\', '/', ':', '*', '?', '\'', '<', '>', '|', '\0']
    reserved = [
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
        'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
        'LPT6', 'LPT7', 'LPT8', 'LPT9',
    ]

    filename = ''.join(c for c in filename if c not in blacklist)

    # Remove all charcters below code point 32
    filename = ''.join(c for c in filename if 31 < ord(c))
    filename = unicodedata.normalize('NFKD', filename).rstrip('. ').strip()

    if all([x == '.' for x in filename]):
        filename = '__' + filename

    if filename in reserved:
        filename = '__' + filename

    if len(filename) > 255:
        parts = re.split(r'/|\\', filename)[-1].split('.')

        if len(parts) > 1:
            ext = '.' + parts.pop()
            filename = filename[:-len(ext)]
        else:
            ext = ''
        if filename == '':
            filename = '__'

        if len(ext) > 254:
            ext = ext[254:]

        maxl = 255 - len(ext)
        filename = filename[:maxl]
        filename = filename + ext

        # Re-check last character (if there was no extension)
        filename = filename.rstrip('. ')

    return filename


class WorkerConfiguration(NamedTuple):
    outputs: VideoOutputs
    collection_name: str
    public: bool
    nsfw: bool
    optimise: bool
    remove_after: int | None
    frames: list[int]
    compression: int
    path: Path
    main: AbstractMainWindow
    delete_cache: bool


class Worker(QObject):
    finished = pyqtSignal()
    progress_bar = pyqtSignal(int)
    progress_status = pyqtSignal(str, int, int)

    is_finished = False

    def _progress_update_func(self, value: int, endvalue: int) -> None:
        if value == 0:
            self.progress_bar.emit(0)
        else:
            self.progress_bar.emit(int(100 * value / endvalue))

    def isFinished(self) -> bool:
        return self.is_finished

    def run(self, conf: WorkerConfiguration) -> None:
        try:
            from requests import Session
            from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                'You are missing `requests` and `requests` toolbelt!\n'
                'Install them with "pip install requests requests_toolbelt"!'
            )

        all_images = list[list[Path]]()
        conf.path.mkdir(parents=True, exist_ok=False)

        try:
            for i, output in enumerate(conf.outputs):
                if self.isFinished():
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
                    if self.isFinished():
                        raise StopIteration
                    conf.main.current_output.frame_to_qimage(f).save(
                        str(path_images[n]), 'PNG', conf.compression
                    )
                    return f

                decimated = select_frames(output.prepared.clip, conf.frames)
                clip = decimated.std.ModifyFrame(decimated, _save)

                with open(os.devnull, 'wb') as devnull:
                    clip.output(devnull, y4m=False, progress_update=self._progress_update_func)

                if self.isFinished():
                    raise StopIteration

                all_images.append(sorted(path_images))
        except StopIteration:
            return self.finished.emit()

        fields = dict[str, Any]()

        for i, (output, images) in enumerate(zip(conf.outputs, all_images)):
            if self.isFinished():
                return self.finished.emit()
            for j, (image, frame) in enumerate(zip(images, conf.frames)):
                if self.isFinished():
                    return self.finished.emit()
                fields[f'comparisons[{j}].name'] = str(frame)
                fields[f'comparisons[{j}].images[{i}].name'] = output.name
                fields[f'comparisons[{j}].images[{i}].file'] = (image.name, image.read_bytes(), 'image/png')

        self.progress_status.emit('upload', 0, 0)

        with Session() as sess:
            sess.get('https://slow.pics/api/comparison')
            if self.isFinished():
                return self.finished.emit()
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
                cast(bytes, monitor.to_string()),
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

        if conf.delete_cache:
            shutil.rmtree(conf.path, True)

        url = f'https://slow.pics/c/{response.text}'

        self.progress_status.emit(url, 0, 0)

        url_out = (
            conf.path.parent / 'Old Comps'
            / clear_filename(f'{conf.collection_name} - {response.text}')
        ).with_suffix('.url')
        url_out.parent.mkdir(parents=True, exist_ok=True)
        url_out.touch(exist_ok=True)
        url_out.write_text(f'[InternetShortcut]\nURL={url}')

        self.finished.emit()


class CompToolbar(AbstractToolbar):
    _thread_running = False

    __slots__ = (
        'random_frames_control', 'manual_frames_lineedit', 'output_url_lineedit',
        'current_frame_checkbox', 'is_public_checkbox', 'is_nsfw_checkbox',
        'output_url_copy_button', 'start_upload_button', 'stop_upload_button',
        'upload_progressbar', 'upload_status_label', 'upload_status_elements'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, CompSettings())
        self.setup_ui()

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.collection_name_lineedit = LineEdit(self, placeholderText='Collection name')

        self.random_frames_control = FrameEdit(self)

        self.manual_frames_lineedit = LineEdit(self, placeholderText='frame,frame,frame')

        self.current_frame_checkbox = CheckBox('Current', self, checked=True)

        self.pic_type_combox = ComboBox[PictureType](
            self, model=PictureTypes(), editable=True, insertPolicy=QComboBox.InsertPolicy.InsertAtCurrent,
            duplicatesEnabled=True, sizeAdjustPolicy=QComboBox.SizeAdjustPolicy.AdjustToContents, currentIndex=0
        )

        self.pic_type_combox.view().setMinimumWidth(self.pic_type_combox.minimumSizeHint().width())
        temp_width = self.pic_type_combox.minimumSizeHint().width()
        self.pic_type_combox.setMinimumWidth(temp_width + temp_width // 10)

        self.is_public_checkbox = CheckBox('Public', self, checked=True)

        self.is_nsfw_checkbox = CheckBox('NSFW', self, checked=False)

        self.output_url_lineedit = LineEdit('https://slow.pics/c/', self, enabled=False)

        self.output_url_copy_button = PushButton('⎘', self, clicked=self.on_copy_output_url_clicked)

        self.start_upload_button = PushButton('Start Upload', self, clicked=self.on_start_upload)

        self.stop_upload_button = PushButton('Stop Upload', self, visible=False, clicked=self.on_stop_upload)

        self.upload_progressbar = ProgressBar(self, value=0)
        self.upload_progressbar.setGeometry(200, 80, 250, 20)

        self.upload_status_label = QLabel(self)

        self.upload_status_elements = (
            self.get_separator(), self.upload_progressbar, self.upload_status_label
        )

        self.hlayout.addWidgets([
            self.collection_name_lineedit,
            QLabel('Random:'), self.random_frames_control,
            QLabel('Manual:'), self.manual_frames_lineedit,
            self.current_frame_checkbox,
            self.get_separator(),
            QLabel('Picture Type:'), self.pic_type_combox,
            self.get_separator(),
            self.is_public_checkbox,
            self.is_nsfw_checkbox,
            self.get_separator(),
            self.output_url_lineedit,
            self.output_url_copy_button,
            self.start_upload_button,
            self.stop_upload_button,
            *self.upload_status_elements
        ])

        self.update_status_label('extract')

        self.update_upload_status_visibility(False)

    def on_copy_output_url_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(self.output_url_lineedit.text())
        self.main.show_message('Slow.pics URL copied to clipboard!')

    def update_upload_status_visibility(self, visible: bool) -> None:
        for element in self.upload_status_elements:
            element.setVisible(visible)

    def on_start_upload(self) -> None:
        if self._thread_running:
            return
        if not self.upload_to_slowpics():
            return
        self.start_upload_button.setVisible(False)
        self.stop_upload_button.setVisible(True)

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

    def _rand_num_frames(self, checked: set[int], rand_func: Callable[[], int]) -> int:
        rnum = rand_func()
        while rnum in checked:
            rnum = rand_func()
        return rnum

    def _select_samples_ptypes(self, num_frames: int, k: int, picture_type: PictureType) -> list[int]:
        samples = set[int]()
        _max_attempts = 0
        _rnum_checked = set[int]()
        while len(samples) < k:
            _attempts = 0
            while True:
                self.update_status_label('search', _attempts, _MAX_ATTEMPTS_PER_PICTURE_TYPE)
                if len(_rnum_checked) >= num_frames:
                    raise ValueError(f'There aren\'t enough of {picture_type} in these clips')
                rnum = self._rand_num_frames(_rnum_checked, partial(random.randrange, start=0, stop=num_frames))
                _rnum_checked.add(rnum)

                if all(
                    cast(bytes, f.props['_PictType']).decode('utf-8') == str(picture_type)[0]
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

        clips: dict[str, vs.VideoNode]
        num = int(self.random_frames_control.value())
        frames = list[int](
            map(int, filter(None, [x.strip() for x in self.manual_frames_lineedit.text().split(',')]))
        )
        picture_type = self.pic_type_combox.currentData()

        lens = set(out.prepared.clip.num_frames for out in self.main.outputs)

        if len(lens) != 1:
            logging.warning('Outputted clips don\'t all have the same length!')

        lens_n = min(lens)

        path = Path(main_window().current_config_dir) / ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=16)
        )

        if num:
            if picture_type is PictureType.ALL:
                samples = random.sample(range(lens_n), num)
            else:
                logging.info('Making samples according to specified picture types...')
                samples = self._select_samples_ptypes(lens_n, num, picture_type)
        else:
            samples = []

        if len(frames):
            samples.extend(frames)

        if self.current_frame_checkbox.isChecked():
            samples.append(int(self.main.current_output.last_showed_frame))

        collection_name = self.collection_name_lineedit.text()

        if not collection_name:
            collection_name = self.settings.DEFAULT_COLLECTION_NAME

        if not collection_name:
            raise ValueError('You have to put a collection name!')

        collection_name = collection_name.format(
            script_name=self.main.script_path.stem
        )

        sample_frames = list(sorted(set(samples)))

        check_frame = sample_frames and sample_frames[0] or 0

        filtered_outputs = []

        for output in self.main.outputs:
            props = output.props

            if not props:
                props = output.source.clip.get_frame(check_frame).props

            if '_VSPDisableComp' in props and props._DisableComp == 1:
                continue

            filtered_outputs.append(output)

        return WorkerConfiguration(
            filtered_outputs, collection_name,
            self.is_public_checkbox.isChecked(), self.is_nsfw_checkbox.isChecked(),
            True, None, sample_frames, -1, path, self.main, self.settings.delete_cache_enabled
        )

    def upload_to_slowpics(self) -> bool:
        try:
            self.main.current_output.graphics_scene_item.setPixmap(
                self.main.current_output.graphics_scene_item.pixmap().copy()
            )

            config = self.get_slowpics_conf()

            self.upload_thread = QThread()

            self.upload_worker = Worker()

            self.upload_worker.moveToThread(self.upload_thread)

            self.upload_thread.started.connect(partial(self.upload_worker.run, config))
            self.upload_thread.finished.connect(self.on_end_upload)

            self.upload_worker.finished.connect(self.upload_thread.quit)
            self.upload_worker.finished.connect(self.upload_worker.deleteLater)

            self.upload_worker.progress_bar.connect(self.upload_progressbar.setValue)
            self.upload_worker.progress_status.connect(self.update_status_label)

            self.upload_thread.start()

            self._thread_running = True

            return True
        except BaseException as e:
            self.main.show_message(str(e))

        return False
