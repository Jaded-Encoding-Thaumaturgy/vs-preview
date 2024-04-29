
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

__all__ = [
    'install_vscode_launch'
]


def install_vscode_launch(mode: Literal['override', 'append', 'ignore'], path: str | Path | None = None) -> None:
    vscode_settings_path = Path(path or Path.cwd()) / '.vscode'
    vscode_settings_path.mkdir(0o777, True, True)

    common_args = {
        "type": "debugpy",
        "request": "launch",
        "console": "internalConsole",
        "gevent": False,
        "justMyCode": True,
        "logToFile": False,
        "subProcess": False,
        "redirectOutput": True,
        "showReturnValue": False,
        "suppressMultipleSessionWarning": False
    }

    settings = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "VS Preview Current File",
                "module": "vspreview",
                "args": [
                    "${file}"
                ],
                **common_args  # type: ignore
            },
            {
                "name": "Run Current File",
                "program": "${file}",
                **common_args  # type: ignore
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

    with open(launch, 'r+', encoding='utf-8') as f:
        try:
            current_settings = json.loads(f.read())
        except json.JSONDecodeError:
            current_settings = {}

    if 'configurations' not in current_settings or len(current_settings['configurations']) == 0:
        current_settings['configurations'] = settings['configurations']
        return _write()

    cast(list[Any], current_settings['configurations']).extend(settings['configurations'])

    current_settings['configurations'] = list({
        (
            '____' if row['name'] == 'VS Preview Current File' else
            ':'.join(str(row[column]) for column in row.keys())
        ): row
        for row in cast(list[dict[str, str]], current_settings['configurations'])
    }.values())

    return _write()
