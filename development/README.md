# Driver development

Paths and commands written in prose are relative to the repository root unless a command
explicitly changes directory. Markdown links are relative to this file. This directory contains
developer information. The published user documentation is in `docs/docs/` and is built with Zensical.

## Package layout

The Python package is `src/firebird/driver/`. Its public namespace is assembled in `__init__.py`;
the other modules separate configuration, DB API behavior, client library bindings, interface
wrappers, types, and hooks. Read the module note before changing its source:

| Source module | Development note | Main responsibility |
| --- | --- | --- |
| `__init__.py` | [__init__.md](__init__.md) | Public exports and version |
| `config.py` | [config.md](config.md) | Driver, server, and database configuration |
| `core.py` | [core.md](core.md) | Connections, transactions, cursors, events, and services |
| `fbapi.py` | [fbapi.md](fbapi.md) | `ctypes` bindings and client library loading |
| `hooks.py` | [hooks.md](hooks.md) | Driver hook kinds and registration imports |
| `interfaces.py` | [interfaces.md](interfaces.md) | Firebird object API wrappers |
| `provider.py` | [provider.md](provider.md) | Runtime provider contract and system-client selection |
| `types.py` | [types.md](types.md) | DB API exceptions, constants, flags, and data types |

The package requires Python 3.11 or newer and depends on `firebird-base` and `python-dateutil`.
`pyproject.toml` is the source of truth for supported test interpreters and build dependencies.

## Tests

The tests in `tests/` are integration tests. `tests/conftest.py` loads the Firebird client
API and connects to a Firebird service manager during pytest configuration. It selects a prepared
database for Firebird 3, 4, or 5, copies it into a temporary directory, and configures a `pytest`
database entry. A working client library, server, and matching test database are therefore
needed even for many narrowly selected tests.

From the repository root, `hatch test` runs the default test environment; `hatch test -a`
runs the Python and backend matrix in `pyproject.toml`. The `local` backend passes
`--host=localhost`; `localem` uses a local embedded connection. Select a single Python 3.11
backend during development, for example `hatch test -i backend=localem -py 3.11`.
`tests/conftest.py` also accepts `--host`, `--port`, `--client-lib`,
`--driver-config`, and `--server`. Use a focused test file while developing, then run the
wider suite when the prepared Firebird environment is available. Do not treat a missing server
or client library as a passing test.

At startup, the tests inspect entry points in `firebird.runtime.providers`. With one provider,
they load its client library before any connection. The driver sets `FIREBIRD` to the provider
root before loading the library if it is unset or points elsewhere. With more than one provider,
setup stops with an error. Without a registered provider, the configured or system
client library is used. The pytest `Firebird:` header reports the loaded provider and the selected
source database, which the fixtures copy for the run. The `fb3em` backend installs
`firebird-embedded~=3.0`; check that its header reports Firebird 3 and `fbtest30.fdb`.
Alternatively, use a driver configuration file with `--driver-config` and select a named server
with `--server`.

## Firebird feature versions

Guard test cases and driver code that use version-specific Firebird features against the tested
engine version. Features remain available in later releases, but a feature introduced in minor
releases of multiple supported branches needs a separate threshold for each branch. For example,
if a feature first appears in 3.0.6 and 4.0.2, a check for `>=3.0.6` would incorrectly allow
4.0.0 and 4.0.1. Express that case as `>=3.0.6,<4.0` or `>=4.0.2`, and document the actual
thresholds beside the guard and here or in the matching module note. Do not infer availability
from the major version alone when a feature was introduced in a minor release.

Current test examples: snapshot-number and READ CONSISTENCY transaction parameters require
Firebird 4.0 or newer; `SET DEBUG OPTION DSQL_KEEP_BLR` requires Firebird 4.0.1 or newer.
Trace session plugin selection requires Firebird 6.0 or newer.

## Documentation and packaging

From the repository root, `hatch run doc:build` builds `docs/zensical.toml` and the Markdown
pages in `docs/docs/`. `hatch run doc:serve` previews them. `hatch run doc:docset` builds
a Dash/Zeal docset and archives it in `dist/`. Read the Docs uses `.readthedocs.yml` to
publish the Zensical output. Keep user-facing API descriptions in source docstrings and
`docs/docs/`; keep implementation and test guidance here.

The project builds with Hatchling. The version comes from `src/firebird/driver/__init__.py`,
and Ruff settings are in `pyproject.toml`.
Run `hatch run build-skill` to package the complete `skills/firebird-driver-python/` directory
as `dist/firebird-driver-<version>-skill.zip` for a GitHub release.
