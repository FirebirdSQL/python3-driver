# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_issues.py
#   DESCRIPTION:    Tests for tracker issues
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

def test_issue_02(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)', [1, None, 1])
        db_connection.commit()
        cur.execute('select C1,C2,C3 from T2 where C1 = 1')
        rows = cur.fetchall()
        assert rows == [(1, None, 1)]

def test_issue_53(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("select cast('0.00' as numeric(9,2)) from rdb$database")
        numeric_val = cur.fetchone()[0]
        numeric_val_exponent = numeric_val.as_tuple()[2]
        db_connection.commit()
        assert numeric_val_exponent == -2

def test_issue_65_prepare_ctx_mgr(db_connection):
    """Freeing a Statement via context manager must not crash when cursor/connection closes."""
    with db_connection.cursor() as cur:
        with cur.prepare('select count(*) from country where 1 < ?') as stmt:
            row = cur.execute(stmt, (2,)).fetchone()
            assert row is not None

def test_issue_65_free_then_cursor_close(db_connection):
    """Explicit stmt.free() followed by cursor.close() must not crash."""
    cur = db_connection.cursor()
    stmt = cur.prepare('select count(*) from country where 1 < ?')
    row = cur.execute(stmt, (2,)).fetchone()
    assert row is not None
    stmt.free()
    cur.close()

def test_issue_65_free_then_conn_close(dsn):
    """stmt.free() followed by connection close must not crash."""
    from firebird.driver import connect
    with connect(dsn) as conn:
        cur = conn.cursor()
        stmt = cur.prepare('select count(*) from country where 1 < ?')
        row = cur.execute(stmt, (2,)).fetchone()
        assert row is not None
        stmt.free()

def test_issue_69_gc_of_abandoned_connection(dsn):
    """A connection abandoned without close() and reclaimed by cyclic garbage
    collection must not crash in Connection.__del__ -> iAttachment.detach().

    During cyclic GC the iAttachment's own iReferenceCounted.__del__ may run
    release() (dropping its refcount to 0 and freeing the native interface)
    before Connection.__del__ calls detach(); detaching the already-released
    interface dereferences freed memory and segfaults.

    On Python builds where the access violation hard-crashes the process the
    worker dies (test fails). On builds where ctypes turns it into an
    "Exception ignored ... in __del__" the failure is delivered via
    sys.unraisablehook, which this test captures.
    """
    import gc
    import sys
    import warnings
    from firebird.driver import connect

    def abandon():
        con = connect(dsn)
        cur = con.cursor()
        cur.execute('select count(*) from country')
        cur.fetchall()
        # deliberately NO con.close(); the reference is dropped on return

    unraisable = []
    old_hook = sys.unraisablehook
    sys.unraisablehook = unraisable.append
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            for _ in range(5):
                abandon()
            gc.collect()
    finally:
        sys.unraisablehook = old_hook

    # The #69 crash is a native access violation (surfaced as OSError) escaping
    # the finalizer; on hard-crashing builds the worker dies before reaching
    # here. Other finalizer noise (e.g. a benign "invalid transaction handle"
    # DatabaseError seen on some versions) is unrelated to this issue.
    access_violations = [a for a in unraisable
                         if isinstance(a.exc_value, OSError)]
    assert not access_violations, \
        f"finalizer access violation: {[a.exc_value for a in access_violations]}"
    # The finalizer must still run and warn about the undisposed connection.
    assert any(issubclass(w.category, ResourceWarning) for w in caught)
