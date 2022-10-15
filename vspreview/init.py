from __future__ import annotations

import json
import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, List, Literal, cast

from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtWidgets import QApplication

# import vsenv as early as possible:
# This is so other modules cannot accidentally use and lock us into a different policy.
from .core.vsenv import get_policy
from .main import MainSettings, MainWindow
from .utils import check_versions, get_temp_screen_resolution

get_policy()


class Application(QApplication):
    def notify(self, obj: QObject, event: QEvent) -> bool:
        isex = False
        try:
            return QApplication.notify(self, obj, event)
        except BaseException:
            isex = True
            logging.error('Application: unexpected error')
            logging.error(*sys.exc_info())
            return False
        finally:
            if isex:
                self.quit()


def main() -> None:
    logging.basicConfig(format='{asctime}: {levelname}: {message}', style='{', level=MainSettings.LOG_LEVEL)
    logging.Formatter.default_msec_format = '%s.%03d'
    if sys.stdout.isatty():
        logging.addLevelName(
            logging.DEBUG, "\033[0;32m%s\033[0m" % logging.getLevelName(logging.DEBUG)
        )
        logging.addLevelName(
            logging.INFO, "\033[1;33m%s\033[0m" % logging.getLevelName(logging.INFO)
        )
        logging.addLevelName(
            logging.WARNING, "\033[1;35m%s\033[1;0m" % logging.getLevelName(logging.WARNING)
        )
        logging.addLevelName(
            logging.ERROR, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR)
        )

    check_versions()

    parser = ArgumentParser(prog='VSPreview')
    parser.add_argument(
        'script_path', help='Path to Vapoursynth script', type=Path, nargs='?'
    )
    parser.add_argument(
        '--version', '-v', action='version', version='%(prog)s 0.2b'
    )
    parser.add_argument(
        '--preserve-cwd', '-c', action='store_true', help='do not chdir to script parent directory'
    )
    parser.add_argument(
        '--arg', '-a', type=str, action='append', metavar='key=value', help='Argument to pass to the script environment'
    )
    parser.add_argument('-f', '--frame', type=int, help='Frame to load initially (defaults to 0)')
    parser.add_argument(
        '--vscode-setup', type=str, choices=['override', 'append', 'ignore'], nargs='?', const='append',
        help='Installs launch settings in cwd\'s .vscode'
    )

    args = parser.parse_args()

    if args.vscode_setup is not None:
        install_vscode_launch(args.vscode_setup)
        sys.exit(0)

    if args.script_path is None:
        logging.error('Script path required.')
        sys.exit(1)

    script_path = args.script_path.resolve()
    if not script_path.exists():
        logging.error('Script path is invalid.')
        sys.exit(1)

    if not args.preserve_cwd:
        os.chdir(script_path.parent)

    width, height = get_temp_screen_resolution()

    hidpi = width > 1920 and height > 1080
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, hidpi)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, hidpi)

    app = Application(sys.argv)
    main_window = MainWindow(Path(os.getcwd()) if args.preserve_cwd else script_path.parent)
    main_window.load_script(
        script_path, [tuple(a.split('=', maxsplit=1)) for a in args.arg or []], False, start_frame=args.frame or None
    )
    main_window.show()

    app.exec_()


def install_vscode_launch(mode: Literal['override', 'append', 'ignore']) -> None:
    vscode_settings_path = Path.cwd() / '.vscode'
    vscode_settings_path.mkdir(0o777, True, True)

    settings = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "VS Preview Current File",
                "type": "python",
                "request": "launch",
                "console": "integratedTerminal",
                "module": "vspreview",
                "args": ["${file}"],
                "showReturnValue": True,
                "subProcess": True
            },
            {
                "name": "Run Current File",
                "type": "python",
                "request": "launch",
                "console": "integratedTerminal",
                "program": "${file}",
                "showReturnValue": True,
                "subProcess": True
            }
        ]
    }

    launch = vscode_settings_path / 'launch.json'

    if launch.exists():
        if mode == 'ignore':
            return
    else:
        launch.touch()

    current_settings = settings.copy()

    def _write() -> None:
        with open(launch, 'w') as f:
            json.dump(current_settings, f, indent=4)
        return

    if mode != 'append':
        return _write()

    with open(launch, 'r+') as f:
        try:
            current_settings = json.loads(f.read())
        except json.JSONDecodeError:
            current_settings = {}

    if 'configurations' not in current_settings or len(current_settings['configurations']) == 0:
        current_settings['configurations'] = settings['configurations']
        return _write()

    cast(List, current_settings['configurations']).extend(settings['configurations'])

    current_settings['configurations'] = list({
        ':'.join(str(row[column]) for column in row.keys()): row
        for row in cast(List[Dict[str, str]], current_settings['configurations'])
    }.values())

    return _write()


if __name__ == '__main__':
    main()
