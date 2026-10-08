# Logging driver activities

The firebird-driver supports [context-based logging system](https://firebird-base.readthedocs.io/en/latest/logging/)
provided by [firebird-base](https://firebird-base.rtfd.io) package through use of `~firebird.base.logging.LoggingIdMixin`.

Classes that use `~firebird.base.logging.LoggingIdMixin`:

* `.Connection` - Internally used objects have `_logging_id_` set to 'Transaction.Main',
    'Transaction.Query' and 'Cursor.internal'. The log context is not defined.
* `.TransactionManager` - The `_logging_id_` is set to 'Transaction'. The
    `~.TransactionManager.log_context()` is the `.Connection`.
* `.DistributedTransactionManager` - The `_logging_id_` is set to 'DTransaction'. The
    `~.DistributedTransactionManager.log_context()` is `~firebird.base.types.UNDEFINED`.
* `.Statement` - The `~.Statement.log_context()` is `.Connection`.
* `.BlobReader` - The `~.Statement.log_context()` is the owning object or `~firebird.base.types.UNDEFINED`.
* `.Cursor` - The `~.Cursor.log_context()` is `.Connection`.
* `.Server` - The log context is not defined.

**Example:**

```python
import logging
from firebird.base.logging import get_logger, LogLevel
from firebird.driver import connect, driver_config

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
    con._logging_id_ = 'employee-1'
    con_log = get_logger(con)
    con_log.info('Start')
    cur1 = con.cursor()
    cur1._logging_id_ = 'cursor-1'
    cur2 = con.cursor()
    cur2._logging_id_ = 'cursor-2'
    execute(cur1, 'select * from country')
    execute(cur2, 'select * from project')
    con_log.info('Stop')

```

Output:

```text
Default logging ids
INFO      : [Connection][UNDEFINED] Start
DEBUG     : [Cursor][Connection] Execute [cmd='select * from country']
DEBUG     : [Cursor][Connection] Execute [cmd='select * from project']
INFO      : [Connection][UNDEFINED] Stop
Custom logging ids
INFO      : [employee-1][UNDEFINED] Start
DEBUG     : [cursor-1][employee-1] Execute [cmd='select * from country']
DEBUG     : [cursor-2][employee-1] Execute [cmd='select * from project']
INFO      : [employee-1][UNDEFINED] Stop

```
You can also trace the driver activities using [trace/audit for class instances](https://firebird-base.readthedocs.io/en/latest/trace/)
provided by [firebird-base](https://firebird-base.rtfd.io) package.

**Example:**

```python
import logging
from firebird.base.logging import get_logger, LogLevel
from firebird.base.trace import trace_manager, add_trace, trace_object, traced, TraceFlag
from firebird.driver import connect, driver_config
from firebird.driver.core import TransactionManager

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
add_trace(Connection, 'close', traced)
trace_manager.register(TransactionManager)
add_trace(TransactionManager, 'begin', traced)
add_trace(TransactionManager, 'commit', traced)
add_trace(TransactionManager, 'rollback', traced)
trace_manager.register(Cursor)
add_trace(Cursor, 'execute', traced)
add_trace(Cursor, 'close', traced)
# Activate trace/audit
trace_manager.trace |= (TraceFlag.ACTIVE | TraceFlag.BEFORE | TraceFlag.AFTER | TraceFlag.FAIL)

# Traced code
with connect('employee') as con:
    trace_object(con)
    trace_object(con.main_transaction)
    con._logging_id_ = 'employee-1'
    cur1 = con.cursor()
    trace_object(cur1)
    cur1._logging_id_ = 'cursor-1'
    cur2 = con.cursor()
    trace_object(cur2)
    cur2._logging_id_ = 'cursor-2'
    execute(cur1, 'select * from country')
    execute(cur2, 'select * from project')
    con.commit()

```

Sample output:

```text
DEBUG     : [cursor-1][employee-1] >>> execute(operation='select * from country', parameters=None)
DEBUG     : [Transaction.Main][employee-1] >>> begin(tpb=None)
DEBUG     : [Transaction.Main][employee-1] <<< begin[0.00672]
DEBUG     : [cursor-1][employee-1] >>> close()
DEBUG     : [cursor-1][employee-1] <<< close[0.00004]
DEBUG     : [cursor-1][employee-1] <<< execute[0.01119] Result: cursor-1
DEBUG     : [cursor-2][employee-1] >>> execute(operation='select * from project', parameters=None)
DEBUG     : [cursor-2][employee-1] >>> close()
DEBUG     : [cursor-2][employee-1] <<< close[0.00002]
DEBUG     : [cursor-2][employee-1] <<< execute[0.00352] Result: cursor-2
DEBUG     : [Transaction.Main][employee-1] >>> commit(retaining=False)
DEBUG     : [cursor-1][employee-1] >>> close()
DEBUG     : [cursor-1][employee-1] <<< close[0.00017]
DEBUG     : [cursor-2][employee-1] >>> close()
DEBUG     : [cursor-2][employee-1] <<< close[0.00012]
DEBUG     : [Transaction.Main][employee-1] <<< commit[0.00225]
DEBUG     : [employee-1][UNDEFINED] >>> close()
DEBUG     : [employee-1][UNDEFINED] <<< close[0.00764]


```
If you will remove the `con.commit()` from the example above, the output will change to:

```text
DEBUG     : [cursor-1][employee-1] >>> execute(operation='select * from country', parameters=None)
DEBUG     : [Transaction.Main][employee-1] >>> begin(tpb=None)
DEBUG     : [Transaction.Main][employee-1] <<< begin[0.00338]
DEBUG     : [cursor-1][employee-1] >>> close()
DEBUG     : [cursor-1][employee-1] <<< close[0.00003]
DEBUG     : [cursor-1][employee-1] <<< execute[0.00730] Result: cursor-1
DEBUG     : [cursor-2][employee-1] >>> execute(operation='select * from project', parameters=None)
DEBUG     : [cursor-2][employee-1] >>> close()
DEBUG     : [cursor-2][employee-1] <<< close[0.00003]
DEBUG     : [cursor-2][employee-1] <<< execute[0.00345] Result: cursor-2
DEBUG     : [employee-1][UNDEFINED] >>> close()
DEBUG     : [Transaction.Main][employee-1] >>> rollback(retaining=False, savepoint=None)
DEBUG     : [cursor-1][employee-1] >>> close()
DEBUG     : [cursor-1][employee-1] <<< close[0.00016]
DEBUG     : [cursor-2][employee-1] >>> close()
DEBUG     : [cursor-2][employee-1] <<< close[0.00014]
DEBUG     : [Transaction.Main][employee-1] <<< rollback[0.00171]
DEBUG     : [employee-1][UNDEFINED] <<< close[0.01001]


```
