"""Offline CatScale reader. Inputs are data, including archived shell scripts.

Format reference: WithSecureLabs/LinuxCatScale, commit
0014f234a472f536d28664902daed90527ff5858 (Cat-Scale.sh).
No upstream code or collector is executed or bundled.
"""
import csv
from dataclasses import dataclass
import gzip
import io
from pathlib import Path, PurePosixPath
import re
import tarfile

from fireblade.core.errors import OperationCancelled, job_cancelled

FAMILIES = {
    'process_and_network': 'Processus et réseau', 'persistence': 'Persistance',
    'logs': 'Journaux et connexions', 'system_info': 'Système',
    'user_files': 'Utilisateurs', 'misc': 'Fichiers et chronologie',
    'docker': 'Conteneurs et virtualisation', 'podman': 'Conteneurs et virtualisation',
    'virsh': 'Conteneurs et virtualisation',
}
HEADERS = ['Hôte', 'Type', 'Lecture', 'Horodatage', 'Utilisateur', 'PID', 'PPID', 'Commande',
    'État', 'Protocole', 'Adresse locale', 'Port local', 'Adresse distante', 'Port distant',
    'Chemin', 'Cible', 'SHA1', 'SHA256', 'Clé', 'Valeur', 'Section', 'Planification',
    'Service', 'Chargement', 'Sous-état', 'Description', 'UID', 'GID', 'GECOS', 'Dossier personnel',
    'Shell', 'Inode', 'Liens', 'Dernier accès', 'Dernière modification', 'Changement métadonnées',
    'Création', 'Groupe', 'Permissions', 'Taille', 'Processus', 'Détail',
    'Famille', 'Collecte', 'Source', 'Ligne', 'Fin de ligne', 'Texte brut']
MAX_LINE = 1024*1024
MAX_MEMBER = 256*1024*1024
MAX_EXPANDED = 4*1024*1024*1024
MAX_MEMBERS = 100000
MAX_DEPTH = 3


def check_cancel():
    if job_cancelled():raise OperationCancelled()


def location(path):
    parts=PurePosixPath(str(path).replace('\\','/')).parts
    for index,part in enumerate(parts):
        if part.casefold() in FAMILIES:
            return FAMILIES[part.casefold()],parts[index+1:]
    return None,()


def recognized(path):
    name=Path(path).name.casefold()
    family,_=location(path)
    context=any(part.casefold() in ('catscale_out','fsecure-out','fsecure_out') for part in Path(path).parts)
    if family and not context:
        for parent in Path(path).parents:
            if parent.name.casefold() in FAMILIES:
                siblings={item.name.casefold() for item in parent.parent.iterdir() if item.is_dir()}
                context=len(siblings & set(FAMILIES))>=2
                break
    return bool((family and (context or re.search(r'-(?:\d{8}|\d{6})-\d{4}-',name))) or re.search(r'-(?:console-error-log|host-date-timezone)\.txt$',name) or
                (name.startswith(('catscale_', 'fsecure_','cat-scale_')) and name.endswith(('.tar.gz','.tgz','.tar'))))


def identity(path):
    # Filenames retain the collection hostname/date even after upstream extraction.
    for part in reversed(PurePosixPath(str(path).replace('\\','/')).parts):
        match=re.search(r'^(.*)-((?:\d{8}|\d{6})-\d{4})(?:-|\.|$)',part)
        if match:return re.sub(r'(?i)^(?:catscale_|fsecure_|cat-scale_)','',match[1]),match[2]
    return '', ''


def kind(path):
    name=PurePosixPath(str(path).replace('\\','/')).name.casefold()
    for token,label in [('processes-','processes'),('process-details','proc-status'),
        ('processhashes','hashes'),('hashes','hashes'),('module-sha1','hashes'),('binhashes','hashes'),
        ('exec-perm-files','hashes'),('ss-anepo','ss'),('netstat-','netstat'),
        ('lsof-','lsof'),('full-timeline','timeline'),('cron-tab-list','cron'),
        ('systemctl_service_status','services'),('systemctl_all','unit-files'),
        ('persistence-systemdlist','systemd'),('process-cmdline','head-blocks'),
        ('process-environment','head-blocks'),('pot-webshell-first-1000','head-blocks'),
        ('bash_history','history'),('bashhistory','history'),('zsh_history','history')]:
        if token in name:return label
    if name in ('passwd','shadow','group'):return name
    if 'links' in name:return 'links'
    if location(path)[0]=='Journaux et connexions':return 'logs'
    return 'text'


def endpoint(value):
    if ':' not in value:return value,''
    address,port=value.rsplit(':',1)
    return address.strip('[]'),port


def records(lines, path, warnings):
    """Yield physical line references and parsed fields; failed matches remain raw."""
    mode=kind(path);columns=None;section='';owner='';block=None;history_time=''
    def row(number,raw,fields=None,end=None):
        return dict(zip(('Ligne','Fin de ligne','Lecture','Texte brut'),
                        (str(number),str(end or number),'Structurée' if fields else 'Brute',raw)),**(fields or {}))
    for number,raw in lines:
        check_cancel()
        text=raw.strip();fields={}
        if mode=='proc-status':
            if text.startswith('Name:') and block:
                yield row(block[0],'\n'.join(block[1]),block[2],block[3]);block=None
            if block is None:block=[number,[],{},number,0]
            block[4]+=len(raw)
            if block[4]>MAX_LINE:raise ValueError('Bloc proc/status supérieur à 1 Mio')
            block[1].append(raw);block[3]=number
            if ':' in text:
                key,value=text.split(':',1);key={'Name':'Processus','Pid':'PID','PPid':'PPID','Uid':'UID','Gid':'GID','State':'État'}.get(key)
                if key:block[2][key]=value.strip()
            continue
        if mode=='head-blocks':
            match=re.fullmatch(r'==> (.*) <==',text)
            if match:section=match[1];fields={'Chemin':section}
            elif section:
                match=re.search(r'/proc/(\d+)/',section)
                fields={'Chemin':section,'PID':match[1] if match else '', 'Commande' if 'cmdline' in str(path) else 'Valeur':raw.replace('\0',' ␀ ')}
        elif mode in ('processes','lsof'):
            if columns is None and re.search(r'\bPID\b',text) and re.search(r'\b(?:CMD|COMMAND|ARGS|NAME)\b',text):
                columns=text.split();continue
            elif columns and text:
                values=text.split(None,len(columns)-1)
                if len(values)==len(columns):
                    mapping={'PID':'PID','PPID':'PPID','USER':'Utilisateur','UID':'Utilisateur','CMD':'Commande','COMMAND':'Commande','ARGS':'Commande','NAME':'Chemin','STAT':'État','S':'État','STIME':'Horodatage','START':'Horodatage','STARTED':'Horodatage','VSZ':'Taille'}
                    fields={mapping[key]:value for key,value in zip(columns,values) if key in mapping}
        elif mode=='ss':
            values=text.split()
            if text.startswith(('Netid','State')):columns=values;continue
            elif values:
                with_protocol=values[0].lower() in ('tcp','udp','u_str','u_dgr','raw','nl','p_raw','dccp','sctp')
                offset=1 if with_protocol else 0
                if len(values)>=offset+5 and values[offset+1].isdigit() and values[offset+2].isdigit():
                    local,lp=endpoint(values[offset+3]);remote,rp=endpoint(values[offset+4])
                    fields={'Protocole':values[0] if with_protocol else '', 'État':values[offset], 'Adresse locale':local,'Port local':lp,'Adresse distante':remote,'Port distant':rp,'Détail':' '.join(values[offset+5:])}
                    match=re.search(r'pid=(\d+)',text)
                    if match:fields['PID']=match[1]
        elif mode=='netstat':
            values=text.split()
            if len(values)>=5 and re.fullmatch(r'(?:tcp|udp|raw|sctp)[46]?',values[0]) and values[1].isdigit() and values[2].isdigit():
                local,lp=endpoint(values[3]);remote,rp=endpoint(values[4])
                fields={'Protocole':values[0],'Adresse locale':local,'Port local':lp,'Adresse distante':remote,'Port distant':rp,'Détail':' '.join(values[5:])}
                if len(values)>5 and re.fullmatch('[A-Z_]+',values[5]):fields['État']=values[5]
                match=re.search(r'\b(\d+)/([^\s]+)',text)
                if match:fields.update(PID=match[1],Processus=match[2])
        elif mode=='hashes':
            match=re.fullmatch(r'(\\?)([0-9a-fA-F]{40}|[0-9a-fA-F]{64}) [ *](.*)',text)
            if match:
                fields={'SHA1' if len(match[2])==40 else 'SHA256':match[2],'Chemin':match[3]}
                if match[1]:fields['Détail']='Chemin échappé par sha1sum/sha256sum'
        elif mode=='timeline':
            if text.startswith('Inode,'):continue
            else:
                first=raw.split(',',2)
                if len(first)==3:
                    tail=first[2].rsplit(',',8)
                    if len(tail)==9 and first[0].isdigit() and first[1].isdigit() and tail[-1].isdigit():
                        fields=dict(zip(['Inode','Liens','Chemin','Dernier accès','Dernière modification','Changement métadonnées','Création','Utilisateur','Groupe','Permissions','Taille'],first[:2]+tail))
        elif mode=='cron':
            if text=='ENDOFUSERCRON':owner='';fields={'Détail':'Fin de crontab'}
            elif re.fullmatch(r'[a-zA-Z_][\w.-]*\$?',text):owner=text;fields={'Utilisateur':owner,'Détail':'Début de crontab'}
            elif text and not text.startswith('#'):
                match=re.match(r'(@\w+|(?:\S+\s+){4}\S+)\s+(.+)',text)
                if match:fields={'Utilisateur':owner,'Planification':match[1],'Commande':match[2]}
        elif mode in ('services','unit-files'):
            values=text.lstrip('● ').split(None,4 if mode=='services' else 2)
            if values and re.search(r'\.(?:service|timer|socket|target|path|mount|automount|slice|scope|swap|device)$',values[0]):
                if mode=='services' and len(values)==5:fields=dict(zip(['Service','Chargement','État','Sous-état','Description'],values))
                elif mode=='unit-files' and len(values)>=2:fields={'Service':values[0],'État':values[1],'Détail':values[2] if len(values)>2 else ''}
        elif mode=='links':
            match=re.search(r'(/proc/\d+/.*?) -> (.*)$',text)
            if match:fields={'Chemin':match[1],'Cible':match[2],'PID':match[1].split('/')[2]}
        elif mode=='passwd' and len(text.split(':'))==7:
            values=text.split(':');fields=dict(zip(['Utilisateur','Détail','UID','GID','GECOS','Dossier personnel','Shell'],values))
        elif mode=='group' and len(text.split(':'))==4:
            values=text.split(':');fields=dict(zip(['Groupe','Détail','GID','Utilisateur'],values))
        elif mode=='history':
            if re.fullmatch(r'#\d{9,}',text):history_time=text[1:];fields={'Horodatage':history_time}
            elif text:fields={'Commande':raw,'Horodatage':history_time}
        elif mode=='logs':
            match=re.match(r'(?P<date>\w{3}\s+\d{1,2}\s+\d\d:\d\d:\d\d|\d{4}-\d\d-\d\dT\S+)\s+(?P<host>\S+)\s+(?P<proc>[^\s:\[]+)(?:\[(?P<pid>\d+)\])?:\s?(?P<msg>.*)',text)
            if match:fields={'Horodatage':match['date'],'Processus':match['proc'],'PID':match['pid'] or '', 'Détail':match['msg'], 'Hôte':match['host']}
            elif text.startswith('type=') and 'msg=audit(' in text:
                fields={'Détail':text}
                for key,target in [('pid','PID'),('ppid','PPID'),('uid','UID'),('exe','Chemin'),('comm','Processus')]:
                    match=re.search(r'\b'+key+r'=("[^"]*"|\S+)',text)
                    if match:fields[target]=match[1].strip('"')
                match=re.search(r'msg=audit\(([^:]+):',text)
                if match:fields['Horodatage']=match[1]
        if not fields and mode in ('text','systemd'):
            if re.fullmatch(r'\[[^\]]+\]',text):section=text[1:-1];fields={'Section':section}
            elif not text.startswith(('#',';')):
                match=re.match(r'([\w. /()-]+?)\s*[:=]\s*(.*)',text)
                if match:fields={'Clé':match[1].strip(),'Valeur':match[2],'Section':section}
        yield row(number,raw,fields)
    if block:yield row(block[0],'\n'.join(block[1]),block[2],block[3])


@dataclass
class Budget:
    expanded:int=0
    members:int=0

    def consume(self,size):
        self.expanded+=size
        if self.expanded>MAX_EXPANDED:raise ValueError('CatScale : limite de données décompressées atteinte (4 Gio)')


def numbered_lines(stream,budget):
    number=0
    while True:
        check_cancel()
        raw=stream.readline(MAX_LINE+1)
        if not raw:break
        budget.consume(len(raw));number+=1
        if len(raw)>MAX_LINE:raise ValueError('CatScale : ligne supérieure à 1 Mio')
        # Surrogate escapes are rendered explicitly; invalid bytes are never silently discarded.
        text=raw.decode('utf-8-sig' if number==1 else 'utf-8',errors='backslashreplace').rstrip('\r\n')
        yield number,text


def safe_member(name):
    normalized=name.replace('\\','/')
    parts=PurePosixPath(normalized).parts
    return bool(parts) and not normalized.startswith('/') and not any(p=='..' or ':' in p for p in parts)


def parse(source,output):
    """Write one CSV per family, return outputs and a complete input disposition list.

    Archives are streamed through extractfile only; paths are never materialized.
    Binaries, links, unsupported archives and size limits are reported explicitly.
    """
    csv.field_size_limit(2**31-1)
    source,output=Path(source),Path(output)
    outputs={};writers={};used={};handles=[];members=[];warnings=[];budget=Budget()
    host,collection=identity(source)
    totals={'structured':0,'raw':0}

    def read(stream,path,fallback=None,depth=0):
        nonlocal host,collection
        check_cancel();budget.members+=1
        if budget.members>MAX_MEMBERS:raise ValueError('CatScale : limite de 100000 fichiers atteinte')
        family,_=location(path);family=family or fallback or 'Collecte CatScale'
        entry=dict(path=path,status='pending');members.append(entry)
        name=path.casefold()
        found_host,found_collection=identity(path)
        record_host,record_collection=found_host or host,found_collection or collection
        try:
            if name.endswith(('.tar.gz','.tgz','.tar')):
                if depth>=MAX_DEPTH:raise ValueError('Limite de profondeur des archives atteinte')
                # Count decompressed tar bytes, including skipped large/special members.
                compressed=name.endswith(('.tar.gz','.tgz'))
                payload=gzip.GzipFile(fileobj=stream) if compressed else stream
                class Counted:
                    def read(self,size=-1):
                        check_cancel()
                        data=payload.read(size)
                        budget.consume(len(data))
                        return data
                with tarfile.open(fileobj=Counted(),mode='r|') as archive:
                    for ordinal,item in enumerate(archive,1):
                        check_cancel();budget.members+=1
                        if budget.members>MAX_MEMBERS:raise ValueError('CatScale : limite de 100000 fichiers atteinte')
                        member_path=path+f'[entry {ordinal}]!/'+item.name
                        if item.isdir():continue
                        if not safe_member(item.name) or not item.isfile() or item.issparse():
                            members.append(dict(path=member_path,status='skipped',reason='Chemin non sûr, lien ou fichier spécial'));continue
                        if item.size>MAX_MEMBER:
                            members.append(dict(path=member_path,status='skipped',reason='Fichier archivé supérieur à 256 Mio'));continue
                        with archive.extractfile(item) as incoming:read(incoming,member_path,family,depth+1)
                entry['status']='archive'
                return
            if name.endswith('.gz'):
                if depth>=MAX_DEPTH:raise ValueError('Limite de profondeur des archives atteinte')
                with gzip.GzipFile(fileobj=stream) as incoming:read(incoming,path+'!/'+PurePosixPath(path.replace('\\','/')).name[:-3],family,depth+1)
                entry['status']='archive';return
            # Peek without assuming seek support on streamed tar members.
            prefix=stream.read(4096)
            if b'\0' in prefix and kind(path) not in ('head-blocks',):
                budget.consume(len(prefix))
                entry.update(status='unsupported',reason='Fichier binaire : conservé dans la source');return
            class Prefixed:
                def __init__(self):self.prefix=io.BytesIO(prefix)
                def readline(self,limit):
                    first=self.prefix.readline(limit)
                    if first.endswith(b'\n') or len(first)==limit:return first
                    return first+stream.readline(limit-len(first))
            total=raw_count=0
            for row in records(numbered_lines(Prefixed(),budget),path,warnings):
                if family not in writers:
                    target=output/('CatScale — '+family+'.csv')
                    handle=target.open('x',encoding='utf-8',newline='');handles.append(handle)
                    writer=csv.DictWriter(handle,HEADERS);writer.writeheader();writers[family]=writer
                    outputs[family]=dict(csv=str(target),family=family,rows=0);used[family]=set()
                row.update({'Hôte':record_host or row.get('Hôte',''),'Collecte':record_collection,'Famille':family,'Type':kind(path),'Source':path})
                writers[family].writerow(row);outputs[family]['rows']+=1;total+=1
                totals['raw' if row['Lecture']=='Brute' else 'structured']+=1
                entry.update(rows=total,raw_rows=raw_count+(row['Lecture']=='Brute'))
                used[family].update(key for key,value in row.items() if value)
                raw_count+=row['Lecture']=='Brute'
            entry.update(status='complete' if total else 'empty',rows=total,raw_rows=raw_count)
        except OperationCancelled:raise
        except (OSError,ValueError,tarfile.TarError,EOFError) as exc:
            entry.update(status='error',reason=str(exc));warnings.append(path+' : '+str(exc))
            if budget.expanded>MAX_EXPANDED or budget.members>MAX_MEMBERS:raise
    try:
        with source.open('rb') as stream:read(stream,str(source))
    finally:
        for handle in handles:handle.close()
    # Remove entirely empty fields using a disk-backed second pass, so each
    # family's grid shows relevant columns without loading the CSV into memory.
    for family,item in outputs.items():
        target=Path(item['csv']);compact=target.with_suffix('.compact')
        columns=[header for header in HEADERS if header in used[family]]
        with target.open(encoding='utf-8',newline='') as incoming,compact.open('x',encoding='utf-8',newline='') as outgoing:
            reader=csv.DictReader(incoming);writer=csv.DictWriter(outgoing,columns,extrasaction='ignore');writer.writeheader()
            for row in reader:check_cancel();writer.writerow(row)
        compact.replace(target)
    if totals['raw']:warnings.append(str(totals['raw'])+' ligne(s) conservée(s) en lecture brute (colonne Lecture)')
    skipped=sum(entry['status'] in ('skipped','unsupported','error') for entry in members)
    if skipped:warnings.append(str(skipped)+' entrée(s) non parsée(s) ; consulter le détail CatScale')
    return dict(outputs=list(outputs.values()),members=members,warnings=warnings,**totals)
