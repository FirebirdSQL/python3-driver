# `firebird.driver.hooks`

Source: `src/firebird/driver/hooks.py`, relative to the repository root.

The module defines `APIHook`, `ConnectionHook`, and `ServerHook` event kinds and exposes
registration helpers from `firebird.base.hooks`. `fbapi.py`, `interfaces.py`, and `core.py`
register or invoke these hooks during API loading, attachment, detachment, and service connection.

When adding or changing an event, trace both registration and invocation sites, including
callback arguments and whether a return value can alter the operation. `tests/test_hooks.py`
covers hook ordering and connection lifecycle behavior. Clear global hook registrations between
tests that mutate them.
