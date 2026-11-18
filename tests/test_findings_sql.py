"""The SQL grouping and the in-memory one must agree, or one of them is wrong."""
import pytest

from fireblade.core.engine import Case
from fireblade.core.findings import group_alerts, group_alerts_sql

HEADER = 'Timestamp,RuleTitle,Level,Computer,Channel,EventID,MitreTactics,MitreTags,Details,RuleID\n'
ROWS = [
    ('2026-11-14T10:00:00Z', 'Rule A', 'high', 'PC01', 'Security', '4624', 'TA0001', 'T1059', 'first', 'r1'),
    ('2026-11-14T10:04:00Z', 'Rule A', 'high', 'PC01', 'Security', '4624', 'TA0001', 'T1059', 'second', 'r1'),
    ('2026-11-14T10:09:59Z', 'Rule A', 'high', 'PC01', 'Security', '4624', 'TA0001', 'T1059', 'third', 'r1'),
    # more than the gap later: a second burst of the same rule
    ('2026-11-14T14:00:00Z', 'Rule A', 'high', 'PC01', 'Security', '4624', 'TA0001', 'T1059', 'fourth', 'r1'),
    # another host, another rule, and a medium level
    ('2026-11-14T10:02:00Z', 'Rule B', 'medium', 'PC02', 'System', '7045', '', '', 'service', 'r2'),
    ('2026-11-14T10:03:00Z', 'Rule B', 'medium', 'PC02', 'System', '7045', '', '', 'service again', 'r2'),
    # no usable timestamp
    ('', 'Rule C', 'critical', 'PC03', 'Defender', '5001', '', '', 'undated', 'r3'),
    ('not a date', 'Rule C', 'critical', 'PC03', 'Defender', '5001', '', '', 'also undated', 'r3'),
]


@pytest.fixture
def case(tmp_path):
    source = tmp_path / 'alerts.csv'
    source.write_text(HEADER + '\n'.join(','.join(row) for row in ROWS) + '\n', encoding='utf-8')
    case = Case(tmp_path / 'alerts.timeline')
    case.import_csv(source)
    return case


def shape(groups):
    return sorted((group.title, group.host, group.level, group.count,
                   group.start.isoformat() if group.start else None) for group in groups)


def test_both_groupings_produce_the_same_findings(case):
    in_memory, _ = group_alerts([dict(zip(('Timestamp', 'RuleTitle', 'Level', 'Computer', 'Channel',
                                           'EventID', 'MitreTactics', 'MitreTags', 'Details', 'RuleID'), row))
                                 for row in ROWS])
    with case.operation():
        from_sql, incidents = group_alerts_sql(case)
    assert shape(from_sql) == shape(in_memory)
    assert incidents


def test_the_sql_grouping_keeps_every_row_once(case):
    with case.operation():
        groups, _ = group_alerts_sql(case)
    samples = [row for group in groups for row in group.samples]
    assert len(samples) == len(set(samples)) == len(ROWS)


def test_the_sql_grouping_counts_the_undated_alerts(case):
    with case.operation():
        groups, _ = group_alerts_sql(case)
    undated = [group for group in groups if group.start is None]
    assert undated and undated[0].count == 2
    assert undated[0].level == 'critical'


def test_the_sql_grouping_uses_the_gap(case):
    with case.operation():
        groups, _ = group_alerts_sql(case)
    rule_a = sorted(group.count for group in groups if group.title == 'Rule A')
    assert rule_a == [1, 3]


def test_event_ids_are_collected_once_per_group(case):
    with case.operation():
        groups, _ = group_alerts_sql(case)
    assert all(group.event_ids == ('4624',) for group in groups if group.title == 'Rule A')
