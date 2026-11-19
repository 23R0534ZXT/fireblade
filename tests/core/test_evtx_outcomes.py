"""A log with nothing in it is named empty; a CSV with records is never called empty."""
from fireblade.core.collection import _empty_output


def test_an_empty_log_is_recognised_from_its_header_alone(tmp_path):
    header_only = tmp_path/'empty.csv'
    header_only.write_text('Time,EventId\n', encoding='utf-8')
    assert _empty_output(header_only) is True


def test_one_record_is_enough_to_exist(tmp_path):
    one_row = tmp_path/'one.csv'
    one_row.write_text('A,B\n1,2\n', encoding='utf-8')
    assert _empty_output(one_row) is False


def test_a_blank_second_line_is_not_a_record(tmp_path):
    blank = tmp_path/'blank.csv'
    blank.write_text('A,B\n\n', encoding='utf-8')
    assert _empty_output(blank) is True


def test_an_unreadable_file_is_never_called_empty(tmp_path):
    missing = tmp_path/'missing.csv'
    assert _empty_output(missing) is False
