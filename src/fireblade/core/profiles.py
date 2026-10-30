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
    transforms: tuple = ()


PROFILES = (
    Profile(
        "MFTECmd",
        ("EntryNumber", "ParentPath", "FileName"),
        ("Created0x10", "Created0x30"),
        (
            "EntryNumber",
            "ParentPath",
            "FileName",
            "Extension",
            "InUse",
            "Created0x10",
            "LastModified0x10",
            "LastRecordChange0x10",
            "LastAccess0x10",
        ),
    ),
    Profile(
        "EvtxECmd",
        ("EventId", "Provider", "Channel"),
        ("TimeCreated",),
        (
            "TimeCreated",
            "EventId",
            "Level",
            "Provider",
            "Channel",
            "Computer",
            "UserName",
            "MapDescription",
            "PayloadData1",
            "ExecutableInfo",
        ),
    ),
    Profile(
        "PECmd",
        ("ExecutableName", "RunCount", "LastRun"),
        ("LastRun",),
        (
            "ExecutableName",
            "SourceFilename",
            "RunCount",
            "LastRun",
            "PreviousRun0",
            "Volume0Name",
        ),
    ),
    Profile(
        "Hayabusa",
        ("Timestamp", "Computer", "Level", "RuleTitle"),
        ("Timestamp",),
        (
            "Timestamp",
            "Computer",
            "Level",
            "EventID",
            "RuleTitle",
            "Details",
            "RecordID",
        ),
    ),
    Profile(
        "Plaso L2T CSV",
        ("date", "time", "timezone", "MACB", "sourcetype"),
        (),
        (
            "date",
            "time",
            "timezone",
            "MACB",
            "source",
            "sourcetype",
            "user",
            "host",
            "short",
            "desc",
        ),
    ),
)


def all_profiles():
    from fireblade.core.profile_catalog import CATALOG
    from fireblade.core.profile_plugins import load_plugins

    custom, _errors = load_plugins()

    def profile(data):
        return Profile(
            data["name"],
            tuple(data["signature"]),
            tuple(data.get("timestamp", [])),
            tuple(data.get("columns", [])),
            tuple(data.get("booleans", [])),
            tuple(data.get("transforms", [])),
        )

    return (
        tuple(profile(p) for p in custom)
        + tuple(profile(p) for p in CATALOG)
        + PROFILES
    )


def detect_profile(headers):
    present = {h.casefold() for h in headers}
    return next(
        (
            p
            for p in all_profiles()
            if all(h.casefold() in present for h in p.signature)
        ),
        None,
    )


def profile_view(profile, headers):
    lookup = {h.casefold(): i for i, h in enumerate(headers)}
    timestamp = next(
        (lookup[h.casefold()] for h in profile.timestamp if h.casefold() in lookup),
        None,
    )
    view = View(
        sort_column=timestamp,
        sort_type="timestamp" if timestamp is not None else "text",
    )
    view.timestamp_columns = [
        lookup[h.casefold()] for h in profile.timestamp if h.casefold() in lookup
    ]
    view.boolean_columns = [
        lookup[h.casefold()] for h in profile.booleans if h.casefold() in lookup
    ]
    if profile.name.startswith("Hayabusa") and "level" in lookup:
        for value, background in [
            ("crit", "#ffc7ce"),
            ("high", "#ffdfad"),
            ("med", "#fff4c2"),
        ]:
            view.format_rules.append(
                FormatRule(
                    FilterGroup("and", [Filter(lookup["level"], "eq", value)]),
                    background,
                )
            )
    descriptions = [
        lookup[h]
        for h in (
            "desc",
            "source_long",
            "sourcelong",
            "artifactname",
            "description",
            "sourcetype",
        )
        if h in lookup
    ]
    if profile.name in (
        "ForensicTimeline",
        "PsortTimeline",
        "L2tTimeline",
        "MactimeTimeline",
        "Plaso L2T CSV",
        "KapeTriage",
    ):
        for tokens, color in [
            (("prefetch", "execution", "amcache", "registry"), "#e2efda"),
            (("lnk", "jump", "shellbag", "folder"), "#ddebf7"),
            (("deleted", "recycle", "deletion"), "#fce4d6"),
            (("http", "url", "web", "visited"), "#fff2cc"),
            (("event log", "evtx", "winevt"), "#e4dfec"),
        ]:
            conditions = [
                Filter(column, "contains", token)
                for column in descriptions
                for token in tokens
            ]
            if conditions:
                view.format_rules.append(
                    FormatRule(FilterGroup("or", conditions), color)
                )
    planned = profile_transformations(
        profile, [h for h in headers if not h.startswith("Fireblade_")]
    )
    normalized = [
        lookup[d["name"].casefold()]
        for d in planned
        if d["operation"] == "timestamp" and d["name"].casefold() in lookup
    ]
    normalized += [
        i
        for i, h in enumerate(headers)
        if (h.startswith("Fireblade_UTC_") or h in profile.timestamp)
        and i not in normalized
    ]
    view.timestamp_columns = list(dict.fromkeys(normalized + view.timestamp_columns))
    if normalized:
        view.sort_column, view.sort_type = normalized[0], "timestamp"
    category = lookup.get("fireblade_category")
    if category is not None:
        from fireblade.core.timeline_categories import COLORS

        view.format_rules = [
            FormatRule(FilterGroup("and", [Filter(category, "eq", name)]), color)
            for name, color in COLORS.items()
        ]
    order = list(
        dict.fromkeys(
            lookup[h.casefold()] for h in profile.columns if h.casefold() in lookup
        )
    )
    order += [i for i in range(len(headers)) if i not in order]
    return view, order


def profile_transformations(profile, headers):
    """Native SQL counterparts of timeline date, MACB and category treatments."""
    from fireblade.core.profile_aliases import FIELD_ALIASES

    lookup = {h.casefold(): h for h in headers}
    aliases = FIELD_ALIASES.get(profile.name, {})
    result = list(profile.transforms)

    def actual(name):
        return lookup.get(name.casefold()) or lookup.get(
            aliases.get(name, "").casefold()
        )

    def timestamp(name, columns, fmt="invariant", zone_column=None):
        if not all(columns):
            return
        if name.casefold() in lookup and name.casefold() not in {h.casefold() for h in profile.signature}:
            return # a previously synthesized plugin timestamp
        target = name if name.casefold() not in lookup else "Fireblade_UTC_" + name
        if target.casefold() in lookup:
            return
        spec = dict(
            name=target,
            operation="timestamp",
            columns=columns,
            format=fmt,
            timezone="UTC",
        )
        if zone_column:
            spec["timezone_column"] = zone_column
        result.append(spec)

    if profile.name in ("SuperTimeline", "Plaso L2T CSV", "L2tTimeline"):
        timestamp(
            "Timestamp", [actual("date"), actual("time")], "mdy", actual("timezone")
        )
    elif profile.name == "MacTime":
        timestamp("Timestamp", [actual("date")])
    elif profile.name in ("PeScan", "Wisp"):
        pairs = (
            [
                ("CompiledTime", 0, 1),
                ("CreatedTime", 2, 3),
                ("AccessedTime", 4, 5),
                ("ModifiedTime", 6, 7),
            ]
            if profile.name == "PeScan"
            else [
                ("ModifiedTime", 5, 6),
                ("AccessedTime", 7, 8),
                ("RecordChangedTime", 9, 10),
                ("CreatedTime", 11, 12),
            ]
        )
        for target, date, time in pairs:
            if len(headers) > time:
                timestamp(target, [headers[date], headers[time]])
    else:
        for field in profile.timestamp:
            if actual(field):
                timestamp(field, [actual(field)])
    if actual("macb") and not actual("Fireblade_MACBMask"):
        result.append(
            dict(name="Fireblade_MACBMask", operation="macb", columns=[actual("macb")])
        )
    if not actual("Fireblade_Category"):
        if profile.name == "ForensicTimeline" and actual("ArtifactName"):
            result.append(
                dict(
                    name="Fireblade_Category",
                    operation="category",
                    family="forensic",
                    columns=[actual("ArtifactName")],
                )
            )
        elif profile.name == "MacTime" and actual("file name"):
            result.append(
                dict(
                    name="Fireblade_Category",
                    operation="category",
                    family="mactime",
                    columns=[actual("file name")],
                )
            )
        elif profile.name in ("PsortTimeline", "SuperTimeline", "Plaso L2T CSV"):
            description = (
                actual("source_long")
                if profile.name == "PsortTimeline"
                else actual("desc")
            )
            source = actual("source")
            detail = actual("sourcetype") or source
            if description and source:
                result.append(
                    dict(
                        name="Fireblade_Category",
                        operation="category",
                        family="plaso",
                        columns=[description, source, detail],
                    )
                )
    return [d for d in result if d["name"].casefold() not in lookup]
