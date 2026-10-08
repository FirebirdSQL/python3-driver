# Configuration

The driver uses configuration built on top of [configuration system](https://firebird-base.readthedocs.io/en/latest/config/)
provided by [firebird-base](https://firebird-base.rtfd.io) package. In addition to global settings, the configuration
also includes the definition of connection parameters to Firebird servers and databases.

The default configuration connects to embedded server using direct/local connection method.
To access remote servers and databases (or local ones through remote protocols), it's
necessary to adjust default configuration, or `register` them in configuration manager.

You can manipulate the configuration objects directly, or load configuration from files or
strings (in `.ini-style` `configparser` format).

## The 'driver_config' object

The global [`driver_config`](../ref-config.md#firebird.driver.config.driver_config) object holds all configurable driver parameters, and access
configuration parameters for registered Firebird servers and databases.

In initial state, all parameters have default values and there are no registered servers
and databases. You can set individual parameter values directly, or you can set multiple
parameters (including registered servers and databases) at once by loading them from
configuration string, dict or file(s).

!!! important

    If you want to use specific Firebird client library, you must set the value of
    [`DriverConfig.fb_client_library`](../ref-config.md#firebird.driver.config.DriverConfig) configuration option **before** your application
    calls any from following functions: [`connect()`](../ref-core.md#firebird.driver.core.connect), [`create_database()`](../ref-core.md#firebird.driver.core.create_database),
    [`connect_server()`](../ref-core.md#firebird.driver.core.connect_server), [`load_api()`](../ref-fbapi.md#firebird.driver.fbapi.load_api) or [`get_api()`](../ref-fbapi.md#firebird.driver.fbapi.get_api).

!!! info

    [`DriverConfig`](../ref-config.md#firebird.driver.config.DriverConfig) for list of available methods and parameters.

## Server and database configuration

Firebird provides ever-increasing list of parameter options for database and server connections.
To keep the Python API clean and manageable, the `firebird-driver` uses server and database
configuration objects instead function parameters to specify values for almost all such options.
Connection functions then provide a name parameter that can refer to particular server / database
or configuration, and few keyword parameters to specify / override selected options.

!!! important

    The configuration objects does not allow specification of next options:

    - set database encryption callback (for technical reasons)
    - set db_key scope (for security reasons)
    - disable garbage collection (for security reasons)
    - disable database triggers (for security reasons)
    - allow overwrite of existing database with newly created database (for security reasons)

    These options could be specified only as keyword arguments in appropriate functions.

!!! info

    [`ServerConfig`](../ref-config.md#firebird.driver.config.ServerConfig) and [`DatabaseConfig`](../ref-config.md#firebird.driver.config.DatabaseConfig) for list of available methods and parameters.
