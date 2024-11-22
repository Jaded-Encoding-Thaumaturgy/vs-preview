from __future__ import annotations

import logging
import re
from copy import deepcopy
from pathlib import Path

from ...core import Frame, Time
from ...models import SceningList

__all__ = [
    'supported_file_types'
]


def import_ass(path: Path, scening_list: SceningList) -> int:
    """
    Imports lines as scenes.
    Text is ignored.
    """
    out_of_range_count = 0

    try:
        from pysubs2 import load as pysubs2_load  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        raise RuntimeError(
            'vspreview: Can\'t import scenes from ass file, you\'re missing the `pysubs2` package!'
        )

    subs = pysubs2_load(str(path))
    for line in subs:
        t_start = Time(milliseconds=line.start)
        t_end = Time(milliseconds=line.end)
        try:
            scening_list.add(Frame(t_start), Frame(t_end))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_celltimes(path: Path, scening_list: SceningList) -> int:
    """
    Imports cell times as single-frame scenes
    """
    out_of_range_count = 0

    for line in path.read_text('utf8').splitlines():
        try:
            scening_list.add(Frame(int(line)))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_cue(path: Path, scening_list: SceningList) -> int:
    """
    Imports tracks as scenes.
    Uses TITLE for scene label.
    """
    out_of_range_count = 0

    try:
        from cueparser import CueSheet  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        raise RuntimeError(
            'vspreview: Can\'t import scenes from cue file, you\'re missing the `cueparser` package!'
        )

    def offset_to_time(offset: str) -> Time | None:
        pattern = re.compile(r'(\d{1,2}):(\d{1,2}):(\d{1,2})')
        match = pattern.match(offset)
        if match is None:
            return None
        return Time(minutes=int(match[1]), seconds=int(match[2]), milliseconds=int(match[3]) / 75 * 1000)

    cue_sheet = CueSheet()
    cue_sheet.setOutputFormat('')
    cue_sheet.setData(path.read_text('utf8'))
    cue_sheet.parse()

    for track in cue_sheet.tracks:
        if track.offset is None:
            continue
        offset = offset_to_time(track.offset)
        if offset is None:
            logging.warning(f"Scening import: INDEX timestamp '{track.offset}' format isn't supported.")
            continue
        start = Frame(offset)

        end = None
        if track.duration is not None:
            end = Frame(offset + Time(track.duration))

        label = ''
        if track.title is not None:
            label = track.title

        try:
            scening_list.add(start, end, label)
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_dgi(path: Path, scening_list: SceningList) -> int:
    """
    Imports IDR frames as single-frame scenes.
    """
    out_of_range_count = 0

    pattern = re.compile(r'IDR\s\d+\n(\d+):FRM', re.RegexFlag.MULTILINE)

    for match in pattern.findall(path.read_text('utf8')):
        try:
            scening_list.add(Frame(match))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_lwi(path: Path, scening_list: SceningList) -> int:
    """
    Imports Key=1 frames as single-frame scenes.
    Ignores everything besides Index=0 video stream.
    """
    out_of_range_count = 0

    AV_CODEC_ID_FIRST_AUDIO = 0x10000
    STREAM_INDEX = 0
    IS_KEY = 1

    pattern = re.compile(r'Index={}.*?Codec=(\d+).*?\n.*?Key=(\d)'.format(
        STREAM_INDEX
    ))

    frame = Frame(0)
    for match in pattern.finditer(path.read_text('utf8'), re.RegexFlag.MULTILINE):
        if int(match[1]) >= AV_CODEC_ID_FIRST_AUDIO:
            frame += Frame(1)
            continue

        if not int(match[2]) == IS_KEY:
            frame += Frame(1)
            continue

        try:
            scening_list.add(deepcopy(frame))
        except ValueError:
            out_of_range_count += 1

        frame += Frame(1)

    return out_of_range_count


def import_matroska_xml_chapters(path: Path, scening_list: SceningList) -> int:
    """
    Imports chapters as scenes.
    Preserve end time and text if they're present.
    """
    from xml.etree import ElementTree
    out_of_range_count = 0

    timestamp_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}(?:\.\d{3})?)')

    try:
        root = ElementTree.parse(str(path)).getroot()
    except ElementTree.ParseError as exc:
        logging.warning(f"Scening import: error occurred while parsing '{path.name}':")
        logging.warning(exc.msg)
        return out_of_range_count

    for chapter in root.iter('ChapterAtom'):
        start_element = chapter.find('ChapterTimeStart')
        if start_element is None or start_element.text is None:
            continue
        match = timestamp_pattern.match(start_element.text)
        if match is None:
            continue
        start = Frame(Time(hours=int(match[1]), minutes=int(match[2]), seconds=float(match[3])))

        end = None
        end_element = chapter.find('ChapterTimeEnd')
        if end_element is not None and end_element.text is not None:
            match = timestamp_pattern.match(end_element.text)
            if match is not None:
                end = Frame(Time(hours=int(match[1]), minutes=int(match[2]), seconds=float(match[3])))

        label = ''
        label_element = chapter.find('ChapterDisplay/ChapterString')
        if label_element is not None and label_element.text is not None:
            label = label_element.text

        try:
            scening_list.add(start, end, label)
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_ogm_chapters(path: Path, scening_list: SceningList) -> int:
    """
    Imports chapters as single-frame scenes.
    Uses NAME for scene label.
    """
    out_of_range_count = 0

    pattern = re.compile(
        r'(CHAPTER\d+)=(\d+):(\d+):(\d+(?:\.\d+)?)\n\1NAME=(.*)',
        re.RegexFlag.MULTILINE
    )
    for match in pattern.finditer(path.read_text('utf8')):
        time = Time(hours=int(match[2]), minutes=int(match[3]), seconds=float(match[4]))
        try:
            scening_list.add(Frame(time), label=match[5])
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_qp(path: Path, scening_list: SceningList) -> int:
    """
    Imports I- and K-frames as single-frame scenes.
    """
    out_of_range_count = 0

    pattern = re.compile(r'(\d+)\sI|K')
    for match in pattern.findall(path.read_text('utf8')):
        try:
            scening_list.add(Frame(int(match)))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_ses(path: Path, scening_list: SceningList) -> int:
    """
    Imports bookmarks as single-frame scenes
    """
    out_of_range_count = 0

    import pickle

    with path.open('rb') as f:
        try:
            session = pickle.load(f)
        except pickle.UnpicklingError:
            logging.warning('Scening import: failed to load .ses file.')
            return out_of_range_count

    if 'bookmarks' not in session:
        return out_of_range_count

    for bookmark in session['bookmarks']:
        try:
            scening_list.add(Frame(bookmark[0]))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_matroska_timestamps_v1(path: Path, scening_list: SceningList) -> int:
    """
    Imports listed scenes.
    Uses FPS for scene label.
    """
    out_of_range_count = 0

    pattern = re.compile(r'(\d+),(\d+),(\d+(?:\.\d+)?)')

    for match in pattern.finditer(path.read_text('utf8')):
        try:
            scening_list.add(
                Frame(int(match[1])), Frame(int(match[2])), '{:.3f} fps'.format(float(match[3]))
            )
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_matroska_timestamps_v2(path: Path, scening_list: SceningList) -> int:
    """
    Imports intervals of constant FPS as scenes.
    Uses FPS for scene label.
    """
    out_of_range_count = 0

    timestamps = list[Time]()
    for line in path.read_text('utf8').splitlines():
        try:
            timestamps.append(Time(milliseconds=float(line)))
        except ValueError:
            continue

    if len(timestamps) < 2:
        logging.warning(
            "Scening import: timestamps file contains less than 2 timestamps, so there's nothing to import."
        )
        return out_of_range_count

    deltas = [
        timestamps[i] - timestamps[i - 1]
        for i in range(1, len(timestamps))
    ]
    scene_delta = deltas[0]
    scene_start = Frame(0)
    scene_end: Frame | None = None
    for i in range(1, len(deltas)):
        if abs(round(float(deltas[i] - scene_delta), 6)) <= 0.000_001:
            continue
        # TODO: investigate, why offset by -1 is necessary here
        scene_end = Frame(i - 1)
        try:
            scening_list.add(scene_start, scene_end, '{:.3f} fps'.format(1 / float(scene_delta)))
        except ValueError:
            out_of_range_count += 1
        scene_start = Frame(i)
        scene_end = None
        scene_delta = deltas[i]

    if scene_end is None:
        try:
            scening_list.add(
                scene_start, Frame(len(timestamps) - 1),
                '{:.3f} fps'.format(1 / float(scene_delta))
            )
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_matroska_timestamps_v3(path: Path, scening_list: SceningList) -> int:
    """
    Imports listed scenes, ignoring gaps.
    Uses FPS for scene label.
    """
    out_of_range_count = 0

    pattern = re.compile(
        r'^((?:\d+(?:\.\d+)?)|gap)(?:,\s?(\d+(?:\.\d+)?))?',
        re.RegexFlag.MULTILINE
    )

    assume_pattern = re.compile(r'assume (\d+(?:\.\d+))')
    if len(mmatch := assume_pattern.findall(path.read_text('utf8'))) > 0:
        default_fps = float(mmatch[0])
    else:
        logging.warning('Scening import: "assume" entry not found.')
        return out_of_range_count

    pos = Time()
    for match in pattern.finditer(path.read_text('utf8')):
        if match[1] == 'gap':
            pos += Time(seconds=float(match[2]))
            continue

        interval = Time(seconds=float(match[1]))
        fps = float(match[2]) if (match.lastindex or 0) >= 2 else default_fps

        try:
            scening_list.add(Frame(pos), Frame(pos + interval), '{:.3f} fps'.format(fps))
        except ValueError:
            out_of_range_count += 1

        pos += interval

    return out_of_range_count


class TFMFrame(Frame):
    mic: int | None


def import_tfm(path: Path, scening_list: SceningList) -> int:
    """
    Imports TFM's 'OVR HELP INFORMATION'.
    Single combed frames are put into single-frame scenes.
    Frame groups are put into regular scenes.
    Combed probability is used for label.
    """
    out_of_range_count = 0

    tfm_frame_pattern = re.compile(r'(\d+)\s\((\d+)\)')
    tfm_group_pattern = re.compile(r'(\d+),(\d+)\s\((\d+(?:\.\d+)%)\)')

    log = path.read_text('utf8')

    start_pos = log.find('OVR HELP INFORMATION')
    if start_pos == -1:
        logging.warning("Scening import: TFM log doesn't contain OVR Help Information.")
        return out_of_range_count

    log = log[start_pos:]

    tfm_frames = set[TFMFrame]()
    for match in tfm_frame_pattern.finditer(log):
        tfm_frame = TFMFrame(int(match[1]))
        tfm_frame.mic = int(match[2])
        tfm_frames.add(tfm_frame)

    for match in tfm_group_pattern.finditer(log):
        try:
            scene = scening_list.add(Frame(int(match[1])), Frame(int(match[2])), f'{match[3]} combed')
        except ValueError:
            out_of_range_count += 1
            continue

        tfm_frames -= set(range(int(scene.start), int(scene.end) + 1))

    for tfm_frame in tfm_frames:
        try:
            scening_list.add(tfm_frame, label=str(tfm_frame.mic))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_vsedit(path: Path, scening_list: SceningList) -> int:
    """
    Imports bookmarks as single-frame scenes
    """
    out_of_range_count = 0

    frames = []

    for bookmark in path.read_text('utf8').split(', '):
        try:
            frames.append(int(bookmark))
        except ValueError:
            out_of_range_count += 1

    ranges = list[list[int]]()
    prev_x: int = 0
    for x in frames:
        if not ranges:
            ranges.append([x])
        elif x - prev_x == 1:
            ranges[-1].append(x)
        else:
            ranges.append([x])
        prev_x = int(x)

    for rang in ranges:
        scening_list.add(
            Frame(rang[0]),
            Frame(rang[-1]) if len(rang) > 1 else None
        )

    return out_of_range_count


def import_x264_2pass_log(path: Path, scening_list: SceningList) -> int:
    """
    Imports I- and K-frames as single-frame scenes.
    """
    out_of_range_count = 0

    pattern = re.compile(r'in:(\d+).*type:I|K')
    for match in pattern.findall(path.read_text('utf8')):
        try:
            scening_list.add(Frame(int(match)))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_xvid(path: Path, scening_list: SceningList) -> int:
    """
    Imports I-frames as single-frame scenes.
    """
    out_of_range_count = 0

    for i, line in enumerate(path.read_text('utf8').splitlines()):
        if not line.startswith('i'):
            continue
        try:
            scening_list.add(Frame(i - 3))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


def import_generic(path: Path, scening_list: SceningList) -> int:
    """
    Import generic (rfs style) frame mappings: {start end}

    """
    out_of_range_count = 0

    for line in path.read_text('utf8').splitlines():
        try:
            fnumbers = [int(n) for n in line.split()]
            scening_list.add(Frame(fnumbers[0]), Frame(fnumbers[1]))
        except ValueError:
            out_of_range_count += 1

    return out_of_range_count


supported_file_types = {
    'Aegisub Project (*.ass)': import_ass,
    'AvsP Session (*.ses)': import_ses,
    'CUE Sheet (*.cue)': import_cue,
    'DGIndex Project (*.dgi)': import_dgi,
    'IfoEdit Celltimes (*.txt)': import_celltimes,
    'L-SMASH Works Index (*.lwi)': import_lwi,
    'Matroska Timestamps v1 (*.txt)': import_matroska_timestamps_v1,
    'Matroska Timestamps v2 (*.txt)': import_matroska_timestamps_v2,
    'Matroska Timestamps v3 (*.txt)': import_matroska_timestamps_v3,
    'Matroska XML Chapters (*.xml)': import_matroska_xml_chapters,
    'OGM Chapters (*.txt)': import_ogm_chapters,
    'TFM Log (*.txt)': import_tfm,
    'VSEdit Bookmarks (*.bookmarks)': import_vsedit,
    'x264/x265 2 Pass Log (*.log)': import_x264_2pass_log,
    'x264/x265 QP File (*.qp *.txt)': import_qp,
    'XviD Log (*.txt)': import_xvid,
    'Generic Mappings (*.txt)': import_generic,
}
