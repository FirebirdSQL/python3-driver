# `firebird.driver.core`

Source: `src/firebird/driver/core.py`, relative to the repository root.

This module implements the high-level DB API: `connect()`, `create_database()`, `connect_server()`,
`Connection`, `TransactionManager`, `Cursor`, statements, BLOB handling, database events,
and service manager operations. It also builds parameter buffers and exposes version-sensitive
information providers.

Keep resource ownership aligned with this structure. A `Connection` owns its transaction managers,
statements, and event collectors; each `Cursor` holds its own transaction manager reference.
The connection creates a main transaction, a read-only query transaction, and an internal cursor.
Closing a connection must account for its dependent resources. The `transaction()` context
manager begins a transaction and commits or rolls back on exit; with `bypass=True`, it joins
an already active transaction without finishing it.

For changes here, select tests by behavior: `test_connection.py`, `test_transaction.py`,
`test_cursor.py`, `test_statement.py`, `test_blob.py`, `test_array.py`, `test_events.py`,
`test_distributed_trans.py`, `test_server.py`, and `test_info_providers.py`. Exercise the real
prepared Firebird environment for lifecycle and wire protocol changes.
