#!/usr/bin/env python3

import setuptools
from pathlib import Path

package_name = 'vspreview'

exec(Path(f'{package_name}/_metadata.py').read_text(), meta := dict[str, str]())

readme = Path('README.md').read_text()
requirements = Path('requirements.txt').read_text()


setuptools.setup(
    name=package_name,
    version=meta['__version__'],
    author=meta['__author_name__'],
    author_email=meta['__author_email__'],
    maintainer=meta['__maintainer_name__'],
    maintainer_email=meta['__maintainer_email__'],
    description=meta['__doc__'],
    long_description=readme,
    long_description_content_type='text/markdown',
    zip_safe=False,
    project_urls={
        'Source Code': 'https://github.com/Setsugennoao/vs-preview',
        'Contact': 'https://discord.gg/setsugen'
    },
    install_requires=requirements,
    python_requires='>=3.11',
    packages=setuptools.find_packages('.', ('docs', 'stubs')),
    package_data={
        package_name: ['py.typed'],
        f'{package_name}.plugins': [
            file.name for file in (Path(package_name) / 'plugins').glob('*.ppy')
        ]
    },
    classifiers=[
        'Topic :: Multimedia :: Graphics',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    entry_points={
        'console_scripts': [
            'vspreview = vspreview.init:main'
        ]
    },
    command_options={
        "build_sphinx": {
            "project": ("setup.py", package_name),
            "version": ("setup.py", meta['__version__']),
            "release": ("setup.py", meta['__version__']),
            "source_dir": ("setup.py", "docs")
        }
    }
)
