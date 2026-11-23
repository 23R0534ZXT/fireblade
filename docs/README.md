# Documentation

Fireblade ships with its guides inside the executable; this folder is the same material,
plus what a contributor needs.

## The two editions

| Need | Document |
|---|---|
| Use the Windows edition | [Desktop](desktop/README.md) |
| Understand the Host edition, its audit and its **beta of a beta** status | [Host](host/README.md) |
| Build and run the Host image | [deploy/host](../deploy/host/README.md) |

## Use it

| Need | Document |
|---|---|
| Learn the interface end to end | [Full tutorial](guides/TUTORIEL-COMPLET.md) |
| Follow a first investigation | [User guide](guides/UTILISATION.md) |
| Import a collection, read the Imports report, run Hayabusa | [Collection](guides/UTILISATION.md) |
| Walk a timeline, correlate, archive, transport a case, produce a report | [Timeline and backups](guides/CHRONOLOGIE-ET-SAUVEGARDES.md) |
| Hunt indicators in bulk | [IOC hunting](guides/CHASSE-IOC.md) |
| Check what a collection did and did not cover | [Coverage and diagnostics](guides/COUVERTURE-COLLECTE.md) |
| Work on a disk image or a mounted volume | [Disks and workspace](guides/DISQUES-ET-ESPACE-DE-TRAVAIL.md) |
| Use the sample datasets | [Test datasets](guides/JEUX-DE-TEST.md) |

The guides are in French today; the interface, the release notes and the README are in
English, and the guides are being translated in that order.

## Understand it

| Need | Document |
|---|---|
| Where the code lives and where to change it | [Architecture](development/ARCHITECTURE.md) |
| Which inputs are supported, and how they are read | [Compatibility](development/COMPATIBILITE.md) |
| The measured comparison with Timeline Explorer | [Benchmark](development/BENCHMARK-0.4.0.md) |
| Write a plugin or a .NET reader | [Plugins](development/PLUGINS.md) |
| Build, test and publish | [Contributing](development/CONTRIBUER.md) |
| What each release changed | [Release notes](development/RELEASE-NOTES.md) |

## Verify it

| Need | Document |
|---|---|
| What the embedded readers were tested against | [Forensic readers](validation/COLLECTE-FORENSIC.md) |
| The Windows qualification scope | [Windows validation](validation/WINDOWS.md) |
| The 3 GiB load qualification | [Load qualification](validation/QUALIFICATION.md) |

Validation reports are kept with the release they belong to; the CI run linked from each
release is the authoritative record.
