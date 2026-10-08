# `firebird.driver.interfaces`

Source: `src/firebird/driver/interfaces.py`, relative to the repository root.

This module wraps Firebird's object API interfaces over the `ctypes` declarations in `fbapi.py`.
The `iVersionedMeta` constructor selects a wrapper class based on the returned interface
version. Versioned classes such as `iAttachment_v3` and `iAttachment_v4` preserve behavior
for older engines; the canonical wrapper represents the newest supported interface.

Ownership matters at this boundary: reference-counted wrappers release references, and
disposable wrappers dispose their interfaces. Status checking translates Firebird status
vectors into driver errors or warnings. On `APIHook.LOADED`, the module obtains the master
and utility interfaces and attaches them to the API object. Check wrapper changes against
the matching `fbapi.py` declarations and run integration tests for the Firebird versions
they affect.
