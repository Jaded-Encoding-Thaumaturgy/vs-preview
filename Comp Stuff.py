from typing import Any, Dict, List, Optional, BinaryIO, TextIO, Union, Callable, Type, TypeVar, Sequence, cast
from concurrent.futures import Future
from threading import Condition
from functools import partial
from requests import Session
import vapoursynth as vs
import random
import time
import os

# Comp Stuff
# select index for base clip
# trim
"""
I do not provide support for this unless its an actual error in the code and not related to your setup.
You'll need:
- Vapoursynth (this was written & tested on R53 with Python 3.9.6)
- pip3 install pathlib anitopy pyperclip requests requests_toolbelt
- https://github.com/HolyWu/L-SMASH-Works/releases/latest/ (Install to your usual Vapoursynth plugins64 folder)
- (if using ffmpeg) ffmpeg installed & in path
How to use:
- Drop comp.py into a folder with the video files you want
- (Recommended) Rename your files to have the typical [Group] Show - EP.mkv naming, since the script will try to parse the group and show name.
e.g. [JPBD] Youjo Senki - 01.m2ts ("fakegroup" for JPBDs so the imagefiles will have JPBD in the name)
- Change vars below (trim if needed)
- Run comp.py
"""

# Change these if you need to

# Ram Limit (in MB)
ram_limit = 6000

# Framecounts
frame_count_dark = 8
frame_count_bright = 4

# Automatically upload to slow.pics
slowpics = True

# Output slow.pics link to discord webhook (disabled if empty)
webhook_url = r""

# Upscale videos to make the clips match the highest found res
upscale = True

# Use ffmpeg as the image renderer (ffmpeg needs to be in path)
ffmpeg = True

"""
Used to trim clips.
Example:
trim_dict = {0: 1000, 1: 1046}
Means:
First clip should start at frame 1000
Second clip should start at frame 1046
(Clips are taken in alphabetical order of the filenames)
"""
trim_dict = {}

# Not recommended to change stuff below

RenderCallback = Callable[[int, vs.VideoFrame], None]
VideoProp = Union[int, Sequence[int],
                  float, Sequence[float],
                  str, Sequence[str],
                  vs.VideoNode, Sequence[vs.VideoNode],
                  vs.VideoFrame, Sequence[vs.VideoFrame],
                  Callable[..., Any],
                  Sequence[Callable[..., Any]]]
T = TypeVar("T", bound=VideoProp)
vs.core.max_cache_size = ram_limit


def lazylist(clip: vs.VideoNode, dark_frames: int = 8, light_frames: int = 4, seed: int = 20202020, diff_thr: int = 15):
    """
    Blame Sea for what this shits out
    A function for generating a list of frames for comparison purposes.
    Works by running `core.std.PlaneStats()` on the input clip,
    iterating over all frames, and sorting all frames into 2 lists
    based on the PlaneStatsAverage value of the frame.
    Randomly picks frames from both lists, 8 from `dark` and 4
    from `light` by default.
    :param clip:          Input clip
    :param dark_frame:    Number of dark frames
    :param light_frame:   Number of light frames
    :param seed:          seed for `random.sample()`
    :param diff_thr:      Minimum distance between each frames (In seconds)
    :return:              List of dark and light frames
    """

    dark = []
    light = []

    def checkclip(n, f, clip):

        avg = f.props["PlaneStatsAverage"]

        if 0.062746 <= avg <= 0.380000:
            dark.append(n)

        elif 0.450000 <= avg <= 0.800000:
            light.append(n)

        return clip

    s_clip = clip.std.PlaneStats()

    eval_frames = vs.core.std.FrameEval(
        clip, partial(checkclip, clip=s_clip), prop_src=s_clip
    )
    print('Rendering clip to get frames...')
    clip_async_render(eval_frames)

    dark.sort()
    light.sort()

    dark_dedupe = [dark[0]]
    light_dedupe = [light[0]]

    thr = round(clip.fps_num / clip.fps_den * diff_thr)
    lastvald = dark[0]
    lastvall = light[0]

    for i in range(1, len(dark)):

        checklist = dark[0:i]
        x = dark[i]

        for y in checklist:
            if x >= y + thr and x >= lastvald + thr:
                dark_dedupe.append(x)
                lastvald = x
                break

    for i in range(1, len(light)):

        checklist = light[0:i]
        x = light[i]

        for y in checklist:
            if x >= y + thr and x >= lastvall + thr:
                light_dedupe.append(x)
                lastvall = x
                break

    if len(dark_dedupe) > dark_frames:
        random.seed(seed)
        dark_dedupe = random.sample(dark_dedupe, dark_frames)

    if len(light_dedupe) > light_frames:
        random.seed(seed)
        light_dedupe = random.sample(light_dedupe, light_frames)

    return dark_dedupe + light_dedupe



def screengen(
        clip: vs.VideoNode,
        folder: str,
        suffix: str,
        frame_numbers: List = None,
        start: int = 1):
    """
    Stoled from Sea
    Mod of Narkyy's screenshot generator, stolen from awsmfunc.
    Generates screenshots from a list of frames.
    Not specifying `frame_numbers` will use `ssfunc.util.lazylist()` to generate a list of frames.
    :param folder:            Name of folder where screenshots are saved.
    :param suffix:            Name prepended to screenshots (usually group name).
    :param frame_numbers:     List of frames. Either a list or an external file.
    :param start:             Frame to start from.
    :param delim:             Delimiter for the external file.
    > Usage: ScreenGen(src, "Screenshots", "a")
             ScreenGen(enc, "Screenshots", "b")
    """

    folder_path = "./{name}".format(name=folder)

    if not os.path.isdir(folder_path):
        os.mkdir(folder_path)

    for i, num in enumerate(frame_numbers, start=start):
        filename = "{path}/{:03d} - {suffix}.png".format(
            i, path=folder_path, suffix=suffix
        )

        matrix = clip.get_frame(0).props._Matrix

        if matrix == 2:
            matrix = 1

        print(f"Saving Frame {i}/{len(frame_numbers)} from {suffix}", end="\r")
        vs.core.imwri.Write(
            clip.resize.Spline36(
                format=vs.RGB24, matrix_in=matrix, dither_type="error_diffusion"
            ),
            "PNG",
            filename,
            overwrite=True,
        ).get_frame(num)


def get_highest_res(files: List[str]) -> int:
    height = 0
    for f in files:
        video = vs.core.lsmas.LWLibavSource(f)
        if height < video.height:
            height = video.height

    return height


def get_frames(clip: vs.VideoNode, frames: List[int]) -> vs.VideoNode:
    out = clip[frames[0]]
    for i in frames[1:]:
        out += clip[i]
    return out


def actual_script():
    files = sorted([f for f in os.listdir('.') if f.endswith('.mkv') or f.endswith('.m2ts') or f.endswith('.mp4')])

    if len(files) < 2:
        print("Not enough video files found.")
        time.sleep(3)
        exit

    print('Files found: ')
    for f in files:
        if trim_dict.get(files.index(f)) is not None:
            print(f + f" (Will be trimmed to start at frame {trim_dict.get(files.index(f))})")
        else:
            print(f)

    print('\n')

    dict = ani.parse(files[0])
    collection_name = dict.get('anime_title') if dict.get('anime_title') is not None else dict.get('episode_title')

    first = vs.core.lsmas.LWLibavSource(files[0])
    if trim_dict.get(0) is not None:
        first = first[trim_dict.get(0):]

    frames = lazylist(first, frame_count_dark, frame_count_bright)
    print(frames)
    print("\n")

    if upscale:
        max_height = get_highest_res(files)

    for file in files:
        dict = ani.parse(file)
        suffix = ""
        if dict.get('release_group') is not None:
            suffix = str(dict.get('release_group')).replace("[\\/:\"*?<>|]+", "")
        if not suffix:
            suffix = file.replace("[\\/:\"*?<>|]+", "")

        print(f"Generating screens for {file}")
        clip = vs.core.lsmas.LWLibavSource(file)
        index = files.index(file)
        if trim_dict.get(index) is not None:
            clip = clip[trim_dict.get(index):]
        if upscale and clip.height < max_height:
            clip = vs.core.resize.Spline36(clip, clip.width * (max_height / clip.height), max_height)

        if ffmpeg:
            import subprocess
            matrix = clip.get_frame(0).props._Matrix
            if matrix == 2:
                matrix = 1
            clip = clip.resize.Bicubic(format=vs.RGB24, matrix_in=matrix, dither_type="error_diffusion")
            clip = get_frames(clip, frames)
            clip = clip.std.ShufflePlanes([1, 2, 0], vs.RGB).std.AssumeFPS(fpsnum=1, fpsden=1)

            if not os.path.isdir("./screens"):
                os.mkdir("./screens")
            path_images = [
                "{path}/{:03d} - {suffix}.png".format(frames.index(f) + 1, path="./screens", suffix=suffix)
                for f in frames
            ]

            print(path_images)

            for i, path_image in enumerate(path_images):
                ffmpeg_line = f"ffmpeg -y -hide_banner -loglevel error -f rawvideo -video_size {clip.width}x{clip.height} -pixel_format gbrp -framerate {str(clip.fps)} -i pipe: -pred mixed -ss {i} -t 1 \"{path_image}\""
                try:
                    with subprocess.Popen(ffmpeg_line, stdin=subprocess.PIPE) as process:
                        clip.output(cast(BinaryIO, process.stdin), y4m=False)
                except BaseException:
                    None
        else:
            screengen(clip, "screens", suffix, frames)


actual_script()
