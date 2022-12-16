from __future__ import annotations

import logging
import re
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any, Callable, Mapping, cast

from PyQt6.QtCore import QModelIndex, Qt, QKeyCombination
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QLabel

from ...core import (
    AbstractMainWindow, AbstractToolbar, CheckBox, Frame, HBoxLayout, LineEdit, PushButton, Time, try_load
)
from ...core.custom import ComboBox
from ...main.timeline import Notches
from ...models import SceningList, SceningLists
from ...utils import fire_and_forget, set_status_label
from .dialog import SceningListDialog
from .settings import SceningSettings


class SceningToolbar(AbstractToolbar):
    storable_attrs = ('current_list_index', 'lists', 'first_frame', 'second_frame')

    __slots__ = (
        *storable_attrs[1:],
        'export_template_pattern', 'export_template_scenes_pattern',
        'scening_list_dialog', 'supported_file_types',
        'add_list_button', 'remove_list_button', 'view_list_button',
        'toggle_first_frame_button', 'toggle_second_frame_button',
        'add_single_frame_button',
        'add_to_list_button', 'remove_last_from_list_button',
        'export_multiline_button', 'export_template_lineedit',
        'always_show_scene_marks_checkbox',
        'status_label', 'import_file_button', 'items_combobox',
        'remove_at_current_frame_button',
        'seek_to_next_button', 'seek_to_prev_button'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, SceningSettings())
        self.setup_ui()

        self.lists = SceningLists()

        self.first_frame: Frame | None = None
        self.second_frame: Frame | None = None
        self.export_template_pattern = re.compile(r'.*(?:{start}|{end}|{label}).*')
        self.export_template_scenes_pattern = re.compile(r'.+')

        self.items_combobox.setModel(self.lists)
        self.scening_update_status_label()
        self.scening_list_dialog = SceningListDialog(self.main)

        self.supported_file_types = {
            'Aegisub Project (*.ass)': self.import_ass,
            'AvsP Session (*.ses)': self.import_ses,
            'CUE Sheet (*.cue)': self.import_cue,
            'DGIndex Project (*.dgi)': self.import_dgi,
            'IfoEdit Celltimes (*.txt)': self.import_celltimes,
            'L-SMASH Works Index (*.lwi)': self.import_lwi,
            'Matroska Timestamps v1 (*.txt)': self.import_matroska_timestamps_v1,
            'Matroska Timestamps v2 (*.txt)': self.import_matroska_timestamps_v2,
            'Matroska Timestamps v3 (*.txt)': self.import_matroska_timestamps_v3,
            'Matroska XML Chapters (*.xml)': self.import_matroska_xml_chapters,
            'OGM Chapters (*.txt)': self.import_ogm_chapters,
            'TFM Log (*.txt)': self.import_tfm,
            'VSEdit Bookmarks (*.bookmarks)': self.import_vsedit,
            'x264/x265 2 Pass Log (*.log)': self.import_x264_2pass_log,
            'x264/x265 QP File (*.qp *.txt)': self.import_qp,
            'XviD Log (*.txt)': self.import_xvid,
            'Generic Mappings (*.txt)': self.import_generic,
        }

        self.items_combobox.valueChanged.connect(self.on_current_list_changed)
        self.add_list_button.clicked.connect(self.on_add_list_clicked)
        self.remove_list_button.clicked.connect(self.on_remove_list_clicked)
        self.view_list_button.clicked.connect(self.on_view_list_clicked)
        self.import_file_button.clicked.connect(self.on_import_file_clicked)
        self.seek_to_prev_button.clicked.connect(self.on_seek_to_prev_clicked)
        self.seek_to_next_button.clicked.connect(self.on_seek_to_next_clicked)

        self.add_single_frame_button.clicked.connect(self.on_add_single_frame_clicked)
        self.toggle_first_frame_button.clicked.connect(self.on_first_frame_clicked)
        self.toggle_second_frame_button.clicked.connect(self.on_second_frame_clicked)
        self.add_to_list_button.clicked.connect(self.on_add_to_list_clicked)
        self.remove_last_from_list_button.clicked.connect(self.on_remove_last_from_list_clicked)
        self.remove_at_current_frame_button.clicked.connect(self.on_remove_at_current_frame_clicked)
        self.export_template_lineedit.textChanged.connect(self.check_remove_export_possibility)
        self.export_multiline_button.clicked.connect(self.export_multiline)

        self.add_shortcuts()

        # FIXME: get rid of workaround
        self._on_list_items_changed = lambda *arg: self.on_list_items_changed(*arg)

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.items_combobox = ComboBox[SceningList](duplicatesEnabled=True, minimumContentsLength=4)

        self.add_list_button = PushButton('Add List')

        self.remove_list_button = PushButton('Remove List', enabled=False)

        self.view_list_button = PushButton('View List', enabled=False)

        self.import_file_button = PushButton('Import List')

        self.seek_to_prev_button = PushButton('⏪', enabled=False)

        self.seek_to_next_button = PushButton('⏩', enabled=False)

        self.always_show_scene_marks_checkbox = CheckBox('Always show scene marks in the timeline', checked=False)

        self.add_single_frame_button = PushButton('🆎', tooltip='Add Single Frame Scene')

        self.toggle_first_frame_button = PushButton('🅰️', tooltip='Toggle Start of New Scene', checkable=True)

        self.toggle_second_frame_button = PushButton('🅱️', tooltip='Toggle End of New Scene', checkable=True)

        self.label_lineedit = LineEdit(placeholder='New Scene Label')

        self.add_to_list_button = PushButton('Add to List', enabled=False)

        self.remove_last_from_list_button = PushButton('Remove Last', enabled=False)

        self.remove_at_current_frame_button = PushButton('Remove at Current Frame', enabled=False)

        self.export_template_lineedit = LineEdit(
            text=self.settings.default_export_template,
            placeholderText='Export Template',
            tooltip=(
                r'Use {start} and {end} as placeholders.'
                r'Both are valid for single frame scenes. '
                r'{label} is available, too. '
            )
        )

        self.export_multiline_button = PushButton('Export Multiline', enabled=False)

        HBoxLayout(self.vlayout, [
            self.items_combobox,
            self.add_list_button,
            self.remove_list_button,
            self.view_list_button,
            self.import_file_button,
            self.get_separator(),
            self.seek_to_prev_button,
            self.seek_to_next_button,
            self.always_show_scene_marks_checkbox
        ]).addStretch()

        HBoxLayout(self.vlayout, [
            self.add_single_frame_button,
            self.toggle_first_frame_button,
            self.toggle_second_frame_button,
            self.label_lineedit,
            self.add_to_list_button,
            self.remove_last_from_list_button,
            self.remove_at_current_frame_button,
            self.get_separator(),
            self.export_template_lineedit,
            self.export_multiline_button
        ]).addStretch(2)

        # statusbar label
        self.status_label = QLabel(self)
        self.status_label.setVisible(False)
        self.main.statusbar.addPermanentWidget(self.status_label)

    def add_shortcuts(self) -> None:
        for i, key in enumerate(self.num_keys[:-2]):
            self.add_shortcut(QKeyCombination(Qt.SHIFT, key), partial(self.switch_list, i))

        self.add_shortcut(
            QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Space).toCombined(), self.on_toggle_single_frame
        )
        self.add_shortcut(
            QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Left).toCombined(), self.seek_to_prev_button.click
        )
        self.add_shortcut(
            QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Right).toCombined(), self.seek_to_next_button.click
        )
        if self.main.settings.azerty_keybinds:
            self.add_shortcut(Qt.Key.Key_A, self.toggle_first_frame_button.click)
            self.add_shortcut(Qt.Key.Key_Z, self.toggle_second_frame_button.click)
        else:
            self.add_shortcut(Qt.Key.Key_Q, self.toggle_first_frame_button.click)
            self.add_shortcut(Qt.Key.Key_W, self.toggle_second_frame_button.click)
        self.add_shortcut(Qt.Key.Key_E, self.add_to_list_button.click)
        self.add_shortcut(Qt.Key.Key_R, self.remove_last_from_list_button.click)
        self.add_shortcut(
            QKeyCombination(Qt.Modifier.SHIFT, Qt.Key.Key_R).toCombined(), self.remove_at_current_frame_button.click
        )
        self.add_shortcut(
            Qt.Key.Key_B, lambda: self.scening_list_dialog.label_lineedit.setText(
                str(self.main.current_output.last_showed_frame)
            )
        )

    def on_toggle(self, new_state: bool) -> None:
        if new_state is True:
            self.check_add_to_list_possibility()
            self.check_remove_export_possibility()

        self.status_label.setVisible(self.is_notches_visible())
        super().on_toggle(new_state)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        self.scening_list_dialog.on_current_output_changed(index, prev_index)

    def on_current_frame_changed(self, frame: Frame) -> None:
        self.check_remove_export_possibility()
        self.scening_list_dialog.on_current_frame_changed(frame, Time(frame))

    def get_notches(self) -> Notches:
        marks = Notches()
        if self.current_list is None:
            return marks
        for scene in self.current_list:
            marks.add(scene, cast(QColor, Qt.green))
        return marks

    @property
    def current_list(self) -> SceningList | None:
        return self.items_combobox.currentValue()

    @current_list.setter
    def current_list(self, item: SceningList) -> None:
        self.items_combobox.setCurrentValue(item)

    @property
    def current_list_index(self) -> int:
        return self.items_combobox.currentIndex()

    @current_list_index.setter
    def current_list_index(self, index: int) -> None:
        if (0 <= index < len(self.lists)):
            return self.items_combobox.setCurrentIndex(index)
        raise IndexError

    def is_notches_visible(self) -> bool:
        return self.always_show_scene_marks_checkbox.isChecked() or self.toggle_button.isChecked()

    # list management
    def on_add_list_clicked(self, checked: bool | None = None) -> None:
        _, self.current_list_index = self.lists.add()

    def on_current_list_changed(self, new_value: SceningList | None, old_value: SceningList) -> None:
        if new_value is not None:
            self.remove_list_button.setEnabled(True)
            self.view_list_button.setEnabled(True)
            new_value.rowsInserted.connect(self._on_list_items_changed)
            new_value.rowsRemoved.connect(self._on_list_items_changed)
            new_value.dataChanged.connect(self._on_list_items_changed)
            self.scening_list_dialog.on_current_list_changed(new_value)
        else:
            self.remove_list_button.setEnabled(False)
            self.view_list_button.setEnabled(False)

        if old_value is not None:
            try:
                old_value.rowsInserted.disconnect(self._on_list_items_changed)
                old_value.rowsRemoved.disconnect(self._on_list_items_changed)
                old_value.dataChanged.disconnect(self._on_list_items_changed)
            except (IndexError, TypeError):
                pass

        self.check_add_to_list_possibility()
        self.check_remove_export_possibility()
        self.notches_changed.emit(self)

    def on_list_items_changed(self, parent: QModelIndex, first: int, last: int) -> None:
        self.notches_changed.emit(self)

    def on_remove_list_clicked(self, checked: bool | None = None) -> None:
        self.lists.remove(self.current_list_index)

        if len(self.lists) == 0:
            self.remove_list_button.setEnabled(False)
            self.view_list_button.setEnabled(False)

    def on_view_list_clicked(self, checked: bool | None = None) -> None:
        self.scening_list_dialog.show()

    def switch_list(self, index: int) -> None:
        try:
            self.current_list_index = index
        except IndexError:
            pass

    # seeking
    def on_seek_to_prev_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        new_pos = self.current_list.get_prev_frame(self.main.current_output.last_showed_frame)
        if new_pos is None:
            return
        self.main.switch_frame(new_pos)

    def on_seek_to_next_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        new_pos = self.current_list.get_next_frame(self.main.current_output.last_showed_frame)
        if new_pos is None:
            return
        self.main.switch_frame(new_pos)

    # scene management
    def on_add_single_frame_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            self.on_add_list_clicked()
        cast(SceningList, self.current_list).add(self.main.current_output.last_showed_frame)
        self.check_remove_export_possibility()

    def on_add_to_list_clicked(self, checked: bool | None = None) -> None:
        self.current_list.add(self.first_frame, self.second_frame, self.label_lineedit.text())

        if self.toggle_first_frame_button.isChecked():
            self.toggle_first_frame_button.click()
        if self.toggle_second_frame_button.isChecked():
            self.toggle_second_frame_button.click()
        self.add_to_list_button.setEnabled(False)
        self.label_lineedit.setText('')

        self.check_remove_export_possibility()

    def on_first_frame_clicked(self, checked: bool, frame: Frame | None = None) -> None:
        if frame is None:
            frame = self.main.current_output.last_showed_frame

        if checked:
            self.first_frame = frame
        else:
            self.first_frame = None
        self.scening_update_status_label()
        self.check_add_to_list_possibility()

    def on_remove_at_current_frame_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        curr = self.main.current_output.last_showed_frame

        for scene in self.current_list:
            if (scene.start == curr or scene.end == curr):
                self.current_list.remove(scene)

        self.remove_at_current_frame_button.clearFocus()
        self.check_remove_export_possibility()

    def on_remove_last_from_list_clicked(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        self.current_list.remove(self.current_list[-1])
        self.remove_last_from_list_button.clearFocus()
        self.check_remove_export_possibility()

    def on_second_frame_clicked(self, checked: bool, frame: Frame | None = None) -> None:
        if frame is None:
            frame = self.main.current_output.last_showed_frame

        if checked:
            self.second_frame = frame
        else:
            self.second_frame = None
        self.scening_update_status_label()
        self.check_add_to_list_possibility()

    def on_toggle_single_frame(self) -> None:
        if self.add_single_frame_button.isEnabled():
            self.add_single_frame_button.click()
        elif self.remove_at_current_frame_button.isEnabled():
            self.remove_at_current_frame_button.click()

    # import
    def on_import_file_clicked(self, checked: bool | None = None) -> None:
        filter_str = ';;'.join(self.supported_file_types.keys())
        path_strs, file_type = QFileDialog.getOpenFileNames(
            self.main, caption='Open chapters file', filter=filter_str
        )

        paths = [Path(path_str) for path_str in path_strs]
        for path in paths:
            self.import_file(self.supported_file_types[file_type], path)

    @fire_and_forget
    @set_status_label('Importing scening list')
    def import_file(self, import_func: Callable[[Path, SceningList, int], None], path: Path) -> None:
        out_of_range_count = 0
        scening_list, scening_list_index = self.lists.add(path.stem)

        import_func(path, scening_list, out_of_range_count)

        if out_of_range_count > 0:
            logging.warning(
                f'Scening import: {out_of_range_count} scenes were out of range of output, so they were dropped.')
        if len(scening_list) == 0:
            logging.warning(f"Scening import: nothing was imported from '{path.name}'.")
            self.lists.remove(scening_list_index)
        else:
            self.current_list_index = scening_list_index

    def import_ass(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports lines as scenes.
        Text is ignored.
        '''
        try:
            from pysubs2 import load as pysubs2_load  # type: ignore[import]
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

    def import_celltimes(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports cell times as single-frame scenes
        '''

        for line in path.read_text().splitlines():
            try:
                scening_list.add(Frame(int(line)))
            except ValueError:
                out_of_range_count += 1

    def import_cue(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports tracks as scenes.
        Uses TITLE for scene label.
        '''
        try:
            from cueparser import CueSheet  # type: ignore[import]
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
        cue_sheet.setData(path.read_text())
        cue_sheet.parse()

        for track in cue_sheet.tracks:
            if track.offset is None:
                continue
            offset = offset_to_time(track.offset)
            if offset is None:
                logging.warning(f"Scening import: INDEX timestamp '{track.offset}' format isn't suported.")
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

    def import_dgi(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports IDR frames as single-frame scenes.
        '''
        pattern = re.compile(r'IDR\s\d+\n(\d+):FRM', re.RegexFlag.MULTILINE)
        for match in pattern.findall(path.read_text()):
            try:
                scening_list.add(Frame(match))
            except ValueError:
                out_of_range_count += 1

    def import_lwi(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports Key=1 frames as single-frame scenes.
        Ignores everything besides Index=0 video stream.
        '''
        AV_CODEC_ID_FIRST_AUDIO = 0x10000
        STREAM_INDEX = 0
        IS_KEY = 1

        pattern = re.compile(r'Index={}.*?Codec=(\d+).*?\n.*?Key=(\d)'.format(
            STREAM_INDEX
        ))

        frame = Frame(0)
        for match in pattern.finditer(path.read_text(), re.RegexFlag.MULTILINE):
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

    def import_matroska_xml_chapters(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports chapters as scenes.
        Preserve end time and text if they're present.
        '''
        from xml.etree import ElementTree

        timestamp_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}(?:\.\d{3})?)')

        try:
            root = ElementTree.parse(str(path)).getroot()
        except ElementTree.ParseError as exc:
            logging.warning(f"Scening import: error occured while parsing '{path.name}':")
            logging.warning(exc.msg)
            return
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

    def import_ogm_chapters(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports chapters as signle-frame scenes.
        Uses NAME for scene label.
        '''
        pattern = re.compile(
            r'(CHAPTER\d+)=(\d{2}):(\d{2}):(\d{2}(?:\.\d{3})?)\n\1NAME=(.*)',
            re.RegexFlag.MULTILINE
        )
        for match in pattern.finditer(path.read_text()):
            time = Time(hours=int(match[2]), minutes=int(match[3]), seconds=float(match[4]))
            try:
                scening_list.add(Frame(time), label=match[5])
            except ValueError:
                out_of_range_count += 1

    def import_qp(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports I- and K-frames as single-frame scenes.
        '''
        pattern = re.compile(r'(\d+)\sI|K')
        for match in pattern.findall(path.read_text()):
            try:
                scening_list.add(Frame(int(match)))
            except ValueError:
                out_of_range_count += 1

    def import_ses(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports bookmarks as single-frame scenes
        '''
        import pickle

        with path.open('rb') as f:
            try:
                session = pickle.load(f)
            except pickle.UnpicklingError:
                logging.warning('Scening import: failed to load .ses file.')
                return
        if 'bookmarks' not in session:
            return

        for bookmark in session['bookmarks']:
            try:
                scening_list.add(Frame(bookmark[0]))
            except ValueError:
                out_of_range_count += 1

    def import_matroska_timestamps_v1(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports listed scenes.
        Uses FPS for scene label.
        '''
        pattern = re.compile(r'(\d+),(\d+),(\d+(?:\.\d+)?)')

        for match in pattern.finditer(path.read_text()):
            try:
                scening_list.add(
                    Frame(int(match[1])), Frame(int(match[2])), '{:.3f} fps'.format(float(match[3]))
                )
            except ValueError:
                out_of_range_count += 1

    def import_matroska_timestamps_v2(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports intervals of constant FPS as scenes.
        Uses FPS for scene label.
        '''
        timestamps = list[Time]()
        for line in path.read_text().splitlines():
            try:
                timestamps.append(Time(milliseconds=float(line)))
            except ValueError:
                continue

        if len(timestamps) < 2:
            logging.warning(
                "Scening import: timestamps file contains less than 2 timestamps, so there's nothing to import."
            )
            return

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

    def import_matroska_timestamps_v3(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports listed scenes, ignoring gaps.
        Uses FPS for scene label.
        '''
        pattern = re.compile(
            r'^((?:\d+(?:\.\d+)?)|gap)(?:,\s?(\d+(?:\.\d+)?))?',
            re.RegexFlag.MULTILINE
        )

        assume_pattern = re.compile(r'assume (\d+(?:\.\d+))')
        if len(match := assume_pattern.findall(path.read_text())) > 0:
            default_fps = float(match[0])
        else:
            logging.warning('Scening import: "assume" entry not found.')
            return

        pos = Time()
        for match in pattern.finditer(path.read_text()):
            if match[1] == 'gap':
                pos += Time(seconds=float(match[2]))
                continue

            interval = Time(seconds=float(match[1]))
            fps = float(match[2]) if match.lastindex >= 2 else default_fps

            try:
                scening_list.add(Frame(pos), Frame(pos + interval), '{:.3f} fps'.format(fps))
            except ValueError:
                out_of_range_count += 1

            pos += interval

    def import_tfm(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports TFM's 'OVR HELP INFORMATION'.
        Single combed frames are put into single-frame scenes.
        Frame groups are put into regular scenes.
        Combed probability is used for label.
        '''
        class TFMFrame(Frame):
            mic: int | None

        tfm_frame_pattern = re.compile(r'(\d+)\s\((\d+)\)')
        tfm_group_pattern = re.compile(r'(\d+),(\d+)\s\((\d+(?:\.\d+)%)\)')

        log = path.read_text()

        start_pos = log.find('OVR HELP INFORMATION')
        if start_pos == -1:
            logging.warning("Scening import: TFM log doesn't contain OVR Help Information.")
            return
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

    def import_vsedit(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports bookmarks as single-frame scenes
        '''

        frames = []

        for bookmark in path.read_text().split(', '):
            try:
                frames.append(int(bookmark))
            except ValueError:
                out_of_range_count += 1

        ranges = list[list[int]]()
        prev_x: int
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

    def import_x264_2pass_log(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports I- and K-frames as single-frame scenes.
        '''
        pattern = re.compile(r'in:(\d+).*type:I|K')
        for match in pattern.findall(path.read_text()):
            try:
                scening_list.add(Frame(int(match)))
            except ValueError:
                out_of_range_count += 1

    def import_xvid(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Imports I-frames as single-frame scenes.
        '''
        for i, line in enumerate(path.read_text().splitlines()):
            if not line.startswith('i'):
                continue
            try:
                scening_list.add(Frame(i - 3))
            except ValueError:
                out_of_range_count += 1

    def import_generic(self, path: Path, scening_list: SceningList, out_of_range_count: int) -> None:
        '''
        Import generic (rfs style) frame mappings: {start end}

        '''
        for line in path.read_text().splitlines():
            try:
                fnumbers = [int(n) for n in line.split()]
                scening_list.add(Frame(fnumbers[0]), Frame(fnumbers[1]))
            except ValueError:
                out_of_range_count += 1

    # export
    def export_multiline(self, checked: bool | None = None) -> None:
        if self.current_list is None:
            return

        template = self.export_template_lineedit.text()
        export_str = str()

        try:
            for scene in self.current_list:
                export_str += template.format(
                    start=scene.start, end=scene.end, label=scene.label, script_name=self.main.script_path.stem
                ) + '\n'
        except KeyError:
            logging.warning('Scening: export template contains invalid placeholders.')
            self.main.show_message('Export template contains invalid placeholders.')
            return

        self.main.clipboard.setText(export_str)
        self.main.show_message('Scening data exported to the clipboard')

    # misc
    def check_add_to_list_possibility(self) -> None:
        self.add_to_list_button.setEnabled(False)

        if not (self.current_list_index != -1 and (self.first_frame is not None or self.second_frame is not None)):
            return

        self.add_to_list_button.setEnabled(True)

    def check_remove_export_possibility(self, checked: bool | None = None) -> None:
        is_enabled = self.current_list is not None and len(self.current_list) > 0
        self.remove_last_from_list_button.setEnabled(is_enabled)
        self.seek_to_next_button.setEnabled(is_enabled)
        self.seek_to_prev_button.setEnabled(is_enabled)

        curr = self.main.current_output.last_showed_frame

        is_enabled = self.current_list is not None and curr in self.current_list
        self.add_single_frame_button.setEnabled(not is_enabled)
        self.remove_at_current_frame_button.setEnabled(is_enabled)

        is_enabled = self.export_template_pattern.fullmatch(self.export_template_lineedit.text()) is not None
        self.export_multiline_button.setEnabled(is_enabled)

    def scening_update_status_label(self) -> None:
        first_frame_text = str(self.first_frame) if self.first_frame is not None else ''
        second_frame_text = str(self.second_frame) if self.second_frame is not None else ''
        self.status_label.setText(f'Scening: {first_frame_text} - {second_frame_text} ')

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'label': self.label_lineedit.text(),
            'scening_export_template': self.export_template_lineedit.text(),
            'always_show_scene_marks': self.always_show_scene_marks_checkbox.isChecked(),
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'lists', SceningLists, self.__setattr__)
        try_load(state, 'current_list_index', int, self.current_list_index)
        try_load(state, 'first_frame', Frame, self.__setattr__, nullable=True)
        try_load(state, 'second_frame', Frame, self.__setattr__, nullable=True)

        if self.first_frame is not None:
            self.toggle_first_frame_button.setChecked(True)

        if self.second_frame is not None:
            self.toggle_second_frame_button.setChecked(True)

        self.scening_update_status_label()
        self.check_add_to_list_possibility()

        try_load(state, 'label', str, self.label_lineedit.setText)
        self.items_combobox.setModel(self.lists)

        try_load(state, 'scening_export_template', str, self.export_template_lineedit.setText)

        always_show_scene_marks = None
        try_load(state, 'always_show_scene_marks', bool, always_show_scene_marks, nullable=True)
        if always_show_scene_marks is None:
            always_show_scene_marks = self.settings.always_show_scene_marks

        self.always_show_scene_marks_checkbox.setChecked(always_show_scene_marks)
        self.status_label.setVisible(always_show_scene_marks)

        super().__setstate__(state)
