<a id="working_with_services"></a>

# Working with Services

Database server maintenance tasks such as user management, load monitoring,
and database backup have traditionally been automated by scripting the
command-line tools `gbak`, `gfix`, `gsec`, and `gstat`.

The API presented to the client programmer by these utilities is inelegant
because they are, after all, command-line tools rather than native components
of the client language. To address this problem, Firebird has a facility called
the `Services API`, which exposes a uniform interface to the administrative
functionality of the traditional command-line tools.

The native Services API, though consistent, is much lower-level than a Pythonic API.
If the native version were exposed directly, accomplishing a given task would probably
require more Python code than scripting the traditional command-line tools. For this
reason, the firebird-driver presents its own abstraction over the native API.


## Services API Connections

All Services API operations are performed in the context of a `connection` to a specific
database server, represented by the [`Server`](../ref-core.md#firebird.driver.core.Server) class. Similarly to database connections,
firebird-driver provides [`connect_server()`](../ref-core.md#firebird.driver.core.connect_server) constructor function to create such connections.

This constructor has one positional and several keyword parameters.

The value of `server` positional parameter must be one of:

* name of registered server configuration
* server host name or address

Keyword parameters are intended to override selected configuration options, or to specify
options that are not configurable.

A simple server connection is typically established with code such as this:

```python
from firebird.driver import connect_server

# Attach to 'embedded' server
srv = connect_server('', user='SYSDBA', password='masterkey')

# Attach to 'local' server
srv = connect_server('localhost', user='SYSDBA', password='masterkey')

# Set 'user' and 'password' via configuration
from firebird.driver import driver_config
driver_config.server_defaults.user.value = 'SYSDBA'
driver_config.server_defaults.password.value = 'masterkey'
srv = connect_server('localhost')

```

However, it's recommended to use specific configuration for servers.
It's possible to register servers directly in code like this:

```python
from firebird.driver import connect_server, driver_config

# Register Firebird server
srv_cfg = """[main_server]
host = 192.168.0.15
user = SYSDBA
password = Xyzzy
"""
driver_config.register_server('main_server', srv_cfg)

# Attach to 'main' server
con = connect('main_server')

```

But more convenient approach is using single configuration file:

```text
# file: myapp.cfg

[firebird.driver]
servers = main_server
databases = employee

[main_server]
host = 192.168.0.15
user = SYSDBA
password = Xyzzy

```

```python
from firebird.driver import connect_server, driver_config

driver_config.read('myapp.cfg')

# Attach to 'main' server
con = connect('main_server')

```

!!! note

    Like database connections, it's important to properly [`close()`](../ref-core.md#firebird.driver.core.Server.close) them
    when you don't need them anymore.

[`Server`](../ref-core.md#firebird.driver.core.Server) object provides main infrastructure for communication with Firebird server services,
and manages number of objects that provide actual server services:

* The [`Server.info`](../ref-core.md#firebird.driver.core.Server.info) property object provides [Server Configuration and State information](working-with-services.md#server-configuration-and-state-information).
* The [`Server.database`](../ref-core.md#firebird.driver.core.Server.database) property object provides [Database options](working-with-services.md#database-options) and [Database maintenance](working-with-services.md#database-maintenance).
* The [`Server.user`](../ref-core.md#firebird.driver.core.Server.user) property object provides [User maintenance](working-with-services.md#user-maintenance).
* The [`Server.trace`](../ref-core.md#firebird.driver.core.Server.trace) property object provides management of [Trace sessions](working-with-services.md#trace-sessions).

!!! info
    [`connect_server()`](../ref-core.md#firebird.driver.core.connect_server) and [`Server`](../ref-core.md#firebird.driver.core.Server) for details.


## Text output from Services

Some services like [`ServerDbServices.backup()`](../ref-core.md#firebird.driver.core.ServerDbServices.backup) may return significant amount of text.
Rather than return the whole text as single string value by methods that provide access
to these services, firebird-driver isolated the transfer process to separate methods:

* [`readline()`](../ref-core.md#firebird.driver.core.Server.readline) - Similar to `file.readline`, returns next line of output from Service.
* [`readline_timed()`](../ref-core.md#firebird.driver.core.Server.readline_timed) - Like [`readline()`](../ref-core.md#firebird.driver.core.Server.readline) but with timeout.
* [`readlines()`](../ref-core.md#firebird.driver.core.Server.readlines) - Like `file.readlines`, returns list of output lines.
* Iteration over [`Server`](../ref-core.md#firebird.driver.core.Server) object, because [`Server`](../ref-core.md#firebird.driver.core.Server) has built-in support for [iterator protocol](https://docs.python.org/3/library/stdtypes.html#iterator-types).
* Using `callback` method provided by developer. Each [`Server`](../ref-core.md#firebird.driver.core.Server) method that returns its result
    asynchronously accepts an optional parameter `callback`, which must be a function that accepts
    one string parameter. This method is then called with each output line coming from service.
* [`wait()`](../ref-core.md#firebird.driver.core.Server.wait) - Waits for Sevice to finish, ignoring rest of the output it may produce.

!!! important

    The Firebird server sends text output from services as packets, that could have two forms.
    The method for packet construction used for text transfer is controlled by [`Server.mode`](../ref-core.md#firebird.driver.core.Server)
    attribute with next possible values:

    1. [`SrvInfoCode.LINE`](../ref-types.md#firebird.driver.types.SrvInfoCode) : A single line of text.
    2. [`SrvInfoCode.TO_EOF`](../ref-types.md#firebird.driver.types.SrvInfoCode) : A block of text up to specified (buffer) size.

    Both methods have specific pros and cons:

    1. [`LINE`](../ref-types.md#firebird.driver.types.SrvInfoCode) means more roundtrips and thus slower transfer of service output,
        but each line is sent to client immediately when it's available.
    2. [`TO_EOF`](../ref-types.md#firebird.driver.types.SrvInfoCode) means fewer roundtrips so large output is transferred quickly,
        but service output is not sent until the transfer buffer is not full, or service stops.

    **The default mode is** [`TO_EOF`](../ref-types.md#firebird.driver.types.SrvInfoCode) **with 64K buffer.**

!!! warning

    Until output is not fully fetched from service, any attempt to start another asynchronous
    service will fail with exception! This constraint is set by Firebird Service API.

    You may check the status of asynchronous Services using [`Server.is_running()`](../ref-core.md#firebird.driver.core.Server.is_running) method.

    In cases when you're not interested in output produced by Service, call [`wait()`](../ref-core.md#firebird.driver.core.Server.wait)
    to wait for service to complete.

!!! important

    Normally, requesting output with [`readline()`](../ref-core.md#firebird.driver.core.Server.readline) blocks until any output is
    available from server. Bacuse this method is used by iteration over [`Server`](../ref-core.md#firebird.driver.core.Server) and
    [`readlines()`](../ref-core.md#firebird.driver.core.Server.readlines) method, they will block as well. Most services produce output
    continuously and without (much) delay, so this is usually not a problem. However, some
    services (eg trace) can produce output at significantly slower intervals (if at all),
    which complicates the creation of responsive applications. In this case, it is necessary
    to use the [`readline_timed()`](../ref-core.md#firebird.driver.core.Server.readline_timed) method, which allows you to limit the waiting
    time for the output.

**Examples:**

```python
from firebird.driver import connect_server
with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    print("Fetch materialized")
    print("==================")
    print("Start backup")
    srv.database.backup(database='employee', backup='employee.fbk')
    print("srv.running is", srv.isrunning())
    report = srv.readlines()
    print(f"{len(report)} lines returned")
    print("First 5 lines from output:")
    for i in xrange(5):
        print(i,report[i])
    print("srv.running is", srv.isrunning())
    print()
    print("Iterate over result")
    print("===================")
    srv.database.backup(database='employee', backup='employee.fbk')
    output = []
    for line in srv:
        output.append(line)
    print(f"{len(output)} lines returned")
    print("Last 5 lines from output:")
    for line in output[-5:]:
        print(line)
    print()
    print("Callback")
    print("========")

    output = []

    # Callback function
    def fetchline(line):
        output.append(line)

    srv.database.backup(database='employee', backup='employee.fbk', callback=fetchline)
    print(f"{len(output)} lines returned")
    print("Last 5 lines from output:")
    for line in output[-5:]:
        print(line)

```

Output:

```text
Fetch materialized
==================
Start backup
svc.running is True
558 lines returned
First 5 lines from output:
0 gbak:readied database employee for backup
1 gbak:creating file employee.fbk
2 gbak:starting transaction
3 gbak:database employee has a page size of 4096 bytes.
4 gbak:writing domains
svc.running is False

Iterate over result
===================
558 lines returned
Last 5 lines from output:
gbak:writing referential constraints
gbak:writing check constraints
gbak:writing SQL roles
gbak:writing names mapping
gbak:closing file, committing, and finishing. 74752 bytes written

Callback
========
558 lines returned
Last 5 lines from output:
gbak:writing referential constraints
gbak:writing check constraints
gbak:writing SQL roles
gbak:writing names mapping
gbak:closing file, committing, and finishing. 74752 bytes written

```

## Server Configuration and State information

!!! important

    Because the scope and type of service information depends on the version of the Firebird
    server, this information is made available through a separate class
    [`ServerInfoProvider`](../ref-core.md#firebird.driver.core.ServerInfoProvider). The [`Server.info`](../ref-core.md#firebird.driver.core.Server.info) property provides access to
    instance of [`ServerInfoProvider`](../ref-core.md#firebird.driver.core.ServerInfoProvider) or it's **ancestor** class according to attached
    Firebird server version.

[`ServerInfoProvider`](../ref-core.md#firebird.driver.core.ServerInfoProvider) methods and properties:

* [`get_log()`](../ref-core.md#firebird.driver.core.ServerInfoProvider.get_log) - Request the contents of the server’s log file (`firebird.log`).

    This method is so-called `Async service` that only initiates log transfer. Actual log
    content could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    [`Server`](../ref-core.md#firebird.driver.core.Server) provides .

* [`version`](../ref-core.md#firebird.driver.core.ServerInfoProvider.version) - Returns Firebird server version as SEMVER string.

* [`engine_version`](../ref-core.md#firebird.driver.core.ServerInfoProvider.engine_version) - Firebird server version as <major>.<minor> float value.

* [`manager_version`](../ref-core.md#firebird.driver.core.ServerInfoProvider.manager_version) - Firebird service manager version.

* [`architecture`](../ref-core.md#firebird.driver.core.ServerInfoProvider.architecture) - Firebird server implementation description.

* [`home_directory`](../ref-core.md#firebird.driver.core.ServerInfoProvider.home_directory) - Firebird server home directory.

* [`security_database`](../ref-core.md#firebird.driver.core.ServerInfoProvider.security_database) - Security database.

* [`lock_directory`](../ref-core.md#firebird.driver.core.ServerInfoProvider.lock_directory) - Directory with lock file(s).

* [`message_directory`](../ref-core.md#firebird.driver.core.ServerInfoProvider.message_directory) - Directory with message file(s).

* [`capabilities`](../ref-core.md#firebird.driver.core.ServerInfoProvider.capabilities) - Firebird server capabilities (as [`ServerCapability`](../ref-types.md#firebird.driver.types.ServerCapability) flags).

* [`connection_count`](../ref-core.md#firebird.driver.core.ServerInfoProvider.connection_count) - Current number of database attachments.

* [`attached_databases`](../ref-core.md#firebird.driver.core.ServerInfoProvider.attached_databases) - List of attached databases.

**Example:**

```python
from firebird.driver import driver_config, connect, connect_server

srv_cfg = """[local]
host = localhost
user = SYSDBA
password = masterkey
"""
driver_config.register_server('local', srv_cfg)
db_cfg = """[employee]
server = local
database = employee.fdb
protocol = inet
"""
driver_config.register_database('employee', db_cfg)
with connect('employee', user='SYSDBA', password='masterkey'), connect_server('local', user='SYSDBA', password='masterkey') as srv:
    print(f'{srv.info.version=}')
    print(f'{srv.info.engine_version=}')
    print(f'{srv.info.manager_version=}')
    print(f'{srv.info.architecture=}')
    print(f'{srv.info.home_directory=}')
    print(f'{srv.info.security_database=}')
    print(f'{srv.info.lock_directory=}')
    print(f'{srv.info.message_directory=}')
    print(f'{srv.info.capabilities=!s}')
    print(f'{srv.info.connection_count=}')
    print(f'{srv.info.attached_databases=}')

```

Sample output for 64-bit Linux Firebird 4.0 Beta 2:

```text
srv.info.version='4.0.0.1963'
srv.info.engine_version=4.0
srv.info.manager_version=2
srv.info.architecture='Firebird/Linux/AMD/Intel/x64'
srv.info.home_directory='/opt/firebird/'
srv.info.security_database='/opt/firebird/security4.fdb'
srv.info.lock_directory='/tmp/firebird/'
srv.info.message_directory='/opt/firebird/'
srv.info.capabilities=ServerCapability.REMOTE_HOP|MULTI_CLIENT
srv.info.connection_count=1
srv.info.attached_databases=['/opt/firebird/examples/empbuild/employee.fdb']

```

## Database options

Database options could be set using [`ServerDbServices`](../ref-core.md#firebird.driver.core.ServerDbServices) instance accessible via
[`Server.database`](../ref-core.md#firebird.driver.core.Server.database) property.

* [`set_default_cache_size()`](../ref-core.md#firebird.driver.core.ServerDbServices.set_default_cache_size) - Sets individual page cache size for database.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_default_cache_size(database='employee.fdb', size=5000)

    ```

* [`set_sweep_interval()`](../ref-core.md#firebird.driver.core.ServerDbServices.set_sweep_interval) - Sets database sweep interval.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_sweep_interval(database='employee.fdb', interval=100000)

    ```

* [`set_space_reservation()`](../ref-core.md#firebird.driver.core.ServerDbServices.set_space_reservation) - Sets space reservation option for database.

    ```python
    >>> from firebird.driver import connect_server, DbSpaceReservation
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_space_reservation(database='employee.fdb', mode=DbSpaceReservation.USE_FULL)

    ```

* [`set_write_mode()`](../ref-core.md#firebird.driver.core.ServerDbServices.set_write_mode) - Sets database write mode (SYNC/ASYNC).

    ```python
    >>> from firebird.driver import connect_server, DbWriteMode
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_write_mode(database='employee.fdb', mode=DbWriteMode.ASYNC)

    ```

* [`set_access_mode()`](../ref-core.md#firebird.driver.core.ServerDbServices.set_access_mode) - Sets database access mode (R/W or R/O).

    ```python
    >>> from firebird.driver import connect_server, DbAccessMode
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_access_mode(database='employee.fdb', mode=DbAccessMode.READ_ONLY)

    ```

* [`set_sql_dialect()`](../ref-core.md#firebird.driver.core.ServerDbServices.set_sql_dialect) - Sets database SQL dialect.

    !!! warning

        Changing SQL dialect on existing database is not recommended. Only newly created
        database objects would respect new dialect setting, while objects created with
        previous dialect remain unchanged. That may have dire consequences.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_sql_dialect(database='employee.fdb', dialect=1)

    ```

* [`no_linger()`](../ref-core.md#firebird.driver.core.ServerDbServices.no_linger) - Sets one-off override for database linger.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.no_linger(database='employee.fdb')

    ```


## Database maintenance

!!! important

    Because available database-related actions depends on the version of the Firebird
    server, they are made available through a separate class [`ServerDbServices`](../ref-core.md#firebird.driver.core.ServerDbServices).
    The [`Server.database`](../ref-core.md#firebird.driver.core.Server.database) property provides access to instance of [`ServerDbServices`](../ref-core.md#firebird.driver.core.ServerDbServices) or
    it's **ancestor** class according to attached Firebird server version.

* [`get_statistics()`](../ref-core.md#firebird.driver.core.ServerDbServices3.get_statistics) - Returns database statistics produced by gstat
    utility.

    This method is so-called `Async service` that only initiates report processing. Actual
    report content could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    [`Server`](../ref-core.md#firebird.driver.core.Server) provides .

    ```python
    from firebird.driver import connect_server, SrvStatFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.get_statistics(database='employee.fdb',
                                    flags=SrvStatFlag.DATA_PAGES | SrvStatFlag.RECORD_VERSIONS),
                                    tables=['EMPLOYEE','PROJECT'])
        stats = srv.readlines()

    ```

* [`backup()`](../ref-core.md#firebird.driver.core.ServerDbServices3.backup) - Performs logical (GBAK) database backup.

    This method is so-called `Async service` that only initiates the backup process. Output
    from gbak could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    [`Server`](../ref-core.md#firebird.driver.core.Server) provides .

    ```python
    from firebird.driver import connect_server, SrvBackupFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.backup(database='employee.fdb',
                            backup='/backup/employee.fbk',
                            flags=SrvBackupFlag.IGNORE_CHECKSUMS | SrvBackupFlag.NO_GARBAGE_COLLECT,
                            stats='TD', verbose=True)
        report = srv.readlines()

    ```

* [`local_backup()`](../ref-core.md#firebird.driver.core.ServerDbServices3.local_backup) - Performs logical (GBAK) database backup into local byte
    stream.

    ```python
    from firebird.driver import connect_server, SrvBackupFlag
    f = open('/backup/employee.fbk',mode='wb')
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.local_backup(database='employee.fdb', backup_stream=f,
                                  flags=SrvBackupFlag.IGNORE_CHECKSUMS | SrvBackupFlag.NO_GARBAGE_COLLECT)
    f.close()

    ```

* [`restore()`](../ref-core.md#firebird.driver.core.ServerDbServices3.restore) - Performs database restore from logical (GBAK) backup.

    This method is so-called `Async service` that only initiates the restore process. Output
    from gbak could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    [`Server`](../ref-core.md#firebird.driver.core.Server) provides .

    ```python
    from firebird.driver import connect_server, SrvRestoreFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.restore(backup='/backup/employee.fbk',
                             database='/data/employee.fdb',
                             flags=SrvRestoreFlag.REPLACE,
                             stats='TD', verbose=True, page_size=8192)
        report = srv.readlines()

    ```

* [`local_restore()`](../ref-core.md#firebird.driver.core.ServerDbServices3.local_restore) - Performs database restore from logical (GBAK) backup
    stored in local byte stream.

    ```python
    from firebird.driver import connect_server, SrvRestoreFlag
    f = open('/backup/employee.fbk',mode='rb')
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.local_restore(backup_stream=f, database='/data/employee.fdb',
                                   flags=SrvRestoreFlag.REPLACE, page_size=8192)
    f.close()

    ```

* [`nbackup()`](../ref-core.md#firebird.driver.core.ServerDbServices3.nbackup) - Performs physical (NBACKUP) database backup.

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.nbackup(database='employee.fdb', backup='/backup/employee.bkp1', level=1)

    ```

* [`nrestore()`](../ref-core.md#firebird.driver.core.ServerDbServices3.nrestore) - Performs restore from physical (NBACKUP) database
    backup.

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.nrestore(backups=['/backup/employee.bkp0', '/backup/employee.bkp1'],
                              database='/data/employee.fdb')

    ```

* [`shutdown()`](../ref-core.md#firebird.driver.core.ServerDbServices3.shutdown) - Database shutdown.

    ```python
    from firebird.driver import connect_server, ShutdownMode, ShutdownMethod
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.shutdown(database='employee.fdb', mode=ShutdownMode.SINGLE,
                              method=ShutdownMethod.FORCED, timeout=10)

    ```

* [`bring_online()`](../ref-core.md#firebird.driver.core.ServerDbServices3.bring_online) - Bring previously shut down database back online.

    ```python
    from firebird.driver import connect_server, OnlineMode
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.bring_online(database='employee.fdb', mode=OnlineMode.MULTI)

    ```

* [`sweep()`](../ref-core.md#firebird.driver.core.ServerDbServices3.sweep) - Performs database sweep operation.

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.sweep(database='employee.fdb')

    ```

* [`validate()`](../ref-core.md#firebird.driver.core.ServerDbServices3.validate) - Performs database validation.

    This method is so-called `Async service` that only initiates the validation process. Output
    from validation could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    [`Server`](../ref-core.md#firebird.driver.core.Server) provides .

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.validate(database='employee.fdb')
        report = srv.readlines()

    ```

* [`repair()`](../ref-core.md#firebird.driver.core.ServerDbServices3.repair) - Performs database repair operation.

    ```python
    from firebird.driver import connect_server, SrvRepairFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.repair(database='employee.fdb',
                            flags=SrvRepairFlag.REPAIR | SrvRepairFlag.KILL_SHADOWS)

    ```

* [`get_limbo_transaction_ids()`](../ref-core.md#firebird.driver.core.ServerDbServices3.get_limbo_transaction_ids) - Returns list of transactions in limbo.

* [`commit_limbo_transaction()`](../ref-core.md#firebird.driver.core.ServerDbServices3.commit_limbo_transaction) - Resolves limbo transaction with commit.

* [`rollback_limbo_transaction()`](../ref-core.md#firebird.driver.core.ServerDbServices3.rollback_limbo_transaction) - Resolves limbo transaction with rollback.

* [`nfix_database`](../ref-core.md#firebird.driver.core.ServerDbServices.nfix_database) - Fixup database after filesystem copy.

* [`set_replica_mode`](../ref-core.md#firebird.driver.core.ServerDbServices.set_replica_mode) - Manage replica database.


## User maintenance

!!! important

    Because user maintenance functionality may depend on the version of the Firebird
    server, this functionality is made available through a separate class
    [`ServerUserServices`](../ref-core.md#firebird.driver.core.ServerUserServices). The [`Server.user`](../ref-core.md#firebird.driver.core.Server.user) property provides access to
    instance of [`ServerUserServices`](../ref-core.md#firebird.driver.core.ServerUserServices) or it's **ancestor** class according to attached
    Firebird server version.

!!! tip

    Since Firebird 2.5 you can use SQL commands (CREATE/ALTER/DROP USER) to manage users in
    a security database from a regular database attachment.

    The SQL set of DDL commands for managing user accounts has been further enhanced in Firebird 3,
    thus improving the DDL capabilities in a way that exceeds capabilities of user management services.

* [`get_all()`](../ref-core.md#firebird.driver.core.ServerUserServices.get_all) - Returns information about all users.

* [`get()`](../ref-core.md#firebird.driver.core.ServerUserServices.get) - Returns information about specified users.

* [`add()`](../ref-core.md#firebird.driver.core.ServerUserServices.add) - Add new user.

* [`update()`](../ref-core.md#firebird.driver.core.ServerUserServices.update) - Update user information.

* [`delete()`](../ref-core.md#firebird.driver.core.ServerUserServices.delete) - Delete user.

* [`exists()`](../ref-core.md#firebird.driver.core.ServerUserServices.exists) - Returns True if user exists.


## Trace sessions

!!! important

    Because trace functionality may depend on the version of the Firebird server, this
    functionality is made available through a separate class [`ServerTraceServices`](../ref-core.md#firebird.driver.core.ServerTraceServices).
    The [`Server.trace`](../ref-core.md#firebird.driver.core.Server.trace) property provides access to instance of [`ServerTraceServices`](../ref-core.md#firebird.driver.core.ServerTraceServices) or
    its **ancestor** class according to attached Firebird server version.

* [`ServerTraceServices.start()`](../ref-core.md#firebird.driver.core.ServerTraceServices.start) - Start new trace session. Requires trace `configuration` and returns `Session ID`.

    This method is so-called `Async service` that only starts the trace session. Output
    from trace session could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services)
    that [`Server`](../ref-core.md#firebird.driver.core.Server) provides .

    ```python
    from firebird.driver import connect_server

    trace_config = """database = %[\\/]employee.fdb
    {
        enabled = true
        log_statement_finish = true
        print_plan = true
        include_filter = %%SELECT%%
        exclude_filter = %%RDB$%%
        time_threshold = 0
        max_sql_length = 2048
    }
    """

    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        trace_id = srv.trace.start(trace_config,'test_trace_1')
        trace_log = []
        # Get first 10 lines of trace output
        for i in range(10):
            trace_log.append(srv.readline())
        # Stop trace session
        # Because trace session blocks the connection, we need another one to stop trace session!
        with connect_server('localhost', user='SYSDBA', password='masterkey') as srv_aux:
            srv_aux.trace.stop(trace_id)

    ```

* [`ServerTraceServices.stop()`](../ref-core.md#firebird.driver.core.ServerTraceServices.stop) - Stop trace session.

* [`ServerTraceServices.suspend()`](../ref-core.md#firebird.driver.core.ServerTraceServices.suspend) - Suspend trace session.

* [`ServerTraceServices.resume()`](../ref-core.md#firebird.driver.core.ServerTraceServices.resume) - Resume trace session.

* [`ServerTraceServices.sessions`](../ref-core.md#firebird.driver.core.ServerTraceServices.sessions) - Dictionary with active trace sessions. The key is session ID, value is [`TraceSession`](../ref-types.md#firebird.driver.types.TraceSession) instance.
