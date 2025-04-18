# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_statement.py
#   DESCRIPTION:    Tests for Statement
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

import pytest
from firebird.driver import connect, StatementType, InterfaceError

@pytest.fixture
def two_connections(dsn):
    with connect(dsn) as con1, connect(dsn) as con2:
        yield con1, con2

def test_basic(two_connections):
    con, _ = two_connections # Unpack fixture
    assert con._statements == []
    with con.cursor() as cur:
        ps = cur.prepare('select * from country')
        assert len(con._statements) == 1
        assert ps._in_cnt == 0
        assert ps._out_cnt == 2
        assert ps.type == StatementType.SELECT
        assert ps.sql == 'select * from country'
    # Test auto-cleanup on connection close
    ps = con.cursor().prepare('select * from country')
    assert len(con._statements) == 2
    con.close()
    assert len(con._statements) == 0

def test_get_plan(two_connections):
    con, _ = two_connections
    with con.cursor() as cur:
        ps = cur.prepare('select * from job')
        assert ps.plan == "PLAN (JOB NATURAL)"
        ps.free()

def test_execution(two_connections):
    con, _ = two_connections
    with con.cursor() as cur:
        ps = cur.prepare('select * from country')
        cur.execute(ps)
        row = cur.fetchone()
        assert row == ('USA', 'Dollar')

def test_wrong_cursor(two_connections):
    con1, con2 = two_connections
    with con1.cursor() as cur1:
        with con2.cursor() as cur2:
            ps = cur1.prepare('select * from country')
            with pytest.raises(InterfaceError,
                               match='Cannot execute Statement that was created by different Connection.'):
                cur2.execute(ps)
