import csv

from fireblade.core.engine import Case
from fireblade.core.models import View


def test_equal_group_counts_export_in_stable_value_order_with_nulls_last(tmp_path):
    source = tmp_path / 'groups.csv'
    source.write_text('Artifact,User\nZulu,bob\nAlpha,bob\n,alice\nZulu,bob\nAlpha,bob\n,alice\n', encoding='utf-8')
    case = Case(tmp_path / 'groups.timeline')
    try:
        case.import_csv(source)
        for groups, expected in [([0], [['Alpha', '2'], ['Zulu', '2'], ['', '2']]),
                                 ([0, 1], [['Alpha', 'bob', '2'], ['Zulu', 'bob', '2'], ['', 'alice', '2']])]:
            target = tmp_path / 'export.csv'
            case.export(target, View(groups=groups), grouped=True)
            with target.open(encoding='utf-8-sig', newline='') as incoming:
                reader = csv.reader(incoming)
                next(reader)
                assert list(reader) == expected
    finally:
        case.close()
