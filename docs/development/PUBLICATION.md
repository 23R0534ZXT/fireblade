# Publishing Kogarasu Host

Host ships as a case image and a per-case driver image. Both use the same version.
The Windows Desktop release is frozen at 0.7.9.

## Prepare the release

1. Set the same version in `pyproject.toml` and `src/fireblade/__init__.py`.
2. Add the release to `CHANGELOG.md`. Start the release notes with a heading in the form
   `# Kogarasu X.Y.Z — Release title`. The publication workflow extracts that section for GitHub.
3. Qualify the release candidate against the [Host workflow](../../.github/workflows/host.yml).
   Check the browser journeys and run the public test pack against the built image.
   Record the tested environments, omissions and results in [the validation reports](../validation/reports).
4. Merge the qualified changes into `main` and verify the release commit and notes before tagging.

## Publish and verify

Push an annotated `vX.Y.Z` tag on the release commit. The [release workflow](../../.github/workflows/release.yml)
creates the GitHub release. The [containers workflow](../../.github/workflows/containers.yml)
publishes the case image as both `kogarasu` and `kogarasu-host`, and the driver as
`kogarasu-driver`. The release and image builds run independently.

Wait for both workflows. Check the release notes on GitHub and pull the exact version
of both images. The case service's `/health` endpoint should return the same version.
The per-case driver and the case containers should use matching tags.

An operator can also dispatch the release workflow manually on `main` with the new tag
as input. That workflow creates the release and dispatches the image builds.
