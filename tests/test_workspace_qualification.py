import copy

import pytest

from scripts.windows.workspace import validate


def report():
    details = {
        'import_320_distinct_csv_databases': dict(documents=320, rows_per_file=1),
        'click_first_middle_last_analysis': dict(visited=[0, 159, 319]),
        'search_all_320_analyses': dict(analyses=320, matching_rows=320, errors=0),
        'save_and_restore_320_analysis_session': dict(saved=320, restored=320, active=319),
    }
    return dict(status='passed', platform='win32', frozen=True, qt_platform='windows', imported_documents=320,
                checks=[dict(name=name, status='passed', details=value) for name, value in details.items()])


def test_native_workspace_gate_accepts_complete_frozen_windows_workload():
    validate(report(), 0)


@pytest.mark.parametrize('mutation', [
    lambda r: r.update(frozen=False), lambda r: r.update(platform='linux'),
    lambda r: r.update(qt_platform='offscreen'), lambda r: r.update(imported_documents=319),
    lambda r: r.update(checks=[]), lambda r: r['checks'][0].update(status='failed'),
    lambda r: r['checks'][2]['details'].update(matching_rows=319),
    lambda r: r['checks'][3]['details'].update(restored=319),
    lambda r: r['checks'][1]['details'].update(visited=[319]),
])
def test_native_workspace_gate_rejects_incomplete_or_source_only_workload(mutation):
    result=report();mutation(result)
    with pytest.raises(RuntimeError):validate(result, 0)
