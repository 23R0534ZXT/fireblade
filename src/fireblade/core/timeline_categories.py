"""Timeline category semantics ported from TLEFilePlugins Timelines.cs.

Upstream revision 7199c81, MIT; see licenses/TLEFilePlugins-MIT.txt. Categories
are investigative hints, not assertions about an event. Later matching rules
win in Plaso/mactime, matching the upstream sequential assignments.
"""

COLORS = {
    "FileFolderOpening": "#ddebf7",
    "DeletedData": "#fce4d6",
    "Execution": "#e2efda",
    "WebHistory": "#fff2cc",
    "LogFile": "#e4dfec",
    "FolderOpening": "#ddebf7",
    "FileOpening": "#ddebf7",
    "Device|USBUsage": "#d9eaf7",
}


def category_sql(family, columns):
    from fireblade.core.derived import literal

    def contains(col, text, insensitive=False):
        return f"contains({'lower(' + col + ')' if insensitive else col},{literal(text.lower() if insensitive else text)})"

    def anyof(col, tokens):
        return "(" + " OR ".join(contains(col, t) for t in tokens) + ")"

    def starts(col, text):
        return f"starts_with({col},{literal(text)})"

    def ends(col, text, insensitive=False):
        return f"ends_with({'lower(' + col + ')' if insensitive else col},{literal(text.lower() if insensitive else text)})"

    d = columns[0]
    if family == "forensic":
        rules = [
            (
                anyof(d, ["LNK", "JumpLists", "WindowsTimelineActivity", "Shellbags"]),
                "FileFolderOpening",
            ),
            (contains(d, "FileDeletion"), "DeletedData"),
            (
                anyof(d, ["AppCompatCache", "Prefetch", "Amcache", "MFT", "Registry"]),
                "Execution",
            ),
            (contains(d, "Web History"), "WebHistory"),
            (contains(d, "Event Logs"), "LogFile"),
        ]
    elif family == "mactime":
        rules = [
            (contains(d, "$Recycle.Bin"), "DeletedData"),
            (starts(d, "[IEHISTORY]"), "WebHistory"),
            (contains(d, ".lnk", True), "FileOpening"),
            (
                " OR ".join(
                    (
                        starts(d, "[SHIMCACHE]"),
                        ends(d, ".pf", True),
                        starts(d, "[USER ASSIST]"),
                        starts(d, "[PROCESS]"),
                    )
                ),
                "Execution",
            ),
        ]
        rules.reverse()
    elif family == "plaso":
        source = columns[1] if len(columns) > 1 else "''"
        desc = columns[2] if len(columns) > 2 else source
        rules = [
            (
                anyof(d, ["RECYCLE", "DELETED", "Deleted Registry", "$Recycle.Bin"]),
                "DeletedData",
            ),
            (
                " OR ".join(
                    (
                        anyof(
                            d,
                            [
                                "Expiration Time",
                                "Cookie",
                                "Visited",
                                "Flash Cookie",
                                "Location:",
                                "time(s) [HTTP",
                                "Last Visited Time",
                            ],
                        ),
                        f"({contains(d, 'URL')} AND NOT {contains(source, 'FILE')})",
                        f"({contains(d, 'LSO')} AND NOT {contains(source, 'REG')})",
                        contains(d, "http://", True),
                        contains(d, "https://", True),
                        starts(source, "WEBHIST"),
                    )
                ),
                "WebHistory",
            ),
            (
                " OR ".join(
                    (
                        anyof(d, ["lnk/shell_items", "BagMRU", "ShellNoRoam/Bags"]),
                        contains(desc, "File entry shell item"),
                    )
                ),
                "FolderOpening",
            ),
            (
                " OR ".join(
                    (
                        anyof(
                            d,
                            [
                                "visited file://",
                                "CreateDate",
                                "URL:file://",
                                "File Opened",
                                "Folder opened",
                                "Shortcut LNK",
                                "RecentDocs key",
                                "Link target:",
                                "File attribute flags",
                                "Birth droid volume identifier:",
                                "UserAssist entry",
                                "Recently opened file",
                                "file of extension",
                                "RecentDocs",
                            ],
                        ),
                        ends(d, ".lnk", True),
                        ends(d, "LNK"),
                        f"(({contains(d, 'Recently')} OR {contains(d, 'file://')}) AND NOT {contains(desc, 'Firefox')})",
                    )
                ),
                "FileOpening",
            ),
            (
                anyof(
                    d,
                    [
                        "MountPoints2",
                        "volume mounted",
                        "USB",
                        "/USB/Vid_",
                        "Enum/USBSTOR/Disk",
                        "RemovableMedia",
                        "STORAGE/RemovableMedia",
                        "drive mounted",
                        "Drive last mounted",
                        "SetupAPI Log",
                    ],
                ),
                "Device|USBUsage",
            ),
            (
                anyof(d, ["EVT", "XP Firewall Log", "Event Level:"])
                + " OR "
                + starts(source, "EVT"),
                "LogFile",
            ),
            (
                " OR ".join(
                    (
                        anyof(
                            d,
                            [
                                "Prefetch {",
                                "AppCompatCache",
                                r"\Software\Sysinternals",
                                "typed the following cmd",
                                "CMD typed",
                                "Last run",
                                "RunMRU",
                                "MUICache",
                                "UserAssist key",
                                "Time of Launch",
                                "Prefetch",
                                "SHIMCACHE",
                                "Scheduled",
                                "was run",
                                "UEME_",
                            ],
                        ),
                        ends(d, ".pf", True),
                        starts(d, "[PROCESS]"),
                    )
                ),
                "Execution",
            ),
        ]
        rules.reverse()
    else:
        raise ValueError("Famille de timeline inconnue")
    return (
        "CASE "
        + " ".join(
            f"WHEN ({condition}) THEN {literal(category)}"
            for condition, category in rules
        )
        + " ELSE NULL END"
    )
