"""Offline artifact orchestration. Every input has a persisted disposition."""
from dataclasses import dataclass, replace
import csv
import copy
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
import duckdb
from fireblade.core.i18n import translate
from fireblade.core.import_index import load as load_index
from fireblade.core.import_index import update as update_index
from fireblade.core.import_journal import ImportJournal
from fireblade.core.settings import Settings, auto_threads, grown_memory, physical_memory_mb
from fireblade.core.models import View


PARSERS = ('EvtxECmd', 'AmcacheParser', 'AppCompatCacheParser', 'PECmd', 'MFTECmd',
           'RECmd', 'LECmd', 'JLECmd', 'SrumECmd', 'WxTCmd', 'RBCmd',
           'RecentFileCacheParser', 'SQLECmd')


ADDITIONAL_PARSERS = ('Shellbags', 'WebCache')


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


def normalise_sources(root):
    """One path or many, files or folders: one operation keeps one list."""
    items = [root] if isinstance(root, (str, os.PathLike)) else list(root)
    if not items:
        raise ValueError('No source to import')
    return [Path(item) for item in items]


def common_root(sources):
    """The folder labels are measured from: the deepest one that holds them all."""
    folders = [item if item.is_dir() else item.parent for item in sources]
    try:
        folders = [Path(os.path.commonpath([str(folder.resolve()) for folder in folders]))]
    except ValueError:
        # Different drives: each source keeps its own absolute path as its label.
        return sources[0].resolve().parent
    return folders[0].resolve()


def verify_analysis(path):
    """Open one written analysis read-only and count what it really holds.

    An import that reports 412 rows and writes 411 is the failure this catches:
    nothing else in the application would ever look again.
    """
    path = Path(path)
    if not path.is_file():
        return dict(status='missing', reason='Analysis file is gone')
    expected = None
    try:
        connection = duckdb.connect(str(path), read_only=True)
        try:
            row = connection.execute("SELECT value FROM metadata WHERE key='source'").fetchone()
            if row:
                expected = json.loads(row[0]).get('rows')
            rows = int(connection.execute('SELECT count(*) FROM events').fetchone()[0])
        finally:
            connection.close()
    except Exception as exc:  # noqa: BLE001 - the verdict is a row, not an exception
        return dict(status='unreadable', reason=str(exc)[:200])
    if expected is not None and rows != expected:
        return dict(status='mismatch', rows=rows, expected=expected,
                    reason=f'{rows} rows on disk, {expected} recorded at import')
    return dict(status='ok', rows=rows, expected=expected)


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
    if magic.startswith(b'ElfFile\0') or name.endswith('.evtx'):
        return ['EvtxECmd']
    if name.startswith(('amcache', 'inventory')) and (magic.startswith(b'regf') or magic.startswith(b'SQLite format 3')):
        return ['AmcacheParser']
    if magic.startswith(b'regf'):
        if name.startswith(('usrclass','ntuser')):return ['RECmd','Shellbags']
        return ['AppCompatCacheParser', 'RECmd'] if name == 'system' else ['RECmd']
    if name.startswith('webcache') and name.endswith('.dat'):
        return ['WebCache']
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
    from fireblade.core.catscale import recognized, kind
    if recognized(path) and (path.suffix.casefold() not in ('.csv','.tsv') or (path.suffix.casefold()=='.csv' and kind(path)=='timeline')):
        return ['CatScale']
    from fireblade.core.linux_logs import recognized as linux_recognized
    if linux_recognized(path, magic):
        return ['LinuxLogs']
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


BLOCKED_SIGNATURES = ('0x800711C7', 'FileLoadException')


def fit_budget_to_file(budget, csv, progress=lambda _: None, ceiling_mb=None):
    """Give an import room for the file it reads, instead of learning it by failing.

    A bulk CSV insert cannot spill to disk: with a 128 MB budget a 3 GB table fails,
    the retry loop multiplies the budget, and every attempt re-reads the whole file.
    The analyst waits several times longer than the work needs, with one unchanging
    message. Sizing the first attempt from the file replaces those passes with one,
    still bounded by half the physical memory.
    """
    if budget is None:
        return budget
    try:
        size_mb = Path(csv).stat().st_size // (1024 * 1024)
    except OSError:
        return budget
    needed = size_mb + size_mb // 4 + 64
    current = int(getattr(budget, 'memory_mb', 0) or 0)
    ceiling = int(ceiling_mb or max(1024, physical_memory_mb() // 2))
    target = min(ceiling, max(current, needed))
    if target > current:
        progress('Import: memory budget raised to %d MB for a %d MB file' % (target, size_mb))
        return replace(budget, memory_mb=target)
    return budget


def blocked_by_windows(log):
    """True when the engine log already says Windows refused one of its libraries."""
    try:
        with Path(log).open('rb') as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - 20000))
            text = stream.read().decode('utf-8', 'replace')
    except OSError:
        return False
    return any(signature in text for signature in BLOCKED_SIGNATURES)


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
            checked = 0.0
            while process.poll() is None:
                check_cancel()
                if time.monotonic() - start > timeout:
                    raise TimeoutError('Délai du moteur dépassé ; consulter le journal')
                # A plugin blocked by Windows keeps the engine alive while it prints
                # FileLoadException: waiting the full hour is a dead end for the user.
                if time.monotonic() - checked > 1:
                    checked = time.monotonic()
                    if blocked_by_windows(log):
                        raise RuntimeError(
                            'Windows a bloqué une bibliothèque de ce moteur (0x800711C7, Smart App Control). '
                            'Autorisez le moteur dans Sécurité Windows → Contrôle des applications et du navigateur, '
                            'ou désactivez Smart App Control, puis relancez la collecte.')
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


def entry_reason(entry):
    """The sentence a report row shows for a file that was not fully read.

    The reason is recorded per run (a reader error) or per member (a file inside a
    jar), never at the file level, so the report's Reason column used to stay empty
    while the information sat one level down. Deduplicated and bounded: a row shows
    one line, the details stay in the file's own panel.
    """
    reasons = []
    for run in entry.get('runs') or []:
        if run.get('error'):
            reasons.append(str(run['error']))
        for member in (run.get('linux_logs') or {}).get('members') or []:
            if member.get('reason'):
                reasons.append(str(member['reason']))
        if not reasons:
            for warning in run.get('warnings') or []:
                reasons.append(str(warning))
    joined = ' ; '.join(dict.fromkeys(reasons))
    return joined[:400]

class CollectionProgress:
    """Where the import stands, told in one place.

    An import of a hundred and nineteen files gives nothing to watch for twenty minutes:
    the rows appear one grid at a time and the window looks asleep. This keeps the counts
    — files done, the file being read, rows written, an estimate of what is left — so the
    interface can show a percentage instead of a spinner.

    Written from several threads: every field is behind one lock, and a snapshot is taken
    under it. The percentage weights files by their size, not by their number: one 4 GB
    image is not worth the same as one 2 KB text file. The file in progress adds a partial
    share, estimated from the speed of the files already finished, and never counted as
    complete before it is.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self.total_weight = 0.0
            self.done_weight = 0.0
            self.done = 0
            self.total = 0
            self.current = ''
            self.rows = 0
            self.started = time.monotonic()
            self.started_current = None
            self.stage = 'inventory'
            self.finished = False

    def inventory(self, weights):
        """The plan is known: weights are bytes, or one each when a size is missing."""
        with self._lock:
            self.total = len(weights)
            self.total_weight = float(sum(weights)) or float(len(weights)) or 1.0

    def begin(self, name, weight=1):
        with self._lock:
            self.current = name
            self.current_weight = max(float(weight), 0.0) or 1.0
            self.started_current = time.monotonic()
            self.rows = 0
            self.stage = 'parse'

    def note(self, text):
        """The parsers say how many records they wrote; that is the only live number."""
        match = re.search(r'([\d][\d  ,.]*)\s+enregistrement', text or '')
        if not match:
            return
        digits = re.sub(r'[^\d]', '', match.group(1))
        if not digits:
            return
        with self._lock:
            if not self.finished:
                self.rows = int(digits)

    def finish_current(self, rows=None):
        with self._lock:
            self.done += 1
            self.done_weight += getattr(self, 'current_weight', 1.0)
            if rows:
                self.rows = int(rows)
            self.current = ''
            self.started_current = None

    def phase(self, name):
        """A step with no weight of its own: the merge that follows the reading."""
        with self._lock:
            self.current = name
            self.stage = 'organize'
            self.started_current = None

    def done_all(self):
        with self._lock:
            self.finished = True
            self.current = ''
            self.stage = 'done'

    def snapshot(self):
        with self._lock:
            elapsed = max(time.monotonic() - self.started, 0.001)
            fraction = self.done_weight / self.total_weight if self.total_weight else 0.0
            partial = 0.0
            if not self.finished and self.started_current is not None and self.done:
                speed = self.done_weight / elapsed
                spent = (time.monotonic() - self.started_current) * speed
                partial = min(spent, 0.6 * getattr(self, 'current_weight', 1.0))
            fraction = max(0.0, min(1.0, fraction + partial / self.total_weight if self.total_weight else 0.0))
            percent = 100.0 if self.finished else min(99.0, fraction * 100.0)
            remaining = 0.0
            if fraction > 0.02 and not self.finished:
                remaining = max(0.0, elapsed * (1.0 - fraction) / fraction)
            return dict(total=self.total, done=self.done, current=self.current, rows=self.rows,
                        percent=round(percent, 1), elapsed=round(elapsed, 1),
                        remaining=round(remaining, 1), phase=self.stage, finished=self.finished)


class Collection:
    # A folder import reads one export once, whatever path it was found under; a disk
    # collection must not: two partitions holding the same bytes are two pieces of
    # evidence, each with its own location, and the report would lose one of them.
    deduplicate_content = True

    def __init__(self, root, output, pack, settings=None, progress=lambda _: None, organization='files',
                 _reopening=False, index_folder=None):
        if organization not in ('files', 'artifacts', 'combined'):
            raise ValueError('Organisation de collecte inconnue')
        self.sources = normalise_sources(root)
        self.root, self.output = common_root(self.sources), Path(output).resolve()
        if not _reopening:
            missing = [str(item) for item in self.sources if not item.exists()]
            if missing:
                raise ValueError('Source not found: ' + ', '.join(missing[:3]))
            for item in self.sources:
                # Only a folder source can swallow the output: walking it would read the
                # collection into itself. A loose file selected beside the case is normal.
                if not item.is_dir():
                    if self.output == item.resolve():
                        raise ValueError('The working folder cannot be the source itself')
                    continue
                folder = item.resolve()
                if self.output == folder or folder in self.output.parents:
                    raise ValueError('Choisissez un dossier de travail hors de la collecte source')
        self.pack, self.settings = pack, settings
        self.emit_text = progress
        self.progress_state = CollectionProgress()
        self.ready = lambda documents: None
        self._last_checkpoint = 0
        self._case_lock = threading.Lock()
        self._active_case = None
        self._cases = set()
        self.journal = ImportJournal(self.output/'journal.jsonl')
        # What this case already imported, keyed by the evidence digest. A digest
        # this operation wrote itself is not a duplicate, or a resume would refuse
        # to redo the file it just lost.
        self.index_folder = Path(index_folder) if index_folder else None
        self.known = {}
        if self.index_folder is not None:
            self.known = {digest: record for digest, record in load_index(self.index_folder).items()
                          if str(record.get('collection', '')) != str(self.output)}
        self._seen = {}
        self._similar = {}
        self._seen_lock = threading.Lock()
        self.report = dict(format='fireblade-collection', version=1, source=str(self.root),
                           sources=[str(item) for item in self.sources],
                           output=str(self.output), organization=organization, status='pending', files=[], documents=[], detection=None)
        manifest = Path(self.pack.root)/'manifest.json'
        if manifest.is_file():
            self.report['toolchain'] = json.loads(manifest.read_text(encoding='utf-8'))

    @classmethod
    def reopen(cls, output, pack, settings=None, progress=lambda _: None, index_folder=None):
        output = Path(output).resolve()
        data = json.loads((output/'collection.json').read_text(encoding='utf-8'))
        if data.get('format') != 'fireblade-collection' or data.get('version') != 1:
            raise ValueError('Dossier de travail Fireblade invalide')
        instance = cls(data.get('sources') or data['source'], output, pack, settings, progress,
                       _reopening=True, index_folder=index_folder)
        instance.report = data
        instance.report.setdefault('sources', [str(item) for item in instance.sources])
        return instance

    def event(self, kind, **fields):
        '''One line in the operation's journal, and its own failure in the report.'''
        record = self.journal.event(kind, **fields)
        if self.journal.error and self.report.get('journal_error') != self.journal.error:
            # A journal that cannot be written may not fail the import, and may not
            # pass for a complete record either.
            self.report['journal_error'] = self.journal.error
        return record

    def summary(self):
        '''Counts the table and the report can both quote: one field, one number.'''
        counts = {}
        for entry in self.report['files']:
            key = str(entry.get('status', 'pending'))
            counts[key] = counts.get(key, 0) + 1
        return dict(files=len(self.report['files']), analyses=len(self.report['documents']), **counts)

    def save(self):
        self._last_checkpoint = time.monotonic()
        self.report['summary'] = self.summary()
        atomic_json(self.output/'collection.json', self.report)
        if self.report['documents']:
            atomic_json(self.output/'collection.fireblade-session', dict(
                format='fireblade-session', version=1, active=0, documents=self.report['documents']))

    def import_result(self, csv, kind, view=None, register=True, evidence=None):
        check_cancel()
        if register and len(self.report['documents']) >= 1000:
            raise ValueError('Limite de 1000 analyses atteinte ; résultat conservé sur disque')
        # Fireblade must read a folder whatever the machine: a collection running out
        # of memory is a budget problem, not a reason to fail. Each attempt raises the
        # budget (x4, at least +256 MB) up to half the physical RAM, then leans on the
        # bounded row-by-row path, which survives a file far larger than memory.
        budget, attempt = fit_budget_to_file(self.settings, csv, self.progress), 0
        while True:
            try:
                return self._import_once(csv, kind, view, register, budget, evidence)
            except (duckdb.OutOfMemoryException, MemoryError) as exc:
                bigger = grown_memory(getattr(budget, 'memory_mb', 128))
                if not bigger:
                    raise
                attempt += 1
                budget = replace(budget, memory_mb=bigger) if budget else Settings(memory_mb=bigger)
                self.progress('Not enough memory: retrying with %d MB…' % bigger)
                # The retry is part of the operation's record: a run that needed three
                # attempts is not the same run as one that needed none.
                self.event('import.retry', file=Path(csv).name, attempt=attempt,
                           memory_mb=bigger, error=str(exc)[:200])

    def _import_once(self, csv, kind, view, register, budget, evidence=None):
        target = self.output/'analyses'/(uuid.uuid4().hex+'.timeline')
        case = Case(target, settings=budget)
        with self._case_lock:
            self._active_case = case
            self._cases.add(case)
        failed = False
        try:
            self.progress('Chargement Fireblade : '+Path(csv).name)
            provenance = None
            if evidence:
                provenance = dict(evidence)
                provenance['working_path'] = str(csv)
            case.import_csv(csv, encoding='auto', progress=self.progress, provenance=provenance)
            view = view or View()
            # Counted on the connection that just wrote the file: opening the analysis
            # again in read-only is what collided with the workspace (DuckDB refuses two
            # connections with different configurations) while a progressive import was
            # already publishing documents to the grid.
            written = int(case.db.execute('SELECT count(*) FROM events').fetchone()[0])
            expected = int((case.info or {}).get('rows') or 0)
            verdict = dict(status='ok' if written == expected else 'mismatch',
                           rows=written, expected=expected)
            if verdict['status'] != 'ok':
                verdict['reason'] = f'{written} rows written, {expected} read from the source'
            document = dict(path=str(target), source=case.info, view=json.loads(view.to_json()),
                            header='', verification=verdict)
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
                self._cases.discard(case)
                case.close()
            if failed:
                target.unlink(missing_ok=True)

    def interrupt(self):
        with self._case_lock:
            # A collection may now parse several files at once: interrupt all of them.
            for case in list(self._cases):
                case.interrupt()

    def entry_for(self, path):
        """The report entry of one file, created when the collection never saw it."""
        wanted = os.path.normcase(str(Path(path)))
        for entry in self.report['files']:
            if os.path.normcase(str(entry.get('path', ''))) == wanted:
                return entry
        entry = dict(path=str(path), status='unsupported', tools=[])
        self.report['files'].append(entry)
        return entry

    def analyse_single(self, path, reader='text'):
        """Read one file with a chosen reader, at the examiner's request.

        The collection does not guess twice. A file whose format was not recognised
        stays unread until somebody asks for it, and the request is written into the
        report next to the hash it was made on, so the decision can be reviewed and
        the outcome reproduced. The source is read, never modified.
        """
        if reader not in ('text', 'html', 'csv', 'pdf'):
            raise ValueError('Lecteur inconnu : '+str(reader))
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError('Fichier introuvable : '+str(path))
        entry = self.entry_for(path)
        if entry.get('status') == 'deleted':
            raise ValueError('Fichier supprimé du bilan : '+str(path))
        digest = sha256(path)
        if entry.get('sha256') and entry['sha256'] != digest:
            raise ValueError('Le fichier a changé depuis la collecte ; analyse refusée')
        entry['sha256'] = digest
        # The tool name is what the report shows: two reads of one file must not look
        # like the same reader twice.
        tool = {'text': 'TextReader', 'html': 'HTMLPage', 'csv': 'native', 'pdf': 'PDFReader'}[reader]
        run = dict(tool=tool, status='running', outputs=[], reader=reader)
        entry.setdefault('runs', []).append(run)
        folder = self.output/'results'/uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if reader == 'csv':
                csvs = [path]
            elif reader == 'pdf':
                from fireblade.core import pdfreader
                if not pdfreader.available():
                    raise ValueError("Lecteur PDF indisponible : installez l’extension pypdf")
                target = folder/(uuid.uuid4().hex+'.csv')
                result = pdfreader.write_csv(path, target)
                run['pdf'] = result
                entry['tools'] = sorted(set(entry.get('tools', [])) | {tool})
                if result['status'] in ('scanned', 'encrypted', 'unreadable', 'empty'):
                    # Not a failure of the tool: what the file is, written as the reason.
                    reason = {'scanned': 'PDF sans couche texte : un scan ne se lit pas sans OCR',
                              'encrypted': 'PDF chiffré : la couche texte demande un mot de passe',
                              'unreadable': 'PDF illisible : ' + (result['warnings'][0] if result['warnings'] else 'aucune page décodée'),
                              'empty': 'PDF sans page'}[result['status']]
                    run.update(status='no_output', error=reason)
                    entry.update(status='no_output', error=reason)
                    return entry
                if not result['rows']:
                    raise ValueError('Aucune ligne lisible dans ce fichier')
                csvs = [target]
            else:
                from fireblade.core import textreader
                target = folder/(uuid.uuid4().hex+'.csv')
                # "text" leaves the decision to the bytes: a binary file stays refused.
                result = textreader.write_csv(path, target, kind='html' if reader == 'html' else None)
                run['textreader'] = result
                if not result['rows']:
                    raise ValueError('Aucune ligne lisible dans ce fichier')
                if result['truncated']:
                    run['warnings'] = [translate('Fichier lu en partie : {} lignes, sur {} octets').format(
                        result['rows'], result['size'])]
                csvs = [target]
            for csv_path in csvs:
                check_cancel()
                evidence = None if reader == 'csv' else dict(
                    path=str(path), size=path.stat().st_size, sha256=entry.get('sha256', ''),
                    label=self.label_for(path), artifact=str(path), parser=tool)
                run['outputs'].append(dict(csv=str(csv_path),
                                           analysis=self.import_result(csv_path, tool, evidence=evidence)))
            run['status'] = 'complete_with_warnings' if run.get('warnings') else 'complete'
        except OperationCancelled:
            run['status'] = 'cancelled'
            entry['status'] = 'cancelled'
            raise
        except Exception as exc:
            run.update(status='error', error=str(exc))
            entry.update(status='error', error=str(exc))
        else:
            entry['tools'] = sorted(set(entry.get('tools', [])) | {tool})
            entry.pop('error', None)
            healthy = all(item['status'] == 'complete' for item in entry.get('runs', []))
            entry['status'] = 'complete' if healthy else 'attention'
            if not healthy:
                entry['reason'] = entry_reason(entry)
        finally:
            self.save()
        return entry

    def label_for(self, source):
        """The shortest name that still tells two analysed logs apart."""
        try:
            return str(Path(source).resolve().relative_to(self.root)).replace('\\', '/')
        except ValueError:
            return Path(source).name

    def prepare_output(self):
        self.output.mkdir(parents=True, exist_ok=False)

    def walk_sources(self, on_error):
        return os.walk(self.root, followlinks=False, onerror=on_error)

    def walk_roots(self, on_error):
        '''One walker per source folder, in the order the examiner chose them.

        Separate from walk_sources because a disk collection walks a volume it
        discovers itself, while a folder import walks what was selected.
        '''
        return [os.walk(folder, followlinks=False, onerror=on_error)
                for folder in self.sources if folder.is_dir()]

    def inventorize(self, on_error):
        '''Every selected file and folder, one row each, in the examiner's order.'''
        pending = []
        for source in self.sources:
            check_cancel()
            if source.is_file():
                # A file chosen on its own is a source like a folder is; it is not
                # skipped because its parent was not selected.
                entry = dict(path=str(source), status='pending', tools=[], origin='file')
                self.report['files'].append(entry)
                pending.append((source, entry))
        for walker in self.walk_roots(on_error):
            for directory, dirs, names in walker:
                for name in list(dirs):
                    path = Path(directory)/name
                    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                        dirs.remove(name)
                        entry = dict(path=str(path), status='skipped', error='Lien de dossier non suivi', tools=[])
                        self.report['files'].append(entry)
                        self.event('file.done', path=str(path), status='skipped',
                                   reason='Lien de dossier non suivi')
                for name in sorted(names):
                    check_cancel()
                    source = Path(directory)/name
                    entry = dict(path=str(source), status='pending', tools=[])
                    self.report['files'].append(entry)
                    pending.append((source, entry))
        return pending

    def publish_results(self, start, entry):
        """Hook for immutable, closed results after source integrity checks."""
        if entry['status'] not in ('complete', 'attention'):
            del self.report['documents'][start:]
        elif self.report['organization'] == 'files':
            self.ready(copy.deepcopy(self.report['documents'][start:]))

    def parse_linux(self, source, output):
        """Read one Linux log in a child process, and never lose the ability to read it.

        A pool that cannot start (a frozen build without the flag, a machine out
        of processes) must cost speed, not the collection: the first failure falls
        back on this process for the rest of the run and says so once.
        """
        pool = self.parser_pool()
        if pool is not None:
            try:
                from fireblade.core.linux_slices import plan, read_in_slices
                spans = plan(source, pool.size)
                if spans:
                    return read_in_slices(pool, source, output, spans, self.progress)
                return pool.run(source, output)
            except Exception as exc:  # noqa: BLE001 - a speed path may not fail a collection
                self.progress('Reading in this process: ' + str(exc))
                pool.close()
                self._parse_pool = None
                self._parse_pool_failed = True
        from fireblade.core.linux_logs import parse
        return parse(source, output, self.progress)

    def parser_pool(self):
        """The processes that read Linux logs, started on first use."""
        if getattr(self, '_parse_pool_failed', False):
            return None
        if getattr(self, '_parse_pool', None) is None:
            from fireblade.core.parse_pool import ParsePool
            self._parse_pool = ParsePool(self.workers()).start()
        return self._parse_pool

    def progress(self, text):
        """One message from a parser or the collection: shown, and counted."""
        self.progress_state.note(text)
        self.emit_text(text)

    def workers(self):
        """How many files at once: the effort level, one per thread, capped at eight.

        The parsers are external processes and the disk is shared, so past a handful
        of workers the run gets slower, not faster. Eight is the measured knee.
        """
        threads = int(getattr(self.settings, 'threads', 0) or 0)
        if threads <= 0:
            threads = auto_threads()
        return max(1, min(threads, 8, os.cpu_count() or 1))

    def _parse_entry(self, source, entry):
        """One file, timed and journalled, whatever it decides.

        The wrapper is what makes the journal exhaustive: a file that is read, a
        file that is refused and a file whose reader dies all leave one line each,
        with the reason the row shows.
        """
        started = time.monotonic()
        self.event('file.started', path=str(source))
        try:
            return self._read_entry(source, entry)
        finally:
            self.event('file.done', path=str(source), status=entry.get('status'),
                       reason=(entry.get('reason') or entry.get('error') or '')[:400] or None,
                       analyses=sum(len(run.get('outputs', [])) for run in entry.get('runs', [])),
                       seconds=round(time.monotonic() - started, 3))

    def _read_entry(self, source, entry):
        """One file, from identity to its analyses. Returns the documents it produced.

        Written to run on a worker thread: it only touches the entry it was given, its
        own output folder, and returns its analyses instead of appending them, so the
        collection keeps file order whatever order the workers finish in.
        """
        documents = []
        check_cancel()
        self.progress('Collecte : '+self.label_for(source))
        try:
            if source.is_symlink() or self.root not in source.resolve().parents:
                entry.update(status='skipped', error='Lien de fichier non suivi')
                return documents
            if not source.is_file():
                entry.update(status='skipped', error='Fichier spécial non lu (socket, FIFO ou périphérique)')
                return documents
            tools = identify(source)
            entry['tools'] = tools
            if not tools:
                entry['status'] = 'unsupported'
                entry['reason'] = 'No reader recognised this file'
                return documents
            entry['sha256'] = digest = sha256(source)
            duplicate = self.duplicate_of(entry)
            if duplicate:
                return documents
            if tools == ['companion']:
                entry.update(tools=[], status='companion', kind='registry_transaction_log')
                return documents
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
                    if tool == 'WebCache':
                        from fireblade.core.webcache import parse
                        result = parse(source, output, self.progress)
                        run['webcache'] = result
                        run['warnings'] = result['warnings']
                        csvs = [Path(item['csv']) for item in result['outputs']]
                    elif tool in ('CatScale', 'LinuxLogs'):
                        if tool == 'LinuxLogs':
                            result = self.parse_linux(source, output)
                        else:
                            from fireblade.core.catscale import parse
                            result = parse(source, output)
                        run['linux_logs' if tool == 'LinuxLogs' else 'catscale'] = result
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
                        # The provenance travels with the import: the parser CSV is
                        # read once, and no enriched copy is written beside it.
                        evidence = None if tool == 'native' else dict(
                            path=str(source), size=source.stat().st_size,
                            sha256=entry.get('sha256', ''), label=self.label_for(source),
                            artifact=str(source), parser=tool)
                        document = self.import_result(csv, tool, register=False, evidence=evidence)
                        documents.append(document)
                        run['outputs'].append(dict(csv=str(csv), analysis=document['path'], **({'family':catscale_outputs[str(csv)]['family']} if tool in ('CatScale', 'LinuxLogs') else {})))
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
            if entry['status'] != 'complete':
                entry['reason'] = entry_reason(entry)
        except OperationCancelled:
            entry['status'] = 'cancelled'
            raise
        except Exception as exc:
            entry.update(status='error', error=str(exc))
        return documents

    def duplicate_of(self, entry):
        """Name the already-read copy of this content, and mark the row a duplicate.

        Two references to one export are one piece of evidence: reading it twice
        doubles the tabs and the analyst's reading time for nothing. The decision
        is taken on the source's SHA-256, and the row keeps the path of the copy
        that was read, so nothing disappears from the report.
        """
        digest = entry.get('sha256')
        if not digest or not self.deduplicate_content:
            return None
        path = str(entry.get('path', ''))
        signature = (Path(path).name.casefold(), entry.get('size'))
        with self._seen_lock:
            # setdefault is the whole decision: the first row to arrive owns the
            # content, and a row that finds itself already registered is reading
            # its own file again (a resume), not a second copy of it.
            first = self._seen.setdefault(digest, entry)
            twin = self._similar.get(signature)
            if twin is None:
                self._similar[signature] = (digest, path)
            elif twin[0] != digest:
                # Same name and same size, different content: the two files look alike and
                # are not the same. It is imported, and the row says what it resembles.
                entry['similar_to'] = twin[1]
        if first is not entry:
            reason = f'Same content as {self.label_for(first.get("path", path))} ; read once'
            entry.update(status='duplicate', reason=reason, duplicate_of=first.get('path'))
            self.event('file.duplicate', path=path, sha256=digest, duplicate_of=first.get('path'))
            return entry
        known = self.known.get(digest)
        # The index excludes this collection's own output, so a hit means another
        # import in this case already read this content — same path or a copy of it.
        if known:
            folder = Path(str(known.get('collection', ''))).name or 'an earlier import'
            reason = f'Already imported from {known.get("path", "?")} ({folder})'
            entry.update(status='duplicate', reason=reason, duplicate_of=known.get('path'))
            self.event('file.duplicate', path=path, sha256=digest, duplicate_of=known.get('path'),
                       collection=str(known.get('collection', '')))
            return entry
        return None

    def safe_parse(self, source, entry):
        """One file's outcome, never the operation's.

        A bug in one reader used to unwind the merge loop and end a collection
        that had already read two thousand files. It now costs one row, with the
        reason, and the other files carry on.
        """
        try:
            return self._parse_entry(source, entry)
        except OperationCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - isolation is the point of this method
            message = (str(exc) or exc.__class__.__name__)[:400]
            entry.update(status='error', reason=message, error=message)
            self.event('file.crashed', path=str(source), reason=message)
            return []

    def record_index(self):
        """Remember what this operation read, so a later import can refuse it."""
        if self.index_folder is None:
            return 0
        records = {}
        for entry in self.report['files']:
            digest = entry.get('sha256')
            if not digest or entry.get('status') not in ('complete', 'attention', 'duplicate'):
                continue
            records[digest] = dict(path=str(entry.get('duplicate_of') or entry.get('path')),
                                   import_path=str(entry.get('path')),
                                   collection=str(self.output), status=entry.get('status'))
        try:
            added = update_index(self.index_folder, records)
        except OSError as exc:
            self.event('index.failed', reason=str(exc))
            return 0
        self.event('index.updated', added=added, files=len(records))
        return added

    def verify_documents(self):
        """Report what the import proved about every analysis it wrote.

        Each analysis was counted on the connection that wrote it, before that connection
        closed. Reopening it here is what broke the workspace: a progressive import
        publishes a document as soon as it exists, the grid opens it read-write, and a
        second read-only connection makes DuckDB refuse both. A document that carries no
        verdict (an older collection) is reported as unchecked, never re-read.
        """
        checked = broken = unchecked = 0
        for document in list(self.report['documents']):
            check_cancel()
            verdict = document.get('verification') or {}
            if not verdict:
                verdict = dict(status='unchecked', reason='imported before the verification existed')
                document['verification'] = verdict
            if verdict.get('status') == 'ok':
                checked += 1
            elif verdict.get('status') == 'unchecked':
                unchecked += 1
            else:
                broken += 1
                self.event('analysis.broken', path=document.get('path'), reason=verdict.get('reason'))
        self.report['verification'] = dict(checked=checked, broken=broken, unchecked=unchecked)
        self.event('verification.done', checked=checked, broken=broken, unchecked=unchecked)
        return self.report['verification']

    @staticmethod
    def _weight(entry):
        """A file's share of the import: its size, one point when the size is unknown."""
        try:
            return float(entry.get('size') or 1)
        except (TypeError, ValueError):
            return 1.0

    def _merge(self, entry, documents):
        """Append one file's analyses, in file order, and publish them."""
        self.report['progress'] = self.progress_state.snapshot()
        start = len(self.report['documents'])
        self.report['documents'].extend(documents)
        self.publish_results(start, entry)
        if time.monotonic()-self._last_checkpoint >= 1:
            self.save()

    def _run_entries(self, pending):
        """Parse every inventoried file, on one thread or on several.

        Files are independent — each has its own output folder and its own analysis —
        so the only shared state is the report, and it is written by this thread alone.
        """
        workers = self.workers()
        if workers <= 1 or len(pending) < 2:
            for source, entry in pending:
                self.progress_state.begin(self.label_for(source), self._weight(entry))
                self._merge(entry, self.safe_parse(source, entry))
                self.progress_state.finish_current()
            return
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='fireblade-parse') as pool:
            # The cancellation flag lives in a ContextVar, and a fresh thread starts
            # with an empty context: without this copy, a worker never sees the stop.
            import contextvars
            context = contextvars.copy_context()
            futures = [pool.submit(context.copy().run, self._parse_entry, source, entry)
                       for source, entry in pending]
            merged = 0
            try:
                for index, ((source, entry), future) in enumerate(zip(pending, futures)):
                    # A worker sees the stop through its copied context, but a file that
                    # finished before the request never raises: before publishing the next
                    # one, this thread honours the stop itself. What is already merged stays.
                    if index:
                        check_cancel()
                    self.progress_state.begin(self.label_for(source), self._weight(entry))
                    self._merge(entry, self._future_documents(future, source, entry))
                    self.progress_state.finish_current()
                    merged += 1
            except OperationCancelled:
                for future in futures:
                    future.cancel()
                # A cancelled collection keeps what it had already finished: the files
                # that completed are published, in file order, before the stop is reported.
                for (source, entry), future in list(zip(pending, futures))[merged:]:
                    if future.done() and not future.cancelled() and future.exception() is None:
                        self._merge(entry, future.result())
                raise

    def _future_documents(self, future, source, entry):
        '''The worker's documents, or the row that says why there are none.'''
        try:
            return future.result()
        except OperationCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - one file may not end the operation
            message = (str(exc) or exc.__class__.__name__)[:400]
            entry.update(status='error', reason=message, error=message)
            self.event('file.crashed', path=str(source), reason=message)
            return []

    def parse(self):
        self.prepare_output()
        (self.output/'analyses').mkdir()
        (self.output/'results').mkdir()
        self.report['status'] = 'running'
        self.event('operation.started', sources=[str(item) for item in self.sources],
                   organization=self.report.get('organization'), threads=self.workers(),
                   memory_mb=getattr(self.settings, 'memory_mb', None))
        self.save()
        pending = []
        try:
            # os.walk does not follow directory symlinks. Every inaccessible entry is reported.
            def walk_error(error):
                message = str(error)
                entry = dict(path=str(getattr(error, 'filename', self.root)), status='error',
                             error=message, reason=message, tools=[])
                self.report['files'].append(entry)
                self.event('file.done', path=entry['path'], status='error', reason=message)
            pending = self.inventorize(walk_error)
            self.progress_state.reset()
            self.progress_state.inventory([self._weight(entry) for _source, entry in pending])
            self.report['progress'] = self.progress_state.snapshot()
            self.event('inventory.done', files=len(self.report['files']), to_read=len(pending))
            self._run_entries(pending)
            from fireblade.core.collection_organization import organize
            if self.report.get('organization') in ('artifacts', 'combined'):
                # Merging the families takes minutes on a big collection: the bar must not
                # claim 100 % while it is still writing the merged grids.
                self.progress_state.phase(translate('Organisation des familles d’artefacts'))
                self.report['progress'] = self.progress_state.snapshot()
            organize(self)
            self.verify_documents()
            self.progress_state.done_all()
            self.report['progress'] = self.progress_state.snapshot()
            self.report['status'] = 'complete'
        except OperationCancelled:
            self.report['status'] = 'cancelled'
            self.progress_state.done_all()
            self.report['progress'] = self.progress_state.snapshot()
        except BaseException:
            self.report['status'] = 'error'
            raise
        finally:
            # The index is part of the operation, so it is written before the line
            # that closes the record: the last event of a journal is its own ending.
            self.record_index()
            self.event('operation.finished', status=self.report['status'],
                       files=len(self.report['files']), analyses=len(self.report['documents']),
                       journal_error=self.journal.error or None)
            self.save()
            pool = getattr(self, '_parse_pool', None)
            if pool is not None:
                pool.close()
                self._parse_pool = None
        return self.report

    def resumable(self):
        '''How many files a reopen would still have to read.'''
        return sum(1 for entry in self.report.get('files', [])
                   if entry.get('status') in ('pending', 'running', 'cancelled')
                   or (entry.get('status') in ('complete', 'attention') and self._analyses_gone(entry)))

    @staticmethod
    def _analyses_gone(entry):
        '''True when a row claims an analysis whose file no longer exists.'''
        for run in entry.get('runs', []):
            for output in run.get('outputs', []):
                analysis = output.get('analysis')
                if analysis and not Path(analysis).is_file():
                    return True
        return False

    def resume(self):
        '''Continue an interrupted operation: keep what is done, read what is not.

        An operation that was stopped, or whose window was closed, left its report
        and its written analyses on disk. Rereading the whole folder to recover a
        handful of files is the cost this removes; a row whose analysis vanished is
        put back in the queue rather than trusted.
        '''
        if not (self.output/'analyses').is_dir():
            (self.output/'analyses').mkdir(parents=True)
        (self.output/'results').mkdir(exist_ok=True)
        self.report['status'] = 'running'
        self.event('resumed', files=len(self.report['files']), pending=self.resumable())
        if self.report.get('raw_documents'):
            # A merged layout is derived: rebuild it from the analyses it merged,
            # because one of the merged tables may be the file that is gone.
            self.report['documents'] = list(self.report['raw_documents'])
            self.report.pop('raw_documents', None)
        # The digest map is a process-local cache: refill it from the rows this
        # operation already read, so a file resumed beside a copy of it stays one row.
        self._seen = {entry['sha256']: entry for entry in self.report['files']
                      if entry.get('sha256') and entry.get('status') in ('complete', 'attention')}
        pending, missing = [], 0
        for entry in self.report['files']:
            status = entry.get('status')
            if status in ('pending', 'running', 'cancelled'):
                entry['status'] = 'pending'
                pending.append((Path(entry['path']), entry))
                continue
            if status in ('complete', 'attention') and self._analyses_gone(entry):
                entry['status'] = 'pending'
                entry.pop('error', None)
                pending.append((Path(entry['path']), entry))
                missing += 1
        self._drop_missing_documents()
        try:
            self._run_entries(pending)
            from fireblade.core.collection_organization import organize
            organize(self)
            self.verify_documents()
            self.report['status'] = 'complete'
        except OperationCancelled:
            self.report['status'] = 'cancelled'
        except BaseException:
            self.report['status'] = 'error'
            raise
        finally:
            self.record_index()
            self.event('operation.finished', status=self.report['status'], resumed=True,
                       reread=len(pending), lost_analyses=missing,
                       files=len(self.report['files']), analyses=len(self.report['documents']),
                       journal_error=self.journal.error or None)
            self.save()
        return self.report

    def _drop_missing_documents(self):
        '''A document whose database is gone must not be offered to the workspace.'''
        kept = []
        for document in self.report['documents']:
            if Path(document.get('path', '')).is_file():
                kept.append(document)
            else:
                self.event('analysis.missing', path=document.get('path'))
        self.report['documents'] = kept

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
            rules = Path(self.pack.root)/'Hayabusa'/'rules'
            try:
                from fireblade.core import hayabusa_rules
                if hayabusa_rules.has_changes():
                    # The analyst edited or switched off rules: Hayabusa reads a folder built
                    # for this run, and the delivered pack stays untouched.
                    merged = Path(self.output)/'hayabusa-rules'
                    receipt = hayabusa_rules.effective_rules(rules, merged)
                    self.progress('Règles Hayabusa : {} utilisateur · {} désactivées · {} liées'.format(
                        receipt['overrides'], receipt['skipped'], receipt['linked']))
                    rules = Path(receipt['path'])
            except Exception as exc:  # noqa: BLE001 - a rule folder must not stop a run
                self.progress('Règles Hayabusa non chargées : '+str(exc))
            command = self.pack.command('Hayabusa') + ['dfir-timeline', '-d', str(inputs), '-o', str(target),
                '-r', str(rules), '--no-wizard', '--min-level', min_level,
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
