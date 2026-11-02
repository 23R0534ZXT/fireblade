"""Persistent, bounded details and complete IOC counts for an offline hunt."""
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import io
from itertools import islice
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import uuid

from fireblade.core.errors import OperationCancelled
from fireblade.core.ioc_hunt import (Indicator, IndicatorBatch, IndicatorMatcher, KINDS, MAX_IOCS,
                                      check_cancelled, indicator)
from fireblade.core.models import View
from fireblade.core.paths import protected_destination
from fireblade.core.timeline import guess_time_column

DEFAULT_HIT_LIMIT = 250_000
MAX_HIT_LIMIT = 5_000_000
FORMAT = 'fireblade-ioc-hunt'


class HuntStorageError(RuntimeError):
    pass


class HuntStore:
    PAGE_SIZE = 250

    def __init__(self, path, create=False):
        self.path=Path(path).resolve();self.lock=threading.RLock();self.closed=False
        if not create and not self.path.is_file():raise ValueError('Résultats de chasse introuvables')
        self.db=sqlite3.connect(str(self.path),check_same_thread=False)
        self.db.execute('PRAGMA trusted_schema=OFF')
        self.db.execute('PRAGMA busy_timeout=3000')
        try:
            if create:
                self.db.execute('PRAGMA journal_mode=DELETE')
                self.db.executescript('''
                    CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE indicators(id INTEGER PRIMARY KEY,kind TEXT,value TEXT,raw TEXT,label TEXT,
                                            fields_count INTEGER DEFAULT 0,rows_count INTEGER DEFAULT 0,stored_count INTEGER DEFAULT 0);
                    CREATE TABLE rejections(line INTEGER,value TEXT,reason TEXT);
                    CREATE TABLE sources(id INTEGER PRIMARY KEY,path TEXT,info TEXT,view TEXT,total INTEGER DEFAULT 0,
                                         scanned INTEGER DEFAULT 0,complete INTEGER DEFAULT 0,error TEXT DEFAULT '');
                    CREATE TABLE hits(id INTEGER PRIMARY KEY,ioc INTEGER,source INTEGER,row_id INTEGER,column_id INTEGER,
                                      column_name TEXT,observed TEXT,snippet TEXT,source_time TEXT,rule TEXT);
                    CREATE INDEX hit_ioc ON hits(ioc,id);
                    CREATE INDEX hit_source ON hits(source,id);
                ''')
                self.set_meta('format',FORMAT);self.set_meta('version',1);self.db.commit()
            else:
                tables=dict(self.db.execute("SELECT name,type FROM sqlite_master WHERE name IN ('meta','indicators','sources','hits','rejections')"))
                if any(tables.get(name)!='table' for name in ('meta','indicators','sources','hits','rejections')):
                    raise ValueError('Structure de chasse invalide')
                if self.meta('format')!=FORMAT or self.meta('version')!=1:raise ValueError('Format de chasse inconnu')
            self.metadata=self.all_meta()
        except BaseException:self.db.close();raise

    def close(self):
        with self.lock:
            if not self.closed:self.db.close();self.closed=True

    def interrupt(self):
        if not self.closed:self.db.interrupt()

    def set_meta(self,key,value):
        self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))

    def meta(self,key,default=None):
        row=self.db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
        if not row:return default
        if len(row[0])>16*1024**2:raise ValueError('Métadonnée de chasse trop volumineuse')
        return json.loads(row[0])

    def all_meta(self):
        keys=[row[0] for row in self.db.execute('SELECT key FROM meta')]
        if len(keys)>64:raise ValueError('Métadonnées de chasse invalides')
        return {key:self.meta(key) for key in keys}

    def indicators(self):
        with self.lock:
            rows=[];size=0
            for row in self.db.execute('SELECT id,kind,value,raw,label,fields_count,rows_count,stored_count FROM indicators ORDER BY id'):
                if len(rows)>=MAX_IOCS:raise ValueError('Chasse limitée à 50000 IOC')
                size+=sum(len(str(value).encode('utf-8')) for value in row[1:5])
                if size>24*1024**2:raise ValueError('Liste IOC enregistrée trop volumineuse')
                normalized=indicator(row[3],row[1],row[4])
                if normalized.value!=row[2]:raise ValueError('IOC enregistré incohérent')
                rows.append(row)
            return rows

    def batch(self):
        rows=self.indicators()
        with self.lock:
            rejected=[];size=0
            for line,value,reason in self.db.execute('SELECT line,value,reason FROM rejections'):
                size+=len(value.encode('utf-8'))+len(reason.encode('utf-8'))
                if len(rejected)>=MAX_IOCS or size>24*1024**2:raise ValueError('Liste de rejets trop volumineuse')
                rejected.append(dict(line=line,value=value,reason=reason))
        return IndicatorBatch([Indicator(r[1],r[2],r[3],r[4]) for r in rows],rejected,
                              self.metadata.get('duplicates',0),self.metadata.get('origin',{}))

    def sources(self):
        with self.lock:
            result=[];size=0
            for row in self.db.execute('SELECT id,path,info,view,total,scanned,complete,error FROM sources ORDER BY id'):
                size+=len(row[2].encode('utf-8'))+len(row[3].encode('utf-8'))
                if len(result)>=1000 or size>16*1024**2:raise ValueError('Périmètre de chasse trop volumineux')
                result.append(dict(id=row[0],path=row[1],info=json.loads(row[2]),view=json.loads(row[3]),
                                   total=row[4],scanned=row[5],complete=bool(row[6]),error=row[7]))
            return result

    def page(self, offset=0, ioc=None, source=None):
        clauses=[];args=[]
        if ioc is not None:clauses.append('h.ioc=?');args.append(int(ioc))
        if source is not None:clauses.append('h.source=?');args.append(int(source))
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        with self.lock:
            count=self.db.execute('SELECT count(*) FROM hits h'+where,args).fetchone()[0]
            rows=self.db.execute('SELECT h.id,h.ioc,h.source,h.row_id,h.column_id,h.column_name,h.observed,h.snippet,h.source_time,h.rule,'
                                 'i.kind,i.value,i.raw,i.label,s.path,s.info FROM hits h '
                                 'JOIN indicators i ON i.id=h.ioc JOIN sources s ON s.id=h.source'+where+
                                 ' ORDER BY h.id LIMIT ? OFFSET ?',args+[self.PAGE_SIZE,max(0,int(offset))]).fetchall()
        return dict(count=count,rows=rows)

    def rebind(self,mapping):
        """Rebind only source references after package verification, never hits."""
        with self.lock:
            for source in self.sources():
                info=source['info'];info['path']=mapping.get(info['path'],info['path'])
                self.db.execute('UPDATE sources SET path=?,info=? WHERE id=?',
                                (mapping.get(source['path'],source['path']),json.dumps(info,ensure_ascii=False),source['id']))
            self.set_meta('portable_rebound',True);self.db.commit();self.metadata=self.all_meta()

    def export(self,target,summary=False):
        target=Path(target).resolve();sources=self.sources()
        protected=[self.path]+[s[key] for s in sources for key in ('path',)]+[s['info']['path'] for s in sources]
        origin=self.metadata.get('origin',{}).get('path')
        if origin:protected.append(origin)
        if target.is_relative_to(self.path.parent.parent) or protected_destination(target,protected):
            raise ValueError('L’export ne peut pas remplacer une chasse, une analyse ou sa source')
        partial=self.metadata.get('status')!='complete'
        truncated=self.metadata.get('truncated',False)
        scope=[self.metadata.get('respect_filters',False),self.metadata.get('include_subdomains',False),len(sources),sum(not s['complete'] for s in sources)]
        if summary:
            headers=['Type','IOC_original','IOC_normalisé','Libellé','Lignes_correspondantes','Champs_correspondants','Détails_conservés','État','Chasse_partielle','Détails_limités','Liste_normalisée_SHA256','Début_UTC','Filtres_appliqués','Sous_domaines','Analyses_du_périmètre','Analyses_incomplètes']
            def records():
                for row in self.indicators():
                    check_cancelled()
                    state='Retrouvé' if row[5] else ('Non retrouvé — périmètre incomplet' if partial else 'Non retrouvé dans le périmètre analysé')
                    yield [KINDS[row[1]],row[3],row[2],row[4],row[6],row[5],row[7],state,partial,truncated,self.metadata['list_sha256'],self.metadata['started'],*scope]
                for line,value,reason in self.db.execute('SELECT line,value,reason FROM rejections'):
                    yield ['Rejet',value,'','','','','',f'Ligne {line} : {reason}',partial,truncated,self.metadata['list_sha256'],self.metadata['started'],*scope]
        else:
            headers=['Type','IOC_original','IOC_normalisé','Libellé','Analyse','Source','SHA256_source_à_l_import','Ligne_source','Colonne','Valeur_observée','Extrait','Date_source','Méthode','Chasse_partielle','Détails_limités','Liste_normalisée_SHA256','Début_UTC','Filtres_appliqués','Sous_domaines','Analyses_du_périmètre','Analyses_incomplètes']
            def records():
                cursor=self.db.execute('SELECT i.kind,i.raw,i.value,i.label,s.path,s.info,h.row_id,h.column_name,h.observed,h.snippet,h.source_time,h.rule '
                                       'FROM hits h JOIN indicators i ON i.id=h.ioc JOIN sources s ON s.id=h.source ORDER BY h.id')
                while rows:=cursor.fetchmany(256):
                    check_cancelled()
                    for row in rows:
                        info=json.loads(row[5])
                        yield [KINDS[row[0]],*row[1:5],info['path'],info.get('sha256',''),*row[6:],partial,truncated,self.metadata['list_sha256'],self.metadata['started'],*scope]
        temporary=None
        try:
            with self.lock:
                with tempfile.NamedTemporaryFile(dir=target.parent,suffix='.partial',delete=False) as stream:temporary=Path(stream.name)
                iterator=iter(records())
                if target.suffix.lower()=='.xlsx':
                    from fireblade.core.spreadsheets import write_xlsx
                    class Cursor:
                        def fetchmany(self,count):return list(islice(iterator,count))
                    write_xlsx(temporary,headers,Cursor(),256,check_cancelled)
                else:
                    with temporary.open('w',encoding='utf-8-sig',newline='') as stream:
                        writer=csv.writer(stream);writer.writerow(headers)
                        for row in iterator:check_cancelled();writer.writerow(row)
                check_cancelled();os.replace(temporary,target)
            return str(target)
        finally:
            if temporary:temporary.unlink(missing_ok=True)


def hunt(reader,batch,root,*,name='Chasse IOC',include_subdomains=True,respect_filters=False,
         hit_limit=DEFAULT_HIT_LIMIT,time_columns=None,progress=lambda _:None):
    if not batch.indicators:raise ValueError('Aucun IOC valide à chasser')
    if len(batch.indicators)>MAX_IOCS or type(hit_limit) is not int or not 1<=hit_limit<=MAX_HIT_LIMIT:
        raise ValueError('Limite de chasse invalide')
    root=Path(root)
    if root.is_symlink():raise ValueError('Le dossier des chasses est un lien')
    root.mkdir(parents=True,exist_ok=True)
    folder=root/uuid.uuid4().hex;folder.mkdir()
    store=None
    try:
        store=HuntStore(folder/'results.sqlite',create=True)
        metadata=dict(name=str(name)[:120],started=datetime.now(timezone.utc).isoformat(),status='running',
                      list_sha256=batch.sha256,origin=batch.origin,duplicates=batch.duplicates,rejected=len(batch.rejected),
                      include_subdomains=bool(include_subdomains),respect_filters=bool(respect_filters),hit_limit=hit_limit)
        for key,value in metadata.items():store.set_meta(key,value)
        store.db.executemany('INSERT INTO indicators(id,kind,value,raw,label) VALUES(?,?,?,?,?)',
                             [(i,ioc.kind,ioc.value,ioc.raw,ioc.label) for i,ioc in enumerate(batch.indicators,1)])
        store.db.executemany('INSERT INTO rejections VALUES(?,?,?)',[(r['line'],r['value'],r['reason']) for r in batch.rejected])
        size=0
        for i,document in enumerate(reader.documents):
            info=json.dumps(document.source_info,ensure_ascii=False);view=(document.view if respect_filters else View()).to_json()
            size+=len(info.encode('utf-8'))+len(view.encode('utf-8'))
            if i>=1000 or size>16*1024**2:raise ValueError('Périmètre limité à 1000 analyses et 16 Mio de métadonnées')
            store.db.execute('INSERT INTO sources(id,path,info,view) VALUES(?,?,?,?)',(i,document.path,info,view))
        store.db.commit()  # A crash retains the input list, marked unfinished.
        store.db.execute('BEGIN')
        matcher=IndicatorMatcher(batch.indicators,include_subdomains)
        fields=[0]*(len(batch.indicators)+1);rows_found=fields.copy();stored=fields.copy()
        pending=[];stored_total=0;total_matches=0;errors=[];scanned_total=0
        def flush():
            if pending:
                try:store.db.executemany('INSERT INTO hits(ioc,source,row_id,column_id,column_name,observed,snippet,source_time,rule) VALUES(?,?,?,?,?,?,?,?,?)',pending)
                except sqlite3.Error as exc:raise HuntStorageError('Écriture des résultats impossible : '+str(exc)) from exc
                pending.clear()
        for source,document in enumerate(reader.documents):
            reader.check();scanned=0;total=0;error=''
            progress(f'Chasse IOC · analyse {source+1}/{len(reader.documents)} · '+Path(document.source_info['path']).name)
            try:
                with reader.open(document) as case:
                    view=document.view if respect_filters else View()
                    total=case.count(view);reader.check()
                    where,args=case.where(view)
                    time_column=(time_columns or {}).get(document.path,guess_time_column(case.headers,document.view.timestamp_columns))
                    if type(time_column) is not int or not 0<=time_column<len(case.headers):time_column=None
                    cursor=case.db.execute('SELECT * FROM events'+where,args)
                    while records:=cursor.fetchmany(32):
                        reader.check()
                        for record in records:
                            scanned+=1;scanned_total+=1;row_matches=set()
                            date=str(record[time_column+1] or '') if time_column is not None else ''
                            if len(date)>512:date=date[:512]+' [abrégée]'
                            for column,value in enumerate(record[1:]):
                                reader.check()
                                if value is None:continue
                                for number,observed,at,rule in matcher.matches(value):
                                    fields[number]+=1;total_matches+=1;row_matches.add(number)
                                    if stored_total<hit_limit:
                                        snippet=value[max(0,at-120):max(0,at-120)+600]
                                        if at>120:snippet='…'+snippet
                                        if max(0,at-120)+600<len(value):snippet+='…'
                                        pending.append((number,source,int(record[0]),column,case.headers[column],observed,snippet,date,rule))
                                        stored[number]+=1;stored_total+=1
                                        if len(pending)>=1024:flush();reader.check()
                            for number in row_matches:rows_found[number]+=1
                        if scanned%1024<32:progress(f'Chasse IOC · {scanned_total:,} lignes lues · {total_matches:,} champs correspondants · {stored_total:,} détails conservés')
            except OperationCancelled:raise
            except (HuntStorageError,MemoryError):raise
            except Exception as exc:
                error=str(exc);errors.append(dict(path=document.path,error=error))
            flush()
            store.db.execute('UPDATE sources SET total=?,scanned=?,complete=?,error=? WHERE id=?',(total,scanned,int(not error),error,source))
        reader.check();flush()
        store.db.executemany('UPDATE indicators SET fields_count=?,rows_count=?,stored_count=? WHERE id=?',
                             [(fields[i],rows_found[i],stored[i],i) for i in range(1,len(fields))])
        for key,value in dict(status='partial' if errors else 'complete',finished=datetime.now(timezone.utc).isoformat(),
                              scanned_rows=scanned_total,matching_fields=total_matches,stored_hits=stored_total,
                              truncated=total_matches>stored_total,errors=errors,matched_iocs=sum(n>0 for n in fields)).items():store.set_meta(key,value)
        reader.check();store.db.commit();store.metadata=store.all_meta()
        return store
    except BaseException:
        try:
            if store:store.close()  # Closing an uncommitted SQLite connection rolls it back.
        finally:shutil.rmtree(folder,ignore_errors=True)
        raise


def discover_hunts(root):
    root=Path(root)
    if not root.exists() or root.is_symlink():return [],[]
    results=[];errors=[]
    for folder in root.iterdir():
        if not folder.is_dir() or folder.is_symlink() or len(folder.name)!=32 or any(c not in '0123456789abcdef' for c in folder.name):continue
        try:
            store=HuntStore(folder/'results.sqlite')
            try:results.append(dict(path=str(store.path),**store.metadata))
            finally:store.close()
        except (ValueError,sqlite3.Error,OSError) as exc:errors.append(str(folder)+' : '+str(exc))
    return sorted(results,key=lambda r:r.get('started',''),reverse=True),errors


def batch_text(batch):
    stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(['type','value','label'])
    writer.writerows((ioc.kind,ioc.raw,ioc.label) for ioc in batch.indicators)
    return stream.getvalue()
