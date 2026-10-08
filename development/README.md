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
runs its Python 3.11–3.14 matrix. The `hatch-test` environment in `pyproject.toml` passes
`--host=localhost` by default. `tests/conftest.py` also accepts `--host`, `--port`, `--client-lib`,
`--driver-config`, and `--server`. Use a focused test file while developing, then run the
wider suite when the prepared Firebird environment is available. Do not treat a missing server
or client library as a passing test.

For embedded-mode testing, remove the `--host=localhost` extra argument from `[tool.hatch.envs.hatch-test]`
in `pyproject.toml` and provide a suitable local client library. Alternatively, use a driver
configuration file with `--driver-config` and select a named server with `--server`. Check
`tests/conftest.py` for how these options are applied before the API is loaded.

## Documentation and packaging

From the repository root, `hatch run doc:build` builds `docs/zensical.toml` and the Markdown
pages in `docs/docs/`. `hatch run doc:serve` previews them. `hatch run doc:docset` builds
a Dash/Zeal docset and archives it in `dist/`. Read the Docs uses `.readthedocs.yml` to
publish the Zensical output. Keep user-facing API descriptions in source docstrings and
`docs/docs/`; keep implementation and test guidance here.

The project builds with Hatchling. The version comes from `src/firebird/driver/__init__.py`,
and Ruff settings are in `pyproject.toml`.
