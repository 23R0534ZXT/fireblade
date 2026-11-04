import csv

from fireblade.core.engine import Case
from fireblade.core.models import Filter, View


def test_wide_export_keeps_order_every_value_and_fixed_memory_budget(tmp_path):
    source = tmp_path / 'wide.csv'
    with source.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['ID', 'Payload'])
        for index in range(12000):
            writer.writerow([str(index), str(index) + 'é,"\n' + 'x' * 8192])
    case = Case(tmp_path / 'wide.timeline', memory_mb=64, threads=1)
    try:
        case.import_csv(source)
        from fireblade.core.export_rows import SourceOrderCursor
        calls = []
        native = SourceOrderCursor.fetchmany
        def traced(self, size):
            calls.append(size)
            return native(self, size)
        from unittest.mock import patch
        with patch.object(SourceOrderCursor, 'fetchmany', traced):
            receipt = case.export(tmp_path / 'export.csv', View())
        assert calls, 'Fixture must exercise the real DuckDB low-memory fallback'
        assert receipt['written'] == receipt['verified_rows'] == 12000
        assert source.read_bytes() == (tmp_path / 'export.csv').read_bytes()
        assert case.db.execute("SELECT current_setting('memory_limit')").fetchone()[0] == '61.0 MiB'
        filtered = tmp_path / 'filtered.csv'
        case.export(filtered, View(filters=[Filter(0, 'eq', '11999')]), include_annotations=True)
        with filtered.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
        assert len(rows) == 2 and rows[1][0] == '11999'
    finally:
        case.close()
