# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_hooks.py
#   DESCRIPTION:    Tests for hooks defined by driver
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

from functools import partial
import pytest
from firebird.base.hooks import add_hook
from firebird.driver import connect_server, connect, Connection, Server
from firebird.driver.hooks import ConnectionHook, ServerHook, hook_manager

hook_state = []

TEST_ID = '_test_id_'

def _reset_hook_state():
    hook_state.clear()
    hook_manager.remove_all_hooks()

def _hook_service_attached(svc):
    hook_state.append("Service attached")

def _hook_db_attached(con):
    hook_state.append("Database attached")

def _hook_db_closed(con):
    hook_state.append(f"Database closed: {getattr(con, TEST_ID, None)}")

def _hook_db_detach_request_a(con):
    hook_state.append(f"Database dettach request RETAIN: {getattr(con, TEST_ID, None)}")
    return True # Retain

def _hook_db_detach_request_b(con):
    hook_state.append(f"Database dettach request NO RETAIN: {getattr(con, TEST_ID, None)}")
    return False # Do not retain

def _hook_db_attach_request_a(dsn, dpb):
    hook_state.append("Database attach request NORMAL CONNECT")
    return None # Allow normal connection

def _hook_db_attach_request_b(dsn, dpb, hook_con_instance): # Pass instance via closure/partial
    # This hook needs the actual connection to return, tricky with fixtures directly
    # Option 1: Pass the created connection instance to the hook registration
    # Option 2: Create connection inside the hook (less ideal)
    hook_state.append("Database attach request PROVIDE CONNECTION")
    return hook_con_instance

@pytest.fixture
def hook_svc(fb_vars):
    with connect_server(fb_vars['host'],
                        user=fb_vars['user'],
                        password=fb_vars['password']) as svc:
        yield svc

def test_hook_db_attached(dsn):
    _reset_hook_state()
    add_hook(ConnectionHook.ATTACHED, Connection, _hook_db_attached)
    with connect(dsn) as con:
        assert len(hook_state) == 1
        assert hook_state[0] == "Database attached"

def test_hook_db_attach_request(dsn):
    _reset_hook_state()
    main_con = connect(dsn)
    add_hook(ConnectionHook.ATTACH_REQUEST, Connection, _hook_db_attach_request_a)
    with connect(dsn) as con:
        assert len(hook_state) == 1
        assert hook_state[0] == "Database attach request NORMAL CONNECT"

    add_hook(ConnectionHook.ATTACH_REQUEST, Connection, partial(_hook_db_attach_request_b,
                                                                hook_con_instance=main_con))
    con = connect(dsn)
    assert len(hook_state) == 3
    assert hook_state[2] == "Database attach request PROVIDE CONNECTION"
    assert con is main_con

def test_hook_db_closed(dsn):
    _reset_hook_state()
    with connect(dsn) as con:
        con._test_id_ = 'OUR CONENCTION'
        add_hook(ConnectionHook.CLOSED, con, _hook_db_closed)
    assert len(hook_state) == 1
    assert hook_state[0] == "Database closed: OUR CONENCTION"

def test_hook_db_detach_request(dsn):
    _reset_hook_state()
    # reject detach
    con = connect(dsn)
    con._test_id_ = 'OUR CONENCTION'
    add_hook(ConnectionHook.DETACH_REQUEST, con, _hook_db_detach_request_a)
    con.close()
    assert len(hook_state) == 1
    assert hook_state[0] == "Database dettach request RETAIN: OUR CONENCTION"
    assert not con.is_closed()

    # accept close
    _reset_hook_state()
    add_hook(ConnectionHook.DETACH_REQUEST, con, _hook_db_detach_request_b)
    con.close()
    assert len(hook_state) == 1
    assert hook_state[0] == "Database dettach request NO RETAIN: OUR CONENCTION"
    assert con.is_closed()

def test_hook_service_attached(fb_vars):
    _reset_hook_state()
    add_hook(ServerHook.ATTACHED, Server, _hook_service_attached)
    with connect_server(fb_vars['host'], user=fb_vars['user'], password=fb_vars['password']) as svc:
        assert len(hook_state) == 1
        assert hook_state[0] == "Service attached"
