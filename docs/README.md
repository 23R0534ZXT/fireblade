# Documentation

Kogarasu Host is the maintained browser edition. The historical Fireblade Desktop
guides describe the Windows interface and its bundled tools.

## Kogarasu Host

| Task | Guide |
| --- | --- |
| Start Host and investigate a sample CSV | [Quick start](../README.md#quick-start) |
| Import and review a case | [Investigation workflow](../README.md#investigation-workflow) · [Host guide](host/README.md) |
| Build, isolate or upgrade an installation | [Deployment guide](../deploy/host/README.md) |
| Check a reader or a known limit | [Reader coverage](host/LINUX-READERS.md) · [Host status](host/STATUS.md) |
| Inspect qualification results | [Reports and measurements](../README.md#qualification-and-scope) |

## Fireblade Desktop

| Task | Guide |
| --- | --- |
| Install the final Windows release | [Desktop](desktop/README.md) |
| Learn the interface end to end | [Full tutorial](guides/TUTORIEL-COMPLET-en.md) |
| Follow an investigation | [User guide](guides/UTILISATION-en.md) |
| Correlate records and transport a case | [Timeline and backups](guides/CHRONOLOGIE-ET-SAUVEGARDES-en.md) |
| Hunt indicators in bulk | [IOC hunting](guides/CHASSE-IOC-en.md) |
| Review the coverage of a collection | [Coverage and diagnostics](guides/COUVERTURE-COLLECTE-en.md) |
| Work with a disk image or mounted volume | [Disks and workspace (French)](guides/DISQUES-ET-ESPACE-DE-TRAVAIL.md) |
| Use sample datasets | [Test datasets (French)](guides/JEUX-DE-TEST.md) |

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
