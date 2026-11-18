"""The case lookups: bounded, honest when a column is absent, never a stack trace."""
from fireblade.core.case_tools import CaseTools

# DuckDB's PRAGMA table_info: (cid, name, type, notnull, default, primary key).
COLUMNS = [('0', 'Timestamp', 'TIMESTAMP', 'NO', None, 'NO'),
           ('1', 'Computer', 'VARCHAR', 'NO', None, 'NO'),
           ('2', 'EventID', 'VARCHAR', 'NO', None, 'NO'),
           ('3', 'Details', 'VARCHAR', 'NO', None, 'NO')]


class Case:
    """A case that answers the way DuckDB would, and records what it was asked."""

    def __init__(self, rows=None, columns=COLUMNS, total=None, grouped=None):
        self.rows = rows if rows is not None else []
        self.columns = columns
        self.total = len(self.rows) if total is None else total
        self.grouped = grouped if grouped is not None else [('FBVM', 12), ('WS01', 3)]
        self.asked = []

    def __call__(self, sql, params):
        self.asked.append((sql, params))
        folded = sql.casefold()
        if 'information_schema.columns' in folded:
            return [(row[1],) for row in self.columns]
        if folded.startswith('pragma table_info'):
            return self.columns
        if 'group by 1 order by 2 desc' in folded:
            return self.grouped
        if 'distinct' in folded:
            return [(15, 15, 4, 'a', 'z')]
        if 'min(' in folded:
            return [('2026-11-17 10:00:00', '2026-11-17 10:30:00')]
        if 'count(*)' in folded and 'group by 1 order by 2 asc' in folded:
            return [('rare.exe', 1), ('common.exe', 40)]
        if 'count(*)' in folded:
            return [(self.total,)]
        return self.rows


def _rows():
    return [('2026-11-17 10:02:52', 'FBVM', '7045', 'ServiceName: updater | ImagePath: C:\\Temp\\u.exe')]


def test_the_brief_lists_hosts_and_the_time_span():
    text = CaseTools(Case(_rows(), total=15)).describe()
    assert '15 row(s)' in text
    assert 'FBVM (12)' in text
    assert '2026-11-17 10:00:00' in text


def test_a_search_names_the_rows_it_read():
    text, count = CaseTools(Case(_rows())).call('search', dict(text='updater'))
    assert count == 1
    assert '[1]' in text and 'FBVM' in text and 'C:\\Temp\\u.exe' in text


def test_a_case_without_a_text_column_says_so_instead_of_raising():
    columns = [('0', 'Timestamp', 'TIMESTAMP', 'NO', None, 'NO')]
    text, count = CaseTools(Case([], columns, total=0)).search('updater')
    assert count == 0
    assert 'no text column' in text


def test_a_case_with_nothing_imported_says_it_plainly():
    empty = CaseTools(Case([], columns=[], total=0))
    assert 'no imported rows' in empty.describe()


def test_detections_are_listed_most_severe_first_from_the_interface():
    items = [dict(level='high', title='Suspicious Service Path', host='FBVM', count=1,
                  start='2026-11-17 10:02:52')]
    text, count = CaseTools(Case(), findings=lambda: items).call('findings', dict())
    assert count == 1
    assert text.startswith('- Suspicious Service Path, high, on FBVM, at 2026-11-17 10:02:52')
    assert '[high]' not in text, 'a bracketed dump is what the model copies verbatim'


def test_an_artifact_lookup_matches_on_the_source_when_there_is_no_artifact_column():
    columns = COLUMNS + [('4', 'SourceFile', 'VARCHAR', 'NO', None, 'NO')]
    case = Case([('2026-11-17 10:00:00', 'FBVM', '', 'Amcache entry')], columns)
    _text, count = CaseTools(case).call('artifact', dict(artifact='Amcache'))
    assert count == 1
    sql, params = case.asked[-1]
    assert 'SourceFile' in sql and params == ['%Amcache%']


def test_an_unknown_lookup_is_named_not_executed():
    case = Case(_rows())
    text, count = CaseTools(case).call('drop_everything', dict())
    assert count == 0
    assert 'Unknown lookup' in text
    assert case.asked == []

def test_the_brief_states_the_severity_of_what_it_lists():
    """A model that reads 'five detections' guesses the severity, and guessed low."""
    items = [dict(level='high', title='Suspicious Service Path', host='FBVM', count=1,
                  start='2026-11-17 10:02:52'),
             dict(level='medium', title='AppX Located in Uncommon Directory', host='FBVM',
                  count=1, start='2026-11-17 10:02:47'),
             dict(level='informational', title='RDP Logon', host='FBVM', count=1,
                  start='2026-11-17 10:02:44')]
    text = CaseTools(Case([]), findings=lambda: items).describe()
    assert 'by severity: 1 high, 1 medium, 1 informational' in text
    assert 'Suspicious Service Path, high' in text and '[high]' not in text

def test_the_assistant_only_reads_the_case():
    """A lookup that would change the case is refused before it reaches DuckDB."""
    import pytest
    from fireblade.core.case_tools import select_only

    for harmless in ("SELECT * FROM events", "select 1", "PRAGMA table_info('events')"):
        assert select_only(harmless) == harmless
    for dangerous in ("DELETE FROM events", "UPDATE events SET a=1", "DROP TABLE events",
                      "INSERT INTO events VALUES (1)", "ATTACH 'x.db'"):
        with pytest.raises(ValueError):
            select_only(dangerous)


def test_a_query_that_writes_never_reaches_the_connection():
    case = Case(_rows())
    tools = CaseTools(case)
    try:
        tools.query('DELETE FROM events', [])
    except ValueError:
        pass
    assert not any('delete' in sql.casefold() for sql, _ in case.asked)


def test_around_asks_for_a_window_on_that_host():
    case = Case(_rows())
    text, count = CaseTools(case).call('around', dict(host='FBVM', time='2026-11-17 10:02:52',
                                                     minutes=5))
    sql, params = case.asked[-1]
    assert 'INTERVAL 5 MINUTE' in sql and 'Computer ILIKE' in sql
    assert params == ['2026-11-17 10:02:52', '2026-11-17 10:02:52', 'FBVM']
    assert count == 1 and 'FBVM' in text


def test_around_without_a_time_says_so():
    text, count = CaseTools(Case(_rows())).call('around', dict(host='FBVM'))
    assert count == 0
    assert 'No time' in text


def test_sequence_orders_the_same_window_in_time():
    case = Case(_rows())
    CaseTools(case).call('sequence', dict(host='FBVM', time='2026-11-17 10:02:52', minutes=15))
    sql, params = case.asked[-1]
    assert 'ORDER BY Timestamp' in sql
    assert 'INTERVAL 15 MINUTE' in sql


def test_rare_lists_the_least_frequent_values_first():
    case = Case(_rows())
    text, count = CaseTools(case).call('rare', dict(column='Details'))
    assert 'rare.exe' in text and count == 2
    assert 'ORDER BY 2 ASC' in case.asked[-1][0]


def test_entity_finds_a_name_in_every_text_column():
    case = Case(_rows())
    CaseTools(case).call('entity', dict(text='updsvc'))
    sql, params = case.asked[-1]
    assert 'Computer ILIKE' in sql and 'Details ILIKE' in sql
    assert params[0] == '%updsvc%'


def test_stats_summarises_one_column():
    text, count = CaseTools(Case(_rows())).stats('Computer')
    assert 'Computer: 15 row(s)' in text and '4 distinct' in text and count == 1

class AnonymisedCase:
    """A real imported analysis: the view is __row_id, c0, c1... and metadata holds names.

    This is what every case looks like on disk, and reading only the view made the
    assistant believe the case had no timestamp and no text to search.
    """

    HEADERS = ['Timestamp', 'Computer', 'Details']

    def __init__(self):
        self.asked = []
        self.rows = [(1, '2026-11-17T10:02:52Z', 'FBVM', 'ServiceName: updsvc'),
                     (2, '2026-11-17T10:03:10Z', 'FBVM', 'ImagePath: C:\\Temp\\u.exe')]

    def __call__(self, sql, params):
        self.asked.append((sql, params))
        folded = sql.casefold()
        if 'information_schema.columns' in folded:
            return [('__row_id',), ('c0',), ('c1',), ('c2',)]
        if 'from metadata' in folded:
            import json
            return [(json.dumps({'headers': self.HEADERS}),)]
        if 'count(*)' in folded and 'group by' not in folded:
            return [(2,)]
        return self.rows


def test_the_real_column_names_are_read_from_the_metadata():
    case = AnonymisedCase()
    tools = CaseTools(case)

    assert tools.labels() == ['Timestamp', 'Computer', 'Details']
    assert tools.column(('timestamp', 'timecreated')) == 'c0'
    assert tools.column(('computer', 'host')) == 'c1'


def test_a_search_uses_the_physical_column_behind_the_name():
    case = AnonymisedCase()

    text, count = CaseTools(case).search('updsvc')

    sql, params = case.asked[-1]
    assert 'c2 ILIKE ?' in sql and params == ['%updsvc%']
    assert count == 2


def test_the_window_around_a_detection_is_read_on_an_imported_case():
    case = AnonymisedCase()

    text, count = CaseTools(case).call('around', dict(host='FBVM', time='2026-11-17T10:02:52Z',
                                                     minutes=5))

    sql, params = case.asked[-1]
    assert 'CAST(c0 AS TIMESTAMP)' in sql and 'c1 ILIKE ?' in sql
    assert count == 2


def test_the_rows_are_printed_with_their_real_names_and_without_the_row_id():
    case = AnonymisedCase()

    text, _count = CaseTools(case).search('updsvc')

    assert 'Timestamp | Computer | Details' in text
    assert '[1] 2026-11-17T10:02:52Z | FBVM | ServiceName: updsvc' in text
