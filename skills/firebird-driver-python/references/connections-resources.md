# Connections and resource lifetime

Use the installed Firebird client by default. Configure
`driver_config.fb_client_library.value` only when the user requires a specific
client library. In that case, set it before `connect()`, `create_database()`,
`connect_server()`, `load_api()`, or `get_api()` loads the client API. See the
[configuration guide](https://firebird-driver.rtfd.io/usage-guide/configuration/index.md)
and [database guide](https://firebird-driver.rtfd.io/usage-guide/databases/index.md).

Prefer named database and server configurations for application connections;
keep credentials out of code when feasible. For other accepted forms, including
database names, paths, and Firebird DSNs, verify the target version's
[API reference](https://firebird-driver.rtfd.io/ref-core/index.md)
and installed code.

Configuration attributes are option objects: assign their `.value`, rather than
replacing the option. Establish process-global `driver_config` settings during
application startup, before concurrent connection work. If a configuration
file is required, check the list of successfully read files returned by
`driver_config.read()`.

Objects holding server resources support context managers. Prefer `with` for
`Connection`, `Server`, cursors, statements, BLOB readers, transaction managers,
distributed transaction managers, and event collectors when the lifetime fits a
clear block. If it does not, make ownership explicit and close/free the object
in reliable cleanup code. A callee receiving a caller-owned connection should
not close it unless the ownership contract says so. Likewise, a callee receiving
a caller-owned transaction manager should not commit, roll back, or close it
without an explicit ownership contract. Obtain attached resource objects
through driver factories or their owners rather than constructing them
directly. Close dependents before their owner and do not use them after the
owner closes.

Resource context managers release resources; they do not all define the same
transaction outcome. In particular, a connection closing with an active
transaction rolls it back, while the [`transaction()` context manager](transactions-sql.md)
provides commit on success and rollback on error. Never rely on `__del__` for
normal cleanup: finalization order is unpredictable, cleanup may fail, and
`ResourceWarning` may be filtered. See the
[database guide](https://firebird-driver.rtfd.io/usage-guide/databases/index.md)
for connection cleanup.

For streamed BLOBs, keep the reader within the cursor and transaction lifetime;
close it promptly. A column may return materialized data or a `BlobReader`
depending on its size and the cursor's streaming settings. See
[BLOB handling](https://firebird-driver.rtfd.io/usage-guide/data-handling-and-conversions/index.md).

Treat [events](https://firebird-driver.rtfd.io/usage-guide/database-events/index.md) as wake-up
signals, not durable messages. A posted event is observable after the posting
transaction commits; notifications contain occurrence counts, not payloads.
Query durable database state to learn what changed. An event collector's context
calls `begin()` and `close()`; outside a context, do both explicitly.
