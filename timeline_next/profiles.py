"""Small, editable display presets. They never transform source evidence."""
from dataclasses import dataclass

from .models import Filter, FilterGroup, FormatRule, View


@dataclass(frozen=True)
class Profile:
    name: str
    signature: tuple[str, ...]
    timestamp: tuple[str, ...]
    columns: tuple[str, ...]


PROFILES = (
    Profile("MFTECmd", ("EntryNumber", "ParentPath", "FileName"), ("Created0x10", "Created0x30"),
            ("EntryNumber", "ParentPath", "FileName", "Extension", "InUse", "Created0x10", "LastModified0x10", "LastRecordChange0x10", "LastAccess0x10")),
    Profile("EvtxECmd", ("EventId", "Provider", "Channel"), ("TimeCreated",),
            ("TimeCreated", "EventId", "Level", "Provider", "Channel", "Computer", "UserName", "MapDescription", "PayloadData1", "ExecutableInfo")),
    Profile("PECmd", ("ExecutableName", "RunCount", "LastRun"), ("LastRun",),
            ("ExecutableName", "SourceFilename", "RunCount", "LastRun", "PreviousRun0", "Volume0Name")),
    Profile("Hayabusa", ("Timestamp", "Computer", "Level", "RuleTitle"), ("Timestamp",),
            ("Timestamp", "Computer", "Level", "EventID", "RuleTitle", "Details", "RecordID")),
    Profile("Plaso L2T CSV", ("date", "time", "timezone", "MACB", "sourcetype"), (),
            ("date", "time", "timezone", "MACB", "source", "sourcetype", "user", "host", "short", "desc")),
)


def detect_profile(headers):
    present = {h.casefold() for h in headers}
    return next((p for p in PROFILES if all(h.casefold() in present for h in p.signature)), None)


def profile_view(profile, headers):
    lookup = {h.casefold(): i for i, h in enumerate(headers)}
    timestamp = next((lookup[h.casefold()] for h in profile.timestamp if h.casefold() in lookup), None)
    view = View(sort_column=timestamp, sort_type="timestamp" if timestamp is not None else "text")
    if profile.name == "Hayabusa":
        for value, background in [("crit", "#ffc7ce"), ("high", "#ffdfad"), ("med", "#fff4c2")]:
            view.format_rules.append(FormatRule(FilterGroup("and", [Filter(lookup["level"], "eq", value)]), background))
    order = [lookup[h.casefold()] for h in profile.columns if h.casefold() in lookup]
    order += [i for i in range(len(headers)) if i not in order]
    return view, order
