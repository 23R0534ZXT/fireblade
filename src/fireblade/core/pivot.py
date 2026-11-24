"""What launched a process: reading one row well enough to ask the right question.

The analyst sees a PowerShell event and wants the process that started it. Nothing in the
schema says which column holds the command: EvtxECmd writes ScriptBlockText, Sysmon writes
Image and CommandLine, 4688 writes NewProcessName and CreatorProcessName. This module reads
a row the way a practitioner does — by column name, then by what the value looks like — and
returns the anchor the timeline needs: the token to search, the host, and the moment.

Nothing is inferred about the launch itself. The anchor only says what to look for, on which
machine, and around which instant; the correlation that follows shows the events, and the
analyst reads them.
"""

import re
from pathlib import PureWindowsPath

HOST_COLUMNS = (
    "computer",
    "computername",
    "hostname",
    "host",
    "machine",
    "machine name",
    "destcomputer",
    "nom de l’ordinateur",
)
TIME_COLUMNS = (
    "timecreated",
    "timestamp",
    "time created",
    "date",
    "datetime",
    "dateandtime",
    "horodatage",
    "eventtime",
    "utctime",
)
PROCESS_COLUMNS = (
    "image",
    "newprocessname",
    "processname",
    "process name",
    "application",
    "executable",
    "program",
    "parentprocessname",
    "creatorprocessname",
)
COMMAND_COLUMNS = (
    "commandline",
    "command line",
    "scriptblocktext",
    "payload",
    "details",
    "processcommandline",
    "script block text",
)
PARENT_COLUMNS = (
    "parentprocessname",
    "creatorprocessname",
    "parentimage",
    "parentprocessid",
    "parent process name",
)

_WINDOWS_PATH = re.compile(r'[A-Za-z]:\\[^"\'<>|]*')
_SHELLS = (
    "powershell.exe",
    "pwsh.exe",
    "cmd.exe",
    "wscript.exe",
    "cscript.exe",
    "mshta.exe",
    "rundll32.exe",
    "regsvr32.exe",
    "certutil.exe",
    "bitsadmin.exe",
    "schtasks.exe",
    "msbuild.exe",
    "installutil.exe",
    "wmic.exe",
    "psexec.exe",
)


def _column(headers, names):
    lowered = {str(header).strip().casefold(): index for index, header in enumerate(headers)}
    for name in names:
        if name in lowered:
            return lowered[name]
    return None


def _basename(value):
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    if "\\" in text or "/" in text:
        return PureWindowsPath(text.replace("/", "\\")).name
    return text.split()[0]


def _token_of(value, shell_hint=""):
    """The shortest string worth searching: a process name, or the first word of a command."""
    text = str(value or "").strip()
    if not text:
        return ""
    found = _WINDOWS_PATH.search(text)
    if found:
        name = PureWindowsPath(found.group(0).strip()).name
        if name:
            return name
    lowered = text.casefold()
    for shell in _SHELLS:
        if shell in lowered:
            return shell
    first = re.split(r"[\s;|&]+", text.strip('"'))[0]
    return first[:60]


def anchor_of(headers, values):
    """The search to run for 'what launched this?', or None when the row says nothing.

    Returns the token (a process name or the first word of a command), the host it ran on
    when the row names one, the parent process when the row carries it, and the moment.
    """
    if not headers or not values:
        return None
    process_index = _column(headers, PROCESS_COLUMNS)
    command_index = _column(headers, COMMAND_COLUMNS)
    host_index = _column(headers, HOST_COLUMNS)
    time_index = _column(headers, TIME_COLUMNS)
    parent_index = _column(headers, PARENT_COLUMNS)

    process = str(values[process_index] or "") if process_index is not None else ""
    command = str(values[command_index] or "") if command_index is not None else ""
    token = _token_of(process) or _token_of(command)
    if not token or len(token) < 3:
        return None
    host = str(values[host_index] or "") if host_index is not None else ""
    parent = str(values[parent_index] or "") if parent_index is not None else ""
    moment = str(values[time_index] or "") if time_index is not None else ""
    return dict(
        token=token,
        host=host,
        parent=parent,
        moment=moment,
        process=_basename(process) or token,
        command=command[:400],
    )
