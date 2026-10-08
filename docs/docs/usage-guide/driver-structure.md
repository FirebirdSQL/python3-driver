# Driver structure

Source code is currently divided into next submodules:

* `types` - Data types used by driver.
* `interfaces` - Interface wrappers for Firebird new API
* `core` - Main driver source code.
* `fbapi` - Python `ctypes` interface to Firebird client library.
* `config` - Driver configuration.
* `hooks` - Drivers hooks.

All important data, functions, classes and constants are available directly in `firebird.driver`
name space. In normal circumstances is not necessary to import sub-modules directly. However,
you may need them to access some not so frequently needed driver functionality like driver
hooks, or to implement your own callback interfaces.

!!! important

    `firebird-driver` is designed to support all Firebird versions starting from version 3.0.
    Because each Firebird major version adds new functionality, and Firebird OO API could
    be extended even in maintenance releases, the driver isolates volatile functionality
    into special class hierarchies.

    For example information about database (provided via `~.iAttachment_v3.get_info()` API
    call) is isolated into separate `.DatabaseInfoProvider` class hierarchy.
    The `.Connection.info` attribute then provides access to instance of appropriate class
    - `.DatabaseInfoProvider` or its ancestor - for connected database.
    The `.DatabaseInfoProvider` class **always** provides functionality of most recent
    Firebird version supported by driver.

    This layout has several important consequences:

    1. The `.DatabaseInfoProvider` class may change in major driver release if new Firebird
        functionality is introduced. This normally represent no problems for client application
        as backward compatibility is guaranteed.
    2. You should check the class hierarchy for "evolving" classes when you start using the
        driver, and whenever you upgrade to new **major** driver version. If there are versioned
        ancestor classes (they always have Firebird version number in their name) for canonical
        (top level) ones, you should adjust your application to deal with situations when
        instance of ancestor class is provided by driver instead top-level one, to prevent
        run-time exceptions caused by access to functionality not provided by currently attached
        Firebird server.

        !!! note

            The same apply for low-level API (`~firebird.driver.interfaces`) with difference
            that they may change in minor driver releases (because API could be extended in
            Firebird maintenance releases).

    !!! info

        `.DatabaseInfoProvider`, `.TransactionInfoProvider`, `.ServerInfoProvider`,
        `.ServerDbServices`, `.ServerUserServices` and `.ServerTraceServices`.
