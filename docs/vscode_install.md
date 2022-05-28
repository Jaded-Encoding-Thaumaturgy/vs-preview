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

To be able to run the file you're currently working on,<br>you'll need to set up a launch.json file,
which tells Visual Studio Code what to do to run it with VS Preview

This is easier said then done

1. Open VSCode.
1. Open an existing or create a new folder where your project files will be saved and open it in VSCode.
    * For "multi-episode" projects, you should select the top level directory that will contain all of your project files.<br>The rule of thumb is doing this in the folder you'll have open and work on.
1. Add the `launch.json` to your project directory.<br>
    Open the terminal by doing `Ctrl + Shift + P and typing "Terminal: Create New Terminal" and write the following:

    ```powershell
    vspreview --vscode-setup
    ```
1. Congratulations, you can now write and preview beautiful filterchains!

**Note:** Step 3 will need to be completed for every new project unless you've saved your `launch.json` directly in `~/.vscode`.

## Running scripts with VSPreview in VSCode

Now that you've configured your current project to use VSPreview. It's time to run it. 

1. Add your `.vpy` file to your workspace either by creating a new file or copying in an existing one. 
1. Open the `.vpy` file.
1. Run the `.vpy` file.
    * The easiest way to run your .vpy file in VSCode is by using the native "Start Debugging" functionality in VSCode<br>either via `Run > Start Debugging` in the menu, or via the `F5` hotkey. 
1. You should see a terminal open at the bottom of the screen with something like this:
    ```powershell
    PS G:\project>& 'D:\Python39\python.exe' 'c:\Users\...\debugpy\launcher' '62134' '--' '~/vapoursynth-preview/run.py' 'G:\project\episode_1_720p.vpy'
    2021-03-19 03:43:03.324: INFO: QSS file sucessfuly loaded.
    2021-03-19 03:43:03.328: INFO: Found application patches to be applied.
    2021-03-19 03:43:04.207: INFO: No storage found. Using defaults.
    ```
    * Any Python debug or console output (print statement) in your script should output into this terminal window.
1. Assuming your `.vpy` file is free from errors, a new window will open and display your video.
