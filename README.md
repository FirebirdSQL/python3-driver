# firebird-driver

## Firebird driver for Python

[![PyPI - Version](https://img.shields.io/pypi/v/firebird-driver.svg)](https://pypi.org/project/firebird-driver)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/firebird-driver.svg)](https://pypi.org/project/firebird-driver)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/firebird-driver)](https://pypi.org/project/firebird-driver)
[![Libraries.io SourceRank](https://img.shields.io/librariesio/sourcerank/pypi/firebird-driver)](https://libraries.io/pypi/firebird-driver)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/FirebirdSQL/python3-driver)

This package provides official Python Database API 2.0-compliant driver for the open
source relational database Firebird®. In addition to the minimal feature set of
the standard Python DB API, this driver also exposes the new (interface-based)
client API introduced in Firebird 3, and number of additional extensions and
enhancements for convenient use of Firebird RDBMS.

-----

**Table of Contents**

- [Installation](#installation)
- [Agent skill](#agent-skill)
- [License](#license)
- [Documentation](#documentation)

## Installation

Requires: Firebird 3+

```console
pip install firebird-driver
```
See [firebird-lib](https://pypi.org/project/firebird-lib/) package for optional extensions
to this driver.

## Agent skill

This repository includes a [skill for coding with firebird-driver](skills/firebird-driver-python/SKILL.md).
Once the skill is published on GitHub, run these commands in a directory where
you want to keep a checkout (Unix-like shell):

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/FirebirdSQL/python3-driver.git firebird-driver-skill-source
git -C firebird-driver-skill-source sparse-checkout set skills/firebird-driver-python
```

Then copy the skill into the directory for each agent you use:

```sh
# Codex
mkdir -p ~/.codex/skills
cp -R firebird-driver-skill-source/skills/firebird-driver-python ~/.codex/skills/

# Claude Code
mkdir -p ~/.claude/skills
cp -R firebird-driver-skill-source/skills/firebird-driver-python ~/.claude/skills/

# Gemini CLI
mkdir -p ~/.gemini/skills
cp -R firebird-driver-skill-source/skills/firebird-driver-python ~/.gemini/skills/
```

Run only the copy commands for the agents you use. Each user-level location makes
the skill available across your projects. Codex lists installed skills with
`/skills`; Claude Code can invoke `/firebird-driver-python`; Gemini CLI lists
them with `/skills list` and can reload them with `/skills reload`.
See the [Codex](https://learn.chatgpt.com/docs/build-skills),
[Claude Code](https://code.claude.com/docs/en/skills), and
[Gemini CLI](https://geminicli.com/docs/cli/using-agent-skills/) skill guides.

## License

`firebird-driver` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Documentation

The documentation for this package is available at [https://firebird-driver.readthedocs.io](https://firebird-driver.readthedocs.io)

## Running tests

See [development/README.md](development/README.md) for the Firebird test setup, Hatch
commands, and development workflow.
