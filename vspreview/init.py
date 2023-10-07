from __future__ import annotations

from . import qt_patch  # noqa: F401

import logging
import os
import signal
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Sequence

from PyQt6.QtWidgets import QApplication

from .core.logger import set_log_level, setup_logger
# import vsenv as early as possible:
# This is so other modules cannot accidentally use and lock us into a different policy.
from .core.vsenv import set_vsengine_loop
from .main import MainWindow
from .plugins.install import install_plugins, plugins_commands, uninstall_plugins

__all__ = [
    'main'
]


def main(_args: Sequence[str] | None = None, no_exit: bool = False) -> None:
    from .utils import exit_func

    parser = ArgumentParser(prog='VSPreview')
    parser.add_argument(
        'script_path_or_command', type=str, nargs='?',
        help=f'Path to Vapoursynth script or plugins command {",".join(plugins_commands)}'
    )
    parser.add_argument(
        'plugins', type=str, nargs='*',
        help='Plugins to install/uninstall/update'
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
    parser.add_argument(
        "--verbose", help="Set the logging to verbose.", action="store_true"
    )
    parser.add_argument(
        "--force", help="Force the install of a plugin even if it exists already.", action="store_true"
    )
    parser.add_argument(
        "--no-deps", help="Ignore downloading dependencies.", action="store_true"
    )

    args = parser.parse_args(_args)

    setup_logger()

    if args.verbose:
        from vstools import VSDebug
        set_log_level(logging.DEBUG, logging.DEBUG)
        VSDebug(use_logging=True)
    else:
        set_log_level(logging.WARNING)

    if args.vscode_setup is not None:
        from .api.other import install_vscode_launch

        install_vscode_launch(args.vscode_setup)

        return exit_func(0, no_exit)

    script_path_or_command = args.script_path_or_command

    if not script_path_or_command and not (args.plugins and (script_path_or_command := next(iter(args.plugins)))):
        logging.error('Script path required.')
        return exit_func(1, no_exit)

    if (command := script_path_or_command) in plugins_commands:
        if not args.plugins:
            logging.error('You must provide at least one plugin!')
            return exit_func(1, no_exit)

        set_log_level(logging.INFO)

        plugins = list(args.plugins)

        if command == 'install':
            install_plugins(plugins, args.force, args.no_deps)
        elif command == 'uninstall':
            uninstall_plugins(plugins)
        elif command == 'update':
            uninstall_plugins(plugins, True)
            install_plugins(plugins, True, args.no_deps)

        return exit_func(0, no_exit)

    script_path = Path(script_path_or_command).resolve()
    if not script_path.exists():
        logging.error('Script path is invalid.')
        return exit_func(1, no_exit)

    if not args.preserve_cwd:
        os.chdir(script_path.parent)

    first_run = not hasattr(main, 'app')

    if first_run:
        main.app = QApplication(sys.argv)
        set_vsengine_loop()
    else:
        from .core.vsenv import make_environment, get_current_environment
        make_environment()
        get_current_environment().use()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    main.main_window = MainWindow(Path(os.getcwd()) if args.preserve_cwd else script_path.parent, no_exit)
    main.main_window.load_script(
        script_path, [tuple(a.split('=', maxsplit=1)) for a in args.arg or []], False, args.frame or None
    )
    main.main_window.show()

    ret_code = main.app.exec()

    if no_exit:
        from .core.vsenv import _dispose

        main.main_window.hide()

        _dispose()

    return exit_func(ret_code, no_exit)


if __name__ == '__main__':
    main()
