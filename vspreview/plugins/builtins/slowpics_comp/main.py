from __future__ import annotations

import logging
import random
import re
import string
from datetime import datetime
from functools import partial
from typing import Any, Callable, Mapping, cast
from uuid import uuid4

import requests
from PyQt6 import QtCore
from PyQt6.QtCore import QKeyCombination, Qt, QThread
from PyQt6.QtWidgets import QComboBox, QFrame, QLabel
from requests import Session
from stgpytools import SPath
from vstools import vs

from vspreview.core import (
    CheckBox, ComboBox, ExtendedWidget, Frame, FrameEdit, HBoxLayout, LineEdit, ProgressBar, PushButton, VBoxLayout,
    main_window, try_load
)
from vspreview.models import GeneralModel

from .settings import CompSettings
from .utils import KEYWORD_RE, MAX_ATTEMPTS_PER_PICTURE_TYPE, get_slowpic_upload_headers, get_slowpic_headers
from .workers import Worker, WorkerConfiguration

__all__ = [
    'CompUploadWidget'
]


class CompUploadWidget(ExtendedWidget):
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

    def __init__(self, settings: CompSettings) -> None:
        super().__init__()

        self.main = main_window()
        self.settings = settings

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
        self.collection_name_lineedit.setText(self.settings.collection_name_template)

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

        self.is_public_checkbox = CheckBox(
            'Public', self, checked=self.settings.default_public, clicked=self._public_click
        )
        self._public_click(self.is_public_checkbox.isChecked())

        self.is_nsfw_checkbox = CheckBox('NSFW', self, checked=self.settings.default_nsfw)

        self.output_url_lineedit = LineEdit('https://slow.pics/c/', self, enabled=False)

        self.output_url_copy_button = PushButton('⎘', self, clicked=self.on_copy_output_url_clicked)

        self.start_upload_button = PushButton('Start Upload', self, clicked=self.on_start_upload)

        self.stop_upload_button = PushButton('Stop Upload', self, visible=False, clicked=self.on_stop_upload)

        self.upload_progressbar = ProgressBar(self, value=0)
        self.upload_progressbar.setGeometry(200, 80, 250, 20)

        self.upload_status_label = QLabel('Select Frames')

        self.upload_status_elements = (self.upload_progressbar, self.upload_status_label)

        VBoxLayout(self.vlayout, [
            HBoxLayout([
                self.collection_name_lineedit,
                self.collection_name_button
            ]),

            HBoxLayout([
                self.manual_frames_lineedit,
                self.current_frame_checkbox
            ])
        ])

        self.collection_name_lineedit.setMinimumWidth(400)

        self.vlayout.addWidget(self.get_separator(True))

        HBoxLayout(self.vlayout, [
            VBoxLayout([QLabel('Random:'), self.random_frames_control]),
            self.get_separator(False),
            VBoxLayout([
                QLabel('Picture types:'),
                HBoxLayout([
                    self.pic_type_button_I,
                    self.pic_type_button_P,
                    self.pic_type_button_B
                ])
            ]),
            self.get_separator(False),
            VBoxLayout([
                QLabel('Options:'),
                HBoxLayout([
                    self.is_public_checkbox,
                    self.is_nsfw_checkbox,
                ])
            ])
        ])

        self.vlayout.addWidget(self.get_separator(True))

        HBoxLayout(self.vlayout, [
            self.tmdb_id_lineedit,
            self.tmdb_type_combox,
        ])

        self.vlayout.addWidget(self.tag_separator)

        VBoxLayout(self.vlayout, [
            HBoxLayout([
                self.tag_filter_lineedit,
                self.tag_add_custom_button
            ]),
            HBoxLayout([
                self.tag_list_combox,
                self.tag_add_button,
            ])
        ])

        self.vlayout.addStretch(1)

        self.vlayout.addSpacing(20)

        self.vlayout.addWidget(self.get_separator())

        self.output_url_lineedit.setMinimumWidth(250)

        VBoxLayout(self.vlayout, [
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

        api_key = self.settings.tmdb_apikey
        url = f'https://api.themoviedb.org/3/{tmdb_type}/{self.tmdb_id_lineedit.text()}?language=en-US'
        headers = {
            'accept': 'application/json'
        }

        if len(api_key) == 32:
            url += f'&api_key={api_key}'
        else:
            headers['Authorization'] = f'Bearer {api_key}'

        resp = requests.get(url, headers=headers)

        if resp.status_code != 200:
            logging.error(f'Error connecting to TMDB: {resp} ({resp.status_code})')
            return

        data: dict[str, Any] = resp.json()

        self.tmdb_data[tmdb_id] = data

    def _handle_collection_generate(self) -> str:
        self._do_tmdb_request()

        collection_text = self.collection_name_lineedit.text()

        matches = set(re.findall(KEYWORD_RE, collection_text))

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
                    sess.headers.update(get_slowpic_headers(sess))
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
                self.update_status_label(self.curr_uuid, 'search', _attempts, MAX_ATTEMPTS_PER_PICTURE_TYPE)
                if len(_rnum_checked) >= num_frames:
                    raise ValueError(f'There aren\'t enough of {picture_types} in these clips')
                rnum = self._rand_num_frames(_rnum_checked, partial(random.randrange, start=interval * num, stop=(interval * (num + 1)) - 1))
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

                if _attempts > MAX_ATTEMPTS_PER_PICTURE_TYPE:
                    logging.warning(
                        f'{MAX_ATTEMPTS_PER_PICTURE_TYPE} attempts were made for sample {len(samples)} '
                        f'and no match found for {picture_types}; stopping iteration...')
                    break

            if _max_attempts > (curr_max_att := MAX_ATTEMPTS_PER_PICTURE_TYPE * k):
                raise RecursionError(f'Comp: attempts max of {curr_max_att} has been reached!')

            if _attempts < MAX_ATTEMPTS_PER_PICTURE_TYPE:
                samples.add(rnum)
                self.upload_progressbar.setValue(int())
                self.upload_progressbar.setValue(int(100 * len(samples) / k))

        return list(map(Frame, samples))

    def create_slowpics_tags(self) -> list[str]:
        tags = list[str]()

        with Session() as sess:
            sess.headers.update(get_slowpic_headers(sess))
            sess.get('https://slow.pics/comparison')

            for tag in self.current_tags:
                if tag in self.tag_data:
                    tags.append(self.tag_data[tag])
                    continue

                api_resp: dict[str, str] = sess.post(
                    'https://slow.pics/api/tags',
                    data=tag,
                    headers=get_slowpic_upload_headers(len(tag), 'application/json', sess)
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

        path = SPath(main_window().current_config_dir) / ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=16)
        )

        if num:
            if picture_types == {'I', 'P', 'B'}:
                interval = lens_n // num
                samples = list(map(Frame, list(random.randrange(interval * i, (interval * (i + 1)) - 1) for i in range(num))))
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
            True, delete_after, sample_frames_int, self.settings.compression, path,
            self.main, self.settings.delete_cache_enabled, self.settings.frame_type_enabled,
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
