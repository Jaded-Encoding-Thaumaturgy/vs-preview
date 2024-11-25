from __future__ import annotations

import logging

from bisect import bisect_left, bisect_right
from functools import partial
from typing import TYPE_CHECKING, Any, NamedTuple

from PyQt6.QtCore import QKeyCombination, Qt
from PyQt6.QtGui import QKeySequence

from ..core import AbstractSettingsScrollArea, ComboBox, storage_err_msg, try_load
from .abstract import (
    MAX_WIDTH_LINE_EDIT, AbtractShortcutSection, AbtractShortcutSectionQYAMLObject,
    AbtractShortcutSectionYAMLObjectSingleton, Modifier, ModifierModel, ShortCutLineEdit, TitleLabel
)

if TYPE_CHECKING:
    from ..main import MainWindow
    from ..plugins.abstract import AbstractPlugin, PluginShortcut


__all__ = ["ShortCutsSettings"]


class ShortCutsSettings(AbstractSettingsScrollArea):
    main: MainWindow
    sections: dict[str, AbtractShortcutSection]
    sections_plugins: dict[str, "PluginSection"]

    def __init__(self, main_window: MainWindow) -> None:
        self.main = main_window

        self.sections = {
            "graphics_view": GraphicsViewSection(self),
            "main": ToolbarMainSection(self),
            "playback": ToolbarPlaybackSection(self),
            "scening": ToolbarSceningSection(self),
            "pipette": ToolbarPipetteSection(self),
            "misc": ToolbarMiscSection(self),
            "script_error": ScriptErrorDialogSection(self),
        }
        self.sections_plugins = {ns: PluginSection(self, plugin) for ns, plugin in self.main.plugins.plugins.items()}
        super().__init__()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.vlayout.addWidget(TitleLabel("Graphics view"))
        self.sections["graphics_view"].setup_ui()

        self.vlayout.addWidget(TitleLabel("Toolbars"))

        self.vlayout.addWidget(TitleLabel("Main", "###"))
        self.sections["main"].setup_ui()

        self.vlayout.addWidget(TitleLabel("Playback", "###"))
        self.sections["playback"].setup_ui()

        self.vlayout.addWidget(TitleLabel("Scening", "###"))
        self.sections["scening"].setup_ui()

        self.vlayout.addWidget(TitleLabel("Pipette", "###"))
        self.sections["pipette"].setup_ui()

        self.vlayout.addWidget(TitleLabel("Misc", "###"))
        self.sections["misc"].setup_ui()

        self.vlayout.addWidget(TitleLabel("Script error dialog"))
        self.sections["script_error"].setup_ui()

        self.vlayout.addWidget(TitleLabel("Plugins"))
        for section in self.sections_plugins.values():
            section.setup_ui()

        self.main.app_settings.addTab(self, "Shortcuts")

    def set_defaults(self) -> None:
        pass

    def setup_shortcuts(self) -> None:
        for section in self.sections.values():
            section.setup_shortcuts()

    def __getstate__(self) -> dict[str, Any]:
        state = super().__getstate__()

        for name, section in (self.sections | self.sections_plugins).items():
            state[name] = section.__getstate__()

        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        for name, section in (self.sections | self.sections_plugins).items():
            try:
                storage = state[name]
                if not isinstance(storage, dict):
                    raise TypeError
            except (KeyError, TypeError) as error:
                logging.error(error)
                logging.warning(storage_err_msg(name))
            else:
                section.__setstate__(storage)


class GraphicsViewSection(AbtractShortcutSectionYAMLObjectSingleton):
    __slots__ = (
        "zoom_levels_lineedit",
        "auto_fit_lineedit",
        "pop_out_plugins_lineedit"
    )

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        self.zoom_levels_lineedit = ShortCutLineEdit()
        self.zoom_levels_lineedit.setText("Ctrl+Scroll")
        self.zoom_levels_lineedit.setDisabled(True)

        self.auto_fit_lineedit = ShortCutLineEdit()
        self.pop_out_plugins_lineedit = ShortCutLineEdit()

        self.setup_ui_shortcut("Cycle through zoom levels", self.zoom_levels_lineedit, hide_reset=True)
        self.setup_ui_shortcut("Auto-fit", self.auto_fit_lineedit, self.auto_fit_default)
        self.setup_ui_shortcut("Pop-out plugins :", self.pop_out_plugins_lineedit, self.pop_out_plugins_default)

    def setup_shortcuts(self) -> None:
        main = self.parent.main

        self.create_shortcut(self.auto_fit_lineedit, main, main.auto_fit_keyswitch)
        self.create_shortcut(self.pop_out_plugins_lineedit, main, main.pop_out_plugins)

    @property
    def auto_fit_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_A).toCombined())

    @property
    def pop_out_plugins_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_P).toCombined())

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            "auto_fit": self.auto_fit_lineedit.text(),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, "auto_fit", str, self.auto_fit_lineedit.setText)


class ToolbarMainSection(AbtractShortcutSectionYAMLObjectSingleton):
    __slots__ = (
        "switch_output_lineedit",
        "switch_output_modifier_combobox",
        "switch_output_next_lineedit",
        "switch_output_previous_lineedit",
        "copy_frame_lineedit",
        "copy_timestamp_lineedit",
        "sync_ouputs_lineedit",
        "switch_timeline_mode_lineedit",
        "settings_lineedit",
    )

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        self.switch_output_lineedit = [
            ShortCutLineEdit(allow_modifiers=False) for _ in range(len(self.switch_output_default))
        ]

        self.switch_output_modifier_combobox = ComboBox[Modifier](
            model=ModifierModel([Modifier.CTRL, Modifier.SHIFT, Modifier.ALT])
        )
        self.switch_output_modifier_combobox.setMaximumWidth(MAX_WIDTH_LINE_EDIT)

        self.switch_output_next_lineedit = ShortCutLineEdit()
        self.switch_output_previous_lineedit = ShortCutLineEdit()

        self.copy_frame_lineedit = ShortCutLineEdit()
        self.copy_timestamp_lineedit = ShortCutLineEdit()

        self.sync_ouputs_lineedit = ShortCutLineEdit()

        self.switch_timeline_mode_lineedit = ShortCutLineEdit()
        self.settings_lineedit = ShortCutLineEdit()

        for i, (le, num_key) in enumerate(zip(self.switch_output_lineedit, self.switch_output_default)):
            self.setup_ui_shortcut(f"View output node {i}", le, num_key)

        self.setup_ui_shortcut("View output node last index modifier", self.switch_output_modifier_combobox)

        self.setup_ui_shortcut(
            "View next output node", self.switch_output_next_lineedit, self.switch_output_next_default
        )
        self.setup_ui_shortcut(
            "View previous output node", self.switch_output_previous_lineedit, self.switch_output_previous_default
        )

        self.setup_ui_shortcut(
            "Copy current frame number to clipboard", self.copy_frame_lineedit, self.copy_frame_default
        )
        self.setup_ui_shortcut(
            "Copy current timestamp to clipboard", self.copy_timestamp_lineedit, self.unassigned_default
        )

        self.setup_ui_shortcut(
            "Toggle whether output nodes are synced", self.sync_ouputs_lineedit, self.sync_ouputs_default
        )

        self.setup_ui_shortcut("Switch timeline mode", self.switch_timeline_mode_lineedit, self.unassigned_default)
        self.setup_ui_shortcut("Open settings window", self.settings_lineedit, self.unassigned_default)

    def setup_shortcuts(self) -> None:
        main = self.parent.main
        main_toolbar = main.toolbars.main

        for i, le in enumerate(self.switch_output_lineedit):
            if not le.text():
                continue
            self.create_shortcut(le, main, partial(main.switch_output, i))
            self.create_shortcut(
                QKeySequence(
                    QKeyCombination(
                        self.switch_output_modifier_combobox.currentValue().modifier, QKeySequence(le.text())[0].key()
                    ).toCombined()
                ),
                main,
                partial(main.switch_output, -(i + 1)),
            )

        self.create_shortcut(
            self.switch_output_next_lineedit,
            main,
            lambda: main.switch_output(main_toolbar.outputs_combobox.currentIndex() + 1),
        )
        self.create_shortcut(
            self.switch_output_previous_lineedit,
            main,
            lambda: main.switch_output(main_toolbar.outputs_combobox.currentIndex() - 1),
        )
        self.create_shortcut(self.copy_frame_lineedit, main, main_toolbar.on_copy_frame_button_clicked)
        self.create_shortcut(self.copy_timestamp_lineedit, main, main_toolbar.on_copy_timestamp_button_clicked)

        self.create_shortcut(self.sync_ouputs_lineedit, main, main_toolbar.sync_outputs_checkbox.click)

        self.create_shortcut(self.switch_timeline_mode_lineedit, main, main_toolbar.switch_timeline_mode_button.click)
        self.create_shortcut(self.settings_lineedit, main, main_toolbar.settings_button.click)

    @property
    def switch_output_default(self) -> list[QKeySequence]:
        return [
            QKeySequence(k)
            for k in [
                Qt.Key.Key_1,
                Qt.Key.Key_2,
                Qt.Key.Key_3,
                Qt.Key.Key_4,
                Qt.Key.Key_5,
                Qt.Key.Key_6,
                Qt.Key.Key_7,
                Qt.Key.Key_8,
                Qt.Key.Key_9,
                Qt.Key.Key_0,
            ]
        ]

    @property
    def switch_output_next_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.SHIFT, Qt.Key.Key_Tab).toCombined())

    @property
    def switch_output_previous_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL | Qt.Modifier.SHIFT, Qt.Key.Key_Tab).toCombined())

    @property
    def sync_ouputs_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_S)

    @property
    def copy_frame_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_V)

    def __getstate__(self) -> dict[str, Any]:
        return (
            super().__getstate__()
            | {
                "switch_output_modifier": self.switch_output_modifier_combobox.currentValue(),
                "switch_output_next": self.switch_output_next_lineedit.text(),
                "switch_output_previous": self.switch_output_previous_lineedit.text(),
                "sync_ouputs": self.sync_ouputs_lineedit.text(),
                "copy_frame": self.copy_frame_lineedit.text(),
                "switch_timeline_mode": self.switch_timeline_mode_lineedit.text(),
                "settings": self.settings_lineedit.text(),
            }
            | {f"switch_output_{i}": so.text() for i, so in enumerate(self.switch_output_lineedit)}
        )

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, "switch_output_modifier", Modifier, self.switch_output_modifier_combobox.setCurrentValue)
        try_load(state, "switch_output_next", str, self.switch_output_next_lineedit.setText)
        try_load(state, "switch_output_previous", str, self.switch_output_previous_lineedit.setText)
        try_load(state, "sync_ouputs", str, self.sync_ouputs_lineedit.setText)
        try_load(state, "copy_frame", str, self.copy_frame_lineedit.setText)
        try_load(state, "switch_timeline_mode", str, self.switch_timeline_mode_lineedit.setText)
        try_load(state, "settings", str, self.settings_lineedit.setText)

        for i, so in enumerate(self.switch_output_lineedit):
            try_load(state, f"switch_output_{i}", str, so.setText)


class ToolbarPlaybackSection(AbtractShortcutSectionYAMLObjectSingleton):
    __slots__ = (
        "play_pause_lineedit",
        "seek_to_prev_lineedit",
        "seek_to_next_lineedit",
        "seek_n_frames_b_lineedit",
        "seek_n_frames_f_lineedit",
        "seek_to_start_lineedit",
        "seek_to_end_lineedit",
        "play_n_frames_lineedit",
        "reset_fps_lineedit",
        "unlimited_fps_lineedit",
        "variable_fps_lineedit",
        "mute_lineedit",
        "decrease_volume_lineedit",
        "increase_volume_lineedit",
    )

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        self.play_pause_lineedit = ShortCutLineEdit()

        self.seek_to_prev_lineedit = ShortCutLineEdit()
        self.seek_to_next_lineedit = ShortCutLineEdit()

        self.seek_n_frames_b_lineedit = (ShortCutLineEdit(), ShortCutLineEdit())
        self.seek_n_frames_f_lineedit = (ShortCutLineEdit(), ShortCutLineEdit())

        self.seek_to_start_lineedit = ShortCutLineEdit()
        self.seek_to_end_lineedit = ShortCutLineEdit()

        self.play_n_frames_lineedit = ShortCutLineEdit()

        self.reset_fps_lineedit = ShortCutLineEdit()
        self.unlimited_fps_lineedit = ShortCutLineEdit()
        self.variable_fps_lineedit = ShortCutLineEdit()

        self.mute_lineedit = ShortCutLineEdit()
        self.decrease_volume_lineedit = ShortCutLineEdit()
        self.increase_volume_lineedit = ShortCutLineEdit()

        self.setup_ui_shortcut("Play/Pause", self.play_pause_lineedit, self.play_pause_default)

        self.setup_ui_shortcut("Seek to previous frame", self.seek_to_prev_lineedit, self.seek_to_prev_default)
        self.setup_ui_shortcut("Seek to next frame", self.seek_to_next_lineedit, self.seek_to_next_default)

        self.setup_ui_shortcut("Seek back n frames", self.seek_n_frames_b_lineedit[0], self.seek_n_frames_b_default[0])
        self.setup_ui_shortcut("", self.seek_n_frames_b_lineedit[1], self.seek_n_frames_b_default[1])
        self.setup_ui_shortcut(
            "Seek forward n frames", self.seek_n_frames_f_lineedit[0], self.seek_n_frames_f_default[0]
        )
        self.setup_ui_shortcut("", self.seek_n_frames_f_lineedit[1], self.seek_n_frames_f_default[1])

        self.setup_ui_shortcut("Seek to first frame", self.seek_to_start_lineedit, self.seek_to_start_default)
        self.setup_ui_shortcut("Seek to last frame", self.seek_to_end_lineedit, self.seek_to_end_default)

        self.setup_ui_shortcut("Play n frames", self.play_n_frames_lineedit, self.unassigned_default)

        self.setup_ui_shortcut("Reset FPS", self.reset_fps_lineedit, self.unassigned_default)
        self.setup_ui_shortcut("Toggle unlimited FPS", self.unlimited_fps_lineedit, self.unassigned_default)
        self.setup_ui_shortcut("Toggle variable FPS", self.variable_fps_lineedit, self.unassigned_default)

        self.setup_ui_shortcut("Toggle audio mute", self.mute_lineedit, self.unassigned_default)
        self.setup_ui_shortcut("Decrease volume", self.decrease_volume_lineedit, self.unassigned_default)
        self.setup_ui_shortcut("Increase volume", self.increase_volume_lineedit, self.unassigned_default)

    def setup_shortcuts(self) -> None:
        main = self.parent.main
        playback_toolbar = main.toolbars.playback

        self.create_shortcut(self.play_pause_lineedit, main, playback_toolbar.play_pause_button.click)

        self.create_shortcut(self.seek_to_prev_lineedit, main, playback_toolbar.seek_to_prev_button.click)
        self.create_shortcut(self.seek_to_next_lineedit, main, playback_toolbar.seek_to_next_button.click)

        for le in self.seek_n_frames_b_lineedit:
            self.create_shortcut(le, main, playback_toolbar.seek_n_frames_b_button.click)
        for le in self.seek_n_frames_f_lineedit:
            self.create_shortcut(le, main, playback_toolbar.seek_n_frames_f_button.click)

        self.create_shortcut(self.seek_to_start_lineedit, main, playback_toolbar.seek_to_start_button.click)
        self.create_shortcut(self.seek_to_end_lineedit, main, playback_toolbar.seek_to_end_button.click)

        self.create_shortcut(self.play_n_frames_lineedit, main, playback_toolbar.play_n_frames_button.click)

        self.create_shortcut(self.reset_fps_lineedit, main, playback_toolbar.fps_reset_button.click)
        self.create_shortcut(
            self.unlimited_fps_lineedit, main, playback_toolbar.fps_unlimited_checkbox.click
        )
        self.create_shortcut(self.variable_fps_lineedit, main, playback_toolbar.fps_variable_checkbox.click)
        self.create_shortcut(self.mute_lineedit, main, playback_toolbar.mute_button.click)

        volume_steps = [x * 10 for x in range(11)]
        volume_slider = playback_toolbar.audio_volume_slider

        self.create_shortcut(
            self.decrease_volume_lineedit,
            main,
            lambda: playback_toolbar.setVolume(
                volume_steps[bisect_left(volume_steps, volume_slider.value() - 10)], updateGui=True
            ),
        )
        self.create_shortcut(
            self.increase_volume_lineedit,
            main,
            lambda: playback_toolbar.setVolume(
                volume_steps[bisect_right(volume_steps, volume_slider.value() + 10) - 1], updateGui=True
            ),
        )

    @property
    def seek_n_frames_b(self) -> list[str]:
        return list(le.text() for le in self.seek_n_frames_b_lineedit)

    @seek_n_frames_b.setter
    def seek_n_frames_b(self, value: tuple[str, str]) -> None:
        for v, le in zip(value, self.seek_n_frames_b_lineedit):
            le.setText(v)

    @property
    def seek_n_frames_f(self) -> list[str]:
        return list(le.text() for le in self.seek_n_frames_f_lineedit)

    @seek_n_frames_f.setter
    def seek_n_frames_f(self, value: tuple[str, str]) -> None:
        for v, le in zip(value, self.seek_n_frames_f_lineedit):
            le.setText(v)

    @property
    def play_pause_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_Space)

    @property
    def seek_to_prev_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_Left)

    @property
    def seek_to_next_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_Right)

    @property
    def seek_n_frames_b_default(self) -> tuple[QKeySequence, QKeySequence]:
        return (
            QKeySequence(QKeyCombination(Qt.Modifier.SHIFT, Qt.Key.Key_Left).toCombined()),
            QKeySequence(Qt.Key.Key_PageUp),
        )

    @property
    def seek_n_frames_f_default(self) -> tuple[QKeySequence, QKeySequence]:
        return (
            QKeySequence(QKeyCombination(Qt.Modifier.SHIFT, Qt.Key.Key_Right).toCombined()),
            QKeySequence(Qt.Key.Key_PageDown),
        )

    @property
    def seek_to_start_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_Home)

    @property
    def seek_to_end_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_End)

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            "play_pause": self.play_pause_lineedit.text(),
            "seek_to_prev": self.seek_to_prev_lineedit.text(),
            "seek_to_next": self.seek_to_next_lineedit.text(),
            "seek_n_frames_b": list(le.text() for le in self.seek_n_frames_b_lineedit),
            "seek_n_frames_f": list(le.text() for le in self.seek_n_frames_f_lineedit),
            "seek_to_start": self.seek_to_start_lineedit.text(),
            "seek_to_end": self.seek_to_end_lineedit.text(),
            "play_n_frames": self.play_n_frames_lineedit.text(),
            "reset_fps": self.reset_fps_lineedit.text(),
            "unlimited_fps": self.unlimited_fps_lineedit.text(),
            "variable_fps": self.variable_fps_lineedit.text(),
            "mute": self.mute_lineedit.text(),
            "decrease_volume": self.decrease_volume_lineedit.text(),
            "increase_volume": self.increase_volume_lineedit.text(),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, "play_pause", str, self.play_pause_lineedit.setText)
        try_load(state, "seek_to_prev", str, self.seek_to_prev_lineedit.setText)
        try_load(state, "seek_to_next", str, self.seek_to_next_lineedit.setText)
        try_load(state, "seek_n_frames_b", list, self)
        try_load(state, "seek_n_frames_f", list, self)
        try_load(state, "seek_to_start", str, self.seek_to_start_lineedit.setText)
        try_load(state, "seek_to_end", str, self.seek_to_end_lineedit.setText)
        try_load(state, "play_n_frames", str, self.play_n_frames_lineedit.setText)
        try_load(state, "reset_fps", str, self.reset_fps_lineedit.setText)
        try_load(state, "unlimited_fps", str, self.unlimited_fps_lineedit.setText)
        try_load(state, "variable_fps", str, self.variable_fps_lineedit.setText)
        try_load(state, "mute", str, self.mute_lineedit.setText)
        try_load(state, "decrease_volume", str, self.decrease_volume_lineedit.setText)
        try_load(state, "increase_volume", str, self.increase_volume_lineedit.setText)


class ToolbarSceningSection(AbtractShortcutSectionYAMLObjectSingleton):
    __slots__ = (
        "add_frame_scene_lineedit",
        "toggle_first_frame_lineedit",
        "toggle_second_frame_lineedit",
        "add_to_list_lineedit",
        "remove_last_from_list_lineedit",
        "remove_scene_at_current_frame_lineedit",
        "switch_list_lineedit",
        "seek_to_prev_scene_start_lineedit",
        "seek_to_next_scene_start_lineedit",
        "paste_frame_scening_model_lineedit",
        "delete_scene_lineedit",
    )

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        self.add_frame_scene_lineedit = ShortCutLineEdit()
        self.toggle_first_frame_lineedit = ShortCutLineEdit()
        self.toggle_second_frame_lineedit = ShortCutLineEdit()

        self.add_to_list_lineedit = ShortCutLineEdit()
        self.remove_last_from_list_lineedit = ShortCutLineEdit()
        self.remove_scene_at_current_frame_lineedit = ShortCutLineEdit()

        self.switch_list_lineedit = [ShortCutLineEdit() for _ in range(len(self.switch_list_default))]

        self.seek_to_prev_scene_start_lineedit = ShortCutLineEdit()
        self.seek_to_next_scene_start_lineedit = ShortCutLineEdit()

        self.paste_frame_scening_model_lineedit = ShortCutLineEdit()
        self.delete_scene_lineedit = ShortCutLineEdit()

        self.setup_ui_shortcut(
            "Add current frame as single frame scene", self.add_frame_scene_lineedit, self.add_frame_scene_default
        )
        self.setup_ui_shortcut(
            "Toggle whether current frame is first frame",
            self.toggle_first_frame_lineedit,
            self.toggle_first_frame_default,
        )
        self.setup_ui_shortcut(
            "Toggle whether current frame is last frame",
            self.toggle_second_frame_lineedit,
            self.toggle_second_frame_default,
        )

        self.setup_ui_shortcut(
            "Add A-B selection to current scene list", self.add_to_list_lineedit, self.add_to_list_default
        )
        self.setup_ui_shortcut(
            "Remove last scene from current scene list",
            self.remove_last_from_list_lineedit,
            self.remove_last_from_list_default,
        )
        self.setup_ui_shortcut(
            "Remove scene at current frame",
            self.remove_scene_at_current_frame_lineedit,
            self.remove_scene_at_current_frame_default,
        )

        for i, (le, num_key) in enumerate(zip(self.switch_list_lineedit, self.switch_list_default)):
            self.setup_ui_shortcut(f"Switch to scene list {i}", le, num_key)

        self.setup_ui_shortcut(
            "Seek to previous scene start",
            self.seek_to_prev_scene_start_lineedit,
            self.seek_to_prev_scene_start_default,
        )
        self.setup_ui_shortcut(
            "Seek to next scene start", self.seek_to_next_scene_start_lineedit, self.seek_to_next_scene_start_default
        )

        self.parent.vlayout.addWidget(TitleLabel("Scening List Dialog", "####"))
        self.setup_ui_shortcut(
            "Paste current frame number\ninto active scening model",
            self.paste_frame_scening_model_lineedit,
            self.paste_frame_scening_model_default,
        )
        self.setup_ui_shortcut("Delete selected scene", self.delete_scene_lineedit, self.delete_scene_default)

    def setup_shortcuts(self) -> None:
        main = self.parent.main
        scening_toolbar = main.toolbars.scening

        self.create_shortcut(self.add_frame_scene_lineedit, scening_toolbar, scening_toolbar.on_toggle_single_frame)
        self.create_shortcut(
            self.toggle_first_frame_lineedit, scening_toolbar, scening_toolbar.toggle_first_frame_button.click
        )
        self.create_shortcut(
            self.toggle_second_frame_lineedit, scening_toolbar, scening_toolbar.toggle_second_frame_button.click
        )

        self.create_shortcut(self.add_to_list_lineedit, scening_toolbar, scening_toolbar.add_to_list_button.click)
        self.create_shortcut(
            self.remove_last_from_list_lineedit, scening_toolbar, scening_toolbar.remove_last_from_list_button.click
        )
        self.create_shortcut(
            self.remove_scene_at_current_frame_lineedit,
            scening_toolbar,
            scening_toolbar.remove_at_current_frame_button.click,
        )

        for i, le in enumerate(self.switch_list_lineedit):
            self.create_shortcut(le, scening_toolbar, partial(scening_toolbar.switch_list, i))

        self.create_shortcut(
            self.seek_to_prev_scene_start_lineedit, scening_toolbar, scening_toolbar.seek_to_prev_button.click
        )
        self.create_shortcut(
            self.seek_to_next_scene_start_lineedit, scening_toolbar, scening_toolbar.seek_to_next_button.click
        )

        self.create_shortcut(
            self.paste_frame_scening_model_lineedit,
            scening_toolbar.scening_list_dialog,
            lambda: scening_toolbar.scening_list_dialog.label_lineedit.setText(
                str(main.current_output.last_showed_frame)
            ),
        )
        self.create_shortcut(
            self.delete_scene_lineedit,
            scening_toolbar.scening_list_dialog,
            scening_toolbar.scening_list_dialog.delete_button.click,
        )

    @property
    def add_frame_scene_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Space).toCombined())

    @property
    def toggle_first_frame_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_Q)

    @property
    def toggle_second_frame_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_W)

    @property
    def add_to_list_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_E)

    @property
    def remove_last_from_list_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_R)

    @property
    def remove_scene_at_current_frame_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.SHIFT, Qt.Key.Key_R).toCombined())

    @property
    def switch_list_default(self) -> list[QKeySequence]:
        return [
            QKeySequence(QKeyCombination(Qt.Modifier.SHIFT, k).toCombined())
            for k in [
                Qt.Key.Key_1,
                Qt.Key.Key_2,
                Qt.Key.Key_3,
                Qt.Key.Key_4,
                Qt.Key.Key_5,
                Qt.Key.Key_6,
                Qt.Key.Key_7,
                Qt.Key.Key_8,
                Qt.Key.Key_9,
                Qt.Key.Key_0,
            ]
        ]

    @property
    def seek_to_prev_scene_start_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Left).toCombined())

    @property
    def seek_to_next_scene_start_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Right).toCombined())

    @property
    def paste_frame_scening_model_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_B)

    @property
    def delete_scene_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_Delete)

    def __getstate__(self) -> dict[str, Any]:
        return (
            super().__getstate__()
            | {
                "add_frame_scene": self.add_frame_scene_lineedit.text(),
                "toggle_first_frame": self.toggle_first_frame_lineedit.text(),
                "toggle_second_frame": self.toggle_second_frame_lineedit.text(),
                "add_to_list": self.add_to_list_lineedit.text(),
                "remove_last_from_list": self.remove_last_from_list_lineedit.text(),
                "remove_scene_at_current_frame": self.remove_scene_at_current_frame_lineedit.text(),
                "seek_to_prev_scene_start": self.seek_to_prev_scene_start_lineedit.text(),
                "seek_to_next_scene_start": self.seek_to_next_scene_start_lineedit.text(),
                "paste_frame_scening_model": self.paste_frame_scening_model_lineedit.text(),
                "delete_scene": self.delete_scene_lineedit.text(),
            }
            | {f"switch_list_{i}": so.text() for i, so in enumerate(self.switch_list_lineedit)}
        )

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, "add_frame_scene", str, self.add_frame_scene_lineedit.setText)
        try_load(state, "toggle_first_frame", str, self.toggle_first_frame_lineedit.setText)
        try_load(state, "toggle_second_frame", str, self.toggle_second_frame_lineedit.setText)
        try_load(state, "add_to_list", str, self.add_to_list_lineedit.setText)
        try_load(state, "remove_last_from_list", str, self.remove_last_from_list_lineedit.setText)
        try_load(state, "remove_scene_at_current_frame", str, self.remove_scene_at_current_frame_lineedit.setText)
        try_load(state, "seek_to_prev_scene_start", str, self.seek_to_prev_scene_start_lineedit.setText)
        try_load(state, "seek_to_next_scene_start", str, self.seek_to_next_scene_start_lineedit.setText)
        try_load(state, "paste_frame_scening_model", str, self.paste_frame_scening_model_lineedit.setText)
        try_load(state, "delete_scene", str, self.delete_scene_lineedit.setText)

        for i, le in enumerate(self.switch_list_lineedit):
            try_load(state, f"switch_list_{i}", str, le.setText)


class ToolbarPipetteSection(AbtractShortcutSectionYAMLObjectSingleton):
    __slots__ = ("copy_position_lineedit",)

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        self.copy_position_lineedit = ShortCutLineEdit()

        self.setup_ui_shortcut(
            "Copy coordinates of pixel position", self.copy_position_lineedit, self.unassigned_default
        )

    def setup_shortcuts(self) -> None:
        main = self.parent.main
        toolbar_pipette = main.toolbars.pipette

        self.create_shortcut(self.copy_position_lineedit, toolbar_pipette, toolbar_pipette.copy_position_button.click)

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            "copy_position": self.copy_position_lineedit.text(),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, "copy_position", str, self.copy_position_lineedit.setText)


class ToolbarMiscSection(AbtractShortcutSectionYAMLObjectSingleton):
    __slots__ = (
        "autosave_lineedit",
        "reload_script_lineedit",
        "save_storage_lineedit",
        "copy_frame_lineedit",
        "save_frame_as_lineedit",
        "toggle_sar_lineedit",
        "enable_crop_lineedit",
        "copy_crop_command_lineedit",
    )

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        self.autosave_lineedit = ShortCutLineEdit()

        self.reload_script_lineedit = ShortCutLineEdit()
        if not self.parent.main.reload_enabled:
            self.reload_script_lineedit.setDisabled(True)

        self.save_storage_lineedit = ShortCutLineEdit()
        self.copy_frame_lineedit = ShortCutLineEdit()

        self.save_frame_as_lineedit = ShortCutLineEdit()

        self.toggle_sar_lineedit = ShortCutLineEdit()
        self.enable_crop_lineedit = ShortCutLineEdit()
        self.copy_crop_command_lineedit = ShortCutLineEdit()

        self.setup_ui_shortcut("Toggle whether autosave is enabled", self.autosave_lineedit, self.unassigned_default)

        self.setup_ui_shortcut("Reload script", self.reload_script_lineedit, self.reload_script_default)
        self.setup_ui_shortcut("Manually save storage", self.save_storage_lineedit, self.save_storage_default)
        self.setup_ui_shortcut("Copy current frame to clipboard", self.copy_frame_lineedit, self.copy_frame_default)

        self.setup_ui_shortcut("Save current frame as", self.save_frame_as_lineedit, self.save_frame_as_default)

        self.parent.vlayout.addWidget(TitleLabel("Cropping assistant", "####"))
        self.setup_ui_shortcut(
            "Toggle whether SAR props are respected", self.toggle_sar_lineedit, self.unassigned_default
        )
        self.setup_ui_shortcut("Toggle crop assistant", self.enable_crop_lineedit, self.unassigned_default)
        self.setup_ui_shortcut("Copy crop command", self.copy_crop_command_lineedit, self.unassigned_default)

    def setup_shortcuts(self) -> None:
        main = self.parent.main
        misc_toolbar = main.toolbars.misc

        self.create_shortcut(self.autosave_lineedit, misc_toolbar, misc_toolbar.autosave_checkbox.click)

        if main.reload_enabled:
            self.create_shortcut(self.reload_script_lineedit, main, misc_toolbar.reload_script_button.click)

        self.create_shortcut(self.save_storage_lineedit, main, misc_toolbar.save_storage_button.click)
        self.create_shortcut(self.copy_frame_lineedit, main, misc_toolbar.copy_frame_button.click)

        self.create_shortcut(self.save_frame_as_lineedit, main, misc_toolbar.save_frame_as_button.click)

        self.create_shortcut(self.toggle_sar_lineedit, main, misc_toolbar.ar_active_switch.click)

        self.create_shortcut(self.enable_crop_lineedit, misc_toolbar, misc_toolbar.crop_active_switch.click)
        self.create_shortcut(self.copy_crop_command_lineedit, misc_toolbar, misc_toolbar.crop_copycommand_button.click)

    @property
    def reload_script_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_R).toCombined())

    @property
    def save_storage_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.ALT, Qt.Key.Key_S).toCombined())

    @property
    def copy_frame_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_S).toCombined())

    @property
    def save_frame_as_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.SHIFT, Qt.Key.Key_S).toCombined())

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            "autosave": self.autosave_lineedit.text(),
            "reload_script": self.reload_script_lineedit.text(),
            "save_storage": self.save_storage_lineedit.text(),
            "copy_frame": self.copy_frame_lineedit.text(),
            "save_frame_as": self.save_frame_as_lineedit.text(),
            "toggle_sar": self.toggle_sar_lineedit.text(),
            "enable_crop": self.enable_crop_lineedit.text(),
            "copy_crop_command": self.copy_crop_command_lineedit.text(),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, "autosave", str, self.autosave_lineedit.setText)
        try_load(state, "reload_script", str, self.reload_script_lineedit.setText)
        try_load(state, "save_storage", str, self.save_storage_lineedit.setText)
        try_load(state, "copy_frame", str, self.copy_frame_lineedit.setText)
        try_load(state, "save_frame_as", str, self.save_frame_as_lineedit.setText)
        try_load(state, "toggle_sar", str, self.toggle_sar_lineedit.setText)
        try_load(state, "enable_crop", str, self.enable_crop_lineedit.setText)
        try_load(state, "copy_crop_command", str, self.copy_crop_command_lineedit.setText)


class ScriptErrorDialogSection(AbtractShortcutSectionYAMLObjectSingleton):
    __slots__ = ("reload_lineedit", "exit_lineedit")

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        self.reload_lineedit = ShortCutLineEdit(conflictable=False)
        self.exit_lineedit = ShortCutLineEdit(conflictable=False)

        self.setup_ui_shortcut("Reload", self.reload_lineedit, self.reload_default, hide_reset=True)
        self.setup_ui_shortcut("Exit", self.exit_lineedit, self.exit_default, hide_reset=True)

        self.reload_lineedit.setDisabled(True)
        self.exit_lineedit.setDisabled(True)

    def setup_shortcuts(self) -> None:
        main = self.parent.main

        self.create_shortcut(
            self.reload_lineedit, main.script_error_dialog, main.script_error_dialog.reload_button.click
        )
        self.create_shortcut(self.exit_lineedit, main.script_error_dialog, main.script_error_dialog.exit_button.click)

    @property
    def reload_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_R).toCombined())

    @property
    def exit_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_Escape)

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            "reload": self.reload_lineedit.text(),
            "exit": self.exit_lineedit.text(),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, "reload", str, self.reload_lineedit.setText)
        try_load(state, "exit", str, self.exit_lineedit.setText)


class _PluginShortcutSettings(NamedTuple):
    lineedit: ShortCutLineEdit
    plugin_shortcut: PluginShortcut


class PluginSection(AbtractShortcutSectionQYAMLObject):
    __slots__ = (
        "plugin_shortcut_settings",
    )

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings, plugin: AbstractPlugin) -> None:
        self.parent = parent
        self.plugin = plugin
        self.plugin_shortcut_settings = dict[str, _PluginShortcutSettings]()
        super().__init__()

    def setup_ui(self) -> None:
        if not self.plugin.shortcuts:
            return

        self.label = TitleLabel(self.plugin._config.display_name, "###")
        self.parent.vlayout.addWidget(self.label)

        for shortcut in self.plugin.shortcuts:
            le = ShortCutLineEdit()
            self.plugin_shortcut_settings[shortcut.name] = _PluginShortcutSettings(le, shortcut)
            self.setup_ui_shortcut(shortcut.description or shortcut.name, le, shortcut.key)

    def setup_shortcuts(self) -> None:
        for sett in self.plugin_shortcut_settings.values():
            plsh = sett.plugin_shortcut

            self.create_shortcut(
                sett.lineedit,
                eval(plsh.parent.replace("self.", "self.plugin.")) if isinstance(plsh.parent, str) else plsh.parent,
                eval(plsh.handler.replace("self.", "self.plugin.")) if isinstance(plsh.handler, str) else plsh.handler,
            )

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {n: sett.lineedit.text() for n, sett in self.plugin_shortcut_settings.items()}

    def __setstate__(self, state: dict[str, Any]) -> None:
        for n, sett in self.plugin_shortcut_settings.items():
            try_load(state, n, str, sett.lineedit.setText)
