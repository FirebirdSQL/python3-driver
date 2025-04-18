# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_events.py
#   DESCRIPTION:    Tests for Firebird events
#   CREATED:        10.4.2025
#
#  Software distributed under the License is distributed AS IS,
#  WITHOUT WARRANTY OF ANY KIND, either express or implied.
#  See the License for the specific language governing rights
#  and limitations under the License.
#
#  The Original Code was created by Pavel Cisar
#
#  Copyright (c) Pavel Cisar <pcisar@users.sourceforge.net>
#  and all contributors signed below.
#
#  All Rights Reserved.
#  Contributor(s): ______________________________________.
#
# See LICENSE.TXT for details.

import time
import threading
import pytest
from firebird.driver import (create_database, DatabaseError, connect_server, ShutdownMethod,
                             ShutdownMode, PageSize)

@pytest.fixture
def event_db(fb_vars, tmp_dir):
    event_file = tmp_dir / 'fbevents.fdb'
    host = fb_vars['host']
    port = fb_vars['port']
    if host is None:
        dsn = str(event_file)
    else:
        dsn = f'{host}/{port}:{event_file}' if port else f'{host}:{event_file}'
    try:
        con = create_database(dsn)
        with con.cursor() as cur:
            cur.execute("CREATE TABLE T (PK Integer, C1 Integer)")
            cur.execute("""CREATE TRIGGER EVENTS_AU FOR T ACTIVE
BEFORE UPDATE POSITION 0
AS
BEGIN
    if (old.C1 <> new.C1) then
        post_event 'c1_updated' ;
END""")
            cur.execute("""CREATE TRIGGER EVENTS_AI FOR T ACTIVE
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
            con.commit()
        yield con
    finally:
        con.drop_database()

def test_one_event(event_db):
    def send_events(command_list):
        with event_db.cursor() as cur:
            for cmd in command_list:
                cur.execute(cmd)
            event_db.commit()

    e = {}
    timed_event = threading.Timer(3.0, send_events, args=[["insert into T (PK,C1) values (1,1)",]])
    with event_db.event_collector(['insert_1']) as events:
        timed_event.start()
        e = events.wait()
    timed_event.join()
    assert e == {'insert_1': 1}

def test_multiple_events(event_db):
    def send_events(command_list):
        with event_db.cursor() as cur:
            for cmd in command_list:
                cur.execute(cmd)
            event_db.commit()

    cmds = ["insert into T (PK,C1) values (1,1)",
            "insert into T (PK,C1) values (1,2)",
            "insert into T (PK,C1) values (1,3)",
            "insert into T (PK,C1) values (1,1)",
            "insert into T (PK,C1) values (1,2)",]
    timed_event = threading.Timer(3.0, send_events, args=[cmds])
    with event_db.event_collector(['insert_1', 'insert_3']) as events:
        timed_event.start()
        e = events.wait()
    timed_event.join()
    assert e == {'insert_3': 1, 'insert_1': 2}

def test_20_events(event_db):
    def send_events(command_list):
        with event_db.cursor() as cur:
            for cmd in command_list:
                cur.execute(cmd)
            event_db.commit()

    cmds = ["insert into T (PK,C1) values (1,1)",
            "insert into T (PK,C1) values (1,2)",
            "insert into T (PK,C1) values (1,3)",
            "insert into T (PK,C1) values (1,1)",
            "insert into T (PK,C1) values (1,2)",]
    e = {}
    timed_event = threading.Timer(1.0, send_events, args=[cmds])
    with event_db.event_collector(['insert_1', 'A', 'B', 'C', 'D',
                                 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
                                 'N', 'O', 'P', 'Q', 'R', 'insert_3']) as events:
        timed_event.start()
        time.sleep(3)
        e = events.wait()
    timed_event.join()
    assert e == {'A': 0, 'C': 0, 'B': 0, 'E': 0, 'D': 0, 'G': 0, 'insert_1': 2,
                 'I': 0, 'H': 0, 'K': 0, 'J': 0, 'M': 0, 'L': 0, 'O': 0, 'N': 0,
                 'Q': 0, 'P': 0, 'R': 0, 'insert_3': 1, 'F': 0}

def test_flush_events(event_db):
    def send_events(command_list):
        with event_db.cursor() as cur:
            for cmd in command_list:
                cur.execute(cmd)
            event_db.commit()

    timed_event = threading.Timer(3.0, send_events, args=[["insert into T (PK,C1) values (1,1)",]])
    with event_db.event_collector(['insert_1']) as events:
        send_events(["insert into T (PK,C1) values (1,1)",
                     "insert into T (PK,C1) values (1,1)"])
        time.sleep(2)
        events.flush()
        timed_event.start()
        e = events.wait()
    timed_event.join()
    assert e == {'insert_1': 1}
