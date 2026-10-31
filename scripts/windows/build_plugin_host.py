"""Build the optional self-contained .NET reader host for the onefile bundle."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def build(root,python=None):
    root=Path(root).resolve();dotnet=os.environ.get('FIREBLADE_DOTNET') or shutil.which('dotnet')
    if not dotnet:raise RuntimeError('Installer le SDK .NET 10 pour construire l’hôte de plugins intégré')
    output=root/'build/windows/plugin-host';fixture=root/'build/windows/plugin-fixture'
    for directory in (output,fixture):
        if directory.exists():shutil.rmtree(directory)
        directory.mkdir(parents=True)
    project=root/'src/fireblade/plugin_host/Fireblade.PluginHost.csproj'
    subprocess.run([dotnet,'publish',str(project),'-c','Release','-r','win-x64','--self-contained','true','-p:DebugType=none','-p:IncludeAllContentForSelfExtract=true','-o',str(output)],check=True)
    subprocess.run([dotnet,'build',str(project.parent/'qa/Fixture.csproj'),'-c','Release','-p:DebugType=none','-o',str(fixture)],check=True)
    host=output/'Fireblade.PluginHost.exe'
    subprocess.run([str(host),'--self-test'],check=True,timeout=120)
    import sys
    environment=os.environ.copy();environment['PYTHONPATH']=str(root/'src')
    subprocess.run([str(python or sys.executable),'-m','scripts.windows.verify_plugin_host','--host',str(host),'--fixture',str(fixture/'Fireblade.PluginFixture.dll')],env=environment,check=True,timeout=120)
    subprocess.run([str(python or sys.executable),'-m','scripts.windows.verify_upstream_plugin','--host',str(host),'--out',str(root/'artifacts/windows-upstream-plugin.json')],env=environment,check=True,timeout=360)
    generated=root/'build/windows/resources';legal=generated/'legal/dotnet';legal.mkdir(parents=True,exist_ok=True)
    cache_output=subprocess.check_output([dotnet,'nuget','locals','global-packages','--list'],text=True)
    cache=Path(next(line.split(': ',1)[1] for line in cache_output.splitlines() if line.startswith('global-packages:')))
    packages=[]
    for package in sorted(cache.glob('microsoft.*.runtime.win-x64')):
        for version in package.iterdir():
            if not version.is_dir():continue
            notices=[]
            for file in version.iterdir():
                if file.is_file() and any(key in file.name.lower() for key in ('license','notice')):
                    target=legal/package.name/version.name/file.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
                    notices.append(str(target.relative_to(generated/'legal')).replace('\\','/'))
            if notices:packages.append(dict(name=package.name,version=version.name,license='MIT / third-party notices',notices=notices))
    if not any('netcore' in p['name'] for p in packages) or not any('windowsdesktop' in p['name'] for p in packages):raise RuntimeError('Licences des runtimes .NET introuvables')
    metadata=generated/'legal/DEPENDENCIES.json';items=json.loads(metadata.read_text(encoding='utf-8'));metadata.write_text(json.dumps(items+packages,indent=2),encoding='utf-8')
    info_path=generated/'build/build-info.json';info=json.loads(info_path.read_text(encoding='utf-8'));info['plugin_host']=dict(framework='net10.0-windows',self_contained=True,sdk=subprocess.check_output([dotnet,'--version'],text=True).strip());info_path.write_text(json.dumps(info,indent=2),encoding='utf-8')
    return host


if __name__=='__main__':build(Path(__file__).resolve().parents[2])
