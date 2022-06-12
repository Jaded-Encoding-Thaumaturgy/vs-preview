# Installation in Vim

vs-preview can be used in a number of different ways.<br>One of them is directly in the free code editor [Vim](https://www.vim.org/).

The following is a way to integrate vs-preview into Vim. 

### Make sure you have the prerequisites installed!


## Configuring Vim to use Python and `.vpy` Files

1. Associate `.vpy` files with Vim.
    1. Right click your `.vpy` file and choose `Open with > Choose another app`.
    1. Check `Always use this app to open .vpy files`.
    1. Scroll down and click `More apps`, then `Look for another app on this PC`.
    1. Browse to Vim and click `Open`.
        * To get correct syntax highlighting, add `au BufReadPost,BufNewFile *.vpy setlocal syntax=python` to your `_vimrc`.

## Running scripts with vs-preview in Vim

Now that you've configured your scripts to use Vim, it's time to run them. 

1. Open your `.vpy` file in Vim.
1. Type `:` to enter command mode.
1. Run the `.vpy` file with `!vspreview "%:p"`.
    * The easiest way to run your .vpy file in Vim is by adding `:map r :w<enter>:!vspreview "%:p"<enter>` to your `_vimrc` and pressing `r` in Vim. 
1. You should see a terminal open in front of your script with something like this:
    ```cmd
    2021-03-19 03:43:03.324: INFO: QSS file sucessfuly loaded.
    2021-03-19 03:43:03.328: INFO: Found application patches to be applied.
    2021-03-19 03:43:04.207: INFO: No storage found. Using defaults.
    ```
    * Any Python debug or console output (print statement) in your script should output into this terminal window.
1. Assuming your `.vpy` file is free from errors, a new window will open and display your video.
