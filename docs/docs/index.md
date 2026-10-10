
# The Python driver for Firebird

The `firebird-driver` package provides official [Python Database API 2.0](http://www.python.org/dev/peps/pep-0249/)-compliant driver
for the open source relational database [Firebird](http://www.firebirdsql.org) ®. In addition to the minimal feature
set of the standard Python DB API, this driver also exposes the new (interface-based) client
API introduced in Firebird 3, and number of additional extensions and enhancements for
convenient use of Firebird RDBMS.

This documentation set is not a tutorial on SQL or Firebird; rather, it is a topical
presentation of driver's feature set, with example code to demonstrate basic usage patterns.
For detailed information about Firebird features, see the
[Firebird documentation](http://www.firebirdsql.org/en/documentation/), and especially
the excellent [The Firebird Book](https://www.ibphoenix.com/products/publications/fbook/)
written by Helen Borrie and published by [IBPhoenix](http://www.ibphoenix.com).

!!! note
    Driver development is sponsored by [IBPhoenix](http://www.ibphoenix.com).

    [![PyPI - Version](https://img.shields.io/pypi/v/firebird-driver.svg)](https://pypi.org/project/firebird-driver)
    [![PyPI - Python Version](https://img.shields.io/pypi/pyversions/firebird-driver.svg)](https://pypi.org/project/firebird-driver)
    [![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
    [![PyPI - Downloads](https://img.shields.io/pypi/dm/firebird-driver)](https://pypi.org/project/firebird-driver)
    [![Libraries.io SourceRank](https://img.shields.io/librariesio/sourcerank/pypi/firebird-driver)](https://libraries.io/pypi/firebird-driver)
    [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/FirebirdSQL/python3-driver)

    [Source repository](https://github.com/FirebirdSQL/python3-driver)

!!! info
    [firebird-lib](https://pypi.org/project/firebird-lib/) package for optional extensions to this driver.

!!! tip
    You can download docset for [Dash](https://kapeli.com/dash) (MacOS) or [Zeal](https://zealdocs.org/) (Windows / Linux) documentation

    readers from [releases](https://github.com/FirebirdSQL/python3-driver/releases) at github.
