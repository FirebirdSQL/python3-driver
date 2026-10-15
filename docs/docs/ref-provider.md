# Runtime provider

The public protocol describes the metadata a runtime provider supplies to the driver.
Applications can use the `firebird.runtime.providers` entry-point group to discover and
instantiate a provider, then pass it to `load_api()`. The driver does not choose an entry point.

::: firebird.driver.provider.FirebirdProvider
