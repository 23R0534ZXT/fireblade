"""Read-only SRUM export for Linux, where SrumECmd cannot run.

SrumECmd loads the Windows ESE library and refuses to start elsewhere. ``dissect.database`` reads the
same ``SRUDB.dat`` without it: every table of the database becomes a CSV, with the application and
the user resolved through ``SruDbIdMapTable`` and the timestamp read as a date. The columns are the
database's own (nothing is decoded that the database does not say), so the names differ from
SrumECmd's: the table is named in a ``SRUM_Table`` column, and what is not understood stays as it is.
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
            target = output / f"SRUM-{index:03d}-{label}.csv"
            rows = 0
            with target.open("x", encoding="utf-8", newline="") as outgoing:
                writer = csv.writer(outgoing)
                leading = ["SRUM_Table", "SRUM_Record", "Timestamp", "Application", "User"]
                rest = [name for name in columns if name not in ("AppId", "UserId", "TimeStamp")]
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
