"""Command line entry points: serve the library, or check that a case is readable.

    python -m fireblade.web serve --root /data/cases --port 8080
    python -m fireblade.web count --root /data/cases            # all cases
    python -m fireblade.web count --root /data/cases --case <id>

`count` is the smoke test of the container: no window, no Qt, and a real number
read from a real DuckDB file.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fireblade.web.service import Library, ServiceError


def _version() -> str:
    """The repository is the source of truth; a stale egg-info is not."""
    try:
        import fireblade
        value = getattr(fireblade, "__version__", "")
        if value:
            return value
    except Exception:
        pass
    try:
        from importlib.metadata import version
        return version("fireblade-forensics")
    except Exception:
        return "0"


def count(args) -> int:
    library = Library(args.root)
    try:
        catalogue = library.cases()
        for error in catalogue["errors"]:
            print(f"error: {error}", file=sys.stderr)
        selected = [c for c in catalogue["cases"] if not args.case or c["id"] == args.case]
        if not selected:
            print(f"no case found under {catalogue['root']}", file=sys.stderr)
            return 1
        grand_total = 0
        for summary in selected:
            detail = library.case(summary["id"])
            print(f"{detail['id']}  {detail['name']}")
            for analysis in detail["analyses"]:
                total = library.rows(detail["id"], analysis["index"], limit=1)["total"]
                grand_total += total
                print(f"    [{analysis['index']}] {analysis['label']}: {total} rows")
        print(f"total: {grand_total} rows")
        return 0
    except (ServiceError, ValueError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        library.close()


def serve(args) -> int:
    import uvicorn

    from fireblade.web.server import create_app

    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    app = create_app(root, _version(), tools_root=args.tools)
    print(f"Fireblade Host {_version()} on {args.host}:{args.port} — cases in {root}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fireblade.web", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="serve the case library over HTTP")
    p_serve.add_argument("--root", default="/data/cases", help="folder holding the case directories")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.add_argument("--tools", default="/opt/fireblade/tools",
                         help="folder holding the .NET readers and their manifest")
    p_serve.add_argument("--log-level", default="info")
    p_serve.set_defaults(func=serve)

    p_count = sub.add_parser("count", help="open the cases and count their rows")
    p_count.add_argument("--root", default="/data/cases")
    p_count.add_argument("--case", default="")
    p_count.set_defaults(func=count)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
