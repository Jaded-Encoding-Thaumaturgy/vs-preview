from __future__ import annotations

import json
import logging
import re
from bisect import bisect_left
from copy import deepcopy

from jetpytools import CustomRuntimeError, DependencyNotFoundError, SPath

from ...core import Frame, Time
from ...models import SceningList

__all__ = [
    'supported_file_types'
]


def import_ass(path: SPath, scening_list: SceningList) -> int:
    """Imports events as scenes. Event content is ignored."""

    logging.debug(f'Importing ASS file: {path.name}')
    out_of_range_count = 0

    try:
        from pysubs2 import load as pysubs2_load  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        logging.error('Failed to import scenes from ASS file: missing `pysubs2` package')

        raise DependencyNotFoundError('vspreview', 'pysubs2')

    subs = pysubs2_load(str(path))
    logging.debug(f'Loaded {len(subs)} subtitle events')

    for line in subs:
        t_start = Time(milliseconds=line.start)
        t_end = Time(milliseconds=line.end)

        try:
            scening_list.add(Frame(t_start), Frame(t_end))
            logging.debug(f'Added scene: {t_start} -> {t_end}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {t_start} -> {t_end}')

    logging.debug(
        f'ASS import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_celltimes(path: SPath, scening_list: SceningList) -> int:
    """Imports cell times as single-frame scenes."""

    logging.debug(f'Importing celltimes file: {path.name}')
    out_of_range_count = 0

    lines = path.read_text('utf8').splitlines()
    logging.debug(f'Found {len(lines)} cell times')

    for line in lines:
        try:
            frame = Frame(int(line))
            scening_list.add(frame)
            logging.debug(f'Added cell time frame: {frame}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {line}')

    logging.debug(
        f'Celltimes import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_cue(path: SPath, scening_list: SceningList) -> int:
    """Imports tracks as scenes. Uses TITLE for scene label."""

    logging.debug(f'Importing CUE file: {path.name}')
    out_of_range_count = 0

    try:
        from cueparser import CueSheet  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        logging.error('Failed to import scenes from CUE file: missing `cueparser` package')

        raise DependencyNotFoundError('vspreview', 'cueparser')

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
    logging.debug(f'Parsed CUE sheet with {len(cue_sheet.tracks)} tracks')

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
            logging.debug(f'Added track scene: {start} -> {end} (label: {label})')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {start} -> {end}')

    logging.debug(
        f'CUE import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_dgi(path: SPath, scening_list: SceningList) -> int:
    """Imports IDR frames as single-frame scenes."""

    logging.debug(f'Importing DGI file: {path.name}')
    out_of_range_count = 0

    pattern = re.compile(r'IDR\s\d+\n(\d+):FRM', re.RegexFlag.MULTILINE)
    matches = pattern.findall(path.read_text('utf8'))
    logging.debug(f'Found {len(matches)} IDR frames')

    for match in matches:
        try:
            frame = Frame(int(match))
            scening_list.add(frame)
            logging.debug(f'Added IDR frame: {frame}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {match}')

    logging.debug(
        f'DGI import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_lwi(path: SPath, scening_list: SceningList) -> int:
    """
    Imports Key=1 frames as single-frame scenes.
    Ignores everything besides Index=0 video stream.
    """

    logging.debug(f'Importing LWI file: {path.name}')
    out_of_range_count = 0

    AV_CODEC_ID_FIRST_AUDIO = 0x10000
    STREAM_INDEX = 0
    IS_KEY = 1

    pattern = re.compile(r'Index={}.*?Codec=(\d+).*?\n.*?Key=(\d)'.format(
        STREAM_INDEX
    ))

    frame = Frame(0)
    key_frames_found = 0

    for match in pattern.finditer(path.read_text('utf8'), re.RegexFlag.MULTILINE):
        if int(match[1]) >= AV_CODEC_ID_FIRST_AUDIO:
            frame += Frame(1)
            continue

        if not int(match[2]) == IS_KEY:
            frame += Frame(1)
            continue

        try:
            scening_list.add(deepcopy(frame))
            logging.debug(f'Added key frame: {frame}')
            key_frames_found += 1
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {frame}')

        frame += Frame(1)

    logging.debug(
        f'LWI import complete. Found {key_frames_found} key frames, '
        f'{out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_matroska_xml_chapters(path: SPath, scening_list: SceningList) -> int:
    """
    Imports chapters as scenes.
    Preserve end time and text if they're present.
    """

    logging.debug(f'Importing Matroska XML chapters: {path.name}')
    from xml.etree import ElementTree
    out_of_range_count = 0

    timestamp_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}(?:\.\d{3})?)')

    try:
        root = ElementTree.parse(str(path)).getroot()
        chapters = list(root.iter('ChapterAtom'))
        logging.debug(f'Found {len(chapters)} chapters')
    except ElementTree.ParseError as exc:
        logging.warning(f"Scening import: error occurred while parsing '{path.name}':")
        logging.warning(exc.msg)
        return out_of_range_count

    for chapter in chapters:
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
            logging.debug(f'Added chapter scene: {start} -> {end} (label: {label})')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {start} -> {end}')

    logging.debug(
        f'Matroska XML chapters import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_ogm_chapters(path: SPath, scening_list: SceningList) -> int:
    """Imports chapters as single-frame scenes. Uses NAME for scene label."""

    logging.debug(f'Importing OGM chapters: {path.name}')
    out_of_range_count = 0

    pattern = re.compile(
        r'(CHAPTER\d+)=(\d+):(\d+):(\d+(?:\.\d+)?)\n\1NAME=(.*)',
        re.RegexFlag.MULTILINE
    )

    matches = list(pattern.finditer(path.read_text('utf8')))
    logging.debug(f'Found {len(matches)} OGM chapters')

    for match in matches:
        time = Time(hours=int(match[2]), minutes=int(match[3]), seconds=float(match[4]))

        try:
            scening_list.add(Frame(time), label=match[5])
            logging.debug(f'Added OGM chapter: {time} (label: {match[5]})')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {time}')

    logging.debug(
        f'OGM chapters import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_qp(path: SPath, scening_list: SceningList) -> int:
    """Imports I- and K-frames as single-frame scenes."""

    logging.debug(f'Importing QP file: {path.name}')
    out_of_range_count = 0

    pattern = re.compile(r'(\d+)\sI|K')
    matches = pattern.findall(path.read_text('utf8'))
    logging.debug(f'Found {len(matches)} I/K frames')

    for match in matches:
        try:
            frame = Frame(int(match))
            scening_list.add(frame)
            logging.debug(f'Added I/K frame: {frame}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {match}')

    logging.debug(
        f'QP import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_ses(path: SPath, scening_list: SceningList) -> int:
    """Imports bookmarks as single-frame scenes."""

    logging.debug(f'Importing SES file: {path.name}')
    out_of_range_count = 0

    import pickle

    with path.open('rb') as f:
        try:
            session = pickle.load(f)
            logging.debug('Successfully loaded session data')
        except pickle.UnpicklingError:
            logging.warning('Scening import: failed to load .ses file.')
            return out_of_range_count

    if 'bookmarks' not in session:
        logging.debug('No bookmarks found in session')
        return out_of_range_count

    bookmarks = session['bookmarks']
    logging.debug(f'Found {len(bookmarks)} bookmarks')

    for bookmark in bookmarks:
        try:
            frame = Frame(bookmark[0])
            scening_list.add(frame)
            logging.debug(f'Added bookmark frame: {frame}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {bookmark[0]}')

    logging.debug(
        f'SES import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_matroska_timestamps_v1(path: SPath, scening_list: SceningList) -> int:
    """Imports listed scenes. Uses FPS for scene label."""

    logging.debug(f'Importing Matroska timestamps v1: {path.name}')
    out_of_range_count = 0

    pattern = re.compile(r'(\d+),(\d+),(\d+(?:\.\d+)?)')
    matches = list(pattern.finditer(path.read_text('utf8')))
    logging.debug(f'Found {len(matches)} timestamp entries')

    for match in matches:
        try:
            start = Frame(int(match[1]))
            end = Frame(int(match[2]))
            fps = float(match[3])
            scening_list.add(start, end, '{:.3f} fps'.format(fps))
            logging.debug(f'Added timestamp scene: {start} -> {end} ({fps:.3f} fps)')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {match[1]} -> {match[2]}')

    logging.debug(
        f'Matroska timestamps v1 import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_matroska_timestamps_v2(path: SPath, scening_list: SceningList) -> int:
    """Imports intervals of constant FPS as scenes. Uses FPS for scene label."""

    logging.debug(f'Importing Matroska timestamps v2: {path.name}')
    out_of_range_count = 0

    timestamps = list[Time]()
    lines = path.read_text('utf8').splitlines()
    logging.debug(f'Found {len(lines)} timestamp lines')

    for line in lines:
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
    logging.debug(f'Calculated {len(deltas)} frame deltas')

    scene_delta = deltas[0]
    scene_start = Frame(0)
    scene_end: Frame | None = None
    scenes_found = 0

    for i in range(1, len(deltas)):
        if abs(round(float(deltas[i] - scene_delta), 6)) <= 0.000_001:
            continue

        # TODO: investigate, why offset by -1 is necessary here
        scene_end = Frame(i - 1)

        try:
            scening_list.add(scene_start, scene_end, '{:.3f} fps'.format(1 / float(scene_delta)))
            logging.debug(f'Added FPS scene: {scene_start} -> {scene_end} ({1/float(scene_delta):.3f} fps)')
            scenes_found += 1
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {scene_start} -> {scene_end}')

        scene_start = Frame(i)
        scene_end = None
        scene_delta = deltas[i]

    if scene_end is None:
        try:
            scening_list.add(
                scene_start, Frame(len(timestamps) - 1),
                '{:.3f} fps'.format(1 / float(scene_delta))
            )
            logging.debug(f'Added final FPS scene: {scene_start} -> {len(timestamps)-1} ({1/float(scene_delta):.3f} fps)')
            scenes_found += 1
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {scene_start} -> {len(timestamps)-1}')

    logging.debug(
        f'Matroska timestamps v2 import complete. Found {scenes_found} scenes, '
        f'{out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_matroska_timestamps_v3(path: SPath, scening_list: SceningList) -> int:
    """Imports listed scenes, ignoring gaps. Uses FPS for scene label."""

    logging.debug(f'Importing Matroska timestamps v3: {path.name}')
    out_of_range_count = 0

    pattern = re.compile(
        r'^((?:\d+(?:\.\d+)?)|gap)(?:,\s?(\d+(?:\.\d+)?))?',
        re.RegexFlag.MULTILINE
    )

    assume_pattern = re.compile(r'assume (\d+(?:\.\d+))')

    if len(mmatch := assume_pattern.findall(path.read_text('utf8'))) > 0:
        default_fps = float(mmatch[0])
        logging.debug(f'Found default FPS: {default_fps:.3f}')
    else:
        logging.warning('Scening import: "assume" entry not found.')
        return out_of_range_count

    pos = Time()
    scenes_found = 0

    for match in pattern.finditer(path.read_text('utf8')):
        if match[1] == 'gap':
            gap_duration = float(match[2])
            pos += Time(seconds=gap_duration)
            logging.debug(f'Found gap of {gap_duration:.3f} seconds')
            continue

        interval = Time(seconds=float(match[1]))
        fps = float(match[2]) if (match.lastindex or 0) >= 2 else default_fps

        try:
            scening_list.add(Frame(pos), Frame(pos + interval), '{:.3f} fps'.format(fps))
            logging.debug(f'Added scene: {pos} -> {pos + interval} ({fps:.3f} fps)')
            scenes_found += 1
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {pos} -> {pos + interval}')

        pos += interval

    logging.debug(
        f'Matroska timestamps v3 import complete. Found {scenes_found} scenes, '
        f'{out_of_range_count} frames out of range'
    )

    return out_of_range_count


class TFMFrame(Frame):
    mic: int | None


def import_tfm(path: SPath, scening_list: SceningList) -> int:
    """
    Imports TFM's 'OVR HELP INFORMATION'.
    Single combed frames are put into single-frame scenes. Frame groups are put into regular scenes.
    Combed probability is used for label.
    """

    logging.debug(f'Importing TFM log: {path.name}')
    out_of_range_count = 0

    tfm_frame_pattern = re.compile(r'(\d+)\s\((\d+)\)')
    tfm_group_pattern = re.compile(r'(\d+),(\d+)\s\((\d+(?:\.\d+)%)\)')

    log = path.read_text('utf8')

    start_pos = log.find('OVR HELP INFORMATION')

    if start_pos == -1:
        logging.warning("Scening import: TFM log doesn't contain OVR Help Information.")
        return out_of_range_count

    log = log[start_pos:]
    logging.debug('Found OVR HELP INFORMATION section')

    tfm_frames = set[TFMFrame]()
    single_frames_found = 0

    for match in tfm_frame_pattern.finditer(log):
        tfm_frame = TFMFrame(int(match[1]))
        tfm_frame.mic = int(match[2])
        tfm_frames.add(tfm_frame)
        single_frames_found += 1

    logging.debug(f'Found {single_frames_found} single combed frames')

    group_frames_found = 0
    for match in tfm_group_pattern.finditer(log):
        try:
            scene = scening_list.add(Frame(int(match[1])), Frame(int(match[2])), f'{match[3]} combed')
            logging.debug(f'Added combed group: {scene.start} -> {scene.end} ({match[3]} combed)')
            group_frames_found += 1
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {match[1]} -> {match[2]}')
            continue

        tfm_frames -= set(range(int(scene.start), int(scene.end) + 1))

    logging.debug(f'Found {group_frames_found} combed frame groups')

    for tfm_frame in tfm_frames:
        try:
            scening_list.add(tfm_frame, label=str(tfm_frame.mic))
            logging.debug(f'Added single combed frame: {tfm_frame} (MIC: {tfm_frame.mic})')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {tfm_frame}')

    logging.debug(
        f'TFM import complete. Found {single_frames_found} single frames and {group_frames_found} groups, '
        f'{out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_vsedit(path: SPath, scening_list: SceningList) -> int:
    """Imports bookmarks as single-frame scenes."""

    logging.debug(f'Importing VSEdit bookmarks: {path.name}')
    out_of_range_count = 0

    frames = []
    text = path.read_text('utf8')
    logging.debug(f'Read {len(text)} bytes from file')

    for bookmark in text.split(', '):
        try:
            frames.append(int(bookmark))
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Invalid bookmark value: {bookmark}')

    logging.debug(f'Found {len(frames)} valid bookmarks')

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

    logging.debug(f'Grouped bookmarks into {len(ranges)} ranges')

    for rang in ranges:
        try:
            scening_list.add(
                Frame(rang[0]),
                Frame(rang[-1]) if len(rang) > 1 else None
            )
            if len(rang) > 1:
                logging.debug(f'Added bookmark range: {rang[0]} -> {rang[-1]}')
            else:
                logging.debug(f'Added single bookmark: {rang[0]}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {rang[0]} -> {rang[-1] if len(rang) > 1 else None}')

    logging.debug(
        f'VSEdit import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_x264_2pass_log(path: SPath, scening_list: SceningList) -> int:
    """Imports I- and K-frames as single-frame scenes."""

    logging.debug(f'Importing x264/x265 2-pass log: {path.name}')
    out_of_range_count = 0

    pattern = re.compile(r'in:(\d+).*type:I|K')
    matches = pattern.findall(path.read_text('utf8'))
    logging.debug(f'Found {len(matches)} I/K frames')

    for match in matches:
        try:
            frame = Frame(int(match))
            scening_list.add(frame)
            logging.debug(f'Added I/K frame: {frame}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {match}')

    logging.debug(
        f'x264/x265 2-pass log import complete. {out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_xvid(path: SPath, scening_list: SceningList) -> int:
    """Imports I-frames as single-frame scenes."""

    logging.debug(f'Importing XviD log: {path.name}')
    out_of_range_count = 0

    lines = path.read_text('utf8').splitlines()
    logging.debug(f'Read {len(lines)} lines from file')

    i_frames_found = 0
    for i, line in enumerate(lines):
        if not line.startswith('i'):
            continue
        try:
            frame = Frame(i - 3)
            scening_list.add(frame)
            logging.debug(f'Added I-frame: {frame}')
            i_frames_found += 1
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {i - 3}')

    logging.debug(
        f'XviD log import complete. Found {i_frames_found} I-frames, '
        f'{out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_generic(path: SPath, scening_list: SceningList) -> int:
    """Import generic (rfs style) frame mappings: {start end}."""

    logging.debug(f'Importing generic frame mappings: {path.name}')
    out_of_range_count = 0

    lines = path.read_text('utf8').splitlines()
    logging.debug(f'Read {len(lines)} lines from file')

    mappings_found = 0
    for line in lines:
        try:
            fnumbers = [int(n) for n in line.split()]
            scening_list.add(Frame(fnumbers[0]), Frame(fnumbers[1]))
            logging.debug(f'Added frame mapping: {fnumbers[0]} -> {fnumbers[1]}')
            mappings_found += 1
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Invalid mapping or frame out of range: {line}')

    logging.debug(
        f'Generic import complete. Found {mappings_found} mappings, '
        f'{out_of_range_count} frames out of range'
    )

    return out_of_range_count


def import_wobbly(path: SPath, scening_list: SceningList) -> int:
    """
    Imports sections from a Wobbly file as scenes.
    End frames of each scene are obtained from the next section's start frame.
    The final scene's end frame is the trim end.
    """

    logging.debug(f'Importing wobbly file: {path.name}')
    out_of_range_count = 0

    try:
        wobbly_data = dict(json.loads(path.read_text('utf8')))
        logging.debug(f'Successfully loaded wobbly file: {path.name}')
    except json.JSONDecodeError as e:
        err_msg = f'Scening import: Failed to decode the wobbly file, \'{path.name}\''
        logging.warning(f'{err_msg}:\n{str(e)}')

        raise CustomRuntimeError(err_msg, import_wobbly)

    if not (sections := wobbly_data.get('sections', [])):
        logging.warning('Scening import: No sections found in wobbly file')

        return 0

    if (missing_starts := [i for i, s in enumerate(sections) if not isinstance(s, int) and 'start' not in s]):
        logging.warning(f'Scening import: Sections missing start frames at indices: {missing_starts}')

        raise CustomRuntimeError(f'Scening import: Sections missing start frames at indices: {missing_starts}', import_wobbly)

    start_frames = [dict(s).get('start', 0) for s in sections]
    logging.debug(f'Found {len(start_frames)} section start frames')

    trim = wobbly_data.get('trim', [0, start_frames[-1]])
    end_frames = start_frames[1:] + [trim[1]]
    logging.debug(f'Generated {len(end_frames)} section end frames')

    if not (decimations := wobbly_data.get('decimated frames', {})):
        logging.debug('No decimation data found, using raw frame numbers')
        for start, end in zip(start_frames, end_frames):
            try:
                scening_list.add(Frame(start), Frame(end))
                logging.debug(f'Added scene: {start} -> {end}')
            except ValueError:
                out_of_range_count += 1
                logging.debug(f'Frame out of range: {start} -> {end}')

        return out_of_range_count

    sorted_decimations = sorted(decimations)
    logging.debug(f'Found {len(sorted_decimations)} decimated frames')

    for start, end in zip(start_frames, end_frames):
        try:
            adjusted_start = start - bisect_left(sorted_decimations, start)
            adjusted_end = end - bisect_left(sorted_decimations, end)
            scening_list.add(Frame(adjusted_start), Frame(adjusted_end))
            logging.debug(f'Added decimation-adjusted scene: {adjusted_start} -> {adjusted_end}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {start} -> {end}')

    return out_of_range_count


def import_wobbly_sections(path: SPath, scening_list: SceningList) -> int:
    """Imports section start frames from a Wobbly sections file as single-frame scenes."""

    logging.debug(f'Importing wobbly sections file: {path.name}')
    out_of_range_count = 0

    try:
        sections = [int(line) for line in path.read_text('utf8').splitlines() if line.strip()]
        logging.debug(f'Successfully loaded wobbly sections file: {path.name}')
    except ValueError as e:
        err_msg = f'Scening import: Failed to parse the wobbly sections file, \'{path.name}\''
        logging.warning(f'{err_msg}:\n{str(e)}')

        raise CustomRuntimeError(err_msg, import_wobbly_sections)

    if not sections:
        logging.warning('Scening import: No sections found in wobbly sections file')

        return 0

    out_of_range_count = 0

    for frame in sections:
        try:
            scening_list.add(Frame(frame))
            logging.debug(f'Added section frame: {frame}')
        except ValueError:
            out_of_range_count += 1
            logging.debug(f'Frame out of range: {frame}')

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
    'Wobbly File (*.wob)': import_wobbly,
    'Wobbly Sections (*.txt)': import_wobbly_sections,
    'x264/x265 2 Pass Log (*.log)': import_x264_2pass_log,
    'x264/x265 QP File (*.qp *.txt)': import_qp,
    'XviD Log (*.txt)': import_xvid,
    'Generic Mappings (*.txt)': import_generic,
}
