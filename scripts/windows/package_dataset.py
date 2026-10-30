"""Package the reproducible CSV as one downloadable ZIP, without external tools."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from scripts.windows.dataset import generate


def package(directory, target_bytes=3 * 1024**3, source_commit=None):
    directory = Path(directory)
    directory.mkdir(parents=True)
    spec = generate(directory / 'source', target_bytes)
    source = Path(spec['source'])
    manifest = {key: spec[key] for key in
                ('format', 'bytes', 'rows', 'sha256', 'seed', 'headers', 'reference', 'description')}
    manifest['source'] = 'Fireblade-test-3GiB.csv'
    if source_commit:
        manifest['generator_commit'] = source_commit
    manifest_path = directory / 'dataset.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    archive = directory / 'Fireblade-test-3GiB.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as output:
        output.write(source, arcname=manifest['source'])
        output.write(manifest_path, arcname='dataset.json')
    if archive.stat().st_size >= 2 * 1024**3:
        raise ValueError('Archive exceeds the GitHub Release asset size limit')
    # Check the actual decompressed bytes, including the ZIP CRC, before upload.
    with zipfile.ZipFile(archive) as incoming:
        if incoming.namelist() != [manifest['source'], 'dataset.json']:
            raise ValueError('Unexpected archive entries')
        if incoming.getinfo(manifest['source']).file_size != manifest['bytes']:
            raise ValueError('CSV size mismatch')
        with incoming.open(manifest['source']) as csv_file:
            if hashlib.file_digest(csv_file, 'sha256').hexdigest() != manifest['sha256']:
                raise ValueError('Decompressed CSV digest mismatch')
        if json.loads(incoming.read('dataset.json')) != manifest:
            raise ValueError('Archive manifest mismatch')
    with archive.open('rb') as incoming:
        archive_hash = hashlib.file_digest(incoming, 'sha256').hexdigest()
    publication = dict(manifest, archive_name=archive.name, archive_bytes=archive.stat().st_size,
                       archive_sha256=archive_hash,
                       download_url='https://github.com/23R0534ZXT/fireblade/releases/download/test-data-3gib/' + archive.name)
    (directory / 'publication.json').write_text(json.dumps(publication, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (directory / 'SHA256SUMS.txt').write_text(
        archive_hash + '  ' + archive.name + '\n' + manifest['sha256'] + '  ' + manifest['source'] + '\n', encoding='ascii')
    return publication


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--source-commit')
    args = parser.parse_args()
    args.directory.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(args.directory.parent).free < 6 * 1024**3:
        parser.error('At least 6 GiB free space is required for packaging')
    result = package(args.directory, source_commit=args.source_commit)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
