
# firebird.driver.types

## Exceptions

Next exceptions are required by Python DB API 2.0

`Error` is imported from `firebird.base.types`.

::: firebird.driver.types.Error

::: firebird.driver.types.InterfaceError

::: firebird.driver.types.DatabaseError

::: firebird.driver.types.DataError

::: firebird.driver.types.OperationalError

::: firebird.driver.types.IntegrityError

::: firebird.driver.types.InternalError

::: firebird.driver.types.ProgrammingError

::: firebird.driver.types.NotSupportedError

::: firebird.driver.types.FirebirdWarning

This is the exception inheritance layout:

```text
Exception
|__Error
    |__InterfaceError
    |__DatabaseError
        |__DataError
        |__OperationalError
        |__IntegrityError
        |__InternalError
        |__ProgrammingError
        |__NotSupportedError

UserWarning
|__FirebirdWarning

```
## Other constants and types required by Python DB API 2.0 specification

### Globals

::: firebird.driver.types.apilevel

::: firebird.driver.types.threadsafety

::: firebird.driver.types.paramstyle

### Helper constants for work with [`Cursor.description`](ref-core.md#firebird.driver.core.Cursor.description) content

- DESCRIPTION_NAME
- DESCRIPTION_TYPE_CODE
- DESCRIPTION_DISPLAY_SIZE
- DESCRIPTION_INTERNAL_SIZE
- DESCRIPTION_PRECISION
- DESCRIPTION_SCALE
- DESCRIPTION_NULL_OK

### Types

::: firebird.driver.types.STRING

::: firebird.driver.types.BINARY

::: firebird.driver.types.NUMBER

::: firebird.driver.types.DATETIME

::: firebird.driver.types.ROWID

### Constructors for data types

::: firebird.driver.types.Date

::: firebird.driver.types.Time

::: firebird.driver.types.Timestamp

::: firebird.driver.types.DateFromTicks

::: firebird.driver.types.TimeFromTicks

::: firebird.driver.types.TimestampFromTicks

::: firebird.driver.types.Binary

## Types for type hints

::: firebird.driver.types.DESCRIPTION

::: firebird.driver.types.CB_OUTPUT_LINE

::: firebird.driver.types.Transactional

## Enums

::: firebird.driver.types.NetProtocol

::: firebird.driver.types.DirectoryCode

::: firebird.driver.types.XpbKind

::: firebird.driver.types.StateResult

::: firebird.driver.types.PageSize

::: firebird.driver.types.DBKeyScope

::: firebird.driver.types.InfoItemType

::: firebird.driver.types.SrvInfoCode

::: firebird.driver.types.BlobInfoCode

::: firebird.driver.types.DbInfoCode

::: firebird.driver.types.ResultSetInfoCode

::: firebird.driver.types.Features

::: firebird.driver.types.ReplicaMode

::: firebird.driver.types.StmtInfoCode

::: firebird.driver.types.ReqInfoCode

::: firebird.driver.types.ReqState

::: firebird.driver.types.TraInfoCode

::: firebird.driver.types.TraInfoIsolation

::: firebird.driver.types.TraInfoReadCommitted

::: firebird.driver.types.TraInfoAccess

::: firebird.driver.types.TraAccessMode

::: firebird.driver.types.TraIsolation

::: firebird.driver.types.TraReadCommitted

::: firebird.driver.types.Isolation

::: firebird.driver.types.TraLockResolution

::: firebird.driver.types.TableShareMode

::: firebird.driver.types.TableAccessMode

::: firebird.driver.types.DefaultAction

::: firebird.driver.types.StatementType

::: firebird.driver.types.SQLDataType

::: firebird.driver.types.DPBItem

::: firebird.driver.types.TPBItem

::: firebird.driver.types.SPBItem

::: firebird.driver.types.BPBItem

::: firebird.driver.types.BlobType

::: firebird.driver.types.BlobStorage

::: firebird.driver.types.ServerAction

::: firebird.driver.types.SrvDbInfoOption

::: firebird.driver.types.SrvRepairOption

::: firebird.driver.types.SrvBackupOption

::: firebird.driver.types.SrvRestoreOption

::: firebird.driver.types.SrvNBackupOption

::: firebird.driver.types.SrvTraceOption

::: firebird.driver.types.SrvPropertiesOption

::: firebird.driver.types.SrvValidateOption

::: firebird.driver.types.SrvUserOption

::: firebird.driver.types.DbAccessMode

::: firebird.driver.types.DbSpaceReservation

::: firebird.driver.types.DbWriteMode

::: firebird.driver.types.ShutdownMode

::: firebird.driver.types.OnlineMode

::: firebird.driver.types.ShutdownMethod

::: firebird.driver.types.TransactionState

::: firebird.driver.types.DbProvider

::: firebird.driver.types.DbClass

::: firebird.driver.types.Implementation

::: firebird.driver.types.ImpCPU

::: firebird.driver.types.ImpOS

::: firebird.driver.types.ImpCompiler

::: firebird.driver.types.CancelType

::: firebird.driver.types.DecfloatRound

::: firebird.driver.types.DecfloatTraps

## Flags

::: firebird.driver.types.StateFlag

::: firebird.driver.types.PreparePrefetchFlag

::: firebird.driver.types.StatementFlag

::: firebird.driver.types.CursorFlag

::: firebird.driver.types.ConnectionFlag

::: firebird.driver.types.EncryptionFlag

::: firebird.driver.types.ServerCapability

::: firebird.driver.types.SrvRepairFlag

::: firebird.driver.types.SrvStatFlag

::: firebird.driver.types.SrvBackupFlag

::: firebird.driver.types.SrvRestoreFlag

::: firebird.driver.types.SrvNBackupFlag

::: firebird.driver.types.SrvPropertiesFlag

::: firebird.driver.types.ImpFlags

## Dataclasses

::: firebird.driver.types.ItemMetadata
    options:
        members: false

::: firebird.driver.types.TableAccessStats
    options:
        members: false

::: firebird.driver.types.UserInfo
    options:
        members: false

::: firebird.driver.types.BCD
    options:
        members: false

::: firebird.driver.types.TraceSession
    options:
        members: false

::: firebird.driver.types.ImpData
    options:
        members: false

::: firebird.driver.types.ImpDataOld
    options:
        members: false

## Helper functions

::: firebird.driver.types.get_timezone
