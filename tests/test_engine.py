import csv
from pathlib import Path

import pytest

from timeline_next.engine import Case, Filter, View


@pytest.fixture
def case(tmp_path):
    source = tmp_path / "source.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(['Time', 'Artifact', 'User', 'ID', 'Description'])
        w.writerows([
            ['2026-01-02 12:00:00', 'MFT', 'alice', '001', 'a,b\nsecond line'],
            ['2026-01-01 12:00:00', 'EVTX', 'bob', '10', "quote \" and ' OR 1=1 --"],
            ['2026-01-03 12:00:00', 'MFT', 'alice', '2', 'évidence'],
            ['invalid date', 'MFT', 'bob', '9007199254740993', '=1+1'],
            ['', 'EVTX', '', '', ''],
        ])
    c = Case(tmp_path / "analysis.timeline", memory_mb=256)
    c.import_csv(source)
    yield c
    c.close()


def test_source_preserved(case):
    rows = case.page(View())
    assert rows[0][4] == '001'
    assert rows[0][5] == 'a,b\nsecond line'
    assert rows[3][4] == '9007199254740993'
    assert len(case.info['sha256']) == 64
    assert case.info['rows'] == 5


def test_filter_and_nested_groups(case):
    v = View(groups=[1, 2])
    assert case.page(v) == [('MFT', 3), ('EVTX', 2)]
    assert case.page(v, ('MFT',)) == [('alice', 2), ('bob', 1)]
    assert [r[0] for r in case.page(v, ('MFT', 'alice'))] == [1, 3]
    assert case.page(v, ('EVTX', None)) == [(5, None, 'EVTX', None, None, None)]
    v.filters = [Filter(3, 'ge', '2'), Filter(1, 'eq', 'MFT')]
    assert case.count(v) == 2


def test_search_injection_regex_and_nulls(case):
    assert case.count(View(search="' OR 1=1 --")) == 1
    assert case.count(View(search="ÉVIDENCE")) == 1
    assert case.count(View(filters=[Filter(3, 'eq', "' OR 1=1 --")])) == 0
    assert case.count(View(filters=[Filter(2, 'empty')])) == 1
    assert case.count(View(filters=[Filter(2, 'regex', '^a.*e$')])) == 2
    with pytest.raises(Exception):
        case.count(View(filters=[Filter(2, 'regex', '[')]))
    with pytest.raises(ValueError):
        case.count(View(filters=[Filter(999, 'eq', 'x')]))


def test_typed_sort_and_date_filter(case):
    assert [r[4] for r in case.page(View(sort_column=3, sort_type='number'))] == ['001', '2', '10', '9007199254740993', None]
    assert case.count(View(filters=[Filter(0, 'after', '2026-01-02')])) == 2
    assert case.count(View(filters=[Filter(3, 'gt', '9007199254740992')])) == 1


def test_bookmarks_views_reopen(case):
    case.bookmark(3, 'investigate')
    v = View(bookmarks_only=True, groups=[1], filters=[Filter(2, 'eq', 'alice')])
    case.save_view('triage', v)
    assert case.count(v) == 1
    assert case.views()['triage'] == v
    # Close and reopen in the same wrapper so fixture cleanup still works.
    case.db.close()
    replacement = Case(case.path)
    case.db = replacement.db
    assert replacement.bookmarks() == {3: 'investigate'}
    assert replacement.info['rows'] == 5
    assert replacement.views()['triage'] == v
    case.bookmark(3, None)
    assert case.count(v) == 0


def test_export_roundtrip(case, tmp_path):
    target = tmp_path / 'export.csv'
    case.export(target, View(filters=[Filter(1, 'eq', 'MFT')]))
    with target.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    assert len(rows) == 4
    assert rows[1][3:] == ['001', 'a,b\nsecond line']
    assert rows[-1][-1] == '=1+1'
    case.export(target, View(groups=[1]), grouped=True)
    assert 'MFT,3' in target.read_text(encoding='utf-8-sig')
    with pytest.raises(ValueError):
        case.export(case.info['path'], View())


def test_paging(tmp_path):
    source = tmp_path / 'many.csv'
    source.write_text('ID,Type\n' + ''.join(f'{i},A\n' for i in range(650)))
    c = Case(tmp_path / 'many.timeline')
    try:
        c.import_csv(source)
        pages = [c.page(View(), offset=i) for i in [0, 250, 500]]
        assert [len(p) for p in pages] == [250, 250, 150]
        assert [r[0] for p in pages for r in p] == list(range(1, 651))
    finally:
        c.close()


def test_delimiter_unicode(tmp_path):
    source = tmp_path / 'semi.csv'
    source.write_bytes('Nom;ID\névidence;0002\n'.encode('latin-1'))
    c = Case(tmp_path / 'semi.timeline')
    try:
        c.import_csv(source, delimiter=';', encoding='latin-1')
        assert c.page(View())[0][1:] == ('évidence', '0002')
    finally:
        c.close()


def test_changed_source_rolls_back(tmp_path):
    source = tmp_path / 'changing.csv'
    source.write_text('ID,Name\n1,original\n')
    c = Case(tmp_path / 'changing.timeline')
    def progress(message):
        if message.startswith('Import sur disque'):
            source.write_text('ID,Name\n2,modified\n')
    try:
        with pytest.raises(ValueError, match='changé'):
            c.import_csv(source, progress=progress)
        assert c.headers == []
        assert c.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='events'").fetchone()[0] == 0
    finally:
        c.close()


def test_utf16_and_import_cancellation(tmp_path):
    source = tmp_path / 'unicode.csv'
    source.write_text('Name,ID\névidence,0001\n', encoding='utf-16')
    c = Case(tmp_path / 'unicode.timeline')
    try:
        def cancel(message):
            if message.startswith('Calcul SHA'):
                c.interrupt()
        with pytest.raises(RuntimeError, match='annulée'):
            c.import_csv(source, encoding='utf-16', progress=cancel)
        c.import_csv(source, encoding='utf-16')
        assert c.page(View())[0][1:] == ('évidence', '0001')
        assert not list(tmp_path.glob('tmp*.csv'))
    finally:
        c.close()


def test_malformed_csv_rolls_back(tmp_path):
    bad = tmp_path / 'bad.csv'
    bad.write_text('a,b\n1,2\n3,4,5\n')
    c = Case(tmp_path / 'bad.timeline')
    try:
        with pytest.raises(Exception):
            c.import_csv(bad, delimiter=',')
        assert c.headers == []
        assert c.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='events'").fetchone()[0] == 0
    finally:
        c.close()
