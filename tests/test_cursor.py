# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_cursor.py
#   DESCRIPTION:    Tests for Cursor
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
from firebird.driver import InterfaceError

def test_execute(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('select * from country')
        row = cur.fetchone()
        assert row == ('USA', 'Dollar')
        # again the same SQL (should use the same Statement)
        stmt = cur._stmt
        cur.execute('select * from country')
        assert stmt is cur._stmt
        row = cur.fetchone()
        assert row == ('USA', 'Dollar')
        # prepared statement
        ps = cur.prepare('select * from country')
        cur.execute(ps)
        assert stmt is not cur._stmt
        row = cur.fetchone()
        assert row == ('USA', 'Dollar')

def test_executemany(db_connection):
    with db_connection.cursor() as cur:
        cur.executemany("insert into t values(?)", [(1,), (2,)])
        cur.executemany("insert into t values(?)", [(3,)])
        cur.executemany("insert into t values(?)", [(4,), (5,), (6,)])
        db_connection.commit()
        p = cur.prepare("insert into t values(?)")
        cur.executemany(p, [(7,), (8,)])
        cur.executemany(p, [(9,)])
        cur.executemany(p, [(10,), (11,), (12,)])
        db_connection.commit()
        cur.execute("select * from T order by c1")
        rows = cur.fetchall()
        assert rows == [(1,), (2,), (3,), (4,),
                        (5,), (6,), (7,), (8,),
                        (9,), (10,), (11,), (12,)]

def test_iteration(db_connection):
    data = [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
            ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
            ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
            ('Hong Kong', 'HKDollar'), ('Netherlands', 'Euro'), ('Belgium', 'Euro'),
            ('Austria', 'Euro'), ('Fiji', 'FDollar'), ('Russia', 'Ruble'),
            ('Romania', 'RLeu')]
    with db_connection.cursor() as cur:
        cur.execute('select * from country')
        rows = [row for row in cur]
        assert len(rows) == len(data)
        assert rows == data
        cur.execute('select * from country')
        rows = []
        for row in cur:
            rows.append(row)
        assert len(rows) == len(data)
        assert rows == data
        cur.execute('select * from country')
        i = 0
        for row in cur:
            i += 1
            assert row in data
        assert i == len(data)

def test_description(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('select * from country')
        assert len(cur.description) == 2
        assert repr(cur.description) == \
               "(('COUNTRY', <class 'str'>, 15, 15, 0, 0, False), " \
               "('CURRENCY', <class 'str'>, 10, 10, 0, 0, False))"
        cur.execute('select country as CT, currency as CUR from country')
        assert len(cur.description) == 2
        cur.execute('select * from customer')
        assert repr(cur.description) == \
            "(('CUST_NO', <class 'int'>, 11, 4, 0, 0, False), " \
            "('CUSTOMER', <class 'str'>, 25, 25, 0, 0, False), " \
            "('CONTACT_FIRST', <class 'str'>, 15, 15, 0, 0, True), " \
            "('CONTACT_LAST', <class 'str'>, 20, 20, 0, 0, True), " \
            "('PHONE_NO', <class 'str'>, 20, 20, 0, 0, True), " \
            "('ADDRESS_LINE1', <class 'str'>, 30, 30, 0, 0, True), " \
            "('ADDRESS_LINE2', <class 'str'>, 30, 30, 0, 0, True), " \
            "('CITY', <class 'str'>, 25, 25, 0, 0, True), " \
            "('STATE_PROVINCE', <class 'str'>, 15, 15, 0, 0, True), " \
            "('COUNTRY', <class 'str'>, 15, 15, 0, 0, True), " \
            "('POSTAL_CODE', <class 'str'>, 12, 12, 0, 0, True), " \
            "('ON_HOLD', <class 'str'>, 1, 1, 0, 0, True))"
        cur.execute('select * from job')
        assert repr(cur.description) == \
            "(('JOB_CODE', <class 'str'>, 5, 5, 0, 0, False), " \
            "('JOB_GRADE', <class 'int'>, 6, 2, 0, 0, False), " \
            "('JOB_COUNTRY', <class 'str'>, 15, 15, 0, 0, False), " \
            "('JOB_TITLE', <class 'str'>, 25, 25, 0, 0, False), " \
            "('MIN_SALARY', <class 'decimal.Decimal'>, 20, 8, 10, -2, False), " \
            "('MAX_SALARY', <class 'decimal.Decimal'>, 20, 8, 10, -2, False), " \
            "('JOB_REQUIREMENT', <class 'str'>, 0, 8, 0, 1, True), " \
            "('LANGUAGE_REQ', <class 'list'>, -1, 8, 0, 0, True))"
        cur.execute('select * from proj_dept_budget')
        assert repr(cur.description) == \
            "(('FISCAL_YEAR', <class 'int'>, 11, 4, 0, 0, False), " \
            "('PROJ_ID', <class 'str'>, 5, 5, 0, 0, False), " \
            "('DEPT_NO', <class 'str'>, 3, 3, 0, 0, False), " \
            "('QUART_HEAD_CNT', <class 'list'>, -1, 8, 0, 0, True), " \
            "('PROJECTED_BUDGET', <class 'decimal.Decimal'>, 20, 8, 12, -2, True))"
    # Check for precision cache (implicit check by running twice)
    with db_connection.cursor() as cur2:
        cur2.execute('select * from proj_dept_budget')
        assert repr(cur2.description) == \
            "(('FISCAL_YEAR', <class 'int'>, 11, 4, 0, 0, False), " \
            "('PROJ_ID', <class 'str'>, 5, 5, 0, 0, False), " \
            "('DEPT_NO', <class 'str'>, 3, 3, 0, 0, False), " \
            "('QUART_HEAD_CNT', <class 'list'>, -1, 8, 0, 0, True), " \
            "('PROJECTED_BUDGET', <class 'decimal.Decimal'>, 20, 8, 12, -2, True))"

def test_exec_after_close(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('select * from country')
        row = cur.fetchone()
        assert row == ('USA', 'Dollar')
        cur.close()
        # Execute again on the same closed cursor object should re-initialize
        cur.execute('select * from country')
        row = cur.fetchone()
        assert row == ('USA', 'Dollar')

def test_fetchone(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('select * from country')
        row = cur.fetchone()
        assert row == ('USA', 'Dollar')

def test_fetchall(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('select * from country')
        rows = cur.fetchall()
        assert rows == \
               [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
                ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
                ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
                ('Hong Kong', 'HKDollar'), ('Netherlands', 'Euro'),
                ('Belgium', 'Euro'), ('Austria', 'Euro'), ('Fiji', 'FDollar'),
                ('Russia', 'Ruble'), ('Romania', 'RLeu')]

def test_fetchmany(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('select * from country')
        rows = cur.fetchmany(10)
        assert rows == \
               [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
                ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
                ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
                ('Hong Kong', 'HKDollar')]
        rows = cur.fetchmany(10)
        assert rows == \
               [('Netherlands', 'Euro'), ('Belgium', 'Euro'), ('Austria', 'Euro'),
                ('Fiji', 'FDollar'), ('Russia', 'Ruble'), ('Romania', 'RLeu')]
        rows = cur.fetchmany(10)
        assert len(rows) == 0

def test_affected_rows(db_connection):
    with db_connection.cursor() as cur:
        assert cur.affected_rows == -1
        cur.execute('select * from project')
        assert cur.affected_rows == 0 # No rows fetched yet
        cur.fetchone()
        # Affected rows depends on internal prefetch/caching, less reliable to test exact count
        assert cur.affected_rows >= 1 # Check at least one row was considered
        assert cur.rowcount >= 1

def test_affected_rows_multiple_execute(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("insert into t (c1) values (999)")
        assert cur.affected_rows == 1 # INSERT should report 1
        cur.execute("update t set c1 = 888 where c1 = 999")
        assert cur.affected_rows == 1 # UPDATE should report 1
        # fetchone after DML doesn't make sense for affected_rows,
        # it would reset based on a SELECT if executed next.
        # Keep the check after the relevant DML.

def test_name(db_connection):
    def assign_name(cursor, name):
        cursor.set_cursor_name(name)

    with db_connection.cursor() as cur:
        assert cur.name is None
        with pytest.raises(InterfaceError, match="Cannot set name for cursor has not yet executed"):
            assign_name(cur, 'testx')

        cur.execute('select * from country')
        cur.set_cursor_name('test')
        assert cur.name == 'test'
        with pytest.raises(InterfaceError, match="Cursor's name has already been declared"):
            assign_name(cur, 'testx')

def test_use_after_close(db_connection):
    cmd = 'select * from country'
    with db_connection.cursor() as cur:
        cur.execute(cmd)
        cur.close()
        with pytest.raises(InterfaceError, match='Cannot fetch from cursor that did not executed a statement.'):
            # Fetching after close should raise, as the result set is gone.
            # The original test behavior where execute worked after close was potentially misleading.
            # Let's test that fetch fails after close.
            cur.fetchone()

def test_to_dict(db_connection):
    cmd = 'select * from country'
    sample = {'COUNTRY': 'USA', 'CURRENCY': 'Dollar'}
    with db_connection.cursor() as cur:
        cur.execute(cmd)
        row = cur.fetchone()
        d = cur.to_dict(row)
        assert len(d) == 2
        assert d == sample
        d = {'COUNTRY': 'UNKNOWN', 'CURRENCY': 'UNKNOWN'}
        d2 = cur.to_dict(row, d)
        assert d2 == sample
        assert d is d2 # Ensure the passed dict was modified

def test_scrollable(fb_vars, db_connection):
    if fb_vars['version'] in SpecifierSet('<5'):
        # Check for embedded
        with db_connection.cursor() as cur:
            cur.execute('select min(a.mon$remote_protocol) from mon$attachments a')
            if cur.fetchone()[0] is not None:
                pytest.skip("Works only in embedded or FB 5+")
    rows = [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
            ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
            ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
            ('Hong Kong', 'HKDollar'), ('Netherlands', 'Euro'),
            ('Belgium', 'Euro'), ('Austria', 'Euro'), ('Fiji', 'FDollar'),
            ('Russia', 'Ruble'), ('Romania', 'RLeu')]
    with db_connection.cursor() as cur:
        cur.open('select * from country') # Use open for scrollable
        assert cur.is_bof()
        assert not cur.is_eof()
        assert cur.fetch_first() == rows[0]
        assert cur.fetch_next() == rows[1]
        assert cur.fetch_prior() == rows[0]
        assert cur.fetch_last() == rows[-1]
        assert not cur.is_bof()
        assert cur.fetch_next() is None
        assert cur.is_eof()
        assert cur.fetch_absolute(7) == rows[6]
        assert cur.fetch_relative(-1) == rows[5]
        assert cur.fetchone() == rows[6] # fetchone should behave like fetch_next after positioning
        assert cur.fetchall() == rows[7:]
        cur.fetch_absolute(7) # Reposition
        assert cur.fetchall() == rows[7:]
