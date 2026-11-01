"""Export the documented TLE SessionFiles contract without losing tag identity."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading

from fireblade.core.engine import Case
from fireblade.core.paths import same_file,protected_destination
from fireblade.core.errors import OperationCancelled,job_cancelled


MAX_SESSION_BYTES=4*1024*1024


class TleSessionExport:
    def __init__(self,documents,settings,active=None):
        self.documents=copy.deepcopy(documents)
        self.settings,self.active=settings,active
        self.cancelled=threading.Event()
        self.lock=threading.Lock()
        self.current=None

    def interrupt(self):
        self.cancelled.set()
        with self.lock:
            if self.current:self.current.interrupt()

    def check_cancelled(self):
        if self.cancelled.is_set() or job_cancelled():raise OperationCancelled()

    @staticmethod
    def source_state(stat):
        return stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns

    def verify_source(self,source,info):
        before=source.stat()
        if before.st_size!=info['size']:raise ValueError('La source a changé depuis son import : '+str(source))
        digest=hashlib.sha256()
        with source.open('rb') as stream:
            while block:=stream.read(1024*1024):
                self.check_cancelled();digest.update(block)
        after=source.stat()
        if digest.hexdigest()!=info['sha256'] or self.source_state(before)!=self.source_state(after):
            raise ValueError('La source a changé depuis son import : '+str(source))
        return self.source_state(after)

    def tags(self,case):
        with case.operation():
            if case.info.get('format')=='tle-plugin':
                count=case.db.execute('SELECT count(*) FROM bookmarks').fetchone()[0]
                if not count:return []
                if count>100000:raise ValueError('100000 tags maximum par fichier TLE')
                if 'TLE_SourceLine' not in case.headers:
                    raise ValueError('Le lecteur ne fournit pas TLE_SourceLine : les signets ne peuvent pas être exportés fidèlement')
                col=case.column(case.headers.index('TLE_SourceLine'))
                records=case.db.execute(f'SELECT try_cast({col} AS BIGINT),regexp_full_match(trim({col}), ?)'
                    ' FROM events e JOIN bookmarks b ON e.__row_id=b.row_id',['[0-9]+']).fetchall()
                if any(line is None or line<1 or not valid for line,valid in records):
                    raise ValueError('Numéro de ligne source du lecteur invalide pour un signet')
                tags=sorted({line for line,_ in records})
                # One TLE tag marks all rows carrying that source line. Refuse
                # a partially marked duplicate instead of changing the selection.
                partial=case.db.execute(f'SELECT 1 FROM events e LEFT JOIN bookmarks b ON e.__row_id=b.row_id'
                    f' WHERE try_cast({col} AS BIGINT) IN (SELECT unnest(?::BIGINT[])) AND b.row_id IS NULL LIMIT 1',[tags]).fetchone()
                if partial:raise ValueError('Plusieurs lignes du lecteur partagent un numéro source et ne sont pas toutes marquées')
                return tags
            tags=[row[0] for row in case.db.execute('SELECT row_id FROM bookmarks ORDER BY row_id LIMIT 100001').fetchall()]
            if len(tags)>100000:raise ValueError('100000 tags maximum par fichier TLE')
            if any(tag<1 or tag>case.info['rows'] for tag in tags):raise ValueError('Signet sans ligne source correspondante')
            return tags

    def run(self,path):
        path=Path(path).resolve()
        if not 1<=len(self.documents)<=1000:raise ValueError('Une session TLE doit contenir de 1 à 1000 fichiers')
        sources={};verified=[];content_bytes=0;protected={Path(doc.path).resolve() for doc in self.documents}
        protected.update(Path(doc.source_info['path']).resolve() for doc in self.documents)
        if protected_destination(path,protected):raise ValueError('La session ne peut pas remplacer une source ou une analyse')
        for doc in self.documents:
            self.check_cancelled()
            target=Path(doc.path).resolve()
            if not target.is_file():raise ValueError('Analyse introuvable : '+str(target))
            own=self.active is None or not same_file(self.active.path,target)
            case=None
            try:
                case=Case(target,settings=self.settings,read_only=True) if own else self.active
                with self.lock:
                    self.current=case
                    self.check_cancelled()
                if case.info!=doc.source_info:raise ValueError('L’analyse a été remplacée : '+str(target))
                source=Path(case.info['path']).resolve()
                if any(same_file(source,previous) for previous in sources):raise ValueError('Une même source apparaît dans plusieurs analyses : '+str(source))
                if not source.is_file():raise ValueError('Source introuvable : '+str(source))
                verified.append((source,self.verify_source(source,case.info)))
                if case.info.get('format') in ('xlsx','xls'):
                    if case.info['format']=='xls':raise ValueError('Le format XLS nécessite un lecteur TLE explicite ; exportez d’abord les données vers CSV')
                    from fireblade.core.spreadsheets import sheet_names
                    if case.info.get('sheet')!=sheet_names(source)[0]:
                        raise ValueError('Une session TLE ne peut représenter que la première feuille Excel : '+str(source))
                tags=self.tags(case)
                # Bound accumulation before serializing the entire session.
                # Pretty-print overhead is checked again on the final bytes.
                content_bytes+=len(json.dumps([str(source),tags],ensure_ascii=False,separators=(',',':')).encode('utf-8'))
                if content_bytes>MAX_SESSION_BYTES:raise ValueError('Session TLE limitée à 4 Mo')
                sources[str(source)]=tags
            finally:
                with self.lock:
                    self.current=None
                    if own and case:case.close()
        encoded=json.dumps({'SessionFiles':sources},ensure_ascii=False,indent=2).encode('utf-8')
        if len(encoded)>MAX_SESSION_BYTES:raise ValueError('Session TLE limitée à 4 Mo')
        temporary=None
        try:
            with tempfile.NamedTemporaryFile('wb',dir=path.parent,suffix='.partial',delete=False) as output:
                temporary=Path(output.name);output.write(encoded)
            self.check_cancelled()
            for source,state in verified:
                if self.source_state(source.stat())!=state:raise ValueError('La source a changé pendant l’export : '+str(source))
            os.replace(temporary,path)
        finally:
            if temporary:temporary.unlink(missing_ok=True)
        return len(sources)
