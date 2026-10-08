# Executing SQL Statements

Firebird-driver implements two ways for execution of SQL commands against connected database:

* `~.Connection.execute_immediate` - for execution of SQL commands that don't return any result.
* `.Cursor` objects that offer rich interface for execution of SQL commands and fetching their results.



## Cursor object

Because `.Cursor` objects always operate in context of single `.Connection` (and `.TransactionManager`),
`.Cursor` instances are not created directly, but by constructor method. Python DB API 2.0 assumes
that if database engine supports transactions, it supports only one transaction per connection,
hence it defines constructor method `~.Connection.cursor` (and other transaction-related methods)
as part of `.Connection` interface. However, Firebird supports multiple independent transactions
per connection. To conform to Python DB API, firebird-driver uses concept of internal
`~.Connection.main_transaction` and secondary `~.Connection.transactions`. Cursor constructor is
primarily defined by `.TransactionManager`, and Cursor constructor on `.Connection` is therefore
a shortcut for `main_transaction.cursor()`.

`.Cursor` objects are used for next operations:

* Execution of SQL Statemets: methods `~.Cursor.execute()`, `~.Cursor.executemany()`, `~.Cursor.open()`
    and `~.Cursor.callproc()`.
* Creating `.Statement` objects for efficient repeated execution of SQL statements, and to obtain
    additional information about SQL statements (like execution `~.Statement.plan`): method `~.Cursor.prepare()`.
* [Fetching results](executing-sql-statements.md#fetching-data-from-server): methods `~.Cursor.fetchone()`, `~.Cursor.fetchmany()`,
    `~.Cursor.fetchall()`, `~.Cursor.fetch_next()`, `~.Cursor.fetch_prior()`, `~.Cursor.fetch_first()`,
    `~.Cursor.fetch_last()`, `~.Cursor.fetch_absolute()` and `~.Cursor.fetch_relative()`.


## SQL Execution Basics

There are five methods how to execute SQL commands:

1. `.Connection.execute_immediate()` or `.TransactionManager.execute_immediate()` for SQL commands
    that don't return any result, and are not executed frequently. This method also **doesn't**
    support either [parameterized statements](executing-sql-statements.md#parameterized-statements) or
    [prepared statements](executing-sql-statements.md#prepared-statements).

    !!! tip

        This method is efficient for `administrative` and [DDL](http://en.wikipedia.org/wiki/Data_Definition_Language) SQL commands, like `DROP`, `CREATE`
        or `ALTER` commands, `SET STATISTICS` etc.

2. `.Cursor.execute()` for SQL commands that return result sets, i.e. sequence of `rows` of the same
    structure, and sequence has unknown number of `rows` (including zero). Each row of the sequence
    can be read only once, and is returned in the order it is read from the server.

    !!! tip

        This method is preferred for all `SELECT` and other [DML](http://en.wikipedia.org/wiki/Data_Manipulation_Language) statements, or any statement that
        is executed frequently, either `as is` or in `parameterized` form.

3. `.Cursor.executemany()` for execution of single parameterized SQL command with various set
    of parameters.

    !!! important

        Because `executemany()` is basically a simple loop that calls `execute()` with different
        parameters, it's possible to execute any statement acceptable by `execute()`. However,
        it's possible to access the result set **only** from last executed command, so this method
        should not be used for SQL commands that return results.

4. `.Cursor.open()` for SQL command that return result sets, i.e. sequence of `rows` of the same
    structure, and sequence has unknown number of `rows` (including zero). Instead of just fetching
    rows sequentially in a forward direction like `execute()`, this method allows flexible navigation
    through an open cursor set both backwards and forwards. Rows next to, prior to and relative to
    the current cursor row can be targeted.

    !!! info
        [Scrollable cursors](executing-sql-statements.md#scrollable-cursors) for details.

5. `.Cursor.callproc()` for execution of `Stored procedures` that always return exactly one set
    of values.

    !!! note

        This method of SP invocation is equivalent to `"EXECUTE PROCEDURE ..."` SQL statement.


## Fetching data from server

Result of SQL statement execution consists from sequence of zero to unknown number of `rows`,
where each `row` is a set of exactly the same number of values. `.Cursor` object offer number
of different methods for fetching these `rows`, that should satisfy all your specific needs:

* `~.Cursor.fetchone()` - Returns the next row of a query result set, or `None` when no more data
    is available.

    !!! tip

        Cursor supports the [iterator protocol](https://docs.python.org/3/library/stdtypes.html#iterator-types), yielding tuples of values
        like `~.Cursor.fetchone()`.

* `~.Cursor.fetchmany()` - Returns the next set of rows of a query result, returning a sequence
    of sequences (e.g. a list of tuples). An empty sequence is returned when no more rows are available.

    The number of rows to fetch per call is specified by the parameter. If it is not given, the
    cursor’s `~.Cursor.arraysize` determines the number of rows to be fetched. The method does try
    to fetch as many rows as indicated by the size parameter. If this is not possible due to
    the specified number of rows not being available, fewer rows may be returned.

    !!! note

        The default value of `~.Cursor.arraysize` is `1`, so without paremeter it's equivalent to
        `~.Cursor.fetchone()`, but returns list of `rows`, instead actual `row` directly.

* `~.Cursor.fetchall()` -  Returns all (remaining) rows of a query result as list of tuples,
    where each tuple is one row of returned values.

    !!! tip

        This method can potentially return huge amount of data, that may exhaust available memory.
        If you need just `iteration` over potentially big result set, use loops with `~.Cursor.fetchone()`
        or Cursor's built-in support for [iterator protocol](https://docs.python.org/3/library/stdtypes.html#iterator-types) instead this method.

* Call to `~.Cursor.execute()` returns `self` (Cursor instance) that itself supports the
    [iterator protocol](https://docs.python.org/3/library/stdtypes.html#iterator-types), yielding tuples of values like `~.Cursor.fetchone()`.

!!! important

    Firebird-driver makes absolutely no guarantees about the `row` return value of the
    `fetch*()` methods except that it is a sequence indexed by field position. Therefore, client
    programmers should not rely on the return value being an instance of a particular class or type.

**Examples:**

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    cur = con.cursor()
    SELECT = "select country, currency from country"

    # 1. Using built-in support for iteration protocol to iterate over the rows available
    # from the cursor, unpacking the resulting sequences to yield their elements (country, currency):
    cur.execute(SELECT)
    for (country, currency) in cur:
        print(f"{country} uses {currency} as currency.")
    # or alternatively you can take an advantage of cur.execute() returning self.
    for (country, currency) in cur.execute(SELECT):
        print(f"{country} uses {currency} as currency.")

    # 2. Equivalently using fetchall():
    # This is potentially dangerous if result set is huge, as the whole result set is
    # first materialized as list and then used for iteration.
    cur.execute(SELECT)
    for row in cur.fetchall():
        print(f"{row[0]} uses {row[1]} as currency.")

```

!!! important

    Method `.Cursor.executemany()` is not intended for operations that return results,
    so it does **NOT** returns `self` like `.Cursor.execute()`, and you can't use calls
    to this method as iterator.

<a id="scrollable-cursors"></a>


## Scrollable cursors

SQL statements executed by `.Cursor.open()` have scrollable result set that could be
navigated using next methods:

* `~.Cursor.fetch_next()` - Moves the cursor's current position to the next row and
    returns it. Returns `None` if the cursor is empty or already positioned at the last row.

* `~.Cursor.fetch_prior()` - Moves the cursor's current position to the prior row and
    returns it. Returns `None` if the cursor is empty or already positioned at the first row.

* `~.Cursor.fetch_first()` - Moves the cursor's current position to the first row and
    returns it. Returns `None` if the cursor is empty.

* `~.Cursor.fetch_last()` - Moves the cursor's current position to the last row and
    returns it. Returns `None` if the cursor is empty.

* `~.Cursor.fetch_absolute()` - Moves the cursor's current position to the specified
    <position> and returns the located row. Returns `None` if <position> is beyond the
    cursor's boundaries.

* `~.Cursor.fetch_relative()` - Moves the cursor's current position backward or forward
    by the specified <offset> and returns the located row. Returns `None` if the calculated
    position is beyond the cursor's boundaries.

!!! important

    Please note that scrollable cursors:

    a) are not supported by all versions of Firebird server.

    b) are internally materialized as a temporary record set, thus consuming
       memory/disk resources, so this feature should be used only when really necessary.

**Example:**

```python
from firebird.driver import connect

def print_row(row):
    if row:
        print(f"{row[0]}, {row[1]}, {row[2]}")
    else:
        print('NO DATA')

with connect('employee', user='SYSDBA', password='masterkey') as con:
    cur = con.cursor()
    cur.open('select row_number() over (order by country), country, currency from country order by country')

    # You can iterate over scrollable cursors
    for row in cur:
        print_row(row)

    print('-' * 10)
    # or fetch particular rows directly
    print_row(cur.fetch_first())
    print_row(cur.fetch_last())
    print_row(cur.fetch_absolute(10))
    print_row(cur.fetch_next())
    print_row(cur.fetch_prior())
    print_row(cur.fetch_relative(-5))
    print_row(cur.fetch_relative(10))

    print('-' * 10)

    cur.fetch_last()
    print_row(cur.fetch_next())

```

**Sample output**:

```text
1, Australia, ADollar
2, Austria, Euro
3, Belgium, Euro
4, Canada, CdnDlr
5, England, Pound
6, Fiji, FDollar
7, France, Euro
8, Germany, Euro
9, Hong Kong, HKDollar
10, Italy, Euro
11, Japan, Yen
12, Netherlands, Euro
13, Romania, RLeu
14, Russia, Ruble
15, Switzerland, SFranc
16, USA, Dollar
----------
1, Australia, ADollar
16, USA, Dollar
10, Italy, Euro
11, Japan, Yen
10, Italy, Euro
5, England, Pound
15, Switzerland, SFranc
----------
NO DATA

```

<a id="parameterized-statements"></a>

## Parameterized statements

When SQL command you want to execute contains data `values`, you can either:

* Embed them `directly` or via `string formatting` into command string, e.g.:

    ```python
    cur.execute("insert into the_table (a,b,c) values ('aardvark', 1, 0.1)")
    # or
    cur.execute("select * from the_table where col == 'aardvark'")
    # or
    cur.execute("insert into the_table (a,b,c) values ('%s', %i, %f)" % ('aardvark',1,0.1))
    # or
    cur.execute(f"select * from the_table where col == '{value}'")

    ```

* Use parameter marker (`?`) in command string in the slots where values are expected,
    then supply those values as Python list or tuple:

    ```python
    cur.execute("insert into the_table (a,b,c) values (?,?,?)", ('aardvark', 1, 0.1))
    # or
    cur.execute("select * from the_table where col == ?",('aardvark',))

    ```

While both methods have the same results, the second one (called `parametrized`) has several
important advantages:

* You don't need to handle conversions from Python data types to strings.
* Firebird-driver will handle all data type conversions (if necessary) from Python data types
    to Firebird ones, including `None/NULL` conversion and conversion from `str` to `bytes`
    in encoding expected by server.
* You may pass BLOB values as open `file-like` objects, and firebird-driver will handle the
    transfer of BLOB value.

Parametrized statemets also have some limitations. Currently:

* `DATE`, `TIME` and `DATETIME` values must be relevant `datetime` objects.
* `NUMERIC` and `DECIMAL` values must be `decimal` objects.


<a id="prepared-statements"></a>

## Prepared Statements

Execution of any SQL statement has three phases:

* *Preparation*: command is analyzed, validated, execution plan is determined
    by optimizer and all necessary data structures (for example for input and output
    parameters) are initialized.
* *Execution*: input parameters (if any) are passed to server and previously
    prepared statement is actually executed by database engine.
* *Fetching*: result of execution and data (if any) are transferred from server
    to client, and allocated resources are then released (by closing the statement).

The preparation phase consumes some amount of server resources (memory and CPU).
Although preparation and release of resources typically takes only small amount
of CPU time, it builds up as number of executed statements grows. Firebird (like
most database engines) allows to spare this time for subsequent execution if
particular statement should be executed repeatedly - by reusing once prepared
statement for repeated execution. This may save significant amount of server
processing time, and result in better overall performance.

Firebird-driver builds on this by encapsulating the Firebird SQL statement data
and related code into separate `.Statement` class, and implementing the `.Cursor`
class around it. The Cursor uses either an internally managed `.Statement` instance
to execute SQL commands provided as `string`, or uses `.Statement` instance
provided by your code as SQL command.

To get the (prepared) `.Statement` instance for later (repeated) execution, use
`~.Cursor.prepare()` method. You can then pass this instance to `~.Cursor.execute()`,
`~.Cursor.executemany()` or `~.Cursor.open()` instead `command string`.

`.Statement` instances are bound to `.Connection` instance, and can't be used
with any other `.Connection`. Beside repeated execution they are also useful
to get information about statement (like its execution `~.Statement.plan` or
`~.Statement.type`) before its execution.

!!! note

    The internally managed `.Statement` instance is released when `.Cursor` is closed,
    or before any new statement is executed. It means that if your code executes
    the same SQL command (passed as string) repeatedly without closing the cursor
    between calls, the same `.Statement` instance is (re)used.

!!! important

    Implementation of Cursor in firebird-driver somewhat violates the Python DB API 2.0,
    which requires that cursor will be unusable after call to `~.Cursor.close()`; and
    an Error (or subclass) exception should be raised if any operation is attempted with
    the cursor. In firebird-driver, the `.Cursor.close()` call only releases resources
    associated with executed statement like the result set, and you can't fetch data or
    query information about the SQL statement. However, you can use the cursor instance
    to execute new SQL commands.

    !!! warning

        If you'll take advantage of this anomaly, your code would be less portable to other
        Python DB API 2.0 compliant drivers.

**Example:**

```python
insertStatement = cur.prepare("insert into the_table (a,b,c) values (?,?,?)")

inputRows = [
    ('aardvark', 1, 0.1),
    ('zymurgy', 2147483647, 99999.999),
    ('foobar', 2000, 9.9)
  ]

for row in inputRows:
   cur.execute(insertStatement,row)
#
# or you can use executemany
#
cur.executemany(insertStatement, inputRows)


```

!!! info
    `.Statement` for details.


## Named Cursors

To allow the Python programmer to perform scrolling **UPDATE** or **DELETE** via the
**“SELECT ... FOR UPDATE”** syntax, the firebird-driver provides the read-only property
`.Cursor.name` and method `.Cursor.set_cursor_name()`.

**Example Program:**

```python
from firebird.driver import connect

with connect('employee', user='sysdba', password='masterkey') as con:
    curScroll = con.cursor()
    curUpdate = con.cursor()

    curScroll.execute("select city from customer for update")
    curScroll.set_cursor_name('city_scroller')
    update = "update customer set city=? where current of " + curScroll.name

    for (city,) in curScroll:
        city = ... # make some changes to city
        curUpdate.execute( update, (city,) )

    con.commit()

```


## Working with stored procedures

Firebird stored procedures can have input parameters and/or output parameters.
Some databases support input/output parameters, where the same parameter is used
for both input and output; Firebird does not support this.

It is important to distinguish between procedures that **return a result set** and
procedures that **populate and return their output parameters** exactly once. Conceptually,
the latter “return their output parameters” like a Python function, whereas the former
“yield result rows” like a Python generator.

Firebird’s **server-side** procedural SQL syntax makes no such distinction, but client-side
SQL code (and C API code) must. A result set is retrieved from a stored procedure by
**SELECT'ing from the procedure, whereas output parameters are retrieved with an
'EXECUTE PROCEDURE' statement**.

To **retrieve a result set** from a stored procedure with firebird-driver, use code
such as this:

```python
cur.execute("select output1, output2 from the_proc(?, ?)", (input1, input2))

# Ordinary fetch code here, such as:
for row in cur:
   ... # process row

con.commit() # If the procedure had any side effects, commit them.

```

To **execute** a stored procedure and **access its output parameters**, you can
choose from two options:

1. Method `.Cursor.callproc()` that **conforms to Python DB API 2.0**. This method
    does not returns the output parameters directly, and you must call `.Cursor.fetchone()`
    **exactly once** to retrieve them.

2. Method `.Cursor.call_procedure()` that returns output parameters directly
    (or `None` if procedure does not have output parameters).

**Examples:**

```python
# Python DB API 2.0 compliant method:
cur.callproc("the_proc", (input1, input2))
# If there are output parameters, retrieve them as though they were the
# first row of a result set...
outputParams = cur.fetchone()

# alternative method:
outputParams = cur.call_procedure("the_proc", (input1, input2))

con.commit() # If the procedure had any side effects, commit them.


```
