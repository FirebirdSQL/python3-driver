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
from packaging.specifiers import SpecifierSet
from firebird.driver import (Isolation, connect, tpb, TransactionManager,
                             transaction, InterfaceError, TPB, TableShareMode,
                             TableAccessMode, TraInfoCode, TraInfoAccess, TraAccessMode,
                             DefaultAction)

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

def test_default_action_rollback(db_connection):
    """Verify TransactionManager closes with rollback if default_action is ROLLBACK."""
    # Ensure table is empty first
    with db_connection.cursor() as cur_clean:
        cur_clean.execute("DELETE FROM t")
        db_connection.commit()

    tr_rollback = None # Define outside 'with' to check is_closed later
    try:
        # Create manager with ROLLBACK default
        tr_rollback = db_connection.transaction_manager(default_action=DefaultAction.ROLLBACK)
        # Use context manager for the TransactionManager itself
        with tr_rollback:
            tr_rollback.begin() # Start the transaction
            with tr_rollback.cursor() as cur:
                cur.execute("insert into t (c1) values (99)")
            # Do not explicitly commit or rollback, let the 'with tr_rollback:' handle it
            assert tr_rollback.is_active()

        # Check transaction is no longer active and manager is closed
        assert not tr_rollback.is_active()
        assert tr_rollback.is_closed()

        # Verify data was rolled back using a separate transaction
        with db_connection.cursor() as cur_verify:
            cur_verify.execute("select * from t where c1 = 99")
            rows = cur_verify.fetchall()
            assert rows == []

    finally:
        # Ensure cleanup even if assertions fail
        if tr_rollback and not tr_rollback.is_closed():
            tr_rollback.close()
        # Clean up table again
        with db_connection.cursor() as cur_clean:
            cur_clean.execute("DELETE FROM t")
            db_connection.commit()

def test_connection_close_with_active_transaction(dsn, db_connection):
    """Verify transaction behavior when connection is closed while active."""
    # Ensure table is empty first
    with db_connection.cursor() as cur_clean:
        cur_clean.execute("DELETE FROM t")
        db_connection.commit()

    tr = db_connection.transaction_manager()
    tr.begin()
    with tr.cursor() as cur:
        cur.execute("insert into t (c1) values (88)")
        # Don't commit or rollback yet

    # Close the connection while transaction is active
    db_connection.close()

    # Assertions on the transaction manager state
    assert tr.is_closed(), "Transaction manager should be closed after connection close"
    assert not tr.is_active(), "Transaction should not be active after connection close"

    # Reconnect and verify data was rolled back
    with connect(dsn) as new_con:
        with new_con.cursor() as cur_verify:
            cur_verify.execute("select * from t where c1 = 88")
            rows = cur_verify.fetchall()
            assert rows == [], "Data inserted before connection close should be rolled back"

def test_complex_savepoints(db_connection):
    """Test rolling back past multiple savepoints."""
    # Ensure table is empty first
    with db_connection.cursor() as cur_clean:
        cur_clean.execute("DELETE FROM t")
        db_connection.commit()

    # Scenario 1: Rollback past multiple savepoints
    db_connection.begin()
    db_connection.savepoint('SP1')
    db_connection.execute_immediate("insert into t (c1) values (1)")
    db_connection.savepoint('SP2')
    db_connection.execute_immediate("insert into t (c1) values (2)")
    db_connection.savepoint('SP3')
    db_connection.execute_immediate("insert into t (c1) values (3)")

    # Rollback to the first savepoint
    db_connection.rollback(savepoint='SP2')

    # Commit the remaining transaction state (only includes insert 1)
    db_connection.commit()

    # Verify state
    with db_connection.cursor() as cur:
        cur.execute("select * from t order by c1")
        rows = cur.fetchall()
        assert rows == [(1,)], "Should only contain data before SP2"

    # Scenario 2: Intermediate rollbacks
    with db_connection.cursor() as cur_clean: # Reuse cursor
        cur_clean.execute("DELETE FROM t")
        db_connection.commit()

    db_connection.begin()
    db_connection.savepoint('SP_A')
    db_connection.execute_immediate("insert into t (c1) values (10)")
    db_connection.savepoint('SP_B')
    db_connection.execute_immediate("insert into t (c1) values (20)")

    # Rollback to SP_B (should effectively do nothing visible yet)
    db_connection.rollback(savepoint='SP_B')
    # Insert another value after rolling back to SP_B
    db_connection.execute_immediate("insert into t (c1) values (30)")
    db_connection.savepoint('SP_C')
    db_connection.execute_immediate("insert into t (c1) values (40)")

    # Rollback to SP_A
    db_connection.rollback(savepoint='SP_A')

    # Commit remaining transaction (should only contain insert 10)
    db_connection.commit()

    # Verify state
    with db_connection.cursor() as cur:
        cur.execute("select * from t order by c1")
        rows = cur.fetchall()
        assert rows == [], "Should only contain data before SP_A"

def test_tpb_at_snapshot_number(fb_vars, db_connection):
    """Test starting a transaction at a specific snapshot number (FB4+)."""
    if fb_vars['version'] not in SpecifierSet('>=4.0'):
        pytest.skip("Requires Firebird 4.0+ for AT SNAPSHOT NUMBER")

    # Ensure table is empty first
    with db_connection.cursor() as cur_clean:
        cur_clean.execute("DELETE FROM t")
        db_connection.commit()

    # 0. Start TR0 (normal), insert different data, commit TR0
    # This changes the *current* state of the database
    with db_connection.cursor() as cur2:
        cur2.execute("insert into t (c1) values (1)")
        db_connection.commit() # Commit TR2

    # 1. Start TR1, insert data, get snapshot number
    tr1: TransactionManager = db_connection.transaction_manager()
    tr1.begin(tpb(Isolation.SNAPSHOT)) # TR1
    snapshot_no = tr1.info.snapshot_number
    assert snapshot_no > 0
    #db_connection.commit() # Commit TR1

    # 2. Start TR2 (normal), insert different data, commit TR2
    # This changes the *current* state of the database
    with db_connection.cursor() as cur2:
        cur2.execute("insert into t (c1) values (2)")
        db_connection.commit() # Commit TR2

    # 3. Start TR3 using the snapshot number from TR1
    tr_snap: TransactionManager = None
    try:
        tr_snap = db_connection.transaction_manager()
        # Create TPB with the specific snapshot number
        tpb_snap = TPB(isolation=Isolation.SNAPSHOT, at_snapshot_number=snapshot_no)
        tr_snap.begin(tpb=tpb_snap.get_buffer())

        # 4. Select data within TR3 - should only see data from TR1's snapshot
        with tr_snap.cursor() as cur_snap:
            cur_snap.execute("select * from t order by c1")
            rows = cur_snap.fetchall()
            assert rows == [(1,)], "Transaction at snapshot should only see data from that snapshot"

        tr_snap.commit() # Commit/Rollback TR3

    finally:
        if tr_snap and not tr_snap.is_closed():
            tr_snap.close()
        # Clean up table again
        with db_connection.cursor() as cur_clean:
            cur_clean.execute("DELETE FROM t")
            db_connection.commit()
