"""The Host driver: one container per case.

The Host used to serve the whole library from a single container. A case is now an
object of its own: opening it creates a container that mounts that case's volume alone,
and destroying the case stops the container, wipes the volume and deletes the folder —
certificate apart, which is written outside the volume.

The driver analyses nothing: it lists, creates, opens, proxies and destroys. Its image
therefore carries neither Qt, nor .NET, nor the readers.
"""
from __future__ import annotations

import asyncio
import collections
import contextlib
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask

from fireblade.core.case_destruction import destroy_case, outside_entries
from fireblade.core.investigations import InvestigationLibrary

STATIC = Path(__file__).with_name("static")
CASE_ID = re.compile(r"^[0-9a-f]{32}$")
CASE_LABEL = "fireblade.case"
ROLE_LABEL = "fireblade.role"
# Headers that belong to one hop: forwarding them makes httpx recompute the wrong ones.
HOP_BY_HOP = {
    "host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length",
}


class DockerError(RuntimeError):
    """The docker command refused: its message is the answer, not a traceback."""


class Docker:
    """The docker CLI, run as a subprocess.

    The command line rather than a client library: every decision this driver takes is
    tested with a fake binary, and the socket stays the only privileged thing in the
    picture.
    """

    def __init__(self, executable="docker", timeout: float = 180):
        self.command = [executable] if isinstance(executable, str) else list(executable)
        self.timeout = timeout

    def run(self, *args: str, check: bool = True) -> str:
        try:
            completed = subprocess.run([*self.command, *args], capture_output=True,
                                       text=True, timeout=self.timeout)
        except FileNotFoundError as exc:
            raise DockerError(f"docker is not available: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerError(f"docker {args[0]} timed out after {self.timeout:.0f}s") from exc
        if check and completed.returncode != 0:
            lines = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise DockerError(f"docker {args[0]}: {lines[-1] if lines else completed.returncode}")
        return completed.stdout.strip()


class CaseContainer:
    """One case, one container: born when the case is opened, gone when it is destroyed."""

    def __init__(self, docker, identifier: str, *, volume, image: str = "fireblade:host",
                 network: str = "fireblade-cases", port: int = 8080, name: str = ""):
        if not CASE_ID.match(identifier or ""):
            raise ValueError("A case identifier is 32 hexadecimal characters")
        self.docker = docker
        self.identifier = identifier
        self.volume = Path(volume)
        self.image = image
        self.network = network
        self.port = port
        self.name = name or f"fireblade-case-{identifier[:8]}"

    @property
    def url(self) -> str:
        # On the private network the container's name is its address; nothing is published.
        return f"http://{self.name}:{self.port}"

    def state(self) -> str:
        found = self.docker.run("ps", "-a", "--filter", f"name=^{self.name}$",
                                "--format", "{{.State}}", check=False).split()
        return found[0] if found else ""

    def exists(self) -> bool:
        return bool(self.state())

    def running(self) -> bool:
        return self.state() == "running"

    def create(self) -> None:
        """The case's own service, over that case's volume and nothing else."""
        self.docker.run(
            "run", "-d", "--name", self.name,
            "--label", f"{CASE_LABEL}={self.identifier}",
            "--label", f"{ROLE_LABEL}=case",
            "--network", self.network,
            "--restart", "no",
            "-v", f"{self.volume}:/data/library",
            self.image,
            "python", "-m", "fireblade.web", "serve",
            "--root", "/data/library", "--host", "0.0.0.0", "--port", str(self.port),
            "--tools", "/opt/fireblade/tools",
        )

    def start(self) -> None:
        self.docker.run("start", self.name)

    def stop(self) -> None:
        self.docker.run("stop", self.name, check=False)

    def remove(self) -> None:
        self.docker.run("rm", "-f", self.name, check=False)

    def wait_healthy(self, timeout: float = 25.0) -> None:
        """A case answers /health in a few seconds; past that, the container is not starting."""
        deadline = time.monotonic() + timeout
        with httpx.Client(timeout=1.5) as client:
            while time.monotonic() < deadline:
                try:
                    if client.get(f"{self.url}/health").status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.3)
        raise DockerError(f"case {self.identifier[:8]}: no answer on /health after {timeout:.0f}s")


def tagged(docker) -> list:
    """Every container that carries a case label, as (identifier, name)."""
    out = docker.run("ps", "-a", "--filter", f"label={ROLE_LABEL}=case",
                     "--format", '{{.Names}}|{{.Label "fireblade.case"}}', check=False)
    found = []
    for line in out.splitlines():
        name, _, identifier = line.partition("|")
        if name.strip() and CASE_ID.match(identifier.strip()):
            found.append((identifier.strip(), name.strip()))
    return found


def _chown_tree(root, uid, gid):
    """Hand the volume to the case container's own user.

    The image runs as uid 10001; a volume created by the driver as root would be
    unreadable for it, and the case would list as a permission error.
    """
    if not hasattr(os, "chown"):
        return
    for current, folders, names in os.walk(root):
        for name in [*folders, *names]:
            try:
                os.chown(Path(current)/name, uid, gid)
            except OSError:
                pass
    try:
        os.chown(root, uid, gid)
    except OSError:
        pass


class Volumes:
    """One folder per case: the case, its exports, its archives, and nothing else."""

    def __init__(self, root):
        self.root = Path(root)

    def folder(self, identifier: str) -> Path:
        if not CASE_ID.match(identifier or ""):
            raise ValueError("A case identifier is 32 hexadecimal characters")
        return self.root/identifier

    def library(self, identifier: str) -> Path:
        """The library root of that volume: what the case's container serves.

        The volume root *is* the library root, which is how the service reads a case
        directory: the case, its exports, its archives and the certificate annexes sit
        side by side, and all of them disappear with the volume.
        """
        return self.folder(identifier)

    def case_folder(self, identifier: str) -> Path:
        return self.library(identifier)/identifier

    def has(self, identifier: str) -> bool:
        try:
            return (self.case_folder(identifier)/"case.json").is_file()
        except ValueError:
            return False

    def create(self, name: str, description: str = "", environment: str = "unspecified",
               uid=None, gid=None) -> dict:
        """Create the volume and the case in it; the container comes when it is opened.

        The library names its own cases, so the volume is built beside its final name and
        takes that name once it is known: a case folder and its volume always agree.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        staging = self.root/(".staging-" + uuid.uuid4().hex[:12])
        try:
            data = InvestigationLibrary(staging).create(name, description, environment)
            for extra in ("exports", "archives"):
                (staging/extra).mkdir(exist_ok=True)
            target = self.root/data["id"]
            if target.exists():
                raise ValueError("A case with that identifier already exists")
            staging.rename(target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        if uid is not None:
            _chown_tree(target, uid, gid if gid is not None else uid)
        return data

    def cases(self) -> dict:
        """Every case in the volumes, read from its register.

        An anomaly is reported, never repaired and never deleted: a folder that is not a
        case may be somebody's evidence.
        """
        found, errors = [], []
        if not self.root.is_dir():
            return {"root": str(self.root), "cases": found, "errors": errors}
        for folder in sorted(self.root.iterdir()):
            if folder.name.startswith(".") or folder.is_symlink() or not folder.is_dir():
                continue
            if not CASE_ID.match(folder.name):
                errors.append(f"{folder.name}: not a case folder")
                continue
            try:
                data = InvestigationLibrary(folder).read(folder.name)
            except (OSError, ValueError) as exc:
                errors.append(f"{folder.name}: {exc}")
                continue
            found.append({"id": folder.name, "name": data.get("name", ""),
                          "status": data.get("status", ""),
                          "environment": data.get("environment", ""),
                          "created": data.get("created", ""),
                          "updated": data.get("updated", "")})
        return {"root": str(self.root), "cases": found, "errors": errors}

    def remove(self, identifier: str) -> None:
        """The volume goes once its case is gone — the certificate lived outside it."""
        shutil.rmtree(self.folder(identifier), ignore_errors=True)


class Agency:
    """The driver's decisions, without HTTP: one container per case, and nothing after it."""

    def __init__(self, volumes, certificates="", docker=None, *, image: str = "fireblade:host",
                 network: str = "fireblade-cases", max_open: int = 3,
                 host_volumes="", host_certificates="", case_uid: int = 10001,
                 case_gid: int = 10001):
        self.volumes = volumes if isinstance(volumes, Volumes) else Volumes(volumes)
        self.volumes.root.mkdir(parents=True, exist_ok=True)
        self.certificates = Path(certificates or (self.volumes.root.parent/"certificates"))
        self.certificates.mkdir(parents=True, exist_ok=True)
        # A driver that runs in a container reads /data/volumes and asks the daemon for
        # a mount; the daemon only understands paths on the host. Two names, one folder.
        self.host_volumes = Path(host_volumes) if host_volumes else self.volumes.root
        self.host_certificates = Path(host_certificates) if host_certificates else self.certificates
        # The case image's user: the volume it mounts has to belong to it.
        self.case_uid = case_uid
        self.case_gid = case_gid
        self.docker = docker if isinstance(docker, Docker) else Docker(docker)
        self.image = image
        self.network = network
        self.max_open = max(1, int(max_open))
        self.opened = collections.OrderedDict()
        self.lock = threading.Lock()
        self.waiting = {}

    # -- one case, one container ------------------------------------------

    def container(self, identifier: str) -> CaseContainer:
        self.volumes.folder(identifier)      # validated here, not in a docker argument
        return CaseContainer(self.docker, identifier, volume=self.host_volumes/identifier,
                             image=self.image, network=self.network)

    def cases(self) -> dict:
        return self.volumes.cases()

    def create(self, name: str, description: str = "", environment: str = "unspecified") -> dict:
        return self.volumes.create(name, description, environment,
                                   uid=self.case_uid, gid=self.case_gid)

    def open(self, identifier: str) -> CaseContainer:
        """The case's container, running and answering; created the first time it is needed."""
        if not self.volumes.has(identifier):
            raise KeyError(identifier)
        with self.lock:
            gate = self.waiting.setdefault(identifier, threading.Lock())
        with gate:
            case = self.container(identifier)
            if case.exists():
                if not case.running():
                    case.start()
            else:
                case.create()
            case.wait_healthy()
            with self.lock:
                self.opened[identifier] = self.opened.pop(identifier, time.monotonic())
        self.evict(keep=identifier)
        return case

    def evict(self, keep: str = "") -> list:
        """Keep at most ``max_open`` containers running; the oldest unused goes first."""
        victims = []
        with self.lock:
            while len(self.opened) > self.max_open:
                oldest = next(iter(self.opened))
                if oldest == keep and len(self.opened) == 1:
                    break
                self.opened.pop(oldest, None)
                victims.append(oldest)
        for identifier in victims:
            try:
                self.container(identifier).stop()
            except (DockerError, ValueError):
                continue
        return victims

    def reconcile(self) -> list:
        """A container whose case is gone is removed; a folder without a case is reported."""
        removed = []
        for identifier, name in tagged(self.docker):
            if self.volumes.has(identifier):
                continue
            try:
                self.docker.run("rm", "-f", name)
                removed.append(identifier)
            except DockerError:
                continue
        with self.lock:
            for identifier in removed:
                self.opened.pop(identifier, None)
        return removed

    def destroy(self, identifier: str, payload: dict | None = None) -> dict:
        """Stop the container, wipe the volume, keep the certificate.

        The client's own destroy button lands here through the prefix: one destruction
        path, so a volume cannot outlive its case by accident.
        """
        payload = payload or {}
        if not CASE_ID.match(identifier or "") or not self.volumes.has(identifier):
            raise KeyError(identifier)
        library_root = self.volumes.library(identifier)
        data = InvestigationLibrary(library_root).read(identifier)
        if (payload.get("confirmation") or "").strip() != (data.get("name") or ""):
            raise ValueError("The case name does not match; nothing was destroyed.")
        case = self.container(identifier)
        if case.exists():
            case.stop()
            case.remove()
        with self.lock:
            self.opened.pop(identifier, None)
        certificate = self.certificates / (datetime.now(timezone.utc).strftime("pv-%Y%m%d-%H%M%S-")
                                           + identifier[:8] + ".html")
        extras = [str(path) for path in outside_entries(library_root, identifier)]
        record = destroy_case(self.volumes.case_folder(identifier), payload.get("method", "dod3"),
                              operator=payload.get("operator", ""),
                              witness=payload.get("witness", ""),
                              reason=payload.get("reason", ""),
                              certificate_path=certificate, case_name=data.get("name", ""),
                              case_id=identifier, extras=extras,
                              attachments=payload.get("attachments") or [])
        if record.get("folder_removed"):
            self.volumes.remove(identifier)
        reported = self.host_certificates/certificate.name
        return {"id": record.get("id"), "method": record.get("method"),
                "files": len(record.get("files") or []),
                "outside": int(record.get("outside") or 0), "residue": extras,
                "certificate": str(reported),
                "bytes": sum(int(item.get("size") or 0) for item in (record.get("files") or []))}


async def form_fields(request: Request) -> dict:
    """The driver's own page posts a form, one field per verb.

    Parsed by hand: the page sends two fields, and a form parser is a dependency the
    driver image would otherwise need to carry.
    """
    body = (await request.body()).decode("utf-8", "replace")
    return {key: values[0] for key, values in parse_qs(body).items()}


def _version() -> str:
    try:
        import fireblade
        value = getattr(fireblade, "__version__", "")
        if value:
            return value
    except Exception:  # noqa: BLE001 - a version is a comfort, not a dependency
        pass
    try:
        from importlib.metadata import version
        return version("fireblade-forensics")
    except Exception:  # noqa: BLE001
        return "0"


def page(catalogue: dict, *, version: str = "", error: str = "") -> str:
    """The driver's own page, in the Host's own clothes.

    It reuses ``static/app.css`` — the client's palette and density, carried from the
    desktop's theme — so the page that opens a case looks like the case it opens.
    """
    rows = []
    for case in catalogue["cases"]:
        identifier = case["id"]
        rows.append(
            "<tr>"
            "<td><a href=\"/case/" + escape(identifier) + "/\">" + escape(case["name"] or identifier)
            + "</a><div class=\"ref\">" + escape(identifier) + "</div></td>"
            "<td>" + escape(case["status"] or "—") + "</td>"
            "<td class=\"when\">" + escape((case["updated"] or "")[:19].replace("T", " ")) + "</td>"
            "<td><form class=\"rowform\" method=\"post\" action=\"/destroy/" + escape(identifier) + "\""
            + " onsubmit=\"return confirm('Erase this case, its container and its volume?')\">"
            + "<input class=\"search\" name=\"confirmation\" placeholder=\"type the name\" required>"
            + "<button class=\"btn\" type=\"submit\">Erase</button></form></td>"
            "</tr>"
        )
    body = ("<table><colgroup><col style=\"width:44%\"><col style=\"width:9%\">"
            "<col style=\"width:19%\"><col style=\"width:28%\"></colgroup>"
            "<thead><tr><th>Name</th><th>Status</th><th>Updated</th><th>Erase</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>") if rows \
        else "<div class=\"emptygrid\">No case yet — create one above.</div>"
    problems = " ".join(escape(item) for item in catalogue["errors"])
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>Fireblade — Host</title>"
            "<link rel=\"stylesheet\" href=\"/static/app.css\"><style>"
            ".wrap{display:flex;flex-direction:column;height:100vh}"
            ".topline{display:flex;align-items:center;gap:10px;padding:3px 7px;"
            "border-bottom:1px solid var(--toolbar-sep);height:26px;flex:0 0 26px}"
            ".brand{font-weight:600}.brand small{font-weight:400;color:var(--muted);margin-left:7px}"
            ".grow{flex:1}.rowform{display:flex;align-items:center;gap:4px;margin:0}"
            ".filterbar{align-items:center;height:24px}"
            ".topline a.btn{text-decoration:none}"
            ".rowform .search{width:118px;flex:none}"
            ".caseswrap td .ref{font:9px monospace;color:var(--muted);line-height:10px}"
            ".caseswrap td.when{color:var(--muted)}"
            ".caseswrap td:first-child{line-height:13px;height:30px}"
            "a{color:var(--text);text-decoration:none}a:hover{text-decoration:underline}"
            "</style></head><body><div class=\"wrap\">"
            "<div class=\"topline\"><span class=\"brand\">Fireblade <small>Host — one container per case"
            "</small></span><span class=\"grow\"></span>"
            "<form class=\"rowform\" method=\"post\" action=\"/new\">"
            "<input class=\"search\" name=\"name\" placeholder=\"New case name…\" required>"
            "<button class=\"btn\" type=\"submit\">New case…</button></form>"
            "<a class=\"btn\" href=\"/\">Refresh</a></div>"
            "<div class=\"filterbar\"><span>" + str(len(catalogue["cases"])) + " case(s)</span></div>"
            "<div class=\"caseswrap\">" + body + "</div>"
            "<div class=\"statusbar\"><span>Opening a case starts its container; erasing it takes the"
            " container and the volume.</span>"
            + ("<span class=\"err\">" + problems + "</span>" if problems else "")
            + ("<span class=\"err\">" + escape(error) + "</span>" if error else "")
            + "<span class=\"right\"><span>version " + escape(version or "0") + "</span></span></div>"
            "</div></body></html>")


def create_app(volumes_root, certificates_root="", *, image: str = "fireblade:host",
               network: str = "fireblade-cases", max_open: int = 3, version: str = "",
               docker=None, agency=None, host_volumes="", host_certificates="",
               case_uid: int = 10001, case_gid: int = 10001) -> FastAPI:
    """The HTTP face of the driver: its own page, and ``/case/<id>/`` for each case."""
    agency = agency or Agency(volumes_root, certificates_root, docker=docker, image=image,
                              network=network, max_open=max_open,
                              host_volumes=host_volumes, host_certificates=host_certificates,
                              case_uid=case_uid, case_gid=case_gid)
    client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0, read=None),
                               follow_redirects=False)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        # A container whose case is gone is removed before the first page is served.
        agency.reconcile()
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(title="Fireblade Host driver", version=version or "0", lifespan=lifespan)
    app.state.agency = agency
    if STATIC.is_dir():
        # The driver ships the client's stylesheet: one palette, carried from the desktop.
        app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/health")
    def health():
        catalogue = agency.cases()
        return {"status": "ok", "version": version or "0", "root": str(catalogue["root"]),
                "cases": len(catalogue["cases"]), "errors": len(catalogue["errors"]),
                "open": len(agency.opened), "containers": len(tagged(agency.docker))}

    @app.get("/")
    def home(error: str = ""):
        return HTMLResponse(page(agency.cases(), version=version or _version(), error=error))

    @app.get("/api/cases")
    def cases():
        return agency.cases()

    @app.post("/api/cases")
    def create(payload: dict):
        payload = payload or {}
        try:
            return agency.create(payload.get("name") or "Untitled case",
                                 payload.get("description", ""),
                                 payload.get("environment", "unspecified"))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/destroy")
    async def destroy(identifier: str, payload: dict | None = None):
        # The case client posts JSON; the driver's own page posts a form (see /destroy/).
        return await asyncio.to_thread(agency.destroy, identifier, payload or {})

    @app.post("/new")
    async def create_form(request: Request):
        form = await form_fields(request)
        try:
            agency.create((form.get("name") or "Untitled case").strip())
        except (ValueError, OSError) as exc:
            return RedirectResponse("/?error=" + quote(str(exc)), status_code=303)
        return RedirectResponse("/", status_code=303)

    @app.post("/destroy/{identifier}")
    async def destroy_form(identifier: str, request: Request):
        form = await form_fields(request)
        try:
            await asyncio.to_thread(agency.destroy, identifier, dict(form))
        except KeyError:
            return RedirectResponse("/", status_code=303)
        except (ValueError, OSError, DockerError) as exc:
            return RedirectResponse("/?error=" + quote(str(exc)), status_code=303)
        return RedirectResponse("/", status_code=303)

    @app.post("/api/reconcile")
    def reconcile_now():
        return {"removed": agency.reconcile()}

    @app.api_route("/case/{identifier}", methods=["GET"])
    def case_root(identifier: str):
        # Relative links in the page resolve against a trailing slash.
        return RedirectResponse(f"/case/{identifier}/", status_code=307)

    @app.api_route("/case/{identifier}/{path:path}",
                   methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    async def proxy(identifier: str, path: str, request: Request):
        """The case container serves its own application; the driver only prefixes it."""
        if not agency.volumes.has(identifier):
            raise HTTPException(status_code=404, detail="Unknown case.")
        if request.method == "POST" and path.strip("/") == f"api/cases/{identifier}/destroy":
            # The client's Erase button reaches the case through the prefix: the case
            # cannot destroy its own container, so the driver does it, and the
            # certificate is written outside the volume.
            payload = {}
            if request.headers.get("content-type", "").startswith("application/json"):
                try:
                    payload = await request.json() or {}
                except ValueError:
                    payload = {}
            try:
                return JSONResponse(await asyncio.to_thread(agency.destroy, identifier, payload))
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Unknown case.") from exc
            except (ValueError, OSError, DockerError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            case = await asyncio.to_thread(agency.open, identifier)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown case.") from exc
        except DockerError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        headers = [(key, value) for key, value in request.headers.items()
                   if key.lower() not in HOP_BY_HOP]
        target = f"{case.url}/{path}"
        try:
            upstream = client.build_request(request.method, target, headers=headers,
                                            content=request.stream())
            answer = await client.send(upstream, stream=True)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"case {identifier[:8]}: {exc}") from exc
        reply = {key: value for key, value in answer.headers.items()
                 if key.lower() not in HOP_BY_HOP}
        location = reply.get("location")
        if location and location.startswith("/") and not location.startswith("/case/"):
            reply["location"] = f"/case/{identifier}{location}"
        return StreamingResponse(answer.aiter_raw(), status_code=answer.status_code,
                                 headers=reply, background=BackgroundTask(answer.aclose))

    return app


def serve(args) -> int:
    import uvicorn

    app = create_app(args.volumes, args.certificates, image=args.image, network=args.network,
                     max_open=args.max_open, version=_version(), docker=args.docker,
                     host_volumes=args.host_volumes, host_certificates=args.host_certificates,
                     case_uid=args.case_uid, case_gid=args.case_gid)
    print(f"Fireblade Host driver {_version()} on {args.host}:{args.port} — volumes in {args.volumes}",
          flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="fireblade.web.agency", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_serve = sub.add_parser("serve", help="drive one container per case")
    p_serve.add_argument("--volumes", default="/data/volumes",
                         help="folder holding one volume per case")
    p_serve.add_argument("--certificates", default="",
                         help="folder for the certificates, outside the volumes (default: ../certificates)")
    p_serve.add_argument("--host-volumes", default="",
                         help="the same folder as --volumes, as the docker daemon sees it"
                              " (needed when the driver runs in a container)")
    p_serve.add_argument("--host-certificates", default="",
                         help="the same folder as --certificates, as the daemon sees it")
    p_serve.add_argument("--case-uid", type=int, default=10001,
                         help="the uid the case image runs as; a new volume is handed to it")
    p_serve.add_argument("--case-gid", type=int, default=10001)
    p_serve.add_argument("--image", default="fireblade:host")
    p_serve.add_argument("--network", default="fireblade-cases")
    p_serve.add_argument("--max-open", type=int, default=3,
                         help="how many case containers may run at once")
    p_serve.add_argument("--docker", default="docker", help="docker executable to use")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.add_argument("--log-level", default="info")
    p_serve.set_defaults(func=serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
