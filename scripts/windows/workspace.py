"""Launch only the frozen executable in isolation and verify its workload report."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from scripts.windows.qa_process import run_executable


def validate(report, code):
    expected = {'import_320_distinct_csv_databases', 'click_first_middle_last_analysis', 'search_all_320_analyses', 'save_and_restore_320_analysis_session'}
    checks = report.get('checks', [])
    if (code != 0 or report.get('status') != 'passed' or report.get('platform') != 'win32'
            or not report.get('frozen') or report.get('qt_platform') != 'windows'
            or report.get('imported_documents') != 320 or {c['name'] for c in checks} != expected
            or any(c.get('status') != 'passed' for c in checks)):
        raise RuntimeError('Native 320-analysis qualification failed; inspect report and captures')
    by_name = {c['name']: c.get('details', {}) for c in checks}
    if (by_name['search_all_320_analyses'] != dict(analyses=320, matching_rows=320, errors=0)
            or by_name['save_and_restore_320_analysis_session'] != dict(saved=320, restored=320, active=319)
            or by_name['click_first_middle_last_analysis'].get('visited') != [0, 159, 319]):
        raise RuntimeError('Incomplete 320-analysis workload results')


def main():
    from scripts.windows.visual_matrix import environment
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='Fireblade workspace ') as temporary:
        root = Path(temporary)
        binary = root/'Application été'
        binary.mkdir()
        exe = binary/'Fireblade.exe'
        shutil.copy2(args.exe, exe)
        report = output/'workspace.json'
        code = run_executable([str(exe), '--workspace-report', str(report)], cwd=root,
                              env=environment(root, 1, root/'profile'), timeout=900)
        result = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
        validate(result, code)


if __name__ == '__main__':
    main()
