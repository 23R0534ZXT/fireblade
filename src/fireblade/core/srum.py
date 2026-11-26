"""Read-only SRUM export for Linux, where SrumECmd cannot run.

SrumECmd loads the Windows ESE library and refuses to start elsewhere. ``dissect.database`` reads the
same ``SRUDB.dat`` without it: every table of the database becomes a CSV, with the application and
the user resolved through ``SruDbIdMapTable`` and the timestamp read as a date. The columns are the
database's own (nothing is decoded that the database does not say). The providers SrumECmd also
writes come out with SrumECmd's columns, in its order and under its names (``Id``, ``Timestamp``,
``ExeInfo``, ``Sid``, ``BytesReceived``…), so the same profiles, dates and searches apply whichever
reader produced the table. What the database cannot say — the user name behind a SID (it lives in the
SOFTWARE hive), the description and timestamp of an executable — stays empty rather than guessed. The
other tables keep the database's own columns, with the table named in a ``SRUM_Table`` column.
"""

import csv
from pathlib import Path

from fireblade.core.errors import OperationCancelled, job_cancelled

PROVIDERS = {
    "{973F5D5C-1D90-4944-BE8E-24B94231A174}": "NetworkUsage",
    "{DD6636C4-8929-4683-974E-22C046A43763}": "NetworkConnections",
    "{DA73FB89-2BEA-4DDC-86B8-6E048C6DA477}": "EnergyEstimator",
    "{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}": "EnergyUsage",
    "{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}LT": "EnergyUsageLongTerm",
    "{D10CA2FE-6FCF-4F6D-848E-B2E99266FA89}": "AppResourceUseInfo",
    "{D10CA2FE-6FCF-4F6D-848E-B2E99266FA86}": "PushNotifications",
    "{5C8CF1C7-7257-4F13-B223-970EF5939312}": "AppTimelineProvider",
    "{7ACBBAA3-D029-4BE4-9A7A-0885927F1D8F}": "VfuProvider",
    "{17F4D97B-F26A-5E79-3A82-90040A47D13D}": "SdpVolumeProvider",
    "{841A7317-3805-518B-C2EA-AD224CB4AF84}": "SdpPhysicalDiskProvider",
    "{DC3D3B50-BB90-5066-FA4E-A5F90DD8B677}": "SdpCpuProvider",
    "{EEE2F477-0659-5C47-EF03-6D6BEFD441B3}": "SdpNetworkProvider",
}


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "hex:" + bytes(value).hex()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# What SrumECmd writes for a provider, after its common columns: (table name, columns, where each
# comes from when the database names it differently). A table whose database columns do not cover its
# list stays in the generic export below, so nothing is renamed on a guess.
COMMON = ["Id", "Timestamp", "ExeInfo", "ExeInfoDescription", "ExeTimestamp"]
IDENTITY = ["SidType", "Sid", "UserName", "UserId", "AppId"]
SRUMECMD = {
    "NetworkUsage": (
        "NetworkUsage",
        [
            "BytesReceived",
            "BytesSent",
            "InterfaceLuid",
            "InterfaceType",
            "L2ProfileFlags",
            "L2ProfileId",
            "ProfileName",
        ],
        {"BytesReceived": "BytesRecvd"},
    ),
    "NetworkConnections": (
        "NetworkConnection",
        [
            "ConnectedTime",
            "ConnectStartTime",
            "InterfaceLuid",
            "InterfaceType",
            "L2ProfileFlags",
            "L2ProfileId",
            "ProfileName",
        ],
        {},
    ),
    "PushNotifications": (
        "PushNotification",
        ["NetworkType", "NotificationType", "PayloadSize"],
        {},
    ),
    "AppResourceUseInfo": (
        "AppResourceUseInfo",
        [
            "BackgroundBytesRead",
            "BackgroundBytesWritten",
            "BackgroundContextSwitches",
            "BackgroundCycleTime",
            "BackgroundNumberOfFlushes",
            "BackgroundNumReadOperations",
            "BackgroundNumWriteOperations",
            "FaceTime",
            "ForegroundBytesRead",
            "ForegroundBytesWritten",
            "ForegroundContextSwitches",
            "ForegroundCycleTime",
            "ForegroundNumberOfFlushes",
            "ForegroundNumReadOperations",
            "ForegroundNumWriteOperations",
        ],
        {},
    ),
    "EnergyUsage": (
        "EnergyUsage",
        [
            "IsLt",
            "ConfigurationHash",
            "EventTimestamp",
            "StateTransition",
            "ChargeLevel",
            "CycleCount",
            "DesignedCapacity",
            "FullChargedCapacity",
            "ActiveAcTime",
            "ActiveDcTime",
            "ActiveDischargeTime",
            "ActiveEnergy",
            "CsAcTime",
            "CsDcTime",
            "CsDischargeTime",
            "CsEnergy",
        ],
        {},
    ),
    "EnergyUsageLongTerm": (
        "EnergyUsage",
        [
            "IsLt",
            "ConfigurationHash",
            "EventTimestamp",
            "StateTransition",
            "ChargeLevel",
            "CycleCount",
            "DesignedCapacity",
            "FullChargedCapacity",
            "ActiveAcTime",
            "ActiveDcTime",
            "ActiveDischargeTime",
            "ActiveEnergy",
            "CsAcTime",
            "CsDcTime",
            "CsDischargeTime",
            "CsEnergy",
        ],
        {},
    ),
}
# Present in the database's own columns under another name, or computed from one that is present.
COMPUTED = {"IsLt", "InterfaceType", "ProfileName"}
# The interface types (IANA ifType, the top 16 bits of the interface LUID) a reader names.
INTERFACE_TYPES = {6: "Ethernet", 24: "SoftwareLoopback", 71: "IEEE80211", 131: "Tunnel"}
WELL_KNOWN_SIDS = {
    "S-1-5-18": "LOCAL SYSTEM",
    "S-1-5-19": "LOCAL SERVICE",
    "S-1-5-20": "NETWORK SERVICE",
    "S-1-5-32-544": "Administrators",
}


def srumecmd_layout(provider, columns):
    """The SrumECmd table this provider is written as, or None when the database cannot fill it."""
    entry = SRUMECMD.get(provider)
    if entry is None:
        return None
    name, wanted, aliases = entry
    present = set(columns)
    for column in wanted:
        if column in COMPUTED:
            continue
        if aliases.get(column, column) not in present:
            return None
    return name, wanted, aliases


def srumecmd_row(layout, number, values, stamp, application, user, is_long_term=False):
    """One record as SrumECmd writes it: its columns, its order, empty where the database is silent."""
    _name, wanted, aliases = layout
    sid = user if str(user).startswith("S-1-") else ""
    sid_type = "" if not sid else ("WellKnown" if sid in WELL_KNOWN_SIDS else "UnknownOrUserSid")
    row = {
        "Id": values.get("AutoIncId", number),
        "Timestamp": stamp,
        "ExeInfo": application,
        "ExeInfoDescription": "",
        "ExeTimestamp": "",
        "SidType": sid_type,
        "Sid": sid,
        "UserName": WELL_KNOWN_SIDS.get(sid, ""),
        "UserId": values.get("UserId"),
        "AppId": values.get("AppId"),
    }
    for column in wanted:
        source = aliases.get(column, column)
        if column == "IsLt":
            row[column] = "True" if is_long_term else "False"
        elif column == "InterfaceType":
            luid = values.get("InterfaceLuid")
            try:
                kind = (int(luid) >> 48) & 0xFFFF
                row[column] = INTERFACE_TYPES.get(kind, str(kind))
            except (TypeError, ValueError):
                row[column] = ""
        elif column == "ProfileName":
            row[column] = ""
        else:
            row[column] = values.get(source)
    return [_cell(row[name]) for name in COMMON + IDENTITY + wanted]


def srumecmd_header(layout):
    return COMMON + IDENTITY + layout[1]


def parse(source, output, progress=lambda _: None):
    from dissect.database.ese.tools.sru import SKIP_TABLES, SRU

    source, output = Path(source), Path(output)
    warnings, outputs = [], []
    with source.open("rb") as stream:
        sru = SRU(stream)
        for index, table in enumerate(sru.db.tables()):
            if job_cancelled():
                raise OperationCancelled()
            if table.name in SKIP_TABLES or table.name.startswith("MSys"):
                continue
            label = PROVIDERS.get(table.name, table.name)
            progress("SRUM : " + label)
            columns = [column.name for column in table.columns]
            layout = srumecmd_layout(label, columns)
            if layout is not None:
                label = layout[0]
            target = output / f"SRUM-{index:03d}-{label}.csv"
            rows = 0
            with target.open("x", encoding="utf-8", newline="") as outgoing:
                writer = csv.writer(outgoing)
                leading = ["SRUM_Table", "SRUM_Record", "Timestamp", "Application", "User"]
                rest = [name for name in columns if name not in ("AppId", "UserId", "TimeStamp")]
                if layout is not None:
                    writer.writerow(srumecmd_header(layout))
                else:
                    writer.writerow(
                        leading + rest + [name for name in ("AppId", "UserId") if name in columns]
                    )
                for number, record in enumerate(table.records(), 1):
                    if job_cancelled():
                        raise OperationCancelled()
                    values = {}
                    for name in columns:
                        try:
                            values[name] = record.get(name)
                        except Exception as exc:  # noqa: BLE001 - a column that cannot be read
                            values[name] = None
                            if len(warnings) < 50:
                                warnings.append(f"{label} record {number}, {name}: {exc}")
                    stamp = ""
                    if values.get("TimeStamp") is not None:
                        try:
                            from dissect.util.ts import oatimestamp

                            stamp = oatimestamp(values["TimeStamp"]).isoformat()
                        except (ValueError, OverflowError, TypeError):
                            stamp = _cell(values["TimeStamp"])
                    application = user = ""
                    try:
                        application = (
                            _cell(sru.resolve_id(values["AppId"]))
                            if values.get("AppId") is not None
                            else ""
                        )
                        user = (
                            _cell(sru.resolve_id(values["UserId"]))
                            if values.get("UserId") is not None
                            else ""
                        )
                    except Exception as exc:  # noqa: BLE001 - an id the map does not know
                        if len(warnings) < 50:
                            warnings.append(f"{label} record {number}: {exc}")
                    if layout is not None:
                        writer.writerow(
                            srumecmd_row(
                                layout,
                                number,
                                values,
                                stamp,
                                application,
                                user,
                                is_long_term=table.name.endswith("LT"),
                            )
                        )
                        rows += 1
                        continue
                    writer.writerow(
                        [label, number, stamp, application, user]
                        + [_cell(values.get(name)) for name in rest]
                        + [
                            _cell(values.get(name))
                            for name in ("AppId", "UserId")
                            if name in columns
                        ]
                    )
                    rows += 1
            if rows:
                outputs.append(dict(csv=str(target), table=label, rows=rows))
            else:
                target.unlink()
    if not outputs:
        raise ValueError("SRUM database without any record")
    return dict(warnings=warnings, outputs=outputs)
