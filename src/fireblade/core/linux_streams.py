"""Bounded adapters used by offline Linux log decoding."""
import io

from fireblade.core.catscale import check_cancel


class StrictZstd(io.RawIOBase):
    """Check frame EOF explicitly, including concatenated/skippable frames.

    zstandard's stream_reader can accept a truncated final frame. Small input
    slices also bound decompressor output: a Zstd block is at most 128 KiB.
    """
    def __init__(self, incoming):
        import zstandard
        super().__init__()
        self.incoming = incoming
        self.factory = zstandard.ZstdDecompressor(max_window_size=64*1024*1024)
        self.decoder = self.factory.decompressobj()
        self.pending = b''
        self.output = memoryview(b'')
        self.finished = False

    def readable(self):
        return True

    def readinto(self, destination):
        if not destination or self.finished:
            return 0
        while not self.output:
            check_cancel()
            if self.decoder.eof:
                self.pending = self.decoder.unused_data or self.incoming.read(1024)
                if not self.pending:
                    self.finished = True
                    return 0
                self.decoder = self.factory.decompressobj()
            data = self.pending or self.incoming.read(1024)
            self.pending = b''
            if not data:
                raise ValueError('Flux Zstandard tronqué')
            value = self.decoder.decompress(data)
            if len(value)>64*1024*1024:
                raise ValueError('Bloc Zstandard développé supérieur à 64 Mio')
            self.output = memoryview(value)
        size = min(len(destination), len(self.output))
        destination[:size] = self.output[:size]
        self.output = self.output[size:]
        return size


class AlignedLines:
    """Read physical UTF-16/32 lines with byte offsets and a bounded buffer."""
    def __init__(self, incoming, encoding):
        self.incoming = incoming
        self.encoding = encoding
        self.newline = '\n'.encode(encoding)
        self.unit = len(self.newline)
        self.buffer = bytearray()
        self.eof = False

    def readline(self, limit):
        search = 0
        while True:
            found = self.buffer.find(self.newline, search)
            while found>=0 and found % self.unit:
                found = self.buffer.find(self.newline, found+1)
            if found>=0:
                end = found+self.unit
                if end>limit:
                    end = limit
                result = bytes(self.buffer[:end]);del self.buffer[:end]
                return result
            if len(self.buffer)>=limit or self.eof:
                end = min(len(self.buffer),limit)
                result = bytes(self.buffer[:end]);del self.buffer[:end]
                return result
            search = max(0,len(self.buffer)-self.unit+1)
            block = self.incoming.read(min(65536,limit-len(self.buffer)))
            if not block:
                self.eof = True
            self.buffer.extend(block)


def bom_encoding(prefix):
    for marker,encoding in [(b'\xff\xfe\0\0','utf-32-le'),(b'\0\0\xfe\xff','utf-32-be'),
                            (b'\xff\xfe','utf-16-le'),(b'\xfe\xff','utf-16-be')]:
        if prefix.startswith(marker):
            return encoding
    return None


def validate_zip(stream, max_members, max_metadata):
    """Bound ZIP central-directory allocation before ZipFile loads its index."""
    import struct
    stream.seek(0,2);length=stream.tell()
    stream.seek(max(0,length-65557));tail=stream.read(65557)
    position=tail.rfind(b'PK\x05\x06')
    if position<0 or len(tail)-position<22:
        raise ValueError('Répertoire ZIP absent ou tronqué')
    disk,central_disk,on_disk,count,central_size,central_offset,comment=struct.unpack_from('<4H2IH',tail,position+4)
    if len(tail)-position != 22+comment or disk or central_disk or on_disk!=count:
        raise ValueError('ZIP multi-volume ou répertoire incohérent')
    absolute=length-len(tail)+position
    if count==65535 or central_size==0xffffffff or central_offset==0xffffffff:
        if absolute<20:
            raise ValueError('Localisateur ZIP64 absent')
        stream.seek(absolute-20);locator=stream.read(20)
        if locator[:4]!=b'PK\x06\x07':
            raise ValueError('Localisateur ZIP64 invalide')
        locator_disk,record_offset,total_disks=struct.unpack_from('<IQI',locator,4)
        if locator_disk or total_disks!=1 or record_offset+56>absolute-20:
            raise ValueError('Localisateur ZIP64 incohérent')
        stream.seek(record_offset);record=stream.read(56)
        if record[:4]!=b'PK\x06\x06':
            raise ValueError('Répertoire ZIP64 absent')
        disk,central_disk,on_disk,count,central_size,central_offset=struct.unpack_from('<IIQQQQ',record,16)
        if disk or central_disk or on_disk!=count:
            raise ValueError('ZIP64 multi-volume non pris en charge')
    if count>max_members or central_size>max_metadata:
        raise ValueError('Index ZIP supérieur aux limites de membres ou de mémoire')
    if central_offset+central_size>absolute:
        raise ValueError('Répertoire ZIP hors du fichier')
    stream.seek(0)


class StrictBlocks(io.RawIOBase):
    """Bounded concatenated BZip2/LZ4 decoding with explicit truncated/trailing errors."""
    def __init__(self,incoming,factory,label):
        super().__init__()
        self.incoming=incoming;self.factory=factory;self.label=label
        self.decoder=factory();self.pending=b'';self.finished=False
    def readable(self):
        return True
    def readinto(self,destination):
        if not destination or self.finished:return 0
        while True:
            check_cancel()
            if self.decoder.eof:
                self.pending=self.decoder.unused_data or self.incoming.read(65536)
                if not self.pending:
                    self.finished=True;return 0
                self.decoder=self.factory()
            if self.decoder.needs_input:
                data=self.pending or self.incoming.read(65536);self.pending=b''
                if not data:raise ValueError('Flux '+self.label+' tronqué')
            else:data=b''
            result=self.decoder.decompress(data,max_length=len(destination))
            if result:
                destination[:len(result)]=result
                return len(result)
