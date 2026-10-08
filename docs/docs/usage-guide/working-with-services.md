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
database server, represented by the `.Server` class. Similarly to database connections,
firebird-driver provides `.connect_server()` constructor function to create such connections.

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

    Like database connections, it's important to properly `~Server.close()` them
    when you don't need them anymore.

`.Server` object provides main infrastructure for communication with Firebird server services,
and manages number of objects that provide actual server services:

* The `.Server.info` property object provides [Server Configuration and State information](working-with-services.md#server-configuration-and-state-information).
* The `.Server.database` property object provides [Database options](working-with-services.md#database-options) and [Database maintenance](working-with-services.md#database-maintenance).
* The `.Server.user` property object provides [User maintenance](working-with-services.md#user-maintenance).
* The `.Server.trace` property object provides management of [Trace sessions](working-with-services.md#trace-sessions).

!!! info
    `.connect_server()` and `.Server` for details.


## Text output from Services

Some services like `.ServerDbServices.backup()` may return significant amount of text.
Rather than return the whole text as single string value by methods that provide access
to these services, firebird-driver isolated the transfer process to separate methods:

* `~.Server.readline()` - Similar to `file.readline`, returns next line of output from Service.
* `~.Server.readline_timed()` - Like `~.Server.readline()` but with timeout.
* `~.Server.readlines()` - Like `file.readlines`, returns list of output lines.
* Iteration over `.Server` object, because `.Server` has built-in support for [iterator protocol](https://docs.python.org/3/library/stdtypes.html#iterator-types).
* Using `callback` method provided by developer. Each `.Server` method that returns its result
    asynchronously accepts an optional parameter `callback`, which must be a function that accepts
    one string parameter. This method is then called with each output line coming from service.
* `~.Server.wait()` - Waits for Sevice to finish, ignoring rest of the output it may produce.

!!! important

    The Firebird server sends text output from services as packets, that could have two forms.
    The method for packet construction used for text transfer is controlled by `.Server.mode`
    attribute with next possible values:

    1. `.SrvInfoCode.LINE` : A single line of text.
    2. `.SrvInfoCode.TO_EOF` : A block of text up to specified (buffer) size.

    Both methods have specific pros and cons:

    1. `~.SrvInfoCode.LINE` means more roundtrips and thus slower transfer of service output,
        but each line is sent to client immediately when it's available.
    2. `~.SrvInfoCode.TO_EOF` means fewer roundtrips so large output is transferred quickly,
        but service output is not sent until the transfer buffer is not full, or service stops.

    **The default mode is** `~.SrvInfoCode.TO_EOF` **with 64K buffer.**

!!! warning

    Until output is not fully fetched from service, any attempt to start another asynchronous
    service will fail with exception! This constraint is set by Firebird Service API.

    You may check the status of asynchronous Services using `.Server.is_running()` method.

    In cases when you're not interested in output produced by Service, call `~.Server.wait()`
    to wait for service to complete.

!!! important

    Normally, requesting output with `~.Server.readline()` blocks until any output is
    available from server. Bacuse this method is used by iteration over `.Server` and
    `~.Server.readlines()` method, they will block as well. Most services produce output
    continuously and without (much) delay, so this is usually not a problem. However, some
    services (eg trace) can produce output at significantly slower intervals (if at all),
    which complicates the creation of responsive applications. In this case, it is necessary
    to use the `~.Server.readline_timed()` method, which allows you to limit the waiting
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
    `.ServerInfoProvider`. The `.Server.info` property provides access to
    instance of `.ServerInfoProvider` or it's **ancestor** class according to attached
    Firebird server version.

`.ServerInfoProvider` methods and properties:

* `~.ServerInfoProvider.get_log()` - Request the contents of the server’s log file (`firebird.log`).

    This method is so-called `Async service` that only initiates log transfer. Actual log
    content could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    `.Server` provides .

* `~.ServerInfoProvider.version` - Returns Firebird server version as SEMVER string.

* `~.ServerInfoProvider.engine_version` - Firebird server version as <major>.<minor> float value.

* `~.ServerInfoProvider.manager_version` - Firebird service manager version.

* `~.ServerInfoProvider.architecture` - Firebird server implementation description.

* `~.ServerInfoProvider.home_directory` - Firebird server home directory.

* `~.ServerInfoProvider.security_database` - Security database.

* `~.ServerInfoProvider.lock_directory` - Directory with lock file(s).

* `~.ServerInfoProvider.message_directory` - Directory with message file(s).

* `~.ServerInfoProvider.capabilities` - Firebird server capabilities (as `.ServerCapability` flags).

* `~.ServerInfoProvider.connection_count` - Current number of database attachments.

* `~.ServerInfoProvider.attached_databases` - List of attached databases.

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

Database options could be set using `.ServerDbServices` instance accessible via
`.Server.database` property.

* `~.ServerDbServices.set_default_cache_size()` - Sets individual page cache size for database.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_default_cache_size(database='employee.fdb', size=5000)

    ```

* `~.ServerDbServices.set_sweep_interval()` - Sets database sweep interval.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_sweep_interval(database='employee.fdb', interval=100000)

    ```

* `~.ServerDbServices.set_space_reservation()` - Sets space reservation option for database.

    ```python
    >>> from firebird.driver import connect_server, DbSpaceReservation
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_space_reservation(database='employee.fdb', mode=DbSpaceReservation.USE_FULL)

    ```

* `~.ServerDbServices.set_write_mode()` - Sets database write mode (SYNC/ASYNC).

    ```python
    >>> from firebird.driver import connect_server, DbWriteMode
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_write_mode(database='employee.fdb', mode=DbWriteMode.ASYNC)

    ```

* `~.ServerDbServices.set_access_mode()` - Sets database access mode (R/W or R/O).

    ```python
    >>> from firebird.driver import connect_server, DbAccessMode
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_access_mode(database='employee.fdb', mode=DbAccessMode.READ_ONLY)

    ```

* `~.ServerDbServices.set_sql_dialect()` - Sets database SQL dialect.

    !!! warning

        Changing SQL dialect on existing database is not recommended. Only newly created
        database objects would respect new dialect setting, while objects created with
        previous dialect remain unchanged. That may have dire consequences.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.set_sql_dialect(database='employee.fdb', dialect=1)

    ```

* `~.ServerDbServices.no_linger()` - Sets one-off override for database linger.

    ```python
    >>> from firebird.driver import connect_server
    >>> with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
    >>>     srv.database.no_linger(database='employee.fdb')

    ```


## Database maintenance

!!! important

    Because available database-related actions depends on the version of the Firebird
    server, they are made available through a separate class `.ServerDbServices`.
    The `.Server.database` property provides access to instance of `.ServerDbServices` or
    it's **ancestor** class according to attached Firebird server version.

* `~.ServerDbServices3.get_statistics()` - Returns database statistics produced by gstat
    utility.

    This method is so-called `Async service` that only initiates report processing. Actual
    report content could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    `.Server` provides .

    ```python
    from firebird.driver import connect_server, SrvStatFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.get_statistics(database='employee.fdb',
                                    flags=SrvStatFlag.DATA_PAGES | SrvStatFlag.RECORD_VERSIONS),
                                    tables=['EMPLOYEE','PROJECT'])
        stats = srv.readlines()

    ```

* `~.ServerDbServices3.backup()` - Performs logical (GBAK) database backup.

    This method is so-called `Async service` that only initiates the backup process. Output
    from gbak could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    `.Server` provides .

    ```python
    from firebird.driver import connect_server, SrvBackupFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.backup(database='employee.fdb',
                            backup='/backup/employee.fbk',
                            flags=SrvBackupFlag.IGNORE_CHECKSUMS | SrvBackupFlag.NO_GARBAGE_COLLECT,
                            stats='TD', verbose=True)
        report = srv.readlines()

    ```

* `~.ServerDbServices3.local_backup()` - Performs logical (GBAK) database backup into local byte
    stream.

    ```python
    from firebird.driver import connect_server, SrvBackupFlag
    f = open('/backup/employee.fbk',mode='wb')
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.local_backup(database='employee.fdb', backup_stream=f,
                                  flags=SrvBackupFlag.IGNORE_CHECKSUMS | SrvBackupFlag.NO_GARBAGE_COLLECT)
    f.close()

    ```

* `~.ServerDbServices3.restore()` - Performs database restore from logical (GBAK) backup.

    This method is so-called `Async service` that only initiates the restore process. Output
    from gbak could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    `.Server` provides .

    ```python
    from firebird.driver import connect_server, SrvRestoreFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.restore(backup='/backup/employee.fbk',
                             database='/data/employee.fdb',
                             flags=SrvRestoreFlag.REPLACE,
                             stats='TD', verbose=True, page_size=8192)
        report = srv.readlines()

    ```

* `~.ServerDbServices3.local_restore()` - Performs database restore from logical (GBAK) backup
    stored in local byte stream.

    ```python
    from firebird.driver import connect_server, SrvRestoreFlag
    f = open('/backup/employee.fbk',mode='rb')
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.local_restore(backup_stream=f, database='/data/employee.fdb',
                                   flags=SrvRestoreFlag.REPLACE, page_size=8192)
    f.close()

    ```

* `~.ServerDbServices3.nbackup()` - Performs physical (NBACKUP) database backup.

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.nbackup(database='employee.fdb', backup='/backup/employee.bkp1', level=1)

    ```

* `~.ServerDbServices3.nrestore()` - Performs restore from physical (NBACKUP) database
    backup.

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.nrestore(backups=['/backup/employee.bkp0', '/backup/employee.bkp1'],
                              database='/data/employee.fdb')

    ```

* `~.ServerDbServices3.shutdown()` - Database shutdown.

    ```python
    from firebird.driver import connect_server, ShutdownMode, ShutdownMethod
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.shutdown(database='employee.fdb', mode=ShutdownMode.SINGLE,
                              method=ShutdownMethod.FORCED, timeout=10)

    ```

* `~.ServerDbServices3.bring_online()` - Bring previously shut down database back online.

    ```python
    from firebird.driver import connect_server, OnlineMode
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.bring_online(database='employee.fdb', mode=OnlineMode.MULTI)

    ```

* `~.ServerDbServices3.sweep()` - Performs database sweep operation.

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.sweep(database='employee.fdb')

    ```

* `~.ServerDbServices3.validate()` - Performs database validation.

    This method is so-called `Async service` that only initiates the validation process. Output
    from validation could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services) that
    `.Server` provides .

    ```python
    from firebird.driver import connect_server
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.validate(database='employee.fdb')
        report = srv.readlines()

    ```

* `~.ServerDbServices3.repair()` - Performs database repair operation.

    ```python
    from firebird.driver import connect_server, SrvRepairFlag
    with connect_server('localhost', user='SYSDBA', password='masterkey') as srv:
        srv.database.repair(database='employee.fdb',
                            flags=SrvRepairFlag.REPAIR | SrvRepairFlag.KILL_SHADOWS)

    ```

* `~.ServerDbServices3.get_limbo_transaction_ids()` - Returns list of transactions in limbo.

* `~.ServerDbServices3.commit_limbo_transaction()` - Resolves limbo transaction with commit.

* `~.ServerDbServices3.rollback_limbo_transaction()` - Resolves limbo transaction with rollback.

* `~.ServerDbServices.nfix_database` - Fixup database after filesystem copy.

* `~.ServerDbServices.set_replica_mode` - Manage replica database.


## User maintenance

!!! important

    Because user maintenance functionality may depend on the version of the Firebird
    server, this functionality is made available through a separate class
    `.ServerUserServices`. The `.Server.user` property provides access to
    instance of `.ServerUserServices` or it's **ancestor** class according to attached
    Firebird server version.

!!! tip

    Since Firebird 2.5 you can use SQL commands (CREATE/ALTER/DROP USER) to manage users in
    a security database from a regular database attachment.

    The SQL set of DDL commands for managing user accounts has been further enhanced in Firebird 3,
    thus improving the DDL capabilities in a way that exceeds capabilities of user management services.

* `~.ServerUserServices.get_all()` - Returns information about all users.

* `~.ServerUserServices.get()` - Returns information about specified users.

* `~.ServerUserServices.add()` - Add new user.

* `~.ServerUserServices.update()` - Update user information.

* `~.ServerUserServices.delete()` - Delete user.

* `~.ServerUserServices.exists()` - Returns True if user exists.


## Trace sessions

!!! important

    Because trace functionality may depend on the version of the Firebird server, this
    functionality is made available through a separate class `.ServerTraceServices`.
    The `.Server.trace` property provides access to instance of `.ServerTraceServices` or
    its **ancestor** class according to attached Firebird server version.

* `.ServerTraceServices.start()` - Start new trace session. Requires trace `configuration` and returns `Session ID`.

    This method is so-called `Async service` that only starts the trace session. Output
    from trace session could be read by one from many methods for [text output from Services](working-with-services.md#text-output-from-services)
    that `.Server` provides .

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

* `.ServerTraceServices.stop()` - Stop trace session.

* `.ServerTraceServices.suspend()` - Suspend trace session.

* `.ServerTraceServices.resume()` - Resume trace session.

* `.ServerTraceServices.sessions` - Dictionary with active trace sessions. The key is session ID, value is `.TraceSession` instance.
