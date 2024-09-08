from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Callable, Final
from uuid import uuid4

from requests import HTTPError, Session
from requests_toolbelt import MultipartEncoder
from vstools import SPath

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

    'sanitize_filename',

    'rand_num_frames',

    'get_frame_time'
]


def get_slowpic_upload_headers(content_length: int, content_type: str, sess: Session) -> dict[str, str]:
    """Generate headers for uploading to Slowpics."""

    return {
        'Content-Length': str(content_length),
        'Content-Type': content_type,
    } | get_slowpic_headers(sess)


def get_slowpic_headers(sess: Session) -> dict[str, str]:
    """Generate general headers for Slowpics requests."""

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
    """Perform a single image upload to Slowpics."""

    upload_info = MultipartEncoder({
        'collectionUuid': collection,
        'imageUuid': imageUuid,
        'file': (image.name, image.read_bytes(), 'image/png'),
        'browserId': browser_id,
    }, str(uuid4()))

    max_retries = 3
    retry_delay_seconds = 1

    for attempt in range(max_retries):
        try:
            req = sess.post(
                'https://slow.pics/upload/image', data=upload_info.to_string(),
                headers=get_slowpic_upload_headers(upload_info.len, upload_info.content_type, sess)
            )
            req.raise_for_status()
            return
        except HTTPError as e:
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")

            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds)
                retry_delay_seconds *= 2
            else:
                logging.error(f"Failed to upload image after {max_retries} attempts")
                raise


def sanitize_filename(filename: str) -> str:
    """Clean and sanitize a filename."""

    if not filename:
        return '__'

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

    if not filename or all(x == '.' for x in filename):
        return '__' + filename

    if filename in reserved:
        return '__' + filename

    if len(filename) <= 255:
        return filename

    parts = re.split(r'/|\\', filename)[-1].split('.')

    if len(parts) > 1:
        ext = '.' + parts.pop()
        filename = filename[:-len(ext)]
    else:
        ext = ''

    if not filename:
        filename = '__'

    if len(ext) > 254:
        ext = ext[254:]

    maxl = 255 - len(ext)
    filename = filename[:maxl] + ext

    # Re-check last character (if there was no extension)
    return filename.rstrip('. ')


def rand_num_frames(checked: set[int], rand_func: Callable[[], int]) -> int:
    """Generate a random frame number that hasn't been checked yet."""

    if not checked:
        return rand_func()

    while True:
        rnum = rand_func()

        if rnum not in checked:
            return rnum


def get_frame_time(main: MainWindow, output: VideoOutput, frame: int, max_value: int) -> str:
    """Get the frame time string based on the current settings."""

    frame_type: str = main.plugins['dev.setsugen.comp'].settings.globals.settings.frame_ntype
    frame_str = str(frame)
    time_str = output.to_time(frame).to_str_minimal(output.to_time(max_value))  # type: ignore

    frame_time_map = {
        'timeline': lambda: frame_str if main.timeline.mode == main.timeline.Mode.FRAME else time_str,
        'frame': lambda: frame_str,
        'time': lambda: time_str,
        'both': lambda: f'{time_str} / {frame_str}'
    }

    return frame_time_map.get(frame_type, frame_time_map['both'])()
