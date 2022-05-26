# Standalone previewer for VapourSynth scripts

Fork of Endilll's [vapoursynth-preview](https://github.com/Endilll/vapoursynth-preview) (not maintained anymore)

This program is meant to be paired with a code editor with integrated terminal like Visual Studio Code.

# Prerequisites

1. [Python](https://www.Python.org/downloads) (3.9+ required)
    * Make sure to install Python to your `PATH`.
1. [Vapoursynth](https://github.com/vapoursynth/vapoursynth/releases) (R57+ required, R58+ required for audio)

**Note:** If you're on Python 3.10, you'll need VapourSynth R58.

# Installation and usage

Install latest stable via pypi:
```bash
pip install vspreview
```


Install latest git:
```bash
pip install -U git+https://github.com/Irrational-Encoding-Wizardry/vs-preview.git
```

It can then be used by running `vspreview script.vpy` or your preferred way in your IDE.

# IDE Integration

* [VSCode](https://github.com/Irrational-Encoding-Wizardry/vs-preview/tree/master/docs/vscode_install.md)
