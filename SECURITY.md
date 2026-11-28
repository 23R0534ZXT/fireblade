# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Use GitHub's private report:
**Security → Report a vulnerability** on <https://github.com/23R0534ZXT/kogarasu/security>.
Include the version or image tag, what you did, what you expected and what happened.

You can expect an acknowledgement within a week and a fix or a decision within a month. This is a
single-maintainer project: the times are targets, not a service level.

## Supported versions

Only the latest release of the Host edition receives fixes. The Desktop edition is frozen at 0.7.9
and receives none.

## What the Host is, and is not, designed to resist

The Host is for one analyst on their own machine. It has no accounts and no access control, and
it must not be exposed to a network: start it with `-p 127.0.0.1:8080:8080`. Today it does not
defend itself against a hostile page open in the same browser, or against another user of the
same machine; both are known limits, tracked for a later release, and reports about them are
welcome as improvements rather than as vulnerabilities.

Within that scope these are vulnerabilities and are taken seriously:

- evidence being modified, or a destruction certificate being wrong about what was destroyed;
- a path or an archive that escapes the case folder or the container;
- a crafted evidence file that executes code, or that crashes the service in a way that loses a case;
- a secret, a path or a hash that leaves the machine without the analyst having asked for it.

The one outbound request the Host makes is the check for a newer release
(`FIREBLADE_UPDATE_CHECK=off` removes it).

Software erasure is not a physical guarantee on SSDs, copy-on-write or journaled file systems; the
certificate states the method that was used, and `docs/host/STATUS.md` says what that means.

## Supply chain

The readers are pinned by version and fetched by hash from `config/forensic-toolchain.json`;
Python dependencies are pinned in `requirements/`; Dependabot proposes updates to both and to the
workflows. Third-party licences are in `licenses/THIRD_PARTY.md`.
