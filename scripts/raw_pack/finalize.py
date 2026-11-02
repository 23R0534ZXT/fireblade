"""Package only after native validation; independently reread every ZIP member."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

from scripts.raw_pack.package import ARCHIVE, GIB, ROOT, TAG, archive_pack, digest, safe_relative
from scripts.test_pack.package import APP_COMMIT


def verify_archive(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(set(name.casefold() for name in names)) != len(names):
            raise ValueError('Duplicate ZIP members')
        for name in names:
            safe_relative(name)
        manifest = json.loads(archive.read(ROOT + '/MANIFEST.json').decode('utf-8'))
        expected = {ROOT + '/' + item['path']: item for item in manifest['files']}
        if set(names) != set(expected) | {ROOT + '/MANIFEST.json'}:
            raise ValueError('Undeclared ZIP members')
        raw_bytes = 0
        for name, item in expected.items():
            with archive.open(name) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != item['sha256'] or archive.getinfo(name).file_size != item['bytes']:
                raise ValueError('ZIP content mismatch: ' + name)
            if item['origin']['kind'] in ('public-native', 'synthetic-raw-linux'):
                raw_bytes += item['bytes']
        if raw_bytes != manifest['raw_bytes'] or raw_bytes < 3 * GIB:
            raise ValueError('Raw input size was not independently verified')
    return manifest


def finalize(directory, publish=False):
    directory = Path(directory).resolve()
    root = directory / ROOT
    report = json.loads((root / 'validation-windows.json').read_text(encoding='utf-8'))
    if report['status'] not in ('passed', 'completed_with_diagnostics'):
        raise ValueError('Native validation did not finish')
    manifest_path = root / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    expectations = ['# Résultats mesurés de ce pack brut', '',
                    f"Application qualifiée : `{APP_COMMIT}`.", '',
                    f"Fichiers parsés : {report['parsed_input_files']}. Lignes des journaux Linux : {report['linux_rows']}.",
                    f"Lecteurs avec au moins une référence ouverte avec succès : {', '.join(report['readers'])}.", '',
                    f"Diagnostics publics : {len(report['errors'])} refus/erreurs et {len(report['warnings'])} avertissements ou sorties vides. Ces fichiers ne sont pas comptés comme un parsing réussi.", '',
                    'Le rapport JSON donne les résultats, comptes, temps et diagnostics par fichier. Les collections publiques conservent leurs variantes et leurs limites. Les assertions du scénario Linux portent sur les comptes exacts de ses journaux bruts et la conservation des sources.', '',
                    '## Refus de lecteurs observés', '']
    expectations += [f"- `{item['path']}` : {item.get('tool', '')} — {item['error']}" for item in report['errors']]
    if not report['errors']:
        expectations.append('Aucun refus de lecteur observé sur cette exécution.')
    (root / 'RESULTATS-ATTENDUS.md').write_text('\n'.join(expectations) + '\n', encoding='utf-8')
    by_path = {item['path']: item for item in manifest['files']}
    for path in sorted(root.rglob('*')):
        if path.is_file() and path != manifest_path:
            name = path.relative_to(root).as_posix()
            if name not in by_path:
                by_path[name] = dict(path=name, bytes=path.stat().st_size, sha256=digest(path), origin=dict(kind='validation-metadata'))
    manifest['files'] = sorted(by_path.values(), key=lambda item: item['path'])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    asset = archive_pack(directory)
    verify_archive(directory / ARCHIVE)
    publication = dict(status='qualified-with-listed-diagnostics', archive=asset, raw_bytes=manifest['raw_bytes'],
                       windows_bytes=manifest['windows_bytes'], linux_raw_bytes=manifest['linux_raw_bytes'],
                       files=len(manifest['files']), application_commit=APP_COMMIT,
                       parsed_input_files=report['parsed_input_files'], linux_rows=report['linux_rows'],
                       public_reader_errors=len(report['errors']), public_reader_warnings=len(report['warnings']))
    (directory / 'publication.json').write_text(json.dumps(publication, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (directory / 'SHA256SUMS.txt').write_text(asset['sha256'] + '  ' + ARCHIVE + '\n', encoding='ascii')
    notes = (f'# Grand pack d’artefacts bruts v1\n\n'
             f'**{manifest["raw_bytes"]:,} octets de fichiers bruts après extraction** : '
             f'{manifest["windows_bytes"]:,} octets Windows natifs et {manifest["linux_raw_bytes"]:,} octets Linux bruts. '
             f'ZIP : {asset["bytes"]:,} octets. La compression explique la différence.\n\n'
             'À importer et parser dans Fireblade : MFT, USN, ruches et journaux de registre, EVTX, Prefetch, LNK, Jump Lists, SRUM, Amcache, Windows Timeline, WebCache, Shellbags et journaux Linux auth/syslog/audit. **Aucun CSV d’analyse ni base `.timeline` n’est distribué.**\n\n'
             'Les collections Windows sont des sources publiques indépendantes de laboratoire, sans réécriture des artefacts. Le scénario Linux est synthétique et identifié séparément. Ce n’est pas une acquisition unique ni un incident commun aux collections.\n\n'
             f'Contrôle Windows : {report["parsed_input_files"]} fichiers soumis au parsing, les 13 références de lecteurs réussies, {report["linux_rows"]} lignes de journaux Linux comptées exactement et empreintes de toutes les sources vérifiées. '
             f'Les corpus publics ont produit **{len(report["errors"])} refus/erreurs** et **{len(report["warnings"])} diagnostics d’avertissement ou de sortie vide** : ils sont conservés dans `validation-windows.json` et `RESULTATS-ATTENDUS.md`, sans les présenter comme des réussites.\n\n'
             'Télécharger le ZIP, lire `LIRE-MOI.md`, puis commencer par un sous-dossier de collecte. Prévoir de l’espace supplémentaire pour les sorties des parseurs et les analyses. Les sources, licences, manifestes et résultats attendus sont inclus.\n\n'
             f'Application de référence : `{APP_COMMIT}`.\n\n'
             f'Workflow : https://github.com/23R0534ZXT/fireblade/actions/runs/{os.environ.get("GITHUB_RUN_ID", "")}\n')
    (directory / 'release-notes.md').write_text(notes, encoding='utf-8')
    if publish:
        repo = os.environ['GITHUB_REPOSITORY']
        existing = subprocess.run(['gh', 'release', 'view', TAG, '--repo', repo], capture_output=True)
        if existing.returncode == 0:
            raise ValueError('Raw pack release already exists; use a new pack version')
        subprocess.run(['gh', 'release', 'create', TAG, str(directory / ARCHIVE), str(directory / 'publication.json'),
                        str(directory / 'SHA256SUMS.txt'), str(root / 'MANIFEST.json'), str(root / 'validation-windows.json'),
                        str(root / 'RESULTATS-ATTENDUS.md'), '--draft', '--prerelease', '--latest=false',
                        '--target', os.environ['GITHUB_SHA'], '--title', 'Fireblade — grand pack BRUT v1 (3,2 Gio extraits)',
                        '--notes-file', str(directory / 'release-notes.md'), '--repo', repo], check=True)
        subprocess.run(['gh', 'release', 'edit', TAG, '--draft=false', '--repo', repo], check=True)
    return publication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    print(json.dumps(finalize(args.directory, args.publish), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
