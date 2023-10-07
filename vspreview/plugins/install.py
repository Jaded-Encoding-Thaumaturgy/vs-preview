from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Iterable

from ..main import MainWindow

BASE_URL = 'https://api.github.com/repos'
PLUGINS_PATH = 'Irrational-Encoding-Wizardry/vs-preview-plugins'
BRANCH = 'master'

CONTENT_URL = f'https://raw.githubusercontent.com/{PLUGINS_PATH}/{BRANCH}/{{path}}'

plugins_commands = ('install', 'uninstall', 'update')


def get_plugins() -> dict[str, Iterable[str]]:
    from requests import get

    response = get(f'{BASE_URL}/{PLUGINS_PATH}/git/trees/{BRANCH}?recursive=1')

    if response.status_code != 200:
        logging.error('There was an error fetching plugin data!')
        sys.exit(1)

    data = response.json()

    if data['truncated']:
        logging.error('Bug setsu to fix!')
        sys.exit(1)

    data = data['tree']

    base_paths = list[str](set(d['path'] for d in data if d['type'] == 'tree' and '/' not in d['path']))

    def _get_generator(path: str) -> Iterable[str]:
        return (
            d['path'] for d in data
            if ('type' not in d or d['type'] != 'tree') and d['path'].startswith(f'{path}/')
        )

    return {path: _get_generator(path) for path in base_paths}


def install_plugins(plugins: list[str], force: bool = False, no_deps: bool = False) -> None:
    from shutil import copytree, rmtree
    from subprocess import Popen
    from tempfile import TemporaryDirectory

    from requests import Session

    existing_plugins = get_plugins()

    found_plugins = set(existing_plugins.keys()).intersection(plugins)

    not_found_plugins = set(plugins) - found_plugins
    if not_found_plugins:
        logging.warn(f'Not found the following plugins: "{", ".join(not_found_plugins)}"')

    with Session() as s:
        for plugin in found_plugins:
            if (MainWindow.global_plugins_dir / plugin).exists():
                if not force:
                    logging.info(f'Skipping "{plugin}" as it\'s already installed.')
                    continue
                else:
                    rmtree(MainWindow.global_plugins_dir / plugin)

            logging.info(f'Downloading "{plugin}"...')

            with TemporaryDirectory() as tempdir:
                tempdir = Path(tempdir)

                requirements = list[Path]()

                for file in existing_plugins[plugin]:
                    logging.info(f'Collecting "{file}"...')

                    temp = tempdir / file
                    (temp if temp.is_dir() else temp.parent).mkdir(parents=True, exist_ok=True)

                    with s.get(CONTENT_URL.format(path=file), stream=True) as req:
                        req.raise_for_status()
                        with temp.open('wb') as f:
                            for chunk in req.iter_content(8192):
                                f.write(chunk)

                    if Path(file).name == 'requirements.txt':
                        requirements.append(temp)

                for requirement in requirements:
                    if not no_deps:
                        Popen([sys.executable, '-m', 'pip', 'install', '-r', str(requirement)]).wait()
                    requirement.unlink()

                copytree(tempdir / plugin, MainWindow.global_plugins_dir / plugin)


def uninstall_plugins(plugins: list[str], ignore: bool = False) -> None:
    from shutil import rmtree

    not_found_plugins = set[str]()

    for plugin in plugins:
        if (MainWindow.global_plugins_dir / plugin).exists():
            rmtree(MainWindow.global_plugins_dir / plugin)
        else:
            not_found_plugins.add(plugin)

    if ignore:
        return

    found_plugins = set(plugins) - not_found_plugins

    if not_found_plugins:
        logging.warn(f'Not found the following plugins: "{", ".join(not_found_plugins)}"')

    logging.info(f'Successfully uninstalled "{", ".join(found_plugins)}"')
