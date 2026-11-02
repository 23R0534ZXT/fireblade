"""Evidence-backed links between Hayabusa alerts and imported EVTX events."""
from datetime import datetime, timedelta, timezone
import csv
import heapq
import json
import os
from pathlib import Path
import re
import uuid

from fireblade.core.engine import Case
from fireblade.core.models import Filter, FormatRule, View
from fireblade.core.collection_organization import column_keys


def path_key(value):
    return os.path.normcase(os.path.normpath(str(value)))


def sources(report):
    documents = {d['path']:d for d in report.get('raw_documents', report['documents'])}
    result = []
    seen = set()
    for entry in report['files']:
        for run in entry.get('runs', []):
            if run['tool'] != 'EvtxECmd':continue
            for output in run.get('outputs', []):
                path = output.get('analysis')
                if path in documents and path not in seen:
                    seen.add(path)
                    result.append((documents[path], entry['path']))
    return result


def parts(value):
    return [part.strip() for part in str(value or '').split(' ¦ ') if part.strip() and part.strip() != '-']


def instant(value):
    try:
        stamp = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
        return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def build_context(collection, alert, alert_analysis, alert_row, minutes=5, max_events=1000, register=True):
    from fireblade.core.collection import check_cancel
    if type(minutes) is not int or not 1 <= minutes <= 1440:
        raise ValueError('Fenêtre de contexte : 1 à 1440 minutes')
    if type(max_events) is not int or not 1 <= max_events <= 1000:
        raise ValueError('Contexte limité à 1000 événements')
    if register and len(collection.report['documents'])>=1000:
        raise ValueError('Limite de 1000 analyses atteinte ; fermez des analyses avant de conserver un contexte')
    source_value = alert.get('Fireblade_EVTX_Source', '')
    try:
        paths = json.loads(source_value) if source_value.startswith('[') else [source_value]
    except (ValueError, AttributeError):
        raise ValueError('Référence EVTX de l’alerte invalide')
    if not isinstance(paths, list) or not paths or not all(isinstance(p,str) and p for p in paths):
        raise ValueError('Référence EVTX de l’alerte absente')
    referenced = {path_key(p) for p in paths}
    record_parts=parts(alert.get('RecordID'))
    records = [int(v) for v in record_parts if re.fullmatch(r'\d{1,20}', v)]
    machines = parts(alert.get('Computer'))
    event_ids = [int(v) for v in parts(alert.get('EventID')) if re.fullmatch(r'\d{1,10}',v)]
    notes = []
    if len(records)!=len(record_parts):notes.append('Certains identifiants de l’alerte ne sont pas exploitables.')
    references_truncated=len(records)>1000
    if len(records)>1000:
        notes.append('Références de l’alerte limitées aux 1000 premiers identifiants.')
        records=records[:1000]
    if len(machines)>1000 or len(event_ids)>1000:
        raise ValueError('Alerte agrégée trop volumineuse pour ce contexte')
    ambiguous = len(paths)>1 or len(record_parts)>1
    expected = sources(collection.report)
    if not expected:
        raise ValueError('Aucune analyse EvtxECmd disponible pour relier cette alerte')
    anchors = {}
    derived_machines = []
    stamp = instant(parts(alert.get('Timestamp'))[0]) if parts(alert.get('Timestamp')) else None
    total_candidates = 0

    def open_source(document):
        case = Case(document['path'], settings=collection.settings, read_only=True)
        with collection._case_lock:collection._active_case=case
        try:
            if case.info != document['source']:
                raise ValueError('Analyse remplacée depuis la collecte')
            columns = {name.casefold():i for i,name in enumerate(case.headers)}
            def find(*names):
                return next((columns[n.casefold()] for n in names if n.casefold() in columns),None)
            return case, dict(record=find('EventRecordId','RecordID'), time=find('TimeCreated','Timestamp'),
                              machine=find('Computer'), event=find('EventId','EventID'))
        except BaseException:
            close_source(case)
            raise

    def close_source(case):
        with collection._case_lock:
            collection._active_case=None
            case.close()

    def take(case, columns, row, source, anchor=False):
        values=tuple(row[1:])
        time_value=values[columns['time']] if columns['time'] is not None else None
        return dict(analysis=str(case.path), row=int(row[0]), headers=tuple(case.headers), values=values,
                    source=source, time=instant(time_value), time_text=time_value, anchor=anchor)

    # Match the file and EventRecordID first. Record numbers alone are not globally unique.
    for document, source in expected:
        check_cancel()
        if path_key(source) not in referenced:continue
        case=None
        try:
            case, columns=open_source(document)
            if columns['record'] is None or not records:continue
            where=['TRY_CAST('+case.column(columns['record'])+' AS HUGEINT) IN ('+','.join('?' for _ in records)+')']
            args=list(records)
            if machines and columns['machine'] is not None:
                where.append('lower('+case.column(columns['machine'])+') IN ('+','.join('lower(?)' for _ in machines)+')')
                args+=machines
            if event_ids and columns['event'] is not None:
                where.append('TRY_CAST('+case.column(columns['event'])+' AS BIGINT) IN ('+','.join('?' for _ in event_ids)+')')
                args+=event_ids
            query='SELECT __row_id,'+','.join(case.column(i) for i in range(len(case.headers)))+' FROM events WHERE '+' AND '.join(where)+' ORDER BY __row_id LIMIT ?'
            with case.operation():
                rows=case.db.execute(query,args+[max_events+1]).fetchall()
            total_candidates+=len(rows)
            for row in rows[:max_events-len(anchors)]:
                item=take(case,columns,row,source,True)
                anchors[(item['analysis'],item['row'])]=item
                if stamp is None and item['time'] is not None:stamp=item['time']
                if columns['machine'] is not None:
                    value=item['values'][columns['machine']]
                    if value and value not in derived_machines:derived_machines.append(value)
        except Exception as exc:
            from fireblade.core.errors import OperationCancelled
            if isinstance(exc,OperationCancelled):raise
            notes.append('Source non reliée : '+source+' — '+str(exc))
        finally:
            if case is not None:close_source(case)
    if not machines:machines=derived_machines
    if not anchors:notes.append('Événement référencé non retrouvé : aucune ligne n’est présentée comme une correspondance certaine.')
    if total_candidates>len(anchors):notes.append('Références limitées par la taille maximale du contexte.')
    if total_candidates>1:ambiguous=True
    if ambiguous and anchors:notes.append('Alerte agrégée ou références multiples : les identifiants donnent des candidats, pas une association individuelle certaine.')
    if stamp is None:notes.append('Horodatage absent ou invalide : voisinage temporel indisponible.')
    if not machines:notes.append('Machine inconnue : voisinage temporel désactivé pour éviter de mélanger des machines.')

    # Keep only the closest neighbors in memory; source queries remain disk-backed.
    heap=[]
    serial=0
    neighbor_candidates=0
    capacity=max_events-len(anchors)
    if stamp is not None and machines:
        try:start=stamp-timedelta(minutes=minutes)
        except OverflowError:start=datetime.min.replace(tzinfo=timezone.utc)
        try:end=stamp+timedelta(minutes=minutes)
        except OverflowError:end=datetime.max.replace(tzinfo=timezone.utc)
        for document, source in expected:
            check_cancel()
            case=None
            try:
                case, columns=open_source(document)
                if columns['time'] is None or columns['machine'] is None:
                    notes.append('Voisinage indisponible pour '+source+' : date ou machine manquante.')
                    continue
                time_sql='TRY_CAST('+case.column(columns['time'])+' AS TIMESTAMPTZ)'
                where=time_sql+' BETWEEN ? AND ? AND lower('+case.column(columns['machine'])+') IN ('+','.join('lower(?)' for _ in machines)+')'
                args=[start,end]+machines
                with case.operation():
                    cursor=case.db.execute('SELECT __row_id,'+','.join(case.column(i) for i in range(len(case.headers)))+' FROM events WHERE '+where+' ORDER BY abs(epoch('+time_sql+')-?) LIMIT ?',args+[stamp.timestamp(),max_events+1])
                    while rows:=cursor.fetchmany(128):
                        check_cancel()
                        for row in rows:
                            key=(str(case.path),int(row[0]))
                            if key in anchors:continue
                            neighbor_candidates+=1
                            if not capacity:continue
                            item=take(case,columns,row,source)
                            distance=abs((item['time']-stamp).total_seconds()) if item['time'] else float('inf')
                            serial+=1
                            candidate=(-distance,serial,item)
                            if len(heap)<capacity:heapq.heappush(heap,candidate)
                            elif candidate[0]>heap[0][0]:heapq.heapreplace(heap,candidate)
            except Exception as exc:
                from fireblade.core.errors import OperationCancelled
                if isinstance(exc,OperationCancelled):raise
                notes.append('Voisinage incomplet pour '+source+' — '+str(exc))
            finally:
                if case is not None:close_source(case)
    events=list(anchors.values())+[item for _,_,item in heap]
    events.sort(key=lambda item:(item['time'] or datetime.min.replace(tzinfo=timezone.utc),item['source'],item['row']))
    truncated=references_truncated or neighbor_candidates>len(heap) or total_candidates>len(anchors)
    if truncated:notes.append('Contexte limité à '+str(max_events)+' événements ; les événements voisins les plus proches sont conservés. Les sources restent complètes.')
    folder=collection.output/'results'/('contexte-'+uuid.uuid4().hex)
    folder.mkdir()
    target=folder/'Contexte EVTX.csv'
    metadata=['Relation à l’alerte','Fireblade_AlertRule','Fireblade_AlertRuleID','Fireblade_AlertRecordID','Fireblade_AlertLevel','Fireblade_EVTX_Source','Fireblade_Analysis','Fireblade_Row']
    used={name.casefold() for name in metadata}
    union=[];positions={};labels=[]
    for event in events:
        for key in column_keys(event['headers']):
            if key in positions:continue
            label=key[0];number=2
            while label.casefold() in used:
                label=key[0]+' ('+str(number)+')';number+=1
            used.add(label.casefold());positions[key]=len(union);union.append(key);labels.append(label)
    priority={'timecreated':0,'timestamp':1,'eventid':2,'computer':3,'channel':4,'mapdescription':5,'username':6,'eventrecordid':7}
    order=sorted(range(len(labels)),key=lambda i:(priority.get(labels[i].casefold(),100),i))
    display_labels=[labels[i] for i in order]
    with target.open('x',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow([metadata[0]]+display_labels+metadata[1:])
        for event in events:
            check_cancel()
            values=[None]*len(union)
            for key,value in zip(column_keys(event['headers']),event['values']):values[positions[key]]=value
            role=('Référence candidate (agrégation)' if ambiguous else 'Événement de l’alerte') if event['anchor'] else 'Proximité temporelle'
            writer.writerow([role]+[values[i] for i in order]+[alert.get('RuleTitle',''),alert.get('RuleID',''),alert.get('RecordID',''),alert.get('Level',''),event['source'],event['analysis'],event['row']])
    view=View(pinned_columns=[0],pinned_widths={'0':220})
    time_index=next((i for i,name in enumerate(display_labels) if name.casefold() in ('timecreated','timestamp')),None)
    if time_index is not None:view.sort_column=1+time_index;view.sort_type='timestamp';view.timestamp_columns=[1+time_index]
    view.format_rules=[FormatRule(Filter(0,'eq','Événement de l’alerte'),bold=True,use_background=False,use_foreground=False)]
    document=collection.import_result(target,'context',view=view,register=False)
    result=dict(analysis=document['path'],alert_analysis=alert_analysis,alert_row=int(alert_row),
                rule=alert.get('RuleTitle',''),level=alert.get('Level',''),minutes=minutes,
                references=len(anchors),events=len(events),truncated=truncated,notes=notes,
                association=('candidate' if ambiguous else 'exact') if anchors else 'unresolved',
                machines=machines, timestamp=stamp.isoformat() if stamp else None)
    result['_document']=document
    if register:
        return retain_context(collection,result)
    return result


def retain_context(collection, result):
    """Publish an inspected preview in the collection/session only on request."""
    if any(item['path']==result['analysis'] for item in collection.report['documents']):
        return {k:v for k,v in result.items() if k!='_document'}
    document=result['_document']
    if len(collection.report['documents'])>=1000:
        raise ValueError('Limite de 1000 analyses atteinte ; contexte CSV conservé sur disque')
    metadata={k:v for k,v in result.items() if k!='_document'}
    collection.report['documents'].append(document)
    collection.report.setdefault('contexts',[]).append(metadata)
    collection.save()
    return metadata


def discard_preview(collection, result):
    """Remove only unregistered files created by the preview builder."""
    if not result or '_document' not in result:return
    if any(item['path']==result['analysis'] for item in collection.report['documents']):return
    database=Path(result['analysis'])
    source=Path(result['_document']['source']['path'])
    if database.parent!=collection.output/'analyses' or source.parent.parent!=collection.output/'results' or not source.parent.name.startswith('contexte-'):
        raise ValueError('Emplacement du contexte temporaire invalide')
    database.unlink(missing_ok=True)
    source.unlink(missing_ok=True)
    source.parent.rmdir()
