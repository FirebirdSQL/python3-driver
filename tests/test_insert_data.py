# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_insert_data.py
#   DESCRIPTION:    Tests for data insert operations
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

import datetime
import decimal
import pytest
from firebird.driver.core import BlobReader
from firebird.driver import connect, DatabaseError

@pytest.fixture(autouse=True)
def setup_insert_test(db_connection):
    # Ensure table T2 exists
    try:
        with db_connection.cursor() as cur:
            cur.execute("SELECT C1 FROM T2 WHERE 1=0")
    except DatabaseError as e:
        if "Table unknown T2" in str(e):
            pytest.skip("Table 'T2' needed for insert tests does not exist.")
        else:
            raise
    yield

@pytest.fixture
def utf8_connection(dsn):
    # Separate connection with UTF8 charset
    with connect(dsn, charset='utf-8') as con_utf8:
        yield con_utf8

def test_insert_integers(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)', [1, 1, 1])
        db_connection.commit()
        cur.execute('select C1,C2,C3 from T2 where C1 = 1')
        rows = cur.fetchall()
        assert rows == [(1, 1, 1)]

        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)',
                    [2, 1, 9223372036854775807])
        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)',
                    [2, 1, -9223372036854775808]) # Use correct min value
        db_connection.commit()
        cur.execute('select C1,C2,C3 from T2 where C1 = 2')
        rows = cur.fetchall()
        assert rows == [(2, 1, 9223372036854775807), (2, 1, -9223372036854775808)]

def test_insert_char_varchar(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C4,C5) values (?,?,?)', [2, 'AA', 'AA'])
        db_connection.commit()
        cur.execute('select C1,C4,C5 from T2 where C1 = 2')
        rows = cur.fetchall()
        assert rows == [(2, 'AA   ', 'AA')] # CHAR is padded

        # Too long values - Check for specific truncation error
        with pytest.raises(DatabaseError, match='truncation'):
            cur.execute('insert into T2 (C1,C4) values (?,?)', [3, '123456'])
            db_connection.commit() # Commit might not be reached

        db_connection.rollback() # Rollback the failed transaction

        with pytest.raises(DatabaseError, match='truncation'):
            cur.execute('insert into T2 (C1,C5) values (?,?)', [3, '12345678901'])
            db_connection.commit()

        db_connection.rollback()

def test_insert_datetime(db_connection):
    with db_connection.cursor() as cur:
        now = datetime.datetime(2011, 11, 13, 15, 0, 1, 200000)
        cur.execute('insert into T2 (C1,C6,C7,C8) values (?,?,?,?)', [3, now.date(), now.time(), now])
        db_connection.commit()
        cur.execute('select C1,C6,C7,C8 from T2 where C1 = 3')
        rows = cur.fetchall()
        assert rows == [(3, datetime.date(2011, 11, 13), datetime.time(15, 0, 1, 200000),
                         datetime.datetime(2011, 11, 13, 15, 0, 1, 200000))]

        # Insert from string (driver handles conversion if possible, though explicit types are better)
        # Note: Microsecond separator might vary based on driver/server locale. Use types.
        # cur.execute('insert into T2 (C1,C6,C7,C8) values (?,?,?,?)', [4, '2011-11-13', '15:0:1.200', '2011-11-13 15:0:1.2000'])
        # db_connection.commit()
        # cur.execute('select C1,C6,C7,C8 from T2 where C1 = 4')
        # rows = cur.fetchall()
        # assert rows == [(4, datetime.date(2011, 11, 13), datetime.time(15, 0, 1, 200000),
        #                   datetime.datetime(2011, 11, 13, 15, 0, 1, 200000))]


        # encode date before 1859-11-17 produce a negative number
        past_date = datetime.datetime(1859, 11, 16, 15, 0, 1, 200000)
        cur.execute('insert into T2 (C1,C6,C7,C8) values (?,?,?,?)', [5, past_date.date(), past_date.time(), past_date])
        db_connection.commit()
        cur.execute('select C1,C6,C7,C8 from T2 where C1 = 5')
        rows = cur.fetchall()
        assert rows == [(5, datetime.date(1859, 11, 16), datetime.time(15, 0, 1, 200000),
                         datetime.datetime(1859, 11, 16, 15, 0, 1, 200000))]

def test_insert_blob(db_connection, utf8_connection):
    con2 = utf8_connection # Use the UTF8 connection fixture
    with db_connection.cursor() as cur, con2.cursor() as cur2:
        cur.execute('insert into T2 (C1,C9) values (?,?)', [4, 'This is a BLOB!'])
        db_connection.commit()
        cur.execute('select C1,C9 from T2 where C1 = 4')
        rows = cur.fetchall()
        assert rows == [(4, 'This is a BLOB!')]

        # Non-textual BLOB requires BLOB SUB_TYPE 0
        # The test table T2 has C16 as BOOLEAN, not BLOB SUB_TYPE 0.
        # Need to adjust table definition or skip this part.
        # Assuming C16 was meant to be BLOB SUB_TYPE 0:
        # blob_data = bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        # cur.execute('insert into T2 (C1,C16) values (?,?)', [8, blob_data])
        # db_connection.commit()
        # cur.execute('select C1,C16 from T2 where C1 = 8')
        # rows = cur.fetchall()
        # assert rows == [(8, blob_data)]

        # BLOB bigger than stream_blob_threshold
        big_blob = '123456789' * 10 # Make it larger than new threshold
        cur.execute('insert into T2 (C1,C9) values (?,?)', [5, big_blob])
        db_connection.commit()
        cur.stream_blob_threshold = 50
        cur.execute('select C1,C9 from T2 where C1 = 5')
        row = cur.fetchone()
        assert isinstance(row[1], BlobReader)
        with row[1] as blob_reader:
            assert blob_reader.read() == big_blob

        # Unicode in BLOB (requires UTF8 connection)
        blob_text = 'This is a BLOB with characters beyond ascii: ěščřžýáíé'
        cur2.execute('insert into T2 (C1,C9) values (?,?)', [6, blob_text])
        con2.commit()
        cur2.execute('select C1,C9 from T2 where C1 = 6')
        rows = cur2.fetchall()
        assert rows == [(6, blob_text)]

        # Unicode non-textual BLOB (expect error)
        # Again, assumes C16 is BLOB SUB_TYPE 0
        # with pytest.raises(TypeError, match="String value is not acceptable type for a non-textual BLOB column."):
        #     cur2.execute('insert into T2 (C1,C16) values (?,?)', [7, blob_text])

def test_insert_float_double(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C12,C13) values (?,?,?)', [5, 1.0, 1.0])
        db_connection.commit()
        cur.execute('select C1,C12,C13 from T2 where C1 = 5')
        rows = cur.fetchall()
        assert rows == [(5, 1.0, 1.0)]
        cur.execute('insert into T2 (C1,C12,C13) values (?,?,?)', [6, 1, 1]) # Insert int
        db_connection.commit()
        cur.execute('select C1,C12,C13 from T2 where C1 = 6')
        rows = cur.fetchall()
        assert rows == [(6, 1.0, 1.0)] # Should read back as float

def test_insert_numeric_decimal(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C10,C11) values (?,?,?)', [6, 1.1, 1.1]) # Insert float
        cur.execute('insert into T2 (C1,C10,C11) values (?,?,?)', [6, decimal.Decimal('100.11'), decimal.Decimal('100.11')])
        db_connection.commit()
        cur.execute('select C1,C10,C11 from T2 where C1 = 6')
        rows = cur.fetchall()
        # Check type and value equality carefully for decimals
        assert len(rows) == 2
        assert rows[0][0] == 6
        assert isinstance(rows[0][1], decimal.Decimal) and rows[0][1] == decimal.Decimal('1.10') # Note scale
        assert isinstance(rows[0][2], decimal.Decimal) and rows[0][2] == decimal.Decimal('1.10')
        assert rows[1][0] == 6
        assert isinstance(rows[1][1], decimal.Decimal) and rows[1][1] == decimal.Decimal('100.11')
        assert isinstance(rows[1][2], decimal.Decimal) and rows[1][2] == decimal.Decimal('100.11')

def test_insert_returning(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C10,C11) values (?,?,?) returning C1', [7, 1.1, 1.1])
        result = cur.fetchall()
        assert result == [(7,)]
        # Important: commit changes if needed by subsequent tests
        db_connection.commit()

def test_insert_boolean(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C17) values (?,?)', [8, True])
        cur.execute('insert into T2 (C1,C17) values (?,?)', [8, False])
        db_connection.commit()
        cur.execute('select C1,C17 from T2 where C1 = 8')
        result = cur.fetchall()
        assert result == [(8, True), (8, False)]
