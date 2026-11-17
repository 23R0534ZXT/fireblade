"""A file that was not fully read must say why, in the report's own words."""
from fireblade.core.collection import entry_reason


def test_the_reason_of_a_file_comes_from_its_members():
    entry = {'status': 'attention', 'runs': [{'status': 'attention', 'linux_logs': {'members': [
        {'path': 'a.log', 'status': 'attention', 'reason': 'read by one of the two readers'},
        {'path': 'b.log', 'status': 'attention', 'reason': 'read by one of the two readers'},
    ]}}]}
    assert entry_reason(entry) == 'read by one of the two readers'


def test_a_reader_error_is_reported_before_a_warning():
    entry = {'runs': [{'status': 'no_output', 'error': 'Moteur intégré absent : SQLECmd'},
                      {'status': 'complete', 'warnings': ['partial']}]}
    assert entry_reason(entry) == 'Moteur intégré absent : SQLECmd'


def test_a_file_with_nothing_to_say_says_nothing():
    assert entry_reason({'runs': [{'status': 'complete'}]}) == ''
