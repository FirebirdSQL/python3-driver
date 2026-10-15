# `firebird.driver.provider`

Source: `src/firebird/driver/provider.py`, relative to the repository root.

`FirebirdProvider` is a structural protocol. External runtime packages can satisfy it without
inheriting from the driver. `_DriverProvider` is private and handles explicit client paths or
system client lookup. Its root, client version, and capabilities are initialized from the loaded
client API by the `interfaces.py` API-loaded hook. They must not be read before that step.

The runtime root comes from `IConfigManager.get_root_directory()`, not from the client filename.
The private provider checks that root's `plugins` directory for a numbered `engineXX` shared
library to determine whether the embedded capability is present. External provider metadata
is not changed by the driver.
