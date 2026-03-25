With Visual Studio Code
-----------------------

``vs-preview`` is intended to work with an IDE that can use an integrated terminal.
One IDE that can do that is Microsoft's free code editor, `Visual Studio Code <https://code.visualstudio.com>`_.

Requirements
^^^^^^^^^^^^

The following programs must be installed before you begin:

* `Visual Studio Code <https://code.visualstudio.com/download>`_

Configuring Visual Studio Code
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. If you have not already, install the `Python Extension <https://marketplace.visualstudio.com/items?itemName=ms-python.python>`_
2. Associate ``.vpy`` files with Python
    1. Open Visual Studio Code's setting menu via ``File > Preferences > Settings`` or the ``Ctrl +`` hotkey
    2. Search for ``files.associations``
    3. Click the "Add Item" button
    4. Fill in ``*.vpy`` for the "Item" field
    5. Fill in ``python`` for the "Value" field
    6. Click the "OK" button

Configuring the launch file
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To easily run ``vs-preview`` on your script,
we'll create a "launch" file.

You can automatically generate or update the ``launch.json`` file by running the
following command in your terminal:

.. code-block:: bash

    python -m vspreview --vscode-setup append

Alternatively, you can manually create the file:

1. Select the **Run** view in the sidebar.
2. Select the **create a launch.json file** link or use the **Run** > **Open configurations** menu command.
3. Select **Python Debugger** from the debugger options list.
4. Select **Python File** in the **Select a debug configuration** menu that appears.
5. Replace the contents of the generated ``launch.json`` file with the following code:

.. code-block:: json

    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "VS Preview Current File",
                "type": "debugpy",
                "request": "launch",
                "module": "vspreview",
                "args": ["${file}"],
                "console": "internalConsole"
            },
            {
                "name": "Run Current File",
                "type": "debugpy",
                "request": "launch",
                "program": "${file}",
                "console": "internalConsole"
            }
        ]
    }

Running your scripts
^^^^^^^^^^^^^^^^^^^^

You can now open the VapourSynth script you want to run in Visual Studio Code
and run ``vs-preview`` by selecting "VS Preview Current File" from the
"Run and Debug" view and pressing ``F5`` or the ▷ button.

If everything works properly,
it should open up the Debug Console at the bottom of the screen
and start printing something like this:

.. code-block:: text

    2021-03-19 03:43:03.324: INFO: QSS file successfully loaded.
    2021-03-19 03:43:03.328: INFO: Found application patches to be applied.
    2021-03-19 03:43:04.207: INFO: No storage found. Using defaults.

If there's an error with your script,
it will print it in the Debug Console.
If your script is fine,
it will open ``vs-preview`` with the current script.
