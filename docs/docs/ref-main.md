# Main driver namespace


## Constants

::: firebird.driver.__VERSION__

## Imports from sub-modules

### config

Classes:  `DatabaseConfig`, `DriverConfig`, and `ServerConfig`.

Globals: `driver_config`

### core


Functions:
    `connect()`, `create_database()`, `connect_server()`, `temp_database()`, `transaction()` and `tpb()`

Translation dictionaries:
    `CHARSET_MAP`

Sentinels:
    `TIMEOUT`

Classes:
    `Connection`, `Cursor`, `Server`, `Statement`, `TransactionManager`, `DistributedTransactionManager` and `TPB`

### types


Exceptions:
    `FirebirdWarning`, `Error`, `InterfaceError`, `DatabaseError`, `DataError`,
    `OperationalError`, `IntegrityError`, `InternalError`, `ProgrammingError`
    and `NotSupportedError`

Enums:
    `NetProtocol`, `DirectoryCode`, `PageSize`, `DBKeyScope`, `DbInfoCode`, `Features`,
    `TraInfoCode`, `ReplicaMode`, `StmtInfoCode`, `ResultSetInfoCode`, `SrvInfoCode`, `TraInfoIsolation`,
    `TraInfoReadCommitted`, `TraInfoAccess`, `TraIsolation`, `TraReadCommitted`,
    `TraLockResolution`, `TraAccessMode`, `TableShareMode`, `TableAccessMode`, `Isolation`,
    `DefaultAction`, `StatementType`, `BlobType`, `DbAccessMode`, `DbSpaceReservation`,
    `DbWriteMode`, `ShutdownMode`, `OnlineMode`, `ShutdownMethod`, `CancelType`,
    `DecfloatRound` and `DecfloatTraps`

Flags:
    `ServerCapability`, `SrvRepairFlag`, `SrvStatFlag`, `SrvBackupFlag`,
    `SrvRestoreFlag`, `SrvNBackupFlag`, `ConnectionFlag` and `EncryptionFlag`

Globals and other objects required by Python DB API 2.0:
    `apilevel`, `threadsafety`, `paramstyle`, `Date`, `Time`, `Timestamp`,
    `DateFromTicks`, `TimeFromTicks`, `TimestampFromTicks`, `STRING`, `BINARY`,
    `NUMBER`, `DATETIME` and `ROWID`

Helper constants:
    `DESCRIPTION_NAME`, `DESCRIPTION_TYPE_CODE`, `DESCRIPTION_DISPLAY_SIZE`,
    `DESCRIPTION_INTERNAL_SIZE`, `DESCRIPTION_PRECISION`, `DESCRIPTION_SCALE`
    and `DESCRIPTION_NULL_OK`

Helper functions:
    `get_timezone()`

### fbapi


Functions `load_api()` and `get_api()`.
