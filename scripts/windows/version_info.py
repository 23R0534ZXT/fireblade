"""Generate and inspect Windows PE version resources from the application version."""
from pathlib import Path
import re


def version_tuple(version):
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):
        raise ValueError('Expected a numeric X.Y.Z application version')
    values=tuple(int(value) for value in version.split('.'))+(0,)
    if any(value>65535 for value in values):
        raise ValueError('Windows version components must fit in 16 bits')
    return values


def write_version_file(path,version):
    values=version_tuple(version)
    strings={'CompanyName':'Fireblade project','FileDescription':'Fireblade forensic investigation workspace',
             'FileVersion':version,'InternalName':'Fireblade','OriginalFilename':'Fireblade.exe',
             'ProductName':'Fireblade','ProductVersion':version}
    entries=',\n'.join('StringStruct('+repr(key)+', '+repr(value)+')' for key,value in strings.items())
    text=f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={values!r}, prodvers={values!r}, mask=0x3f,
                   flags=0x2, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [{entries}])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])])
'''
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')
    return path


def read_version_resource(executable):
    import ctypes
    from ctypes import wintypes
    library=ctypes.WinDLL('version',use_last_error=True)
    library.GetFileVersionInfoSizeW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(wintypes.DWORD)]
    library.GetFileVersionInfoSizeW.restype=wintypes.DWORD
    library.GetFileVersionInfoW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
    library.GetFileVersionInfoW.restype=wintypes.BOOL
    library.VerQueryValueW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.UINT)]
    library.VerQueryValueW.restype=wintypes.BOOL
    ignored=wintypes.DWORD()
    size=library.GetFileVersionInfoSizeW(str(executable),ctypes.byref(ignored))
    if not size:raise ctypes.WinError(ctypes.get_last_error())
    data=ctypes.create_string_buffer(size)
    if not library.GetFileVersionInfoW(str(executable),0,size,data):
        raise ctypes.WinError(ctypes.get_last_error())
    def query(key):
        pointer=ctypes.c_void_p();length=wintypes.UINT()
        if not library.VerQueryValueW(data,key,ctypes.byref(pointer),ctypes.byref(length)):
            raise ValueError('Missing Windows version resource: '+key)
        return pointer.value,length.value
    pointer,length=query('\\')
    if length<52:raise ValueError('Truncated fixed Windows version resource')
    fixed=ctypes.cast(pointer,ctypes.POINTER(wintypes.DWORD*13)).contents
    if fixed[0]!=0xFEEF04BD:raise ValueError('Invalid Windows version resource signature')
    def parts(high,low):
        return [high>>16,high&65535,low>>16,low&65535]
    result={'file_version':parts(fixed[2],fixed[3]),'product_version':parts(fixed[4],fixed[5])}
    for key in ('FileVersion','ProductVersion','ProductName','OriginalFilename'):
        pointer,length=query('\\StringFileInfo\\040904B0\\'+key)
        result[key]=ctypes.wstring_at(pointer,max(0,length-1))
    return result
