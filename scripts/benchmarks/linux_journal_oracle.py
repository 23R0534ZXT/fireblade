"""Compare external systemd journal fixtures with native journalctl; never publish."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from fireblade.core.linux_logs import journal_rows


def qualify(directory):
    results=[]
    for source in sorted(Path(directory).glob('*.journal')):
        rows=[];error=None
        try:
            with source.open('rb') as stream:
                for row in journal_rows(stream):rows.append(row)
        except ValueError as exc:error=str(exc)
        run=subprocess.run(['journalctl','--file',str(source),'-o','json','--no-pager'],capture_output=True,text=True,check=True)
        native=[json.loads(line) for line in run.stdout.splitlines()]
        verify=subprocess.run(['journalctl','--file',str(source),'--verify'],capture_output=True,text=True)
        same=len(rows)==len(native)
        if same:
            for row,reference in zip(rows,native):
                fields=json.loads(row['Champs'])['fields']
                expected={k: v if isinstance(v,list) else [v] for k,v in reference.items() if not k.startswith('__')}
                same &= fields==expected
        with source.open('rb') as stream:source_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        entry=dict(name=source.name,sha256=source_sha,
                   bytes=source.stat().st_size,fireblade_records=len(rows),journalctl_records=len(native),
                   all_data_fields_identical=bool(same),fireblade_error=error,journalctl_verify_exit=verify.returncode)
        if source.name!='unused.journal':
            assert same and not error and verify.returncode==0,entry
        else:
            # This upstream sample deliberately corrupts an ENTRY_ARRAY link.
            # Native journalctl stops early; Fireblade exposes partial recovery
            # and the invalid link. Do not present the recovered rows as complete.
            assert error and verify.returncode!=0,entry
            entry['interpretation']='corruption detected; partial recovery differs from native traversal; no completeness claim'
        results.append(entry)
    assert len(results)>=3
    return dict(format='fireblade-systemd-journal-oracle',version=1,fixtures=results)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=qualify(args.directory)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
