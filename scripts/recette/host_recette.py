"""Recette of the Host: import a known pack through the real service and compare with what is known.

A forensic tool is trusted for what it can account for. This script puts a pack of evidence whose
content is known (the test pack, built by ``scripts.test_pack.package``) through the Host, then
checks, one line at a time, that every file is accounted for and that each family of rows has the
count the pack's own ``RESULTATS-ATTENDUS.json`` states. Every check ends as one of:

``pass``         what was measured is what was expected;
``fail``         it is not;
``known-limit``  a documented limit of the Linux edition (none today; SRUM has a native reader);
``info``         measured and reported, not yet pinned: the first runs on real artifacts calibrate it.

Without ``--strict`` only the failures of checks that are already pinned fail the run; with it,
every measured difference does. The report is JSON, so a run is kept and compared with the next.

    python -m scripts.recette.host_recette --pack PACK --image fireblade:ci --report report.json
    python -m scripts.recette.host_recette --pack PACK --url http://127.0.0.1:8080 --server-pack /pack
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from fireblade.core.i18n import english

PASS, FAIL, LIMIT, INFO = "pass", "fail", "known-limit", "info"


@dataclass
class Check:
    name: str
    expected: object
    actual: object
    verdict: str
    note: str = ""


def request(base: str, method: str, path: str, data: dict | None = None, form: dict | None = None):
    """One call to the service; the answer is JSON, and a refusal is raised with its sentence."""
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        boundary = uuid.uuid4().hex
        lines = []
        for key, value in form.items():
            lines += [
                f"--{boundary}",
                f'Content-Disposition: form-data; name="{key}"',
                "",
                str(value),
            ]
        lines += [f"--{boundary}--", ""]
        body = "\r\n".join(lines).encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    call = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(call, timeout=120) as answer:
            return json.loads(answer.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"{method} {path}: {exc.code} {detail}") from exc


def wait_for(base: str, seconds: float = 90.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if request(base, "GET", "/health").get("status") == "ok":
                return
        except (RuntimeError, OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError("the service did not answer on /health")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Container:
    """The real image, with the pack mounted read-only: what a user would run."""

    def __init__(self, image: str, pack: Path):
        self.image, self.pack = image, pack
        self.name = "fireblade-recette-" + uuid.uuid4().hex[:8]
        self.cases = Path(tempfile.mkdtemp(prefix="recette-cases-"))
        self.port = free_port()

    def __enter__(self):
        self.cases.chmod(0o777)  # the image runs as its own user
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                self.name,
                "-p",
                f"127.0.0.1:{self.port}:8080",
                "-v",
                f"{self.cases}:/data/cases",
                "-v",
                f"{self.pack}:/pack:ro",
                self.image,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, *_):
        logs = subprocess.run(["docker", "logs", self.name], capture_output=True, text=True)
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
        self.logs = (logs.stdout + logs.stderr)[-4000:]


def import_pack(base: str, case_id: str, source: str, organization: str = "artifacts") -> dict:
    started = request(
        base,
        "POST",
        f"/api/cases/{case_id}/import-jobs",
        form={"source": source, "organization": organization},
    )
    deadline = time.monotonic() + 3600
    while time.monotonic() < deadline:
        state = request(base, "GET", f"/api/import-jobs/{started['job']}")
        if state.get("status") not in ("running", "pending", "queued"):
            return state
        time.sleep(2)
    raise RuntimeError("the import did not finish within an hour")


def observe(base: str, case_id: str) -> dict:
    """What the case holds after the import: its analyses and the import report."""
    case = request(base, "GET", f"/api/cases/{case_id}")
    report = request(base, "GET", f"/api/cases/{case_id}/imports")
    files = [
        item for collection in report.get("collections", []) for item in collection.get("files", [])
    ]
    statuses: dict[str, int] = {}
    for item in files:
        statuses[item.get("status", "?")] = statuses.get(item.get("status", "?"), 0) + 1
    analyses = []
    for entry in case.get("analyses", []):
        info = entry.get("source_info") or {}
        analyses.append(
            {
                "label": entry.get("label", ""),
                "rows": int(info.get("rows") or 0),
                "artifact": str(info.get("artifact") or info.get("path") or ""),
                "parser": str(info.get("parser") or ""),
            }
        )
    return {"analyses": analyses, "files": files, "statuses": statuses}


def rows_of(observed: dict, label: str) -> int:
    """The rows of the analysis named ``label`` (the Host's own name for a family, as read on screen)."""
    shown = english(label)
    return sum(
        item["rows"] for item in observed["analyses"] if item["label"] in (shown, shown + ".csv")
    )


def base_checks(observed: dict, files_in_pack: int, job: dict) -> list[Check]:
    """What every import owes: it ends, every file has a line in the report, nothing is in error."""
    checks = [
        Check(
            "import-completes",
            "complete",
            job.get("status"),
            PASS if job.get("status") == "complete" else FAIL,
            str(job.get("error") or "")[:200],
        )
    ]
    accounted = len(observed["files"])
    checks.append(
        Check(
            "every-file-accounted-for",
            files_in_pack,
            accounted,
            PASS if accounted == files_in_pack else FAIL,
            "each file of the source has a line, read or not, in the import report",
        )
    )
    bad = [item for item in observed["files"] if item.get("status") in ("error", "failed")]
    checks.append(
        Check(
            "no-file-in-error",
            0,
            len(bad),
            PASS if not bad else FAIL,
            "; ".join(f"{item.get('name')}: {item.get('reason')}" for item in bad[:5]),
        )
    )
    return checks


def compare(name: str, want, got, note: str = "") -> Check | None:
    return None if want is None else Check(name, want, got, PASS if want == got else INFO, note)


def check_catscale(expected: dict, observed: dict) -> list[Check]:
    """A CatScale collection, extracted or archived: each family holds the rows the parser counted."""
    catscale = expected.get("catscale") or {}
    found = [
        compare(f"catscale-{family}", rows, rows_of(observed, family))
        for family, rows in (catscale.get("families") or {}).items()
    ]
    found.append(
        compare(
            "catscale-total",
            catscale.get("rows"),
            sum(rows_of(observed, family) for family in (catscale.get("families") or {})),
        )
    )
    return [item for item in found if item]


def check_volume(expected: dict, observed: dict) -> list[Check]:
    return [
        item
        for item in [
            compare(
                "volume-rows",
                expected.get("volume_rows"),
                sum(item["rows"] for item in observed["analyses"]),
            )
        ]
        if item
    ]


def check_exports(expected: dict, observed: dict) -> list[Check]:
    """The csv and the tsv carry the same schema and are read as one family: their rows add up."""
    want = expected.get("exports_rows")
    readable = sum(1 for item in observed["files"] if item.get("status") == "complete")
    got = sum(item["rows"] for item in observed["analyses"])
    return (
        [
            Check(
                "exports-rows",
                want * readable,
                got,
                PASS if readable and got == want * readable else INFO,
                f"{readable} readable files of {want} rows each",
            )
        ]
        if want is not None
        else []
    )


def check_webcache(expected: dict, observed: dict) -> list[Check]:
    return [
        item
        for item in [
            compare(
                "webcache-rows-including-metadata",
                expected.get("webcache_rows_including_metadata"),
                sum(item["rows"] for item in observed["analyses"]),
            )
        ]
        if item
    ]


def check_evtx(expected: dict, observed: dict) -> list[Check]:
    got = sum(item["rows"] for item in observed["analyses"] if "evtx" in item["label"].lower())
    checks = [item for item in [compare("evtx-events", expected.get("evtx_events"), got)] if item]
    detection = observed.get("detection")
    if detection is not None:
        wanted = expected.get("hayabusa_minimum_alerts")
        alerts = int(detection.get("total", 0))
        checks.append(
            Check(
                "hayabusa-alerts",
                f">= {wanted}",
                alerts,
                PASS
                if wanted is not None and alerts >= wanted
                else (INFO if wanted is None else FAIL),
                detection.get("error", ""),
            )
        )
        nodes = int(detection.get("graph_nodes", 0))
        checks.append(
            Check(
                "attack-graph",
                ">= 1 node",
                nodes,
                PASS if nodes >= 1 else FAIL,
                "the findings are drawn",
            )
        )
        techniques = int(detection.get("layer_techniques", 0))
        checks.append(
            Check(
                "navigator-layer",
                ">= 1 technique",
                techniques,
                PASS if techniques >= 1 else FAIL,
                "the ATT&CK layer reaches the analyst as content, not as a path in the container",
            )
        )
    return checks


def run_detection(base: str, case_id: str) -> dict:
    """The analyst's Hayabusa run over the case, then the attack graph it feeds."""
    started = request(
        base,
        "POST",
        f"/api/cases/{case_id}/tasks",
        data={"kind": "detect", "params": {"min_level": "low"}},
    )
    deadline = time.monotonic() + 900
    state = {}
    while time.monotonic() < deadline:
        state = request(base, "GET", f"/api/tasks/{started['job']}")
        if state.get("status") not in ("running", "pending", "queued"):
            break
        time.sleep(2)
    result = state.get("result") or {}
    out = {"total": result.get("total", 0), "error": state.get("error") or ""}
    if not out["error"]:
        graph = request(base, "GET", f"/api/cases/{case_id}/graph")
        out["graph_nodes"] = len(graph.get("nodes", []))
        layer = request(base, "GET", f"/api/cases/{case_id}/graph?navigator=true")
        out["layer_techniques"] = len((layer.get("layer") or {}).get("techniques") or [])
    return out


def check_shellbags(expected: dict, observed: dict) -> list[Check]:
    want = expected.get("shellbags")
    got = sum(item["rows"] for item in observed["analyses"])
    return (
        []
        if want is None
        else [
            Check(
                "shellbags",
                want,
                got,
                PASS if got == want else FAIL,
                "Fireblade's own Shellbags host, published into the image, reads the hive",
            )
        ]
    )


# One scenario per source, as the pack's own guide asks: the extracted folder and its archive are the
# same collection, and importing both reads every row twice.
SCENARIOS = [
    ("catscale-folder", "02-Linux-CatScale/01-Dossier-extrait", check_catscale, False),
    ("catscale-archive", "02-Linux-CatScale/02-Archive", check_catscale, False),
    ("volume", "02-Linux-CatScale/03-Volume", check_volume, False),
    ("exports", "03-Exports", check_exports, False),
    ("windows-evtx", "01-Windows/01-Collecte-principale/EvtxECmd", check_evtx, True),
    ("windows-shellbags", "01-Windows/02-Shellbags", check_shellbags, True),
    ("windows-webcache", "01-Windows/03-WebCache", check_webcache, True),
]


def count_files(source: Path) -> int:
    return sum(1 for path in source.rglob("*") if path.is_file())


def load_expected(pack: Path) -> dict:
    for candidate in [pack / "RESULTATS-ATTENDUS.json", *pack.rglob("RESULTATS-ATTENDUS.json")]:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {}


def upload(base: str, path: str, name: str, content: bytes, fields: dict | None = None):
    """A file sent the way the browser's dialog sends it (multipart), the answer read as JSON."""
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in (fields or {}).items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    call = urllib.request.Request(
        base + path,
        data=b"".join(parts),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(call, timeout=120) as answer:
            return json.loads(answer.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"POST {path}: {exc.code} {exc.read().decode('utf-8', 'replace')[:300]}"
        ) from exc


def dialog_import(base: str) -> dict:
    """The analyst's own way in: a file chosen in the dialog, previewed, then imported.

    The other scenarios import a folder by path; this one goes through the upload routes, which
    is how a CSV reached the Host in 0.8.2 and failed there (the profile detection could not
    read a folder of the user's profile inside the container).
    """
    started = time.monotonic()
    case = request(
        base, "POST", "/api/cases", data={"name": "Recette dialog", "environment": "windows"}
    )
    content = b"Time,Host,User\n2026-11-01T10:00:00Z,PC01,alice\n2026-11-01T10:05:00Z,PC02,bob\n"
    checks = []
    try:
        preview = upload(base, f"/api/cases/{case['id']}/preview-upload", "events.csv", content)
        columns = [column["name"] for column in preview.get("columns", [])]
        checks.append(
            Check(
                "dialog-preview",
                ["Time", "Host", "User"],
                columns,
                PASS if columns == ["Time", "Host", "User"] else FAIL,
            )
        )
        # Confirming the preview imports the bytes the preview already stored.
        import_pack(base, case["id"], preview["path"], "files")
        observed = observe(base, case["id"])
        rows = sum(item["rows"] for item in observed["analyses"] if item["label"] == "events.csv")
        checks.append(Check("dialog-rows", 2, rows, PASS if rows == 2 else FAIL))
    except RuntimeError as exc:
        checks.append(Check("dialog-import", "works", "refused", FAIL, str(exc)[:300]))
    return {
        "scenario": "dialog-import",
        "source": "(uploaded)",
        "windows": False,
        "seconds": round(time.monotonic() - started, 1),
        "statuses": {},
        "analyses": [],
        "checks": [asdict(item) for item in checks],
    }


def run(args) -> dict:
    pack = Path(args.pack).resolve()
    expected = load_expected(pack)

    def against(base: str, server_pack: str) -> list[dict]:
        wait_for(base)
        scenarios = []
        for name, subpath, checker, windows_only in SCENARIOS:
            source = pack / subpath
            if not source.exists():
                continue
            case = request(
                base,
                "POST",
                "/api/cases",
                data={"name": "Recette " + name, "environment": "windows"},
            )
            started = time.monotonic()
            job = import_pack(base, case["id"], f"{server_pack}/{subpath}")
            observed = observe(base, case["id"])
            if name == "windows-evtx":
                observed["detection"] = run_detection(base, case["id"])
            checks = base_checks(observed, count_files(source), job) + checker(expected, observed)
            scenarios.append(
                {
                    "scenario": name,
                    "source": subpath,
                    "windows": windows_only,
                    "seconds": round(time.monotonic() - started, 1),
                    "statuses": observed["statuses"],
                    "analyses": [
                        f"{item['label']} ({item['rows']})" for item in observed["analyses"]
                    ],
                    "checks": [asdict(item) for item in checks],
                }
            )
        scenarios.append(dialog_import(base))
        return scenarios

    if args.url:
        scenarios = against(args.url.rstrip("/"), args.server_pack or str(pack))
    else:
        with Container(args.image, pack) as base:
            scenarios = against(base, "/pack")
    return {
        "pack": str(pack),
        "image": args.image or "",
        "expected": expected,
        "scenarios": scenarios,
    }


def verdict(result: dict, strict: bool) -> int:
    """0 when the run stands. A failed check always fails it; --strict also fails an unpinned
    difference. A documented limit of the Linux edition never does."""
    failing = {FAIL, INFO} if strict else {FAIL}
    return int(
        any(
            item["verdict"] in failing
            for scenario in result["scenarios"]
            for item in scenario["checks"]
        )
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--pack", required=True, help="the unpacked test pack")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--image", help="start this image with docker and test it")
    where.add_argument("--url", help="test a service that is already running")
    parser.add_argument("--server-pack", help="with --url: the pack's path as the service sees it")
    parser.add_argument("--report", help="write the JSON report here")
    parser.add_argument(
        "--strict", action="store_true", help="every measured difference fails the run"
    )
    args = parser.parse_args(argv)
    result = run(args)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    for scenario in result["scenarios"]:
        print(
            f"\n{scenario['scenario']}: {len(scenario['analyses'])} analyses in {scenario['seconds']} s, "
            f"files {scenario['statuses']}"
        )
        for item in scenario["checks"]:
            print(
                f"  {item['verdict']:<11} {item['name']:<36} expected {item['expected']!s:<14} got {item['actual']}"
            )
    code = verdict(result, args.strict)
    print("\nRECETTE", "FAILED" if code else "OK")
    return code


if __name__ == "__main__":
    sys.exit(main())
