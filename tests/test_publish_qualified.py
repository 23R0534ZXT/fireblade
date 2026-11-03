import hashlib

import pytest

from scripts.publish_qualified import REQUIRED_JOBS, qualified_commit, verify_binary


def successful():
    run = dict(repository=dict(full_name='owner/repo'), head_repository=dict(full_name='owner/repo'),
        path='.github/workflows/windows.yml', status='completed', conclusion='success', head_sha='a'*40)
    jobs = [dict(name=name, conclusion='success') for name in REQUIRED_JOBS]
    return run, jobs


def test_only_successful_windows_gates_qualify():
    run, jobs = successful()
    assert qualified_commit(run, jobs, 'owner/repo') == 'a'*40
    jobs[0]['conclusion'] = 'skipped'
    with pytest.raises(ValueError, match='qualification'):
        qualified_commit(run, jobs, 'owner/repo')


@pytest.mark.parametrize('field,value', [('conclusion','failure'), ('status','in_progress'),
    ('path','.github/workflows/linux-logs.yml'), ('head_sha','main'),
    ('head_repository',dict(full_name='fork/repo'))])
def test_wrong_workflow_or_source_is_rejected(field, value):
    run, jobs = successful(); run[field] = value
    with pytest.raises(ValueError): qualified_commit(run, jobs, 'owner/repo')


def test_missing_or_duplicate_required_jobs_are_rejected():
    run, jobs = successful()
    with pytest.raises(ValueError): qualified_commit(run, jobs[:-1], 'owner/repo')
    with pytest.raises(ValueError): qualified_commit(run, jobs+[jobs[0]], 'owner/repo')


def test_binary_must_match_the_qualified_hash_and_version(tmp_path):
    executable = tmp_path/'Fireblade.exe'; executable.write_bytes(b'MZ qualified fixture')
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    report = dict(status='passed', bundle_verification=dict(status='passed',
        application_version='0.2.0', executable_sha256=digest))
    assert verify_binary(executable, report, '0.2.0') == digest
    with pytest.raises(ValueError): verify_binary(executable, report, '0.1.1')
    executable.write_bytes(b'MZ other build')
    with pytest.raises(ValueError, match='SHA-256'): verify_binary(executable, report, '0.2.0')
