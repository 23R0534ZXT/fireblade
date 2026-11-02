"""Offline artifact orchestration. Every input has a persisted disposition."""
from dataclasses import dataclass
import csv
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import time
import threading
import uuid

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, job_cancelled
from fireblade.core.models import View


PARSERS = ('EvtxECmd', 'AmcacheParser', 'AppCompatCacheParser', 'PECmd', 'MFTECmd',
           'RECmd', 'LECmd', 'JLECmd', 'SrumECmd', 'WxTCmd', 'RBCmd',
           'RecentFileCacheParser', 'SQLECmd')


def check_cancel():
    if job_cancelled():
        raise OperationCancelled()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            check_cancel()
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def identify(path):
    """File signatures and well-known names; never execute an input file."""
    path = Path(path)
    name = path.name.casefold()
    with path.open('rb') as stream:
        magic = stream.read(32)
    if name.endswith(('.log1', '.log2')):
        hive = path.with_name(path.name.rsplit('.', 1)[0])
        if hive.is_file() and not hive.is_symlink():
            with hive.open('rb') as stream:
                if stream.read(4) == b'regf':
                    return ['companion']
        return []
    if magic.startswith(b'ElfFile\0') or name.endswith('.evtx'):
        return ['EvtxECmd']
    if name.startswith(('amcache', 'inventory')) and (magic.startswith(b'regf') or magic.startswith(b'SQLite format 3')):
        return ['AmcacheParser']
    if magic.startswith(b'regf'):
        return ['AppCompatCacheParser', 'RECmd'] if name == 'system' else ['RECmd']
    if name.endswith('.pf'):
        return ['PECmd']
    if name.endswith(('$mft', '$j', '$boot')) or magic.startswith(b'FILE'):
        return ['MFTECmd']
    if magic.startswith(b'\x4c\x00\x00\x00\x01\x14\x02\x00') or name.endswith('.lnk'):
        return ['LECmd']
    if name.endswith(('.automaticdestinations-ms', '.customdestinations-ms')):
        return ['JLECmd']
    if name == 'srudb.dat':
        return ['SrumECmd']
    if name == 'activitiescache.db':
        return ['WxTCmd']
    if name.startswith('$i') and len(name) > 2:
        return ['RBCmd']
    if name == 'recentfilecache.bcf':
        return ['RecentFileCacheParser']
    if magic.startswith(b'SQLite format 3\0'):
        return ['SQLECmd']
    from fireblade.core.catscale import recognized
    if recognized(path):
        return ['CatScale']
    if path.suffix.casefold() in ('.csv', '.tsv'):
        return ['native']
    return []


@dataclass
class ToolPack:
    root: Path

    def command(self, name):
        root = Path(self.root).resolve()
        if name == 'Hayabusa':
            exe = root / name / 'hayabusa.exe'
            if exe.is_file():
                return [str(exe)]
        else:
            dll = root / name / (name + '.dll')
            host = root / 'dotnet' / 'dotnet.exe'
            if dll.is_file() and host.is_file():
                return [str(host), str(dll)]
        raise FileNotFoundError(f'Moteur intégré absent : {name}. La construction du pack forensic est nécessaire.')

    def available(self, name):
        try:
            self.command(name)
            return True
        except FileNotFoundError:
            return False

    def arguments(self, name, source, output):
        args = self.command(name) + ['-f', str(source), '--csv', str(output)]
        if name == 'RECmd':
            batch = Path(self.root) / name / 'BatchExamples' / 'Kroll_Batch.reb'
            if not batch.is_file():
                raise FileNotFoundError('Batch RECmd Kroll_Batch.reb absent')
            args += ['--bn', str(batch)]
        return args


def execute(command, cwd, log, timeout=3600):
    """Bound process lifetime and log to disk; no shell and no unbounded PIPE."""
    check_cancel()
    env = os.environ.copy()
    options = dict(cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                   start_new_session=os.name != 'nt')
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    with Path(log).open('wb') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, **options)
        start = time.monotonic()
        try:
            while process.poll() is None:
                check_cancel()
                if time.monotonic() - start > timeout:
                    raise TimeoutError('Délai du moteur dépassé ; consulter le journal')
                time.sleep(.1)
            if process.returncode:
                raise RuntimeError(f'Moteur terminé avec le code {process.returncode} ; journal : {log}')
        finally:
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)


class Collection:
    def __init__(self, root, output, pack, settings=None, progress=lambda _: None, organization='files', _reopening=False):
        if organization not in ('files', 'artifacts', 'combined'):
            raise ValueError('Organisation de collecte inconnue')
        self.root, self.output = Path(root).resolve(), Path(output).resolve()
        if not _reopening and not self.root.is_dir():
            raise ValueError('Dossier de collecte introuvable')
        if self.output == self.root or self.root in self.output.parents:
            raise ValueError('Choisissez un dossier de travail hors de la collecte source')
        self.pack, self.settings, self.progress = pack, settings, progress
        self._last_checkpoint = 0
        self._case_lock = threading.Lock()
        self._active_case = None
        self.report = dict(format='fireblade-collection', version=1, source=str(self.root),
                           output=str(self.output), organization=organization, status='pending', files=[], documents=[], detection=None)
        manifest = Path(self.pack.root)/'manifest.json'
        if manifest.is_file():
            self.report['toolchain'] = json.loads(manifest.read_text(encoding='utf-8'))

    @classmethod
    def reopen(cls, output, pack, settings=None, progress=lambda _: None):
        output = Path(output).resolve()
        data = json.loads((output/'collection.json').read_text(encoding='utf-8'))
        if data.get('format') != 'fireblade-collection' or data.get('version') != 1:
            raise ValueError('Dossier de travail Fireblade invalide')
        instance = cls(data['source'], output, pack, settings, progress, _reopening=True)
        instance.report = data
        return instance

    def save(self):
        self._last_checkpoint = time.monotonic()
        atomic_json(self.output/'collection.json', self.report)
        if self.report['documents']:
            atomic_json(self.output/'collection.fireblade-session', dict(
                format='fireblade-session', version=1, active=0, documents=self.report['documents']))

    def import_result(self, csv, kind, view=None, register=True):
        check_cancel()
        if register and len(self.report['documents']) >= 1000:
            raise ValueError('Limite de 1000 analyses atteinte ; résultat conservé sur disque')
        target = self.output/'analyses'/(uuid.uuid4().hex+'.timeline')
        case = Case(target, settings=self.settings)
        with self._case_lock:
            self._active_case = case
        failed = False
        try:
            self.progress('Chargement Fireblade : '+Path(csv).name)
            case.import_csv(csv, encoding='auto', progress=self.progress)
            view = view or View()
            document = dict(path=str(target), source=case.info, view=json.loads(view.to_json()), header='')
            if register:
                self.report['documents'].append(document)
                return str(target)
            return document
        except BaseException:
            failed = True
            raise
        finally:
            with self._case_lock:
                self._active_case = None
                case.close()
            if failed:
                target.unlink(missing_ok=True)

    def interrupt(self):
        with self._case_lock:
            if self._active_case is not None:
                self._active_case.interrupt()

    def enrich_result(self, source, artifact, tool):
        """Keep upstream CSV and append raw-artifact provenance to a separate copy."""
        target = source.with_name(source.stem+'-fireblade.csv')
        if target.exists():
            target = source.with_name(source.stem+'-fireblade-'+uuid.uuid4().hex+'.csv')
        csv.field_size_limit(2**31-1)
        with source.open(encoding='utf-8-sig', newline='') as incoming, target.open('x', encoding='utf-8', newline='') as outgoing:
            reader = csv.reader(incoming)
            headers = next(reader, None)
            if not headers:
                raise ValueError('CSV du parseur vide ou sans en-tête')
            names = []
            for base in ('Fireblade_ArtifactSource', 'Fireblade_Parser'):
                name, suffix = base, 2
                while name in headers+names:
                    name = base+'_'+str(suffix)
                    suffix += 1
                names.append(name)
            writer = csv.writer(outgoing)
            writer.writerow(headers+names)
            for row in reader:
                check_cancel()
                if len(row) != len(headers):
                    raise ValueError('CSV du parseur : largeur de ligne incohérente')
                writer.writerow(row+[str(artifact), tool])
        return target

    def parse(self):
        self.output.mkdir(parents=True, exist_ok=False)
        (self.output/'analyses').mkdir()
        (self.output/'results').mkdir()
        self.report['status'] = 'running'
        self.save()
        try:
            # os.walk does not follow directory symlinks. Every inaccessible entry is reported.
            def walk_error(error):
                self.report['files'].append(dict(path=str(error.filename), status='error', error=str(error), tools=[]))
            for directory, dirs, names in os.walk(self.root, followlinks=False, onerror=walk_error):
                for name in list(dirs):
                    path = Path(directory)/name
                    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                        dirs.remove(name)
                        self.report['files'].append(dict(path=str(path), status='skipped', error='Lien de dossier non suivi', tools=[]))
                for name in sorted(names):
                    check_cancel()
                    source = Path(directory)/name
                    entry = dict(path=str(source), status='pending', tools=[])
                    self.report['files'].append(entry)
                    self.progress('Collecte : '+str(source.relative_to(self.root)))
                    try:
                        if source.is_symlink() or self.root not in source.resolve().parents:
                            entry.update(status='skipped', error='Lien de fichier non suivi')
                            continue
                        tools = identify(source)
                        entry['tools'] = tools
                        if not tools:
                            entry['status'] = 'unsupported'
                            continue
                        entry['sha256'] = sha256(source)
                        if tools == ['companion']:
                            entry.update(tools=[], status='companion', kind='registry_transaction_log')
                            continue
                        companions = {}
                        if any(t in ('RECmd', 'AmcacheParser', 'AppCompatCacheParser') for t in tools):
                            for sibling in source.parent.iterdir():
                                if sibling.name.casefold() in (source.name.casefold()+'.log1', source.name.casefold()+'.log2') and sibling.is_file() and not sibling.is_symlink():
                                    companions[str(sibling)] = sha256(sibling)
                            entry['companions'] = companions
                        entry['runs'] = []
                        for tool in tools:
                            check_cancel()
                            run = dict(tool=tool, status='running', outputs=[])
                            entry['runs'].append(run)
                            output = self.output/'results'/uuid.uuid4().hex
                            output.mkdir()
                            try:
                                catscale_outputs = {}
                                if tool == 'CatScale':
                                    from fireblade.core.catscale import parse
                                    result = parse(source, output)
                                    run['catscale'] = result
                                    run['warnings'] = result['warnings']
                                    csvs = [Path(item['csv']) for item in result['outputs']]
                                    catscale_outputs = {item['csv']:item for item in result['outputs']}
                                elif tool == 'native':
                                    csvs = [source]
                                else:
                                    command = self.pack.arguments(tool, source, output)
                                    run['command'] = command
                                    self.progress(tool+' : '+str(source.relative_to(self.root)))
                                    execute(command, str(Path(self.pack.root)/tool), output/'parser.log')
                                    csvs = sorted(output.rglob('*.csv'))
                                for csv in csvs:
                                    enriched = csv if tool == 'native' else self.enrich_result(csv, source, tool)
                                    run['outputs'].append(dict(csv=str(csv), analysis=self.import_result(enriched, tool), **({'family':catscale_outputs[str(csv)]['family']} if tool=='CatScale' else {})))
                                run['status'] = ('complete_with_warnings' if run.get('warnings') else 'complete') if csvs else 'no_output'
                                log = output/'parser.log'
                                if log.is_file():
                                    warnings = []
                                    with log.open(encoding='utf-8', errors='replace') as stream:
                                        for line in stream:
                                            if re.search(r'(?i)(?:\bERR\]|\bWRN\]|failed to|error (?:processing|reading|loading)|could not)', line) and len(warnings)<100:
                                                warnings.append(line.strip())
                                    if warnings:
                                        run['warnings'] = warnings
                                        if csvs:run['status'] = 'complete_with_warnings'
                            except OperationCancelled:
                                run['status'] = 'cancelled'
                                raise
                            except Exception as exc:
                                run.update(status='error', error=str(exc))
                        if any(sha256(path) != digest for path, digest in companions.items()):
                            raise ValueError('Journal de transaction modifié pendant le traitement')
                        if sha256(source) != entry['sha256']:
                            raise ValueError('Source modifiée pendant le traitement ; résultats à vérifier')
                        entry['status'] = 'complete' if all(r['status']=='complete' for r in entry['runs']) else 'attention'
                    except OperationCancelled:
                        entry['status'] = 'cancelled'
                        raise
                    except Exception as exc:
                        entry.update(status='error', error=str(exc))
                    finally:
                        if time.monotonic()-self._last_checkpoint >= 1:
                            self.save()
            from fireblade.core.collection_organization import organize
            organize(self)
            self.report['status'] = 'complete'
        except OperationCancelled:
            self.report['status'] = 'cancelled'
        except BaseException:
            self.report['status'] = 'error'
            raise
        finally:
            self.save()
        return self.report

    def analyze(self, min_level='low'):
        """One Hayabusa run over verified EVTX copies, including cross-file context."""
        if min_level not in ('informational', 'low', 'medium', 'high', 'critical'):
            raise ValueError('Niveau Hayabusa invalide')
        evtx = [e for e in self.report['files'] if 'EvtxECmd' in e.get('tools', []) and 'sha256' in e]
        if not evtx:
            raise ValueError('Aucun EVTX inventorié dans cette collecte')
        folder = self.output/'results'/('hayabusa-'+uuid.uuid4().hex)
        inputs = folder/'inputs'
        inputs.mkdir(parents=True)
        detection = dict(status='running', files=len(evtx), min_level=min_level, outputs=[])
        self.report['detection'] = detection
        self.save()
        try:
            origins = {}
            for index, entry in enumerate(evtx):
                check_cancel()
                source = Path(entry['path'])
                if sha256(source) != entry['sha256']:
                    raise ValueError(f'EVTX modifié depuis inventaire : {source}')
                self.progress(f'Préparation Hayabusa : {index+1}/{len(evtx)} · {source.name}')
                copy = inputs/f'{index:06d}.evtx'
                with source.open('rb') as incoming, copy.open('wb') as outgoing:
                    while block := incoming.read(1024*1024):
                        check_cancel()
                        outgoing.write(block)
                if sha256(copy) != entry['sha256'] or sha256(source) != entry['sha256']:
                    raise ValueError(f'EVTX modifié pendant copie : {source}')
                origins[copy.name] = str(source)
            target = folder/'hayabusa.csv'
            command = self.pack.command('Hayabusa') + ['dfir-timeline', '-d', str(inputs), '-o', str(target),
                '-r', str(Path(self.pack.root)/'Hayabusa'/'rules'), '--no-wizard', '--min-level', min_level,
                '--profile', 'verbose', '--iso-8601', '--no-color', '--scan-all-evtx-files']
            detection['command'] = command
            self.progress('Hayabusa : analyse de tous les EVTX vérifiés…')
            execute(command, str(Path(self.pack.root)/'Hayabusa'), folder/'hayabusa.log')
            if not target.exists():
                raise ValueError('Hayabusa n’a pas produit de CSV ; vérifier le journal')
            summary, warnings = {}, []
            with (folder/'hayabusa.log').open(encoding='utf-8', errors='replace') as log:
                for line in log:
                    if 'Total | Unique detections:' in line:
                        match = re.search(r'detections:\s*([\d,]+)\s*\|', line)
                        if match:summary['detections'] = int(match[1].replace(',', ''))
                    if re.search(r'(?i)(?:\[error\]|\[warn\]|failed to|parse error|could not)', line) and len(warnings)<100:
                        warnings.append(line.strip())
            detection['summary'], detection['warnings'] = summary, warnings
            if target.stat().st_size == 0:
                if summary.get('detections') != 0:
                    raise ValueError('Sortie vide sans bilan explicite de zéro détection ; consulter le journal')
                columns = ['Timestamp','RuleTitle','Level','Computer','Channel','EventID','MitreTactics','MitreTags',
                           'OtherTags','RecordID','Details','ExtraFieldInfo','RuleFile','RuleID','EvtxFile']
                with target.open('w', encoding='utf-8', newline='') as stream:
                    csv.writer(stream).writerow(columns)
            merged = folder/'Alertes Hayabusa.csv'
            count = 0
            with target.open(encoding='utf-8-sig', newline='') as incoming, merged.open('w', encoding='utf-8', newline='') as outgoing:
                reader = csv.DictReader(incoming)
                if not reader.fieldnames or 'EvtxFile' not in reader.fieldnames:
                    raise ValueError('CSV Hayabusa sans colonne EvtxFile ; profil verbose requis')
                writer = csv.DictWriter(outgoing, fieldnames=reader.fieldnames+['Fireblade_EVTX_Source'])
                writer.writeheader()
                for row in reader:
                    check_cancel()
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError('Ligne Hayabusa de largeur incorrecte')
                    mapped = []
                    for item in row['EvtxFile'].split(' ¦ '):
                        name = item.replace(chr(92), '/').rsplit('/', 1)[-1]
                        if name not in origins:
                            raise ValueError('Source EVTX Hayabusa non reconnue : '+item)
                        mapped.append(origins[name])
                    row['Fireblade_EVTX_Source'] = mapped[0] if len(mapped)==1 else json.dumps(mapped, ensure_ascii=False)
                    writer.writerow(row)
                    count += 1
            detection['analysis'] = self.import_result(merged, 'Hayabusa')
            detection['outputs'] = [dict(csv=str(merged), analysis=detection['analysis'])]
            detection.update(status='complete_with_warnings' if warnings else 'complete', alerts=count)
        except OperationCancelled:
            detection['status'] = 'cancelled'
        except Exception as exc:
            detection.update(status='error', error=str(exc))
        finally:
            shutil.rmtree(inputs)
            self.save()
        return self.report
