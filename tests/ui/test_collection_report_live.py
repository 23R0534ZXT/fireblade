"""The Imports table follows a running collection without being rebuilt."""
from fireblade.ui.collection_report import CollectionReport


def test_rows_appear_and_states_change_without_a_reset(qt_application):
    panel = CollectionReport()
    resets = []
    panel.model.modelAboutToBeReset.connect(lambda: resets.append(True))
    report = {'status': 'running', 'source': 'C:/web01', 'output': 'C:/out', 'files': [], 'documents': []}
    panel.set_report(report, 'running')
    resets.clear()   # opening the report legitimately resets the model
    assert panel.model.rowCount() == 0

    report['files'].append({'path': 'C:/web01/a.log', 'status': 'running', 'tools': []})
    panel.refresh(report, 'running')
    assert panel.model.rowCount() == 1
    assert panel.model.entries[0] is report['files'][0]

    report['files'][0]['status'] = 'complete'
    panel.refresh(report, 'running')
    assert panel.model.index(0, 0).data() != 'complete', 'the status is shown, not the raw code'
    report['files'].append({'path': 'C:/web01/b.log', 'status': 'running', 'tools': []})
    panel.refresh(report, 'running')
    assert panel.model.rowCount() == 2
    assert not resets, 'a running collection must grow without resetting the model'

    report['files'].clear()
    panel.refresh(report, 'running')
    assert panel.model.rowCount() == 0
    assert resets, 'a file that leaves the report resets the model'
    panel.close()
