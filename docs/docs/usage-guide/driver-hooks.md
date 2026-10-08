<a id="driver-hooks"></a>



# Driver hooks

The firebird-driver uses [hook manager](https://firebird-base.readthedocs.io/en/latest/hooks/) from [firebird-base](https://firebird-base.rtfd.io) package
to provide internal notification mechanism that allows installation of custom hooks into
certain driver tasks.

Driver hooks are divided into several types exposed as enums in `firebird.driver.hooks` module.

## APIHook

`.APIHook.LOADED` - This hook is invoked once when instance of `.FirebirdAPI` is created.
It could be used for additional initialization tasks that require Firebird API, or to manipulate
the FirebirdAPI instance itself before its use.

Hook routine must have signature: `hook_func(api: FirebirdAPI) -> None`. Any value returned
by hook is ignored.

## ConnectionHook

* `.ConnectionHook.ATTACH_REQUEST`

    This hook is invoked after all parameters are preprocessed and before `.Connection` is created.

    Hook routine must have signature: `hook_func(dsn: str, dpb: bytes) -> Optional[Connection]`
    where `dpb` is Database Parameter Buffer that would be used to create the attachment to the
    database defined by `dsn`. It may return `.Connection` (or subclass) instance or `None`.

    First instance returned by any hook of this type will become the return value of caller function
    and other hooks of the same type are not invoked.

* `.ConnectionHook.ATTACHED`

    This hook is invoked just before `.Connection` (or subclass) instance is returned to the client
    application.

    Hook routine must have signature: `hook_func(con: Connection) -> None`.

* `.ConnectionHook.DETACH_REQUEST`

    This hook is invoked before connection is closed.

    Hook must have signature: `hook_func(con: Connection) -> None`.

    If any hook function returns True, connection is not closed.

* `.ConnectionHook.CLOSED`

    This hook is invoked after connection is closed.

    Hook routine must have signature: `hook_func(con: Connection) -> None`.

* `.ConnectionHook.DROPPED`

    This hook is invoked after database is dropped (and connection is closed).

    Hook routine must have signature: `hook_func(con: Connection) -> None`.

## ServerHook

* `.ServerHook.ATTACHED`

    This hook is invoked before `.Server` instance is returned.

    Hook routine must have signature: `hook_func(srv: Server) -> None`.


