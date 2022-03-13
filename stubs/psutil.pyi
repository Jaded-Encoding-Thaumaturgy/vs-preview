from typing import List, Optional

# pylint: skip-file


class Process:
    def cpu_affinity(self, cpu_list: Optional[List[int]] = None) -> List[int]: ...


def cpu_count(logical: bool = True) -> int: ...
