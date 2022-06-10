With VIM
--------

``vs-preview`` is intended to work with an IDE that can use an integrated terminal.
One IDE that can do that is `Vim <https://www.vim.org/>`_.

Requirements
^^^^^^^^^^^^

The following programs must be installed before you begin:

* `Vim <https://www.vim.org/download.php>`_

Configuring VSCode
^^^^^^^^^^^^^^^^^^

1. Associate ``.vpy``` files with Vim
    1. Right-click a ``.vpy`` file and press ``Open with > Choose another app``
    2. Check "Always use this app to open .vpy files"
    3. Scroll down and click "More apps", then "Look for another app on this PC"
    4. Browse to your Vim install location and press "Open"

.. note::

   To get correct syntax highlighting, add `au BufReadPost,BufNewFile *.vpy setlocal syntax=python` to your `_vimrc`.

Running your script
^^^^^^^^^^^^^^^^^^^

.. note::

    The easiest way to run your .vpy file in Vim is by adding `:map r :!vspreview "%:p"<enter>` to your `_vimrc` and pressing `r` in Vim.

1. Open your ``_vimrc``
2. Add ``:map r :!vspreview "%:p"<enter>`` to your ``_vimrc`` file

You can now open the VapourSynth script you want to run in Vim
and run ``vs-preview`` by pressing ``r``.

If everything works properly,
it should open up a terminal at the bottom of the screen
and start printing something like this:

.. code-block:: bash

    2021-03-19 03:43:03.324: INFO: QSS file successfuly loaded.
    2021-03-19 03:43:03.328: INFO: Found application patches to be applied.
    2021-03-19 03:43:04.207: INFO: No storage found. Using defaults.

If there's an error with your script,
it will print it in the terminal.
If your script is fine,
it will open ``vspreview`` with the current script.
