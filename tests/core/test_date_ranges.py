import csv
from datetime import datetime,timedelta,timezone
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.filter_text import parse_filter
from fireblade.core.date_ranges import RANGES


def test_relative_dates_include_boundaries_and_reject_unknown_names(tmp_path):
    now=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    source=tmp_path/'s.csv'
    with source.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Date']);w.writerows([[(now+timedelta(days=days)).isoformat()] for days in [-1,0,1]])
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source)
        for mode in ('Yesterday','Today','Tomorrow'):
            assert case.count(View(expression=parse_filter(f"InDateRange([Date], '{mode}')",case.headers)))==1
        for mode in RANGES:
            view=View(expression=parse_filter(f"InDateRange([Date], '{mode}')",case.headers));case.validate_view(view);case.count(view)
        with pytest.raises(ValueError,match='Intervalle de date'):
            case.count(View(expression=parse_filter("InDateRange([Date], 'unknown')",case.headers)))
    finally:case.close()
