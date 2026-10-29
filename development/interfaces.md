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
they affect. The same hook completes metadata for the private driver provider using the root
directory and client version reported by the loaded API. `iUtil.get_client_version()` returns
`(major, minor)`.

Attachment, transaction, statement, result set, and BLOB wrappers propagate the owning
connection's lifecycle flag. Status errors for `isc_conn_lost`, `isc_net_read_err`,
`isc_net_write_err`, `isc_lost_db_connection`, and `isc_att_shutdown` mark that flag dead.
Reference-counted finalizers skip native release when it is dead.
