---
name: release
description: End-to-end release workflow — version bump, changelog generation, git tag, build, and publish to PyPI. Invoke with /release [version]. Use semantic versioning.
disable-model-invocation: true
---

# Release Workflow

End-to-end release process: validate, version bump, changelog, build, tag, publish to PyPI via GitHub Actions.

## Usage

```
/release 1.0.0
/release 1.2.0-beta
/release 2.0.0-rc.1
```

The version argument is required and must follow semantic versioning (X.Y.Z with optional pre-release suffix like `-alpha`, `-beta.1`, `-rc.2`).

## Release Flow

Execute these steps in order. Each step has a validation gate -- stop and ask the user before proceeding if something looks wrong.

### Step 1: Validate version

Check the provided version string:

```bash
echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*)?$'
```

- If the version does not match semver format, stop and tell the user the expected format: `X.Y.Z` or `X.Y.Z-prerelease`.
- Determine if this is a pre-release (version contains `-`) or stable release. This matters for Step 9.

### Step 2: Check clean state

Verify no uncommitted changes:

```bash
git status --porcelain
```

- If there are uncommitted changes, stop. Tell the user to commit or stash them before releasing.
- Do not proceed with dirty working tree.

### Step 3: Check main branch

Verify the current branch is `main`:

```bash
git branch --show-current
```

- If not on `main`, stop and tell the user. Releases should come from `main`.
- Suggest: `git checkout main && git pull origin main`

### Step 4: Show diff since last tag

Generate a changelog summary from the commits since the last tag:

```bash
LAST_TAG=$(git tag --sort=-v:refname | head -1)
echo "Changes since $LAST_TAG:"
git log --oneline "$LAST_TAG"..HEAD
```

Present the commit list to the user and ask for confirmation:

```
Changelog since $LAST_TAG:
  <commit list>

Release whaagent v$VERSION with these changes? [y/n]
```

Do not proceed without explicit user confirmation.

### Step 5: Run checks and tests

Run the full quality gate:

```bash
make check && make test
```

- If either fails, stop. Report the failures and tell the user to fix them before releasing.
- Do not skip or bypass failures.

### Step 6: Update version in pyproject.toml

Edit `pyproject.toml` to set the new version. Use the Edit tool to replace the `version = "..."` line:

```
Old: version = "1.0.0-beta"
New: version = "1.2.0"
```

Verify the change:

```bash
head -5 pyproject.toml
```

Confirm the version line is correct before proceeding.

### Step 7: Commit and tag

Commit the version bump and create an annotated tag:

```bash
git add pyproject.toml
git commit -m "release: v$VERSION"
git tag -a "v$VERSION" -m "Release v$VERSION"
```

Verify:

```bash
git log --oneline -1
git tag -l "v$VERSION"
```

If the tag already exists, stop and tell the user. They may need to delete the existing tag first.

### Step 8: Push commit and tag

```bash
git push origin main --tags
```

If the push fails, stop and report the error. Do not force push.

### Step 9: Create GitHub release

Use `gh` to create the GitHub release. Pre-releases go to TestPyPI, stable releases go to PyPI (handled by `.github/workflows/release.yml`).

For a **pre-release** (version contains `-`):

```bash
gh release create "v$VERSION" --title "v$VERSION" --prerelease --notes "## whaagent v$VERSION

Released $(date +%Y-%m-%d).

### Changes

<paste commit list from Step 4>"
```

For a **stable release**:

```bash
gh release create "v$VERSION" --title "v$VERSION" --notes "## whaagent v$VERSION

Released $(date +%Y-%m-%d).

### Changes

<paste commit list from Step 4>"
```

The GitHub release triggers the `release.yml` workflow which:
- **Stable**: builds and publishes to [PyPI](https://pypi.org/p/whaagent)
- **Pre-release**: builds and publishes to [TestPyPI](https://test.pypi.org/p/whaagent)

### Step 10: Verify

Check that the GitHub Actions workflow was triggered:

```bash
gh run list --workflow=release.yml --limit=1
```

Monitor the workflow run:

```bash
gh run watch
```

Once the workflow completes, verify the package is available:

- **Stable**: `https://pypi.org/p/whaagent`
- **Pre-release**: `https://test.pypi.org/p/whaagent`

## Summary

After completion, report:

```
Released whaagent v$VERSION.
  Tag: v$VERSION
  GitHub: https://github.com/jeancsil/whaagent/releases/tag/v$VERSION
  PyPI: https://pypi.org/p/whaagent (stable) or https://test.pypi.org/p/whaagent (pre-release)
```

## Rollback

If something goes wrong after the tag is pushed:

1. Delete the remote tag: `git push origin :refs/tags/v$VERSION`
2. Delete the GitHub release: `gh release delete v$VERSION --yes`
3. Reset the commit: `git reset --hard HEAD~1`
4. Force push (with caution): `git push origin main --force`

Only attempt rollback if the user explicitly asks. Always confirm destructive operations.

## Notes

- The release script at `scripts/release.sh` automates this same flow. The skill replicates it with interactive validation gates.
- `gh` CLI must be installed and authenticated (`gh auth status`).
- Pre-release versions (containing `-alpha`, `-beta`, `-rc`) are published to TestPyPI. Stable versions (no suffix) are published to PyPI.
- Gateway binaries are built and attached to the GitHub release by `scripts/build-gateway.sh` (if Go is available).
- The `release.yml` GitHub Actions workflow handles the actual PyPI/TestPyPI publishing using trusted publisher (OIDC) authentication.
