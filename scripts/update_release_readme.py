"""Promote a verified published application release in the English README."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from scripts.release import application_version


def promote(text, release, version, digest, commit, run_url):
    if (release.get('draft', True) or release.get('tag_name')!='v'+version
            or 'Commit : '+commit not in release.get('body','')
            or 'SHA-256 de Fireblade.exe : '+digest not in release.get('body','')):
        raise ValueError('Published release identity does not match the qualified binary')
    assets=release.get('assets',[])
    if len(assets)!=1 or assets[0]['name']!='Fireblade.exe' or assets[0].get('digest')!='sha256:'+digest:
        raise ValueError('Published executable hash differs from the qualified binary')
    banner='> Download the Windows x64 executable from [GitHub Releases]'
    lines=text.splitlines()
    replacement=f"**[Download Fireblade {version} — Windows x64]({assets[0]['browser_download_url']})** · [Release notes and SHA-256]({release['html_url']}) · [Windows qualification]({run_url})"
    index=next(i for i,line in enumerate(lines) if line.startswith(banner) or line.startswith('**[Download Fireblade '))
    lines[index]=replacement+'\n\nThe desktop interface and most user guides are currently in French.'
    return '\n'.join(lines)+'\n'


def main():
    root=Path.cwd();repo=os.environ['GITHUB_REPOSITORY'];commit=os.environ['GITHUB_SHA']
    version=application_version(root)
    with (root/'dist/Fireblade.exe').open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    release=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases/tags/v{version}'],text=True))
    url=f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    path=root/'README.md';updated=promote(path.read_text(encoding='utf-8'),release,version,digest,commit,url)
    subprocess.run(['git','fetch','origin','main'],check=True)
    head=subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip()
    if head!=commit:raise ValueError('Main changed during qualification; refusing to overwrite it')
    path.write_text(updated,encoding='utf-8')
    subprocess.run(['git','config','user.name','github-actions[bot]'],check=True)
    subprocess.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],check=True)
    subprocess.run(['git','add','README.md'],check=True)
    subprocess.run(['git','commit','-m',f'Docs: link qualified Fireblade {version} release'],check=True)
    subprocess.run(['git','push','origin','HEAD:main'],check=True)


if __name__=='__main__':main()
