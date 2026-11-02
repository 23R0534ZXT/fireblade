"""Offline bulk IOC matching: extract once, then look up canonical indicators.

No DNS/HTTP requests, SQL patterns or user-provided regular expressions. Evidence
values are never rewritten. Matches are observations, not compromise verdicts.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
import csv
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

import idna

from fireblade.core.errors import OperationCancelled, job_cancelled

MAX_INPUT_BYTES = 8 * 1024**2
MAX_IOCS = 50_000
MAX_VALUE = 8192
KINDS = {'ip':'IP', 'domain':'Domaine', 'url':'URL', 'md5':'MD5', 'sha1':'SHA-1', 'sha256':'SHA-256', 'sha512':'SHA-512'}
HASH_LENGTHS = {32:'md5', 40:'sha1', 64:'sha256', 128:'sha512'}
_HEX = re.compile(r'[a-fA-F0-9]+\Z')
_HASH = re.compile(r'(?<!\w)(?:[a-fA-F0-9]{128}|[a-fA-F0-9]{64}|[a-fA-F0-9]{40}|[a-fA-F0-9]{32})(?!\w)')
_SEP = r'(?:\.|\[\.\]|\(\.\))'
_IP4 = re.compile(r'(?<![\w.])[0-9]{1,3}(?:'+_SEP+r'[0-9]{1,3}){3}(?![\w.])')
_IP6 = re.compile(r'(?<![\w:.])[a-fA-F0-9:.]+(?:%[A-Za-z0-9_.-]+)?(?![\w:.])')
_URL = re.compile(r'(?:https?|hxxps?)(?:://|\[:\]//|\[://\])[^\s<>\x00-\x1f\"\x27`]+', re.IGNORECASE)
# Whole tokens, including Unicode marks, prevent matching a suffix of an invalid
# hostname. Validation/IDNA happens after lexical extraction, not in this regex.
_DOMAIN_TOKEN = re.compile(r'(?:\[\.\]|\(\.\)|[^\s\\/:<>\"\x27@,;!?=()\[\]{}|&#\x00-\x1f])+')
_ASCII_LABEL = re.compile(r'[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\Z')


def check_cancelled():
    if job_cancelled():raise OperationCancelled()


def deobfuscate(value):
    value = value.replace('[.]','.').replace('(.)','.').replace('[://]', '://').replace('[:]',':')
    return re.sub(r'(?i)^hxxp(s?)://', r'http\1://', value)


@lru_cache(maxsize=32768)
def normalize_ip(value):
    value=deobfuscate(value.strip())
    if value.startswith('[') and value.endswith(']'):value=value[1:-1]
    return ipaddress.ip_address(value.split('%',1)[0]).compressed.lower()


@lru_cache(maxsize=32768)
def normalize_domain(value):
    value=unicodedata.normalize('NFC',deobfuscate(value.strip())).lower().rstrip('.')
    wildcard=value.startswith('*.')
    host=value[2:] if wildcard else value
    if not host or len(host)>1024 or '.' not in host or any(c in host for c in '/:@*'):
        raise ValueError('Nom de domaine invalide')
    try:ipaddress.ip_address(host)
    except ValueError:pass
    else:raise ValueError('Utilisez le type IP pour cette adresse')
    labels=[]
    for label in host.split('.'):
        if label.isascii():
            if not _ASCII_LABEL.fullmatch(label):raise ValueError('Étiquette DNS invalide')
            labels.append(label)
        else:
            labels.append(idna.encode(label,uts46=True,transitional=False,std3_rules=True).decode('ascii'))
    host='.'.join(labels)
    if len(host)>253:raise ValueError('Nom de domaine supérieur à 253 octets')
    return ('*.' if wildcard else '')+host


@lru_cache(maxsize=4096)
def normalize_url(value):
    value=deobfuscate(value.strip())
    if len(value)>MAX_VALUE or any(c.isspace() or ord(c)<32 for c in value):raise ValueError('URL invalide ou trop longue')
    parts=urlsplit(value)
    if parts.scheme.lower() not in ('http','https') or not parts.hostname:raise ValueError('URL HTTP ou HTTPS attendue')
    host=parts.hostname
    try:
        address=ipaddress.ip_address(host)
        host='['+address.compressed.lower()+']' if address.version==6 else str(address)
    except ValueError:
        host=host.lower() if host.isascii() and _ASCII_LABEL.fullmatch(host) else normalize_domain(host)
        if host.startswith('*.'):raise ValueError('Hôte URL générique interdit')
    port=parts.port  # Invalid/out-of-range ports raise rather than disappearing.
    if port is not None and port!={'http':80,'https':443}[parts.scheme.lower()]:host+=':'+str(port)
    if '@' in parts.netloc:host=parts.netloc.rsplit('@',1)[0]+'@'+host
    return urlunsplit((parts.scheme.lower(),host,parts.path or '/',parts.query,parts.fragment))


def type_key(value):
    value=''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]','',value)


@dataclass(frozen=True)
class Indicator:
    kind: str
    value: str
    raw: str
    label: str = ''


@dataclass
class IndicatorBatch:
    indicators: list[Indicator] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    duplicates: int = 0
    origin: dict = field(default_factory=dict)

    @property
    def sha256(self):
        payload=[[ioc.kind,ioc.value,ioc.label] for ioc in self.indicators]
        return hashlib.sha256(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()


def indicator(value, declared='', label=''):
    raw=value.strip()
    if not raw or len(raw)>MAX_VALUE or any(ord(c)<32 for c in raw):raise ValueError('Valeur vide, caractères de contrôle ou plus de 8192 caractères')
    if len(label)>2000 or any(ord(c)<32 and c not in '\t\r\n' for c in label):raise ValueError('Libellé invalide ou supérieur à 2000 caractères')
    value=deobfuscate(raw)
    aliases={'ip':'ip','adresseip':'ip','ipv4':'ip','ipv6':'ip','ipv4addr':'ip','ipv6addr':'ip',
             'domain':'domain','domainname':'domain','domaine':'domain','hostname':'domain',
             'url':'url','uri':'url','md5':'md5','sha1':'sha1','sha256':'sha256','sha512':'sha512','hash':'hash','empreinte':'hash'}
    declared_key=type_key(declared)
    kind=aliases.get(declared_key) if declared_key else None
    if declared_key and kind is None:raise ValueError('Type non pris en charge : '+declared)
    if kind is None:
        if '://' in value:kind='url'
        else:
            try:normalize_ip(value);kind='ip'
            except ValueError:
                kind=HASH_LENGTHS.get(len(value)) if _HEX.fullmatch(value) else 'domain'
    if kind=='ip':
        normalized=normalize_ip(value)
        version=ipaddress.ip_address(normalized).version
        if declared_key in ('ipv4','ipv4addr') and version!=4 or declared_key in ('ipv6','ipv6addr') and version!=6:
            raise ValueError('Version IP différente du type déclaré')
    elif kind=='domain':normalized=normalize_domain(value)
    elif kind=='url':normalized=normalize_url(value)
    elif kind=='hash' or kind in HASH_LENGTHS.values():
        actual=HASH_LENGTHS.get(len(value))
        if actual is None or not _HEX.fullmatch(value) or kind!='hash' and actual!=kind:
            raise ValueError('Empreinte hexadécimale MD5 / SHA-1 / SHA-256 / SHA-512 attendue')
        kind=actual;normalized=value.lower()
    else:raise ValueError('Type non reconnu : IP, domaine, URL ou empreinte attendu')
    return Indicator(kind,normalized,raw,label.strip())


def parse_indicators(text, format=None):
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_INPUT_BYTES:raise ValueError('Liste IOC limitée à 8 Mio')
    text=text.lstrip('\ufeff');batch=IndicatorBatch();seen=set()
    sample=next((line for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')),'')
    delimiter='\t' if format=='tsv' else ','
    try:delimiter=csv.Sniffer().sniff(sample,delimiters=',;\t').delimiter
    except csv.Error:pass
    first=next(csv.reader([sample],delimiter=delimiter),[])
    values={'ioc','indicator','indicateur','value','valeur','observable'}
    is_header=bool(values.intersection(type_key(h) for h in first))
    structured=format in ('csv','tsv') or is_header
    def add(line,value,kind='',label=''):
        check_cancelled()
        if len(batch.indicators)+len(batch.rejected)+batch.duplicates>=MAX_IOCS:
            raise ValueError('Liste limitée à 50000 indicateurs (doublons et rejets compris)')
        try:
            ioc=indicator(value,kind,label)
            key=(ioc.kind,ioc.value)
            if key in seen:batch.duplicates+=1
            else:seen.add(key);batch.indicators.append(ioc)
        except (ValueError,UnicodeError) as exc:
            batch.rejected.append(dict(line=line,value=value[:MAX_VALUE],reason=str(exc)[:500]))
    if structured:
        reader=csv.reader(io.StringIO(text,newline=''),delimiter=delimiter,strict=True)
        header=None
        try:
            for row in reader:
                if not row or len(row)==1 and (not row[0].strip() or row[0].lstrip().startswith('#')):continue
                if header is None and is_header:
                    header=[type_key(h) for h in row]
                    choices=[i for i,h in enumerate(header) if h in values]
                    if len(choices)!=1:raise ValueError('Une seule colonne IOC / value / valeur est requise')
                    value_at=choices[0]
                    type_at=next((i for i,h in enumerate(header) if h in ('type','kind','categorie')),None)
                    label_at=next((i for i,h in enumerate(header) if h in ('label','libelle','name','nom','description','comment','commentaire')),None)
                    continue
                if header is not None:
                    if len(row)!=len(header):add(reader.line_num,'','', '');batch.rejected[-1]['reason']='Nombre de colonnes CSV incohérent';continue
                    add(reader.line_num,row[value_at],row[type_at] if type_at is not None else '',row[label_at] if label_at is not None else '')
                elif len(row)==1:add(reader.line_num,row[0])
                else:raise ValueError('CSV à plusieurs colonnes : ajoutez les en-têtes type,value,label')
        except csv.Error as exc:raise ValueError('CSV IOC invalide : '+str(exc)) from exc
    else:
        for number,line in enumerate(text.splitlines(),1):
            if line.strip() and not line.lstrip().startswith('#'):add(number,line)
    return batch


def read_indicator_file(path):
    path=Path(path)
    with path.open('rb') as stream:data=stream.read(MAX_INPUT_BYTES+1)
    if len(data)>MAX_INPUT_BYTES:raise ValueError('Liste IOC limitée à 8 Mio')
    encoding='utf-8-sig'
    if data.startswith((b'\xff\xfe\x00\x00',b'\x00\x00\xfe\xff')):encoding='utf-32'
    elif data.startswith((b'\xff\xfe',b'\xfe\xff')):encoding='utf-16'
    try:text=data.decode(encoding)
    except UnicodeDecodeError:text=data.decode('cp1252')
    batch=parse_indicators(text,path.suffix.lower().lstrip('.'))
    batch.origin=dict(path=str(path.resolve()),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    return batch


class IndicatorMatcher:
    def __init__(self, indicators, include_subdomains=True):
        self.maps={kind:defaultdict(list) for kind in KINDS}
        self.include_subdomains=include_subdomains
        for number,ioc in enumerate(indicators,1):
            if indicator(ioc.raw,ioc.kind,ioc.label).value!=ioc.value:raise ValueError('IOC normalisé incohérent')
            value=ioc.value[2:] if ioc.kind=='domain' and ioc.value.startswith('*.') else ioc.value
            self.maps[ioc.kind][value].append((number,ioc.value.startswith('*.')))

    def matches(self, text):
        """One hit per IOC and cell; repeated occurrences do not inflate counts."""
        seen=set()
        def exact(kind,value,observed,at,rule):
            for number,_ in self.maps[kind].get(value,()):
                if number not in seen:seen.add(number);yield number,observed,at,rule
        if self.maps['ip']:
            for match in _IP4.finditer(text):
                check_cancelled()
                try:value=normalize_ip(match.group())
                except ValueError:continue
                yield from exact('ip',value,match.group(),match.start(),'Adresse IP normalisée')
            for match in _IP6.finditer(text):
                check_cancelled()
                raw=match.group()
                if raw.count(':')<2 or len(raw)>128:continue
                try:value=normalize_ip(raw)
                except ValueError:continue
                yield from exact('ip',value,raw,match.start(),'Adresse IP normalisée')
        if any(self.maps[k] for k in HASH_LENGTHS.values()):
            for match in _HASH.finditer(text):
                check_cancelled()
                yield from exact(HASH_LENGTHS[len(match.group())],match.group().lower(),match.group(),match.start(),'Empreinte exacte')
        if self.maps['url']:
            for match in _URL.finditer(text):
                check_cancelled()
                raw=match.group()
                if len(raw)>MAX_VALUE:continue
                # Try the full URL before treating terminal prose punctuation as
                # a delimiter. The retained rule makes this distinction visible.
                variants=[(raw,'URL normalisée')]
                trimmed=raw.rstrip('.,;')
                for closer,opener in ((')', '('),(']', '['),('}', '{')):
                    while trimmed.endswith(closer) and trimmed.count(closer)>trimmed.count(opener):trimmed=trimmed[:-1]
                if trimmed!=raw:variants.append((trimmed,'URL — ponctuation finale ignorée'))
                for value,rule in variants:
                    try:normalized=normalize_url(value)
                    except (ValueError,UnicodeError):continue
                    yield from exact('url',normalized,raw,match.start(),rule)
        if self.maps['domain']:
            for match in _DOMAIN_TOKEN.finditer(text):
                check_cancelled()
                raw=match.group()
                if len(raw)>1024 or '.' not in raw or match.end()<len(text) and text[match.end()]=='@':continue
                try:value=normalize_domain(raw)
                except (ValueError,UnicodeError):continue
                labels=value.split('.')
                for offset in range(len(labels)-1):
                    suffix='.'.join(labels[offset:])
                    for number,wildcard in self.maps['domain'].get(suffix,()):
                        if number in seen or wildcard and offset==0 or not wildcard and offset>0 and not self.include_subdomains:continue
                        seen.add(number)
                        yield number,raw,match.start(),'Sous-domaine' if offset else 'Domaine exact'
