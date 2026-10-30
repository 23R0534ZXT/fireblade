"""Compare file identity, including Windows UNC/drive aliases and hard links."""
import os
from pathlib import Path


def same_file(first, second):
    first,second=Path(first).resolve(),Path(second).resolve()
    if first==second:return True
    try:return os.path.samefile(first,second)
    except (OSError,ValueError):return False


def protected_destination(target, paths):
    return any(same_file(target,path) for path in paths)
