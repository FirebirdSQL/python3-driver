# `firebird.driver.types`

Source: `src/firebird/driver/types.py`, relative to the repository root.

This module defines DB API exception classes, Firebird protocol and information codes,
parameter block items, flags, dataclasses, and typing helpers. It also defines the DB API
constants `apilevel`, `threadsafety`, and `paramstyle`, plus date/time constructors and
type objects. Public selections are re-exported by `__init__.py`.

Keep numeric protocol values and flag combinations consistent with the Firebird client API.
If a type or exception changes, check its use in `core.py` and `interfaces.py` and the relevant
DB API compliance and information provider tests. Do not change exception inheritance or
public constants without checking their DB API contract.
