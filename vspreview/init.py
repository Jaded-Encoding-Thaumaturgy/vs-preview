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
from ._metadata import __version__

# import vsenv as early as possible:
# This is so other modules cannot accidentally use and lock us into a different policy.
from .core.vsenv import set_vsengine_loop
from .main import MainWindow
from .plugins import get_installed_plugins
from .plugins.abstract import FileResolverPlugin, ResolvedScript
from .plugins.install import (
    install_plugins,
    plugins_commands,
    print_available_plugins,
    uninstall_plugins,
)

__all__ = ["main"]


def get_resolved_script(
    filepath: Path,
) -> tuple[ResolvedScript, FileResolverPlugin | None] | int:
    for plugin in get_installed_plugins(FileResolverPlugin, False).values():
        if plugin.can_run_file(filepath):
            return plugin.resolve_path(filepath), plugin

    if not filepath.exists():
        logging.error("Script or file path is invalid.")
        return 1

    return ResolvedScript(filepath, str(filepath)), None


def main(_args: Sequence[str] | None = None, no_exit: bool = False) -> int:
    from .utils import exit_func

    parser = ArgumentParser(prog="VSPreview")
    parser.add_argument(
        "script_path_or_command",
        type=str,
        nargs="?",
        help=f'Path to Vapoursynth script, video file(s) or plugins command {", ".join(plugins_commands)}',
    )
    parser.add_argument(
        "plugins",
        type=str,
        nargs="*",
        help=f'Plugins to {"/".join(plugins_commands[:-1])} or arguments to pass to the script environment.',
    )
    parser.add_argument("--version", "-v", action="version", version="%(prog)s " + __version__)
    parser.add_argument(
        "--preserve-cwd",
        "-c",
        action="store_true",
        help="do not chdir to script parent directory",
    )
    parser.add_argument(
        "-f", "--frame", type=int, help="Frame to load initially (defaults to 0)"
    )
    parser.add_argument(
        "--vscode-setup",
        type=str,
        choices=["override", "append", "ignore"],
        nargs="?",
        const="append",
        help="Installs launch settings in cwd's .vscode",
    )
    parser.add_argument(
        "--verbose", help="Set the logging to verbose.", action="store_true"
    )
    parser.add_argument(
        "--force",
        help="Force the install of a plugin even if it exists already.",
        action="store_true",
    )
    parser.add_argument(
        "--no-deps", help="Ignore downloading dependencies.", action="store_true"
    )
    parser.add_argument(
        "--force-storage",
        help="Force override or local/global storage.",
        action="store_true",
        default=False,
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

    if not script_path_or_command and not (
        args.plugins and (script_path_or_command := next(iter(args.plugins)))
    ):
        logging.error("Script/Video path required.")
        return exit_func(1, no_exit)

    if script_path_or_command.startswith("--") and args.plugins:
        script_path_or_command = args.plugins.pop()
        args.plugins = [args.script_path_or_command, *args.plugins]

    if (command := script_path_or_command) in plugins_commands:
        if command == "available":
            print_available_plugins()
            return exit_func(0, no_exit)

        if not args.plugins:
            logging.error("You must provide at least one plugin!")
            return exit_func(1, no_exit)

        set_log_level(logging.INFO)

        plugins = list(args.plugins)

        if command == "install":
            install_plugins(plugins, args.force, args.no_deps)
        elif command == "uninstall":
            uninstall_plugins(plugins)
        elif command == "update":
            uninstall_plugins(plugins, True)
            install_plugins(plugins, True, args.no_deps)

        return exit_func(0, no_exit)

    script_or_err = get_resolved_script(Path(script_path_or_command).resolve())

    if isinstance(script_or_err, int):
        return exit_func(script_or_err, no_exit)

    script, file_resolve_plugin = script_or_err

    if (
        file_resolve_plugin
        and hasattr(file_resolve_plugin, "_config")
        and file_resolve_plugin._config.namespace == "dev.setsugen.vssource_load"
    ):
        setattr(args, "preserve_cwd", True)

    if not args.preserve_cwd:
        os.chdir(script.path.parent)

    first_run = not hasattr(main, "app")

    if first_run:
        main.app = QApplication(sys.argv)
        set_vsengine_loop()
    else:
        from .core.vsenv import get_current_environment, make_environment

        make_environment()
        get_current_environment().use()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    arguments = script.arguments.copy()

    def _parse_arg(kv: str) -> tuple[str, str | int | float]:
        v: str | int | float
        k, v = kv.split("=", maxsplit=1)

        try:
            v = int(v)
        except ValueError:
            try:
                v = float(v)
            except ValueError:
                ...

        return k.strip("--"), v

    if args.plugins:
        if file_resolve_plugin._config.namespace == "dev.setsugen.vssource_load":
            additional_files = list[Path](
                Path(filepath).resolve() for filepath in args.plugins
            )
            arguments.update(additional_files=additional_files)
        else:
            arguments |= {k: v for k, v in map(_parse_arg, args.plugins)}

    main.main_window = MainWindow(
        Path(os.getcwd()) if args.preserve_cwd else script.path.parent,
        no_exit,
        script.reload_enabled,
        args.force_storage,
    )
    main.main_window.load_script(
        script.path,
        list(arguments.items()),
        False,
        args.frame or None,
        script.display_name,
        file_resolve_plugin,
    )

    ret_code = main.app.exec()

    if no_exit:
        from .core.vsenv import _dispose

        main.main_window.hide()

        _dispose()

    return exit_func(ret_code, no_exit)


if __name__ == "__main__":
    main()
