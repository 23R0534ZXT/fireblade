"""Build and verify a portable forensic demonstration ZIP; no user evidence."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request
import zipfile

TAG='test-pack-v1'
ROOT='Fireblade-Test-Pack-v1'
ARCHIVE=ROOT+'.zip'
APP_COMMIT='0c36f0d95e47015302983fa8966ef5f2023ff94d'
APP_SHA256='8ecbf0f816a951536eba49d7b771a42f1d45bed91899d5d3381adad5077d3bac'
DOWNLOAD='https://github.com/23R0534ZXT/fireblade/releases/download/'+TAG+'/'+ARCHIVE
ROWS=[['EVTX','alice','PC01','4624','2026-11-02T10:00:00Z','2048','Connexion réussie','000001'],
      ['EVTX','bob','PC02','4625','2026-11-02T10:01:00Z','512','Échec de connexion','000002'],
      ['Amcache','alice','PC01','','2026-11-02T10:02:00Z','4096','Programme de démonstration','9007199254740993'],
      ['MFT','charlie','PC03','','2026-11-02T10:03:00Z','18446744073709551615','Chemin avec virgule, accent et\nplusieurs lignes','000004'],
      ['EVTX','alice','PC02','4688','2026-11-02T10:04:00Z','128','Processus observé','000005'],
      ['MFT','bob','PC01','','2026-11-02T10:05:00Z','0','','000006']]
HEADERS=['Artifact','User','Computer','EventID','Time','Size','Message','Identifier']


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def fetch(url,expected=None):
    with urllib.request.urlopen(url,timeout=90) as response:data=response.read(256*1024*1024+1)
    if len(data)>256*1024*1024:raise ValueError('Download exceeds fixture limit')
    if expected and hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Fixture SHA-256 mismatch: '+url)
    return data


def tar_directory(source,target):
    # The collector directory is the archive root, just like the real collector.
    with target.open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for path in sorted(source.rglob('*')):
                if not path.is_file():continue
                info=tarfile.TarInfo('catscale_out/'+path.relative_to(source).as_posix())
                info.size=path.stat().st_size;info.mtime=0;info.mode=0o644
                with path.open('rb') as incoming:archive.addfile(info,incoming)


def write_catscale(destination):
    from fireblade.validation.catscale import write_corpus
    write_corpus(destination)
    files={
        'Process_and_Network/node-20261102-1000-process-details.txt':b'Name:\tsshd\nPid:\t42\nPPid:\t1\nUid:\t0\t0\t0\t0\n',
        'Process_and_Network/node-20261102-1000-processhashes.txt':('a'*40+'  /proc/42/exe\n').encode(),
        'Process_and_Network/node-20261102-1000-process-exe-links.txt':b'lrwxrwxrwx 1 root root 0 Nov 2 10:00 /proc/42/exe -> /usr/sbin/sshd\n',
        'Process_and_Network/node-20261102-1000-process-cmdline.txt':b'==> /proc/42/cmdline <==\n/usr/sbin/sshd\x00-D\x00\n',
        'Process_and_Network/node-20261102-1000-netstat-antup.txt':b'tcp6 0 0 :::22 :::* LISTEN 42/sshd\n',
        'User_Files/home/alice/passwd':b'alice:x:1000:1000:Alice:/home/alice:/bin/bash\n',
        'System_Info/node-20261102-1000-meminfo.txt':b'MemTotal: 8388608 kB\nMemFree: 4194304 kB\n',
        'Logs/audit/audit.log':b'type=SYSCALL msg=audit(1793613600.123:42): pid=42 ppid=1 uid=1000 exe="/usr/bin/id"\n',
        'System_Info/node-20261102-1000-unrecognized-output.txt':b'Unformatted demonstration output retained as raw text\n',
    }
    for relative,data in files.items():
        path=destination/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def write_volume(destination,rows):
    destination.parent.mkdir(parents=True,exist_ok=True)
    raw=destination.with_suffix('.csv')
    with raw.open('w',encoding='utf-8',newline='') as stream:
        stream.write('Inode,Hard link Count,Full Path,Last Access,Last Modification,Last Status Change,File Creation,User,Group,File Permissions,File Size(bytes)\n')
        for index in range(rows):
            owner='alice' if index%2 else 'bob'
            stream.write(f'{index:020d},1,/tmp/café,{index}.txt,2026-11-02 10:00:00 +0000,2026-11-02 10:01:00 +0000,2026-11-02 10:02:00 +0000,-,{owner},users,-rw-r--r--,18446744073709551615\n')
    with destination.open('wb') as file,gzip.GzipFile(filename='',fileobj=file,mode='wb',mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            info=tarfile.TarInfo('catscale_out/Misc/volume-20261102-1000-full-timeline.csv');info.size=raw.stat().st_size;info.mode=0o644
            with raw.open('rb') as incoming:archive.addfile(info,incoming)
    raw.unlink()


def write_exports(destination):
    from openpyxl import Workbook
    destination.mkdir()
    for suffix,delimiter in [('csv',','),('tsv','\t')]:
        with (destination/('activite.'+suffix)).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream,delimiter=delimiter);writer.writerow(HEADERS);writer.writerows(ROWS)
    workbook=Workbook();sheet=workbook.active;sheet.title='Activite'
    for row in [HEADERS]+ROWS:
        sheet.append(row)
        for cell in sheet[sheet.max_row]:cell.data_type='s'
    workbook.save(destination/'activite.xlsx')


def write_guide(root,expected,volume_rows):
    family='\n'.join('- '+name+' : '+str(count)+' ligne(s).' for name,count in expected['catscale']['families'].items())
    (root/'LIRE-MOI.md').write_text(f'''# Pack de test Fireblade v1

1. Téléchargez Fireblade.exe depuis les releases du projet. Version qualifiée : commit `{APP_COMMIT}`.
2. Extrayez ce ZIP entièrement avec l’Explorateur Windows.
3. Lancez Fireblade, créez un case et utilisez **Importer un dossier de collecte…** pour les artefacts bruts.
4. Sélectionnez les sous-dossiers indiqués ci-dessous. Pour les exports, utilisez **Ouvrir un fichier**.

## 1 — Windows : tous les moteurs

Importez `01-Windows/01-Collecte-principale`. Choisissez un onglet par artefact.
Cette collecte couvre les 13 EZ Tools : EVTX, Amcache, AppCompatCache et registre, Prefetch, MFT,
LNK, Jump Lists, SRUM, Windows Timeline, corbeille, RecentFileCache et SQLite.
Gardez SYSTEM.LOG1 et SYSTEM.LOG2 à côté de SYSTEM.

Dans Collecte et détection, lancez **Analyser avec Hayabusa**, gravité minimale Faible.
Attendu : 13 événements EVTX et au moins deux alertes de démonstration : effacement d’un journal
et modification du démarrage du service Event Log. Ouvrez leur contexte, puis l’événement EVTX source.
Les artefacts Windows proviennent de plusieurs sources publiques indépendantes.

Importez ensuite `01-Windows/02-Shellbags` dans le même case.
Attendu : 523 Shellbags. La ruche publique est sale et ses journaux ne sont pas disponibles :
un avertissement du lecteur Shellbags et le refus du passage registre RECmd sont attendus.
Les chemins lisibles et les données brutes restent consultables. Cela ne constitue pas une récupération complète.

Importez `01-Windows/03-WebCache`.
Attendu : 1 612 lignes, métadonnées comprises. Filtrez `WebCache_Container` sur `History`,
ou `Url` sur `code.google.com/p/libyal`. Comparez les FILETIME bruts et leurs colonnes UTC.

## 2 — Linux CatScale

Ce jeu est **synthétique**, construit selon les formats du collecteur CatScale. Il contient
uniquement des données de démonstration ; les commandes inscrites dans les logs sont des valeurs à explorer.
Créez un second case et importez **un seul** de ces dossiers :

- `02-Linux-CatScale/01-Dossier-extrait` : fichiers déjà extraits ;
- `02-Linux-CatScale/02-Archive` : mêmes données en archive CatScale.

Les deux doivent donner les mêmes {expected['catscale']['rows']} lignes dans sept familles :
{family}

Un avertissement de lecture brute est volontaire : filtrez la colonne Lecture sur Brute pour retrouver
la ligne non structurée de démonstration. La provenance garde source, entrée d’archive et numéros de ligne.
Hayabusa s’applique aux EVTX Windows.

Option volume : importez `02-Linux-CatScale/03-Volume`.
Attendu : **{volume_rows:,} lignes** de timeline, réparties entre alice et bob, avec des chemins accentués
contenant une virgule, des inodes à zéros initiaux et la taille exacte `18446744073709551615`.
Ce scénario est indépendant de la petite collecte ci-dessus.

## 3 — CSV, TSV et Excel

Ouvrez les trois fichiers de `03-Exports` séparément : six lignes par fichier.
Testez Contient sous chaque colonne, tri Nombre/Texte, groupes, conditions ET/OU/NON,
signets, notes et exports CSV/XLSX. Les identifiants `000001` et `9007199254740993` doivent rester exacts.
La cellule Message de charlie contient une virgule, des accents et un retour à la ligne.

## 4 — Cases et sessions

Enregistrez les cases et leurs sessions. Changez de case : chaque case doit retrouver ses propres
onglets, filtres, groupes et notes. Fermez puis relancez Fireblade : les cases doivent être visibles,
sans analyses chargées avant votre ouverture explicite. Testez aussi recherche, modification et archivage.

## Sources, intégrité et taille

`MANIFEST.json` contient les sources, tailles et SHA-256 des fichiers. Les licences et attributions
sont dans `NOTICES`. Les fichiers d’analyse et résultats restent en dehors de cette collecte source.
Le pack fournit des exemples représentatifs des moteurs, pas chaque variante possible d’artefact.
Le CSV de plus de 3 Gio est distribué séparément :
https://github.com/23R0534ZXT/fireblade/releases/tag/test-data-3gib
''',encoding='utf-8')


def verify_archive(archive):
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:raise ValueError('ZIP CRC mismatch')
        names=zipped.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP entries')
        manifest=json.loads(zipped.read(ROOT+'/MANIFEST.json'))
        expected={ROOT+'/MANIFEST.json'}
        for item in manifest['files']:
            relative=Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts or '\\' in item['path'] or ':' in item['path']:raise ValueError('Unsafe manifest path')
            name=ROOT+'/'+item['path'];expected.add(name)
            if zipped.getinfo(name).file_size!=item['bytes']:raise ValueError('Entry size mismatch')
            with zipped.open(name) as incoming:actual=hashlib.file_digest(incoming,'sha256').hexdigest()
            if actual!=item['sha256']:raise ValueError('Entry SHA-256 mismatch')
        if set(names)!=expected:raise ValueError('Unexpected ZIP entries')
    return manifest


def package(directory,project,volume_rows=250000,source_commit=None):
    from fireblade.core.catscale import parse
    project,directory=Path(project),Path(directory);directory.mkdir(parents=True)
    root=directory/ROOT;root.mkdir();records=[]
    def store(relative,data,origin):
        target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        records.append(dict(path=relative,origin=origin))
    fixtures=json.loads((project/'config/forensic-qa-fixtures.json').read_text())
    browsers=json.loads((project/'config/forensic-browser-qa-fixtures.json').read_text())
    lock=json.loads((project/'config/forensic-toolchain.json').read_text())
    for item in fixtures+browsers:
        data=fetch(item['url'])
        if item['compression']=='gzip':data=gzip.decompress(data)
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Pinned artifact mismatch: '+item['tool'])
        group='02-Shellbags' if item['tool']=='Shellbags' else '03-WebCache' if item['tool']=='WebCache' else '01-Collecte-principale/'+item['tool']
        relative='01-Windows/'+group+'/'+item['name']
        store(relative,data,dict(kind='public-artifact',tool=item['tool'],url=item['url'],sha256=item['sha256']))
    # Transaction logs must accompany their hive in the same directory.
    evtx=lock['evtx_fixture'];store('01-Windows/01-Collecte-principale/EvtxECmd/System.evtx',fetch(evtx['url'],evtx['sha256']),dict(kind='public-artifact',tool='EvtxECmd',**evtx))
    linux=root/'02-Linux-CatScale';extracted=linux/'01-Dossier-extrait'/'node-20261102-1000';write_catscale(extracted)
    (linux/'02-Archive').mkdir();tar_directory(extracted,linux/'02-Archive/catscale_node-20261102-1000.tar.gz')
    write_volume(linux/'03-Volume/catscale_volume-20261102-1000.tar.gz',volume_rows)
    write_exports(root/'03-Exports')
    scratch=directory/'catscale-expectations';scratch.mkdir();totals={};structured=raw=0
    for index,path in enumerate(sorted(extracted.rglob('*'))):
        if not path.is_file():continue
        output=scratch/str(index);output.mkdir();result=parse(path,output)
        for item in result['outputs']:totals[item['family']]=totals.get(item['family'],0)+item['rows']
        structured+=result['structured'];raw+=result['raw']
    expected=dict(catscale=dict(rows=structured+raw,structured=structured,raw=raw,families=totals),volume_rows=volume_rows,
                  exports_rows=6,shellbags=523,webcache_rows_including_metadata=1612,evtx_events=13,hayabusa_minimum_alerts=2)
    store('RESULTATS-ATTENDUS.json',(json.dumps(expected,ensure_ascii=False,indent=2)+'\n').encode(),dict(kind='generated-expectations'))
    notices={
        'DFIRArtifactMuseum-LICENSE.txt':(lock['registry_fixture_license']['url'],lock['registry_fixture_license']['sha256']),
        'DeepBlueCLI-LICENSE.txt':('https://raw.githubusercontent.com/sans-blue-team/DeepBlueCLI/2eecc65698e8666408ece67525577c895676d579/LICENSE',None),
        'Registry-LICENSE.txt':('https://raw.githubusercontent.com/EricZimmerman/Registry/de0bdbbea699637fe0e7b519c9f7fc07aafb173a/LICENSE.md',None),
        'SQLECmd-LICENSE.txt':('https://raw.githubusercontent.com/EricZimmerman/SQLECmd/c67634af503bd53777689998f1d9e3c0b4e2fdff/LICENSE',None),
        'WebCache-LICENSE.txt':('https://raw.githubusercontent.com/Sootmark/ese/3570ed9280f73d0d4796ed8979a7a4e30ea022d9/tests/fixtures/plaso/LICENSE',None),
        'WebCache-NOTICE.txt':('https://raw.githubusercontent.com/Sootmark/ese/3570ed9280f73d0d4796ed8979a7a4e30ea022d9/tests/fixtures/plaso/NOTICE',None),
    }
    for name,(url,sha) in notices.items():store('NOTICES/'+name,fetch(url,sha),dict(kind='notice',url=url))
    store('NOTICES/Fireblade-LICENSE.txt',(project/'LICENSE').read_bytes(),dict(kind='project-license'))
    write_guide(root,expected,volume_rows)
    origins={item['path']:item['origin'] for item in records}
    files=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(root).as_posix()
        files.append(dict(path=relative,bytes=path.stat().st_size,sha256=digest(path),origin=origins.get(relative,dict(kind='synthetic-demonstration',license='MIT'))))
    manifest=dict(format='fireblade-test-pack',version=1,application_commit=APP_COMMIT,application_sha256=APP_SHA256,files=files,expected=expected)
    if source_commit:manifest['generator_commit']=source_commit
    (root/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    archive=directory/ARCHIVE
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as zipped:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                info=zipfile.ZipInfo(ROOT+'/'+path.relative_to(root).as_posix(),date_time=(2026,11,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                with path.open('rb') as incoming,zipped.open(info,'w') as outgoing:shutil.copyfileobj(incoming,outgoing)
    verified=verify_archive(archive)
    publication=dict(status='verified',archive_name=ARCHIVE,archive_bytes=archive.stat().st_size,archive_sha256=digest(archive),uncompressed_bytes=sum(item['bytes'] for item in files),files=len(files),download_url=DOWNLOAD,application_commit=APP_COMMIT,expected=verified['expected'])
    (directory/'publication.json').write_text(json.dumps(publication,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (directory/'SHA256SUMS.txt').write_text(publication['archive_sha256']+'  '+ARCHIVE+'\n',encoding='ascii')
    return publication


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--volume-rows',type=int,default=250000);parser.add_argument('--source-commit');args=parser.parse_args()
    if args.volume_rows<2:parser.error('At least two volume records are required')
    print(json.dumps(package(args.out,Path(__file__).parents[2],args.volume_rows,args.source_commit),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
