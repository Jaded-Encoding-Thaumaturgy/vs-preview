#!/usr/bin/env python3
# coding: utf-8

from setuptools import find_packages, setup

with open("README.md", "r", encoding="UTF-8") as rdm:
    long_desc = rdm.read()

with open("requirements.txt", "r", encoding="UTF-8") as rq:
    req = rq.read()

setup(
    name="vspreview",
    version="0.2.2b",
    author="Endilll",
    maintainer='Setsugennoao',
    maintainer_email='setsugen@setsugen.dev',
    description="Preview for VapourSynth scripts",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url="https://github.com/Irrational-Encoding-Wizardry/vs-preview",
    packages=find_packages('.', ("docs", "stubs")),
    install_requires=req,
    python_requires=">=3.9",
    zip_safe=False,
        project_urls={
            'Documentation': 'https://github.com/Irrational-Encoding-Wizardry/vs-preview/#readme',
            'Source': 'https://github.com/Irrational-Encoding-Wizardry/vs-preview',
            'Tracker': 'https://github.com/Irrational-Encoding-Wizardry/vs-preview/issues'
    },
    classifiers=[
        "Topic :: Multimedia :: Graphics",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'vspreview = vspreview.init:main'
        ]
    }
)
