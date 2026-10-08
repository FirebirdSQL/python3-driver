# Database Events

## What they are
The Firebird engine features a distributed, inter-process communication mechanism based on
messages called `database events`. A database event is a message passed from a trigger or
stored procedure to an application to announce the occurrence of a specified condition or
action, usually a database change such as an insertion, modification, or deletion of a record.
The Firebird event mechanism enables applications to respond to actions and database changes
made by other, concurrently running applications without the need for those applications to
communicate directly with one another, and without incurring the expense of CPU time
required for periodic polling to determine if an event has occurred.

## Why use them
Anything that can be accomplished with database events can also be implemented using other
techniques, so why bother with events? Since you’ve chosen to write database-centric programs
in Python rather than assembly language, you probably already know the answer to this question,
but let’s illustrate.

A typical application for database events is the handling of administrative messages.
Suppose you have an administrative message database with a `message's` table, into which
various applications insert timestamped status reports. It may be desirable to react to
these messages in diverse ways, depending on the status they indicate: to ignore them, to
initiate the update of dependent databases upon their arrival, to forward them by e-mail
to a remote administrator, or even to set off an alarm so that on-site administrators will
know a problem has occurred.

It is undesirable to tightly couple the program whose status is being reported
(the `message producer`) to the program that handles the status reports (the `message handler`).
There are obvious losses of flexibility in doing so. For example, the message producer may
run on a separate machine from the administrative message database and may lack access rights
to the downstream reporting facilities (e.g., network access to the SMTP server, in the case
of forwarded e-mail notifications). Additionally, the actions required to handle status
reports may themselves be time-consuming and error-prone, as in accessing a remote network
to transmit e-mail.

In the absence of database event support, the message handler would probably be implemented
via `polling`. Polling is simply the repetition of a check for a condition at a specified
interval. In this case, the message handler would check in an infinite loop to see whether
the most recent record in the `messages` table was more recent than the last message it had
handled. If so, it would handle the fresh message(s); if not, it would go to sleep for
a specified interval, then loop.

The `polling-based` implementation of the message handler is fundamentally flawed. Polling
is a form of [busy-wait](http://www.catb.org/jargon/html/B/busy-wait.html); the check for new messages is performed at the specified interval,
regardless of the actual activity level of the message producers. If the polling interval
is lengthy, messages might not be handled within a reasonable time period after their arrival;
if the polling interval is brief, the message handler program (and there may be many such
programs) will waste a large amount of CPU time on unnecessary checks.

The database server is necessarily aware of the exact moment when a new message arrives.
Why not let the message handler program request that the database server send it a notification
when a new message arrives? The message handler can then efficiently sleep until the moment
its services are needed. Under this `event-based` scheme, the message handler becomes
aware of new messages at the instant they arrive, yet it does not waste CPU time checking
in vain for new messages when there are none available.

## How events are exposed

1. Server Process ("An event just occurred!")

    To notify any interested listeners that a specific event has
    occurred, issue the `POST_EVENT` statement from Stored Procedure
    or Trigger. The `POST_EVENT` statement has one parameter: the name
    of the event to post. In the preceding example of the administrative
    message database, `POST_EVENT` might be used from an `after insert`
    trigger on the `messages` table, like this:

    ```sql
    create trigger trig_messages_handle_insert
      for messages
        after insert
    as
    begin
      POST_EVENT 'new_message';
    end

    ```

    !!! note
        The physical notification of the client process does not

        occur until the transaction in which the `POST_EVENT` took place is
        actually committed. Therefore, multiple events may *conceptually*
        occur before the client process is *physically* informed of even one
        occurrence. Furthermore, the database engine makes no guarantee that
        clients will be informed of events in the same groupings in which they
        conceptually occurred. If, within a single transaction, an event named
        `event_a` is posted once and an event named `event_b` is posted once,
        the client may receive those posts in separate "batches", despite the
        fact that they occurred in the same conceptual unit (a single
        transaction). This also applies to multiple occurrences of *the same*
        event within a single conceptual unit: the physical notifications may
        arrive at the client separately.

1. Client Process ("Send me a message when an event occurs.")

    !!! note
        If you don't care about the gory details of event notification,

        skip to the [Python event API](#api-for-python-developers).

    The Firebird C client library offers two forms of event notification.
    The first form is *synchronous* notification, by way of the function
    `isc_wait_for_event()`. This form is admirably simple for a C programmer
    to use, but is inappropriate as a basis for firebird-driver's event support,
    chiefly because it's not sophisticated enough to serve as the basis for
    a comfortable Python-level API. The other form of event notification
    offered by the database client library is *asynchronous*, by way of the
    functions `isc_que_events()` (note that the name of that function
    is misspelled), `isc_cancel_events()`, and others. The details are
    as nasty as they are numerous, but the essence of using asynchronous
    notification from C is as follows:

   1. Call `isc_event_block()` to create a formatted binary buffer that will tell
      the server which events the client wants to listen for.
   1. Call `isc_que_events()` (passing the buffer created in the previous step) to
      inform the server that the client is ready to receive event notifications, and provide
      a callback that will be asynchronously invoked when one or more of the registered events occurs.
   1. [The thread that called `isc_que_events()` to initiate event listening must
      now do something else.]
   1. When the callback is invoked (the database client library starts a thread dedicated
      to this purpose), it can use the `isc_event_counts()` function to determine
      how many times each of the registered events has occurred since the last call to
      `isc_event_counts()` (if any).
   1. [The callback thread should now "do its thing", which may include communicating with
      the thread that called `isc_que_events()`.]
   1. When the callback thread is finished handling an event notification, it must call
      `isc_que_events()` again in order to receive future notifications. Future
      notifications will invoke the callback again, effectively "looping" the callback
      thread back to Step 4.

## API for Python developers

The Firebird-driver database event API is comprised of the following: the method
[`Connection.event_collector()`](../ref-core.md#firebird.driver.core.Connection.event_collector) and the class [`EventCollector`](../ref-core.md#firebird.driver.core.EventCollector).

Use the [`Connection.event_collector()`](../ref-core.md#firebird.driver.core.Connection.event_collector) method (takes a sequence of string event
names as parameter) to create [`EventCollector`](../ref-core.md#firebird.driver.core.EventCollector) instance, that collects database event
notifications sent from the server for given database.

!!! important

    To start listening for events it's necessary to call [`EventCollector.begin()`](../ref-core.md#firebird.driver.core.EventCollector.begin)
    method or use EventCollector's context manager interface.

Immediately when [`begin()`](../ref-core.md#firebird.driver.core.EventCollector.begin) method is called, EventCollector starts
to accumulate notifications of any event that occur within the collector’s internal queue
until the collector is closed either explicitly (via the [`close()`](../ref-core.md#firebird.driver.core.EventCollector.close)
method) or implicitly (via garbage collection).

Notifications about events are aquired through call to [`wait()`](../ref-core.md#firebird.driver.core.EventCollector.wait) method,
that blocks the calling thread until at least one of the events occurs, or the specified
`timeout` (if any) expires, and returns `None` if the wait timed out, or a dictionary that
maps `event_name -> event_occurrence_count`.

!!! important

    [`EventCollector`](../ref-core.md#firebird.driver.core.EventCollector) can act as context manager that ensures execution of
    [`begin()`](../ref-core.md#firebird.driver.core.EventCollector.begin) and [`close()`](../ref-core.md#firebird.driver.core.EventCollector.close) methods.
    It's strongly advised to use the [`EventCollector`](../ref-core.md#firebird.driver.core.EventCollector) with the `with` statement.

**Example:**

```python
with connection.event_collector(['event_a', 'event_b']) as collector:
    events = collector.wait()
    process_events(events)

```

If you want to drop notifications accumulated so far by conduit, call
[`EventCollector.flush()`](../ref-core.md#firebird.driver.core.EventCollector.flush) method.

**Example program:**

```python
from firebird.driver import create_database, transaction
import threading
import time

# Prepare database
con = create_database('event-test', user='SYSDBA', password='masterkey')
with transaction(con):
    con.execute_immediate("CREATE TABLE T (PK Integer, C1 Integer)")
    con.execute_immediate("""CREATE TRIGGER EVENTS_AU FOR T ACTIVE
    BEFORE UPDATE POSITION 0
    AS
    BEGIN
       if (old.C1 <> new.C1) then
          post_event 'c1_updated' ;
    END""")
    con.execute_immediate("""CREATE TRIGGER EVENTS_AI FOR T ACTIVE
    AFTER INSERT POSITION 0
    AS
    BEGIN
       if (new.c1 = 1) then
         post_event 'insert_1' ;
       else if (new.c1 = 2) then
         post_event 'insert_2' ;
       else if (new.c1 = 3) then
         post_event 'insert_3' ;
       else
         post_event 'insert_other' ;
    END""")
cur = con.cursor()

# Utility function
def send_events(command_list):
    with transaction(con):
        for cmd in command_list:
            cur.execute(cmd)

print("One event")
#      =========
timed_event = threading.Timer(3.0,send_events,args=[["insert into T (PK,C1) values (1,1)",]])
with con.event_collector(['insert_1']) as events:
    timed_event.start()
    e = events.wait()
print(e)

print("Multiple events")
#      ===============
cmds = ["insert into T (PK,C1) values (1,1)",
        "insert into T (PK,C1) values (1,2)",
        "insert into T (PK,C1) values (1,3)",
        "insert into T (PK,C1) values (1,1)",
        "insert into T (PK,C1) values (1,2)",]
timed_event = threading.Timer(3.0,send_events,args=[cmds])
with con.event_collector(['insert_1','insert_3']) as events:
    timed_event.start()
    e = events.wait()
print(e)

print("20 events")
#      =========
cmds = ["insert into T (PK,C1) values (1,1)",
        "insert into T (PK,C1) values (1,2)",
        "insert into T (PK,C1) values (1,3)",
        "insert into T (PK,C1) values (1,1)",
        "insert into T (PK,C1) values (1,2)",]
timed_event = threading.Timer(1.0,send_events,args=[cmds])
with con.event_collector(['insert_1','A','B','C','D',
                          'E','F','G','H','I','J','K','L','M',
                          'N','O','P','Q','R','insert_3']) as events:
    timed_event.start()
    time.sleep(3)
    e = events.wait()
print(e)

print("Flush events")
#      ============
timed_event = threading.Timer(3.0,send_events,args=[["insert into T (PK,C1) values (1,1)",]])
with con.event_collector(['insert_1']) as events:
    send_events(["insert into T (PK,C1) values (1,1)",
                 "insert into T (PK,C1) values (1,1)"])
    time.sleep(2)
    events.flush()
    timed_event.start()
    e = events.wait()
print(e)

# Finalize
con.drop_database()
con.close()

```

Output:

```text
One event
{'insert_1': 1}
Multiple events
{'insert_3': 1, 'insert_1': 2}
20 events
{'A': 0, 'C': 0, 'B': 0, 'E': 0, 'D': 0, 'G': 0, 'insert_1': 2, 'I': 0, 'H': 0, 'K': 0, 'J': 0, 'M': 0,
 'L': 0, 'O': 0, 'N': 0, 'Q': 0, 'P': 0, 'R': 0, 'insert_3': 1, 'F': 0}
Flush events
{'insert_1': 1}

```
