"""Case-scoped CLR references. Evidence objects never round-trip through JSON.

Only opaque references and approved file provenance cross the helper pipe.
The helper recreates the reader's graph lazily and owns its lifetime.
"""
import json
from fireblade.core.plugin_registry import approved_for_analysis,digest


def has_reference(value):
    if isinstance(value,dict):
        return value.get('$fb_type') in ('clr_column','clr_path','clr_handle','clr_single') or any(has_reference(v) for v in value.values())
    return isinstance(value,list) and any(has_reference(v) for v in value)


def has_column(value):
    if isinstance(value,dict):return value.get('$fb_type')=='clr_column' or any(has_column(v) for v in value.values())
    return isinstance(value,list) and any(has_column(v) for v in value)


def complex_column(column):
    if 'complex' in column:return column['complex'] is True
    clr=column.get('type','') or ''
    scalar=('String','Boolean','Char','SByte','Byte','Int16','UInt16','Int32','UInt32','Int64','UInt64','Single','Double','Decimal','DateTime','DateTimeOffset')
    return bool(clr) and not any(clr=='System.'+name or clr.startswith('System.Nullable`1[[System.'+name+',') for name in scalar)


class ObjectSession:
    def __init__(self,case,function):
        from fireblade.core.tle_plugins import FunctionSession
        self.case=case;self.reader=case.info.get('plugin');self.reader_path=None
        if digest(function.path)!=function.sha256:raise ValueError('DLL de fonctions modifiée : '+str(function.path))
        if self.reader:self.reader_path=approved_for_analysis(case.path,self.reader['sha256'])
        self.session=FunctionSession(function.path,case.check_cancelled,host_plugin=self.reader_path)
        self.loaded={function.path};self.reader_loaded=False;self.handles=False

    def evaluate(self,function,name,arguments,reference):
        if function.path not in self.loaded:
            if digest(function.path)!=function.sha256:raise ValueError('DLL de fonctions modifiée : '+str(function.path))
            self.session.request(dict(op='load_functions',path=str(function.path),sha256=function.sha256))
            self.loaded.add(function.path)
        if has_column(arguments) and not self.reader_loaded:
            if not self.reader:raise ValueError('Aucun lecteur CLR associé à cette analyse')
            # Approval belongs to this analysis, not to an untrusted serialized path.
            path=approved_for_analysis(self.case.path,self.reader['sha256'])
            self.session.request(dict(op='load_reader',path=str(path),sha256=self.reader['sha256'],
                source=self.case.info['path'],source_sha256=self.case.info['sha256'],
                type=self.reader['type'],rows=self.case.info['rows'],converted_sha256=self.reader.get('converted_sha256')),timeout=3600)
            self.reader_loaded=True
        result=self.session.request(dict(name=name,arguments=arguments,reference=reference))
        if reference:
            self.handles=True
            return json.dumps(result['operand'],ensure_ascii=False)
        return result['value']

    def clear_handles(self):
        if self.handles:
            self.session.request(dict(op='clear_handles'))
            self.handles=False

    def close(self):self.session.close()


def evaluate(case,name,arguments,reference=False):
    function=case._plugin_functions.get(name.casefold())
    if function is None:raise ValueError('Fonction .NET non chargée : '+name)
    if not reference and not has_reference(arguments):return function.evaluate(name,arguments)
    with case._plugin_object_lock:
        case.check_cancelled()
        session=case._plugin_object_session
        if session is None or session.session.process.poll() is not None:
            if session is not None:session.close()
            session=ObjectSession(case,function);case._plugin_object_session=session
        try:return session.evaluate(function,name,arguments,reference)
        except BaseException:
            session.close();case._plugin_object_session=None
            raise
