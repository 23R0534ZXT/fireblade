"""Disk-backed cross-artifact chronology with exact UTC nanosecond keys."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import tempfile
import threading
import csv
import os

import duckdb

from fireblade.core.errors import OperationCancelled
from fireblade.core.models import View
from fireblade.core.timestamps import timestamp_key
from fireblade.core.workspace_reader import WorkspaceReader
from fireblade.core.csv_chunks import csv_chunks

KINDS = {'text': 'Tout le texte', 'user': 'Utilisateur', 'ip': 'Adresse IP', 'path': 'Chemin', 'hash': 'Empreinte'}


def field_kind(header):
    value = re.sub(r'[^a-z0-9]', '', header.casefold())
    if any(token in value for token in ('username', 'accountname', 'userid', 'subjectuser', 'targetuser')) or value in ('user', 'utilisateur', 'account'):
        return 'user'
    if any(token in value for token in ('ipaddress', 'sourceip', 'destinationip', 'remoteip', 'localip')) or value in ('ip', 'srcip', 'dstip','sourceaddress','destinationaddress','remoteaddress','localaddress','adressedistante','adresselocale','adressesource','adressedestination'):
        return 'ip'
    if any(token in value for token in ('filepath', 'fullpath', 'targetpath', 'imagepath', 'executablepath')) or value in ('path', 'chemin', 'image', 'filename'):
        return 'path'
    if any(token in value for token in ('sha256', 'sha1', 'md5', 'sha512')) or value in ('hash', 'hashes', 'empreinte'):
        return 'hash'
    return None


def guess_time_column(headers, preferred=()):
    for index in preferred:
        if type(index) is int and 0 <= index < len(headers):return index
    normalized = [re.sub(r'[^a-z0-9]', '', name.casefold()) for name in headers]
    for name in ('timestamputc', 'timecreatedutc', 'datetimeutc', 'timestamp', 'timecreated', 'datetime', 'eventtime', 'date', 'time', 'horodatage', 'dateheure', 'lastwritetimestamp', 'lastwritetime', 'creationtime'):
        if name in normalized:return normalized.index(name)
    return next((i for i, name in enumerate(normalized) if name.endswith('utc')), None)


def utc_label(ns):
    if ns is None:return 'Sans date'
    seconds, fraction = divmod(int(ns), 1_000_000_000)
    try:
        date = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
        return f'{date.year:04}-{date.month:02}-{date.day:02} {date.hour:02}:{date.minute:02}:{date.second:02}' + (f'.{fraction:09d}' if fraction else '') + ' UTC'
    except (OverflowError, ValueError):return str(ns) + ' ns UTC'


class TimelineStore:
    PAGE_SIZE = 250
    def __init__(self, directory=None, memory_mb=256):
        self.temporary = tempfile.TemporaryDirectory(prefix='fireblade-timeline-', dir=directory)
        self.root = Path(self.temporary.name)
        self.db = duckdb.connect(str(self.root/'timeline.duckdb'))
        self.db.execute(f"SET memory_limit='{max(64, int(memory_mb))}MB'")
        self.db.execute('SET threads=1')
        self.db.execute('SET preserve_insertion_order=false')
        self.db.execute('SET enable_progress_bar=false')
        self.lock = threading.RLock()
        self.reader = None
        self.sources = []
        self.closed = False
        self.memory_mb = max(64, int(memory_mb))
        self.db.execute('CREATE TABLE events(source INTEGER, row_id BIGINT, time_ns HUGEINT, source_time VARCHAR, '
                        'summary VARCHAR, note VARCHAR, bookmarked BOOLEAN, naive BOOLEAN, text VARCHAR, '
                        'users VARCHAR, ips VARCHAR, paths VARCHAR, hashes VARCHAR)')

    def close(self):
        with self.lock:
            if not self.closed:
                self.db.close();self.closed=True;self.temporary.cleanup()

    def interrupt(self):
        if self.reader:self.reader.interrupt()
        if not self.closed:self.db.interrupt()

    def build(self, reader: WorkspaceReader, columns, respect_filters=False, progress=lambda _:None):
        self.reader = reader
        with self.lock:
            try:
                self.db.execute('BEGIN')
                self.db.execute('DELETE FROM events')
                sources = []
                for number, document in enumerate(reader.documents):
                    reader.check()
                    progress(f'Chronologie · lecture de l’analyse {number+1}/{len(reader.documents)} : {Path(document.source_info["path"]).name}')
                    source = dict(id=number, path=document.path, name=Path(document.source_info['path']).name,
                                  original=document.source_info['path'],
                                  sha256=document.source_info.get('sha256',''),
                                  rows=0, dated=0, undated=0, naive=0, error='', column=columns.get(document.path))
                    stage = 'reading'
                    try:
                        with reader.open(document) as case:
                            index = columns.get(document.path)
                            source['column_name']=case.headers[index] if index is not None and type(index) is int and 0<=index<len(case.headers) else ''
                            time = case.column(index) if index is not None else 'NULL::VARCHAR'
                            key = timestamp_key(time)
                            fields = {kind: [case.column(i) for i, header in enumerate(case.headers) if field_kind(header) == kind]
                                      for kind in ('user', 'ip', 'path', 'hash')}
                            arrays = [f'to_json(list_value({",".join(fields[kind])}))' if fields[kind] else "'[]'"
                                      for kind in ('user', 'ip', 'path', 'hash')]
                            all_columns = [case.column(i) for i in range(len(case.headers))]
                            text = 'concat_ws(chr(31),' + ','.join(all_columns) + ')'
                            summary_columns = [case.column(i) for i, h in enumerate(case.headers)
                                               if field_kind(h) or any(s in h.casefold() for s in ('description', 'commandline', 'eventid', 'rule', 'artifact'))][:8]
                            if not summary_columns:summary_columns = all_columns[:5]
                            summary = 'left(concat_ws(\' · \',' + ','.join('left('+c+',200)' for c in summary_columns) + '),1000)'
                            naive = f"({key}) IS NOT NULL AND NOT regexp_matches(coalesce({time},''), '(Z|[+-][0-9]{{2}}:?[0-9]{{2}})\\s*$')"
                            where, args = case.where(document.view if respect_filters else View())
                            query = (f'SELECT {number} AS source, __row_id AS row_id, ({key}) AS time_ns, {time} AS source_time, '
                                     f'{summary} AS summary, (SELECT note FROM bookmarks b WHERE b.row_id=events.__row_id) AS note, '
                                     'EXISTS(SELECT 1 FROM bookmarks b WHERE b.row_id=events.__row_id) AS bookmarked, '
                                     f'{naive} AS naive, {text} AS text, ' +
                                     ','.join(f'{value} AS {name}' for value, name in zip(arrays, ('users','ips','paths','hashes'))) +
                                     ' FROM events' + where)
                            from fireblade.core.coverage import analysis_fingerprint
                            source['analysis_fingerprint']=analysis_fingerprint(case,reader.check)
                            # The analysis connection can write only inside its
                            # own spill space; do not grant access to the host's
                            # timeline directory just to transfer query results.
                            spill = Path(str(case.path)+'.tmp'); spill.mkdir(exist_ok=True)
                            transfer = tempfile.TemporaryDirectory(dir=spill, prefix='.timeline-')
                            bridge = Path(transfer.name)/'bridge.csv'
                            try:
                                location = str(bridge).replace("'", "''")
                                case.db.execute(f"COPY ({query}) TO '{location}' (FORMAT CSV, HEADER)", args)
                                reader.check()
                                stage = 'indexing'
                                headers=['source','row_id','time_ns','source_time','summary','note','bookmarked','naive','text','users','ips','paths','hashes']
                                chunks=csv_chunks(bridge,headers,',',self.root,min(16*1024**2,self.memory_mb*1024**2//16),reader.check)
                                written=0
                                try:
                                    for chunk,records in chunks:
                                        reader.check()
                                        buffer=max(16384,chunk.stat().st_size+1)
                                        self.db.execute('INSERT INTO events SELECT source::INTEGER,row_id::BIGINT,time_ns::HUGEINT,source_time,summary,note,'
                                                        'bookmarked::BOOLEAN,naive::BOOLEAN,text,users,ips,paths,hashes '
                                                        "FROM read_csv(?,header=true,all_varchar=true,parallel=false,delim=',',"
                                                        f'max_line_size={buffer},buffer_size={buffer})', [str(chunk)])
                                        written+=records
                                        progress(f'Chronologie · analyse {number+1}/{len(reader.documents)} · {written:,} événements indexés')
                                finally:chunks.close()
                            finally:
                                bridge.unlink(missing_ok=True)
                                transfer.cleanup()
                        stats = self.db.execute("SELECT count(*),count(time_ns),count(*) FILTER(WHERE naive),count(*) FILTER(WHERE time_ns IS NULL AND (source_time IS NULL OR trim(source_time)='')),count(*) FILTER(WHERE time_ns IS NULL AND source_time IS NOT NULL AND trim(source_time)<>'') FROM events WHERE source=?", [number]).fetchone()
                        source.update(rows=stats[0], dated=stats[1], undated=stats[0]-stats[1], naive=stats[2],empty_dates=stats[3],invalid_dates=stats[4])
                        if stats[4]:source['invalid_examples']=[dict(row_id=r[0],value=r[1]) for r in self.db.execute("SELECT row_id,left(source_time,200) FROM events WHERE source=? AND time_ns IS NULL AND source_time IS NOT NULL AND trim(source_time)<>'' ORDER BY row_id LIMIT 5",[number]).fetchall()]
                    except OperationCancelled:raise
                    except Exception as exc:
                        # DuckDB errors in our transaction abort it; source errors do not.
                        if stage == 'indexing':
                            raise
                        source['error'] = str(exc)
                    sources.append(source)
                reader.check();self.db.execute('COMMIT');self.sources = sources
                return sources
            except BaseException:
                self.db.execute('ROLLBACK');raise
            finally:self.reader = None

    def where(self, *, start=None, end=None, sources=None, text='', kind='text', exact=False,
              bookmarks=False, include_undated=False):
        clauses, args = [], []
        if sources is not None:
            clauses.append('source IN (SELECT unnest(?::INTEGER[]))');args.append(list(sources))
        dates = []
        if start is not None:dates.append('time_ns>=cast(? AS HUGEINT)');args.append(str(int(start)))
        if end is not None:dates.append('time_ns<=cast(? AS HUGEINT)');args.append(str(int(end)))
        if dates:clauses.append('(' + ' AND '.join(dates) + (' OR time_ns IS NULL' if include_undated else '') + ')')
        if bookmarks:clauses.append('bookmarked')
        if kind not in KINDS:raise ValueError('Type de corrélation invalide')
        if text:
            if kind == 'text':
                clauses.append('lower(coalesce(text,\'\')) = lower(?)' if exact else 'contains(lower(coalesce(text,\'\')),lower(?))')
            else:
                column = {'user':'users','ip':'ips','path':'paths','hash':'hashes'}[kind]
                value = "json_extract_string(j.value,'$')"
                comparison = f'lower(trim({value}))=lower(trim(?))' if exact else f'contains(lower({value}),lower(?))'
                clauses.append(f'EXISTS(SELECT 1 FROM json_each({column}) j WHERE {comparison})')
            args.append(text)
        return (' WHERE '+' AND '.join(clauses) if clauses else ''), args

    def extent(self, **filters):
        where, args = self.where(**filters)
        with self.lock:
            return self.db.execute('SELECT min(time_ns),max(time_ns),count(*),count(time_ns) FROM events'+where,args).fetchone()

    def page(self, offset=0, **filters):
        where, args = self.where(**filters)
        with self.lock:
            count = self.db.execute('SELECT count(*) FROM events'+where,args).fetchone()[0]
            rows = self.db.execute('SELECT source,row_id,time_ns,source_time,summary,note,bookmarked,naive FROM events'+where+
                                   ' ORDER BY time_ns ASC NULLS LAST,source,row_id LIMIT ? OFFSET ?',args+[self.PAGE_SIZE,max(0,int(offset))]).fetchall()
            return dict(count=count, rows=rows)

    def histogram(self, start, end, bins=120, **filters):
        if int(end)<int(start):raise ValueError('Période de chronologie invalide')
        bins = max(1,min(512,int(bins),int(end)-int(start)+1))
        width = max(1,(int(end)-int(start)+1+bins-1)//bins)
        where, args = self.where(start=start,end=end,**filters)
        where += ' AND time_ns IS NOT NULL'
        with self.lock:
            rows = self.db.execute('SELECT source,((time_ns-cast(? AS HUGEINT))//cast(? AS HUGEINT))::INTEGER AS bucket,count(*),count(*) FILTER(WHERE bookmarked) FROM events'+where+
                                   ' GROUP BY source,bucket ORDER BY source,bucket',[str(int(start)),str(width)]+args).fetchall()
        return dict(start=int(start),end=int(end),width=width,bins=bins,rows=rows)

    def parse_time(self, value):
        with self.lock:
            result = self.db.execute('SELECT '+timestamp_key('cast(? AS VARCHAR)'),[value,value]).fetchone()[0]
        if result is None:raise ValueError('Date ISO invalide ; indiquez le fuseau (ex. 2026-01-01T12:00:00Z)')
        return int(result)

    def export_csv(self, target, *, receipt=False, **filters):
        from fireblade.core.case_package import check_cancelled
        from fireblade.core.paths import protected_destination
        target = Path(target).resolve()
        if protected_destination(target, [s[key] for s in self.sources for key in ('path','original')]):
            raise ValueError('L’export ne peut pas remplacer une analyse ou sa source')
        where, args = self.where(**filters)
        temporary = None
        try:
            with self.lock, tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='', dir=target.parent, suffix='.partial', delete=False) as stream:
                temporary = Path(stream.name)
                from fireblade.core.coverage import RowDigest,verify_export
                content=RowDigest();writer = csv.writer(stream)
                headers=['Date_UTC','Analyse','Source','Ligne_source','Date_source','Résumé_d’événement','Note','Signet','Fuseau_UTC_supposé','SHA256_source_à_l_import']
                writer.writerow(headers)
                expected=self.db.execute('SELECT count(*) FROM events'+where,args).fetchone()[0]
                cursor = self.db.execute('SELECT source,row_id,time_ns,source_time,summary,note,bookmarked,naive FROM events'+where+
                                         ' ORDER BY time_ns ASC NULLS LAST,source,row_id',args)
                count = 0
                while rows := cursor.fetchmany(2048):
                    check_cancelled()
                    for row in rows:
                        source = self.sources[row[0]]
                        values=[utc_label(row[2]),source['path'],source['original'],row[1],row[3],row[4],row[5],row[6],row[7],source['sha256']]
                        content.update(values);writer.writerow(values)
                    count += len(rows)
            if count!=expected:raise ValueError(f'Export incomplet : {count} / {expected} lignes')
            verified=verify_export(temporary,expected,headers,content.hexdigest(),checker=check_cancelled);sha=verified['sha256']
            check_cancelled();os.replace(temporary,target)
            if receipt:return dict(path=str(target),expected=expected,written=count,sha256=sha,verified_rows=verified['verified_rows'],content_sha256=verified['content_sha256'],filters=filters,
                                   partial=any(s['error'] for s in self.sources),undated=sum(s['undated'] for s in self.sources),sources=self.sources)
            return count
        finally:
            if temporary:temporary.unlink(missing_ok=True)
