"""Protect immutable versions and never publish a failed upload."""
from pathlib import Path
import subprocess

import pytest

from scripts.release import application_version, publish, release_plan


def project(tmp_path):
    (tmp_path / 'src/fireblade').mkdir(parents=True)
    (tmp_path / 'docs/development').mkdir(parents=True)
    (tmp_path / 'src/fireblade/__init__.py').write_text('__version__ = "0.7.1"\n')
    (tmp_path / 'pyproject.toml').write_text('[project]\nversion="0.7.1"\n')
    (tmp_path / 'docs/development/RELEASE-NOTES.md').write_text('New release\n')
    executable = tmp_path / 'Fireblade.exe'
    executable.write_bytes(b'MZ synthetic test executable')
    return executable


def test_tag_and_metadata_versions_must_agree(tmp_path):
    project(tmp_path)
    assert application_version(tmp_path) == '0.7.1'
    with pytest.raises(ValueError, match='Tag'):
        release_plan('0.7.1', 'v0.7.2', [])
    (tmp_path / 'pyproject.toml').write_text('[project]\nversion="0.8.0"\n')
    with pytest.raises(ValueError, match='must match'):
        application_version(tmp_path)


@pytest.mark.parametrize('tag,title', [
    ('v0.7.0', 'Any title'),
    ('prototype-old-sha', 'Fireblade 0.7.0 — Windows x64 (prototype)'),
])
def test_published_version_is_protected_even_with_legacy_tag(tag, title):
    with pytest.raises(ValueError, match='already published'):
        release_plan('0.7.0', '', [dict(tagName=tag, name=title, isDraft=False)])


@pytest.mark.parametrize('existing', [False, True])
def test_asset_is_uploaded_to_draft_before_publication(tmp_path, existing):
    executable = project(tmp_path)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if 'list' in command:
            data = '[{"tagName":"v0.7.1","name":"Draft","isDraft":true}]' if existing else '[]'
            return subprocess.CompletedProcess(command, 0, stdout=data)
        if 'create' in command:
            assert '--draft' in command
        if '--notes-file' in command:
            notes = Path(command[command.index('--notes-file') + 1]).read_text()
            assert 'Commit : tested-commit' in notes and 'SHA-256 de Fireblade.exe' in notes
        return subprocess.CompletedProcess(command, 0)
    result = publish(tmp_path, executable, 'owner/repo', 'tested-commit', 'v0.7.1', run=run)
    assert result['tag'] == 'v0.7.1'
    assert ('upload' if existing else 'create') in calls[1]
    assert 'edit' in calls[2] and '--draft=false' in calls[2]


def test_failed_upload_cannot_make_draft_public(tmp_path):
    executable = project(tmp_path)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if 'list' in command:
            return subprocess.CompletedProcess(command, 0, stdout='[]')
        raise subprocess.CalledProcessError(1, command)
    with pytest.raises(subprocess.CalledProcessError):
        publish(tmp_path, executable, 'owner/repo', 'tested-commit', run=run)
    assert len(calls) == 2 and not any('edit' in command for command in calls)
