"""Check that standalone session saves remain readable or preserve the old file.

Uses synthetic evidence in a new directory. Exit status 1 means an invariant
failed; this is an audit, not a performance benchmark.
"""
import argparse
import json
from pathlib import Path
import shutil

from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.sessions import read_session, write_session


def audit(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / 'synthetic.csv'
    source.write_text('ID,User\n001,alice\n', encoding='utf-8')
    database = directory / 'original.timeline'
    case = Case(database)
    try:
        info = case.import_csv(source)
    finally:
        case.close()
    snapshots = []
    for number in range(1001):
        path = directory / f'analysis-{number:04}.timeline'
        shutil.copyfile(database, path)
        snapshots.append(AnalysisSnapshot(str(path), info, View(), b''))
    checks = []
    for name, count, search_size in (
        ('1000 analyses', 1000, 0),
        ('1001 analyses', 1001, 0),
        ('320 analyses, recherche de 14000 caractères chacune', 320, 14000),
    ):
        target = directory / f'session-{count}-{search_size}.fireblade-session'
        documents = [AnalysisSnapshot(s.path, s.source_info, View(search='a' * search_size), s.header_state)
                     for s in snapshots[:count]]
        write_session(target, snapshots[:1], 0)
        original = target.read_bytes()
        check = dict(name=name, status='passed')
        try:
            write_session(target, documents, 0)
        except ValueError as exc:
            check['rejected_save'] = str(exc)
            if target.read_bytes() != original:
                check.update(status='failed', error='La sauvegarde refusée a modifié la session précédente.')
        else:
            check['bytes'] = target.stat().st_size
            try:
                restored, active = read_session(target)
                if len(restored) != count or active != 0:
                    raise ValueError('Session restaurée différente de la session enregistrée.')
            except ValueError as exc:
                check.update(status='failed', error=str(exc),
                             previous_valid_session_replaced=target.read_bytes() != original)
        checks.append(check)
    report = dict(status='failed' if any(c['status'] == 'failed' for c in checks) else 'passed', checks=checks)
    (directory / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True, help='Nouveau dossier de données synthétiques')
    args = parser.parse_args()
    if args.directory.exists():
        parser.error('Choisissez un nouveau dossier ; aucune donnée existante ne sera écrasée.')
    report = audit(args.directory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
