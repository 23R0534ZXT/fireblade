"""Small, editable display presets. They never transform source evidence."""
from dataclasses import dataclass

from fireblade.core.models import Filter, FilterGroup, FormatRule, View


@dataclass(frozen=True)
class Profile:
    name: str
    signature: tuple[str, ...]
    timestamp: tuple[str, ...]
    columns: tuple[str, ...]
    booleans: tuple[str, ...] = ()


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


def all_profiles():
    from fireblade.core.profile_catalog import CATALOG
    from fireblade.core.profile_plugins import load_plugins
    custom, _errors = load_plugins()
    def profile(data):
        return Profile(data['name'], tuple(data['signature']), tuple(data.get('timestamp', [])),
                       tuple(data.get('columns', [])), tuple(data.get('booleans', [])))
    return tuple(profile(p) for p in custom) + tuple(profile(p) for p in CATALOG) + PROFILES


def detect_profile(headers):
    present = {h.casefold() for h in headers}
    return next((p for p in all_profiles() if all(h.casefold() in present for h in p.signature)), None)


def profile_view(profile, headers):
    lookup = {h.casefold(): i for i, h in enumerate(headers)}
    timestamp = next((lookup[h.casefold()] for h in profile.timestamp if h.casefold() in lookup), None)
    view = View(sort_column=timestamp, sort_type="timestamp" if timestamp is not None else "text")
    view.timestamp_columns = [lookup[h.casefold()] for h in profile.timestamp if h.casefold() in lookup]
    view.boolean_columns = [lookup[h.casefold()] for h in profile.booleans if h.casefold() in lookup]
    if profile.name.startswith("Hayabusa") and "level" in lookup:
        for value, background in [("crit", "#ffc7ce"), ("high", "#ffdfad"), ("med", "#fff4c2")]:
            view.format_rules.append(FormatRule(FilterGroup("and", [Filter(lookup["level"], "eq", value)]), background))
    descriptions = [lookup[h] for h in ("desc", "source_long", "sourcelong", "artifactname", "description", "sourcetype") if h in lookup]
    if profile.name in ("ForensicTimeline", "PsortTimeline", "L2tTimeline", "MactimeTimeline", "Plaso L2T CSV", "KapeTriage"):
        for tokens, color in [(("prefetch", "execution", "amcache", "registry"), "#e2efda"),
                              (("lnk", "jump", "shellbag", "folder"), "#ddebf7"),
                              (("deleted", "recycle", "deletion"), "#fce4d6"),
                              (("http", "url", "web", "visited"), "#fff2cc"),
                              (("event log", "evtx", "winevt"), "#e4dfec")]:
            conditions = [Filter(column, "contains", token) for column in descriptions for token in tokens]
            if conditions:
                view.format_rules.append(FormatRule(FilterGroup("or", conditions), color))
    order = list(dict.fromkeys(lookup[h.casefold()] for h in profile.columns if h.casefold() in lookup))
    order += [i for i in range(len(headers)) if i not in order]
    return view, order
