# firebird-driver

## Firebird driver for Python

[![PyPI - Version](https://img.shields.io/pypi/v/firebird-driver.svg)](https://pypi.org/project/firebird-driver)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/firebird-driver.svg)](https://pypi.org/project/firebird-driver)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/firebird-driver)](https://pypi.org/project/firebird-driver)
[![Libraries.io SourceRank](https://img.shields.io/librariesio/sourcerank/pypi/firebird-driver)](https://libraries.io/pypi/firebird-driver)

This package provides official Python Database API 2.0-compliant driver for the open
source relational database Firebird®. In addition to the minimal feature set of
the standard Python DB API, this driver also exposes the new (interface-based)
client API introduced in Firebird 3, and number of additional extensions and
enhancements for convenient use of Firebird RDBMS.

-----

**Table of Contents**

- [Installation](#installation)
- [License](#license)
- [Documentation](#documentation)

## Installation

Requires: Firebird 3+

```console
pip install firebird-driver
```
See [firebird-lib](https://pypi.org/project/firebird-lib/) package for optional extensions
to this driver.

## License

`firebird-driver` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Documentation

The documentation for this package is available at [https://firebird-driver.readthedocs.io](https://firebird-driver.readthedocs.io)

## Running tests

This project uses [hatch](https://hatch.pypa.io/latest/) , so you can use:
```console
hatch test
```
to run all tests for default Python version (3.11). To run tests for all Python versions
defined in matrix, use `-a` switch.

This project is using [pytest](https://docs.pytest.org/en/stable/) for testing, and our
tests add several options via `tests/conftest.py`.

By default, tests are configured to use local Firebird installation via network access.
To use local instllation in `mebedded` mode, comment out the section:
```
[tool.hatch.envs.hatch-test]
extra-args = ["--host=localhost"]
```
in `pyproject.toml`.

You can also use firebird driver configuration file to specify server(s) that should be
used for testing, and then pass `--driver-config` and `--server` options to `pytest`.
