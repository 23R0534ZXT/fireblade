"""Format positional criteria parameters as typed, escaped data literals."""
import datetime
from decimal import Decimal
import math
import uuid


def constant(value):
    if value is None:return 'Null'
    if type(value) is bool:return 'True' if value else 'False'
    if isinstance(value,str):return "'"+value.replace("'","''")+"'"
    if isinstance(value,uuid.UUID):return '{'+str(value)+'}'
    if isinstance(value,datetime.datetime):return '#'+value.isoformat()+'#'
    if isinstance(value,datetime.date):return '#!'+value.isoformat()+'!#'
    if isinstance(value,datetime.time):return '#!'+value.isoformat()+'!#'
    if isinstance(value,(int,float,Decimal)):
        if isinstance(value,float) and not math.isfinite(value) or isinstance(value,Decimal) and not value.is_finite():raise ValueError('Paramètre numérique non fini')
        return str(value)+('m' if isinstance(value,Decimal) else 'd' if isinstance(value,float) else '')
    raise ValueError('Type de paramètre de critère non pris en charge')


def bind(text,parameters=None):
    if not isinstance(text,str) or len(text)>65536:raise ValueError('Expression limitée à 64 Ko')
    values=list(parameters or [])
    if len(values)>4096:raise ValueError('4096 paramètres au maximum')
    import re
    result=[];index=0;i=0;quote=None;previous=''
    while i<len(text):
        char=text[i]
        if quote:
            result.append(char)
            if char==quote:
                if quote!="#" and i+1<len(text) and text[i+1]==quote:result.append(char);i+=2;continue
                quote=None
        elif char in ("'",'"','#'):quote=char;result.append(char)
        elif char=='[' and previous!=']':
            field=re.match(r'\[(?:[^\[\]]|\]\])*\]',text[i:])
            if field:
                result.append(field.group());i+=field.end();previous=']';continue
            result.append(char)
        elif char=='?':
            result.append(constant(values[index] if index<len(values) else None));index+=1
        else:result.append(char)
        if not char.isspace():previous=char
        i+=1
    if len(values)>index:raise ValueError('Trop de paramètres pour les emplacements du critère')
    rendered=''.join(result)
    if len(rendered)>65536:raise ValueError('Expression liée limitée à 64 Ko')
    return rendered
