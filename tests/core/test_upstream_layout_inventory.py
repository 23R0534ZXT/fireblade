"""All public default layouts, with inferred schemas and pinned byte provenance."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest

from fireblade.core.tle_layout import properties, text, read_tle_layout
from fireblade.core.tle_layout_export import write_tle_layout

ROOT=Path(__file__).parents[1]/'fixtures/tle-layouts'
MANIFEST=json.loads((ROOT/'upstream-layouts.json').read_text())


@pytest.mark.parametrize('entry',MANIFEST['files'],ids=lambda entry:entry['file'])
def test_all_published_layouts_import_and_export_with_pinned_provenance(tmp_path,entry):
    with zipfile.ZipFile(ROOT/'upstream-layouts.zip') as archive:
        data=archive.read(entry['file'])
    assert hashlib.sha256(data).hexdigest()==entry['sha256']
    source=tmp_path/entry['file'];source.write_bytes(data)
    root=ET.fromstring(data.decode('utf-8-sig'))
    headers=[]
    for item in properties(root)['Columns']:
        name=text(item,'FieldName') or text(item,'Name')
        name=name[3:] if name.startswith('col') else name
        if name and name not in headers:headers.append(name)
    before=read_tle_layout(source,headers)
    assert not before.warnings
    exported=tmp_path/'exported.layout'
    write_tle_layout(exported,headers,before.view,before.columns)
    after=read_tle_layout(exported,headers)
    assert [(c['column'],c['position'],c['width']) for c in after.columns]==[(c['column'],c['position'],c['width']) for c in before.columns]
    assert after.view.groups==before.view.groups
    assert after.view.search==before.view.search
    assert after.view.pinned_columns==before.view.pinned_columns
    assert after.view.right_pinned_columns==before.view.right_pinned_columns
    assert len(after.view.format_rules)==len(before.view.format_rules)
    assert after.view.layout_styles==before.view.layout_styles
