# Transanction management

For the sake of simplicity, firebird-driver lets the Python programmer ignore
transaction management to the greatest extent allowed by the Python Database
API Specification 2.0. The specification says, “if the database supports an
auto-commit feature, this must be initially off”. At a minimum, therefore,
it is necessary to call the commit method of the connection in order to persist
any changes made to the database.

Remember that because of ACID, every data manipulation operation in the Firebird
database engine takes place in the context of a transaction, including operations
that are conceptually “read-only”, such as a typical SELECT. The client programmer
of firebird-driver establishes a transaction implicitly by using any SQL execution
method, such as `.Connection.execute_immediate()`, `.Cursor.execute()`, or
`.Cursor.callproc()`.

Although firebird-driver allows the programmer to pay little attention to transactions,
it also exposes the full complement of the database engine’s advanced transaction
control features: [transaction parameters](transanction-management.md#transaction-parameters), [retaining transactions](transanction-management.md#retaining-transactions), [savepoints](transanction-management.md#savepoints),
and [distributed transactions](transanction-management.md#distributed-transactions).

## Basics

When it comes to transactions, Python Database API 2.0 specify that `.Connection` object
has to respond to the following methods:

`.Connection.commit()`

  Commits any pending transaction to the database. Note that if the database supports
  an auto-commit feature, this must be initially off. An interface method may be provided
  to turn it back on. Database modules that do not support transactions should implement
  this method with void functionality.

`.Connection.rollback()`

  (optional) In case a database does provide transactions this method causes the the
  database to roll back to the start of any pending transaction. **Closing a connection
  without committing the changes first will cause an implicit rollback to be performed.**

In addition to the implicit transaction initiation required by Python Database API,
firebird-driver allows the programmer to start transactions explicitly via the
`.Connection.begin()` method. Also `.Connection.savepoint()` method was added to provide
support for [Firebird SAVEPOINTs](http://www.firebirdsql.org/refdocs/langrefupd15-savepoint.html).

But Python Database API 2.0 was created with assumption that connection can support only
one transactions per single connection. However, Firebird can support multiple independent
transactions that can run simultaneously within single connection / attachment to the
database. This feature is very important, as applications may require multiple transaction
opened simultaneously to perform various tasks, which would require to open multiple
connections and thus consume more resources than necessary.

Firebird-driver surfaces this Firebird feature by separating transaction management out
from `.Connection` into separate `.TransactionManager` objects. To comply with Python DB
API 2.0 requirements, `.Connection` object uses one `.TransactionManager` instance as
`main transaction`, and delegates `~.Connection.begin()`,
`~.Connection.savepoint()`, `~.Connection.commit()`, `~.Connection.rollback()` and
`~.Connection.execute_immediate()` calls to it.

!!! info

    More about using multiple transactions with the same connection in separate
    [section](transanction-management.md#multiple_transactions).

**Example:**

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    cur = con.cursor()

    # Most minimalistic transaction management -> implicit start, only commit() and rollback()
    # ========================================================================================
    #
    # Transaction is started implicitly
    cur.execute('insert into country values ('Oz','Crowns')
    con.commit() # commits active transaction
    # Again, transaction is started implicitly
    cur.execute('insert into country values ('Barsoom','XXX')
    con.rollback() # rolls back active transaction
    cur.execute('insert into country values ('Pellucidar','Shells')

# Commit was not performed before connection context was closed
# This will roll back the transaction because Python DB API 2.0
# requires that closing connection with pending transaction must
# cause an implicit rollback

```

!!! info
    `.TransactionManager` for details.


## Auto-commit

Firebird-driver doesn't support `auto-commit` feature directly, but developers
may achieve the similar result using `explicit` transaction start, taking advantage
of `.TransactionManager.default_action` and its default value (`~.DefaultAction.COMMIT`).

**Example:**

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    cur = con.cursor()

    con.begin()
    cur.execute('insert into country values ('Oz','Crowns')
    con.begin() # commits active transaction and starts new one
    cur.execute('insert into country values ('Barsoom','XXX')
    con.begin() # commits active transaction and starts new one
    cur.execute('insert into country values ('Pellucidar','Shells')

    # However, commit is required before connection is closed,
    # because Python DB API 2.0 requires that closing connection
    # with pending transaction must cause an implicit rollback
    con.commit()

```


## Transaction parameters

The database engine offers the client programmer an optional facility called
`transaction parameter buffers` (TPBs) for tweaking the operating characteristics
of the transactions he initiates. These include characteristics such as whether
the transaction has read and write access to tables, or read-only access, and
whether or not other simultaneously active transactions can share table access
with the transaction.

Transaction manager has `~.TransactionManager.default_tpb` attribute that can be
changed to set the default TPB to be used for all subsequent transactions started
by this manager. Also Connection have a `~.Connection.default_tpb` attribute,
but it's used to set the default TPB for all transactions managers subsequently
created for the connection (see `.Connection.transaction_manager()`).

Alternatively, if the programmer only wants to set the TPB for a single transaction,
he can start a transaction explicitly via the `.Connection.begin()` or
`.TransactionManager.begin()` method and pass a TPB for that single transaction.

The TPB is a `bytes` value constructed from various tags and binary values, as
defined by API. While you can construct the TPB manually, the firebird-driver
provides several convenient ways for TPB construction:

1. The `.tpb()` function for simple TPBs.

2. The `~firebird.driver.core.TPB` class for complex TPBs (including table reservation etc.).

**Examples:**

```python
from firebird.driver import tpb, TPB, Isolation, TraAccessMode, TableShareMode, TableAccessMode

# Use tpb() if isolation, timeout and access_mode parameters are enough for you
simple_tpb = tpb(Isolation.READ_COMMITTED_READ_CONSISTENCY,100,TraAccessMode.WRITE)

# Use TPB if you want additional parameters than isolation, timeout and access_mode
my_tpb = TPB(isolation=Isolation.SNAPSHOT,
             access_mode=TraAccessMode.WRITE,
             lock_timeout=100,
             no_auto_undo=True,
             auto_commit=True,
             ignore_limbo=True)
my_tpb.reserve_table('MY_TABLE', TableShareMode.PROTECTED, TableAccessMode.LOCK_WRITE)
complex_tpb = my_tpb.get_buffer()

```


## Getting information about transaction

!!! important

    Because the scope and type of transaction information depends on the version of the Firebird
    server, this information is made available through a separate class
    `.TransactionInfoProvider`. The `.TransactionManager.info` property provides access to
    instance of `.TransactionInfoProvider` or it's **ancestor** class according to used
    Firebird version.

Although you may query the information directly from server using
`~.TransactionInfoProvider3.get_info()` method (that wraps the Firebird `ITransaction.getInfo()`
API call), the `.TransactionInfoProvider` object provides more convenient methods and properties
for obtaining specific information directly.

**Example:**

```python
from firebird.driver import connect, driver_config

driver_config.server_defaults.host.value = 'localhost'
with connect('employee', user='SYSDBA', password='masterkey') as con:
    con.begin()
    info = con.main_transaction.info
    print(f"Transaction ID: {info.id}")
    print(f"Database: {info.database}")
    print(f"Isolation level: {info.isolation!s}")
    print(f"Lock timeout: {info.lock_timeout}")
    print(f"Is Read-Only: {info.is_read_only()}")
    print(f"ID of Oldest Interesting Transaction: {info.oit}")
    print(f"ID of Oldest Active Transaction: {info.oat}")
    print(f"ID of Oldest Snapshot Transaction: {info.ost}")

```

Output:

```text
Transaction ID: 352
Database: localhost:employee
Isolation level: Isolation.SNAPSHOT
Lock timeout: -1
Is Read-Only: False
ID of Oldest Interesting Transaction: 350
ID of Oldest Active Transaction: 352
ID of Oldest Snapshot Transaction: 352

```

## Retaining transactions

The `~.TransactionManager.commit()` and `~.TransactionManager.rollback()` methods
accept an optional boolean keyword parameter `retaining` (**default False**) to
indicate whether to recycle the transactional context of the transaction being resolved
by the method call.

If retaining is `True`, the infrastructural support for the transaction active at
the time of the method call will be “retained” (efficiently and transparently recycled)
after the database server has committed or rolled back the conceptual transaction.

!!! important

    In code that commits or rolls back frequently in short amount of time (like in loop),
    “retaining” the transaction may yield better performance. However, retaining transactions
    must be used cautiously because they can interfere with the server’s ability to garbage
    collect old record versions. For details about this issue, read the “Garbage” section of
    [this document](http://www.ibphoenix.com/resources/documents/search/doc_21) by Ann Harrison.

    It's definitely no recommended to use retaining for all transactions, or retain the transaction
    context indefinitely (you should eventually commit/rollback the transaction in normal
    way).

For more information about retaining transactions, see `Firebird documentation`.


## Savepoints

Savepoints are named, intermediate control points within an open transaction that
can later be rolled back to, without affecting the preceding work. Multiple savepoints
can exist within a single unresolved transaction, providing “multi-level undo” functionality.

Although Firebird savepoints are fully supported from SQL alone via the `SAVEPOINT ‘name’`
and `ROLLBACK TO ‘name’` statements, firebird-driver also exposes savepoints at the Python
API level for the sake of convenience.

Call to method `.TransactionManager.savepoint()` establishes a savepoint with the specified
`name`. To roll back to a specific savepoint, call the `~.TransactionManager.rollback()`
method and provide the name of the savepoint for the `savepoint` keyword parameter. If the
savepoint parameter of `~.TransactionManager.rollback()` is not specified, the active
transaction is cancelled in its entirety, as required by the Python Database API Specification.

The following program demonstrates savepoint manipulation via the firebird-driver API,
rather than raw SQL.

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    cur = con.cursor()

    cur.execute("recreate table test_savepoints (a integer)")
    con.commit()

    print('Before the first savepoint, the contents of the table are:')
    cur.execute("select * from test_savepoints")
    print(' ', cur.fetchall())

    cur.execute("insert into test_savepoints values (?)", [1])
    con.savepoint('A')
    print('After savepoint A, the contents of the table are:')
    cur.execute("select * from test_savepoints")
    print(' ', cur.fetchall())

    cur.execute("insert into test_savepoints values (?)", [2])
    con.savepoint('B')
    print('After savepoint B, the contents of the table are:')
    cur.execute("select * from test_savepoints")
    print(' ', cur.fetchall())

    cur.execute("insert into test_savepoints values (?)", [3])
    con.savepoint('C')
    print('After savepoint C, the contents of the table are:')
    cur.execute("select * from test_savepoints")
    print(' ', cur.fetchall())

    con.rollback(savepoint='B')
    print('After rolling back to savepoint B, the contents of the table are:')
    cur.execute("select * from test_savepoints")
    print(' ', cur.fetchall())

    con.rollback()
    print('After rolling back entirely, the contents of the table are:')
    cur.execute("select * from test_savepoints")
    print(' ', cur.fetchall())

```

The output of the example program is shown below:

```text
Before the first savepoint, the contents of the table are:
  []
After savepoint A, the contents of the table are:
  [(1,)]
After savepoint B, the contents of the table are:
  [(1,), (2,)]
After savepoint C, the contents of the table are:
  [(1,), (2,), (3,)]
After rolling back to savepoint B, the contents of the table are:
  [(1,), (2,)]
After rolling back entirely, the contents of the table are:
  []

```

<a id="multiple_transactions"></a>

## Using multiple transactions with the same connection

To use additional transactions that could run simultaneously with
`main transaction` managed by `.Connection`,
create new `.TransactionManager` object calling `.Connection.transaction_manager()`
method. If you don't specify the optional `default_tpb` parameter, this new
`.TransactionManager` inherits the `~.Connection.default_tpb` from `.Connection`.
Physical transaction is not started when `.TransactionManager` instance is
created, but implicitly when first SQL statement for cursor created from
this manager is executed, or explicitly via `.TransactionManager.begin()` call.

To execute statements in context of this additional transaction you have to
use `cursors` obtained directly from this `.TransactionManager` instance calling
its `~.TransactionManager.cursor()` method, or call `.TransactionManager.execute_immediate()`
method.

**Example:**

```python
from firebird.driver import connect, tpb, Isolation, TraAccessMode

with connect('employee', user='SYSDBA', password='masterkey') as con:
    # Cursor for main_transaction context
    cur = con.cursor()

    # Create new READ ONLY READ COMMITTED transaction
    ro_transaction = con.transaction_manager(tpb(Isolation.READ_COMMITTED_RECORD_VERSION,
                                                 access=TraAccessMode.READ))
    # and cursor
    ro_cur = ro_transaction.cursor()

    cur.execute('insert into country values ('Oz','Crowns')
    con.commit() # commits main transaction

    # Read data created by main transaction from second one
    ro_cur.execute("select * from COUNTRY where COUNTRY = `Oz`")
    print(ro_cur.fetchall())

    # Insert more data, but don't commit
    cur.execute('insert into country values ('Barsoom','XXX')

    # Read data created by main transaction from second one
    ro_cur.execute("select * from COUNTRY where COUNTRY = `Barsoom`")
    print(ro_cur.fetchall())

```


<a id="distributed_transactions"></a>

## Distributed Transactions

Distributed transactions are transactions that span multiple databases.
Firebird-driver provides this Firebird feature through `.DistributedTransactionManager`
class. Instances of this class must be created manually, and managed transactions
are fully independent from all other transactions, main or secondary, of member connections.

Similarly to `.TransactionManager`, distributed transactions are managed
through `~.DistributedTransactionManager.begin()`,
`~.DistributedTransactionManager.savepoint()`, `~.DistributedTransactionManager.commit()`
and `~.DistributedTransactionManager.rollback()` methods.
Additionally, `.DistributedTransactionManager` exposes method
`~.DistributedTransactionManager.prepare()` that explicitly initiates the
first phase of `Two-Phase Commit Protocol`. Transaction parameters are defined
similarly to `.TransactionManager` using `~.DistributedTransactionManager.default_tpb`
or as optional parameter to `~.DistributedTransactionManager.begin()` call.

SQL statements that should belong to context of distributed transaction are
executed via `.Cursor` instances aquired through `.DistributedTransactionManager.cursor()`
method, or calling `.DistributedTransactionManager.execute_immediate()` method.

!!! note

    Because `.Cursor` instances can belong to only one `.Connection`, the
    `~.DistributedTransactionManager.cursor()` method has mandatory parameter
    `connection`, to specify to which member connection cursor should belong.

    The `~.DistributedTransactionManager.execute_immediate()` method operates
    on **all** databases in *group*.

**Example program:**

```python
from firebird.driver import create_database, DistributedTransactionManager

# First database
con1 = create_database('db1.fdb', user='SYSDBA', password='masterkey')
con1.execute_immediate("recreate table T (PK integer, C1 integer)")
con1.commit()

# Second database
con2 = create_database('db2.fdb', user='SYSDBA', password='masterkey')
con2.execute_immediate("recreate table T (PK integer, C1 integer)")
con2.commit()

# Create distributed transaction manager
dt = DistributedTransactionManager((con1,con2))

# Prepare cursors for each connection
dc1 = dt.cursor(con1)
dc2 = dt.cursor(con2)

# Connection cursors to check content of databases
q = 'select * from T order by pk'

cc1 = con1.cursor()
p1 = cc1.prep(q)

cc2 = con2.cursor()
p2 = cc2.prep(q)

print("Distributed transaction: COMMIT")
#      ===============================
dc1.execute('insert into t (pk) values (1)')
dc2.execute('insert into t (pk) values (1)')
dt.commit()

# check it
con1.commit()
cc1.execute(p1)
print('db1:', cc1.fetchall())
con2.commit()
cc2.execute(p2)
print('db2:', cc2.fetchall())

print("Distributed transaction: PREPARE + COMMIT")
#      =========================================
dc1.execute('insert into t (pk) values (2)')
dc2.execute('insert into t (pk) values (2)')
dt.prepare()
dt.commit()

# check it
con1.commit()
cc1.execute(p1)
print('db1:', cc1.fetchall())
con2.commit()
cc2.execute(p2)
print('db2:', cc2.fetchall())

print("Distributed transaction: SAVEPOINT + ROLLBACK to it")
#      ===================================================
dc1.execute('insert into t (pk) values (3)')
dt.savepoint('CG_SAVEPOINT')
dc2.execute('insert into t (pk) values (3)')
dt.rollback(savepoint='CG_SAVEPOINT')

# check it - via group cursors, as transaction is still active
dc1.execute(q)
print('db1:', dc1.fetchall())
dc2.execute(q)
print('db2:', dc2.fetchall())

print("Distributed transaction: ROLLBACK")
#      =================================
dt.rollback()

# check it
con1.commit()
cc1.execute(p1)
print('db1:', cc1.fetchall())
con2.commit()
cc2.execute(p2)
print('db2:', cc2.fetchall())

print("Distributed transaction: EXECUTE_IMMEDIATE")
#      ==========================================
dt.execute_immediate('insert into t (pk) values (3)')
dt.commit()

# check it
con1.commit()
cc1.execute(p1)
print('db1:', cc1.fetchall())
con2.commit()
cc2.execute(p2)
print('db2:', cc2.fetchall())

# Finalize
con1.drop_database()
con1.close()
con2.drop_database()
con2.close()

```

Output:

```text
Distributed transaction: COMMIT
db1: [(1, None)]
db2: [(1, None)]
Distributed transaction: PREPARE + COMMIT
db1: [(1, None), (2, None)]
db2: [(1, None), (2, None)]
Distributed transaction: SAVEPOINT + ROLLBACK to it
db1: [(1, None), (2, None), (3, None)]
db2: [(1, None), (2, None)]
Distributed transaction: ROLLBACK
db1: [(1, None), (2, None)]
db2: [(1, None), (2, None)]
Distributed transaction: EXECUTE_IMMEDIATE
db1: [(1, None), (2, None), (3, None)]
db2: [(1, None), (2, None), (3, None)]

```

<a id="transaction-context-manager"></a>

## Transaction Context Manager

Firebird-driver provides context manager `~firebird.driver.core.transaction` that allows automatic
transaction management using WITH statement. It can work with
any object that supports `begin()`, `commit()` and `rollback()` methods, i.e.
`.Connection`, `.TransactionManager` or `.DistributedTransactionManager`.

It starts transaction when WITH block is entered and commits it if no exception
occurs within it, or calls `rollback()` otherwise. Exceptions raised in WITH
block are never suppressed.

Examples:

```python
from firebird.driver import connect, transaction, DistributedTransactionManager

with connect('employee', user='SYSDBA', password='masterkey') as con:

    # Uses default main transaction
    with transaction(con):
        cur = con.cursor()
        cur.execute("insert into T (PK,C1) values (1,'TXT')")

    # Uses separate transaction
    with transaction(con.transaction_manager()) as tr:
        cur = tr.cursor()
        cur.execute("insert into T (PK,C1) values (2,'AAA')")

    # Uses distributed transaction
    with connect('employee2', user='SYSDBA', password='masterkey') as con2,
         DistributedTransactionManager(con, con2) as dtm:
        with transaction(dtm):
            cur1 = cg.cursor(con)
            cur2 = cg.cursor(con2)
            cur1.execute("insert into T (PK,C1) values (3,'Local')")
            cur2.execute("insert into T (PK,C1) values (3,'Remote')")

```
