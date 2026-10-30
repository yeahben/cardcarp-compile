# Install

Compile is installed by a dataset repo, never by an app. It isn't published to a package registry: a dataset names it as a git dependency, so there's no account to keep and no release step. The repository is the release.

## A dataset repo

The dataset's `pyproject.toml` names Compile as its one dependency. Compile brings its own requirements, ruamel.yaml and cerberus, with it.

<sub>pyproject.toml</sub>

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "ptcg-dataset"
version = "0.0.0"
requires-python = ">=3.10"

dependencies = [
    "cardcarp-compile-core @ git+https://github.com/yeahben/cardcarp-compile.git",
]

# A data repo, not a library: there is no Python here to package.
[tool.setuptools]
packages = []
```

Don't drop the setuptools block at the end. A dataset repo has `data/` and `schema/` folders and no Python of its own, and without a block declaring no packages, setuptools takes those folders for packages and refuses to build.

```sh
pip install .
cardcarp-compile
```

That's the whole local setup a contributor needs, and it's what each dataset's CONTRIBUTING tells them to run.

## Checks on every pull request

Most edits to a dataset are a single card changed in GitHub's web editor, by someone who never runs anything locally. The workflow runs the same two steps on every pull request, so a malformed file, or a card pointing at a set that doesn't exist, fails the check before anyone merges it.

<sub>.github/workflows/validate.yml</sub>

```yaml
name: Validate Data

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.10'
    - run: pip install .
    - run: cardcarp-compile
```

## Holding a version

Without a ref, the dependency follows Compile's default branch, and every run picks up its newest commit. To keep a dataset on a known build, add a tag or a commit to the URL.

<sub>pyproject.toml</sub>

```toml
dependencies = [
    "cardcarp-compile-core @ git+https://github.com/yeahben/cardcarp-compile.git@v0.1.0",
]
```

## Working on Compile

To change the pipeline, install your checkout of Compile in editable mode inside a dataset repo. The dataset's commands then run your working copy, so a change can be tried against real data before it's pushed.

```sh
pip install -e ../compile     # an editable install of your checkout
cardcarp-compile              # the dataset now builds with your working copy

cd ../compile
python util.test.py           # Compile's own tests
```

---

← [Overview](README.md) · [Compile](README.md) · [Configuration](configuration.md) →
