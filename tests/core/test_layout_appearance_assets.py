import base64
import json
import struct
import pytest
from fireblade.core.tle_appearance import validate_styles
from fireblade.core.layout_images import normalize_image,image_bytes
from fireblade.core.tle_layout import read_tle_layout
from fireblade.core.tle_styles import custom_styles,style


def test_bounded_rasters_reject_paths_objects_and_oversized_dimensions():
    for raw in ('C:/secret/image.png','not base64','A'*350001,base64.b64encode(b'not an image').decode()):
        with pytest.raises(ValueError):normalize_image(raw)
    encoded=base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+struct.pack('>II',8192,8192)+b'\x00'*50).decode()
    with pytest.raises(ValueError):image_bytes(encoded)
    for value in ([],{},None):
        with pytest.raises(ValueError):validate_styles({'row':{'image':value}},0)


@pytest.mark.parametrize('property,value',[('WordWrap','Invalid'),('Trimming','Invalid'),('HotkeyPrefix','Invalid')])
def test_invalid_text_options_are_rejected(tmp_path,property,value):
    path=tmp_path/'bad.layout';path.write_text(f'<XtraSerializer><property name="Appearance"><property name="Row"><property name="TextOptions"><property name="{property}">{value}</property></property></property></property></XtraSerializer>')
    with pytest.raises(ValueError):read_tle_layout(path,['Value'])


def test_image_wrapper_is_extracted_without_object_deserialization():
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    from PySide6.QtGui import QImage,QColor
    image=QImage(4,4,QImage.Format_RGB32);image.fill(QColor('red'))
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);assert image.save(buffer,'PNG')
    envelope=b'\x00\x01\x00\x00\x00\xff\xff\xff\xff'+b'System.Drawing.Bitmap'+bytes(data)+b'\x0b'
    result=normalize_image(base64.b64encode(envelope).decode())
    assert image_bytes(result)==bytes(data)


def test_global_and_layout_custom_style_precedence_and_validation(tmp_path):
    from fireblade.runtime.windows_paths import user_directory
    global_file=user_directory()/'Layouts'/'styles.json';global_file.parent.mkdir(parents=True)
    global_file.write_text(json.dumps({'Evidence':{'bold':True,'foreground':'#112233'},'Other':{'italic':True}}))
    layout=tmp_path/'test.layout';sidecar=tmp_path/'test.layout.styles.json'
    sidecar.write_text(json.dumps({'Evidence':{'background':'#123456'}}))
    loaded=custom_styles(layout)
    assert style('Evidence',loaded)=={'background':'#123456'} and style('Other',loaded)=={'italic':True}
    assert style('Red Text',loaded)=={'foreground':'#9c0006'}
    sidecar.write_text(json.dumps({'Evidence':{'execute':'arbitrary'}}))
    with pytest.raises(ValueError):custom_styles(layout)
    with pytest.raises(ValueError):style('Missing')


def test_options_disable_inherited_custom_text_image_and_border(tmp_path):
    from fireblade.core.tle_appearance import appearance
    from fireblade.core.tle_layout import text,properties,color
    import xml.etree.ElementTree as ET
    node=ET.fromstring('<property><property name="Options"><property name="UseTextOptions">false</property><property name="UseImage">false</property><property name="UseBorderColor">false</property></property></property>')
    result=appearance(node,text,properties,color,[],dict(word_wrap=True,hotkey='Show',horizontal='Far',image='bad',border_color='#ffffff'))
    assert result=={}
