from datetime import timedelta
from typing import List, Optional

# pylint: skip-file


class CueTrack:
    duration: Optional[timedelta]
    offset: Optional[str]
    title: Optional[str]


class CueSheet:
    tracks: List[CueTrack]

    def parse(self) -> None: ...
    def setData(self, data: str) -> None: ...
    def setOutputFormat(self, outputFormat: str, trackOutputFormat: str = '') -> None: ...
