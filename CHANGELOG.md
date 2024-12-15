# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [1.10.7] - 2024-12-15

### Changed

- Rename `DbClass` items to become more descriptive
- Cleanup of Useless StmtInfoCode codes
- Use new info codes in Statement

### Added

- `DatabaseInfoProvider3.supports` and `TransactionInfoProvider3.supports` functions.
- `StatementInfoProvider` and use it in `Cursor.affected_rows` implementation.
- Dataclasses `IpData` and `ImpDataOld`
- Missing `ReqInfoCode` codes.
- missing `encoding` and `errors` SPB config parameters.

### Fixed

- `DatabaseInfoProvider3.implementation` property.
- Issue when wrong close is selected in class hierarchy.
- Handling of `DbInfoCode.BASE_LEVEL`, `DbInfoCode.DB_FILE_SIZE`,
  `DbInfoCode.IMPLEMENTATION`, `DbInfoCode.IMPLEMENTATION_OLD`, `DbInfoCode.ACTIVE_TRANSACTIONS`,
  `DbInfoCode.LIMBO`, `DbInfoCode.PAGE_CONTENTS`, `DbInfoCode.USER_NAME`, `DbInfoCode.SQL_ROLE` codes

## [1.10.6] - 2024-08-15

### Fixed

- Unregistered bug: Big NUMERIC/DECIMAL (i.e. INT128) ARRAYs do not work.
- Unregistered bug: ARRAYs of TIME WITH TIMEZONE do not work.

## [1.10.5] - 2024-07-26

### Fixed

- Unregistered bug: DECFLOAT ARRAYs do not work.

## [1.10.4] - 2024-05-07

### Added

- Support for values fetched from environment variables in configuration files via
  EnvExtendedInterpolation provided by firebird-base package v1.8.0.

### Fixed

- Unregistered bug: db info call for CRYPT_KEY, CRYPT_PLUGIN, WIRE_CRYPT, DB_GUID and
  DB_FILE_ID returned mangled values.
- Unregistered bug: db info call for FIREBIRD_VERSION or Connection.info.firebird_version
  always returned only one string. Now it returns all values returned by server, separated
  by newline.

## [1.10.3] - 2024-05-03

### Fixed

- #30 - It is not possible to start a transaction without specifying an isolation level
  The fix allows use of empty tpb in `TransactionManager.begin()`

## [1.10.2] - 2024-05-03

### Fixed

- Mangled output for `DbInfoCode` itsens `CRYPT_PLUGIN`, `WIRE_CRYPT`, `DB_GUID` and `DB_FILE_ID`
- #34 - Pre-1970 dates causes OverflowError
- #38 - 'datetime.date' object has no attribute 'date'

## [1.10.1] - 2023-12-21

### Fixed

- Call iProvider.shutdown() on program exit.
- #33 - SIGABRT on interface detach.

## [1.10.0] - 2023-10-03

### Fixed

- #27 - Failed to establish a connection to the server on the specified port.
- #15 - Documentation issue.
- Fixed issue on MacOS (see #7827 in Firebird)

### Changed

- Build system changed from setuptools to hatch

## [1.9.0] - 2023-06-27

### Added

- Initial (as for Beta 1) support for Firebird 5.0 API and features.

  - New and extended types: Extended `DbInfoCode`, `StmtInfoCode`, `DPBItem`,
    `SrvRepairOption`, `SrvBackupOption`, `SrvNBackupOption`, `Implementation`,
    `SrvRepairFlag`, `SrvBackupFlag` and new `ResultSetInfoCode`.
  - API: `iResultSet.get_info` method available for FB5 attachments.
  - Parallel workers: Added `DatabaseConfig.parallel_workers` configuration option, added
    `parallel_workers` parameter to `ServerDbServices3.backup`, `ServerDbServices3.restore`
    and `ServerDbServices3.sweep`, added `parallel_workers` to `DPB`
  - New `ServerDbServices.upgrade` method (in-place minor ODS upgrades)
- Classic API functions for BLR and BLOB manipulation to `FirebirdAPI`.

### Fixed

- Test: Fix name for `to_dict()` test.
- Wait for completion of `ServerDbServices` services that do not return data.
  Otherwise subsequent service calls may end with "Service is currently busy" error.
- Documentation link for the driver, provided by @mariuz
- #20: Cursor.description returning () instead of None when the cursor has no rows,
  which is violation of PEP 249. Fix provided by @fdcastel

### Changed

- Improvement: Internal handling of attachment and trasansaction handles.

## [1.8.0] - 2022-12-07

### Added

- `Server.readline_timed` method.

## [1.7.0] - 2022-11-28

### Added

- `Cursor.to_dict` method.

### Changed

- Move away from setup.cfg to pyproject.toml, changed source tree layout.

## [1.6.0] - 2022-10-12

### Changed

- Further code optimizations.
- Addressing issues reported by pylint.
- Updated Firebird OO API (interface extensions between 3.0.7->3.0.10, 4.0.0->4.0.2)
- Improved documentation.

## [1.5.2] - 2022-10-03

### Added

- Documentation is now also provided as Dash / Zeal docset, downloadable from releases at github.

### Chaged

- Code optionizations.

## [1.5.1] - 2022-08-23

### Fixed

- `ServerDbServices.set_replica_mode()` now works correctly.

## [1.5.0] - 2022-05-23

### Adeed

- `verbint` parameter for `ServerDbServices3.backup()` and `ServerDbServices3.restore()`

  This is undocumented Firebird v3 gbak feature. See [this](https://github.com/FirebirdSQL/firebird/issues/808)
  for details. It's mutually exclusive with `verbose`, and minimal value is 100.

### Fixed

- `firebird.driver.core.create_database()` now use server configuration user/password
  if either is not specified in database configuration (like `.connect()`)
- Problem in `Server` processing incomplete LINE responses.

### Changed

** Potentially breaking changes **

- Change in `ServerDbServices3.restore()`: The `verbose` parameter default value was changed
  to `False` to be consistent with `ServerDbServices3.backup()`
- Change in `ShutdownMethod`: DENNY_ATTACHMENTS/DENNY_TRANSACTIONS renamed to
  DENY_ATTACHMENTS/DENY_TRANSACTIONS.

## [1.4.3] - 2022-03-30

### Fixed

- Load driver configuration only when it's successfully read from file(s)
- Reading service output will fail if line is greater than 64K
- Avoid division by zero if fetches stats is zero in DatabaseInfoProvider.cache_hit_ratio
- Rewind buffer with version string after using in EngineVersionProvider
- Add low-level access to fb_shutdown_callback API function

## [1.4.2] - 2022-01-11

### Added

- New `ServerConfig` options: `ServerConfig.encoding` and `ServerConfig.encoding_errors`.
- New `connect_server` parameters: `encoding` and `encoding_errors`.

### Changed

- Requires `firebird-base 1.3.1`

## [1.4.1] - 2021-12-21

### Fixed

- Fixed important bug when `iAttachment` was not properly released.

## [1.4.0] - 2021-12-16

### Added

- Added `role` parameter to `connect_server` and `firebird.driver.core.SPB_ATTACH`.
- Added `encoding` parameter to `firebird.driver.core.SPB_ATTACH` with default value
  `ascii` - used to encode `config`, `user`, `password` and `expected_db` values.
- Added `encoding` parameter to `firebird.driver.core.TPB` with default value `ascii`
  (used to encode table names).
- `firebird.driver.core.DPB` parameter `charset` is now used to determine encoding for
  `config`, `user`, `password` and `role` values.
- `connect_server` has new `encoding` parameter with default value `ascii` that is passed
  to new `Server.encoding` attribute. `Server.encoding` is used to encode/decode various
  string values passed between client and server in parameter buffers (see below), and text
  output from services.
- `ServerInfoProvider` now uses `Server.encoding` for returned SERVER_VERSION, IMPLEMENTATION,
  GET_ENV, GET_ENV_MSG, GET_ENV_LOCK, USER_DBPATH and DBNAME values.
- `ServerDbServices` now uses `Server.encoding` for DBNAME, SQL_ROLE_NAME, FILE, SKIP_DATA,
  INCLUDE_DATA, INCLUDE_TABLE, EXCLUDE_TABLE, INCLUDE_INDEX, EXCLUDE_INDEX, LINE and
  isc_spb_sts_table SPB values.
- `ServerUserServices` now uses `Server.encoding` for DBNAME, SQL_ROLE_NAME, USER_NAME,
  GROUP_NAME, FIRST_NAME, MIDDLE_NAME, LAST_NAME and PASSWORD (on storage only) SPB values.
- `ServerTraceServices` now uses `Server.encoding` for CONFIG SPB value.
- Failed `Connection.close()` should not cause problems on object destruction anymore.
- Failed `Server.close()` should not cause problems on object destruction anymore.

### Changed

** Backward incompatible changes **

- `tpb` parameter `access` renamed to `access_mode`.
- `FirebirdWarning` now descends from `UserWarning` instead `Warning`, and is reported
  to application via `.warnings.warn` instead raised as exception.
- `iAttachment_v3` attribute `charset` was renamed to `encoding`.
- `iXpbBuilder.insert_string` optional parameter `encoding` is now  keyword-only.
  Parameter also added to `iXpbBuilder.get_string` method.

## [1.3.4] - 2021-11-30

### Added

- User-defined encoding for string parameter and response values exchanged between driver
  and Firebird engine. This includes TPB, DPB, SPB and various service values:

  - `firebird.driver.core.TPB`: New `encoding` constructor parameter & attribute. Used
    for `table names` in table reservation.
  - `firebird.driver.core.DPB`: Encoding based on connection charset for `config`,
    `user name`, `password` and `role`.
  - `firebird.driver.core..SPB`: New `encoding` constructor parameter & attribute. Used
    for `config`, `user name`, `password` and `expected database`.
  - Connection-related providers: Encoding based on connection charset.
  - Server and Service providers: New `Server.encoding` attribute.

### Fixed

- Bug in `ServerDbServices3.get_statistics` when `tables` are specified.

### Changed

- `FirebirdWarning` is not raised as exception, but reported via `warnings.warn`  mechanism.

## [1.3.3] - 2021-10-20

### Added

- New exception type `FirebirdWarning`. From now on, warnings from engine are raised as
  `FirebirdWarning` instead `Warning`. In some future release, warnings will not be raised,
  but reported via `warnings.warn` mechanism.

### Fixed

- Unregistered bug: Newly extended interface breaks the driver (affects usability of
  the driver with Firebird development versions).

## [1.3.2] - 2021-09-17

### Added

- New context manager `temp_database`.

### Fixed

- Unregistered bug: iUtil methods removed after FB 4 Beta 2 broke the Int128/TZ handling.

## [1.3.1] - 2021-09-16

### Fixed

- Unregistered bug: wrong handling of Firebird 4 string info parameters.

## [1.3.0] - Unreleased

### Added

- All methods of `ServerDbServices3` except 3 related to limbo transactions have new
  optional keyword-only parameter `role` that is passed to called utility.
- Function `connect_server()` has new optional keyword-only parameter `expected_db`,
  to access services with non-default security database.
- Improved Firebird 4 support.

  - Version-specific classes introduced. Internal classes `DatabaseInfoProvider`,
    `TransactionInfoProvider` and `ServerDbServices` now implement only Firebird 4 features
    and descend from Firebird 3 versions. The proper variant is returned according to
    connected server.
  - New `DatabaseConfig` options `session_time_zone`, `set_bind`, `decfloat_round` and
    `decfloat_traps`.
  - New `firebird.driver.core.DPB` parameters `session_time_zone`, `set_db_replica`,
    `set_bind`, `decfloat_round` and `decfloat_traps`.
  - New `session_time_zone` keyword parameter for `connect()`.
  - Added explicit support for READ COMMITTED READ CONSISTENCY isolation (when disabled in
    Firebird configuration).
  - Support for transactions started at specified snapshot number.
    New `TransactionInfoProvider.snapshot_number` property.
    The `firebird.driver.core.TPB` has new `at_snapshot_number` parameter.
  - `backup()` and `local_backup()` have new optional keyword-only arguments
    `include_data`, `keyhoder`, `keyname` and `crypt`, and `ZIP` value was added to `SrvBackupFlag`.
  - `restore()` and `local_restore()` have new optional keyword-only
    arguments `include_data`, `keyhoder`, `keyname`, `crypt` and `replica_mode`.
  - `nbackup()` has new optional keyword-only parameter `guid`.
  - Support for new services.
    New methods `ServerDbServices.nfix_database()` and `set_replica_mode()`.
  - Support for `Statement.timeout`, and `idle_timeout` and `statement_timeout` in `Connection.info`.
  - New types: `Features`, `ReplicaMode`, `CancelType`, `DecfloatRound`, `DecfloatTraps`,
    `ConnectionFlag` and `EncryptionFlag`. Firebird 4-related values added to some other
    enum types.

### Fixed

- Bug #4: exeption returns non ascii-127 symbols.
  The error message decode uses `.fbapi.err_encoding` value that is initialized to
  `locale.getpreferredencoding`. Also, the decode is now done with `errors="replace"`.
- Unregistered bug: wrong handling of milliseconds in TIME and TEMEPSTAMP datatype.
- Sync `_VERSION_` value with package version
- Unregistered bug: Do not raise exception if accessed `Statement.plan` is `None`.
- Unregistered bug: `get_statistics()` does not send `tables` correctly.
- Fix annotations.
- `ServerTraceServices` methods now have return values.
- User name added to `TraceSession`.
- Unregistered bug: `auth_plugin_list` configuration option is ignored

## [1.2.1] - 2021-06-03

### Fixed

- Fixed dependency to `firebird-base` (v1.3.0)

## [1.2.0] - 2021-06-02

### Added

- Added `Server.mode` attribute to allow fetching service output using LINE or TO_EOF method.
  Default mode is TO_EOF.

### Fixed

- Unregistered bug: `sql_dialect` is used instead `db_sql_dialect` in
  `firebird.driver.core.create_database`.
- Bug #2: error when handling input parameters with value None

## [1.1.0] - 2021-03-04

### Important

Support for Firebird 4 TIMEZONE is broken (for FB4 RC1). It will be fixed in next driver version.

### Fixed

- Unregistered bug in `InfoProvider`.
- Unregistered bug in `FirebirdAPI` initialization.

### Changed

- Build scheme changed to `PEP 517`.
- Various changes to documentation and type hint adjustments.
- `DriverConfig.db_defaults` and `DriverConfig.server_defaults` are now created
  as `optional` (introduced by firebird-base 1.2.0), so configuration file does not require
  `firebird.db.defaults` and `firebird.server.defaults` sections (even empty).

## [1.0.0] - 2020-10-13

### Added

- Support for schema and monitor modules from `firebird-lib` package.

### Changed

- Documentation: adjustments to css.

## [0.8.0] - 2020-09-18

### Important

The driver is no longer *beta*, and is now considered as **stable** for Firebird 3.0 (support
for Firebird 4 is still evolving till final release).

### Added

- Support for new FB4 data types in ARRAY fields.
- New `Cursor.call_procedure()` method.

### Changed

- Documentation, both in code and separate (especially Usage Guide).
- Refactoring in driver hooks.
- Refactoring and fixes in Server and its services.

## [0.7.0] - 2020-08-31

### Added

- Support for new FB4 data types (TIME/TIMESTAMP WITH TIMEZONE, DECFLOAT[16|34] and
  extended DECIMAL/NUMERIC via INT128 storage).

## [0.6.0] - 2020-06-30

### Added

- More documentation.
- Initial support for Firebird 4+ (interfaces and other definitions). Includes support for
  interface versions.
- New module: `firebird.driver.config` - Driver configuration
- New module: `firebird.driver.interfaces` - Interface wrappers for Firebird new API

### Changed

- `Service` renamed to `Server`. Selected functionality moved to inner objects (relates to
  FB4+ support).
- Module: `firebird.driver.types`:

  - Interface wrapper moved to separate module
  - Buffer managers moved to `firebird.driver.core` module
- Module `~firebird.driver.core`:

  - `connect()`, `create_database()` and `connect_server()` now use driver configuration.
  - Simplified/unified transaction isolation specification.
  - Emit warnings when objects with allocated Firebird resources are disposed (by Python
    GC) without prior call to `close()`.
  - Trace instrumentation removed. Use dynamic trace configuration from firebird-base 0.6.0.
  - `Connection` and `Transaction` information moved to inner objects accessible via `info`
    properties (relates to FB4+ support).

## [0.1.0] - 2020-05-28

Initial release.
