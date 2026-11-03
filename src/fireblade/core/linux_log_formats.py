"""Additional log payload schemas; all interpretations retain source text."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import json
import re


def utc_time(value, epoch=False):
    """Normalize only explicitly zoned dates/Unix epochs; never infer local time."""
    try:
        if epoch:
            from fireblade.core.linux_logs import timestamp
            number = Decimal(str(value))
            seconds = int(number.to_integral_value(rounding=ROUND_FLOOR))
            fraction = format(number-seconds,'f').partition('.')[2]
            base = timestamp(seconds)
            return base[:-6]+('.'+fraction.ljust(6,'0') if fraction else '')+'+00:00'
        value = str(value)
        if not re.search(r'(?:Z|[+-]\d{2}:?\d{2})$', value):
            return ''
        result = datetime.fromisoformat(value).astimezone(timezone.utc)
        fraction = re.search(r'\d{2}:\d{2}:\d{2}[.,](\d+)',value)
        if fraction:
            return result.replace(microsecond=0).isoformat()[:-6]+'.'+fraction[1]+'+00:00'
        return result.isoformat()
    except (InvalidOperation, ValueError, OverflowError):
        return ''


def audit_value(value):
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if re.fullmatch(r'(?:[0-9a-fA-F]{2})+', value):
        return bytes.fromhex(value).decode('utf-8','backslashreplace').replace('\0',' ␀ ')
    return value


def enrich(fields, text):
    fields = dict(fields)
    fmt = fields.get('Format','')
    message = fields.get('Détail', text)
    if fmt == 'Linux audit':
        pairs = json.loads(fields['Champs'])
        for key,target in [('exe','Chemin'),('comm','Processus'),('name','Chemin'),('cwd','Dossier'),('proctitle','Commande')]:
            if key in pairs:
                fields[target] = audit_value(pairs[key])
        fields['Horodatage UTC'] = utc_time(fields['Horodatage'],epoch=True)
        fields['Clé de corrélation'] = fields.get('Hôte','')+'|'+fields['Horodatage']+':'+fields['Événement']
    else:
        fields['Horodatage UTC'] = utc_time(fields.get('Horodatage',''))
    ssh = re.search(r'\b(Accepted|Failed) (\S+) for (invalid user )?(\S+) from (\S+) port (\d+)', message) if ' for ' in message and ' from ' in message else None
    if ssh:
        fields.update(Utilisateur=ssh[4], **{'Adresse distante':ssh[5], 'Port distant':ssh[6],
                                           'Événement':'SSH '+ssh[1], 'Statut':ssh[1]})
    if 'TTY=' in message and 'COMMAND=' in message:
        user, separator, payload = message.partition(':')
        parts = payload.split(';',3)
        if separator and len(parts)==4 and re.fullmatch(r'\S+',user.strip()):
            pairs = [part.strip().partition('=') for part in parts]
            if [part[0] for part in pairs]==['TTY','PWD','USER','COMMAND'] and all(part[1] for part in pairs):
                fields.update(Utilisateur=user.strip(), Dossier=pairs[1][2], Commande=pairs[3][2],
                              **{'Événement':'sudo', 'Utilisateur cible':pairs[2][2]})
    ufw = re.search(r'\[UFW ([^\]]+)\]',message)
    if ufw:
        pairs = dict(re.findall(r'\b([A-Z]+)=(\S*)',message))
        fields.update(Statut=ufw[1], **{'Événement':'UFW'})
        for key,target in [('SRC','Adresse source'),('DST','Adresse destination'),('SPT','Port source'),('DPT','Port destination'),('PROTO','Protocole')]:
            fields[target] = pairs.get(key,'')
        fields['Champs'] = json.dumps(pairs,ensure_ascii=False)
    cef = re.search(r'(?:^|\s)CEF:(\d+)\|',message) if 'CEF:' in message else None
    if cef:
        # Split only unescaped pipes; preserve raw extension values in Champs.
        parts = re.split(r'(?<!\\)\|',message[cef.start():].lstrip(),maxsplit=7)
        if len(parts)==8:
            fields['Format'] = 'CEF'
            header = [v.replace(r'\|','|').replace('\\\\','\\') for v in parts[:7]]
            extension = {}
            matches = list(re.finditer(r'(?:^| )([A-Za-z][A-Za-z0-9]*)=',parts[7]))
            for index,match in enumerate(matches):
                end = matches[index+1].start() if index+1<len(matches) else len(parts[7])
                extension[match[1]] = parts[7][match.end():end].replace(r'\=','=').replace(r'\n','\n').replace(r'\r','\r')
            fields['Champs'] = json.dumps({'header':header,'extension':extension},ensure_ascii=False)
            fields['Événement'] = header[4]
            fields['Statut'] = header[6]
            for key,target in [('src','Adresse source'),('dst','Adresse destination'),('suser','Utilisateur'),('request','Chemin')]:
                if key in extension:fields[target]=extension[key]
    return fields


def rfc5424_body(value):
    """Split structured data and MSG without treating escaped brackets as ends."""
    if value=='-':
        return '-', ''
    if value.startswith('- '):
        return '-', value[2:]
    if not value.startswith('['):
        return None
    quoted = escaped = False
    for index,char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char=='\\' and quoted:
            escaped = True
        elif char=='"':
            quoted = not quoted
        elif char==']' and not quoted:
            end=index+1
            if end==len(value):
                return value, ''
            if value[end]=='[':
                continue
            if value[end]==' ':
                return value[:end], value[end+1:]
            return None
    return None
