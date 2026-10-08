# Versioned features and Services API

The driver detects the connected Firebird version and chooses the appropriate
provider object. Examples include database, transaction, and statement
`*InfoProvider` objects and `Server.database`'s `ServerDbServices*` object.
Methods shown on a newer provider class may be absent on an object returned
for an older Firebird server. The Python package version alone cannot establish
server feature availability.

Before writing code that calls a version-dependent provider method, ask which
Firebird server versions the code must support if that is not already clear.
Then check the method on the provider class selected for those versions and
write for the stated support range. Do not add repetitive `hasattr()` checks
before every call merely because providers are versioned. If the user needs
multiple server versions, choose a shared API or an explicit version-specific
branch where behavior genuinely differs.

Use the [Services guide](https://firebird-driver.rtfd.io/usage-guide/working-with-services/index.md)
for administrative work and the [Core API reference](https://firebird-driver.rtfd.io/ref-core/index.md)
for exact provider methods. Services API objects have their own ownership and
lifetimes; use `Server` as a context manager where practical. Do not assume a
SQL `Connection` or cursor method performs a Services API operation.

Paths supplied to backup, restore, and maintenance services are interpreted by
the Firebird server, which may run on a different host from the Python process.
Some service actions produce output or continue after the initiating call;
follow the method's completion and output contract, using `Server` output
methods or `wait()` as appropriate before treating the action as finished.
