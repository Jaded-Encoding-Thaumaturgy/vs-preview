from __future__ import annotations

import logging
import webbrowser
from datetime import datetime

from PyQt6.QtCore import QFileSystemWatcher, QTimer
from PyQt6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem
from vstools import SPath

from vspreview.core import (
    ExtendedWidget,
    HBoxLayout,
    PushButton,
    Stretch,
    VBoxLayout,
    main_window,
)

__all__ = ["CompHistoryWidget"]


class CompHistoryWidget(ExtendedWidget):
    __slots__ = (
        "history_table",
        "clear_history_button",
        "trash_dir",
        "url_data",
        "file_watcher",
        "update_timer",
        "_updating",
    )

    def __init__(self) -> None:
        super().__init__()

        self.main = main_window()
        self.url_data = dict[int, str]()
        self.trash_dir = self.get_history_directory() / ".trash"
        self._updating = False

        self.cleanup_trash_on_startup()
        self.setup_ui()
        self.setup_file_watcher()
        self.set_qobject_names()
        self.load_history()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.history_table = QTableWidget(self)
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(
            ["Title", "Slowpics ID", "Created"]
        )

        if (header := self.history_table.horizontalHeader()) is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.history_table.itemDoubleClicked.connect(self.open_url)

        self.clear_history_button = PushButton(
            "Clear History", self, clicked=self.clear_history
        )

        VBoxLayout(
            self.vlayout,
            [
                self.history_table,
                HBoxLayout([self.clear_history_button, Stretch()]),
            ],
        )

    def setup_file_watcher(self) -> None:
        """Set up file system watcher to monitor for new URL files."""

        self.file_watcher = QFileSystemWatcher(self)

        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.load_history)

        if (parent_dir := self.get_history_directory().parent).exists():
            self.file_watcher.addPath(str(parent_dir))

        if (history_dir := self.get_history_directory()).exists():
            self.file_watcher.addPath(str(history_dir))

        self.file_watcher.directoryChanged.connect(self._on_directory_changed)

    def get_history_directory(self) -> SPath:
        """Get the path to the Old Comps directory."""

        return SPath(main_window().current_config_dir) / "Old Comps"

    def cleanup_trash_on_startup(self) -> None:
        """Delete trash directory on startup to permanently clear any previously trashed history."""

        if not self.trash_dir.exists():
            return

        import shutil

        try:
            shutil.rmtree(self.trash_dir)
            logging.debug(f"Cleaned up trash directory: {self.trash_dir}")
        except Exception as e:
            logging.debug(f"Error cleaning up trash directory: {e}")

    def update_clear_button_text(self) -> None:
        """Update the clear button text based on whether trash exists."""

        has_trash = self.trash_dir.exists() and any(self.trash_dir.glob("*.url"))
        button_text = "Restore History" if has_trash else "Clear History"

        self.clear_history_button.setText(button_text)

    def load_history(self) -> None:
        """Load and display history from .url files."""

        self._updating = True

        try:
            if not (history_dir := self.get_history_directory()).exists():
                self.history_table.setRowCount(0)
                self.url_data.clear()
                self.update_clear_button_text()
                self._update_file_watcher()
                return

            if not (url_files := list(history_dir.glob("*.url"))):
                self.history_table.setRowCount(0)
                self.url_data.clear()
                self.update_clear_button_text()
                self._update_file_watcher()
                return

            self.history_table.setRowCount(len(url_files))
            self.url_data.clear()

            for row, url_file in enumerate(
                sorted(url_files, key=lambda f: f.stat().st_mtime, reverse=True)
            ):
                try:
                    title, slowpics_id, created_str, url = self._load_url_file(url_file)
                except Exception as e:
                    logging.error(f"Error loading file {url_file}: {e}")
                    self._set_error_row(row, f"Error: {url_file.name}")

                    continue

                self.url_data[row] = url
                self.history_table.setItem(row, 0, QTableWidgetItem(title))
                self.history_table.setItem(row, 1, QTableWidgetItem(slowpics_id))
                self.history_table.setItem(row, 2, QTableWidgetItem(created_str))

            self.update_clear_button_text()
            self._update_file_watcher()
        finally:
            self._updating = False

    def open_url(self, item: QTableWidgetItem) -> None:
        """Open the URL in the default browser when double-clicked."""

        row = item.row()

        if not (url := self.url_data.get(row, "")):
            title = self.history_table.item(row, 0).text() or "Unknown"  # type: ignore
            msg = f"No URL found for {title} ({row + 1})"

            logging.error(msg)
            self.main.show_message(msg)

            return

        webbrowser.open(url)

    def clear_history(self) -> None:
        """Clear history files or restore from trash."""

        if self._has_trashed_files():
            self._restore_from_trash()
        else:
            self._move_to_trash()

    def _on_directory_changed(self, path: str) -> None:
        if self._updating:
            return

        history_dir = self.get_history_directory()
        parent_dir = history_dir.parent

        if SPath(path) == history_dir or SPath(path) == parent_dir:
            if SPath(path) == parent_dir and history_dir.exists():
                self._update_file_watcher()

            self.update_timer.start(500)

    def _update_file_watcher(self) -> None:
        history_dir = self.get_history_directory()

        if not history_dir.exists():
            return

        if str(history_dir) not in self.file_watcher.directories():
            self.file_watcher.addPath(str(history_dir))

    def _extract_url_from_content(self, content: str) -> str:
        for line in content.splitlines():
            if line.startswith("URL="):
                return line[4:]

        return ""

    def _extract_slowpics_id_from_url(self, url: str) -> str:
        if not url:
            return "Unknown"

        if not (parts := url.rsplit("/", 1)):
            return "Unknown"

        if "slow.pics" not in parts[0]:
            return "Unknown"

        return parts[-1]

    def _clean_title_from_filename(self, filename: str, slowpics_id: str) -> str:
        if not filename or filename == "Unknown":
            return "Unknown"

        if filename.endswith(f" - {slowpics_id}"):
            return filename[: -len(f" - {slowpics_id}")].strip()

        return filename.strip() or "Unknown"

    def _set_error_row(self, row: int, error_message: str) -> None:
        self.url_data[row] = ""
        self.history_table.setItem(row, 0, QTableWidgetItem(error_message))
        self.history_table.setItem(row, 1, QTableWidgetItem(""))
        self.history_table.setItem(row, 2, QTableWidgetItem(""))

    def _load_url_file(self, url_file: SPath) -> tuple[str, str, str, str]:
        url_content = url_file.read_text()
        url = self._extract_url_from_content(url_content)

        slowpics_id = self._extract_slowpics_id_from_url(url)
        title = self._clean_title_from_filename(url_file.stem, slowpics_id)

        created_time = datetime.fromtimestamp(url_file.stat().st_mtime)
        created_str = created_time.strftime("%Y-%m-%d %H:%M:%S")

        return title, slowpics_id, created_str, url

    def _has_trashed_files(self) -> bool:
        return self.trash_dir.exists() and any(self.trash_dir.glob("*.url"))

    def _move_to_trash(self) -> None:
        if not (history_dir := self.get_history_directory()).exists():
            self.main.show_message("No history to clear.")
            return

        if not (url_files := list(history_dir.glob("*.url"))):
            self.main.show_message("No history to clear.")
            return

        self.trash_dir.mkdir(parents=True, exist_ok=True)

        moved_count = 0

        for url_file in url_files:
            try:
                if trash_file := self.trash_dir / url_file.name:
                    url_file.rename(trash_file)
                    moved_count += 1
            except Exception as e:
                msg = f"Error moving {url_file} to trash: {e}"

                logging.error(msg)
                self.main.show_message(msg)

        self.load_history()
        self.update_clear_button_text()
        self.main.show_message(f"Moved {moved_count} history entries to trash.")

    def _restore_from_trash(self) -> None:
        if not self.trash_dir.exists():
            self.main.show_message("No trashed history to restore.")
            return

        if not (trash_files := list(self.trash_dir.glob("*.url"))):
            self.main.show_message("No trashed history to restore.")
            return

        history_dir = self.get_history_directory()
        history_dir.mkdir(parents=True, exist_ok=True)

        restored_count = 0

        for trash_file in trash_files:
            try:
                if history_file := history_dir / trash_file.name:
                    trash_file.rename(history_file)

                    restored_count += 1
            except Exception as e:
                msg = f"Error restoring {trash_file} from trash: {e}"

                logging.error(msg)
                self.main.show_message(msg)

        try:
            self.trash_dir.rmdir()
        except Exception as e:
            logging.debug(f"Error removing empty trash directory: {e}")

        self.load_history()
        self.update_clear_button_text()
        self.main.show_message(f"Restored {restored_count} history entries.")
