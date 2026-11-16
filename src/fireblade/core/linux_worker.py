"""Read a Linux log in a process of its own.

The reader is pure Python, so eight worker threads stay on a single core: measured
on a 250 MB access.log, two files read by two threads finished in 50.8 s against
28.3 s alone, a gain of x1.11. This module is the far end of `parse_pool`: one job
per line on stdin, one answer per line on stdout, so the parent keeps the report
and the child keeps the CPU.
"""
import json
import sys
from pathlib import Path


def _plain(value):
    """JSON has no Path: a result travels as text."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def main():
    from fireblade.core.linux_logs import parse
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
            if job.get('stop'):
                break
            result = parse(Path(job['source']), Path(job['output']), span=job.get('span'))
            answer = dict(status='ok', result=_plain(result))
        except BaseException as exc:  # noqa: BLE001 - the parent needs the reason
            answer = dict(status='error', error='%s: %s' % (type(exc).__name__, exc))
        sys.stdout.write(json.dumps(answer) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
