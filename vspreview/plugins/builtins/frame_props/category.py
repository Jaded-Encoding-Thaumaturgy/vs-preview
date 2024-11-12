__all__ = [
    'frame_props_categories',
    'frame_props_category_prefix_lut',
    'frame_props_category_suffix_lut',
]

video_props: list[str] = [
    # Colorimetry
    '_Matrix', '_Transfer', '_Primaries',
    '_ChromaLocation', '_ColorRange',
    # Frame Properties
    '_DurationNum', '_DurationDen', '_AbsoluteTime',
    '_SARNum', '_SARDen',
    '_FieldBased',
    # Other
    '_FrameNumber', '_Alpha', 'Name', 'IdxFilePath',
]
"""Properties related to video colorimetry, frame characteristics, and other video-specific information."""

metrics_props: list[str] = [
    # Scene detection
    '_SceneChangeNext', '_SceneChangePrev', 'SceneChange',
    # DMetrics
    'MMetrics', 'VMetrics',
]
"""Properties related to video analysis metrics and statistics."""

field_props: list[str] = [
    '_Combed', '_Field', '_FieldBased',
]
"""Properties specific to interlaced video and field-based processing."""

wobbly_props: list[str] = []
"""Properties related to wobbly processing."""

other_props: list[str] = []
"""Props that don't fit into other categories or haven't been sorted"""

frame_props_categories: dict[str, list[str]] = {
    'Video': video_props,
    'Metrics': metrics_props,
    'Field': field_props,
    'Wobbly': wobbly_props,
    'Other': other_props
}

frame_props_category_prefix_lut: dict[str, str] = {
    str(prefix): str(category) for category, prefixes in {
        'Metrics': (
            # PlaneStats
            'PlaneStats', 'psm', 'VFMPlaneStats',
            # DGIndex (via vssource)
            'Dgi',
            # Auto-balancing (via stgfunc)
            'AutoBalance',
            # Scene-based graining (via lvsfunc)
            'SceneGrain',
            # Packet sizes (via lvsfunc)
            'Pkt',
            # VMAF
            'ciede2000', 'psnr_',
            # SSIMULACRA2
            '_SSIMULACRA2',
        ),
        'Field': (
            # VIVTC
            'VFM', 'VDecimate',
            # TIVTC
            'TFM', 'TDecimate',
        ),
        'Wobbly': (
            # Wobbly (via vswobbly)
            'Wobbly'
        )
    }.items()
    for prefix in prefixes
}
"""LUT for categorizing frame properties based on prefixes."""

frame_props_category_suffix_lut: dict[str, str] = {
    str(suffix): str(category) for category, suffixes in {
        'Metrics': (
            # VMAF
            '_ssim',
        )
    }.items()
    for suffix in suffixes
}
"""LUT for categorizing frame properties based on suffixes."""
