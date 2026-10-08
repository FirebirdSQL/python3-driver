
# firebird.driver.config

This module defines the configuration system for the firebird-driver.
It uses an INI-style format managed via the `DriverConfig` class, which
allows defining settings for the driver itself, default server/database
parameters, and named configurations for specific servers and databases.

Configuration can be loaded from files, strings, or dictionaries, and
supports environment variable interpolation. The primary interaction point
is usually the global `driver_config` instance.

## Classes

::: firebird.driver.config.DriverConfig

::: firebird.driver.config.ServerConfig

::: firebird.driver.config.DatabaseConfig

## Globals

::: firebird.driver.config.driver_config
