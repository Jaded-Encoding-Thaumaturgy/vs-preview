# Installation in VS Code

Vapoursynth Preview can be used in a number of different ways.<br>One of them is directly in Microsoft's free code editor [Visual Studio Code](https://code.visualstudio.com).

The following is a way to integrate VS-Preview into VSCode. 

### Make sure you have the prerequisites installed!


## Configuring VSCode to use Python and `.vpy` Files

1. If you have not already, install the [Python Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python).
1. Associate `.vpy` files with Python.
    1. Open VSCode settings via `File > Preferences > Settings` or the `Ctrl + ,` hotkey.
    1. Search for `files.associations`.
    1. Select the "Add Item" button.
    1. Enter `*.vpy` for the "Item".
    1. Enter `python` for the "Value".
    1. Select the "OK" button.

## Setting Up a `launch.json` File

To properly map your `.vpy` Vapoursynth files to not just the Python executable environment, but also to VSPreview project folder workspace, you'll need to create a settings file called `launch.json`. 

1. Create a new folder in your global `.vscode` settings folder (%APPDATA%\\..\\..\\.vscode) named `vspreview`.
1. Create a `launch.json` inside of your new folder and add the following:
    ```json
    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "VS Preview Current File",
                "type": "python",
                "request": "launch",
                "console": "integratedTerminal",
                "module": "vspreview",
                "args": ["${file}"],
                "showReturnValue": true,
                "subProcess": true
            }
        ]
    }
    ```
1. Save your `launch.json`.

## Setting Up Your Project Environment

Now that you've installed the prerequisites, you can begin working on your first project.

If you've saved your `launch.json` directly into `.vscode/launch.json`, you can skip this section entirely. 

1. Open VSCode.
1. Open an existing or create a new folder where your project files will be saved and open it in VSCode.
    * For "multi-episode" projects, you can select the top level directory that will contain all of your project files or you can select just the single episode's project dirctory.
1. Add the `launch.json` to your project directory. Two options:
    1. Create a new `project/.vscode` directory and copy your `launch.json` into it.
    1. Use a VSCode extension to link your global `~/.vscode/vspreview` directory into your current project folder. 
        1. Install [Global Config](https://marketplace.visualstudio.com/items?itemName=Gruntfuggly.global-config) or another alternative extension.
        1. Use the Command Pallette to run Global Config by pressing the `Ctrl + Shift + P` hotkey.
        1. Type "Copy Global Config".
            * Note that at this stage you can assign a hotkey to run Global Config by clicking the gear icon at the end of the search result.
        1. Select your `~/.vscode/vspreview` directory.
        1. All of your settings will be copied to your project directory in `project/.vscode/launch.json`.

**Note:** Step 3 will need to be completed for every new project unless you've saved your `launch.json` directly in `~/.vscode`. If you use the Global Config extension, you will only need to run the extension for each new project directory one time.

## Running scripts with VSPreview in VSCode

Now that you've configured your current project to use VS-Preview. It's time to run it. 

1. Add your `.vpy` file to your workspace either by creating a new file or copying in an existing one. 
1. Open the `.vpy` file.
1. Run the `.vpy` file.
    * The easiest way to run your .vpy file in VSCode is by using the native "Start Debugging" functionality in VSCode either via `Run > Start Debugging` in the menu, or via the `F5` hotkey. 
1. You should see a terminal open at the bottom of the screen with something like this:
    ```powershell
    PS G:\project>& 'D:\Python39\python.exe' 'c:\Users\...\debugpy\launcher' '62134' '--' '~/vapoursynth-preview/run.py' 'G:\project\episode_1_720p.vpy'
    2021-03-19 03:43:03.324: INFO: QSS file sucessfuly loaded.
    2021-03-19 03:43:03.328: INFO: Found application patches to be applied.
    2021-03-19 03:43:04.207: INFO: No storage found. Using defaults.
    ```
    * Any Python debug or console output (print statement) in your script should output into this terminal window.
1. Assuming your `.vpy` file is free from errors, a new window will open and display your video.