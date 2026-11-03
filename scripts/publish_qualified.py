"""Publish an existing successful Windows build without rebuilding its executable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from scripts.release import application_version, publish


REQUIRED_JOBS = {
    'Python syntax and name checks',
    'Windows / Python 3.11', 'Windows / Python 3.12', 'Windows / Python 3.13',
    'Windows x64 executable', 'Native Windows UNC and long paths',
    'Native upstream reader matrix', 'Windows visual and 3-GiB qualification',
    'Native EXE with 320 analyses',
}


def qualified_commit(run, jobs, repository):
    if (run.get('repository', {}).get('full_name') != repository or
        run.get('head_repository', {}).get('full_name') != repository or
        run.get('path', '').split('@', 1)[0] != '.github/workflows/windows.yml' or
        run.get('status') != 'completed' or run.get('conclusion') != 'success'):
        raise ValueError('Expected a successful Windows workflow from this repository')
    commit = run.get('head_sha', '')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Invalid qualified commit')
    for name in REQUIRED_JOBS:
        matches = [job for job in jobs if job.get('name') == name]
        if len(matches) != 1 or matches[0].get('conclusion') != 'success':
            raise ValueError('Missing or unsuccessful qualification: '+name)
    return commit


def inspect_run(repository, run_id):
    if not re.fullmatch(r'[1-9][0-9]*', run_id):
        raise ValueError('Invalid workflow run ID')
    def api(endpoint):
        result = subprocess.run(['gh', 'api', endpoint], check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    run = api(f'repos/{repository}/actions/runs/{run_id}')
    jobs = api(f'repos/{repository}/actions/runs/{run_id}/jobs?per_page=100')
    if jobs['total_count'] > 100:
        raise ValueError('Qualification has too many jobs to validate in one page')
    return qualified_commit(run, jobs['jobs'], repository)


def verify_binary(executable, report, version):
    verification = report.get('bundle_verification', {})
    if (report.get('status') != 'passed' or verification.get('status') != 'passed' or
        verification.get('application_version') != version):
        raise ValueError('Missing or mismatched Windows verification report')
    with Path(executable).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != verification.get('executable_sha256'):
        raise ValueError('Executable SHA-256 differs from the qualified artifact')
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect', 'publish'))
    args = parser.parse_args()
    repository = os.environ['GITHUB_REPOSITORY']
    commit = inspect_run(repository, os.environ['REQUESTED_RUN_ID'])
    if args.operation == 'inspect':
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write('commit='+commit+'\n')
        return
    if commit != os.environ['QUALIFIED_COMMIT']:
        raise ValueError('Qualification changed between inspection and publication')
    root = Path.cwd()
    source = root/'qualified-source'
    version = application_version(source)
    if application_version(root) != version:
        raise ValueError('Release notes and qualified source versions must match')
    executables = list((root/'artifacts/executable').rglob('Fireblade.exe'))
    reports = list((root/'artifacts/verification').rglob('windows-single-file.json'))
    if len(executables) != 1 or len(reports) != 1:
        raise ValueError('Expected exactly one executable and one verification report')
    report = json.loads(reports[0].read_text(encoding='utf-8-sig'))
    verify_binary(executables[0], report, version)
    # Keep the tested code/tag while using the final release notes from main.
    (source/'docs/development/RELEASE-NOTES.md').write_text(
        (root/'docs/development/RELEASE-NOTES.md').read_text(encoding='utf-8'), encoding='utf-8')
    result = publish(source, executables[0], repository, commit, 'v'+version)
    (root/'artifacts/release.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('Published '+result['tag']+' from qualified commit '+commit)


if __name__ == '__main__':
    main()
