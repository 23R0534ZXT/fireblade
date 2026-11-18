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
        if 'min(' in folded:
            return [('2026-11-17 10:00:00', '2026-11-17 10:30:00')]
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
