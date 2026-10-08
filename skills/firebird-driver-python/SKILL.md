---
name: firebird-driver-python
description: Generate, review, debug, and explain Python application code using the official firebird-driver package. Use for connections, SQL, transactions, events, BLOBs, configuration, and Services API; exclude legacy fdb, KInterbasDB, and unrelated generic SQL.
---

# Firebird driver for Python

Use the official `firebird-driver` API for the user's **target driver version**.
Identify that version from the target project's dependency constraints or installed
package (`importlib.metadata.version("firebird-driver")`). If an exact symbol,
signature, or behavior matters, check the target package's public API and docs.
Use the published [documentation index](https://firebird-driver.rtfd.io/llms.txt)
to find the relevant usage guide or API reference in Markdown. Read its driver
version label: if the target package differs, verify exact details against its
installed code and version-matched documentation. Follow the canonical topic
links from the index. Do not import APIs from `fdb`, KInterbasDB, or unverified
generic DB-API examples.

Read only the guidance relevant to the task:

- [Connections and resources](references/connections-resources.md) for client
  selection, configuration, connection lifetime, BLOBs, and events.
- [Transactions and SQL](references/transactions-sql.md) for transaction
  boundaries, TPBs, cursors, statements, and SQL execution.
- [Versioned features and services](references/versioned-features.md) for
  `*InfoProvider`, `ServerDbServices*`, and Services API calls.

Before writing code that uses functionality selected by the **connected Firebird
server version**, establish which Firebird versions the user must support. Ask
if that is unknown; then code for the stated target without repetitive runtime
feature checks. Distinguish the Firebird server version from the Python driver
package version.

In reviews, report invalid API calls, resource/transaction ownership defects,
and unsafe SQL separately from preferences. Verify that examples use symbols
available in the target version and that resource cleanup and commit/rollback
behavior are intentional.
