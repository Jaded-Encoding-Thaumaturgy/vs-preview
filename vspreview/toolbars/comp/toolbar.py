from __future__ import annotations

import logging
import random
import re
import shutil
import string
import unicodedata
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Final, Mapping, NamedTuple, cast
from uuid import uuid4

import requests
from PyQt6 import QtCore
from PyQt6.QtCore import QKeyCombination, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QLabel
from requests import HTTPError, Session
from requests_toolbelt import MultipartEncoder  # type: ignore
from requests_toolbelt import MultipartEncoderMonitor
from vstools import remap_frames, vs, get_prop

from ...core import (
    AbstractToolbar, CheckBox, ComboBox, Frame, FrameEdit, HBoxLayout, LineEdit, ProgressBar, PushButton, VBoxLayout,
    VideoOutput, main_window, try_load
)
from ...models import GeneralModel
from .settings import CompSettings

if TYPE_CHECKING:
    from ...main import MainWindow


__all__ = [
    'CompToolbar'
]


_MAX_ATTEMPTS_PER_PICTURE_TYPE: Final[int] = 50


def _get_slowpic_headers(content_length: int, content_type: str, sess: Session) -> dict[str, str]:
    return {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9',
        'Access-Control-Allow-Origin': '*',
        'Content-Length': str(content_length),
        'Content-Type': content_type,
        'Origin': 'https://slow.pics/',
        'Referer': 'https://slow.pics/comparison',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        ),
        'X-XSRF-TOKEN': sess.cookies.get('XSRF-TOKEN')
    }


def _do_single_slowpic_upload(sess: Session, collection: str, imageUuid: str, image: Path, browser_id: str) -> None:
    upload_info = MultipartEncoder({
        'collectionUuid': collection,
        'imageUuid': imageUuid,
        'file': (image.name, image.read_bytes(), 'image/png'),
        'browserId': browser_id,
    }, str(uuid4()))

    while True:
        try:
            req = sess.post(
                'https://slow.pics/upload/image', data=upload_info.to_string(),
                headers=_get_slowpic_headers(upload_info.len, upload_info.content_type, sess)
            )

            req.raise_for_status()
            break
        except HTTPError as e:
            logging.debug(e)


def clear_filename(filename: str) -> str:
    blacklist = ['\\', '/', ':', '*', '?', '\'', '<', '>', '|', '\0']
    reserved = [
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
        'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
        'LPT6', 'LPT7', 'LPT8', 'LPT9',
    ]

    filename = ''.join(c for c in filename if c not in blacklist)

    # Remove all characters below code point 32
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
    uuid: str
    outputs: list[VideoOutput]
    collection_name: str
    public: bool
    nsfw: bool
    optimise: bool
    remove_after: str | None
    frames: list[list[int]]
    compression: int
    path: Path
    main: MainWindow
    delete_cache: bool
    frame_type: bool
    browser_id: str
    session_id: str
    tmdb: str
    tags: list[str]


class Worker(QObject):
    finished = pyqtSignal(str)
    progress_bar = pyqtSignal(str, int)
    progress_status = pyqtSignal(str, str, int, int)

    is_finished = False

    def _progress_update_func(self, value: int, endvalue: int, *, uuid: str) -> None:
        if value == 0:
            self.progress_bar.emit(uuid, 0)
        else:
            self.progress_bar.emit(uuid, int(100 * value / endvalue))

    def isFinished(self) -> bool:
        if self.is_finished:
            self.deleteLater()
        return self.is_finished

    def run(self, conf: WorkerConfiguration) -> None:
        all_images = list[list[Path]]()
        all_image_types = list[list[str]]()
        conf.path.mkdir(parents=True, exist_ok=False)

        if conf.browser_id and conf.session_id:
            with Session() as sess:
                sess.cookies.set('SLP-SESSION', conf.session_id, domain='slow.pics')
                browser_id = conf.browser_id
                base_page = sess.get('https://slow.pics/comparison')
                if base_page.text.find('id="logoutBtn"') == -1:
                    self.progress_status.emit(conf.uuid, 'Session Expired', 0, 0)
                    return

        try:
            for i, output in enumerate(conf.outputs):
                if self.isFinished():
                    raise StopIteration
                self.progress_status.emit(conf.uuid, 'extract', i + 1, len(conf.outputs))

                folder_name = str(uuid4())
                path_name = conf.path / folder_name
                path_name.mkdir(parents=True)

                max_num = max(conf.frames[i])
                len_num = len(conf.frames[i])
                image_types = []

                if hasattr(vs.core, "fpng"):
                    path_images = [
                        path_name / (f'{folder_name}_{f}.png')
                        for f in conf.frames[i]
                    ]

                    clip = output.prepare_vs_output(output.source.clip, is_comp=True)
                    clip = vs.core.fpng.Write(clip, filename=path_name / f'{folder_name}_%d.png', compression=1)

                    decimated = remap_frames(clip, conf.frames[i])
                    for j, f in enumerate(decimated.frames(close=True)):
                        if self.isFinished():
                            raise StopIteration
                        image_types.append(get_prop(f.props, '_PictType', str, None, '?'))
                        self._progress_update_func(j + 1, len_num, uuid=conf.uuid)
                else:
                    path_images = [
                        path_name / (f'{folder_name}_' + f'{f}'.zfill(len('%i' % max_num)) + '.png')
                        for f in conf.frames[i]
                    ]

                    decimated = remap_frames(output.prepared.clip, conf.frames[i])

                    for i, f in enumerate(decimated.frames(close=True)):
                        if self.isFinished():
                            raise StopIteration

                        image_types.append(get_prop(f.props, '_PictType', str, None, '?'))

                        conf.main.current_output.frame_to_qimage(f).save(
                            str(path_images[i]), 'PNG', conf.compression
                        )

                        self._progress_update_func(i + 1, decimated.num_frames, uuid=conf.uuid)

                if self.isFinished():
                    raise StopIteration

                all_images.append(path_images)
                all_image_types.append(image_types)
        except StopIteration:
            return self.finished.emit(conf.uuid)
        except vs.Error as e:
            if 'raise StopIteration' in str(e):
                return self.finished.emit(conf.uuid)
            raise e

        total_images = 0
        fields = dict[str, Any]()
        for i, (output, images) in enumerate(zip(conf.outputs, all_images)):
            if self.isFinished():
                return self.finished.emit(conf.uuid)
            for j, (image, frame) in enumerate(zip(images, conf.frames[i])):
                if self.isFinished():
                    return self.finished.emit(conf.uuid)
                fields[f'comparisons[{j}].name'] = str(frame)
                fields[f'comparisons[{j}].imageNames[{i}]'] = (f'({all_image_types[i][j]}) ' if conf.frame_type else '') + f'{output.name}'
                total_images += 1

        self.progress_status.emit(conf.uuid, 'upload', 0, 0)

        with Session() as sess:
            if conf.browser_id and conf.session_id:
                sess.cookies.set('SLP-SESSION', conf.session_id, domain='slow.pics')
                browser_id = conf.browser_id
                check_session = True
            else:
                browser_id = str(uuid4())
                check_session = False

            base_page = sess.get('https://slow.pics/comparison')
            if self.isFinished():
                return self.finished.emit(conf.uuid)

            if check_session:
                if base_page.text.find('id="logoutBtn"') == -1:
                    self.progress_status.emit(conf.uuid, 'Session Expired', 0, 0)
                    return

            head_conf = {
                'collectionName': conf.collection_name,
                'hentai': str(conf.nsfw).lower(),
                'optimizeImages': str(conf.optimise).lower(),
                'browserId': browser_id,
                'public': str(conf.public).lower(),
            }
            if conf.remove_after is not None:
                head_conf |= {'removeAfter': str(conf.remove_after)}

            if conf.tmdb:
                head_conf |= {'tmdbId': conf.tmdb}

            if conf.public and conf.tags:
                head_conf |= {f'tags[{index}]': tag for index, tag in enumerate(conf.tags)}

            def _monitor_cb(monitor: MultipartEncoderMonitor) -> None:
                self._progress_update_func(monitor.bytes_read, monitor.len, uuid=conf.uuid)
            files = MultipartEncoder(head_conf | fields, str(uuid4()))
            monitor = MultipartEncoderMonitor(files, _monitor_cb)
            comp_response = sess.post(
                'https://slow.pics/upload/comparison', data=monitor.to_string(),
                headers=_get_slowpic_headers(monitor.len, monitor.content_type, sess)
            ).json()
            collection = comp_response['collectionUuid']
            key = comp_response['key']
            image_ids = comp_response['images']
            images_done = 0
            self._progress_update_func(0, total_images, uuid=conf.uuid)
            with ThreadPoolExecutor() as executor:
                futures = list[Future[None]]()

                for i, (output, images) in enumerate(zip(conf.outputs, all_images)):
                    if self.isFinished():
                        return self.finished.emit(conf.uuid)
                    for j, (image, frame) in enumerate(zip(images, conf.frames[i])):
                        if self.isFinished():
                            return self.finished.emit(conf.uuid)
                        while len(futures) >= 5:
                            if self.isFinished():
                                return self.finished.emit(conf.uuid)
                            for future in futures.copy():
                                if self.isFinished():
                                    return self.finished.emit(conf.uuid)
                                if future.done():
                                    futures.remove(future)
                                    images_done += 1
                                    self._progress_update_func(
                                        images_done, total_images, uuid=conf.uuid
                                    )

                        futures.append(
                            executor.submit(
                                _do_single_slowpic_upload,
                                sess=sess, collection=collection, imageUuid=image_ids[j][i],
                                image=image, browser_id=browser_id
                            )
                        )
            self._progress_update_func(total_images, total_images, uuid=conf.uuid)
        if conf.delete_cache:
            shutil.rmtree(conf.path, True)

        url = f'https://slow.pics/c/{key}'

        self.progress_status.emit(conf.uuid, url, 0, 0)

        url_out = (
            conf.path.parent / 'Old Comps' / clear_filename(f'{conf.collection_name} - {key}')
        ).with_suffix('.url')
        url_out.parent.mkdir(parents=True, exist_ok=True)
        url_out.touch(exist_ok=True)
        url_out.write_text(f'[InternetShortcut]\nURL={url}')

        self.finished.emit(conf.uuid)


class CompToolbar(AbstractToolbar):
    _thread_running = False

    __slots__ = (
        'random_frames_control', 'manual_frames_lineedit', 'output_url_lineedit',
        'current_frame_checkbox', 'is_public_checkbox', 'is_nsfw_checkbox',
        'output_url_copy_button', 'start_upload_button', 'stop_upload_button',
        'upload_progressbar', 'upload_status_label', 'upload_status_elements'
    )

    settings: CompSettings

    upload_thread: QThread
    upload_worker: Worker

    pic_type_button_I: CheckBox
    pic_type_button_P: CheckBox
    pic_type_button_B: CheckBox

    tag_add_button: PushButton
    tag_add_custom_button: PushButton

    tag_filter_lineedit: LineEdit
    tmdb_id_lineedit: LineEdit

    tag_list_combox: ComboBox[str]

    tag_separator: QFrame

    tag_data: dict[str, str]
    current_tags: list[str]

    tag_data_cache: dict[str, str] | None
    tag_data_error: bool

    collection_name_cache: str | None

    curr_uuid = ''
    tmdb_data = dict[str, dict[str, Any]]()

    _old_threads_workers = list[Any]()

    KEYWORD_RE = re.compile(r'\{[a-z0-9_-]+\}', flags=re.IGNORECASE)

    def __init__(self, main: MainWindow) -> None:
        super().__init__(main, CompSettings(self))

        self.setup_ui()

        self.set_qobject_names()

        self.add_shortcuts()

        self.tag_data_cache = None
        self.tag_data_error = False

    def _force_clicked(self, self_s: str) -> Callable[[bool], None]:
        def _on_clicked(is_checked: bool) -> None:
            if self_s == 'I':
                el = self.pic_type_button_I
                oth = (self.pic_type_button_P, self.pic_type_button_B)
            elif self_s == 'P':
                el = self.pic_type_button_P
                oth = (self.pic_type_button_I, self.pic_type_button_B)
            else:
                el = self.pic_type_button_B
                oth = (self.pic_type_button_I, self.pic_type_button_P)

            if not is_checked and not any(o.isChecked() for o in oth):
                el.click()

        return _on_clicked

    def _select_filter_text(self, text: str) -> None:
        if text:
            if text in self.current_tags:
                self.tag_add_custom_button.setText('Remove Tag')
            else:
                self.tag_add_custom_button.setText('Add Tag')

            index = self.tag_list_combox.findText(text, QtCore.Qt.MatchFlag.MatchContains)

            if index < 0:
                return

            self.tag_list_combox.setCurrentIndex(
                index
            )

    def _handle_current_combox_tag(self) -> None:
        value = self.tag_list_combox.currentValue()

        if value in self.current_tags:
            self.current_tags.remove(value)
            self.tag_add_button.setText('Add Tag')
        else:
            self.current_tags.append(value)
            self.tag_add_button.setText('Remove Tag')

    def _handle_current_new_tag(self) -> None:
        value = self.tag_filter_lineedit.text()

        if value in self.current_tags:
            self.current_tags.remove(value)
            self.tag_add_custom_button.setText('Add Tag')
        else:
            self.current_tags.append(value)
            self.tag_add_custom_button.setText('Remove Tag')

    def _handle_tag_index(self, index: int) -> None:
        value = self.tag_list_combox.currentValue()

        if value in self.current_tags:
            self.tag_add_button.setText('Remove Tag')
        else:
            self.tag_add_button.setText('Add Tag')

    def _public_click(self, is_checked: bool) -> None:
        self.tag_add_button.setHidden(not is_checked)
        self.tag_add_custom_button.setHidden(not is_checked)
        self.tag_filter_lineedit.setHidden(not is_checked)
        self.tag_list_combox.setHidden(not is_checked)
        self.tag_separator.setHidden(not is_checked)
        self.on_public_toggle(is_checked)

    def _handle_collection_name_down(self) -> None:
        self.collection_name_cache = self.collection_name_lineedit.text()
        self.collection_name_lineedit.setText(self._handle_collection_generate())

    def _handle_collection_name_up(self) -> None:
        if self.collection_name_cache is not None:
            self.collection_name_lineedit.setText(self.collection_name_cache)
            self.collection_name_cache = None

    def setup_ui(self) -> None:
        super().setup_ui()

        self.collection_name_lineedit = LineEdit('Collection name', self)

        self.random_frames_control = FrameEdit(self)

        self.manual_frames_lineedit = LineEdit('Manual frames: frame,frame,frame', self, )

        self.current_frame_checkbox = CheckBox('Current frame', self, checked=True)

        self.collection_name_cache = None

        self.collection_name_button = PushButton(
            '🛈', self, pressed=self._handle_collection_name_down, released=self._handle_collection_name_up
        )

        self.pic_type_button_I = CheckBox('I', self, checked=True, clicked=self._force_clicked('I'))
        self.pic_type_button_P = CheckBox('P', self, checked=True, clicked=self._force_clicked('P'))
        self.pic_type_button_B = CheckBox('B', self, checked=True, clicked=self._force_clicked('B'))

        self.tmdb_id_lineedit = LineEdit('TMDB ID', self)
        self.tmdb_id_lineedit.setMaximumWidth(75)

        self.tmdb_type_combox = ComboBox[str](
            self, model=GeneralModel[str](['TV', 'MOVIE'], to_title=False),
            currentIndex=0, sizeAdjustPolicy=QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        self.tag_data = dict[str, str]()
        self.current_tags = list[str]()

        self.tag_list_combox = ComboBox[str](
            self, currentIndex=0, sizeAdjustPolicy=QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self.tag_list_combox.setMaximumWidth(250)

        self.update_tags()

        self.tag_filter_lineedit = LineEdit('Tag Selection', self, textChanged=self._select_filter_text)

        self.tag_add_custom_button = PushButton('Add Tag', self, clicked=self._handle_current_new_tag)

        self.tag_add_button = PushButton('Add Tag', self, clicked=self._handle_current_combox_tag)

        self.tag_separator = self.get_separator()

        self.delete_after_lineedit = LineEdit('Days', self)
        self.delete_after_lineedit.setMaximumWidth(75)

        self.is_public_checkbox = CheckBox('Public', self, checked=False, clicked=self._public_click)
        self._public_click(self.is_public_checkbox.isChecked())

        self.is_nsfw_checkbox = CheckBox('NSFW', self, checked=False)

        self.output_url_lineedit = LineEdit('https://slow.pics/c/', self, enabled=False)

        self.output_url_copy_button = PushButton('⎘', self, clicked=self.on_copy_output_url_clicked)

        self.start_upload_button = PushButton('Start Upload', self, clicked=self.on_start_upload)

        self.stop_upload_button = PushButton('Stop Upload', self, visible=False, clicked=self.on_stop_upload)

        self.upload_progressbar = ProgressBar(self, value=0)
        self.upload_progressbar.setGeometry(200, 80, 250, 20)

        self.upload_status_label = QLabel('Select Frames')

        self.upload_status_elements = (self.upload_progressbar, self.upload_status_label)

        VBoxLayout(self.hlayout, [
            HBoxLayout([
                self.collection_name_lineedit,
                self.collection_name_button,
            ]),
            self.manual_frames_lineedit,
        ])

        self.collection_name_lineedit.setMinimumWidth(400)

        self.hlayout.addWidget(self.get_separator())

        VBoxLayout(self.hlayout, [
            HBoxLayout([self.current_frame_checkbox]),
            HBoxLayout([QLabel('Random:'), self.random_frames_control])
        ])

        self.hlayout.addWidget(self.get_separator())

        VBoxLayout(self.hlayout, [
            QLabel('Picture types:'),
            HBoxLayout([
                self.pic_type_button_I,
                self.pic_type_button_P,
                self.pic_type_button_B
            ])
        ])

        self.hlayout.addWidget(self.get_separator())

        VBoxLayout(self.hlayout, [
            self.tmdb_id_lineedit,
            self.tmdb_type_combox,
        ])

        self.hlayout.addWidget(self.tag_separator)

        VBoxLayout(self.hlayout, [
            HBoxLayout([
                self.tag_filter_lineedit,
                self.tag_add_custom_button
            ]),
            HBoxLayout([
                self.tag_list_combox,
                self.tag_add_button,
            ])
        ])

        self.hlayout.addStretch(1)

        self.hlayout.addSpacing(20)
        VBoxLayout(self.hlayout, [
            self.is_public_checkbox,
            self.is_nsfw_checkbox,
        ])

        self.hlayout.addWidget(self.get_separator())

        self.output_url_lineedit.setMinimumWidth(250)

        VBoxLayout(self.hlayout, [
            HBoxLayout([
                self.output_url_lineedit, self.output_url_copy_button,
                QLabel('Delete After:'), self.delete_after_lineedit,
                self.start_upload_button, self.stop_upload_button
            ]),
            HBoxLayout([*self.upload_status_elements])
        ])

        self.tag_list_combox.currentIndexChanged.connect(self._handle_tag_index)

    def _get_replace_option(self, key: str) -> str | None:
        if not self.main.outputs:
            return ''

        tmdb_id = self.tmdb_id_lineedit.text() or ''

        if 'tmdb_' in key and tmdb_id not in self.tmdb_data:
            return ''

        data = self.tmdb_data.get(tmdb_id, {"name": "Unknown"})

        match key:
            case '{tmdb_title}':
                return data.get('name', data.get('title', ''))
            case '{tmdb_year}':
                return str(
                    datetime.strptime(
                        data.get('first_air_date', data.get('release_date', '1970-1-1')),
                        '%Y-%m-%d'
                    ).year
                )
            case '{video_nodes}':
                return ' vs '.join([video.name for video in self.main.outputs])

        return None

    def _do_tmdb_request(self) -> None:
        if not (self.settings.tmdb_apikey and self.tmdb_id_lineedit.text()):
            return

        tmdb_type = self.tmdb_type_combox.currentText().lower()
        tmdb_id = self.tmdb_id_lineedit.text()

        url = f'https://api.themoviedb.org/3/{tmdb_type}/{self.tmdb_id_lineedit.text()}?language=en-US'

        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {self.settings.tmdb_apikey}'
        }

        resp = requests.get(url, headers=headers)

        assert resp.status_code == 200, 'Response isn\'t 200'

        data: dict[str, Any] = resp.json()

        assert data.get('success', True), 'Success is false'

        self.tmdb_data[tmdb_id] = data

        return

    def _handle_collection_generate(self) -> str:
        self._do_tmdb_request()

        collection_text = self.collection_name_lineedit.text()

        matches = set(re.findall(self.KEYWORD_RE, collection_text))

        for match in matches:
            replace = self._get_replace_option(match)
            if replace is not None:
                collection_text = collection_text.replace(match, replace)

        return collection_text

    def add_shortcuts(self) -> None:
        self.main.add_shortcut(
            QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Space).toCombined(), self.add_current_frame_to_comp
        )

    def update_tags(self) -> None:
        self.tag_list_combox.setModel(GeneralModel[str](sorted(self.tag_data.keys()), to_title=False))

    def on_public_toggle(self, new_state: bool) -> None:
        if not new_state or self.tag_data:
            return

        if self.tag_data_cache is None or self.tag_data_error:
            try:
                with Session() as sess:
                    sess.get('https://slow.pics/comparison')

                    api_resp = sess.get('https://slow.pics/api/tags').json()

                    self.tag_data = {data['label']: data['value'] for data in api_resp}

                    self.tag_data_cache = self.tag_data
                    self.tag_data_error = False
            except Exception:
                self.tag_data = {'Network error': 'Network error'}
                self.tag_data_error = True
        else:
            self.tag_data = self.tag_data_cache

        self.update_tags()

    def add_current_frame_to_comp(self) -> None:
        frame = str(self.main.current_output.last_showed_frame).strip()
        current_frames = self.manual_frames_lineedit.text()

        if not current_frames:
            self.manual_frames_lineedit.setText(frame)
        else:
            current_frames_l = current_frames.split(',')

            if frame not in current_frames_l:
                current_frames_l.append(frame)
            else:
                current_frames_l.remove(frame)

            self.manual_frames_lineedit.setText(','.join(current_frames_l))

    def on_copy_output_url_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(self.output_url_lineedit.text())
        self.main.show_message('Slow.pics URL copied to clipboard!')

    def on_start_upload(self) -> None:
        if self._thread_running:
            return

        if not self.upload_to_slowpics():
            return

        self.start_upload_button.setVisible(False)
        self.stop_upload_button.setVisible(True)

    def on_end_upload(self, uuid: str, forced: bool = False) -> None:
        if not forced and uuid != self.curr_uuid:
            return

        self.start_upload_button.setVisible(True)
        self.stop_upload_button.setVisible(False)

        self._thread_running = False

        if forced:
            self.upload_progressbar.setValue(int())
            self.upload_status_label.setText('Stopped!')
        else:
            self.upload_status_label.setText('Finished!')

    def on_stop_upload(self) -> None:
        self.upload_worker.is_finished = True

        self.on_end_upload(self.curr_uuid, forced=True)

    def update_status_label(self, uuid: str, kind: str, curr: int | None = None, total: int | None = None) -> None:
        if uuid != self.curr_uuid:
            return

        message = ''

        moreinfo = f" {curr or '?'}/{total or '?'} " if curr or total else ''

        if kind == 'extract':
            message = 'Extracting'
        elif kind == 'upload':
            message = 'Uploading'
        elif kind == 'search':
            message = 'Searching'
        else:
            self.output_url_lineedit.setText(kind)
            self.on_end_upload(self.curr_uuid, False)

            return

        self.upload_status_label.setText(f'{message}{moreinfo}...')

    def _rand_num_frames(self, checked: set[int], rand_func: Callable[[], int]) -> int:
        rnum = rand_func()

        while rnum in checked:
            rnum = rand_func()

        return rnum

    def _select_samples_ptypes(self, num_frames: int, k: int, picture_types: set[str]) -> list[Frame]:
        samples = set[int]()
        _max_attempts = 0
        _rnum_checked = set[int]()

        assert self.main.outputs

        picture_types_b = {p.encode() for p in picture_types}

        interval = num_frames // k
        while len(samples) < k:
            _attempts = 0
            while True:
                if self.upload_worker.is_finished:
                    raise RuntimeError

                num = len(samples)
                self.update_status_label(self.curr_uuid, 'search', _attempts, _MAX_ATTEMPTS_PER_PICTURE_TYPE)
                if len(_rnum_checked) >= num_frames:
                    raise ValueError(f'There aren\'t enough of {picture_types} in these clips')
                rnum = self._rand_num_frames(_rnum_checked, partial(random.randrange, start=interval*num, stop=(interval*(num+1))-1))
                _rnum_checked.add(rnum)

                if all(
                    cast(bytes, f.props['_PictType']) in picture_types_b
                    for f in vs.core.std.Splice(
                        [out.prepared.clip[rnum] for out in self.main.outputs], True
                    ).frames(close=True)
                ):
                    break

                _attempts += 1
                _max_attempts += 1

                if _attempts > _MAX_ATTEMPTS_PER_PICTURE_TYPE:
                    logging.warning(
                        f'{_MAX_ATTEMPTS_PER_PICTURE_TYPE} attempts were made for sample {len(samples)} '
                        f'and no match found for {picture_types}; stopping iteration...')
                    break

            if _max_attempts > (curr_max_att := _MAX_ATTEMPTS_PER_PICTURE_TYPE * k):
                raise RecursionError(f'Comp: attempts max of {curr_max_att} has been reached!')

            if _attempts < _MAX_ATTEMPTS_PER_PICTURE_TYPE:
                samples.add(rnum)
                self.upload_progressbar.setValue(int())
                self.upload_progressbar.setValue(int(100 * len(samples) / k))

        return list(map(Frame, samples))

    def create_slowpics_tags(self) -> list[str]:
        tags = list[str]()

        with Session() as sess:
            sess.get('https://slow.pics/comparison')

            for tag in self.current_tags:
                if tag in self.tag_data:
                    tags.append(self.tag_data[tag])
                    continue

                api_resp: dict[str, str] = sess.post(
                    'https://slow.pics/api/tags',
                    data=tag,
                    headers=_get_slowpic_headers(len(tag), 'application/json', sess)
                ).json()

                label, value = api_resp['label'], api_resp['value']

                self.tag_data[label] = value

                tags.append(value)

        self.update_tags()

        return tags

    def get_slowpics_conf(self) -> WorkerConfiguration:
        assert self.main.outputs

        num = int(self.random_frames_control.value())
        frames = list[Frame](
            map(lambda x: Frame(int(x)), filter(None, [x.strip() for x in self.manual_frames_lineedit.text().split(',')]))
        )

        picture_types = set[str]()

        if self.pic_type_button_I.isChecked():
            picture_types.add('I')

        if self.pic_type_button_B.isChecked():
            picture_types.add('B')

        if self.pic_type_button_P.isChecked():
            picture_types.add('P')

        lens = set(out.prepared.clip.num_frames for out in self.main.outputs)

        if len(lens) != 1:
            logging.warning('Outputted clips don\'t all have the same length!')

        lens_n = min(lens)

        path = Path(main_window().current_config_dir) / ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=16)
        )

        if num:
            if picture_types == {'I', 'P', 'B'}:
                interval = lens_n // num
                samples = list(map(Frame, list(random.randrange(interval*i, (interval*(i+1))-1) for i in range(num))))
            else:
                logging.info('Making samples according to specified picture types...')
                samples = self._select_samples_ptypes(lens_n, num, picture_types)
        else:
            samples = []

        if len(frames):
            samples.extend(frames)

        if self.current_frame_checkbox.isChecked():
            samples.append(self.main.current_output.last_showed_frame)

        collection_name = self._handle_collection_generate().strip()

        if not collection_name:
            collection_name = self.settings.DEFAULT_COLLECTION_NAME

        if not collection_name:
            raise ValueError('You have to put a collection name!')

        if len(collection_name) <= 1:
            raise ValueError('Your collection name is too short!')

        collection_name = collection_name.format(script_name=self.main.script_path.stem)

        sample_frames_current_output = list(sorted(set(samples)))

        if self.main.timeline.mode == self.main.timeline.Mode.FRAME:
            sample_frames = [sample_frames_current_output] * len(self.main.outputs)
        else:
            sample_timestamps = list(map(self.main.current_output.to_time, sample_frames_current_output))
            sample_frames = [
                list(map(output.to_frame, sample_timestamps))
                for output in self.main.outputs
            ]

        delete_after = self.delete_after_lineedit.text() or None

        if delete_after and re.match(r'^\d+$', delete_after) is None:
            raise ValueError('Delete after has to be a number!')

        tmdb_id = self.tmdb_id_lineedit.text()
        if tmdb_id:
            tmdb_type = self.tmdb_type_combox.currentData()
            if tmdb_type == 'TV':
                suffix = 'TV_'
            elif tmdb_type == 'MOVIE':
                suffix = 'MOVIE_'
            else:
                raise ValueError('Unknown TMDB type!')

            if not tmdb_id.startswith(suffix):
                tmdb_id = f'{suffix}{tmdb_id}'

        tags = self.create_slowpics_tags()

        filtered_outputs = []
        for output in self.main.outputs:
            if output.info.get('disable_comp', False):
                continue

            filtered_outputs.append(output)

        sample_frames_int = sorted([list(map(int, x)) for x in sample_frames])

        return WorkerConfiguration(
            str(uuid4()), filtered_outputs, collection_name,
            self.is_public_checkbox.isChecked(), self.is_nsfw_checkbox.isChecked(),
            True, delete_after, sample_frames_int, -1, path, self.main, self.settings.delete_cache_enabled, self.settings.frame_type_enabled,
            self.settings.browser_id, self.settings.session_id, tmdb_id, tags
        )

    def upload_to_slowpics(self) -> bool:
        try:
            self.main.current_scene.setPixmap(self.main.current_scene.pixmap().copy())

            if hasattr(self, 'upload_thread'):
                self._old_threads_workers.append(self.upload_thread)

            if hasattr(self, 'upload_worker'):
                self._old_threads_workers.append(self.upload_worker)

            self.upload_thread = QThread()
            self.upload_worker = Worker()

            self.upload_worker.moveToThread(self.upload_thread)

            try:
                config = self.get_slowpics_conf()
            except RuntimeError as e:
                print(e)
                self.on_end_upload('', True)
                return False

            self.curr_uuid = config.uuid

            self.upload_thread.started.connect(partial(self.upload_worker.run, config))
            self.upload_thread.finished.connect(self.on_end_upload)

            self.upload_worker.progress_bar.connect(
                lambda uuid, val: self.upload_progressbar.setValue(val) if uuid == self.curr_uuid else None
            )
            self.upload_worker.progress_status.connect(self.update_status_label)

            self.upload_thread.start()

            self._thread_running = True

            return True
        except BaseException as e:
            self.main.show_message(str(e))

        return False

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'collection_format': self.collection_name_lineedit.text()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        super().__setstate__(state)
        try_load(state, 'collection_format', str, self.collection_name_lineedit.setText)
