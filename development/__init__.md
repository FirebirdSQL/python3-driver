# `firebird.driver.__init__`

Source: `src/firebird/driver/__init__.py`, relative to the repository root.

This module re-exports the public DB API, configuration objects, hook access points, and
selected types from the implementation modules. It also defines `__VERSION__`, which Hatchling
reads for the package version and the docset script reads for its archive name.

When changing a public symbol, check whether it must be exported here and documented in
`docs/docs/ref-main.md` or another API page. Keep implementations in their owning modules.
Check imports after export changes because importing `firebird.driver` loads several
implementation modules and registers API hooks.
