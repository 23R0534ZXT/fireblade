"""Fireblade on the biggest benchmark file: peak memory sampled from outside, and how much
of the import is the integrity hashing rather than the parsing.

The comparison with Timeline Explorer has to be honest on both axes: wall time and memory.
Fireblade hashes the source twice (before and after) so a modified file cannot pass silently;
that costs seconds on every import and belongs in the numbers, separated out.
"""
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\23R\dev\fireblade\src")
sys.path.insert(0, r"C:\Users\23R\dev\fireblade\.venv\Lib\site-packages")

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.settings import Settings

CSV = Path(r"C:\Users\23R\fb-bench\size-32000000-1\auth.log.csv")
WORK = Path(r"C:\Users\23R\fb-bench-work\peak-32000000")
if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)
WORK.parent.mkdir(parents=True, exist_ok=True)

# 1. What the hash alone costs on this file.
started = time.monotonic()
digest = hashlib.sha256()
with CSV.open('rb') as stream:
    while True:
        block = stream.read(4 * 1024 * 1024)
        if not block:
            break
        digest.update(block)
hash_seconds = time.monotonic() - started
size_mb = CSV.stat().st_size / 1e6
print('sha256 alone: %.1fs (%.0f MB/s) for %.0f MB' % (hash_seconds, size_mb / hash_seconds, size_mb), flush=True)

# 2. The import, with its peak measured elsewhere (this process cannot read its own peak
#    reliably: GetProcessMemoryInfo returns 0 on this build).
collection = Collection(CSV.parent, WORK, ToolPack(WORK / 'pack'),
                        settings=Settings(memory_mb=1024, threads=4))
collection.report['organization'] = 'files'
collection.prepare_output()
started = time.monotonic()
document = collection.import_result(str(CSV), 'native', register=False)
elapsed = time.monotonic() - started
print('default import: %.1fs (%.1f MB/s)' % (elapsed, size_mb / elapsed), flush=True)

# 3. The same import with the effort control at its tightest: 512 MB, one thread.
shutil.rmtree(WORK, ignore_errors=True)
WORK.parent.mkdir(parents=True, exist_ok=True)
collection = Collection(CSV.parent, WORK, ToolPack(WORK / 'pack'),
                        settings=Settings(memory_mb=512, threads=1))
collection.report['organization'] = 'files'
collection.prepare_output()
started = time.monotonic()
document = collection.import_result(str(CSV), 'native', register=False)
elapsed_low = time.monotonic() - started
print('low budget (512 MB, 1 thread): %.1fs (%.1f MB/s)' % (elapsed_low, size_mb / elapsed_low), flush=True)

# 4. And with the maximum the machine allows.
shutil.rmtree(WORK, ignore_errors=True)
WORK.parent.mkdir(parents=True, exist_ok=True)
collection = Collection(CSV.parent, WORK, ToolPack(WORK / 'pack'),
                        settings=Settings(memory_mb=8192, threads=20))
collection.report['organization'] = 'files'
collection.prepare_output()
started = time.monotonic()
document = collection.import_result(str(CSV), 'native', register=False)
elapsed_max = time.monotonic() - started
print('maximum (8 GB, 20 threads): %.1fs (%.1f MB/s)' % (elapsed_max, size_mb / elapsed_max), flush=True)

Path(r"C:\Users\23R\fb-bench\peak.json").write_text(json.dumps(dict(
    file_mb=round(size_mb, 1), hash_seconds=round(hash_seconds, 2),
    default_seconds=round(elapsed, 2), low_seconds=round(elapsed_low, 2),
    max_seconds=round(elapsed_max, 2)), indent=2), encoding='utf-8')
