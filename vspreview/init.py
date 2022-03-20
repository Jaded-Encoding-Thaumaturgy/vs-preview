from __future__ import annotations

import os
import sys
import logging
import pretty_traceback
from pathlib import Path
from argparse import ArgumentParser

from PyQt5.QtCore import QEvent, QObject
from PyQt5.QtWidgets import QApplication

# import vsenv as early as possible:
# This is so other modules cannot accidentally use and lock us into a different policy.
from .core.vsenv import get_policy
from .main import MainWindow
from .utils import check_versions

pretty_traceback.install()
get_policy()


class Application(QApplication):
    def notify(self, obj: QObject, event: QEvent) -> bool:
        isex = False
        try:
            return QApplication.notify(self, obj, event)
        except Exception:
            isex = True
            logging.error('Application: unexpected error')
            print(*sys.exc_info())
            return False
        finally:
            if isex:
                self.quit()


def main() -> None:
    logging.basicConfig(format='{asctime}: {levelname}: {message}', style='{', level=MainWindow.LOG_LEVEL)
    logging.Formatter.default_msec_format = '%s.%03d'

    check_versions()

    parser = ArgumentParser()
    parser.add_argument(
        'script_path', help='Path to Vapoursynth script', type=Path, nargs='?'
    )
    parser.add_argument(
        '-c', '--preserve-cwd', action='store_true', help='do not chdir to script parent directory'
    )
    parser.add_argument(
        '-a', '--arg', type=str, action='append', metavar='key=value', help='Argument to pass to the script environment'
    )
    args = parser.parse_args()

    if args.script_path is None:
        print('Script path required.')
        sys.exit(1)

    script_path = args.script_path.resolve()
    if not script_path.exists():
        print('Script path is invalid.')
        sys.exit(1)

    if not args.preserve_cwd:
        os.chdir(script_path.parent)

    app = Application(sys.argv)
    main_window = MainWindow(Path(os.getcwd()) if args.preserve_cwd else script_path.parent)
    main_window.load_script(script_path, [tuple(a.split('=', maxsplit=1)) for a in args.arg or []], False)
    main_window.show()

    app.exec_()


if __name__ == '__main__':
    main()
