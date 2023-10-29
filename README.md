# Standalone previewer for VapourSynth scripts

Fork of Endilll's [vapoursynth-preview](https://github.com/Endilll/vapoursynth-preview) (not maintained anymore)

This program is meant to be paired with a code editor with integrated terminal like Visual Studio Code.

# Prerequisites

1. [Python](https://www.Python.org/downloads) (3.10+ required)
   - Make sure to install Python to your `PATH`.
1. [VapourSynth](https://github.com/vapoursynth/vapoursynth/releases) (R60+ required)

# Installation

Install latest stable via pypi:

```bash
pip install vspreview
```

Install latest git:

```bash
pip install -U git+https://github.com/Setsugennoao/vs-preview.git
```

# Usage

It can be used by running `vspreview script.vpy` or your preferred way in [your IDE](#ide-integration).

[Keyboard Shortcuts](https://github.com/Setsugennoao/vs-preview/blob/master/docs/accessibility/keybinds.rst)

[Saved Frame Filename Variables](https://github.com/Setsugennoao/vs-preview/tree/master/docs/save_frame_placeholders.md)

# IDE Integration

- [Visual Studio Code](https://github.com/Setsugennoao/vs-preview/tree/master/docs/installation/install_vscode.rst)
- [Vim](https://github.com/Setsugennoao/vs-preview/tree/master/docs/installation/install_vim.rst)
- [Notepad++](https://github.com/Setsugennoao/vs-preview/tree/master/docs/installation/install_notepad++.rst)

# Plugins

You can install external plugins by using the following command:

```bash
vspreview install [plugin-name]
```

A list of plugins can be found in [this repo](https://github.com/Setsugennoao/vs-preview-plugins). `plugin-name` is the name of the plugin directory in the repo.

To develop new plugins or manually install them, create a .ppy file inside the global plugins directory. You can find the path to that in the storage file. You can add additional search paths by adding them to a .pth file inside the global plugins directory, just like you can with python path and site-packages.
