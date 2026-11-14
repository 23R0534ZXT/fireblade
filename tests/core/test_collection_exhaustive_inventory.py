"""A collection must account for every entry of the tree, whatever its shape.

The promise made to the examiner is simple: whatever the folder looks like, every
file inside is seen, and each one ends up either analysed or listed with a reason.
These tests encode that promise as an invariant, not as a sample of happy paths:
they build a deliberately hostile tree and compare the report with the tree that
was actually created.

If a future change starts dropping files silently, or leaves an entry pending,
these tests fail before any examiner notices.
"""
import json
from pathlib import Path
import os

import pytest

from fireblade.core.collection import Collection, ToolPack

ACCEPTED = {'pending', 'running', 'complete', 'complete_with_warnings', 'unsupported',
            'skipped', 'error', 'cancelled', 'attention', 'no_output', 'companion'}


# --------------------------------------------------------------------------- setup

def make_pack(tmp_path):
    pack = tmp_path / 'pack'
    (pack / 'EvtxECmd').mkdir(parents=True, exist_ok=True)
    (pack / 'EvtxECmd' / 'EvtxECmd.dll').touch()
    (pack / 'dotnet').mkdir(exist_ok=True)
    (pack / 'dotnet' / 'dotnet.exe').touch()
    return ToolPack(pack)


def fake_execute(command, cwd, log, timeout=3600):
    """Stand-in for an external parser: writes a plausible CSV, never a real one."""
    Path(log).write_text('tool executed')
    target = Path(command[command.index('-o') + 1])
    source = next(Path(command[command.index('-d') + 1]).glob('*.evtx'))
    target.write_text('Level,RuleTitle,RecordID,EvtxFile\nhigh,Test detection,12,' + str(source) + '\n')


def hostile_tree(root):
    """Create a tree the way a seized disk looks, and return the regular files made.

    Only regular files that must be inventoried are returned; links and special
    entries are checked separately because they are reported, not parsed.
    """
    created = []

    def write(relative, payload=b'x'):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        created.append(path)
        return path

    write('Security.evtx', b'ElfFile\0' + b'\0' * 48)      # recognised, will be parsed
    write('data.csv', b'User,Value\nalice,001\n')            # native CSV
    write('notes.txt', b'rien a voir avec du forensic')      # unsupported by design
    write('rapport.pdf', b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')   # unsupported, binary
    write('page.html', b'<html><body>bonjour</body></html>') # unsupported, text
    write('empty.bin', b'')                                  # zero byte
    write('binary.dat', bytes(range(256)))                   # opaque bytes
    write('export cp1252.csv', 'User;Ville\nanne;Orl\xe9ans\n'.encode('cp1252'))  # non UTF-8 CSV
    write('accents/éléphant.log', b'2026-11-14 host sshd[1]: ok\n')
    write('espaces et accents/dossier été/sous-sol/fichier final.txt', b'texte')
    write('深度/子目录/note.txt', '深层'.encode())                    # non-latin names
    for index in range(40):
        write(f'nombres/fichier-{index:03d}.txt', b'x')
    write('var/log/syslog', b'Nov 14 07:00:01 host cron[9]: ok\n')
    write('var/log/kern.log', b'Nov 14 07:00:02 host kernel: ok\n')
    write('var/log/journal/broken.journal', os.urandom(64))
    return created


def tree_links(root):
    """Create links that must be reported and never followed."""
    made = []
    for relative, target, is_dir in (('loop', '.', True),
                                     ('attached.csv', 'data.csv', False)):
        path = root / relative
        try:
            path.symlink_to((root / target) if target != '.' else root,
                            target_is_directory=is_dir)
        except (OSError, NotImplementedError):
            continue
        made.append(path)
    return made


# --------------------------------------------------------------------------- tests

def test_every_regular_file_is_accounted_for_exactly_once(tmp_path, monkeypatch):
    root = tmp_path / 'evidence'
    root.mkdir()
    created = hostile_tree(root)
    links = tree_links(root)
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)

    collection = Collection(root, tmp_path / 'work', make_pack(tmp_path))
    report = collection.parse()

    def key(path):
        # Deliberately no resolve(): a link must stay distinct from its target,
        # otherwise the test hides a link that was silently followed.
        return os.path.normcase(os.path.abspath(str(path)))

    reported = [key(entry['path']) for entry in report['files']]
    assert len(reported) == len(set(reported)), 'un fichier est décrit deux fois dans le bilan'

    missing = [path for path in created if key(path) not in set(reported)]
    assert not missing, 'fichiers présents sur le disque mais absents du bilan : ' + repr(missing)

    statuses = {entry['status'] for entry in report['files']}
    assert statuses <= ACCEPTED, f'états inconnus dans le bilan : {statuses - ACCEPTED}'
    assert 'pending' not in statuses, 'un fichier est resté en attente : la collecte a abandonné sans le dire'

    for entry in report['files']:
        if entry['status'] in ('error', 'skipped', 'unsupported'):
            assert entry.get('error') or entry['status'] == 'unsupported', \
                f"un fichier écarté sans motif : {entry['path']}"

    followed = [key(path) for path in links if key(path) in set(reported)]
    for entry in report['files']:
        if key(entry['path']) in followed:
            assert entry['status'] == 'skipped', 'un lien a été suivi au lieu d\'être signalé'


def test_unrecognised_files_are_listed_with_a_reason_not_parsed(tmp_path, monkeypatch):
    root = tmp_path / 'evidence'
    root.mkdir()
    hostile_tree(root)
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)

    report = Collection(root, tmp_path / 'work', make_pack(tmp_path)).parse()
    by_name = {Path(entry['path']).name: entry for entry in report['files']}

    for name in ('rapport.pdf', 'page.html', 'notes.txt', 'empty.bin', 'binary.dat'):
        entry = by_name[name]
        assert entry['status'] == 'unsupported', f'{name} devrait être écarté, état {entry["status"]}'
        assert entry['tools'] == [], f'{name} ne doit être confié à aucun lecteur'
        assert entry['path'], f'{name} doit rester consultable dans le bilan'

    assert by_name['Security.evtx']['tools'], 'le fichier EVTX doit être reconnu'


def test_unicode_names_and_deep_paths_survive_the_inventory(tmp_path, monkeypatch):
    root = tmp_path / 'evidence'
    root.mkdir()
    hostile_tree(root)
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)

    report = Collection(root, tmp_path / 'work', make_pack(tmp_path)).parse()
    paths = [entry['path'] for entry in report['files']]

    assert any('éléphant.log' in path for path in paths)
    assert any('fichier final.txt' in path for path in paths)
    assert any('子目录' in path for path in paths)
    assert any('export cp1252.csv' in path for path in paths)
    # The persisted report must stay readable: a collection is reopened later.
    payload = json.dumps(report, ensure_ascii=False)
    assert 'éléphant.log' in payload and '子目录' in payload


def test_report_survives_a_reopen_with_the_same_file_count(tmp_path, monkeypatch):
    root = tmp_path / 'evidence'
    root.mkdir()
    created = hostile_tree(root)
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)

    work = tmp_path / 'work'
    first = Collection(root, work, make_pack(tmp_path)).parse()
    second = Collection.reopen(work, make_pack(tmp_path)).report
    assert len(second['files']) == len(first['files'])
    assert len(second['files']) >= len(created)
