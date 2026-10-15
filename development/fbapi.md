# `firebird.driver.fbapi`

Source: `src/firebird/driver/fbapi.py`, relative to the repository root.

This is the low-level `ctypes` boundary. It defines Firebird C constants, structures, vtables,
and the `FirebirdAPI` loader. `get_api()` calls `load_api()` on first use; the loaded API
is cached in the module. An explicit filename, provider instance, or
`driver_config.fb_client_library.value` selects the client library before first load. Filenames
are wrapped in the private driver provider; provider instances are used directly. The
`APIHook.LOADED` callbacks initialize the private provider after the master and utility
interfaces are available.

Changes to C layouts, pointer types, or signatures can affect every higher-level wrapper.
Compare them with the supported Firebird client API and run focused integration tests on
the affected Firebird versions. Preserve the initialization order used by `interfaces.py`
and `core.py` hooks.
