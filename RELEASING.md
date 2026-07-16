# Releasing whaagent

This document describes how to release new versions of the `whaagent` package to PyPI.

## Overview

whaagent is a single package that includes both the core framework and WhatsApp integration:

- **whaagent** (v1.0.0-alpha): AI agent framework with WhatsApp support

## Prerequisites

### 1. Trusted Publishers (One-time setup)

whaagent uses PyPI's [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) for secure, OIDC-based authentication. No API tokens or passwords are stored in GitHub.

**Configure for `whaagent`:**

1. Go to https://pypi.org/manage/project/whaagent/settings/publishing/
2. Click "Add a new pending publisher"
3. Configure:
   - **PyPI Project Name:** `whaagent`
   - **Owner:** `jeancsil`
   - **Repository name:** `whaagent`
   - **Workflow name:** `.github/workflows/release.yml`
   - **Environment name:** `pypi` (or leave blank)

### 2. Permissions

- You must have `push` access to the repository
- You must be a maintainer/owner of PyPI projects
- **You must be on the `main` branch** (or use `FORCE_RELEASE=1` to bypass)

### 3. GitHub CLI

The automated release requires GitHub CLI (`gh`) installed and authenticated:

```bash
brew install gh        # macOS
# OR
apt install gh         # Linux

gh auth login
```

## Automated Release (Recommended)

Use the `make` command for streamlined releases:

```bash
make release VERSION=1.0.0-beta
```

This releases `whaagent` to version 1.0.0-beta and:
- Updates `pyproject.toml` version
- Runs all tests
- Commits, tags, and pushes to GitHub
- Creates GitHub release (triggers PyPI publish)

## Manual Release (Without make command)

If you need more control, you can manually execute the release script:

```bash
# Release whaagent
./scripts/release.sh 1.0.0-beta
```

## Step-by-Step Manual Release

If you prefer manual control over each step:

### Step 1: Ensure main is up to date

```bash
git checkout main
git pull origin main
```

### Step 2: Verify all checks pass

```bash
make check
make test
```

### Step 3: Update version number

Edit `pyproject.toml` and update the `version` field:

```toml
version = "1.0.0-beta"  # Update this
```

### Step 4: Commit and push

```bash
git add pyproject.toml
git commit -m "chore: bump version to 1.0.0-beta"
git push origin main
```

### Step 5: Create a GitHub Release

```bash
gh release create v1.0.0-beta --title "v1.0.0-beta" --notes "Release notes here"
```

Or use the GitHub UI:
1. Go to https://github.com/jeancsil/whaagent/releases/new
2. Tag: `v1.0.0-beta`
3. Title: `v1.0.0-beta`
4. Add release notes
5. Click "Publish release"

## Version Strategy

### Versioning

The package follows semantic versioning with optional pre-release suffixes:

| Package | Current Version | Tag Format |
|---------|-----------------|------------|
| whaagent | 1.0.0-alpha | `vX.Y.Z[-prerelease]` |

### Semantic Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes

### When to Bump Which Version

| Scenario | Version Change | Command |
|----------|----------------|----------|
| Bug fix | Patch (x.y.Z) | `make release VERSION=x.y.z` |
| New feature | Minor (x.Y.0) | `make release VERSION=x.y.0` |
| Breaking change | Major (X.0.0) | `make release VERSION=X.0.0` |

## What Happens Next

The [release workflow](.github/workflows/release.yml) automatically:

1. **Builds** the `whaagent` package
2. **Publishes to PyPI** (for full releases)
3. **Publishes to TestPyPI** (for pre-releases)

### For Full Releases

- Packages are published to https://pypi.org/project/whaagent/
- Users can install with `pip install whaagent`

### For Pre-releases

Create a pre-release by marking the GitHub release as "pre-release":
- Packages go to https://test.pypi.org/project/whaagent/
- Install with `pip install -i https://test.pypi.org/simple/ whaagent`

## Verification

### Verify Release on PyPI

After the GitHub Actions workflow completes:

```bash
# Check whaagent
curl -s https://pypi.org/pypi/whaagent/json | jq -r '.info.version'
```

### Test Install Fresh Version

```bash
# Test install
uv pip install --force-reinstall whaagent==1.0.0-beta
```

## Troubleshooting

### "Uncommitted changes detected"

Commit or stash your changes before releasing:

```bash
git status
git commit -am "WIP"
# OR
git stash
```

### "Invalid version format"

Versions must follow semantic versioning: `X.Y.Z`

```bash
# Correct
make release VERSION=1.0.0-beta

# Incorrect
make release VERSION=0.3       # Missing patch
make release VERSION=0.3.0.1    # Too many parts
make release VERSION=v0.3.0     # Don't include 'v' prefix
```

### "Tests failed. Aborting release"

Fix test failures before releasing:

```bash
make check && make test
# Fix issues, then retry release
```

### "You are on branch 'X', but releases should be done from 'main'"

The release script checks that you're on the `main` branch before releasing. This prevents accidental releases from feature branches.

**To fix:**

```bash
# Switch to main branch
git checkout main
git pull origin main

# Then try release again
make release VERSION=1.0.0-beta
```

**To bypass this check (not recommended):**

```bash
# Only use this if you know what you're doing
FORCE_RELEASE=1 make release VERSION=1.0.0-beta
```

### "GitHub CLI (gh) is required"

Install and authenticate gh:

```bash
brew install gh  # macOS
# OR
apt install gh  # Linux

gh auth login
```

### Release failed with "400 Bad Request"

This usually means the Trusted Publisher isn't configured:

1. Verify publisher settings on PyPI match exactly:
   - Repository name (case-sensitive)
   - Workflow name (including `.yml` extension)
   - Environment name (if used)

### Package already exists

You cannot republish the same version. Increment the version number and try again.

### Build fails

Run locally to debug:

```bash
make build
ls -la dist/
```

### Tests fail in CI but pass locally

Ensure your `.env` has the required API keys for testing:
```bash
export OPENAI_API_KEY=sk-test  # For CI
```

### Rollback

PyPI does not allow overwriting existing versions. If something goes wrong:

1. Delete the GitHub release
2. Delete the git tag (locally and remotely)
3. Increment version to a new number
4. Create new release

```bash
# Delete remote tag
git push origin --delete v1.0.0-beta

# Delete local tag
git tag -d v1.0.0-beta

# Release with new version
make release VERSION=1.0.0-beta.2
```

## Manual Publishing (Emergency Only)

If GitHub Actions is unavailable, you can publish manually:

```bash
# Build
make build

# Publish to PyPI (requires API token)
uv run twine upload dist/*
```

Note: Manual publishing requires a PyPI API token, which is less secure than Trusted Publishers.

## Quick Reference

```bash
# View current version
grep "^version" pyproject.toml

# View recent tags
git tag -l --sort=-version:refname

# Run full check before release
make check && make test

# Release command
make release VERSION=1.0.0-beta

# Manual script command
./scripts/release.sh 1.0.0-beta
```
