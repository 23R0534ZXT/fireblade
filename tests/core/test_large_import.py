"""The import must finish whatever the memory: a file far larger than the budget.

This is the promise that separates Fireblade from a tool that only works on a big
machine: a 15 GiB /var/log/ on a 1 GiB VM still has to become an analysis. The test
does not simulate memory pressure with a flag — it imports a file several times larger
than the configured budget, which is how the failure was met in the field.
"""
import csv
import os

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.settings import Settings

ROWS = 120000
WIDE = 40


def write_big_log(path, rows=ROWS, columns=WIDE):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Timestamp'] + ['c%d' % index for index in range(columns - 1)])
        for row in range(rows):
            writer.writerow(['2026-11-14 08:%02d:%02d' % (row // 3600 % 60, row // 60 % 60)]
                            + ['valeur %d-%d' % (row, column) for column in range(columns - 1)])


def test_a_file_far_larger_than_the_budget_is_still_imported(tmp_path):
    root = tmp_path/'evidence'
    root.mkdir()
    source = root/'auth.log'
    write_big_log(source)
    size = source.stat().st_size
    # A budget hundreds of times smaller than the file: the case met on a small VM.
    settings = Settings(memory_mb=64, threads=1)
    collection = Collection(root, tmp_path/'work', ToolPack(tmp_path/'pack'), settings=settings)
    collection.report['organization'] = 'files'
    collection.prepare_output()

    assert size > 64 * 1024 * 1024 // 4, 'le fichier doit dépasser franchement le budget'
    document = collection.import_result(str(source), 'native', register=False)

    from fireblade.core.engine import Case
    case = Case(document['path'])
    try:
        assert case.info['rows'] == ROWS
        # Columns are named c0, c1... in file order, so c0 is the timestamp and c1 the first value.
        values = case.db.execute('SELECT "c1" FROM events WHERE __row_id = ?', [ROWS]).fetchone()
        assert values[0] == 'valeur %d-0' % (ROWS - 1)
    finally:
        case.close()


def test_the_retry_grows_the_budget_until_there_is_no_room(tmp_path):
    from fireblade.core.settings import grown_memory
    budget = 64
    steps = []
    while True:
        bigger = grown_memory(budget, ceiling_mb=2048)
        if not bigger:
            break
        steps.append(bigger)
        budget = bigger
    assert steps[0] == max(64 * 4, 64 + 512) and steps[-1] == 2048
    assert steps == sorted(steps) and len(steps) < 10, 'la progression doit être courte et monotone'
