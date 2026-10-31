import csv
import io
import pytest
from fireblade.core.csv_preamble import HEADERS, preamble_lines
from fireblade.core.engine import Case
from fireblade.core.models import View


@pytest.mark.parametrize('prefix', HEADERS)
def test_tool_preamble_requires_exact_header_and_preserves_source(prefix,tmp_path):
    header = HEADERS[prefix]
    row = ['001'] * len(header.split(','))
    output = io.StringIO();csv.writer(output,lineterminator='\n').writerow(row)
    text = prefix+'version\nmetadata\nmetadata\n\n'+header+'\n'+output.getvalue()
    source=tmp_path/'tool.csv';source.write_text(text,encoding='utf-8');before=source.read_bytes()
    case=Case(tmp_path/'case.timeline')
    try:
        case.import_csv(source)
        assert list(case.page(View())[0][1:]) == row
        assert source.read_bytes() == before
    finally:case.close()
    assert preamble_lines(io.StringIO(prefix+'version\nx\nx\nx\nID,Name\n')) == 0
    assert preamble_lines(io.StringIO('ID,Name\n'+text)) == 0
