# Building and running the Host

The image is built from the **repository root**: it needs the shared core, the pinned
readers, the toolchain manifest and the web layer. The build inputs therefore stay at
the root — this folder only keeps the entry point and the instructions.

| file | what it is |
| --- | --- |
| [`../../Dockerfile`](../../Dockerfile) | `python:3.12-slim` + the .NET 10 runtime + the thirteen readers fetched by `scripts/fetch_readers.py` |
| [`../../docker-compose.yml`](../../docker-compose.yml) | one service, port `${FIREBLADE_PORT:-8080}`, one volume for the cases and one for the plugins |
| [`../../requirements-core.txt`](../../requirements-core.txt) | the core's Python dependencies, without Qt |
| [`../../.dockerignore`](../../.dockerignore) | what the build must not carry |
| [`Dockerfile.driver`](Dockerfile.driver) | the driver: docker CLI, FastAPI, httpx and the core modules that destroy a case — no readers, no .NET, no DuckDB |
| [`docker-compose.driver.yml`](docker-compose.driver.yml) | one container per case: the driver mounts the socket, the volumes and the certificates folder |

## Build

```bash
docker build -t fireblade:host .
```

The readers are downloaded during the build (the pinned versions in
`config/forensic-toolchain.json`), so the first build needs network access and a few
minutes. Nothing else is fetched at run time.

## Run

```bash
FIREBLADE_CASES=/srv/fireblade/cases FIREBLADE_PORT=8080 docker compose up -d
```

or, without compose:

```bash
docker run -d --name fireblade-host -p 8080:8080 \
    -v /srv/fireblade/cases:/data/cases \
    -v /srv/fireblade/plugins:/data/plugins \
    fireblade:host
```

Open <http://localhost:8080>. The health check is `/health`; the API documents itself at
`/api/docs`.

## One container per case

```bash
docker build -f deploy/host/Dockerfile.driver -t fireblade:driver .

FIREBLADE_VOLUMES=/srv/fireblade/volumes \
FIREBLADE_CERTIFICATES=/srv/fireblade/certificates \
docker compose -f deploy/host/docker-compose.driver.yml up -d
```

The driver creates `fireblade-case-<id8>` containers from the `fireblade:host` image, joins
them to the private `fireblade-cases` network and serves each case under `/case/<id>/`. It
needs the docker socket — that is root on the host, and the one privileged process of this
edition (see `docs/host/HOST-EDITION.md`). The certificates are written outside the volumes,
which is why an erasure can take the whole volume with it.

## Smoke test of an image

```bash
docker run --rm -v /srv/fireblade/cases:/data/cases fireblade:host \
    python -m fireblade.web count
```

It opens every case in the library and counts its rows: a real number from a real
DuckDB file, with no browser involved.

> The Host edition is a **beta of a beta**: no published tag, no upgrade path. See
> [`../../docs/host/BETA.md`](../../docs/host/BETA.md).
