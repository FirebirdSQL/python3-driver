# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_transaction.py
#   DESCRIPTION:    Tests for Transaction
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
from firebird.driver import (Isolation,
                             transaction, InterfaceError, TPB, TableShareMode,
                             TableAccessMode, TraInfoCode, TraInfoAccess, TraAccessMode)

def test_cursor(db_connection):
    with db_connection: # Use connection context manager
        tr = db_connection.main_transaction
        tr.begin()
        with tr.cursor() as cur:
            cur.execute("insert into t (c1) values (1)")
            tr.commit()
            cur.execute("select * from t")
            rows = cur.fetchall()
            assert rows == [(1,)]
            cur.execute("delete from t")
            tr.commit()
            assert len(tr.cursors) == 1
            assert tr.cursors[0] is cur # This checks weakref behavior, might need adjustment

def test_context_manager(db_connection):
    with db_connection.cursor() as cur:
        with transaction(db_connection):
            cur.execute("insert into t (c1) values (1)")

        cur.execute("select * from t")
        rows = cur.fetchall()
        assert rows == [(1,)]

        with pytest.raises(Exception): # Use pytest.raises
            with transaction(db_connection):
                cur.execute("delete from t")
                raise Exception("Simulating error")

        cur.execute("select * from t")
        rows = cur.fetchall()
        assert rows == [(1,)] # Should still be 1 due to rollback

        with transaction(db_connection):
            cur.execute("delete from t")

        cur.execute("select * from t")
        rows = cur.fetchall()
        assert rows == []

def test_savepoint(db_connection):
    db_connection.begin()
    tr = db_connection.main_transaction
    db_connection.execute_immediate("insert into t (c1) values (1)")
    tr.savepoint('test')
    db_connection.execute_immediate("insert into t (c1) values (2)")
    tr.rollback(savepoint='test')
    tr.commit()
    with tr.cursor() as cur:
        cur.execute("select * from t")
        rows = cur.fetchall()
    assert rows == [(1,)]

def test_fetch_after_commit(db_connection):
    db_connection.execute_immediate("insert into t (c1) values (1)")
    db_connection.commit()
    with db_connection.cursor() as cur:
        cur.execute("select * from t")
        db_connection.commit()
        with pytest.raises(InterfaceError, match='Cannot fetch from cursor that did not executed a statement.'):
            cur.fetchall()

def test_fetch_after_rollback(db_connection):
    db_connection.execute_immediate("insert into t (c1) values (1)")
    db_connection.rollback()
    with db_connection.cursor() as cur:
        cur.execute("select * from t")
        # Rollback implicitly happens if not committed when transaction ends
        # Or explicitly:
        db_connection.rollback()
        with pytest.raises(InterfaceError, match='Cannot fetch from cursor that did not executed a statement.'):
            cur.fetchall()

def test_tpb(db_connection):
    tpb_obj = TPB(isolation=Isolation.READ_COMMITTED, no_auto_undo=True)
    tpb_obj.lock_timeout = 10
    tpb_obj.reserve_table('COUNTRY', TableShareMode.PROTECTED, TableAccessMode.LOCK_WRITE)
    tpb_buffer = tpb_obj.get_buffer()

    with db_connection.transaction_manager(tpb_buffer) as tr:
        info = tr.info.get_info(TraInfoCode.ISOLATION)
        # Version check might be needed here as before
        engine_version = db_connection.info.engine_version
        if engine_version >= 4.0:
            assert info in [Isolation.READ_COMMITTED_READ_CONSISTENCY,
                            Isolation.READ_COMMITTED_RECORD_VERSION]
        else:
            assert info == Isolation.READ_COMMITTED_RECORD_VERSION
        assert tr.info.get_info(TraInfoCode.ACCESS) == TraInfoAccess.READ_WRITE
        assert tr.info.lock_timeout == 10

    del tpb_obj
    tpb_parsed = TPB()
    tpb_parsed.parse_buffer(tpb_buffer)
    assert tpb_parsed.access_mode == TraAccessMode.WRITE
    assert tpb_parsed.isolation == Isolation.READ_COMMITTED_RECORD_VERSION
    assert tpb_parsed.lock_timeout == 10
    assert not tpb_parsed.auto_commit
    assert tpb_parsed.no_auto_undo
    assert not tpb_parsed.ignore_limbo
    assert tpb_parsed._table_reservation == [('COUNTRY',
                                              TableShareMode.PROTECTED,
                                              TableAccessMode.LOCK_WRITE)]

def test_transaction_info(db_connection, db_file):
    with db_connection.main_transaction as tr:
        assert tr.is_active()
        assert str(db_file) in tr.info.database # Check fixture use
        assert tr.info.isolation == Isolation.SNAPSHOT

        assert tr.info.id > 0
        assert tr.info.oit > 0
        assert tr.info.oat > 0
        assert tr.info.ost > 0
        assert tr.info.lock_timeout == -1
        assert tr.info.isolation == Isolation.SNAPSHOT
