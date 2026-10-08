# Transactions and SQL

Manage transactions explicitly. Prefer `transaction()` when the work fits a
context: it begins on entry, commits on normal exit, and rolls back on error.
Use `Connection.cursor()` for the main transaction, a separate
`TransactionManager.cursor()` for that manager, and
`DistributedTransactionManager.cursor(connection)` for a distributed
transaction's member connection. A cursor belongs to one transaction manager;
do not obtain it from a different manager. See the
[transaction guide](https://firebird-driver.rtfd.io/usage-guide/transactions/index.md).

The connection's initial `default_tpb` is a snapshot, read-write transaction
with an infinite lock wait and no TPB auto-commit. New transaction managers
inherit the connection's current default TPB; changing the connection default
does not retroactively change existing managers. Use `tpb()` for simple
isolation/access/timeout choices and `TPB` for additional parameters such as
table reservations. Supply a one-off TPB to `transaction(..., tpb=...)` or
`begin(tpb)`, or set a transaction manager's `default_tpb` for its subsequent
transactions. Verify defaults and supported isolation modes against the target
version before giving exact advice.

```python
from firebird.driver import Isolation, TraAccessMode, connect, tpb, transaction

read_tpb = tpb(Isolation.READ_COMMITTED_RECORD_VERSION,
               access_mode=TraAccessMode.READ)
with connect("employee") as con:
    with transaction(con, tpb=read_tpb):
        with con.cursor() as cur:
            cur.execute("select country from country where currency = ?", ("Euro",))
            rows = list(cur)
```

`TransactionManager.default_action` controls what happens when that manager
implicitly ends an active transaction; its default is `COMMIT`. The TPB
`auto_commit` flag is a different Firebird transaction parameter, and neither
replaces a deliberate transaction boundary. Avoid both TPB `auto_commit=True`
and auto-commit emulation by starting a new transaction for every statement,
unless the user explicitly needs that behavior. Do not assume that closing a
connection commits pending work. Review
[transaction parameters](https://firebird-driver.rtfd.io/usage-guide/transactions/index.md)
for details and check any server-version restrictions on TPB options.

Pass data values as SQL parameters, never by string formatting or concatenation.
Use `?` placeholders with the driver's parameter API. Stream unbounded result
sets rather than fetching them all; prepare statements when reuse or metadata
inspection warrants it. `execute_immediate()` is only for statements without
results and does not accept bound parameters; use a cursor when either is
needed. See [SQL execution](https://firebird-driver.rtfd.io/usage-guide/executing-sql-statements/index.md).
