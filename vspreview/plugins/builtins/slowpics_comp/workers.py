from __future__ import annotations

import json
import logging
import random
import shutil
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from functools import partial
from typing import Any, NamedTuple
from uuid import uuid4
from PyQt6.QtCore import QObject, pyqtSignal
from requests import Session
from requests_toolbelt import MultipartEncoder  # type: ignore
from requests_toolbelt import MultipartEncoderMonitor
from requests.utils import cookiejar_from_dict, dict_from_cookiejar
from jetpytools import SPath, ndigits
from vstools import clip_data_gather, get_prop, remap_frames, vs

from vspreview.core import Frame, PackingType, VideoOutput
from vspreview.main import MainWindow

from .utils import (
    MAX_ATTEMPTS_PER_BRIGHT_TYPE, MAX_ATTEMPTS_PER_PICTURE_TYPE, clear_filename, do_single_slowpic_upload,
    get_slowpic_headers, get_slowpic_upload_headers, rand_num_frames, get_frame_time
)

__all__ = [
    'WorkerConfiguration', 'Worker',

    'FindFramesWorkerConfiguration', 'FindFramesWorker'
]


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
    path: SPath
    main: MainWindow
    delete_cache: bool
    frame_type: bool
    cookies: SPath
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
        all_images = list[list[SPath]]()
        all_image_types = list[list[str]]()
        conf.path.mkdir(parents=True, exist_ok=False)

        if conf.cookies.is_file():
            with Session() as sess:
                sess.cookies.update(cookiejar_from_dict(json.loads(conf.cookies.read_text())))
                base_page = sess.get('https://slow.pics/comparison')
                if base_page.text.find('id="logoutBtn"') == -1:
                    self.progress_status.emit(conf.uuid, 'Session Expired', 0, 0)
                    raise StopIteration
                conf.cookies.write_text(json.dumps(dict_from_cookiejar(sess.cookies)))

        try:
            for i, output in enumerate(conf.outputs):
                if self.isFinished():
                    raise StopIteration
                self.progress_status.emit(conf.uuid, 'extract', i + 1, len(conf.outputs))

                folder_name = str(uuid4())
                path_name = conf.path / folder_name
                path_name.mkdir(parents=True)

                curr_filename = (path_name / folder_name).append_to_stem(f'%0{ndigits(max(conf.frames[i]))}d').with_suffix('.png')

                clip = output.prepare_vs_output(
                    output.source.clip, not hasattr(vs.core, "fpng"),
                    PackingType.CURRENT.vs_format.replace(bits_per_sample=8, sample_type=vs.INTEGER)
                )

                path_images = [SPath(str(curr_filename) % n) for n in conf.frames[i]]

                def _frame_callback(n: int, f: vs.VideoFrame) -> str:
                    if self.isFinished():
                        raise StopIteration

                    return get_prop(f.props, '_PictType', str, None, '?')

                if hasattr(vs.core, "fpng"):
                    clip = vs.core.fpng.Write(clip, filename=curr_filename, compression=conf.compression)
                    frame_callback = _frame_callback
                else:
                    qcomp = (0 if conf.compression == 1 else 100) if conf.compression else 80

                    def frame_callback(n: int, f: vs.VideoFrame) -> str:
                        if not conf.main.current_output.frame_to_qimage(f).save(path_images[n].to_str(), 'PNG', qcomp):
                            raise StopIteration('There was an error saving the image to disk!')

                        return _frame_callback(n, f)

                decimated = remap_frames(clip, conf.frames[i])  # type: ignore

                image_types = clip_data_gather(decimated, partial(self._progress_update_func, uuid=conf.uuid), frame_callback)

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
        is_comparison = len(all_images) > 1
        fields = dict[str, Any]()
        for i, (output, images) in enumerate(zip(conf.outputs, all_images)):
            if self.isFinished():
                return self.finished.emit(conf.uuid)
            max_value = max(conf.frames[i])
            for j, (image, frame) in enumerate(zip(images, conf.frames[i])):
                if self.isFinished():
                    return self.finished.emit(conf.uuid)

                image_name = (f'({all_image_types[i][j]}) ' if conf.frame_type else '') + f'{output.name}'

                frame_time = get_frame_time(conf.main, output, frame, max_value)

                if is_comparison:
                    fields[f'comparisons[{j}].name'] = frame_time
                    fields[f'comparisons[{j}].imageNames[{i}]'] = image_name
                else:
                    fields[f'imageNames[{j}]'] = f'{frame_time} - {image_name}'

                total_images += 1

        self.progress_status.emit(conf.uuid, 'upload', 0, 0)

        with Session() as sess:
            browser_id = str(uuid4())
            check_session = conf.cookies.is_file()
            if check_session:
                sess.cookies.update(cookiejar_from_dict(json.loads(conf.cookies.read_text())))

            base_page = sess.get('https://slow.pics/comparison', headers=get_slowpic_headers(sess))
            if self.isFinished():
                return self.finished.emit(conf.uuid)

            if check_session:
                if base_page.text.find('id="logoutBtn"') == -1:
                    self.progress_status.emit(conf.uuid, 'Session Expired', 0, 0)
                    raise StopIteration
                conf.cookies.write_text(json.dumps(dict_from_cookiejar(sess.cookies)))

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
                f'https://slow.pics/upload/{"comparison" if is_comparison else "collection"}', data=monitor.to_string(),
                headers=get_slowpic_upload_headers(monitor.len, monitor.content_type, sess)
            ).json()
            collection = comp_response['collectionUuid']
            key = comp_response['key']
            image_ids = comp_response['images']
            self._progress_update_func(0, total_images, uuid=conf.uuid)
            with ThreadPoolExecutor() as executor:
                futures = list[Future[None]]()

                for i, (output, images) in enumerate(zip(conf.outputs, all_images)):
                    if self.isFinished():
                        return self.finished.emit(conf.uuid)
                    for j, (image, frame) in enumerate(zip(images, conf.frames[i])):
                        if self.isFinished():
                            return self.finished.emit(conf.uuid)

                        imageUuid = image_ids[j][i] if is_comparison else image_ids[0][j]
                        futures.append(
                            executor.submit(
                                do_single_slowpic_upload,
                                sess=sess, collection=collection, imageUuid=imageUuid,
                                image=image, browser_id=browser_id
                            )
                        )

                images_done = 0
                for _ in as_completed(futures):
                    if self.isFinished():
                        return self.finished.emit(conf.uuid)
                    images_done += 1
                    self._progress_update_func(images_done, total_images, uuid=conf.uuid)

            self._progress_update_func(total_images, total_images, uuid=conf.uuid)
        if conf.delete_cache:
            shutil.rmtree(conf.path, True)

        if check_session:
            conf.cookies.write_text(json.dumps(dict_from_cookiejar(sess.cookies)))

        url = f'https://slow.pics/c/{key}'

        self.progress_status.emit(conf.uuid, url, 0, 0)

        url_out = (
            conf.path.parent / 'Old Comps' / clear_filename(f'{conf.collection_name} - {key}')
        ).with_suffix('.url')
        url_out.parent.mkdir(parents=True, exist_ok=True)
        url_out.touch(exist_ok=True)
        url_out.write_text(f'[InternetShortcut]\nURL={url}')

        self.finished.emit(conf.uuid)


class FindFramesWorkerConfiguration(NamedTuple):
    uuid: str
    current_output: VideoOutput
    outputs: list[VideoOutput]
    main: MainWindow
    start_frame: int
    end_frame: int
    num_frames: int
    dark_frames: int
    light_frames: int
    ptype_num: int
    picture_types: set[str]
    samples: list[Frame]


class FindFramesWorker(QObject):
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

    def _select_samples_ptypes(self, conf: FindFramesWorkerConfiguration) -> list[Frame]:
        samples = set[int]()
        _max_attempts = 0
        _rnum_checked = set[int]()

        picture_types_b = {p.encode() for p in conf.picture_types}

        interval = conf.num_frames // conf.ptype_num
        while len(samples) < conf.ptype_num:
            _attempts = 0
            while True:
                if self.isFinished():
                    raise StopIteration

                num = len(samples)
                self.progress_status.emit(conf.uuid, 'search', _attempts, MAX_ATTEMPTS_PER_PICTURE_TYPE)
                if len(_rnum_checked) >= conf.num_frames:
                    logging.warning(f'There aren\'t enough of {conf.picture_types} in these clips')
                    raise StopIteration

                rnum = conf.start_frame + rand_num_frames(
                    _rnum_checked, partial(random.randrange, start=interval * num, stop=(interval * (num + 1)) - 1)
                )
                _rnum_checked.add(rnum)

                if all(
                    get_prop(f.props, '_PictType', str, None, '').encode() in picture_types_b
                    for f in vs.core.std.Splice(
                        [out.prepared.clip[rnum] for out in conf.outputs], True
                    ).frames(close=True)
                ):
                    break

                _attempts += 1
                _max_attempts += 1

                if _attempts > MAX_ATTEMPTS_PER_PICTURE_TYPE:
                    logging.warning(
                        f'{MAX_ATTEMPTS_PER_PICTURE_TYPE} attempts were made and only found {len(samples)} samples '
                        f'and no match found for {conf.picture_types}; stopping iteration...'
                    )
                    break

            if _max_attempts > (curr_max_att := MAX_ATTEMPTS_PER_PICTURE_TYPE * conf.ptype_num):
                logging.warning(f'Comp: attempts max of {curr_max_att} has been reached!')
                raise StopIteration

            if _attempts < MAX_ATTEMPTS_PER_PICTURE_TYPE:
                samples.add(rnum)
                self._progress_update_func(len(samples), conf.ptype_num, uuid=conf.uuid)

        return list(map(Frame, samples))

    def _find_dark_light(self, conf: FindFramesWorkerConfiguration) -> list[Frame]:
        dark = set[int]()
        light = set[int]()
        _max_attempts = 0
        _rnum_checked = set[int]()

        stats = conf.current_output.source.clip.std.PlaneStats()

        req_frame_count = max(conf.dark_frames, conf.light_frames)
        frames_needed = conf.dark_frames + conf.light_frames
        interval = conf.num_frames // frames_needed

        while (len(light) + len(dark)) < frames_needed:
            _attempts = 0
            while True:
                if self.isFinished():
                    raise StopIteration

                num = len(light) + len(dark)
                self.progress_status.emit(conf.uuid, 'search', _attempts, MAX_ATTEMPTS_PER_BRIGHT_TYPE)
                if len(_rnum_checked) >= conf.num_frames:
                    logging.warning('There aren\'t enough of dark/light in these clips')
                    raise StopIteration

                rnum = conf.start_frame + rand_num_frames(
                    _rnum_checked, partial(random.randrange, start=interval * num, stop=(interval * (num + 1)) - 1)
                )
                _rnum_checked.add(rnum)

                avg = get_prop(stats.get_frame(rnum), "PlaneStatsAverage", float, None, 0)
                if 0.062746 <= avg <= 0.380000:
                    if len(dark) < conf.dark_frames:
                        dark.add(rnum)
                        break
                elif 0.450000 <= avg <= 0.800000:
                    if len(light) < conf.light_frames:
                        light.add(rnum)
                        break

                _attempts += 1
                _max_attempts += 1

                if _attempts > MAX_ATTEMPTS_PER_BRIGHT_TYPE:
                    logging.warning(
                        f'{MAX_ATTEMPTS_PER_BRIGHT_TYPE} attempts were made and only found '
                        f'{len(light) + len(dark)} samples '
                        f'and no match found for dark/light; stopping iteration...')
                    break

            if _max_attempts > (curr_max_att := MAX_ATTEMPTS_PER_BRIGHT_TYPE * req_frame_count):
                logging.warning(f'Comp: attempts max of {curr_max_att} has been reached!')
                raise StopIteration

            if _attempts < MAX_ATTEMPTS_PER_BRIGHT_TYPE:
                self._progress_update_func(len(light) + len(dark), frames_needed, uuid=conf.uuid)

        return list(map(Frame, dark | light))

    def run(self, conf: FindFramesWorkerConfiguration) -> None:  # type: ignore
        samples = []

        try:
            if conf.ptype_num:
                if conf.picture_types == {'I', 'P', 'B'}:
                    interval = (conf.end_frame - conf.start_frame) // conf.ptype_num
                    samples = list(
                        map(
                            Frame,
                            list(
                                conf.start_frame + random.randrange(interval * i, (interval * (i + 1)) - 1)
                                for i in range(conf.ptype_num)
                            )
                        )
                    )
                else:
                    logging.info('Making samples according to specified picture types...')
                    samples = self._select_samples_ptypes(conf)

            if conf.dark_frames or conf.light_frames:
                logging.info('Making samples according to specified brightness levels...')
                samples.extend(self._find_dark_light(conf))

        except StopIteration:
            return self.finished.emit(conf.uuid)
        except vs.Error as e:
            if 'raise StopIteration' in str(e):
                return self.finished.emit(conf.uuid)
            raise e

        conf.samples.extend(samples)

        self.finished.emit(conf.uuid)
        self.deleteLater()
