"""The shortest name that still says what a piece of evidence is.

A collection records the path it read, which is the right record and the wrong
label: in a narrow tree a long saved-files path is one grey line whose only
readable part is the beginning. What the analyst needs is
"Event logs · Security" and the full path in the tooltip.

The table is deliberately short and boring: every entry is a name a forensic
practitioner already uses. When nothing matches, the folder the file was found in
is the label, because that is what a person reads first anyway.
"""
from collections import Counter
from pathlib import Path

# Names that identify an artefact on their own, whatever folder they sit in.
FILES = {
    'amcache.hve': 'Amcache',
    '$mft': 'MFT',
    '$j': 'USN journal',
    '$boot': 'Boot sector',
    '$logfile': 'NTFS log',
    'ntuser.dat': 'NTUSER.DAT',
    'usrclass.dat': 'UsrClass.dat',
    'srudb.dat': 'SRUM',
    'activitiescache.db': 'Activities cache',
    'recentfilecache.bcf': 'RecentFileCache',
    'consolehost_history.txt': 'PowerShell history',
    'places.sqlite': 'Browser history',
    'cookies.sqlite': 'Browser cookies',
    'favicons.sqlite': 'Browser icons',
    'downloads.sqlite': 'Browser downloads',
    'history': 'Browser history',
    'cookies': 'Browser cookies',
    'top sites': 'Browser history',
    'web data': 'Browser forms',
    'login data': 'Browser logins',
    'favicons': 'Browser icons',
    'formhistory.sqlite': 'Browser forms',
    'webcachev01.dat': 'WebCache',
    'system': 'Registry · SYSTEM',
    'software': 'Registry · SOFTWARE',
    'sam': 'Registry · SAM',
    'security': 'Registry · SECURITY',
    'default': 'Registry · DEFAULT',
}

# Formats: the suffix says what the file is.
SUFFIXES = (
    ('.evtx', 'Event logs'),
    ('.pf', 'Prefetch'),
    ('.lnk', 'Shortcuts'),
    ('.automaticdestinations-ms', 'Jump lists'),
    ('.customdestinations-ms', 'Jump lists'),
    ('.timeline', 'Analysis'),
    ('.log1', 'Registry transaction'),
    ('.log2', 'Registry transaction'),
    ('.hve', 'Registry hive'),
    ('.sqlite', 'SQLite database'),
    ('.log', 'Logs'),
)

# Folder names: a folder of one artefact, named by the tool that produced it.
FOLDERS = {
    'amcache': 'Amcache',
    'browser_history': 'Browser history',
    'webcache': 'WebCache',
    'windows_event_logs': 'Event logs',
    'event_logs': 'Event logs',
    'prefetch_files': 'Prefetch',
    'prefetch': 'Prefetch',
    'jumplists-automaticdestinations': 'Jump lists',
    'jumplists-customdestinations': 'Jump lists',
    'jump lists': 'Jump lists',
    'powershell_history': 'PowerShell history',
    'powershell_console': 'PowerShell history',
    'shellbags': 'Shellbags',
    'srum': 'SRUM',
    'usn_journal': 'USN journal',
    'mft': 'MFT',
    'ntuser.dat': 'NTUSER.DAT',
    'recycle_bin': 'Recycle Bin',
    '$recycle.bin': 'Recycle Bin',
    'activitiescache': 'Activities cache',
    'registry': 'Registry',
    'execution': 'Execution artefacts',
    # A container, not an artefact: never a label of its own.
    'saved_files': '',
}

CONTAINERS = ('saved_files',)

# A folder that says where something was, never what it was.
GENERIC_FOLDERS = {
    'c', 'd', 'e', 'users', 'windows', 'system32', 'syswow64', 'appdata', 'roaming',
    'locallow', 'local', 'programdata', 'program files', 'program files (x86)',
    'desktop', 'documents', 'downloads', 'temp', 'tmp', 'config', 'profiles',
    'microsoft', 'packages', 'cache', 'data', 'user data', 'default',
}


def parts_of(path):
    """Path segments, whatever separators the record kept."""
    text = str(path or '').replace('/', '\\').strip('\\')
    return [part for part in text.split('\\') if part]


def _looks_like_file(name):
    return '.' in name or name.startswith('$')


def kind_of(path):
    """The artefact type this path names, or an empty string."""
    segments = parts_of(path)
    if not segments:
        return ''
    name = segments[-1].casefold()
    if name in FILES:
        return FILES[name]
    for suffix, label in SUFFIXES:
        if name.endswith(suffix):
            return label
    # An export named after its artefact: `Prefetch.csv` is a Prefetch export, and its
    # folder is often just the working directory the collector happened to use.
    stem = Path(name).stem.casefold()
    if stem != name and FOLDERS.get(stem):
        return FOLDERS[stem]
    # A folder named after its artefact, nearest one first, containers skipped.
    for segment in reversed(segments[:-1]):
        label = FOLDERS.get(segment.casefold())
        if label:
            return label
    return ''


def _folder_of(path):
    r"""The nearest folder that says something: containers and plumbing are skipped.

    A user profile name (the segment after "Users") is plumbing too: it names a
    person, not an artefact, and a tree full of "OCD" rows says nothing about what
    was read.
    """
    segments = parts_of(path)
    if not segments:
        return ''
    lowered = [segment.casefold() for segment in segments]
    skipped = set(GENERIC_FOLDERS) | set(CONTAINERS)
    for index, segment in enumerate(lowered[:-1]):
        if segment == 'users':
            skipped.add(lowered[index + 1])
    candidates = segments[:-1] if _looks_like_file(segments[-1]) else segments
    for segment in reversed(candidates):
        if segment.casefold() in skipped:
            continue
        return segment
    return segments[-2] if len(segments) > 1 else segments[-1]


def friendly_label(path):
    """What this evidence is; the folder it was found in when that is unknown."""
    kind = kind_of(path)
    if kind:
        return kind
    segments = parts_of(path)
    if not segments:
        return ''
    folder = FOLDERS.get(segments[-1].casefold())
    if folder:
        return folder
    return _folder_of(path) or segments[-1]


def _qualifier(path):
    """What tells two rows of the same type apart: the file's own name."""
    segments = parts_of(path)
    if not segments:
        return ''
    name = segments[-1]
    if not _looks_like_file(name):
        return ''
    stem = Path(name).stem if not name.startswith('$') else name
    if len(stem) < 3:
        # 'a.bin' tells nothing; the numbering pass will separate those rows.
        return ''
    # A channel is read as Security or Sysmon/Operational, not as its escaped form.
    return stem.replace('%4', '/')[:40]


def unique_labels(paths):
    """One label per path, disambiguated only where two would read the same."""
    paths = list(paths)
    labels = {path: friendly_label(path) for path in paths}
    counts = Counter(labels.values())
    result = {}
    for path in paths:
        label = labels[path]
        if counts[label] <= 1:
            result[path] = label
            continue
        if not kind_of(path):
            # The label is the folder, and several files share it: the file's own name
            # says more than "resume (3)" ever will.
            name = (parts_of(path) or [''])[-1]
            result[path] = name or label
            continue
        qualifier = _qualifier(path)
        result[path] = f'{label} · {qualifier}' if qualifier and qualifier.casefold() != label.casefold() else label
    again = Counter(result.values())
    numbered = {}
    for path in paths:
        label = result[path]
        if again[label] <= 1:
            continue
        numbered[label] = numbered.get(label, 0) + 1
        result[path] = f'{label} ({numbered[label]})'
    return result
