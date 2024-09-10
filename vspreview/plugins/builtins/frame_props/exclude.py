__all__ = [
    'frame_props_excluded_keys'
]

# Define categories of excluded frame properties
vs_internals = {'_AbsoluteTime', '_DurationNum', '_DurationDen', '_PictType'}
handled_separately = {'_SARNum', '_SARDen'}
source_filter_props = {'_FrameNumber'}
vstools_props = {'Name'}

# Combine all categories into a single set of excluded keys
frame_props_excluded_keys: set[str] = (
    vs_internals | handled_separately | source_filter_props | vstools_props
)
