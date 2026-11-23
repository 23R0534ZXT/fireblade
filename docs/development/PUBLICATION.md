# Publishing a version

## Checks and a release are two separate operations

Pull requests and code changes on `main` run the Windows checks. A change to
`README.md`, `docs/` or the notices alone does not launch the full build on a push.
An ordinary successful build keeps the EXE in the Actions artefacts and creates no
public release.

A release is created by hand, from a tag, in one of two ways:

1. **`workflow_dispatch` on `windows.yml`** with `publish_release` set — the workflow
   builds, qualifies, then publishes.
2. **`scripts/release.py`** on the workstation that holds the `gh` session — it reads
   `docs/development/RELEASE-NOTES.md`, checks the SHA-256 of the zip it publishes, and
   links the release from `README.md` through `scripts/update_release_readme.py`.

## What a release must carry

- The zip, its SHA-256 in the notes, and the same hash in the release body.
- A title and notes in UTF-8 (pass them through the API, not through a console code
  page, or the accents arrive mangled).
- A link back from `README.md`; the release script writes it, and refuses to promote a
  draft, a mismatched tag or a release without its asset.

## The rule that keeps a version readable

Nothing is pushed to `main` while a single check is red. A version is a documented
batch: the notes say why each group exists, not only what changed.
