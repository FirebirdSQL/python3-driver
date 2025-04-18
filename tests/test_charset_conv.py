# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_charset_conv.py
#   DESCRIPTION:    Tests for Character Set conversions
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
from firebird.driver.core import BlobReader
from firebird.driver import connect, DatabaseError

@pytest.fixture
def utf8_connection(dsn):
    # Separate connection with UTF8 charset
    with connect(dsn, charset='utf-8') as con_utf8:
        yield con_utf8

@pytest.fixture(autouse=True)
def setup_charset_test(db_connection):
    # Clean tables
    with db_connection.cursor() as cur:
        cur.execute("delete from t3")
        cur.execute("delete from t4")
        db_connection.commit()
    yield

def test_octets(db_connection): # Request fixture
    bytestring = bytes([1, 2, 3, 4, 5])
    with db_connection.cursor() as cur:
        cur.execute("insert into T4 (C1, C_OCTETS, V_OCTETS) values (?,?,?)",
                    (1, bytestring, bytestring))
        db_connection.commit()
        cur.execute("select C1, C_OCTETS, V_OCTETS from T4 where C1 = 1")
        row = cur.fetchone()
        assert row == (1, b'\x01\x02\x03\x04\x05', b'\x01\x02\x03\x04\x05')

def test_utf82win1250(dsn, utf8_connection):
    s5 = 'ěščřž'
    s30 = 'ěščřžýáíéúůďťňóĚŠČŘŽÝÁÍÉÚŮĎŤŇÓ'

    # Create the win1250 connection within the test if not provided by fixture
    with connect(dsn, charset='win1250') as con1250:
        with utf8_connection.cursor() as c_utf8, con1250.cursor() as c_win1250:
            # Insert unicode data via UTF8 connection
            c_utf8.execute("insert into T4 (C1, C_WIN1250, V_WIN1250, C_UTF8, V_UTF8)"
                           "values (?,?,?,?,?)",
                           (1, s5, s30, s5, s30))
            utf8_connection.commit()

            # Read from win1250 connection
            c_win1250.execute("select C1, C_WIN1250, V_WIN1250, C_UTF8, V_UTF8 from T4 where C1 = 1")
            row_win = c_win1250.fetchone()
            # Read from utf8 connection
            c_utf8.execute("select C1, C_WIN1250, V_WIN1250, C_UTF8, V_UTF8 from T4 where C1 = 1")
            row_utf = c_utf8.fetchone()

            # Compare results - CHAR fields might be padded differently depending on charset/driver interpretation
            assert row_win[0] == 1
            assert row_utf[0] == 1
            assert row_win[1].strip() == s5 # Check content ignoring padding
            assert row_utf[1].strip() == s5
            assert row_win[2] == s30 # VARCHAR should be exact
            assert row_utf[2] == s30
            assert row_win[3].strip() == s5
            assert row_utf[3].strip() == s5
            assert row_win[4] == s30
            assert row_utf[4] == s30

def testCharVarchar(utf8_connection):
    s = 'Introdução' # Requires UTF8 connection/charset
    assert len(s) == 10
    data = tuple([1, s, s])
    with utf8_connection.cursor() as cur: # Use UTF8 connection
        cur.execute('insert into T3 (C1,C2,C3) values (?,?,?)', data)
        utf8_connection.commit()
        cur.execute('select C1,C2,C3 from T3 where C1 = 1')
        row = cur.fetchone()
        assert row[0] == 1
        assert row[1].strip() == s  # CHAR padding
        assert row[2] == s          # VARCHAR exact

def testBlob(utf8_connection):
    s = """Introdução

Este artigo descreve como você pode fazer o InterBase e o Firebird 1.5
coehabitarem pacificamente seu computador Windows. Por favor, note que esta
solução não permitirá que o Interbase e o Firebird rodem ao mesmo tempo.
Porém você poderá trocar entre ambos com um mínimo de luta. """
    assert len(s) == 292
    data = tuple([2, s])
    b_data = tuple([3, b'bytestring'])
    with utf8_connection.cursor() as cur: # Use UTF8 connection for text blob
        # Text BLOB
        cur.execute('insert into T3 (C1,C4) values (?,?)', data)
        utf8_connection.commit()
        cur.execute('select C1,C4 from T3 where C1 = 2')
        row = cur.fetchone()
        assert row == data

        # Insert Unicode into non-textual BLOB (should fail)
        with pytest.raises(TypeError, match="String value is not acceptable type for a non-textual BLOB column."):
            cur.execute('insert into T3 (C1,C5) values (?,?)', data)
            # utf8_connection.commit() # Commit likely won't be reached

        utf8_connection.rollback() # Rollback the failed attempt

        # Read binary from non-textual BLOB
        cur.execute('insert into T3 (C1,C5) values (?,?)', b_data)
        utf8_connection.commit()
        cur.execute('select C1,C5 from T3 where C1 = 3')
        row = cur.fetchone()
        assert row == b_data
