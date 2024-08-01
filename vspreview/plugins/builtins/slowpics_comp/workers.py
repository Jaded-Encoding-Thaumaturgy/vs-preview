from __future__ import annotations

import shutil
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from typing import Any, NamedTuple
from uuid import uuid4

from PyQt6.QtCore import QObject, pyqtSignal
from requests import Session
from requests_toolbelt import MultipartEncoder  # type: ignore
from requests_toolbelt import MultipartEncoderMonitor
from stgpytools import SPath, ndigits
from vstools import clip_data_gather, get_prop, remap_frames, vs

from vspreview.core import PackingType, VideoOutput
from vspreview.main import MainWindow

from .utils import clear_filename, do_single_slowpic_upload, get_slowpic_headers, get_slowpic_upload_headers

__all__ = [
    'WorkerConfiguration', 'Worker'
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
        all_images = list[list[SPath]]()
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

                decimated = remap_frames(clip, conf.frames[i])

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
            for j, (image, frame) in enumerate(zip(images, conf.frames[i])):
                if self.isFinished():
                    return self.finished.emit(conf.uuid)

                image_name = (f'({all_image_types[i][j]}) ' if conf.frame_type else '') + f'{output.name}'

                if is_comparison:
                    fields[f'comparisons[{j}].name'] = str(frame)
                    fields[f'comparisons[{j}].imageNames[{i}]'] = image_name
                else:
                    fields[f'imageNames[{j}]'] = f'{frame} - {image_name}'

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

            base_page = sess.get('https://slow.pics/comparison', headers=get_slowpic_headers(sess))
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
                f'https://slow.pics/upload/{"comparison" if is_comparison else "collection"}', data=monitor.to_string(),
                headers=get_slowpic_upload_headers(monitor.len, monitor.content_type, sess)
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

                        imageUuid = image_ids[j][i] if is_comparison else image_ids[0][j]
                        futures.append(
                            executor.submit(
                                do_single_slowpic_upload,
                                sess=sess, collection=collection, imageUuid=imageUuid,
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
