"""Bounded raster data only: never deserialize .NET objects or follow file paths."""
import base64
from functools import lru_cache
from PySide6.QtCore import QByteArray,QBuffer,QIODevice
from PySide6.QtGui import QImageReader

@lru_cache(maxsize=32)
def image_bytes(encoded):
    if not isinstance(encoded,str) or len(encoded)>350000:raise ValueError('Image de disposition limitée à 256 Ko')
    try:data=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError):raise ValueError('Image de disposition : base64 invalide') from None
    if len(data)>256*1024:raise ValueError('Image de disposition limitée à 256 Ko')
    if not data.startswith((b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'BM',b'GIF87a',b'GIF89a')):raise ValueError('Image de disposition : raster PNG/JPEG/BMP/GIF requis, objet .NET sérialisé non accepté')
    buffer=QBuffer();buffer.setData(QByteArray(data));buffer.open(QIODevice.ReadOnly)
    reader=QImageReader(buffer);size=reader.size()
    if not size.isValid() or size.width()>1024 or size.height()>1024:raise ValueError('Image de disposition limitée à 1024 × 1024 pixels')
    if reader.read().isNull():raise ValueError('Image de disposition corrompue')
    return data

def normalize_image(raw):
    raw=''.join(raw.split())
    if raw.startswith('data:image/') and ';base64,' in raw:raw=raw.split(';base64,',1)[1]
    # ImageConverter/BinaryFormatter envelopes can contain a raster byte array.
    # Extract bytes only: no types, constructors or object deserializer are invoked.
    if len(raw)>350000:raise ValueError('Image de disposition limitée à 256 Ko')
    try:data=base64.b64decode(raw,validate=True)
    except (ValueError,TypeError):raise ValueError('Image de disposition : base64 invalide') from None
    if data.startswith(b'\x00\x01\x00\x00\x00\xff\xff\xff\xff'):
        start=data.find(b'\x89PNG\r\n\x1a\n')
        if start>=0:
            end=data.find(b'IEND',start)
            if end>=0:data=data[start:end+8]
        else:
            start=data.find(b'\xff\xd8\xff');end=data.rfind(b'\xff\xd9')
            if start>=0 and end>start:data=data[start:end+2]
        raw=base64.b64encode(data).decode('ascii')
    image_bytes(raw)
    return raw
