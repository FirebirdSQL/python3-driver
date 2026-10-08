# Databases

Access to the database is made available through [`Connection`](../ref-core.md#firebird.driver.core.Connection) objects. Firebird-driver
provides two constructors for these:

* [`connect`](../ref-core.md#firebird.driver.core.connect) - Returns [`Connection`](../ref-core.md#firebird.driver.core.Connection) to database that already exists.
* [`create_database`](../ref-core.md#firebird.driver.core.create_database) - Returns [`Connection`](../ref-core.md#firebird.driver.core.Connection) to newly created database.



## Using connect()

This constructor has one positional and several keyword parameters.

The value of `database` positional parameter must be one of:

* name of registered database configuration
* database name / alias

!!! important
    This value **cannot** be DSN / fully qualified Firebird connection string!

Keyword parameters are intended to override selected configuration options, or to specify
options that are not configurable.

!!! note

    If `database` value is not recognized as name of registered database configuration,
    the driver uses [`db_defaults`](../ref-config.md#firebird.driver.config.DriverConfig) and [`server_defaults`](../ref-config.md#firebird.driver.config.DriverConfig)
    configuration objects.

A simple database connection is typically established with code such as this:

```python
from firebird.driver import connect

# Attach to 'employee' database/alias using embedded server connection
con = connect('employee', user='sysdba', password='masterkey')

# Attach to 'employee' database/alias using local server connection
from firebird.driver import driver_config
driver_config.server_defaults.host.value = 'localhost'
con = connect('employee', user='sysdba', password='masterkey')

# Set 'user' and 'password' via configuration
driver_config.server_defaults.user.value = 'SYSDBA'
driver_config.server_defaults.password.value = 'masterkey'
con = connect('employee')

```

However, it's recommended to use specific configuration for servers and databases.
It's possible to register servers and databases directly in code like this:

```python
from firebird.driver import connect, driver_config

# Register Firebird server
srv_cfg = """[local]
host = localhost
user = SYSDBA
password = masterkey
"""
driver_config.register_server('local', srv_cfg)

# Register database
db_cfg = """[employee]
server = local
database = employee.fdb
protocol = inet
charset = utf8
"""
driver_config.register_database('employee', db_cfg)

# Attach to 'employee' database
con = connect('employee')

```

But more convenient approach is using single configuration file:

```text
# file: myapp.cfg

[firebird.driver]
servers = local
databases = employee

[local]
host = localhost
user = SYSDBA
password = masterkey

[employee]
server = local
database = employee.fdb
protocol = inet
charset = utf8

```

```python
from firebird.driver import connect, driver_config

driver_config.read('myapp.cfg')

# Attach to 'employee' database
con = connect('employee')

```

!!! info
    [`connect()`](../ref-core.md#firebird.driver.core.connect) for details.


## Using create_database()

This constructor returns connection to newly created database. It works in the same way
as [`connect()`](../ref-core.md#firebird.driver.core.connect), but utilizes additional database configuration options.

It's possible to specify these options in code like this:

```python
from firebird.driver import connect, driver_config

# Register Firebird server
srv_cfg = """[local]
host = localhost
user = SYSDBA
password = masterkey
"""
driver_config.register_server('local', srv_cfg)

# Register database
db_cfg = """[mydb]
server = local
database = mydb.fdb
protocol = inet
charset = utf8
# create options
page_size = 16384
db_charset = utf8
sweep_interval = 80000
reserve_space = no
"""
driver_config.register_database('mydb', db_cfg)

# create 'mydb' database
con = create_database('mydb')

```

But more convenient approach is using single configuration file:

```text
# file: myapp.cfg

[firebird.driver]
servers = local
databases = mydb

[local]
host = localhost
user = SYSDBA
password = masterkey

[mydb]
server = local
database = mydb.fdb
protocol = inet
charset = utf8
# create options
page_size = 16384
db_charset = utf8
sweep_interval = 80000
reserve_space = no

```

```python
from firebird.driver import create_database, driver_config

driver_config.read('myapp.cfg')

# create 'mydb' database
con = create_database('mydb')

```

!!! info
    [`create_database()`](../ref-core.md#firebird.driver.core.create_database) for details.


## Deleting databases

The Firebird engine also supports dropping (deleting) databases dynamically,
but dropping is a more complicated operation than creating, for several reasons:
an existing database may be in use by users other than the one who requests
the deletion, it may have supporting objects such as temporary sort files, and
it may even have dependent shadow databases. Although the database engine
recognizes a `DROP DATABASE` SQL statement, support for that statement is limited
to the `isql` command-line administration utility. However, the engine supports
the deletion of databases via an API call, which `firebird-driver` exposes as
[`drop_database`](../ref-core.md#firebird.driver.core.Connection.drop_database) method in [`Connection`](../ref-core.md#firebird.driver.core.Connection) class. So, to drop a database
you need to connect to it first.

**Example:**

```python
from firebird.driver import connect, driver_config

driver_config.read('myapp.cfg')

# Attach to 'myapp' database
con = connect('myapp')
con.drop_database()

```

!!! info
    [`Connection.drop_database()`](../ref-core.md#firebird.driver.core.Connection.drop_database) for details.


## Connection object

[`Connection`](../ref-core.md#firebird.driver.core.Connection) object represents a direct link to database, and works as
gateway for next operations with it:

* [Executing SQL Statements](executing-sql-statements.md#executing-sql-statements): methods [`execute_immediate()`](../ref-core.md#firebird.driver.core.Connection.execute_immediate) and [`cursor()`](../ref-core.md#firebird.driver.core.Connection.cursor).
* [Dropping database](databases.md#deleting-databases): method [`drop_database()`](../ref-core.md#firebird.driver.core.Connection.drop_database).
* [Transactions](transactions.md#transactions): methods [`begin()`](../ref-core.md#firebird.driver.core.Connection.begin), [`commit()`](../ref-core.md#firebird.driver.core.Connection.commit),
    [`rollback()`](../ref-core.md#firebird.driver.core.Connection.rollback), [`savepoint()`](../ref-core.md#firebird.driver.core.Connection.savepoint), [`transaction_manager()`](../ref-core.md#firebird.driver.core.Connection.transaction_manager),
    [`is_active()`](../ref-core.md#firebird.driver.core.Connection.is_active), and attributes [`main_transaction`](../ref-core.md#firebird.driver.core.Connection.main_transaction),
    [`query_transaction`](../ref-core.md#firebird.driver.core.Connection.query_transaction), [`transactions`](../ref-core.md#firebird.driver.core.Connection.transactions) and [`default_tpb`](../ref-core.md#firebird.driver.core.Connection).
* Work with [Database Events](database-events.md#database-events): method [`event_collector`](../ref-core.md#firebird.driver.core.Connection.event_collector).
* [Getting information about connection](databases.md#getting-information-about-connection): methods [`is_closed()`](../ref-core.md#firebird.driver.core.Connection.is_closed) and
    [`ping()`](../ref-core.md#firebird.driver.core.Connection.ping) and attributes [`dsn`](../ref-core.md#firebird.driver.core.Connection.dsn), [`charset`](../ref-core.md#firebird.driver.core.Connection.charset)
    and [`sql_dialect`](../ref-core.md#firebird.driver.core.Connection.sql_dialect).
* [Getting information about database](databases.md#getting-information-about-database): attribute [`info`](../ref-core.md#firebird.driver.core.Connection.info).
* [Closing the connection](databases.md#closing-the-connection): method [`close()`](../ref-core.md#firebird.driver.core.Connection.close)


## Closing the connection

There are many local and server resources used by firebird-driver that must be properly
managed, and disposed when they are no longer necessary. All objects that require proper
finalization provide `close()` method that must be called when object is no longer needed.
The [`Connection`](../ref-core.md#firebird.driver.core.Connection) (and [`Server`](../ref-core.md#firebird.driver.core.Server)) objects are the most important ones, as other most frequently
used objects like cursors, prepared statements and transactions are typically associated with
connections.

You may call the `close()` method directly, or use the with statement
and context manager support provided by all these objects.

**Example:**

```python
from firebird.driver import connect, driver_config

driver_config.read('myapp.cfg')

with connect('employee') as con:
    cur = con.cursor()
    cur.execute('select 1 from rdb$database')
    print(cur.fetchone()[0])


```

!!! note

    Objects that require proper finalization are: [`Connection`](../ref-core.md#firebird.driver.core.Connection), [`TransactionManager`](../ref-core.md#firebird.driver.core.TransactionManager)
    and [`DistributedTransactionManager`](../ref-core.md#firebird.driver.core.DistributedTransactionManager), [`Statement`](../ref-core.md#firebird.driver.core.Statement), [`BlobReader`](../ref-core.md#firebird.driver.core.BlobReader), [`Cursor`](../ref-core.md#firebird.driver.core.Cursor) and [`Server`](../ref-core.md#firebird.driver.core.Server).

    Although only [`Connection`](../ref-core.md#firebird.driver.core.Connection) and [`Server`](../ref-core.md#firebird.driver.core.Server) objects must be closed directly because
    all other objects are associated with them and thus closed when connection is
    closed, it's **recommended** to directly close any resource object obtained by
    your code when it's no longer needed (either directly by calling `close()` or using
    `with` statement).

!!! important

    All managed objects have [`__del__`](https://docs.python.org/3/reference/datamodel.html#object.__del__) method, which ensures that the object in
    the active state is properly closed before it is destroyed by the Python memory manager.
    However, **the close operation may fail** as the state of your application could be arbitrary
    and the sequence in which objects are disposed by memory manager is not deterministic.

    The [`__del__`](https://docs.python.org/3/reference/datamodel.html#object.__del__) methods should be thus considered as safe guard of last resort
    that your code should not rely upon. To indicate that your code is not managing
    resources properly, the `ResourceWarning` is raises when active object is disposed
    by memory manager.

    !!! note

        Such warnings may not reach your attention if warnings are disabled or filtered
        on your system. You should always develop and test your applications with enabled
        delivery of resource warnings.

!!! info
    [`Connection.close()`](../ref-core.md#firebird.driver.core.Connection.close) for details.


## Getting information about connection

Only (most useful) part of information associated with [`Connection`](../ref-core.md#firebird.driver.core.Connection) object is directly
available:

* It's possible to check whether Connection object is closed or not with
    [`is_closed()`](../ref-core.md#firebird.driver.core.Connection.is_closed) method.
* It's possible to check whether connection to the Firebird server is not broken with
    [`ping()`](../ref-core.md#firebird.driver.core.Connection.ping) method.
* The DSN (fully qualified Firebird database connection string) is surfaced as [`dsn`](../ref-core.md#firebird.driver.core.Connection.dsn)
    read-only property.
* The character set used by Connection is surfaced as [`charset`](../ref-core.md#firebird.driver.core.Connection.charset) read-only property.
* The SQL dialect used by Connection is surfaced as [`sql_dialect`](../ref-core.md#firebird.driver.core.Connection.sql_dialect) read-only property.

!!! tip

    Additional connection-specific information is currently held as `bytes` in protected
    `Connection._dpb` attribute that could be processed using [`DPB`](../ref-core.md#firebird.driver.core.DPB) object.


## Getting information about database

!!! important

    Because the scope and type of database information depends on the version of the Firebird
    server and database ODS, this information is made available through a separate class
    [`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider). The [`Connection.info`](../ref-core.md#firebird.driver.core.Connection.info) property provides access to
    instance of [`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider) or it's **ancestor** class according to ODS of attached
    database and Firebird version.

Although you may query the information directly from server using
[`get_info()`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider3.get_info) method (that wraps the Firebird
[`iAttachment_v3.get_info()`](../ref-intf.md#firebird.driver.interfaces.iAttachment_v3.get_info) API call), the [`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider) object
provides more convenient methods and properties for obtaining specific information directly.

!!! note

    Some information provided by [`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider) properties
    (like [`cache_hit_ratio`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider3.cache_hit_ratio)) could not be obtained via
    `get_info()` method.

**Example:**

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    print(f"Database character set: {con.info.charset}")
    print(f"Page size (in bytes): {con.info.page_size}")
    print(f"Attachment ID: {con.info.id}")
    print(f"SQL dialect used by connected database: {con.info.sql_dialect}")
    print(f"Database name (filename or alias): {con.info.name}")
    print(f"Database site name: {con.info.site}")
    print(f"Implementation (old format): {con.info.implementation!s}")
    print(f"Database Provider: {con.info.provider!s}")
    print(f"Database Class: {con.info.db_class!s}")
    print(f"Date when database was created: {con.info.creation_date}")
    print(f"Size of page cache used by connection: {con.info.page_cache_size}")
    print(f"Number of pages allocated for database: {con.info.pages_allocated}")
    print(f"Number of database pages in active use: {con.info.pages_used}")
    print(f"Number of free allocated pages in database: {con.info.pages_free}")
    print(f"Sweep interval: {con.info.sweep_interval}")
    print(f"Data page space usage (USE_FULL or RESERVE): {con.info.space_reservation!s}")
    print(f"Database write mode (SYNC or ASYNC): {con.info.write_mode!s}")
    print(f"Database access mode (READ_ONLY or READ_WRITE): {con.info.access_mode!s}")
    print(f"Current I/O statistics - Reads from disk to page cache: {con.info.reads}")
    print(f"Current I/O statistics - Fetches from page cache: {con.info.fetches}")
    print(f"Cache hit ratio = 1 - (reads / fetches): {con.info.cache_hit_ratio}")
    print(f"Current I/O statistics - Writes from page cache to disk: {con.info.writes}")
    print(f"Current I/O statistics - Writes to page in cache: {con.info.marks}")
    print(f"Total amount of memory curretly used by database engine: {con.info.current_memory}")
    print(f"Max. total amount of memory so far used by database engine: {con.info.max_memory}")
    print(f"ID of Oldest Interesting Transaction: {con.info.oit}")
    print(f"ID of Oldest Active Transaction: {con.info.oat}")
    print(f"ID of Oldest Snapshot Transaction: {con.info.ost}")
    print(f"ID for next transaction: {con.info.next_transaction}")

```

**Sample output**:

```text
Database character set: NONE
Page size (in bytes): 8192
Attachment ID: 378
SQL dialect used by connected database: 3
Database name (filename or alias): /opt/firebird/examples/empbuild/employee.fdb
Database site name: NewAmarisk
Implementation (old format): Implementation.RDB_VMS
Database Provider: DbProvider.FIREBIRD
Database Class: DbClass.SERVER_ACCESS
Date when database was created: 2020-05-13 10:13:57.005010
Size of page cache used by connection: 2048
Number of pages allocated for database: 346
Number of database pages in active use: 311
Number of free allocated pages in database: 35
Sweep interval: 20000
Data page space usage (USE_FULL or RESERVE): DbSpaceReservation.RESERVE
Database write mode (SYNC or ASYNC): DbWriteMode.SYNC
Database access mode (READ_ONLY or READ_WRITE): DbAccessMode.READ_WRITE
Current I/O statistics - Reads from disk to page cache: 87
Current I/O statistics - Fetches from page cache: 1525
Cache hit ratio = 1 - (reads / fetches): 0.9429508196721311
Current I/O statistics - Writes from page cache to disk: 2
Current I/O statistics - Writes to page in cache: 5
Total amount of memory curretly used by database engine: 21925248
Max. total amount of memory so far used by database engine: 22033760
ID of Oldest Interesting Transaction: 307
ID of Oldest Active Transaction: 308
ID of Oldest Snapshot Transaction: 308
ID for next transaction: 308

```

!!! info
    [`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider) for details.

#### Getting information about Firebird version

Because functionality and some features depends on actual Firebird version, it could be
important for driver users to check it. This (otherwise) simple task could be confusing
for new Firebird users, because Firebird uses two different version lineages. This abomination
was introduced to Firebird thanks to its InterBase legacy (Firebird 1.0 is a fork of InterBase
6.0), as applications designed to work with InterBase can often work with Firebird without
problems (and vice versa).

[`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider) provides these version strings as two properties:

* [`server_version`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider.server_version) - Legacy InterBase-friendly version string.
* [`firebird_version`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider.firebird_version) - Firebird’s own version string.

However, this version string contains more information than version number. For example for
Linux Firebird 4.0.0 it’s ‘LI-T4.0.0.1963 Firebird 4.0 Beta 2’. So [`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider)
provides two more properties for your convenience:

* [`version`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider.version) - Only Firebird version number. It’s a string with
    format: major.minor.subrelease.build
* [`engine_version`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider.engine_version) - Engine (major.minor) version as (float) number.


**Example:**

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    print(f"server_version: '{con.info.server_version}'")
    print(f"firebird_version: '{con.info.firebird_version}'")
    print(f"version: '{con.info.version}'")
    print(f"engine_version: {con.info.engine_version}")

```

**Sample output**:

```text
server_version: 'LI-T6.3.0.1963 Firebird 4.0 Beta 2'
firebird_version: 'LI-T4.0.0.1963 Firebird 4.0 Beta 2'
version: '4.0.0.1963'
engine_version: 4.0

```
#### Database On-Disk Structure

Particular Firebird features may also depend on specific support in database
(for example number and structure of monitoring tables). These required structures are
present automatically when database is created by particular engine verison that needs
them, but Firebird engine may work with databases created by older versions and thus with
older structure, so it could be necessary to consult also On-Disk Structure (ODS for short)
version. [`DatabaseInfoProvider`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider) provides this number as [`ods`](../ref-core.md#firebird.driver.core.DatabaseInfoProvider.ods) (float)
property.

**Example:**

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    print(f"ods: {con.info.ods}")
    print(f"ods_version: {con.info.ods_version}")
    print(f"ods_minor_version: {con.info.ods_minor_version}")

```

**Sample output**:

```text
ods: 13.0
ods_version: 13
ods_minor_version: 0



```
