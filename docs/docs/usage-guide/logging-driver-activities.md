# Logging driver activities

The driver works with the [context-based logging system](https://firebird-base.readthedocs.io/en/latest/logging/)
provided by firebird-base. Pass a driver object to `firebird.base.logging.get_logger()`
to obtain a logger with an agent name and context. By default, the agent name is the
object's fully qualified class name. Set its `_agent_name_` attribute before obtaining
the logger to use a different name.

The driver's `log_context` properties provide the context for these objects:

* `TransactionManager`, `Statement`, and `Cursor`: their `Connection`.
* `DistributedTransactionManager`: `UNDEFINED` from `firebird.base.types`.
* `BlobReader`: its owner, or `UNDEFINED` when no owner is available.

`Connection` and `Server` have no `log_context`, so their context is `None`.
The context field contains the context object itself; its displayed value depends
on that object's string representation, not its `_agent_name_`.

**Example:**

```python
import logging
from firebird.base.logging import get_logger, LogLevel
from firebird.driver import Cursor, connect, driver_config

# Helper function
def execute(cur: Cursor, cmd: str) -> None:
    get_logger(cur).debug(f"Execute [{cmd=}]")
    cur.execute(cmd)

# Basic Python logging configuration
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)-10s: [%(agent)s][%(context)s] %(message)s'))
logger = logging.getLogger()
logger.addHandler(sh)
logger.setLevel(LogLevel.DEBUG)

# Firebird driver configuration
srv_cfg = """[local]
host = localhost
user = SYSDBA
password = masterkey
"""
driver_config.register_server('local', srv_cfg)
db_cfg = """[employee]
server = local
database = employee.fdb
protocol = inet
"""
driver_config.register_database('employee', db_cfg)

print("Default logging ids")
with connect('employee') as con:
    con_log = get_logger(con)
    con_log.info('Start')
    cur1 = con.cursor()
    cur2 = con.cursor()
    execute(cur1, 'select * from country')
    execute(cur2, 'select * from project')
    con_log.info('Stop')

print("Custom logging ids")
with connect('employee') as con:
    con._agent_name_ = 'employee-1'
    con_log = get_logger(con)
    con_log.info('Start')
    cur1 = con.cursor()
    cur1._agent_name_ = 'cursor-1'
    cur2 = con.cursor()
    cur2._agent_name_ = 'cursor-2'
    execute(cur1, 'select * from country')
    execute(cur2, 'select * from project')
    con_log.info('Stop')

```

Representative output (`Connection[...]` contains a runtime handle):

```text
Default logging ids
INFO      : [firebird.driver.core.Connection][None] Start
DEBUG     : [firebird.driver.core.Cursor][Connection[...]] Execute [cmd='select * from country']
DEBUG     : [firebird.driver.core.Cursor][Connection[...]] Execute [cmd='select * from project']
INFO      : [firebird.driver.core.Connection][None] Stop
Custom logging ids
INFO      : [employee-1][None] Start
DEBUG     : [cursor-1][Connection[...]] Execute [cmd='select * from country']
DEBUG     : [cursor-2][Connection[...]] Execute [cmd='select * from project']
INFO      : [employee-1][None] Stop

```
You can also trace the driver activities using [trace/audit for class instances](https://firebird-base.readthedocs.io/en/latest/trace/)
provided by [firebird-base](https://firebird-base.rtfd.io) package.

**Example:**

```python
import logging
from firebird.base.logging import get_logger, LogLevel
from firebird.base.trace import trace_manager, add_trace, trace_object, TraceFlag
from firebird.driver import Connection, Cursor, TransactionManager, connect, driver_config

# Helper function
def execute(cur: Cursor, cmd: str) -> None:
    cur.execute(cmd)

# Basic Python logging configuration
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)-10s: [%(agent)s][%(context)s] %(message)s'))
logger = logging.getLogger()
logger.addHandler(sh)
logger.setLevel(LogLevel.DEBUG)

# Firebird driver configuration
srv_cfg = """[local]
host = localhost
user = SYSDBA
password = masterkey
"""
driver_config.register_server('local', srv_cfg)
db_cfg = """[employee]
server = local
database = employee.fdb
protocol = inet
"""
driver_config.register_database('employee', db_cfg)

# Trace configuration
# First: register classes and methods that could be traced
trace_manager.register(Connection)
add_trace(Connection, 'close')
trace_manager.register(TransactionManager)
add_trace(TransactionManager, 'begin')
add_trace(TransactionManager, 'commit')
add_trace(TransactionManager, 'rollback')
trace_manager.register(Cursor)
add_trace(Cursor, 'execute')
add_trace(Cursor, 'close')
# Activate trace/audit
trace_manager.flags |= (TraceFlag.ACTIVE | TraceFlag.BEFORE | TraceFlag.AFTER | TraceFlag.FAIL)

# Traced code
with connect('employee') as con:
    trace_object(con)
    trace_object(con.main_transaction)
    con._agent_name_ = 'employee-1'
    cur1 = con.cursor()
    trace_object(cur1)
    cur1._agent_name_ = 'cursor-1'
    cur2 = con.cursor()
    trace_object(cur2)
    cur2._agent_name_ = 'cursor-2'
    execute(cur1, 'select * from country')
    execute(cur2, 'select * from project')
    con.commit()

```

The trace records show calls before and after the traced methods. The `commit()` call
produces transaction commit records; without it, closing the connection rolls back
its active transaction. Agent names reflect `_agent_name_` when set, while the context
field for cursors and transaction managers displays their connection object. Exact
records, connection handles, and timings depend on the executed statements and server.
