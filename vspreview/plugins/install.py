from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Iterable

from ..main import MainWindow
from . import get_installed_plugins
from .abstract import AbstractPlugin, FileResolverPlugin

BASE_URL = 'https://api.github.com/repos'
REPO_NAME = 'vs-preview-plugins'
PLUGINS_PATH = f'Jaded-Encoding-Thaumaturgy/{REPO_NAME}'
BRANCH = 'master'

CONTENT_URL = f'https://raw.githubusercontent.com/{PLUGINS_PATH}/{BRANCH}/{{path}}'

PLUGIN_STRING = ' {:25s}{install_from}{:10s} {:30s} {:s}'

plugins_commands = ('install', 'uninstall', 'update', 'available')


def get_repo_plugins() -> dict[str, Iterable[str]]:
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

    existing_packages = get_repo_plugins()

    found_plugins = set(existing_packages.keys()).intersection(plugins)

    not_found_plugins = set(plugins) - found_plugins
    if not_found_plugins:
        logging.warning(f'Could not find the following plugins: "{", ".join(not_found_plugins)}"')

    with Session() as s:
        for plugin in found_plugins:
            if (MainWindow.global_plugins_dir / plugin).exists():
                if not force:
                    logging.info(f'Skipping "{plugin}" as it\'s already installed.')
                    continue
                else:
                    rmtree(MainWindow.global_plugins_dir / plugin)

            logging.info(f'Downloading "{plugin}"...')

            with TemporaryDirectory() as tmpdir:
                tempdir = Path(tmpdir)

                requirements = list[Path]()

                for file in existing_packages[plugin]:
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
        logging.warning(f'Could not find plugins: "{", ".join(not_found_plugins)}"')

    logging.info(f'Successfully uninstalled "{", ".join(found_plugins)}"')


def print_available_plugins() -> None:
    existing_packages = set(get_repo_plugins().keys())

    def _header(value: str) -> str:
        return f'{value}\n{"-" * len(value)}'

    installed_plugins = [
        (
            plugin_cls.__module__, kind, plugin_cls._config.display_name,
            plugin_cls._config.namespace, sys.modules[plugin_cls.__module__].__file__
        )
        for kind, plugin_parent in (('Generic', AbstractPlugin), ('Source', FileResolverPlugin))
        for plugin_cls in [v for _, v in sorted(get_installed_plugins(plugin_parent, True).items(), key=lambda v: v[0])]
    ]

    preinstalled_packages = set[Path]()
    installed_packages = set[str](module for module, *_ in installed_plugins)

    plugins_path = Path(__file__).parent

    print(_header('Installed plugins:'))
    print(PLUGIN_STRING.format('Package', 'Type', 'Name', 'Namespace', install_from=''))

    for *values, module_path in installed_plugins:
        if not module_path:
            continue

        install_path = Path(module_path).parent

        if plugins_path == install_path:
            preinstalled_packages.add(install_path)
        elif (MainWindow.global_plugins_dir in install_path.parents) or (install_path.parent.stem == REPO_NAME):
            installed_packages.add(install_path.stem)

    for *values, module_path in installed_plugins:
        if module_path:
            pkg_name = Path(module_path).parent

            if pkg_name in preinstalled_packages:
                install_from = '*'
            elif pkg_name.stem in existing_packages:
                install_from = '+'
            else:
                install_from = '?'
        else:
            install_from = ' '

        print(' ' + PLUGIN_STRING.format(*values, install_from=install_from))

    print('\n * => Pre-installed, + => Installed, ? => Custom\n')

    external_packages = existing_packages - installed_packages

    print(_header('Missing VSPreview Plugins:'))

    if not len(external_packages):
        print('  None found!')
    else:
        print('  ' + ', '.join(external_packages))
