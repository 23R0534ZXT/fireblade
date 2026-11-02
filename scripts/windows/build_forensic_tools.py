"""Build pinned MIT EZ parsers and stage Hayabusa with rules in the one-file bundle."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import zipfile
import xml.etree.ElementTree as ET


def unpack(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            target = (destination/item.filename).resolve()
            if destination not in target.parents and target != destination:
                raise ValueError('Chemin ZIP hors du dossier de destination')
        zipped.extractall(destination)


def build(root, resources):
    root, resources = Path(root), Path(resources)
    lock = json.loads((root/'config/forensic-toolchain.json').read_text())
    destination = resources/'forensic-tools'
    destination.mkdir(parents=True, exist_ok=True)
    legal = resources/'legal'/'forensic-tools'
    legal.mkdir(parents=True, exist_ok=True)
    checkout = root/'build'/'forensic-sources'
    checkout.mkdir(parents=True, exist_ok=True)
    for tool in lock['parsers']:
        source = checkout/tool['name']
        if not (source/'.git').exists():
            subprocess.run(['git', 'clone', '--no-checkout', tool['repository'], str(source)], check=True)
        subprocess.run(['git', 'checkout', '--force', '--detach', tool['commit']], cwd=source, check=True)
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
        if revision != tool['commit']:
            raise ValueError('Révision du parseur incorrecte')
        notice = source/tool['license']
        if 'permission is hereby granted' not in notice.read_text(encoding='utf-8-sig').lower():
            raise ValueError('Licence du parseur à vérifier : '+tool['name'])
        shutil.copy2(notice, legal/(tool['name']+'-LICENSE.txt'))
        # Offline forensic processing must never submit artifact-derived crash data.
        patched = 0
        for code in source.rglob('*.cs'):
            if any(part in ('obj', 'bin', '.git') for part in code.relative_to(source).parts):
                continue
            original = code.read_text(encoding='utf-8-sig')
            updated, count = re.subn(r'ExceptionlessClient\.Default\.Startup\([^;]*\);',
                'ExceptionlessClient.Default.Configuration.Enabled = false;', original)
            if count:
                code.write_text(updated, encoding='utf-8')
                patched += count
        tool['telemetry_disabled_startups'] = patched
        target = destination/tool['name']
        subprocess.run(['dotnet', 'publish', str(source/tool['project']), '-c', 'Release', '-f', 'net10.0',
                        '-r', 'win-x64', '--self-contained', 'false', '-p:UseAppHost=false',
                        '-o', str(target)], check=True)
        for relative in ('evtx/Maps', 'SQLMap/Maps', 'BatchExamples', 'Plugins'):
            extra = source/relative
            if extra.is_dir():
                shutil.copytree(extra, target/extra.name, dirs_exist_ok=True)
        if not (target/(tool['name']+'.dll')).is_file():
            raise ValueError('Parseur non publié : '+tool['name'])
        tool['binary_sha256'] = hashlib.sha256((target/(tool['name']+'.dll')).read_bytes()).hexdigest()
    # Fireblade's offline Shellbags host shares the MIT Registry/ExtensionBlocks
    # readers already used by the EZ engines and the embedded .NET runtime.
    shellbags = lock['shellbags']
    shellbags['source_commit'] = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    subprocess.run(['dotnet','publish',str(root/shellbags['project']),'-c','Release','-r','win-x64',
                    '--self-contained','false','-p:UseAppHost=false','-p:RestoreLockedMode=true','-o',str(destination/'Shellbags')],check=True)
    shellbags['binary_sha256'] = hashlib.sha256((destination/'Shellbags'/'Shellbags.dll').read_bytes()).hexdigest()
    for library in shellbags['libraries']:
        url = library['repository'].replace('https://github.com/','https://raw.githubusercontent.com/')+'/'+library['commit']+'/'+library['license']
        with urllib.request.urlopen(url,timeout=60) as response:notice=response.read()
        if b'permission is hereby granted' not in notice.lower():raise ValueError('Licence Shellbags à vérifier')
        (legal/('Shellbags-'+library['name']+'-LICENSE.txt')).write_bytes(notice)
    # Preserve the Apache-licensed public WebCache fixture's source notices.
    for name in ('LICENSE','NOTICE'):
        url='https://raw.githubusercontent.com/Sootmark/ese/3570ed9280f73d0d4796ed8979a7a4e30ea022d9/tests/fixtures/plaso/'+name
        with urllib.request.urlopen(url,timeout=60) as response:(legal/('WebCache-QA-'+name+'.txt')).write_bytes(response.read())
    plugins = lock['registry_plugins']
    source = checkout/'RegistryPlugins'
    if not (source/'.git').exists():
        subprocess.run(['git', 'clone', '--no-checkout', plugins['repository'], str(source)], check=True)
    subprocess.run(['git', 'checkout', '--force', '--detach', plugins['commit']], cwd=source, check=True)
    notice = source/plugins['license']
    if 'permission is hereby granted' not in notice.read_text(encoding='utf-8-sig').lower():
        raise ValueError('Licence RegistryPlugins à vérifier')
    shutil.copy2(notice, legal/'RegistryPlugins-LICENSE.txt')
    subprocess.run(['dotnet', 'build', str(source/plugins['solution']), '-c', 'Release',
                    '-p:MinVerVersionOverride=2026.10.7'], check=True)
    target = destination/'RECmd'/'Plugins'
    target.mkdir(exist_ok=True)
    plugin_names = []
    for node in ET.parse(source/plugins['solution']).getroot().iter('Project'):
        project = source/node.attrib['Path']
        name = project.stem
        if not name.startswith('RegistryPlugin.'):
            continue
        library = project.parent/'bin'/'Release'/'netstandard2.0'/(name+'.dll')
        if not library.is_file():
            raise ValueError('Plugin de registre non compilé : '+name)
        shutil.copy2(library, target/library.name)
        plugin_names.append(name)
    if not plugin_names:
        raise ValueError('Aucun plugin RECmd construit')
    plugins['included'] = plugin_names
    # Reuse the runtime installed by setup-dotnet, not a runtime on the recipient's PC.
    listing = subprocess.check_output(['dotnet', '--list-runtimes'], text=True)
    candidates = re.findall(r'^Microsoft.NETCore.App (10\.\S+) \[(.+)\]$', listing, re.M)
    if not candidates:
        raise ValueError('Runtime .NET 10 x64 nécessaire à la construction')
    version, shared = candidates[-1]
    runtime_root = Path(shared).parents[1]
    runtime = destination/'dotnet'
    (runtime/'shared'/'Microsoft.NETCore.App').mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(shared)/version, runtime/'shared'/'Microsoft.NETCore.App'/version)
    shutil.copytree(runtime_root/'host'/'fxr'/version, runtime/'host'/'fxr'/version)
    shutil.copy2(runtime_root/'dotnet.exe', runtime/'dotnet.exe')
    for name in ('LICENSE.txt', 'ThirdPartyNotices.txt'):
        if not (runtime_root/name).is_file():
            raise ValueError('Notice .NET absente : '+name)
        shutil.copy2(runtime_root/name, legal/('dotnet-'+name))
    hayabusa = lock['hayabusa']
    archive = checkout/'hayabusa.zip'
    with urllib.request.urlopen(hayabusa['url'], timeout=120) as source, archive.open('wb') as output:
        shutil.copyfileobj(source, output)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != hayabusa['sha256']:
        raise ValueError('Empreinte Hayabusa incorrecte')
    unpack(archive, checkout/'hayabusa')
    binaries = list((checkout/'hayabusa').rglob('*win-x64.exe'))
    if len(binaries) != 1:
        raise ValueError('Binaire Hayabusa x64 ambigu ou absent')
    git_head = binaries[0].parent/'rules'/'.git'/'HEAD'
    if git_head.is_file():
        head = git_head.read_text().strip()
        if head.startswith('ref: refs/'):
            ref = binaries[0].parent/'rules'/'.git'/head[5:]
            if ref.is_file():head = ref.read_text().strip()
        if re.fullmatch('[0-9a-f]{40}', head):hayabusa['rules_commit'] = head
    lock['dotnet_runtime_version'] = version
    shutil.copytree(binaries[0].parent, destination/'Hayabusa', dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
    shutil.copy2(binaries[0], destination/'Hayabusa'/'hayabusa.exe')
    if not (destination/'Hayabusa'/'rules').is_dir():
        raise ValueError('Règles Hayabusa absentes de l’archive ; publication refusée')
    for file in (destination/'Hayabusa').rglob('*'):
        if file.is_file() and any(s in file.name.casefold() for s in ('license', 'copying', 'notice')):
            target = legal/'Hayabusa'/file.relative_to(destination/'Hayabusa')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    # Provide the corresponding source alongside the bundled AGPL executable.
    source_url = hayabusa['source_url']
    with urllib.request.urlopen(source_url, timeout=120) as source, (destination/'Hayabusa-source.zip').open('wb') as output:
        shutil.copyfileobj(source, output)
    source_archive = destination/'Hayabusa-source.zip'
    if hashlib.sha256(source_archive.read_bytes()).hexdigest() != hayabusa['source_sha256']:
        raise ValueError('Empreinte des sources Hayabusa incorrecte')
    with zipfile.ZipFile(source_archive) as zipped:
        license_name = next(name for name in zipped.namelist() if name.endswith('/LICENSE.txt') and name.count('/') == 1)
        (legal/'Hayabusa-LICENSE.txt').write_bytes(zipped.read(license_name))
    # Verify every shipped entry point with only the embedded .NET runtime.
    checks = []
    for tool in lock['parsers']:
        command = [str(runtime/'dotnet.exe'), str(destination/tool['name']/(tool['name']+'.dll')), '--help']
        result = subprocess.run(command, cwd=destination/tool['name'], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise ValueError('Moteur intégré inutilisable : '+tool['name']+' '+result.stderr[-2000:])
        checks.append(dict(tool=tool['name'], help_passed=True))
    command=[str(runtime/'dotnet.exe'),str(destination/'Shellbags'/'Shellbags.dll'),'--help']
    subprocess.run(command,cwd=destination/'Shellbags',check=True,timeout=60)
    checks.append(dict(tool='Shellbags',help_passed=True))
    result = subprocess.run([str(destination/'Hayabusa'/'hayabusa.exe'), 'dfir-timeline', '--help'],
                            cwd=destination/'Hayabusa', capture_output=True, text=True, timeout=60)
    if result.returncode or '--no-wizard' not in result.stdout:
        raise ValueError('Contrat CLI Hayabusa non vérifié')
    checks.append(dict(tool='Hayabusa', help_passed=True))
    (destination/'verification.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    (legal/'SOURCES.txt').write_text(json.dumps(lock, indent=2)+'\nHayabusa source: '+source_url+'\n', encoding='utf-8')
    qa = destination/'qa'
    qa.mkdir(exist_ok=True)
    fixture = 'https://api.github.com/repos/Yamato-Security/hayabusa-sample-evtx/git/blobs/5e7ce922ee681277c8c8d82413bb9ba944caef54'
    with urllib.request.urlopen(fixture, timeout=60) as response:
        sample = base64.b64decode(json.load(response)['content'])
    if hashlib.sha256(sample).hexdigest() != '7645e96c6d778f96d60ce2a6f209cc4202385c9d87cc077139921270a8e9bb23':
        raise ValueError('EVTX de qualification incorrect')
    (qa/'System.evtx').write_bytes(sample)
    (legal/'QA-SOURCE.txt').write_text('EVTX public de démonstration (DeepBlueCLI), non issu d’une collecte utilisateur.\n'+fixture+'\n', encoding='utf-8')
    registry_samples = checkout/'RECmd'/'RECmd.Test'/'TestFiles'/'DFIRArtifactMuseum'
    registry_qa = qa/'registry'
    registry_qa.mkdir(exist_ok=True)
    for name in ('SYSTEM', 'SYSTEM.LOG1', 'SYSTEM.LOG2'):
        shutil.copy2(registry_samples/'Win11'/'RathbunVM'/(name+'.gz'), registry_qa/(name+'.gz'))
    shutil.copy2(registry_samples/'README.md', legal/'Registry-QA-SOURCE.md')
    fixture_license = lock['registry_fixture_license']
    with urllib.request.urlopen(fixture_license['url'], timeout=60) as response:
        notice = response.read()
    if hashlib.sha256(notice).hexdigest() != fixture_license['sha256']:
        raise ValueError('Licence DFIR Artifact Museum incorrecte')
    (legal/'DFIR-Artifact-Museum-LICENSE.txt').write_bytes(notice)
    # Preserve NuGet license declarations and bundled license files of parser dependencies.
    packages = Path(os.environ.get('NUGET_PACKAGES', Path.home()/'.nuget'/'packages'))
    for source in packages.rglob('*'):
        if source.is_file() and (source.suffix == '.nuspec' or any(s in source.name.casefold() for s in ('license', 'notice', 'copying'))):
            target = legal/'NuGet'/source.relative_to(packages)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    if not (destination/'Shellbags'/'Shellbags.dll').is_file():raise ValueError('Hôte Shellbags absent')
    (destination/'manifest.json').write_text(json.dumps(lock, indent=2), encoding='utf-8')
    stage_parser_fixtures(root, destination)
    return destination


def stage_parser_fixtures(root, destination):
    """Pinned public examples, hashed after decompression; no user evidence."""
    import gzip
    for config, group in [('forensic-qa-fixtures.json','matrix'),('forensic-browser-qa-fixtures.json','browser')]:
        entries = json.loads((Path(root)/'config'/config).read_text())
        for item in entries:
            with urllib.request.urlopen(item['url'], timeout=90) as response:
                data = response.read()
            if item['compression'] == 'gzip':
                data = gzip.decompress(data)
            if hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('Échantillon de qualification modifié : '+item['tool'])
            target = Path(destination)/'qa'/group/item['tool']/item['name']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (Path(destination)/'qa'/(group+'-sources.json')).write_text(json.dumps(entries, indent=2), encoding='utf-8')
