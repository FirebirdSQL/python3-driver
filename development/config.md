# `firebird.driver.config`

Source: `src/firebird/driver/config.py`, relative to the repository root.

`ServerConfig` and `DatabaseConfig` define connection settings. `DriverConfig` holds global
settings, server and database defaults, and named registration lists. The module-level
`driver_config` is the shared configuration object. Configuration loading uses the `firebird.base.config`
parser with environment interpolation; registration rejects duplicate names.

Set `driver_config.fb_client_library.value` before the first call that loads the Firebird API.
`fbapi.get_api()` caches that API, so changing the configured path afterward does not reload
the library. Changes to defaults, named entries, or connection option precedence should be
checked against `tests/test_connection.py`, `tests/test_server.py`, and the configuration
setup in `tests/conftest.py`.
