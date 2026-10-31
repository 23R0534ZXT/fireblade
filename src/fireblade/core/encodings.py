"""BOM-based CSV decoding; unmarked text retains the explicit UTF-8 default."""
from pathlib import Path


def bom_encoding(path):
    with Path(path).open('rb') as source:prefix=source.read(4)
    if prefix.startswith((b'\xff\xfe\x00\x00',b'\x00\x00\xfe\xff')):return 'utf-32'
    if prefix.startswith((b'\xff\xfe',b'\xfe\xff')):return 'utf-16'
    return 'utf-8'
