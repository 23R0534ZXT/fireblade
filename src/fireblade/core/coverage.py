"""Evidence-based collection coverage: observations, omissions and actionable causes.

Never infer acquisition completeness from an empty result or a successful parser.
All scans use the same immutable analysis snapshots as the workspace reader.
"""
from collections import Counter
import copy
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from fireblade.core.errors import OperationCancelled,job_cancelled
from fireblade.core.models import View
from fireblade.core.timeline import guess_time_column
from fireblade.core.timestamps import timestamp_key

FORMAT='fireblade-coverage'
MAX_EVENTS=2000
MAX_STATE_BYTES=8*1024**2
STAGES=('Collecte','Import','Analyse','Chronologie','Chasse IOC','Export','Intégrité')
EXPECTED={
 'observed':(),
 'windows':('EvtxECmd','RECmd','PECmd','MFTECmd','LECmd','JLECmd','AmcacheParser','AppCompatCacheParser','SrumECmd','WxTCmd','RBCmd','RecentFileCacheParser','SQLECmd','Shellbags','WebCache'),
 'linux':('CatScale',*('CatScale:'+name for name in ('Processus et réseau','Persistance','Journaux et connexions','Système','Utilisateurs','Fichiers et chronologie'))),
}
REMEDIES={
 'source_missing':'Rétablir la source originale ou documenter son absence ; la base importée peut rester lisible.',
 'source_changed':'Comparer avec l’original conservé et réimporter dans une nouvelle analyse. Ne pas écraser les preuves.',
 'analysis_unreadable':'Vérifier le chemin, les droits, la disponibilité du disque et rouvrir la bonne base.',
 'row_mismatch':'Vérifier la base référencée et refaire l’import depuis l’original dans une nouvelle analyse.',
 'undated':'Choisir la bonne colonne de date ou créer une conversion explicite, puis reconstruire la chronologie.',
 'naive_dates':'Confirmer le fuseau de la source et convertir les dates locales avant la chronologie.',
 'no_time_column':'Choisir une colonne de date ; une donnée sans date reste analysable mais ne peut pas être placée sur la courbe.',
 'missing_family':'Vérifier que cette famille était prévue dans le plan de collecte, acquérir les artefacts et relancer le lecteur adapté.',
 'reader_problem':'Lire le journal du lecteur, vérifier sa disponibilité, ses entrées et ses fichiers compagnons, puis relancer.',
 'output_missing':'Rétablir les résultats depuis la sauvegarde ou relancer le traitement depuis la source conservée.',
 'export_changed':'Conserver ce fichier comme une nouvelle version ou refaire l’export ; son intégrité ne correspond plus au reçu.',
}


def check():
    if job_cancelled():raise OperationCancelled()


def digest(path,checker=check):
    before=Path(path).stat();sha=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(1024**2):checker();sha.update(block)
    after=Path(path).stat();checker()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Fichier modifié pendant la vérification')
    return sha.hexdigest()


def diagnostic_action(reason):
    value=str(reason).casefold()
    for tokens,action in (
        (('permission','access is denied','errno 13','accès refusé'),'Vérifier les droits de lecture/écriture et les fichiers verrouillés, puis choisir une destination accessible.'),
        (('no space','disk full','errno 28','disque plein'),'Libérer de l’espace sur le disque de travail et la destination, puis relancer ; conserver la source originale.'),
        (('out of memory','allocation','mémoire insuffisante'),'Réduire les réglages mémoire et le parallélisme, fermer les opérations concurrentes et relancer.'),
        (('encoding','unicode','utf-','encodage'),'Choisir l’encodage exact de la source ; conserver l’original et refaire l’import dans une nouvelle base.'),
        (('csv error','separator','delimiter','séparateur','nombre de colonnes'),'Vérifier le séparateur, les guillemets, l’en-tête et la structure des enregistrements ; ne pas ignorer silencieusement les lignes invalides.'),
        (('sha-256','sha256','empreinte','source a changé'),'Comparer l’empreinte avec l’original conservé ; refaire le traitement depuis une copie vérifiée.'),
        (('not found','introuvable','no such file','absent'),'Rétablir le chemin ou le fichier manquant et vérifier que la source ou le lecteur attendu est disponible.'),
    ):
        if any(token in value for token in tokens):return action
    return 'Consulter le détail et les journaux de l’opération, corriger la cause puis relancer ; conserver les sources et la destination précédente.'


def finding(stage,severity,code,path,reason,impact='',action=None,**metrics):
    return dict(stage=stage,severity=severity,code=code,path=str(path),reason=str(reason)[:16000],
                impact=str(impact)[:4000],action=action or REMEDIES.get(code,diagnostic_action(reason)),metrics=metrics)


def event(stage,severity,reason,path='',**metrics):
    return dict(time=datetime.now(timezone.utc).isoformat(),**finding(stage,severity,'operation',path,reason,**metrics))


def save_state(path,state):
    from fireblade.core.layout import write_json
    path=Path(path)
    if path.is_symlink():raise ValueError('Le journal de couverture est un lien')
    encoded=json.dumps(state,ensure_ascii=False,indent=2).encode('utf-8')
    if len(encoded)>MAX_STATE_BYTES:raise ValueError('Journal de couverture limité à 8 Mio ; exporter les résultats avant de poursuivre')
    write_json(path,state)


def load_state(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>MAX_STATE_BYTES:raise ValueError('Journal de couverture invalide ou supérieur à 8 Mio')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or value.get('format')!=FORMAT or value.get('version')!=1 or not isinstance(value.get('events'),list) or len(value['events'])>MAX_EVENTS:
        raise ValueError('Format de journal de couverture invalide')
    if type(value.get('dropped',0)) is not int or value.get('dropped',0)<0:raise ValueError('Compteur d’historique invalide')
    plan=value.get('plan',{})
    if not isinstance(plan,dict) or not isinstance(plan.get('profile','observed'),str):raise ValueError('Plan de couverture invalide')
    readers=plan.get('readers')
    if readers is not None and (not isinstance(readers,list) or len(readers)>100 or any(not isinstance(r,str) or len(r)>200 for r in readers)):raise ValueError('Familles attendues invalides')
    for item in value['events']:
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in ('stage','severity','reason','path','time')):
            raise ValueError('Entrée de journal de couverture invalide')
        if not isinstance(item.get('metrics',{}),dict):raise ValueError('Mesures du journal invalides')
        if item['severity'] not in ('info','warning','error'):raise ValueError('Gravité de journal invalide')
    return value


def audit(reader,*,collections=(),timeline=None,hunts=(),events=(),verify_hashes=False,expected='observed',expected_tools=None,deep_checks=True,progress=lambda _:None):
    if expected not in EXPECTED:raise ValueError('Profil de couverture inconnu')
    wanted=list(EXPECTED[expected] if expected_tools is None else expected_tools)
    if len(wanted)>100 or any(not isinstance(name,str) or len(name)>200 for name in wanted):raise ValueError('Plan de familles attendu invalide')
    findings=[];counts=Counter();omitted_findings=0;sources=[];seen=set();tools=set();families=set();checked_files={};reader.check()
    if len(reader.documents)>1000:raise ValueError('Contrôle limité à 1000 analyses')
    def add(*args,**kwargs):
        nonlocal omitted_findings
        item=finding(*args,**kwargs);counts[item['severity']]+=1
        if len(findings)<20000:findings.append(item)
        else:omitted_findings+=1
        return item
    def verify(path,info,stage='Intégrité'):
        path=Path(path)
        key=(str(path),info.get('size'),info.get('sha256'))
        if key in checked_files:return checked_files[key]
        try:
            if path.is_symlink():
                add(stage,'warning','symbolic_source',path,'Lien symbolique non suivi pendant le contrôle.','L’intégrité de cette référence n’est pas revérifiée.');return
            if not path.is_file():
                add(stage,'warning','source_missing',path,'Source originale indisponible.','Son empreinte et sa taille ne peuvent pas être revérifiées.');return
            size=path.stat().st_size
            if type(info.get('size')) is int and size!=info['size']:
                add(stage,'error','source_changed',path,'La taille actuelle diffère de celle enregistrée.',expected_bytes=info['size'],actual_bytes=size)
            if verify_hashes and info.get('sha256'):
                actual=digest(path,reader.check)
                if actual!=info['sha256']:add(stage,'error','source_changed',path,'SHA-256 différent de celui enregistré.',expected_sha256=info['sha256'],actual_sha256=actual)
                else:add(stage,'info','source_verified',path,'SHA-256 actuel identique à l’empreinte enregistrée.',action='Conserver la source et le reçu de vérification.',sha256=actual)
            elif info.get('sha256'):add(stage,'info','hash_not_checked',path,'Empreinte enregistrée, non recalculée pendant ce contrôle.',action='Cocher la vérification SHA-256 pour contrôler le contenu actuel.')
            else:add(stage,'warning','hash_missing',path,'Aucune empreinte enregistrée : l’intégrité du contenu n’est pas démontrée.')
        except OperationCancelled:raise
        except Exception as exc:add(stage,'error','source_unreadable',path,str(exc),'Vérification d’intégrité impossible.')
        finally:checked_files[key]=True
    for number,document in enumerate(reader.documents):
        reader.check();seen.add(document.path);progress(f'Couverture · analyse {number+1}/{len(reader.documents)}')
        record=dict(path=document.path,source=document.source_info.get('path',''),imported=document.source_info.get('rows'),read=None,selected=None,dated=None,undated=None,naive=None)
        verify(record['source'],document.source_info)
        try:
            with reader.open(document) as case:
                total=case.count(View());selected=case.count(document.view);record.update(read=total,selected=selected)
                if timeline:
                    linked=next((s for s in timeline.get('sources',[]) if s['path']==document.path),None)
                    if linked and linked.get('analysis_fingerprint') and linked['analysis_fingerprint']!=analysis_fingerprint(case,reader.check):
                        add('Chronologie','warning','stale_timeline_annotations',document.path,'Les annotations, colonnes ou définitions calculées ont changé depuis l’indexation.','Les signets, notes, champs de corrélation ou dates de cet index peuvent être anciens.',action='Reconstruire la chronologie pour actualiser son contenu.')
                if total!=record['imported']:add('Import','error','row_mismatch',document.path,'Le nombre de lignes actuel diffère de l’import.',expected=record['imported'],actual=total)
                if not total:add('Import','warning','empty_analysis',document.path,'Analyse vide : zéro ligne importée.','Une sortie vide ne démontre pas l’absence d’activité.')
                if deep_checks and total:
                    reader.check()
                    ids=case.db.execute('SELECT count(DISTINCT __row_id),min(__row_id),max(__row_id) FROM events').fetchone();reader.check()
                    if ids!=(total,1,total):add('Analyse','error','row_ids_invalid',document.path,'Identifiants des lignes dupliqués, absents ou hors de la plage attendue.','Les renvois aux lignes sources peuvent être ambigus.',unique_ids=ids[0],first=ids[1],last=ids[2],expected=total)
                    empty=[]
                    for start in range(0,len(case.headers),64):
                        reader.check();progress(f'Couverture · colonnes {start+1}–{min(start+64,len(case.headers))} · '+Path(document.path).name)
                        indexes=list(range(start,min(start+64,len(case.headers))))
                        expressions=[f"count(*) FILTER(WHERE {case.column(i)} IS NULL OR trim({case.column(i)})='')" for i in indexes]
                        nulls=case.db.execute('SELECT '+','.join(expressions)+' FROM events').fetchone()
                        empty.extend(case.headers[i] for i,n in zip(indexes,nulls) if n==total)
                    record['empty_columns']=empty
                    if empty:add('Import','warning','empty_columns',document.path,f'{len(empty)} colonnes entièrement vides.','Cela peut être normal pour ce format ou révéler un lecteur ou un schéma inadapté.',action='Comparer le schéma et les valeurs avec la source et le journal du lecteur avant de conclure.',columns=empty)
                if selected<total:add('Analyse','info','filtered_scope',document.path,f'{selected} / {total} lignes dans la vue actuelle.','Les filtres réduisent volontairement le périmètre ; les autres lignes restent dans la base.',action='Retirer les filtres pour contrôler la totalité des lignes.',selected=selected,total=total)
                if selected==0 and total:add('Analyse','warning','empty_view',document.path,'Les filtres de cette vue ne retiennent aucune ligne.','Ce résultat ne constitue pas une absence sur l’ensemble des données.')
                index=guess_time_column(case.headers,document.view.timestamp_columns)
                if timeline:
                    linked=next((s for s in timeline.get('sources',[]) if s['path']==document.path),None)
                    if linked is not None:index=linked.get('column',index)
                if index is None:add('Chronologie','warning','no_time_column',document.path,'Aucune colonne temporelle reconnue.')
                elif type(index) is not int or not 0<=index<len(case.headers):add('Chronologie','error','no_time_column',document.path,'La colonne temporelle configurée n’existe plus.')
                else:
                    col=case.column(index);key=timestamp_key(col)
                    stats=case.db.execute(f"SELECT count(*),count(*) FILTER(WHERE {col} IS NULL OR trim({col})=''),count({key}),count(*) FILTER(WHERE ({key}) IS NOT NULL AND NOT regexp_matches(coalesce({col},''),'(Z|[+-][0-9]{{2}}:?[0-9]{{2}})\\s*$')) FROM events").fetchone();reader.check()
                    record.update(dated=stats[2],undated=stats[0]-stats[2],naive=stats[3],time_column=case.headers[index],empty_dates=stats[1],invalid_dates=stats[0]-stats[2]-stats[1])
                    if record['undated']:date_issue=add('Chronologie','warning','undated',document.path,f"{record['undated']} / {total} lignes sans date exploitable dans {case.headers[index]}.",'Ces lignes ne sont pas placées sur le graphique.',empty=stats[1],invalid=record['invalid_dates'],dated=stats[2],total=total)
                    if record['naive']:add('Chronologie','warning','naive_dates',document.path,f"{record['naive']} dates sans fuseau explicite.",'Le placement UTC est une hypothèse, pas une preuve du fuseau source.',count=stats[3])
                    if record['invalid_dates']:
                        samples=case.db.execute(f"SELECT __row_id,left({col},200) FROM events WHERE ({key}) IS NULL AND {col} IS NOT NULL AND trim({col})<>'' ORDER BY __row_id LIMIT 5").fetchall()
                        record['invalid_samples']=[dict(row_id=r[0],value=r[1]) for r in samples]
                        date_issue['metrics']['invalid_examples']=record['invalid_samples']
        except OperationCancelled:raise
        except Exception as exc:add('Analyse','error','analysis_unreadable',document.path,str(exc),'Cette analyse n’a pas pu être entièrement contrôlée.')
        sources.append(record)
        add('Analyse','info','row_coverage',document.path,f"Import déclaré : {record['imported']} lignes ; base lue : {record['read']} ; vue courante : {record['selected']}.",action='Comparer les périmètres avant de conclure à une absence.',coverage=record)
    for report in collections:
        reader.check()
        try:
            if not isinstance(report,dict) or not all(isinstance(report.get(k,''),str) for k in ('source','output','status')):raise ValueError('En-tête d’inventaire invalide')
            if not isinstance(report.get('files',[]),list) or len(report.get('files',[]))>200000:raise ValueError('Inventaire invalide ou supérieur à 200 000 entrées')
            for entry in report.get('files',[]):
                if not isinstance(entry,dict) or not isinstance(entry.get('path'),str) or not isinstance(entry.get('runs',[]),list) or not isinstance(entry.get('tools',[]),list):raise ValueError('Entrée d’inventaire invalide')
                for run in entry.get('runs',[]):
                    if not isinstance(run,dict) or not isinstance(run.get('outputs',[]),list):raise ValueError('Résultat de lecteur invalide')
                    for output in run.get('outputs',[]):
                        if not isinstance(output,dict) or any(k in output and not isinstance(output[k],str) for k in ('csv','analysis','family')):raise ValueError('Référence de sortie invalide')
            if not isinstance(report.get('documents',[]),list) or any(not isinstance(d,dict) or not isinstance(d.get('path'),str) for d in report.get('documents',[])):raise ValueError('Référence d’analyse invalide')
        except (ValueError,TypeError) as exc:
            add('Collecte','error','inventory_invalid','',str(exc),'Cet inventaire n’a pas été utilisé pour conclure à une couverture.');continue
        reader.check();root=report.get('output','');progress('Couverture · bilan de collecte '+root)
        entries=report.get('files',[])
        if report.get('status') in ('running','pending','error','cancelled'):add('Collecte','warning','unfinished_collection',root,'Collecte non terminée : '+str(report.get('status')),'Le périmètre collecté ou parsé peut être incomplet.')
        inventory={str(Path(e['path']).absolute()) for e in entries if e.get('path')}
        source_root=Path(report.get('source',''))
        if deep_checks and str(report.get('source','')):
            if not source_root.is_dir():add('Collecte','warning','source_missing',source_root,'Dossier de collecte source indisponible ; inventaire actuel non vérifiable.')
            elif source_root.is_symlink():add('Collecte','warning','inventory_not_checked',source_root,'Dossier source symbolique : inventaire non suivi.')
            else:
                walked=0;stop_walk=False
                def walk_error(exc):add('Collecte','error','inventory_unreadable',getattr(exc,'filename',source_root),str(exc),'Une partie du dossier n’a pas pu être inventoriée.')
                for directory,dirs,names in os.walk(source_root,followlinks=False,onerror=walk_error):
                    reader.check()
                    for name in dirs:
                        if (Path(directory)/name).is_symlink():add('Collecte','warning','symbolic_directory',Path(directory)/name,'Lien de dossier non suivi ; couverture de son contenu inconnue.')
                    dirs[:]=[d for d in dirs if not (Path(directory)/d).is_symlink()]
                    for name in names:
                        reader.check();walked+=1
                        if walked>200000:
                            add('Collecte','warning','inventory_limited',source_root,'Inventaire limité à 200 000 fichiers.','Les fichiers au-delà de cette limite ne sont pas contrôlés.');stop_walk=True;break
                        path=Path(directory)/name
                        if str(path.absolute()) not in inventory:add('Collecte','warning','uninventoried_file',path,'Fichier présent mais absent de l’inventaire de collecte.','Ce fichier n’est pas attesté comme traité par cette collecte.',action='Vérifier sa pertinence et relancer un import dans un nouveau dossier de travail.')
                    if stop_walk:break
        if not entries:add('Collecte','warning','empty_inventory',root,'Aucun fichier inventorié.','La couverture de la collecte n’est pas établie.')
        for entry in entries:
            reader.check();tools.update(entry.get('tools',[]));path=entry.get('path','')
            verify(path,entry)
            state=entry.get('status','unknown')
            if state not in ('complete','companion'):
                add('Collecte','error' if state=='error' else 'warning','reader_problem',path,f"{state} : {entry.get('error') or entry.get('reason') or 'Voir le journal du lecteur ; aucune réussite complète attestée.'}")
            for run in entry.get('runs',[]):
                tools.add(run.get('tool',''))
                for warning in run.get('warnings',[]):add('Import','warning','reader_problem',path,str(run.get('tool',''))+' : '+str(warning))
                if run.get('status') not in ('complete','complete_with_warnings'):
                    add('Import','error' if run.get('status')=='error' else 'warning','reader_problem',path,str(run.get('tool',''))+' : '+str(run.get('error') or run.get('status')))
                for member in run.get('catscale',{}).get('members',[]):
                    if member.get('status') in ('error','unsupported','skipped'):add('Import','warning','reader_problem',member.get('path',path),str(member.get('reason') or member.get('status')))
                for output in run.get('outputs',[]):
                    if output.get('family'):families.add(output['family'])
                    for k in ('csv','analysis'):
                        if output.get(k) and not Path(output[k]).is_file():add('Import','error','output_missing',output[k],'Sortie déclarée par le lecteur mais absente du disque.')
        for document in report.get('documents',[]):
            if not Path(document['path']).is_file():add('Analyse','error','analysis_unreadable',document['path'],'Analyse de collecte absente du disque.')
            elif document['path'] not in seen:add('Analyse','warning','closed_analysis',document['path'],'Analyse de collecte non ouverte dans cet espace de travail.','Elle n’est pas incluse dans les contrôles des lignes, la chasse IOC ou la chronologie courante.',action='Ouvrir cette analyse ou documenter son exclusion.')
        detection=report.get('detection')
        if detection:
            if detection.get('status') not in ('complete','complete_with_warnings'):add('Analyse','warning','reader_problem',root,'Détection Hayabusa : '+str(detection.get('error') or detection.get('status')))
            for warning in detection.get('warnings',[]):add('Analyse','warning','reader_problem',root,'Hayabusa : '+str(warning))
        else:add('Analyse','info','detection_not_run',root,'Aucune exécution Hayabusa enregistrée.','Les données importées n’ont pas nécessairement été soumises à ce moteur de détection.')
    for tool in wanted:
        if tool not in tools and tool not in {'CatScale:'+name for name in families}:add('Collecte','warning','missing_family',tool,'Famille attendue non observée dans les inventaires de collecte : '+tool,'L’absence peut venir du périmètre choisi ou d’une acquisition manquante ; elle ne prouve pas une absence sur la machine.')
    if not collections:add('Collecte','warning','no_inventory','','Aucun inventaire de collecte disponible.','Les fichiers jamais acquis ne peuvent pas être déduits des analyses ouvertes.',action='Importer ou reprendre le dossier de collecte et choisir les familles attendues.')
    if not sources:add('Analyse','warning','no_analysis','','Aucune analyse ouverte.','Les données ne peuvent pas être contrôlées.')
    if timeline:
        indexed={s['path'] for s in timeline.get('sources',[])}
        if indexed!=seen or timeline.get('stale'):add('Chronologie','warning','stale_timeline','','L’index ne correspond plus au périmètre courant.','Des analyses, vues ou annotations peuvent manquer.',action='Reconstruire la chronologie après les changements d’espace de travail.')
        for s in timeline.get('sources',[]):
            if s.get('error'):add('Chronologie','error','analysis_unreadable',s['path'],s['error'],'Analyse absente de l’index temporel.')
        if timeline.get('respect_filters'):add('Chronologie','info','filtered_scope','','L’index temporel a été construit avec les filtres des analyses.','Les lignes exclues par ces filtres ne participent pas à la chronologie.')
        if not timeline.get('include_undated'):add('Chronologie','info','undated_hidden','','Les événements sans date sont masqués dans le tableau courant.','Ils ne sont jamais dessinés sur la courbe ; activer leur inclusion pour consulter le tableau.')
    else:add('Chronologie','warning','timeline_not_built','','Aucune chronologie construite dans cet espace de travail.',action='Construire la chronologie pour mesurer la couverture réelle de son index.')
    for run in hunts:
        if run.get('status')!='complete' or run.get('truncated') or run.get('rejected'):
            add('Chasse IOC','warning','partial_hunt',run.get('path',''),'Chasse partielle, détails limités ou IOC rejetés.','L’export des occurrences peut ne pas contenir toutes les observations.',action='Consulter le bilan de la chasse, les IOC rejetés et les analyses non lues.',status=run.get('status'),rejected=run.get('rejected',0),truncated=run.get('truncated',False))
    if verify_hashes:
        checked_exports=set()
        for item in reversed(list(events)):
            reader.check();metrics=item.get('metrics',{})
            if item.get('stage')=='Export' and metrics.get('sha256'):
                path=Path(item['path']);identity=str(path.resolve())
                if identity in checked_exports:continue
                checked_exports.add(identity)
                try:
                    if not path.is_file():add('Export','error','output_missing',path,'Fichier exporté absent lors du contrôle.')
                    else:
                        actual=digest(path,reader.check)
                        if actual!=metrics['sha256']:add('Export','error','export_changed',path,'SHA-256 différent du dernier reçu d’export.',expected_sha256=metrics['sha256'],actual_sha256=actual)
                        else:add('Export','info','export_verified',path,'SHA-256 actuel identique au dernier reçu d’export.',action='Conserver le reçu avec ce fichier.',sha256=actual)
                except OperationCancelled:raise
                except Exception as exc:add('Export','error','output_unreadable',path,str(exc),'Le fichier exporté ne peut pas être revérifié.')
    reader.check()
    if omitted_findings:
        counts['warning']+=1;findings.append(finding('Analyse','warning','diagnostic_limit','',f'{omitted_findings} constats supplémentaires non détaillés ; compteurs complets conservés.',action='Réduire le périmètre et relancer pour obtenir le détail.'))
    return dict(format=FORMAT,version=1,created=datetime.now(timezone.utc).isoformat(),verify_hashes=verify_hashes,deep_checks=deep_checks,expected_profile=expected,expected_readers=wanted,
                scope='Analyses ouvertes, inventaires fournis et opérations journalisées ; aucune preuve de complétude des fichiers jamais acquis.',
                observed_readers=sorted(tools),observed_families=sorted(families),sources=sources,findings=findings,events=copy.deepcopy(list(events)),omitted_findings=omitted_findings,counts={level:counts[level] for level in ('info','warning','error')})


def export_report(target,report,protected=()):
    """Atomic JSON or flat CSV, with source and database protection."""
    from fireblade.core.paths import protected_destination
    target=Path(target).resolve()
    protected=list(protected)+[s[k] for s in report.get('sources',[]) for k in ('path','source')]
    if protected_destination(target,protected):raise ValueError('Le bilan ne peut pas remplacer une source ou une analyse')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,suffix='.partial',delete=False) as stream:temporary=Path(stream.name)
        if target.suffix.lower()=='.csv':
            with temporary.open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['Date_du_contrôle','Étape','Gravité','Code','Chemin','Cause','Impact','Action','Mesures_JSON'])
                for item in report['findings']+report.get('events',[]):
                    check();writer.writerow([item.get('time',report['created']),*[item.get(k,'') for k in ('stage','severity','code','path','reason','impact','action')],json.dumps(item.get('metrics',{}),ensure_ascii=False)])
        else:temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        check();os.replace(temporary,target)
    finally:
        if temporary:temporary.unlink(missing_ok=True)


def save_report(path,report):
    from fireblade.core.layout import write_json
    path=Path(path)
    if path.is_symlink():raise ValueError('Le bilan de couverture est un lien')
    if len(json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8'))>32*1024**2:raise ValueError('Bilan de couverture limité à 32 Mio ; exporter le résultat séparément')
    write_json(path,report)


def load_report(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>32*1024**2:raise ValueError('Bilan de couverture invalide ou supérieur à 32 Mio')
    report=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(report,dict) or report.get('format')!=FORMAT or report.get('version')!=1:raise ValueError('Format de bilan invalide')
    if not isinstance(report.get('sources'),list) or len(report['sources'])>1000 or not isinstance(report.get('findings'),list) or len(report['findings'])>22002:raise ValueError('Périmètre de bilan invalide')
    if not isinstance(report.get('created'),str):raise ValueError('Date de bilan invalide')
    for source in report['sources']:
        if not isinstance(source,dict) or not isinstance(source.get('path'),str) or not isinstance(source.get('source'),str):raise ValueError('Référence de source invalide')
    for item in report['findings']:
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in ('stage','severity','path','reason','impact','action')) or not isinstance(item.get('metrics'),dict):raise ValueError('Constat de bilan invalide')
    if not isinstance(report.get('counts'),dict) or any(type(report['counts'].get(k)) is not int or report['counts'][k]<0 for k in ('info','warning','error')):raise ValueError('Compteurs de bilan invalides')
    return report


class RowDigest:
    """Hash the textual representation exported by both CSV and XLSX writers."""
    def __init__(self):self.sha=hashlib.sha256();self.count=0
    def update(self,row):
        encoded=json.dumps(['' if value is None else str(value) for value in row],ensure_ascii=False,separators=(',',':')).encode('utf-8')
        self.sha.update(len(encoded).to_bytes(8,'big'));self.sha.update(encoded);self.count+=1
    def hexdigest(self):return self.sha.hexdigest()


class ExportCursor:
    def __init__(self,cursor):self.cursor=cursor;self.rows=RowDigest()
    @property
    def written(self):return self.rows.count
    def fetchmany(self,size):
        batch=self.cursor.fetchmany(size)
        for row in batch:self.rows.update(row)
        return batch


def verify_export(path,expected,headers,content_sha256,*,xlsx=False,checker=check):
    """Independently reopen the new file before replacement; no silent loss."""
    rows=RowDigest();checker()
    def read(iterator,pad=False):
        actual_header=next(iterator,None)
        if actual_header is None or list(actual_header)!=list(headers):raise ValueError('En-tête du fichier exporté différent du schéma attendu')
        for row in iterator:
            if pad and len(row)<len(headers):row=(*row,*([None]*(len(headers)-len(row))))
            if len(row)!=len(headers):raise ValueError('Nombre de colonnes incohérent dans le fichier exporté')
            rows.update(row)
            if rows.count%256==0:checker()
    if xlsx:
        from openpyxl import load_workbook
        with Path(path).open('rb') as stream:
            workbook=load_workbook(stream,read_only=True,data_only=False,keep_links=False)
            try:
                for sheet in workbook.worksheets:
                    checker();read(iter(sheet.iter_rows(values_only=True)),pad=True)
            finally:workbook.close()
    else:
        csv.field_size_limit(max(csv.field_size_limit(),16*1024**2))
        with Path(path).open(encoding='utf-8-sig',newline='') as stream:read(iter(csv.reader(stream,strict=True)))
    checker()
    if rows.count!=expected:raise ValueError(f'Export incomplet à la relecture : {rows.count} lignes au lieu de {expected}')
    if rows.hexdigest()!=content_sha256:raise ValueError('Contenu du fichier exporté différent des valeurs transmises au rédacteur')
    return dict(verified_rows=rows.count,content_sha256=rows.hexdigest(),sha256=digest(path,checker))


def analysis_fingerprint(case,checker=check):
    rows=RowDigest();rows.update([json.dumps(dict(headers=case.headers,derived=getattr(case,'derived',[])),ensure_ascii=False,sort_keys=True)])
    cursor=case.db.execute('SELECT row_id,note FROM bookmarks ORDER BY row_id')
    while batch:=cursor.fetchmany(1024):
        checker()
        for row in batch:rows.update(row)
    checker();return rows.hexdigest()
