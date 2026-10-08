# Data handling and conversions


## Implicit Conversion of Input Parameters from Strings

The Firebird database engine treats most SQL data types in a weakly typed fashion:
the engine may attempt to convert the raw value to a different type, as appropriate
for the current context. For instance, the SQL expressions `123` (integer) and `‘123’`
(string) are treated equivalently when the value is to be inserted into an `integer`
field; the same applies when `‘123’` and `123` are to be inserted into a `varchar` field.

This weak typing model is quite unlike Python’s dynamic yet strong typing. Although
weak typing is regarded with suspicion by most experienced Python programmers, the
database engine is in certain situations so aggressive about its typing model that
firebird-driver must compromise in order to remain an elegant means of programming
the database engine.

An example is the handling of “magic values” for date and time fields. The database
engine interprets certain string values such as `‘yesterday’` and `‘now’` as having
special meaning in a date/time context. If firebird-driver did not accept strings as
the values of parameters destined for storage in date/time fields, the resulting code
would be awkward. Consider the difference between the two Python snippets below, which
insert a row containing an integer and a timestamp into a table defined with the following
DDL statement:

```sql
create table test_table (i integer, t timestamp)

```

```python
i = 1
t = 'now'
sqlWithMagicValues = f"insert into test_table (i, t) values (?, '{t}')"
cur.execute(sqlWithMagicValues, (i,))

```

```python
i = 1
t = 'now'
cur.execute("insert into test_table (i, t) values (?, ?)", (i, t))

```

If firebird-driver did not support weak parameter typing, string parameters that
the database engine is to interpret as “magic values” would have to be rolled into
the SQL statement in a separate operation from the binding of the rest of the parameters,
as in the first Python snippet above. Implicit conversion of parameter values from
strings allows the consistency evident in the second snippet, which is both more
readable and more general.

!!! note

    It should be noted that firebird-driver does not perform the conversion from string
    itself. Instead, it passes that responsibility to the database engine by changing
    the parameter metadata structure dynamically at the last moment, then restoring
    the original state of the metadata structure after the database engine has performed
    the conversion.

A secondary benefit is that when one uses firebird-driver to import large amounts
of data from flat files into the database, the incoming values need not necessarily
be converted to their proper Python types before being passed to the database engine.
Eliminating this intermediate step may accelerate the import process considerably,
although other factors such as the chosen connection protocol and the deactivation
of indexes during the import are more consequential. For bulk import tasks, the
database engine’s external tables also deserve consideration. External tables can
be used to suck semi-structured data from flat files directly into the relational
database without the intervention of an ad hoc conversion program.


## Automatic conversion from/to Unicode

In Firebird, every `CHAR`, `VARCHAR` or textual `BLOB` field can (or, better: must)
have a `character set` assigned. While it's possible to define single character set
for whole database, it's also possible to define different character set for each
textual field. This information is used to correctly store the bytes that make up
the character string, and together with collation information (that defines the sort
ordering and uppercase conversions for a string) is vital for correct data manipulation,
including automatic transliteration between character sets when necessary.

!!! important

    Because data also flow between server and client application, it's vital that client
    will send data encoded only in character set(s) that server expects. While it's
    possible to leave this responsibility completely on client application, it's better
    when client and server settle on single character set they would use for communication,
    especially when database operates with multiple character sets, or uses character set
    that is not `native` for client application.

    Character set for communication is specified using [`charset`](../ref-config.md#firebird.driver.config.DatabaseConfig)
    configuration option, or parameter in [`connect()`](../ref-core.md#firebird.driver.core.connect) or [`create_database()`](../ref-core.md#firebird.driver.core.create_database) call.

    When `connection charset` is defined, all textual data returned from server are encoded
    in this charset, and client application must ensure that all textual data sent to server
    are encoded only in this charset as well.

Firebird-driver helps with client side of this character set bargain by automatically
converting Python `str` values into `bytes` encoded in connection character set,
and vice versa. However, developers are still responsible that `bytes` strings
passed to server are in correct encoding (because firebird-driver makes no assumption
about encoding of `bytes` strings, so it can't recode them to connection charset).

!!! important

    In case that `connection charset` is NOT defined at all, or `NONE` charset is specified,
    firebird-driver uses `locale.getpreferredencoding` to determine encoding for conversions
    from/to `unicode`.

!!! important

    There is one exception to automatic conversion: when character set OCTETS is defined
    for data column. Values assigned to OCTETS columns are always passed `as is`, because
    they're basically binary streams. This has specific implications. Python 3 native
    strings are `unicode`, and you would probably want to use `bytes` type instead. However,
    firebird-driver in this case doesn't check the value type at all, so you'll not be
    warned if you'll make a mistake and pass `str` to OCTETS column (unless you'll pass
    more bytes than column may hold, or you intend to store unicode that way).

Conversion is fully automatic in both directions for all textual data, i.e. including
for string values returned by Firebird Service  and `info` calls etc. When `connection
charset` is not specified, firebird-driver uses `locale.getpreferredencoding` to
determine encoding for conversions from/to `unicode`.

!!! tip

    Except for legacy databases that doesn't have `character set` defined, **always**
    define character set for your databases and specify `connection charset`. It will
    make your life much easier.


## Working with TIME/TIMESTAMP WITH TIMEZONE

Firebird 4 introduced support for TIME and TIMESTAMP WITH TIMEZONE. The driver supports these
types with timezone-aware `datetime.datetime` and `datetime.time` objects. However, this
support has some specific limitations:

1. The driver uses `python-dateutil` package to handle timezone information. Due to specific
    requirements it's not possible to use standard `zoneinfo` package available in Python since
    version 3.9, neither any other `datetime.tzinfo` implementation.
2. All timezone-aware `datetime.datetime` and `datetime.time` objects passed to the driver
    must use `datetime.tzinfo` created with [`get_timezone()`](../ref-types.md#firebird.driver.types.get_timezone) utility function.

**Examples:**

```python
import datetime
from firebird.driver import get_timezone

ts_region = datetime.datetime(2020, 12, 31, 23, 55, 35, 123400, get_timezone('Europe/Prague'))
ts_offset = datetime.datetime(2020, 12, 31, 23, 55, 35, 123400, get_timezone('+02:00'))

```

<a id="working_with_blobs"></a>

## Working with BLOBs

Firebird-driver uses two types of BLOB values:

* **Materialized** BLOB values are Python `str` or `bytes` values. This is the **default** type.
* **Streamed** BLOB values are `file-like` objects.

Materialized BLOBs are easy to work with, but are not suitable for:

* **deferred loading** of BLOBs. They're called `materialized` because they're always
    fetched from server as part of row fetch. Fetching BLOB value means separate API calls
    (and network roundtrips), which may slow down you application considerably.
* **large values**, as they are always stored in memory in full size.

These drawbacks are addressed by `stream` BLOBs. Using BLOBs in `stream` mode is easy:

* For **input** values, simply use [parameterized statement](executing-sql-statements.md#parameterized-statements)
    and pass any `file-like` object in place of BLOB parameter. The `file-like` object must
    implement only the [`read`](https://docs.python.org/3/library/io.html#io.IOBase) method, as no other method is used.
* For **output** values, add column name(s) that should be returned as `file-like`
    objects to [`Cursor.stream_blobs`](../ref-core.md#firebird.driver.core.Cursor) list attribute. Firebird-driver then returns
    [`BlobReader`](../ref-core.md#firebird.driver.core.BlobReader) instance instead string in place of returned BLOB value for these column(s).

!!! important

    The firebird-driver provides [`Cursor.stream_blob_threshold`](../ref-core.md#firebird.driver.core.Cursor) attribute that controls
    the maximum size of materialized blobs (as memory exhaustion safeguard). When particular
    blob value exceeds this threshold, an instance of [`BlobReader`](../ref-core.md#firebird.driver.core.BlobReader) is returned instead
    string/bytes value.

    Zero threshold value effectively forces all blobs to be returned as stream blobs.
    Negative value means no size limit for materialized blobs (use at your own risk).
    Please note that positive threshold value means that your application has to be
    prepared to handle BLOBs in both incarnations.

    The default threshold is 64K and could be changed using [`DriverConfig.stream_blob_threshold`](../ref-config.md#firebird.driver.config.DriverConfig)
    configuration option.

    Blob size threshold has effect only on materialized blob columns, i.e. columns not
    explicitly requested to be returned as streamed ones using [`Cursor.stream_blobs`](../ref-core.md#firebird.driver.core.Cursor)
    attribute, that are **always** returned as stream blobs.

The [`BlobReader`](../ref-core.md#firebird.driver.core.BlobReader) instance is bound to [`Cursor`](../ref-core.md#firebird.driver.core.Cursor) instance, and it's automatically closed
with cursor. However, it's good practice to use `with` statement or call [`BlobReader.close()`](../ref-core.md#firebird.driver.core.BlobReader.close)
once you're finished reading to release system resources associated with BLOB value.

!!! important

    When working with BLOB values, always have memory efficiency in mind, especially when
    you're processing huge quantity of rows with BLOB values at once. Materialized BLOB
    values may exhaust your memory quickly, but using stream BLOBs may have inpact on
    performance too, as new [`BlobReader`](../ref-core.md#firebird.driver.core.BlobReader) instance is created for each value fetched.

**Example program:**

```python
from firebird.driver import connect

with connect('employee', user='SYSDBA', password='masterkey') as con:
    cur = con.cursor()
    print("Materialized retrieval (as str):")
    cur.execute('select proj_id, proj_desc from project')
    proj_id, proj_desc = cur.fetchone()
    print(f"{proj_id=}, {proj_desc=}")

    print("\nStreaming retrieval (via BlobReader):")
    cur.stream_blobs.append('PROJ_DESC')
    cur.execute('select proj_id, proj_desc from project')
    proj_id, proj_desc = cur.fetchone()
    with proj_desc:
        print(f"{proj_id=}, {proj_desc=}")
        print(proj_desc.read())

```

Output:

```text
Materialized retrieval (as str):
proj_id='VBASE', proj_desc='Design a video data base management system for\ncontrolling on-demand video distribution.\n'

Streaming retrieval (via BlobReader):
proj_id='VBASE', proj_desc=BlobReader[size=89]
Design a video data base management system for
controlling on-demand video distribution.

```

## Firebird ARRAY type

Firebird-driver supports Firebird ARRAY data type. ARRAY values are represented as
Python lists. On input, the Python sequence (list or tuple) must be nested appropriately
if the array field is multi-dimensional, and the incoming sequence must not fall short
of its maximum possible length (it will not be “padded” implicitly–see below). On output,
the lists will be nested if the database array has multiple dimensions.

!!! note

    Database arrays have no place in a purely relational data model, which requires that
    data values be atomized (that is, every value stored in the database must be reduced
    to elementary, non-decomposable parts). The Firebird implementation of database arrays,
    like that of most relational database engines that support this data type, is fraught
    with limitations.

    Database arrays are of fixed size, with a predeclared number of dimensions (max. 16)
    and number of elements per dimension. Individual array elements cannot be set to
    NULL / None, so the mapping between Python lists (which have dynamic length and are
    therefore not normally “padded” with dummy values) and non-trivial database arrays is
    clumsy.

    Stored procedures cannot have array parameters.

    Finally, many interface libraries, GUIs, and even the isql command line utility do not
    support database arrays.

    In general, it is preferable to avoid using database arrays unless you have a compelling
    reason.

**Example:**

```python
>>> from firebird.driver import connect
>>> con = connect('employee',user='sysdba', password='masterkey')
>>> cur = con.cursor()
>>> cur.execute("select LANGUAGE_REQ from job where job_code='Eng' and job_grade=3 and job_country='Japan'")
>>> cur.fetchone()
(['Japanese\n', 'Mandarin\n', 'English\n', '\n', '\n'],)

```

**Example program:**

```python
from firebird.driver import connect

arrayIn = [
    [1, 2, 3, 4],
    [5, 6, 7, 8],
    [9,10,11,12]
  ]

with connect('/temp/test.db', user='sysdba', password='pass') as con:
    con.execute_immediate("recreate table array_table (a int[3,4])")
    con.commit()

    cur = con.cursor()

    print(f"{arrayIn=}")
    cur.execute("insert into array_table values (?)", (arrayIn,))
    con.commit()

    cur.execute("select a from array_table")
    arrayOut = cur.fetchone()[0]
    print(f"{arrayOut=}")

```

Output:

```text
arrayIn=[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
arrayOut=[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]

```
