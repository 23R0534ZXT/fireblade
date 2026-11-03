"""Offline Linux log reader; streaming input, explicit provenance and dispositions.

Never executes collected files. Unknown text remains raw; unsupported binaries
and malformed/truncated records are reported. Timestamps retain source semantics.
"""
import bz2
import csv
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile
import tempfile

from fireblade.core.errors import OperationCancelled
from fireblade.core.catscale import check_cancel, safe_member

HEADERS = ['Format', 'Lecture', 'Horodatage', 'Hôte', 'Processus', 'PID', 'PPID',
           'Utilisateur', 'UID', 'Adresse distante', 'Méthode', 'Chemin', 'Statut',
           'Octets', 'Événement', 'Détail', 'Champs', 'Source', 'Ligne',
           'Fin de ligne', 'Offset', 'Texte brut']
MAX_LINE = 8 * 1024 * 1024
MAX_OBJECT = 64 * 1024 * 1024
MAX_EXPANDED = 1024 ** 4  # Per input, including archive traversal (1 TiB).
MAX_MEMBERS = 100000
MAX_DEPTH = 8
COMPRESSIONS = ('.gz', '.bz2', '.xz', '.lzma', '.zst', '.zstd')
KNOWN = re.compile(r'^(?:syslog|messages|secure|auth\.log|kern\.log|daemon\.log|'
                   r'user\.log|mail\.(?:log|info|warn|err)|cron|boot\.log|dmesg|'
                   r'audit\.log|access\.log|error\.log|dpkg\.log|alternatives\.log|'
                   r'fail2ban\.log|ufw\.log|wtmp|btmp|utmp|lastlog)(?:[.-].*)?$')


def plain_name(path):
    name = PurePosixPath(str(path).replace('\\', '/')).name.casefold()
    while name.endswith(COMPRESSIONS):
        name = name.rsplit('.', 1)[0]
    return name


def recognized(path, magic=b''):
    parts = str(path).replace('\\', '/').casefold().split('/')
    in_var_log = any(parts[i:i+2] == ['var', 'log'] for i in range(len(parts)-1))
    name = plain_name(path)
    return bool(in_var_log or 'log' in parts[:-1] or KNOWN.fullmatch(name)
                or re.fullmatch(r'(?:var[-_]log|linux[-_]logs).*\.(?:tar|tgz)', name)
                or re.search(r'\.log(?:[.-].*)?$', name) or name.endswith(('.journal', '.journal~'))
                or magic.startswith(b'LPKSHHRH'))


def display(value):
    return value.decode('utf-8', 'backslashreplace') if isinstance(value, bytes) else str(value)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def text_fields(text, path=''):
    """Decode one physical line without guessing a year, timezone or custom schema."""
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith('{'):
        try:
            obj = json.loads(stripped)
        except (ValueError, RecursionError):
            pass
        else:
            if isinstance(obj, dict):
                fields = {'Format': 'JSON Lines', 'Champs': encoded(obj)}
                for keys, target in [(('timestamp', '@timestamp', 'time', 'ts'), 'Horodatage'),
                                     (('hostname', 'host', '_HOSTNAME'), 'Hôte'),
                                     (('message', 'msg', 'MESSAGE'), 'Détail'),
                                     (('pid', '_PID'), 'PID')]:
                    for key in keys:
                        if key in obj:
                            fields[target] = encoded(obj[key]) if isinstance(obj[key], (dict, list)) else str(obj[key])
                            break
                return fields
    audit = re.match(r'(?:node=(\S+)\s+)?type=(\S+)\s+msg=audit\(([^:]+):(\d+)\):\s*(.*)', stripped)
    if audit:
        fields = {'Format': 'Linux audit', 'Hôte': audit[1] or '', 'Horodatage': audit[3],
                  'Événement': audit[4], 'Détail': audit[5]}
        pairs = dict(re.findall(r'\b([\w]+)=("[^"\n]*"|\S+)', stripped))
        fields['Champs'] = encoded(pairs)
        for key, target in [('pid', 'PID'), ('ppid', 'PPID'), ('uid', 'UID'), ('auid', 'Utilisateur'),
                            ('exe', 'Chemin'), ('addr', 'Adresse distante')]:
            if key in pairs:
                fields[target] = pairs[key].strip('"')
        # Each audit record keeps its event serial; no adjacency-based merging.
        return fields
    rfc5424 = re.match(r'^<(\d{1,3})>([1-9]\d*) (\S+) (\S+) (\S+) (\S+) (\S+) (.*)$', stripped)
    if rfc5424:
        # Structured data may contain spaces: preserve its full syntax verbatim.
        return {'Format': 'Syslog RFC5424', 'Horodatage': rfc5424[3], 'Hôte': rfc5424[4],
                'Processus': rfc5424[5], 'PID': rfc5424[6], 'Événement': rfc5424[7],
                'Détail': rfc5424[8], 'Champs': encoded({'priority': rfc5424[1], 'version': rfc5424[2]})}
    syslog = re.match(r'^(?:<\d{1,3}>)?(\w{3}\s+\d{1,2}\s+\d\d:\d\d:\d\d|'
                      r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d\S*)\s+(\S+)\s+'
                      r'([^\s:\[]+)(?:\[(\d+)\])?:\s?(.*)$', stripped)
    if syslog:
        return {'Format': 'Syslog', 'Horodatage': syslog[1], 'Hôte': syslog[2],
                'Processus': syslog[3], 'PID': syslog[4] or '', 'Détail': syslog[5]}
    web = re.match(r'^(\S+) (\S+) (\S+) \[([^\]]+)\] "([^"\n]*)" (\d{3}|-) (\d+|-)(.*)$', stripped)
    if web:
        request = web[5].split(' ', 2)
        return {'Format': 'HTTP access', 'Horodatage': web[4], 'Adresse distante': web[1],
                'Utilisateur': web[3], 'Méthode': request[0], 'Chemin': request[1] if len(request)>1 else '',
                'Statut': web[6], 'Octets': web[7], 'Détail': web[8]}
    kernel = re.match(r'^\[\s*(\d+(?:\.\d+)?)\]\s*(.*)', stripped)
    if kernel:
        return {'Format': 'Kernel monotonic', 'Horodatage': kernel[1], 'Détail': kernel[2]}
    dated = re.match(r'^(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?)\s+(.*)', stripped)
    if dated:
        return {'Format': 'Application timestamp', 'Horodatage': dated[1], 'Détail': dated[2]}
    nginx = re.match(r'^(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d) \[([^\]]+)\] (\d+)#\d+: (.*)', stripped)
    if nginx:
        return {'Format': 'Nginx error', 'Horodatage': nginx[1], 'Statut': nginx[2], 'PID': nginx[3], 'Détail': nginx[4]}
    apache = re.match(r'^\[([^\]]+)\]\s+\[([^\]]+)\](.*)', stripped)
    if apache and re.search(r'\d\d:\d\d:\d\d', apache[1]):
        return {'Format': 'Apache error', 'Horodatage': apache[1], 'Statut': apache[2], 'Détail': apache[3]}
    return {}


def timestamp(seconds, micros=0):
    try:
        return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds, microseconds=micros)).isoformat()
    except (OverflowError, ValueError):
        raise ValueError('Horodatage binaire hors plage') from None


def binary_rows(stream, path):
    """Linux glibc little-endian utmp (384 B), lastlog (292 B); never guess ABI."""
    name = plain_name(path)
    lastlog = bool(re.fullmatch(r'lastlog(?:[.-].*)?', name))
    size = 292 if lastlog else 384
    ordinal = 0

    def chunks():
        nonlocal ordinal
        while True:
            check_cancel()
            block = stream.read(size * 2048)
            if not block:
                return
            if len(block) % size:
                raise ValueError(f'Enregistrement Linux tronqué à {ordinal*size+len(block)} ; ABI attendu : glibc LE {size} octets')
            if not any(block):
                ordinal += len(block)//size
                continue
            for index in range(0, len(block), size):
                raw = block[index:index+size]
                offset = ordinal * size
                ordinal += 1
                if any(raw):
                    yield offset, ordinal, raw

    for offset, ordinal, raw in chunks():
        check_cancel()
        if lastlog:
            seconds, = struct.unpack_from('<i', raw)
            line, host = raw[4:36], raw[36:292]
            fields = {'Format': 'lastlog glibc LE', 'UID': str(ordinal-1), 'Horodatage': timestamp(seconds),
                      'Chemin': display(line.split(b'\0')[0]), 'Hôte': display(host.split(b'\0')[0])}
        else:
            typ, = struct.unpack_from('<h', raw)
            pid, = struct.unpack_from('<i', raw, 4)
            seconds, micros = struct.unpack_from('<ii', raw, 340)
            if not 0 <= typ <= 9 or not 0 <= micros < 1000000:
                raise ValueError(f'ABI utmp inconnu ou fichier corrompu à {offset}')
            fields = {'Format': 'utmp glibc LE', 'Événement': str(typ), 'PID': str(pid),
                      'Horodatage': timestamp(seconds, micros), 'Utilisateur': display(raw[44:76].split(b'\0')[0]),
                      'Hôte': display(raw[76:332].split(b'\0')[0]), 'Chemin': display(raw[8:40].split(b'\0')[0])}
        yield dict(fields, Offset=str(offset), Lecture='Structurée', **{'Texte brut': raw.hex()})


def journal_rows(stream):
    """Read systemd journal objects directly (standard and compact layouts).

    References: systemd JOURNAL_FILE_FORMAT. Hash/seal verification is not done.
    Random access uses the original file or a disk spool for compressed streams.
    """
    stream.seek(0, 2)
    length = stream.tell()
    stream.seek(0)
    header = stream.read(208)
    if len(header) < 208 or header[:8] != b'LPKSHHRH':
        raise ValueError('En-tête systemd journal invalide ou tronqué')
    incompatible, = struct.unpack_from('<I', header, 12)
    if incompatible & ~31:
        raise ValueError(f'Options incompatibles systemd journal inconnues : {incompatible:#x}')
    compact = bool(incompatible & 16)
    header_size, arena_size = struct.unpack_from('<QQ', header, 88)
    tail, = struct.unpack_from('<Q', header, 136)
    expected_entries, = struct.unpack_from('<Q', header, 152)
    if header_size < 208 or header_size > length or arena_size > length-header_size:
        raise ValueError('Tailles systemd journal invalides ou source tronquée')
    end = header_size + arena_size

    def object_at(offset, expected=None):
        if offset < header_size or offset % 8 or offset + 16 > end:
            raise ValueError(f'Offset systemd journal invalide : {offset}')
        stream.seek(offset)
        head = stream.read(16)
        typ, flags, size = struct.unpack('<BB6xQ', head)
        if expected is not None and typ != expected:
            raise ValueError(f'Type systemd journal inattendu à {offset}')
        if not 1 <= typ <= 7 or size < 16 or offset + size > end:
            raise ValueError(f'Objet systemd journal invalide ou tronqué à {offset}')
        load_payload = expected is not None or typ == 3
        if load_payload and size > MAX_OBJECT:
            raise ValueError(f'Objet systemd journal supérieur à 64 Mio à {offset}')
        data = stream.read(size-16) if load_payload else b''
        if load_payload and len(data) != size-16:
            raise ValueError(f'Objet systemd journal tronqué à {offset}')
        return typ, flags, size, data

    offset = header_size
    count = 0
    while tail and offset <= tail:
        check_cancel()
        typ, flags, size, data = object_at(offset)
        if typ == 3:
            if flags or len(data) < 48:
                raise ValueError(f'Enregistrement journal invalide à {offset}')
            seq, realtime, monotonic = struct.unpack_from('<QQQ', data)
            width = 4 if compact else 16
            if (len(data)-48) % width:
                raise ValueError('Références de données journal tronquées')
            fields = {}
            entry_bytes = 0
            for position in range(48, len(data), width):
                check_cancel()
                ref, = struct.unpack_from('<I' if compact else '<Q', data, position)
                _, compression, _, payload = object_at(ref, 1)
                skip = 56 if compact else 48
                if len(payload) < skip:
                    raise ValueError('Objet DATA journal tronqué')
                payload = payload[skip:]
                if compression == 1:
                    decoder = lzma.LZMADecompressor(memlimit=MAX_OBJECT)
                    payload = decoder.decompress(payload, max_length=MAX_OBJECT+1)
                    if len(payload)>MAX_OBJECT or not decoder.eof:
                        raise ValueError('Données XZ journal tronquées ou supérieures à 64 Mio')
                elif compression == 2:
                    import lz4.block
                    if len(payload)<8:
                        raise ValueError('Données LZ4 journal tronquées')
                    expanded, = struct.unpack_from('<Q', payload)
                    if expanded>MAX_OBJECT:
                        raise ValueError('Données LZ4 journal supérieures à 64 Mio')
                    payload = lz4.block.decompress(payload[8:], uncompressed_size=expanded)
                    if len(payload)!=expanded:
                        raise ValueError('Taille LZ4 journal incohérente')
                elif compression == 4:
                    import zstandard
                    with zstandard.ZstdDecompressor(max_window_size=MAX_OBJECT//1024).stream_reader(io.BytesIO(payload)) as reader:
                        payload = reader.read(MAX_OBJECT+1)
                    if len(payload)>MAX_OBJECT:
                        raise ValueError('Données Zstandard journal supérieures à 64 Mio')
                elif compression:
                    raise ValueError('Compression systemd journal inconnue')
                entry_bytes += len(payload)
                if entry_bytes > MAX_OBJECT:
                    raise ValueError('Entrée journal développée supérieure à 64 Mio')
                key, sep, value = payload.partition(b'=')
                if not sep:
                    raise ValueError('Champ systemd journal sans séparateur')
                fields.setdefault(display(key), []).append(display(value))
            values = {key: value[0] for key, value in fields.items()}
            count += 1
            yield {'Format': 'systemd journal', 'Lecture': 'Structurée', 'Offset': str(offset),
                   'Horodatage': timestamp(realtime//1000000, realtime%1000000),
                   'Hôte': values.get('_HOSTNAME', ''), 'Processus': values.get('SYSLOG_IDENTIFIER', values.get('_COMM', '')),
                   'PID': values.get('_PID', ''), 'UID': values.get('_UID', ''), 'Détail': values.get('MESSAGE', ''),
                   'Événement': str(seq), 'Champs': encoded({'fields': fields, 'monotonic_us': monotonic,
                                                              'boot_id': data[24:40].hex()}), 'Texte brut': encoded(fields)}
        offset += (size+7) & ~7
    if count != expected_entries:
        raise ValueError(f'Nombre d’entrées journal incohérent : {count} lu(es), {expected_entries} annoncé(es)')


def export_rows(stream):
    """systemd Journal Export Format, including length-prefixed binary fields."""
    fields = {}
    field_bytes = 0
    start = stream.tell()
    while True:
        check_cancel()
        offset = stream.tell()
        raw = stream.readline(MAX_LINE+1)
        if len(raw)>MAX_LINE:
            raise ValueError('Champ journal export supérieur à 8 Mio')
        if not raw or raw == b'\n':
            if fields:
                values = {k: v[0] for k, v in fields.items()}
                micros = values.get('__REALTIME_TIMESTAMP', '')
                yield {'Format': 'Journal export', 'Lecture': 'Structurée', 'Offset': str(start),
                       'Horodatage': timestamp(int(micros)//1000000, int(micros)%1000000) if micros.isdigit() else '',
                       'Hôte': values.get('_HOSTNAME', ''), 'PID': values.get('_PID', ''),
                       'Détail': values.get('MESSAGE', ''), 'Champs': encoded(fields), 'Texte brut': encoded(fields)}
                fields = {}
                field_bytes = 0
            if not raw:
                return
            start = stream.tell()
            continue
        line = raw.rstrip(b'\n')
        key, sep, value = line.partition(b'=')
        if not sep:
            length = stream.read(8)
            if len(length)!=8:
                raise ValueError(f'Longueur de champ export tronquée à {offset}')
            size, = struct.unpack('<Q', length)
            if size>MAX_LINE:
                raise ValueError('Champ binaire journal export supérieur à 8 Mio')
            value = stream.read(size)
            if len(value)!=size or stream.read(1)!=b'\n':
                raise ValueError(f'Champ binaire export tronqué à {offset}')
        if not re.fullmatch(rb'[A-Z_][A-Z_0-9]*', key):
            raise ValueError(f'Nom de champ journal export invalide à {offset}')
        fields.setdefault(display(key), []).append(display(value))
        field_bytes += len(key)+len(value)
        if field_bytes > MAX_OBJECT:
            raise ValueError('Entrée journal export supérieure à 64 Mio')



class BoundedLzma(io.RawIOBase):
    """Bound dictionary allocation and output chunks, including concatenated streams."""
    def __init__(self, incoming):
        super().__init__()
        self.incoming = incoming
        self.decoder = lzma.LZMADecompressor(memlimit=MAX_OBJECT)
        self.pending = b''
        self.finished = False

    def readable(self):
        return True

    def readinto(self, destination):
        if not destination or self.finished:
            return 0
        while True:
            check_cancel()
            if self.decoder.eof:
                self.pending = self.decoder.unused_data or self.incoming.read(65536)
                if not self.pending:
                    self.finished = True
                    return 0
                self.decoder = lzma.LZMADecompressor(memlimit=MAX_OBJECT)
            if self.decoder.needs_input:
                data = self.pending or self.incoming.read(65536)
                self.pending = b''
                if not data:
                    raise ValueError('Flux XZ/LZMA tronqué')
            else:
                data = b''
            result = self.decoder.decompress(data, max_length=len(destination))
            if result:
                destination[:len(result)] = result
                return len(result)


def parse(source, output, progress=lambda _: None):
    """Stream into disk CSVs. Partial outputs survive with explicit error status."""
    source, output = Path(source), Path(output)
    members, warnings, outputs = [], [], []
    total = structured = raw_count = expanded = member_count = 0
    target = output/'Linux — journaux.csv'
    handle = None
    writer = None

    def consume(size):
        nonlocal expanded
        expanded += size
        if expanded > MAX_EXPANDED:
            raise ValueError('Budget Linux de 1 Tio de données lues/décompressées atteint')

    class Counted:
        def __init__(self, incoming):
            self.incoming = incoming
        def read(self, size=-1):
            check_cancel()
            value = self.incoming.read(size)
            consume(len(value))
            return value
        def readline(self, size=-1):
            check_cancel()
            value = self.incoming.readline(size)
            consume(len(value))
            return value

    def emit(row, path, entry):
        nonlocal total, structured, raw_count, handle, writer
        if writer is None:
            handle = target.open('x', encoding='utf-8', newline='')
            writer = csv.DictWriter(handle, HEADERS)
            writer.writeheader()
        row['Source'] = path
        writer.writerow(row)
        total += 1
        is_raw = row.get('Lecture') == 'Brute'
        raw_count += is_raw
        structured += not is_raw
        entry['rows'] += 1
        entry['raw_rows'] += is_raw
        if total % 100000 == 0:
            progress(f'Linux : {total:,} enregistrements ; {expanded:,} octets parcourus')

    def read(stream, path, depth=0):
        nonlocal member_count
        check_cancel()
        member_count += 1
        if member_count > MAX_MEMBERS:
            raise ValueError('Limite de 100000 membres Linux atteinte')
        entry = dict(path=path, status='pending', rows=0, raw_rows=0)
        members.append(entry)
        try:
            prefix = stream.read(4096)
            class Prefix:
                def __init__(self):
                    self.buffer = io.BytesIO(prefix)
                def read(self, size=-1):
                    if size < 0:
                        raise ValueError('Lecture non bornée interdite')
                    first = self.buffer.read(size)
                    return first + stream.read(size-len(first)) if len(first)<size else first
                def readline(self, size=-1):
                    first = self.buffer.readline(size)
                    return first if first.endswith(b'\n') or len(first)==size else first+stream.readline(size-len(first))
                def readable(self):
                    return True
            incoming = Prefix()
            name = path.casefold()
            compression = None
            if prefix.startswith(b'\x1f\x8b'):
                compression = 'gzip'
            elif prefix.startswith(b'BZh'):
                compression = 'bzip2'
            elif prefix.startswith(b'\xfd7zXZ\0') or name.endswith('.lzma'):
                compression = 'xz'
            elif prefix.startswith(b'\x28\xb5\x2f\xfd') or name.endswith(('.zst', '.zstd')):
                compression = 'zstd'
            if not compression and name.endswith(COMPRESSIONS):
                raise ValueError('Signature de compression absente ou fichier tronqué')
            if compression:
                if depth>=MAX_DEPTH:
                    raise ValueError('Profondeur de compression/archives supérieure à 8')
                child = path.rsplit('.', 1)[0] if name.endswith(COMPRESSIONS) else path+'.decoded'
                if name.endswith('.tgz'):
                    child = path[:-4]+'.tar'
                if compression == 'gzip':
                    decoder = gzip.GzipFile(fileobj=incoming)
                elif compression == 'bzip2':
                    decoder = bz2.BZ2File(incoming)
                elif compression == 'xz':
                    decoder = io.BufferedReader(BoundedLzma(incoming))
                else:
                    import zstandard
                    decoder = io.BufferedReader(zstandard.ZstdDecompressor(max_window_size=MAX_OBJECT//1024).stream_reader(incoming))
                child = path+'!/'+PurePosixPath(child.replace('\\', '/')).name
                with decoder:
                    read(Counted(decoder), child, depth+1)
                entry['status'] = 'archive'
                return
            if name.endswith('.tar') or (len(prefix)>262 and prefix[257:262]==b'ustar'):
                if depth>=MAX_DEPTH:
                    raise ValueError('Profondeur de compression/archives supérieure à 8')
                with tarfile.open(fileobj=Counted(incoming), mode='r|') as archive:
                    for ordinal, item in enumerate(archive, 1):
                        check_cancel()
                        if item.isdir():
                            member_count += 1
                            if member_count>MAX_MEMBERS:
                                raise ValueError('Limite de 100000 membres Linux atteinte')
                            continue
                        member_path = path+f'[entry {ordinal}]!/'+item.name
                        if not safe_member(item.name) or not item.isfile() or item.issparse():
                            member_count += 1
                            if member_count>MAX_MEMBERS:
                                raise ValueError('Limite de 100000 membres Linux atteinte')
                            members.append(dict(path=member_path, status='skipped', reason='Lien, chemin non sûr ou fichier spécial/sparse'))
                            continue
                        with archive.extractfile(item) as child:
                            read(child, member_path, depth+1)
                entry['status'] = 'archive'
                return
            if prefix.startswith(b'LPKSHHRH'):
                if depth == 0:
                    # Plain files already support random access; avoid a second disk copy.
                    stream.seek(0)
                    for row in journal_rows(stream):
                        emit(row, path, entry)
                else:
                    with tempfile.TemporaryFile() as spool:
                        while block := incoming.read(1024*1024):
                            check_cancel()
                            consume(len(block))
                            spool.write(block)
                        spool.seek(0)
                        for row in journal_rows(spool):
                            emit(row, path, entry)
                entry['note'] = 'Objets décodés ; scellement et hachages internes non vérifiés'
            elif re.fullmatch(r'(?:utmp|wtmp|btmp|lastlog)(?:[.-].*)?', plain_name(path)):
                for row in binary_rows(Counted(incoming), path):
                    emit(row, path, entry)
            elif prefix.startswith((b'__CURSOR=', b'__REALTIME_TIMESTAMP=')):
                with tempfile.TemporaryFile() as spool:
                    while block := incoming.read(1024*1024):
                        consume(len(block))
                        spool.write(block)
                    spool.seek(0)
                    for row in export_rows(spool):
                        emit(row, path, entry)
            elif b'\0' in prefix:
                entry.update(status='unsupported', reason='Binaire inconnu ; aucun décodage arbitraire')
                return
            elif name.endswith(('.journal', '.journal~')):
                raise ValueError('Signature systemd journal absente')
            else:
                number = 0
                offset = 0
                columns = None
                separator = None
                table_format = ''
                while True:
                    check_cancel()
                    raw = incoming.readline(MAX_LINE+1)
                    if not raw:
                        break
                    consume(len(raw))
                    number += 1
                    if len(raw)>MAX_LINE:
                        raise ValueError(f'Ligne {number} supérieure à 8 Mio ; lecture interrompue explicitement')
                    text = raw.decode('utf-8-sig' if number==1 else 'utf-8', 'backslashreplace').rstrip('\r\n')
                    fields = text_fields(text, path)
                    if text.startswith('#separator '):
                        token = text[len('#separator '):]
                        match = re.fullmatch(r'\\x([0-9a-fA-F]{2})', token)
                        separator = chr(int(match[1], 16)) if match else token
                        if len(separator) != 1:
                            raise ValueError('Séparateur Zeek non reconnu')
                        table_format = 'Zeek TSV'
                    elif text.startswith('#fields') and separator:
                        columns = text.split(separator)[1:]
                    elif text.startswith('#Fields: '):
                        columns = text[len('#Fields: '):].split()
                        separator = None
                        table_format = 'W3C extended'
                    elif columns and not text.startswith('#'):
                        values = text.split(separator)
                        if len(values) == len(columns):
                            obj = dict(zip(columns, values))
                            fields = {'Format': table_format, 'Champs': encoded(obj)}
                            if table_format == 'Zeek TSV':
                                fields.update(Horodatage=obj.get('ts', ''), **{'Adresse distante': obj.get('id.orig_h', '')})
                            else:
                                fields.update(Horodatage=' '.join(obj.get(k, '') for k in ('date', 'time')).strip(),
                                              **{'Adresse distante': obj.get('c-ip', ''), 'Méthode': obj.get('cs-method', ''),
                                                 'Chemin': obj.get('cs-uri-stem', ''), 'Statut': obj.get('sc-status', '')})
                    if '\0' in text:
                        fields = {}  # Later binary data is visibly raw, never structured text.
                    row = dict(fields, Lecture='Structurée' if fields else 'Brute', Ligne=str(number),
                               Offset=str(offset), **{'Fin de ligne': str(number), 'Texte brut': text})
                    emit(row, path, entry)
                    offset += len(raw)
            entry['status'] = 'complete' if entry['rows'] else 'empty'
        except OperationCancelled:
            raise
        except Exception as exc:
            entry.update(status='error', reason=str(exc))
            if expanded>MAX_EXPANDED or member_count>MAX_MEMBERS:
                raise

    try:
        with source.open('rb') as stream:
            read(stream, str(source))
    finally:
        if handle:
            handle.close()
    if total:
        outputs.append(dict(csv=str(target), family='Journaux Linux', rows=total))
    if raw_count:
        warnings.append(f'{raw_count} ligne(s) non structurée(s), conservée(s) en texte brut')
    for entry in members:
        if entry['status'] in ('error', 'unsupported', 'skipped'):
            warnings.append(entry['path']+' : '+entry.get('reason', entry['status']))
        if entry.get('note'):
            warnings.append(entry['path']+' : '+entry['note'])
    return dict(outputs=outputs, members=members, warnings=warnings, structured=structured,
                raw=raw_count, expanded_bytes=expanded)
