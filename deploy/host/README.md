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

## Published images

```bash
ghcr.io/23r0534zxt/kagarasu-host     # the case image
ghcr.io/23r0534zxt/kagarasu-driver   # the driver: one container per case
```

`:edge` follows `main`; `:X.Y.Z`, `:X.Y` and `:latest` come from a version tag. The
workflow is `.github/workflows/containers.yml`; nothing is built on a machine of ours.

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

## Storage for imports

The import dialogs compare free space on the case filesystem with a planning estimate.
The recommended working space is three times the source size plus 256 MiB and an
additional 1 MiB per known input or extraction candidate. The browser folder estimate
also includes the copy staged for upload. When the copy is in the case filesystem,
Host refreshes the comparison against the remaining free space.

For a mounted volume, Host estimates the bytes in recognized artifact candidates and
their likely transaction sidecars. For a disk image, it prefers the logical disk size
and can use the stored image segments as a fallback. A physical device whose size
cannot be measured shows an unknown estimate. Reader output, combined grids and other
writes can change peak usage. At job start, Host refuses a folder import below its
existing minimum of 1.5 times the source size plus 256 MiB. Disk estimates are advisory.

If Docker runs in a VMware guest, check the guest filesystem containing the case
directory and the physical host volume or datastore holding the VMDK and snapshots.
Guest free space can be high while the physical datastore lacks room for a thin or
dynamically growing disk. Deleting a case can free guest filesystem space while the
VMDK stays the same size on the datastore. Use VMware's storage tools to monitor
host-side capacity and reclaim it when appropriate.

## One container per case

```bash
docker run -d --name fireblade-driver -p 8080:8080 --network fireblade-cases \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /srv/fireblade/volumes:/data/volumes \
    -v /srv/fireblade/certificates:/data/certificates \
    ghcr.io/23r0534zxt/kagarasu-driver:latest \
    python -m fireblade.web.agency serve \
      --image ghcr.io/23r0534zxt/kagarasu:latest \
      --volumes /data/volumes --host-volumes /srv/fireblade/volumes \
      --certificates /data/certificates --host-certificates /srv/fireblade/certificates \
      --host 0.0.0.0 --port 8080
```

From a clone: `docker compose -f deploy/host/docker-compose.driver.yml up -d --build`
(built as `fireblade:driver`).

The driver creates `fireblade-case-<id8>` containers from the `fireblade:host` image, joins
them to the private `fireblade-cases` network and serves each case under `/case/<id>/`. It
needs the docker socket — that is root on the host, and the one privileged process of this
edition (see `docs/host/HOST-EDITION.md`). The certificates are written outside the volumes,
which is why an erasure can take the whole volume with it.

## Upgrade to a new release

```bash
docker pull ghcr.io/23r0534zxt/kagarasu:0.8.8
docker pull ghcr.io/23r0534zxt/kagarasu-driver:0.8.8
docker rm -f fireblade-driver
docker run -d --name fireblade-driver -p 8080:8080 --network fireblade-cases \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /srv/fireblade/volumes:/data/volumes \
    -v /srv/fireblade/certificates:/data/certificates \
    ghcr.io/23r0534zxt/kagarasu-driver:0.8.8 \
    python -m fireblade.web.agency serve \
      --image ghcr.io/23r0534zxt/kagarasu:0.8.8 \
      --volumes /data/volumes --host-volumes /srv/fireblade/volumes \
      --certificates /data/certificates --host-certificates /srv/fireblade/certificates \
      --host 0.0.0.0 --port 8080
```

The volumes are the contract: a case keeps its folder and its format, nothing is migrated.
The driver compares the image id of every case container with the image it is configured
with — a container built from another image is stopped, removed and rebuilt on the next
open, and the stale ones are swept at start-up. A case nobody opens is upgraded the day it
is opened, not before.

Without `--image`, the driver uses the published `ghcr.io/23r0534zxt/kagarasu:latest`;
pinning the same tag as the driver is what makes an upgrade reproducible.

The client says when a newer release exists: a band across the window, the version you
run, and the command to paste (dismissable, remembered per version). The check is cached
for six hours and never reports a failed request as "up to date" — `/api/version` carries
the answer, `/health` repeats it.

Nothing updates itself. If you want the host to follow the releases on its own, Watchtower
does it with the labels it already understands:

```bash
docker run -d --name watchtower \
    -v /var/run/docker.sock:/var/run/docker.sock \
    containrrr/watchtower --label-enable --interval 3600 fireblade-driver
# and add  --label com.centurylinklabs.watchtower.enable=true  to the driver's run
```

Case containers need nothing: the driver rebuilds them from the new image the next time
a case is opened, and sweeps the stale ones when it starts.

## Smoke test of an image

```bash
docker run --rm -v /srv/fireblade/cases:/data/cases fireblade:host \
    python -m fireblade.web count
```

It opens every case in the library and counts its rows: a real number from a real
DuckDB file, with no browser involved.

> What the Host's tests verify, and what they do not: [`../../docs/host/STATUS.md`](../../docs/host/STATUS.md).
