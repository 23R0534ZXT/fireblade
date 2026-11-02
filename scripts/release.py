"""Publish an explicitly requested, qualified Windows build without replacing a version."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib


def application_version(root):
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    module = ast.parse((root / 'src/fireblade/__init__.py').read_text(encoding='utf-8'))
    versions = [ast.literal_eval(node.value) for node in module.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    if len(versions) != 1 or versions[0] != project['project']['version']:
        raise ValueError('Application and project versions must match')
    if not isinstance(versions[0], str) or not re.fullmatch(r'\d+\.\d+\.\d+', versions[0]):
        raise ValueError('Use a numeric X.Y.Z release version')
    return versions[0]


def release_plan(version, requested_tag, releases):
    tag = 'v' + version
    if requested_tag and requested_tag != tag:
        raise ValueError('Tag and application version do not match')
    title = f'Fireblade {version} — Windows x64 (prototype)'
    same_version = re.compile(r'^Fireblade\s+' + re.escape(version) + r'(?:\s|$)')
    for release in releases:
        if not release['isDraft'] and (release['tagName'] == tag or same_version.match(release['name'])):
            raise ValueError('This version is already published; increase the application version')
    return dict(tag=tag, title=title,
                draft_exists=any(release['tagName'] == tag for release in releases))


def publish(root, executable, repository, commit, requested_tag='', run=subprocess.run):
    version = application_version(root)
    def gh(*args, capture=False):
        return run(['gh', *args, '--repo', repository], check=True, text=True,
                   capture_output=capture)
    response = gh('release', 'list', '--limit', '100', '--json', 'name,tagName,isDraft', capture=True)
    plan = release_plan(version, requested_tag, json.loads(response.stdout))
    # Read-only metadata checks above must finish before any remote mutation.
    with executable.open('rb') as stream:
        if stream.read(2) != b'MZ':
            raise ValueError('Expected a Windows executable')
        stream.seek(0)
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    notes = (root / 'docs/development/RELEASE-NOTES.md').read_text(encoding='utf-8')
    notes += f'\n\nCommit : {commit}\n\nSHA-256 de Fireblade.exe : {digest}\n'
    with tempfile.TemporaryDirectory(prefix='fireblade-release-') as folder:
        path = Path(folder) / 'notes.md'
        path.write_text(notes, encoding='utf-8')
        if plan['draft_exists']:
            gh('release', 'upload', plan['tag'], str(executable), '--clobber')
        else:
            gh('release', 'create', plan['tag'], str(executable), '--draft', '--prerelease',
               '--target', commit, '--title', plan['title'], '--notes-file', str(path))
        # Failed upload/create leaves a draft; nothing is published in that case.
        gh('release', 'edit', plan['tag'], '--title', plan['title'], '--notes-file', str(path),
           '--prerelease', '--draft=false')
    return dict(**plan, sha256=digest, commit=commit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    repository, commit = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA']
    requested_tag = os.environ.get('REQUESTED_TAG', '')
    print(json.dumps(publish(root, args.exe.resolve(), repository, commit, requested_tag), ensure_ascii=False))


if __name__ == '__main__':
    main()
