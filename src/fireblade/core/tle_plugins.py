"""Explicit .NET reader imports, isolated in a cancellable helper process."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from fireblade.runtime.resources import resource_path


def host_command():
    override=os.environ.get('FIREBLADE_PLUGIN_HOST')
    path=Path(override) if override else resource_path('plugin-host/Fireblade.PluginHost.exe')
    if not path.is_file():
        # Source checkouts may use the published helper produced by the build script.
        path=Path(__file__).resolve().parents[3]/'build/windows/plugin-host/Fireblade.PluginHost.exe'
    if not path.is_file():raise ValueError('Hôte de plugins absent : construire Fireblade avec le SDK .NET 10')
    return [os.environ.get('FIREBLADE_DOTNET','dotnet'),str(path)] if path.suffix.lower()=='.dll' else [str(path)]


def terminate(process):
    if process.poll() is not None:return
    if os.name=='nt':
        try:subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except (OSError,subprocess.TimeoutExpired):pass
    if process.poll() is None:process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()


def run_host(arguments,check_cancelled=lambda:None,timeout=3600):
    with tempfile.TemporaryDirectory(prefix='fireblade-plugin-') as folder:
        stdout=Path(folder)/'stdout.log';stderr=Path(folder)/'stderr.log'
        with stdout.open('wb') as out,stderr.open('wb') as err:
            process=subprocess.Popen(host_command()+list(map(str,arguments)),stdout=out,stderr=err,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            start=time.monotonic()
            try:
                while process.poll() is None:
                    check_cancelled()
                    if time.monotonic()-start>timeout:raise TimeoutError('Le plugin a dépassé son délai')
                    time.sleep(.05)
                check_cancelled()
            finally:
                if process.poll() is None:
                    terminate(process)
        def tail(path):
            with path.open('rb') as stream:
                stream.seek(max(0,path.stat().st_size-1024*1024));return stream.read().decode('utf-8-sig',errors='replace')
        if process.returncode:raise ValueError('Échec du plugin TLE : '+tail(stderr)[-12000:])
        for line in reversed(tail(stdout).splitlines()):
            try:return json.loads(line)
            except json.JSONDecodeError:continue
        raise ValueError('Le plugin n’a pas produit de résultat valide')


def inspect_plugin(path,check_cancelled=lambda:None):
    return run_host(['inspect',Path(path).resolve()],check_cancelled,60)


def import_plugin(case,source,plugin,type_name,progress=lambda _:None):
    source,plugin=Path(source).resolve(),Path(plugin).resolve()
    def digest(path):
        h=hashlib.sha256()
        with path.open('rb') as stream:
            while data:=stream.read(4*1024*1024):case.check_cancelled();h.update(data)
        return h.hexdigest()
    progress('Plugin TLE · contrôle de la source…')
    original=digest(source);stat=source.stat();plugin_hash=digest(plugin)
    with tempfile.TemporaryDirectory(prefix='.fireblade-plugin-',dir=case.path.parent) as directory:
        target=Path(directory)/'converted.csv'
        progress('Plugin TLE · conversion dans le processus .NET…')
        result=run_host(['convert',plugin,type_name,source,target],case.check_cancelled)
        if digest(source)!=original or stat.st_size!=source.stat().st_size:
            raise ValueError('La source a changé pendant son traitement par le plugin')
        provenance=dict(path=str(source),size=stat.st_size,sha256=original,format='tle-plugin',
            plugin=dict(path=str(plugin),sha256=plugin_hash,type=type_name,columns=result['columns'],transformed=True))
        info=case._import_table(target,',','utf-8',progress,provenance=provenance)
        if info['rows']!=result['rows']:raise ValueError('Comptage du plugin incohérent')
        return info


class FunctionSession:
    """One persistent host per selected DLL; pipe waits remain cancellable."""
    def __init__(self,path,check_cancelled):
        import queue,threading
        self.check=check_cancelled;self.responses=queue.Queue();self.lock=threading.Lock()
        self.logs=tempfile.TemporaryFile('w+b')
        self.process=subprocess.Popen(host_command()+['serve',str(Path(path).resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.logs,text=True,encoding='utf-8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def read():
            try:
                for line in self.process.stdout:
                    try:self.responses.put(json.loads(line))
                    except json.JSONDecodeError:continue
            finally:self.responses.put({'error':'Hôte de fonctions terminé'})
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        try:
            ready=self.wait(60)
            if not ready.get('ready'):raise ValueError('Hôte de fonctions invalide')
            self.names=ready['functions']
            self.types={name.casefold():kind for name,kind in ready.get('types',{}).items()}
        except BaseException:self.close();raise
    def wait(self,timeout):
        import queue
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.check()
            try:
                result=self.responses.get(timeout=.05)
                if 'error' in result:raise ValueError(result['error'])
                return result
            except queue.Empty:continue
        raise TimeoutError('Délai dépassé dans une fonction du plugin')
    def evaluate(self,name,arguments):
        with self.lock:
            try:
                self.check();self.process.stdin.write(json.dumps(dict(name=name,arguments=arguments),ensure_ascii=False)+'\n');self.process.stdin.flush()
                return self.wait(60)['value']
            except BaseException:self.close();raise
    def close(self):
        terminate(self.process)
        if self.reader is not __import__('threading').current_thread():self.reader.join(timeout=2)
        if self.process.stdin:self.process.stdin.close()
        if self.process.stdout and not self.reader.is_alive():self.process.stdout.close()
        self.logs.close()


def _register_functions(case,path):
    if not case._plugin_udf:
        def plugin_scalar(name,payload):
            session=case._plugin_functions.get(name.casefold())
            if session is None:raise ValueError('Fonction .NET non chargée : '+name)
            return session.evaluate(name,json.loads(payload))
        case.db.create_function('__fireblade_plugin_eval',plugin_scalar,['VARCHAR','VARCHAR'],'VARCHAR',null_handling='special',side_effects=True)
        case._plugin_udf=True
    session=FunctionSession(path,case.check_cancelled)
    if not session.names:session.close();raise ValueError('Aucune fonction Evaluate(object[]) avec propriété Name trouvée')
    overlap=set(n.casefold() for n in session.names)&set(case._plugin_functions)
    if overlap:session.close();raise ValueError('Fonctions déjà chargées : '+', '.join(sorted(overlap)))
    for name in session.names:case._plugin_functions[name.casefold()]=session
    from fireblade.core.expressions import register_function_metadata
    register_function_metadata(session.types)
    case._plugin_sessions.append(session)
    return session.names


def register_functions(case,path):
    with case.operation():return _register_functions(case,path)
