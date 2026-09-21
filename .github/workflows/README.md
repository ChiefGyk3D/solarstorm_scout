# GitHub Actions Workflows

Three thin callers. The jobs themselves live in
[ChiefGyk3D/git-your-ship-together](https://github.com/ChiefGyk3D/git-your-ship-together),
shared with Typo Sniper, Stream Daemon, Star Daemon and Boon Tube Daemon, so a
pipeline fix or a new scan step lands once. Each file here says only what is
specific to SolarStorm Scout: Python versions, the import check, the
Dockerfile path, the Doppler project.

| Workflow | Triggers | Calls | What it does |
|---|---|---|---|
| `ci.yml` | push to main, PRs, manual | `python-ci.yml` | Lint (ruff), import and `pip check` on Python 3.11–3.14, Docker build with an import check, one `CI green` gate job for branch protection |
| `release.yml` | push to main, `v*.*.*` tags, PRs, weekly, manual | `python-docker-release.yml` | Build and test on every PR; on main and tags publish a multi-arch (amd64 + arm64) image to `ghcr.io/chiefgyk3d/solarstorm_scout`, signed with cosign, with a syft SBOM attached and SLSA provenance recorded; Trivy scan to the Security tab |
| `security.yml` | push to main/develop, PRs, weekly, manual | `security.yml` | CodeQL, gitleaks over the full history, pip-audit, dependency review on PRs, Snyk |

## Secrets: Doppler, not GitHub

No secret is stored in this repository's GitHub secrets. A job authenticates
to Doppler with a short-lived token minted from its own GitHub OIDC identity
(a Doppler Service Account Identity) and reads the `ci` config of the shared
`ci` Doppler project, which holds only what the pipelines need:

| Name | Used by |
|---|---|
| `SNYK_TOKEN` | `security.yml`, Snyk |

The bot's own runtime credentials (Bluesky, Mastodon) live in a different
Doppler config and never reach CI.

The one per-repository setting is the **repository variable**
`DOPPLER_IDENTITY_ID` (Settings → Secrets and variables → Actions →
Variables), the UUID of the identity. It is an identifier, not a secret.

Before that is set the pipelines still run: Snyk warns and skips, and GHCR
publishing works regardless because it uses the job's own `GITHUB_TOKEN`.

The setup runbook, the fallback path (a Doppler Service Token as the single
GitHub secret `DOPPLER_TOKEN`), and every input are documented in the
git-your-ship-together README.

## Verifying a published image

```sh
cosign verify ghcr.io/chiefgyk3d/solarstorm_scout:latest \
  --certificate-identity-regexp '^https://github.com/ChiefGyk3D/git-your-ship-together/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

gh attestation verify oci://ghcr.io/chiefgyk3d/solarstorm_scout:latest --owner ChiefGyk3D
```

The SBOM is also attached to every run of `release.yml` as the
`sbom.spdx.json` artifact.

## Image tags

- `latest` (main branch only)
- `1.2.3`, `1.2`, `1` (from `v1.2.3` tags)
- `main`, `sha-<short>` (branch and commit)
- `pr-123` (pull requests; built and tested, never pushed)

## Dependabot

`dependabot.yml` opens weekly PRs for Python packages, the Docker base image
and GitHub Actions, each with a seven-day cooldown on new releases.

## Status badges

```markdown
[![CI](https://github.com/ChiefGyk3D/solarstorm_scout/actions/workflows/ci.yml/badge.svg)](https://github.com/ChiefGyk3D/solarstorm_scout/actions/workflows/ci.yml)
[![Release](https://github.com/ChiefGyk3D/solarstorm_scout/actions/workflows/release.yml/badge.svg)](https://github.com/ChiefGyk3D/solarstorm_scout/actions/workflows/release.yml)
[![Security](https://github.com/ChiefGyk3D/solarstorm_scout/actions/workflows/security.yml/badge.svg)](https://github.com/ChiefGyk3D/solarstorm_scout/actions/workflows/security.yml)
```

## What changed in the migration

- `ci-tests.yml`, `docker-build-publish.yml`, `codeql-analysis.yml`,
  `dependency-review.yml`, `dependency-scan.yml` and `snyk-security.yml` were
  replaced by the three callers above.
- The old lint step ran `ruff check penguin-overlord/`, a directory that does
  not exist in this repository (copied from another project), so it had never
  linted anything. It now lints `solarstorm_scout/`, still advisory until the
  tree is clean.
- Bandit and `safety check` were dropped: `safety check` is deprecated
  upstream and needs an account, and both ran as advisory-only. CodeQL and
  ruff's `S` rules cover SAST; pip-audit covers the advisory database.
- pip-audit gates. Ruff lint stays advisory (`lint-continue-on-error`) until
  the tree is clean; delete that line to make it gate.
- `.gitleaks.toml` extends the default ruleset with an empty allowlist; the
  first full-history scan found nothing.
- Images are now signed, carry an SBOM and provenance, and the multi-arch
  build uses the GitHub Actions cache on pull requests instead of
  `no-cache: true`; a publishing build starts clean.
