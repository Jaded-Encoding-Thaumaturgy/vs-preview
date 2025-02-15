from __future__ import annotations

import math
from typing import Any, Callable
from jetpytools import SPath
from vstools import ChromaLocation, ColorRange, FieldBased, Matrix, Primaries, PropEnum, Transfer

__all__ = [
    'frame_props_lut'
]


def _create_enum_props_lut(enum: type[PropEnum], pretty_name: str) -> tuple[str, dict[str, dict[int, str]]]:
    return enum.prop_key, {
        pretty_name: {
            idx: enum.from_param(idx).pretty_string if enum.is_valid(idx) else 'Invalid'
            for idx in range(min(enum.__members__.values()) - 1, max(enum.__members__.values()) + 1)
        }
    }


# Utils
def _handle_na(value: int) -> str:
    return "N/A" if value < 0 else str(value)


def _handle_nan(value: Any) -> str:
    if isinstance(value, float) and math.isnan(value):
        return 'NaN'
    return str(value)


# Basic frame properties
basic_frame_props_lut: dict[str, dict[str, list[str] | Callable[[Any], str]]] = {
    '_Combed': {
        'Is Combed': [
            'No',
            'Yes'
        ]
    },
    '_Field': {
        'Frame Field Type': [
            'Bottom Field',
            'Top Field'
        ]
    },
    '_SceneChangeNext': {
        'Scene Cut': [
            'Current Scene',
            'End of Scene'
        ]
    },
    '_SceneChangePrev': {
        'Scene Change': [
            'Current Scene',
            'Start of Scene'
        ]
    },
}

# VIVTC-related properties
vivtc_props_lut: dict[str, dict[str, list[str] | Callable[[Any], str]]] = {
    'VFMMics': {
        'VFM Mics': lambda mics: ' | '.join(
            f'{key}: {_handle_na(value)}' for key, value in zip('pcnbu', mics)
        )
    },
    'VFMMatch': {
        'VFM Match': [
            'p',
            'c',
            'n',
            'b',
            'u'
        ]
    },
    'VFMSceneChange': {
        'VFM Scene Start/End': [
            'No',
            'Yes'
        ]
    },
    'VDecimateDrop': {
        'VDecimate Drop Frame': [
            'No',
            'Yes'
        ]
    },
    'VDecimateMaxBlockDiff': {
        'VDecimate Max Block Diff': lambda max_block_diff: str(max_block_diff)
    },
    'VDecimateTotalDiff': {
        'VDecimate Absolute Total Diff': lambda total_diff: str(total_diff)
    },
}

# TIVTC-related properties
tivtc_props_lut: dict[str, dict[str, list[str] | Callable[[Any], str]]] = {
    'TFMMics': {
        'TFM Mics': lambda mics: ' | '.join(
            f'{key}: {_handle_na(value)}' for key, value in zip('pcnbu', mics)
        )
    },
    'TFMMatch': {
        'TFM Match': [
            'p',
            'c',
            'n',
            'b',
            'u'
        ]
    },
}

# DMetrics-related properties
dmetrics_props_lut: dict[str, dict[str, Callable[[Any], str]]] = {
    'MMetrics': {
        'DMetrics MMetrics': lambda metrics: str(metrics)
    },
    'VMetrics': {
        'DMetrics VMetrics': lambda metrics: str(metrics)
    },
}

# Packet size properties
packet_size_props_lut: dict[str, dict[str, Callable[[Any], str]]] = {
    'PktSize': {
        'Packet Size': lambda size: _handle_na(size)
    },
    'PktSceneAvgSize': {
        'Packet Scene Average Size': lambda size: _handle_na(size)
    },
    'PktSceneMinSize': {
        'Packet Scene Minimum Size': lambda size: _handle_na(size)
    },
    'PktSceneMaxSize': {
        'Packet Scene Maximum Size': lambda size: _handle_na(size)
    },
}

# vssource properties
vssource_props_lut: dict[str, dict[str, Callable[[Any], str]]] = {
    'IdxFilePath': {
        'Path to File': lambda filepath: SPath(filepath).as_posix()
    },
    # DGIndex(NV)
    'DgiFieldOp': {
        'DGIndex Field Operation': lambda dgi: str(dgi)
    },
    'DgiOrder': {
        'DGIndex Field Order': lambda dgi: str(dgi)
    },
    'DgiFilm': {
        'DGIndex FILM': lambda dgi: str(dgi) + '%'
    },
}

# Wobbly Parser properties
wobbly_props_lut: dict[str, dict[str, list[str] | Callable[[Any], str]]] = {
    'WobblyMatch': {
        'Field Match': lambda x: (
            x if str(x) in ['p', 'c', 'n', 'b', 'u']
            else ['p', 'c', 'n', 'b', 'u'][x] if isinstance(x, int) and 0 <= x < 5
            else '?'
        )
    },
    'WobblyCombed': {
        'Combed': [
            'No',
            'Yes'
        ]
    },
    'WobblyCycleFps': {
        'Current Cycle Framerate': lambda fps: str(fps)
    },
    'WobblyFreeze': {
        'Freeze Ranges': lambda freeze: freeze
    },
    'WobblyInterlacedFades': {
        'Interlaced Fade': [
            'No',
            'Yes'
        ]
    },
    'WobblyOrphanFrame': {
        'Orphan Frame': lambda m: f"Yes ({m})" if not isinstance(m, int) or m >= 0 else "No"
    },
    'WobblyOrphanDeinterlace': {
        'Orphan Field Deinterlaced': lambda m: f"Yes ({m})" if not isinstance(m, int) or m >= 0 else "No"
    },
    'WobblyPreset': {
        'Filtering Preset Applied': lambda preset: str(preset)
    },
    'WobblyPresetPosition': {
        'Filtering Preset Position': lambda position: str(position).title()
    },
    'WobblyPresetFrames': {
        'Filtering Preset Frame Range': lambda r: str(r) if isinstance(r, int) else f'({r[0]}, {r[-1]})'
    },
}

# VMAF-related properties
vmaf_props_lut: dict[str, dict[str, Callable[[Any], str]]] = {
    'ciede2000': {
        'CIEDE2000': lambda ciede2000: _handle_nan(ciede2000)
    },
    'float_ssim': {
        'SSIM (Float)': lambda float_ssim: _handle_nan(float_ssim)
    },
    'float_ms_ssim': {
        'MS-SSIM (Float)': lambda float_ms_ssim: _handle_nan(float_ms_ssim)
    },
    'psnr_y': {
        'PSNR Luma (Y)': lambda psnr_y: _handle_nan(psnr_y)
    },
    'psnr_cb': {
        'PSNR Chroma Blue (Cb)': lambda psnr_cb: _handle_nan(psnr_cb)
    },
    'psnr_cr': {
        'PSNR Chroma Red (Cr)': lambda psnr_cr: _handle_nan(psnr_cr)
    },
    'psnr_hvs': {
        'PSNR (HVS)': lambda psnr_hvs: _handle_nan(psnr_hvs)
    },
    'psnr_hvs_y': {
        'PSNR (HVS) Luma (Y)': lambda psnr_hvs_y: _handle_nan(psnr_hvs_y)
    },
    'psnr_hvs_cb': {
        'PSNR (HVS) Chroma Blue (Cb)': lambda psnr_hvs_cb: _handle_nan(psnr_hvs_cb)
    },
    'psnr_hvs_cr': {
        'PSNR (HVS) Chroma Red (Cr)': lambda psnr_hvs_cr: _handle_nan(psnr_hvs_cr)
    },
}

enum_props_lut = dict([
    _create_enum_props_lut(enum, name)
    for enum, name in list[tuple[type[PropEnum], str]]([
        (FieldBased, 'Field Type'),
        (Matrix, 'Matrix'),
        (Transfer, 'Transfer'),
        (Primaries, 'Primaries'),
        (ChromaLocation, 'Chroma Location'),
        (ColorRange, 'Color Range')
    ])
])

# Combine all the LUTs
frame_props_lut = dict[str, Any](
    **basic_frame_props_lut,
    **vssource_props_lut,
    **vivtc_props_lut,
    **tivtc_props_lut,
    **dmetrics_props_lut,
    **packet_size_props_lut,
    **wobbly_props_lut,
    **vmaf_props_lut,
) | enum_props_lut
