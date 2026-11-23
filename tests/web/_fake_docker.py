"""A docker command line that answers like docker, and remembers what it was told.

The driver runs docker as a subprocess, so a fake executable is enough to test every
decision it takes: which containers exist, what they mount, in which state they are.
The state lives in the JSON file named by ``FAKE_DOCKER_STATE``; every call is kept, so
a test can read back the arguments that were actually used.
"""
import json
import os
import sys
from pathlib import Path


def state_path() -> Path:
    return Path(os.environ["FAKE_DOCKER_STATE"])


def load() -> dict:
    path = state_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"containers": {}, "calls": []}


def save(state: dict) -> None:
    state_path().write_text(json.dumps(state, indent=1), encoding="utf-8")


def flag(args, name, default=""):
    return args[args.index(name) + 1] if name in args else default


def main(argv) -> int:
    state = load()
    state["calls"].append(argv)
    containers = state["containers"]
    command, args = argv[0], argv[1:]

    if command == "ps":
        filters = [args[index + 1] for index, value in enumerate(args) if value == "--filter"]
        fmt = flag(args, "--format", "{{.Names}}")
        rows = []
        for name, item in sorted(containers.items()):
            labels = item.get("labels", {})
            skip = False
            for value in filters:
                if value.startswith("name="):
                    expected = value[5:].strip("^$")
                    skip = skip or expected != name
                elif value.startswith("label="):
                    key, _, wanted = value[6:].partition("=")
                    skip = skip or labels.get(key) != wanted
            if skip:
                continue
            if "{{.State}}" in fmt:
                rows.append(item.get("state", ""))
            elif "{{.Names}}" in fmt and "Label" in fmt:
                rows.append(name + "|" + labels.get("fireblade.case", ""))
            else:
                rows.append(name)
        print("\n".join(rows))
        return 0

    if command == "run":
        name = flag(args, "--name")
        labels = {}
        for index, value in enumerate(args):
            if value == "--label":
                key, _, content = args[index + 1].partition("=")
                labels[key] = content
        containers[name] = {"state": "running", "labels": labels, "args": args}
        save(state)
        print("fake-" + name)
        return 0

    if command in ("start", "stop"):
        name = args[0]
        if name not in containers:
            print(f"Error response from daemon: No such container: {name}", file=sys.stderr)
            return 1
        containers[name]["state"] = "running" if command == "start" else "exited"
        save(state)
        print(name)
        return 0

    if command == "rm":
        name = args[-1]
        if name not in containers:
            if "-f" in args:
                save(state)
                return 0
            print(f"Error response from daemon: No such container: {name}", file=sys.stderr)
            return 1
        containers.pop(name)
        save(state)
        print(name)
        return 0

    print(f"fake docker: {command} is not implemented", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
