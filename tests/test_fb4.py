# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_fb4.py
#   DESCRIPTION:    Tests for Firebird 4+ features
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
from packaging.specifiers import SpecifierSet
from firebird.driver.core import BlobReader
from firebird.driver import connect, DatabaseError, get_timezone

@pytest.fixture(autouse=True)
def setup_fb4_test(db_connection, fb_vars):
    if fb_vars['version'] not in SpecifierSet('>=4'):
        pytest.skip("Requires Firebird 4.0+")
    # Ensure table exists
    try:
        with db_connection.cursor() as cur:
            # Simplified check, assume table exists if no error
            cur.execute("SELECT PK FROM FB4 WHERE 1=0")
    except DatabaseError as e:
        if "Table unknown FB4" in str(e):
            pytest.skip("Table 'FB4' needed for FB4 tests does not exist.")
        else:
            raise
    yield

def test_01_select_with_timezone_region(db_connection):
    data = {1: (2020, 1, 31, 11, 55, 35, 123400, 'Europe/Prague'),
            2: (2020, 6, 1, 1, 55, 35, 123400, 'Europe/Prague'),
            3: (2020, 12, 31, 23, 55, 35, 123400, 'Europe/Prague'),}
    with db_connection.cursor() as cur:
        cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (1, '11:55:35.1234 Europe/Prague', '2020-01-31 11:55:35.1234 Europe/Prague')")
        cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (2, '01:55:35.1234 Europe/Prague', '2020-06-01 01:55:35.1234 Europe/Prague')")
        cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (3, '23:55:35.1234 Europe/Prague', '2020-12-31 23:55:35.1234 Europe/Prague')")
        db_connection.commit()
        cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
        for pk, t_tz, ts_tz in cur:
            d = data[pk]
            assert isinstance(t_tz, datetime.time)
            assert t_tz.tzinfo is not None
            assert getattr(t_tz.tzinfo, '_timezone_') is not None
            assert t_tz.hour == d[3]
            assert t_tz.minute == d[4]
            assert t_tz.second == d[5]
            assert t_tz.microsecond == d[6]
            assert t_tz.tzinfo._timezone_ == d[7]
            #
            assert isinstance(ts_tz, datetime.datetime)
            assert ts_tz.tzinfo is not None
            assert getattr(ts_tz.tzinfo, '_timezone_') is not None
            assert ts_tz.year == d[0]
            assert ts_tz.month == d[1]
            assert ts_tz.day == d[2]
            assert ts_tz.hour == d[3]
            assert ts_tz.minute == d[4]
            assert ts_tz.second == d[5]
            assert ts_tz.microsecond == d[6]
            assert ts_tz.tzinfo._timezone_ == d[7]

def test_02_select_with_timezone_offset(db_connection):
    data = {1: (2020, 1, 31, 11, 55, 35, 123400, '+01:00'),
            2: (2020, 6, 1, 1, 55, 35, 123400, '+02:00'),
            3: (2020, 12, 31, 23, 55, 35, 123400, '+01:00'),}
    with db_connection.cursor() as cur:
        cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (1, '11:55:35.1234 +01:00', '2020-01-31 11:55:35.1234 +01:00')")
        cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (2, '01:55:35.1234 +02:00', '2020-06-01 01:55:35.1234 +02:00')")
        cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (3, '23:55:35.1234 +01:00', '2020-12-31 23:55:35.1234 +01:00')")
        db_connection.commit()
        cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
        for pk, t_tz, ts_tz in cur:
            d = data[pk]
            assert isinstance(t_tz, datetime.time)
            assert t_tz.tzinfo is not None
            assert getattr(t_tz.tzinfo, '_timezone_', None) is not None
            assert t_tz.hour == d[3]
            assert t_tz.minute == d[4]
            assert t_tz.second == d[5]
            assert t_tz.microsecond == d[6]
            assert t_tz.tzinfo._timezone_ == d[7]
            #
            assert isinstance(ts_tz, datetime.datetime)
            assert ts_tz.tzinfo is not None
            assert getattr(ts_tz.tzinfo, '_timezone_', None) is not None
            assert ts_tz.year == d[0]
            assert ts_tz.month == d[1]
            assert ts_tz.day == d[2]
            assert ts_tz.hour == d[3]
            assert ts_tz.minute == d[4]
            assert ts_tz.second == d[5]
            assert ts_tz.microsecond == d[6]
            assert ts_tz.tzinfo._timezone_ == d[7]

def test_03_insert_with_timezone_region(db_connection):
    data = {1: (2020, 1, 31, 11, 55, 35, 123400, 'Europe/Prague'),
            2: (2020, 6, 1, 1, 55, 35, 123400, 'Europe/Prague'),
            3: (2020, 12, 31, 23, 55, 35, 123400, 'Europe/Prague'),}
    with db_connection.cursor() as cur:
        for pk, d in data.items():
            zone = get_timezone(d[7])
            ts = datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5], d[6], zone)
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (?, ?, ?)", (pk, ts.timetz(), ts))
            db_connection.commit()
        cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
        for pk, t_tz, ts_tz in cur:
            d = data[pk]
            assert isinstance(t_tz, datetime.time)
            assert t_tz.tzinfo is not None
            assert getattr(t_tz.tzinfo, '_timezone_') is not None
            assert t_tz.hour == d[3]
            assert t_tz.minute == d[4]
            assert t_tz.second == d[5]
            assert t_tz.microsecond == d[6]
            assert t_tz.tzinfo._timezone_ == d[7]
            #
            assert isinstance(ts_tz, datetime.datetime)
            assert ts_tz.tzinfo is not None
            assert getattr(ts_tz.tzinfo, '_timezone_') is not None
            assert ts_tz.year == d[0]
            assert ts_tz.month == d[1]
            assert ts_tz.day == d[2]
            assert ts_tz.hour == d[3]
            assert ts_tz.minute == d[4]
            assert ts_tz.second == d[5]
            assert ts_tz.microsecond == d[6]
            assert ts_tz.tzinfo._timezone_ == d[7]

def test_04_insert_with_timezone_offset(db_connection):
    data = {1: (2020, 1, 31, 11, 55, 35, 123400, '+01:00'),
            2: (2020, 6, 1, 1, 55, 35, 123400, '+02:00'),
            3: (2020, 12, 31, 23, 55, 35, 123400, '+01:00'),}
    with db_connection.cursor() as cur:
        for pk, d in data.items():
            zone = get_timezone(d[7])
            ts = datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5], d[6], zone)
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (?, ?, ?)", (pk, ts.timetz(), ts))
            db_connection.commit()
        cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
        for pk, t_tz, ts_tz in cur:
            d = data[pk]
            assert isinstance(t_tz, datetime.time)
            assert t_tz.tzinfo is not None
            assert getattr(t_tz.tzinfo, '_timezone_') is not None
            assert t_tz.hour == d[3]
            assert t_tz.minute == d[4]
            assert t_tz.second == d[5]
            assert t_tz.microsecond == d[6]
            assert t_tz.tzinfo._timezone_ == d[7]
            #
            assert isinstance(ts_tz, datetime.datetime)
            assert ts_tz.tzinfo is not None
            assert getattr(ts_tz.tzinfo, '_timezone_') is not None
            assert ts_tz.year == d[0]
            assert ts_tz.month == d[1]
            assert ts_tz.day == d[2]
            assert ts_tz.hour == d[3]
            assert ts_tz.minute == d[4]
            assert ts_tz.second == d[5]
            assert ts_tz.microsecond == d[6]
            assert ts_tz.tzinfo._timezone_ == d[7]

def test_05_select_defloat(db_connection):
    data = {4: (decimal.Decimal('1111111111222222222233333333334444'),
                decimal.Decimal('1111111111222222'),
                decimal.Decimal('1111111111222222222233333333334444')),
            }
    with db_connection.cursor() as cur:
        cur.execute("insert into FB4 (PK,DF,DF16,DF34) values (4, 1111111111222222222233333333334444, 1111111111222222, 1111111111222222222233333333334444)")
        db_connection.commit()
        cur.execute('select PK,DF,DF16,DF34 from FB4 where PK = 4')
        for pk, df, df16, df34 in cur:
            d = data[pk]
            assert isinstance(df, decimal.Decimal)
            assert df == d[0]
            assert isinstance(df16, decimal.Decimal)
            assert df16 == d[1]
            assert isinstance(df34, decimal.Decimal)
            assert df34 == d[2]

def test_06_insert_defloat(db_connection):
    data = {4: (decimal.Decimal('1111111111222222222233333333334444'),
                decimal.Decimal('1111111111222222'),
                decimal.Decimal('1111111111222222222233333333334444')),
            }
    with db_connection.cursor() as cur:
        for pk, d in data.items():
            cur.execute("insert into FB4 (PK,DF,DF16,DF34) values (?, ?, ?, ?)", (pk, d[0], d[1], d[2]))
            db_connection.commit()
        cur.execute('select PK,DF,DF16,DF34 from FB4 where PK = 4')
        for pk, df, df16, df34 in cur:
            d = data[pk]
            assert isinstance(df, decimal.Decimal)
            assert df == d[0]
            assert isinstance(df16, decimal.Decimal)
            assert df16 == d[1]
            assert isinstance(df34, decimal.Decimal)
            assert df34 == d[2]

def test_07_select_int128(db_connection):
    data = {5: decimal.Decimal('1111111111222222222233333333.334444'),
            6: decimal.Decimal('111111111122222222223333333333.4444'),
            7: decimal.Decimal('111111111122222222223333333333.444455'),
            8: decimal.Decimal('111111111122222222223333333333.444456'),
            }
    with db_connection.cursor() as cur:
        cur.execute("insert into FB4 (PK,N128,D128) values (5, 1111111111222222222233333333.334444, 1111111111222222222233333333.334444)")
        cur.execute("insert into FB4 (PK,N128,D128) values (6, 111111111122222222223333333333.4444, 111111111122222222223333333333.4444)")
        cur.execute("insert into FB4 (PK,N128,D128) values (7, 111111111122222222223333333333.444455, 111111111122222222223333333333.444455)")
        cur.execute("insert into FB4 (PK,N128,D128) values (8, 111111111122222222223333333333.4444559, 111111111122222222223333333333.4444559)")
        db_connection.commit()
        cur.execute('select PK,N128,D128 from FB4 where PK between 5 and 8 order by pk')
        for pk, n128, d128 in cur:
            d = data[pk]
            assert isinstance(n128, decimal.Decimal)
            assert n128 == d
            assert isinstance(d128, decimal.Decimal)
            assert d128 == d

def test_08_insert_int128(db_connection):
    data = {5: (decimal.Decimal('1111111111222222222233333333.334444'),decimal.Decimal('1111111111222222222233333333.334444')),
            6: (decimal.Decimal('111111111122222222223333333333.4444'),decimal.Decimal('111111111122222222223333333333.4444')),
            7: (decimal.Decimal('111111111122222222223333333333.444455'),decimal.Decimal('111111111122222222223333333333.444455')),
            8: (decimal.Decimal('111111111122222222223333333333.4444559'),decimal.Decimal('111111111122222222223333333333.444456')),
            }
    with db_connection.cursor() as cur:
        for pk, d in data.items():
            cur.execute("insert into FB4 (PK,N128,D128) values (?, ?, ?)", (pk, d[0], d[0]))
            db_connection.commit()
        cur.execute('select PK,N128,D128 from FB4 where PK between 5 and 8 order by pk')
        for pk, n128, d128 in cur:
            d = data[pk]
            assert isinstance(n128, decimal.Decimal)
            assert n128 == d[1]
            assert isinstance(d128, decimal.Decimal)
            assert d128 == d[1]

def test_09_array_defloat(db_connection):
    d_df = [decimal.Decimal('1111111111222222222233333333334444'),
           decimal.Decimal('1111111111222222222233333333334445')]
    d_df16 = [decimal.Decimal('1111111111222222'),
             decimal.Decimal('1111111111222223')]
    d_df34 = [decimal.Decimal('1111111111222222222233333333334444'),
             decimal.Decimal('1111111111222222222233333333334445')]
    data = {9: (d_df, d_df16, d_df34),
            }
    with db_connection.cursor() as cur:
        for pk, d in data.items():
            cur.execute("insert into FB4 (PK,ADF,ADF16,ADF34) values (?, ?, ?, ?)", (pk, d[0], d[1], d[2]))
            db_connection.commit()
        cur.execute('select PK,ADF,ADF16,ADF34 from FB4 where PK = 9')
        for pk, adf, adf16, adf34 in cur:
            d = data[pk]
            assert isinstance(adf, list)
            for v in adf:
                assert isinstance(v, decimal.Decimal)
            assert adf == d_df
            assert isinstance(adf16, list)
            for v in adf16:
                assert isinstance(v, decimal.Decimal)
            assert adf16 == d_df16
            assert isinstance(adf34, list)
            for v in adf34:
                assert isinstance(v, decimal.Decimal)
            assert adf34 == d_df34

def test_10_array_int128(db_connection):
    d_int128 = [decimal.Decimal('1111111111222222222233333333.334444'),
                decimal.Decimal('1111111111222222222233333333.334444')]
    data = {11: (d_int128)}
    with db_connection.cursor() as cur:
        for pk, d in data.items():
            cur.execute("insert into FB4 (PK,AN128,AD128) values (?, ?, ?)", (pk, d, d))
            db_connection.commit()
        cur.execute('select PK,AN128,AD128 from FB4 where PK = 11 order by pk')
        for pk, an128, ad128 in cur:
            d = data[pk]
            assert isinstance(an128, list)
            for v in an128:
                assert isinstance(v, decimal.Decimal)
            assert an128 == d
            assert isinstance(ad128, list)
            for v in ad128:
                assert isinstance(v, decimal.Decimal)
            assert ad128 == d

def test_11_array_time_tz(db_connection):
    data = [(2020, 1, 31, 11, 55, 35, 123400, 'Europe/Prague'),
            (2020, 6, 1, 1, 55, 35, 123400, 'Europe/Prague')]
    pk = 11
    ar_data = []
    with db_connection.cursor() as cur:
        for d in data:
            zone = get_timezone(d[7])
            ts = datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5], d[6], zone)
            ar_data.append(ts.timetz())
        cur.execute("insert into FB4 (PK,AT_TZ) values (?, ?)", (pk, ar_data))
        cur.execute(f'select AT_TZ from FB4 where PK = {pk}')
        for row in cur:
            for d, t_tz in zip(data, row[0]):
                assert isinstance(t_tz, datetime.time)
                assert t_tz.tzinfo is not None
                assert getattr(t_tz.tzinfo, '_timezone_') is not None
                assert t_tz.hour == d[3]
                assert t_tz.minute == d[4]
                assert t_tz.second == d[5]
                assert t_tz.microsecond == d[6]
                assert t_tz.tzinfo._timezone_ == d[7]

def test_12_array_timestamp_tz(db_connection):
    data = [(2020, 1, 31, 11, 55, 35, 123400, 'Europe/Prague'),
            (2020, 6, 1, 1, 55, 35, 123400, 'Europe/Prague')]
    pk = 12
    ar_data = []
    with db_connection.cursor() as cur:
        for d in data:
            zone = get_timezone(d[7])
            ts = datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5], d[6], zone)
            ar_data.append(ts)
        cur.execute("insert into FB4 (PK,ATS_TZ) values (?, ?)", (pk, ar_data))
        cur.execute(f'select ATS_TZ from FB4 where PK = {pk}')
        for row in cur:
            for d, ts_tz in zip(data, row[0]):
                assert isinstance(ts_tz, datetime.datetime)
                assert ts_tz.tzinfo is not None
                assert getattr(ts_tz.tzinfo, '_timezone_') is not None
                assert ts_tz.year == d[0]
                assert ts_tz.month == d[1]
                assert ts_tz.day == d[2]
                assert ts_tz.hour == d[3]
                assert ts_tz.minute == d[4]
                assert ts_tz.second == d[5]
                assert ts_tz.microsecond == d[6]
                assert ts_tz.tzinfo._timezone_ == d[7]
