from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Callable, Final
from uuid import uuid4

from requests import HTTPError, Session
from requests.utils import dict_from_cookiejar
from requests_toolbelt import MultipartEncoder  # type: ignore
from jetpytools import SPath

from vspreview.core import VideoOutput
from vspreview.main import MainWindow

KEYWORD_RE = re.compile(r'\{[a-z0-9_-]+\}', flags=re.IGNORECASE)
MAX_ATTEMPTS_PER_PICTURE_TYPE: Final[int] = 50
MAX_ATTEMPTS_PER_BRIGHT_TYPE: Final[int] = 100


__all__ = [
    'KEYWORD_RE', 'MAX_ATTEMPTS_PER_PICTURE_TYPE',

    'get_slowpic_upload_headers',
    'get_slowpic_headers',
    'do_single_slowpic_upload',

    'clear_filename',

    'rand_num_frames',

    'get_frame_time'
]


def get_slowpic_upload_headers(content_length: int, content_type: str, sess: Session) -> dict[str, str]:
    return {
        'Content-Length': str(content_length),
        'Content-Type': content_type,
    } | get_slowpic_headers(sess)


def get_slowpic_headers(sess: Session) -> dict[str, str]:
    return {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9',
        'Access-Control-Allow-Origin': '*',
        'Origin': 'https://slow.pics/',
        'Referer': 'https://slow.pics/comparison',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        ),
        'X-XSRF-TOKEN': sess.cookies.get('XSRF-TOKEN', None),
    }


def do_single_slowpic_upload(sess: Session, collection: str, imageUuid: str, image: SPath, browser_id: str) -> None:
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
                headers=get_slowpic_upload_headers(upload_info.len, upload_info.content_type, sess)
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


def rand_num_frames(checked: set[int], rand_func: Callable[[], int]) -> int:
    rnum = rand_func()

    while rnum in checked:
        rnum = rand_func()

    return rnum


def get_frame_time(main: MainWindow, output: VideoOutput, frame: int, max_value: int) -> str:
    frame_type: str = main.plugins['dev.setsugen.comp'].settings.globals.settings.frame_ntype

    frame_str = str(frame)
    time_str = output.to_time(frame).to_str_minimal(output.to_time(max_value))  # type: ignore

    if frame_type == 'timeline':
        return frame_str if main.timeline.mode == main.timeline.Mode.FRAME else time_str

    if frame_type == 'frame':
        return frame_str

    if frame_type == 'time':
        return time_str

    return f'{time_str} / {frame_str}'


def do_login(username:str, password:str, path:SPath):
    path.parent.mkdir(parents=True, exist_ok=True)

    with Session() as session:
        session.headers.update(get_slowpic_headers(session))

        home = session.get('https://slow.pics/login')
        home.raise_for_status()

        csrf = re.search(r'<input type="hidden" name="_csrf" value="([a-zA-Z0-9-_]+)"\/>', home.text)

        if not csrf:
            raise Exception('Couldn\'t find csrf')

        login_params = {
            "_csrf": csrf.group(1),
            "username": username,
            "password": password,
            "remember-me": 'on'
        }


        login = session.post('https://slow.pics/login', data=login_params, allow_redirects=True)
        login.raise_for_status()

        path.write_text(json.dumps(dict_from_cookiejar(session.cookies)))