"""Small inline PNG icons make rule libraries independent of local paths."""
import base64
import struct


def png_bytes(encoded):
    if not isinstance(encoded,str) or len(encoded)>90000:raise ValueError('Icône PNG trop volumineuse')
    try:data=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError):raise ValueError('Icône PNG invalide') from None
    if len(data)<24 or data[:8]!=b'\x89PNG\r\n\x1a\n' or data[12:16]!=b'IHDR':raise ValueError('Icône PNG invalide')
    width,height=struct.unpack('>II',data[16:24])
    if not 0<width<=128 or not 0<height<=128:raise ValueError('Icône limitée à 128 × 128 pixels')
    return data
