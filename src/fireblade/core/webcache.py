"""Read-only ESE WebCache export. No live APIs, recovery writes or network access."""
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from fireblade.core.errors import OperationCancelled, job_cancelled

TIME_COLUMNS = {'CreationTime','ModifiedTime','AccessedTime','ExpiryTime','SyncTime',
                'PostCheckTime','LastAccessTime','LastScavengeTime','ExpirationTime'}
EPOCH = datetime(1601,1,1,tzinfo=timezone.utc)


def check_cancel():
    if job_cancelled():raise OperationCancelled()


def filetime(value):
    """Add a UTC interpretation without replacing the exact 100 ns integer."""
    if value is None or value in (0,-1,0xffffffffffffffff):return ''
    if not isinstance(value,int) or isinstance(value,bool) or value<0:raise ValueError('FILETIME invalide')
    seconds,ticks=divmod(value,10000000)
    moment=EPOCH+timedelta(seconds=seconds)
    return moment.strftime('%Y-%m-%dT%H:%M:%S')+'.'+f'{ticks:07d}'+'Z'


def cell(value):
    if value is None:return ''
    if isinstance(value,(bytes,bytearray,memoryview)):return 'hex:'+bytes(value).hex()
    if isinstance(value,datetime):return value.isoformat()
    if isinstance(value,(list,tuple,dict)):
        return json.dumps(value,ensure_ascii=False,default=lambda item:cell(item),separators=(',',':'))
    return str(value)


def parse(source,output,progress=lambda _:None):
    from dissect.esedb import EseDB
    source,output=Path(source),Path(output)
    warnings=[];tables=[];outputs=[];warning_count=0
    def warn(message):
        nonlocal warning_count
        warning_count+=1
        if len(warnings)<100:warnings.append(message)
    with source.open('rb') as stream:
        db=EseDB(stream)
        by_name={table.name:table for table in db.tables()}
        if 'Containers' not in by_name or not any(name.startswith('Container_') for name in by_name):
            raise ValueError('Base ESE sans schéma WebCache Containers/Container_*')
        state=int(db.header.dbstate)
        if state!=3:warn(f'Base ESE non fermée proprement (état {state}) : lecture des pages disponibles, sans rejeu des journaux ni récupération des enregistrements supprimés.')
        containers={}
        try:
            for record in by_name['Containers'].records():
                check_cancel()
                try:containers[str(record.get('ContainerId'))]=(cell(record.get('Name')),cell(record.get('Directory')))
                except Exception as exc:warn('Métadonnées de conteneur illisibles : '+str(exc))
        except OperationCancelled:raise
        except Exception as exc:warn('Table Containers partiellement lisible : '+str(exc))
        for index,table in enumerate(sorted(by_name.values(),key=lambda table:(not table.name.startswith('Container_'),table.name))):
            check_cancel()
            if table.name.startswith('MSys'):continue
            progress('WebCache : '+table.name)
            entry=dict(table=table.name,status='running',rows=0);tables.append(entry)
            target=output/f'WebCache-{index:04d}.csv'
            columns=[column.name for column in table.columns]
            used={column.casefold() for column in columns}
            def unique(name):
                base=name;number=2
                while name.casefold() in used:name=base+'_'+str(number);number+=1
                used.add(name.casefold());return name
            metadata=[unique(name) for name in ('WebCache_Table','WebCache_Container','WebCache_Directory','WebCache_RecordType','WebCache_RecordNumber','WebCache_ReadError')]
            conversions=[(name,unique(name+'_UTC')) for name in columns if name in TIME_COLUMNS]
            try:
                with target.open('x',encoding='utf-8',newline='') as outgoing:
                    writer=csv.writer(outgoing)
                    original_headers=metadata+columns+[label for _,label in conversions]
                    leading=['Url','Filename','AccessedTime_UTC','CreationTime_UTC','ModifiedTime_UTC',metadata[0],metadata[1]]
                    headers=leading+[name for name in original_headers if name not in leading]
                    writer.writerow(headers)
                    for number,record in enumerate(table.records(),1):
                        check_cancel();values={};errors=[]
                        for column in columns:
                            try:values[column]=record.get(column)
                            except Exception as exc:errors.append(column+' : '+str(exc))
                        container_id=cell(values.get('ContainerId')) or (table.name.split('_',1)[1] if table.name.startswith('Container_') else '')
                        name,directory=containers.get(container_id,('',''))
                        dates=[]
                        for column,_ in conversions:
                            try:dates.append(filetime(values.get(column)))
                            except (ValueError,OverflowError):dates.append('');errors.append(column+' : FILETIME hors plage')
                        if errors:warn(table.name+f' ligne {number} : '+' ; '.join(errors))
                        category=('CacheEntry' if table.name.startswith('Container_') else
                                  'AppCacheEntry' if table.name.startswith('AppCacheEntry_') else
                                  'DependencyEntry' if table.name.startswith('DependencyEntry_') else
                                  'Metadata' if table.name in ('Containers','Partitions') or table.name.startswith('AppCache_') else 'TableRecord')
                        row=dict(zip(original_headers,[table.name,name,directory,category,number,' ; '.join(errors)]+[cell(values.get(column)) for column in columns]+dates))
                        writer.writerow([row.get(column,'') for column in headers])
                        entry['rows']+=1
                entry['status']='complete'
            except OperationCancelled:raise
            except Exception as exc:
                entry.update(status='error',error=str(exc));warn(table.name+' : '+str(exc))
            if entry['rows']:outputs.append(dict(csv=str(target),table=table.name,rows=entry['rows']))
    if warning_count>len(warnings):warnings.append(f'{warning_count-len(warnings)} avertissement(s) supplémentaire(s) non détaillé(s).')
    return dict(outputs=outputs,tables=tables,warnings=warnings,warning_count=warning_count,database_state=state,
                rows=sum(entry['rows'] for entry in tables))
