from __future__ import annotations

import logging
import re
import unicodedata
from typing import Callable, Final
from uuid import uuid4

from requests import HTTPError, Session
from requests_toolbelt import MultipartEncoder  # type: ignore
from vstools import SPath

KEYWORD_RE = re.compile(r'\{[a-z0-9_-]+\}', flags=re.IGNORECASE)
MAX_ATTEMPTS_PER_PICTURE_TYPE: Final[int] = 50
MAX_ATTEMPTS_PER_BRIGHT_TYPE: Final[int] = 100


__all__ = [
    'KEYWORD_RE', 'MAX_ATTEMPTS_PER_PICTURE_TYPE',

    'get_slowpic_upload_headers',
    'get_slowpic_headers',
    'do_single_slowpic_upload',

    'clear_filename',

    'rand_num_frames'
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
