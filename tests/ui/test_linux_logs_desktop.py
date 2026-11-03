from fireblade.validation.linux_logs import verify_linux_logs


def test_linux_log_desktop_import_grid_notes_and_case_restore(qt_application,tmp_path):
    result=verify_linux_logs(qt_application,tmp_path)
    assert result['rows']==12 and result['source_files_unchanged'] and result['case_restored']
