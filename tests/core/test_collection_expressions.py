import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View,Filter,FilterGroup


@pytest.mark.parametrize('expression',[
 '[Items].Count() = 3',
 '[Items][[Amount] > 5].Count() = 2',
 '[Items][[Amount] > 5].Sum([Amount]) = 30',
 '[Items].Average([Amount]) = 11',
 '[Items].Max([Amount]) = 20',
 '[Items].Min([Amount]) = 3',
 "[Items].Exists([Name] = 'évidence')",
 "JsonAll([Items], '[Amount] > 0')",
 "Contains('[Items].Count()', 'Count')",
])
def test_collection_criteria_share_native_filter_pipeline(tmp_path,expression):
    import csv,json
    source=tmp_path/'data.csv'
    with source.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Items']);w.writerow([json.dumps([{'Amount':3,'Name':'a'},{'Amount':10,'Name':'évidence'},{'Amount':20,'Name':'c'}])])
    case=Case(tmp_path/'data.timeline')
    try:
        case.import_csv(source)
        assert case.count(View(expression=FilterGroup('and',[Filter(0,'expression',expression)])))==1
    finally:case.close()

@pytest.mark.parametrize('expression', ["[Items][[Amount] = 10].Single([Name]) = 'évidence'", "[Items][[Amount] > 100].Single([Name]) Is Null", "Contains([Items][[Amount] = 10].Single(), 'évidence')"])
def test_single_collection_matches_object_expression(tmp_path,expression):
    test_collection_criteria_share_native_filter_pipeline(tmp_path,expression)


def test_single_rejects_multiple_objects(tmp_path):
    with pytest.raises(Exception,match='plusieurs objets'):
        test_collection_criteria_share_native_filter_pipeline(tmp_path,'[Items].Single([Amount]) = 3')
