#coding:utf-8
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           test/driver.py
#   DESCRIPTION:    Unit tests for firebird.driver
#   CREATED:        21.3.2020
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
#  Contributor(s): Philippe Makowski <pmakowski@ibphoenix.fr>
#                  ______________________________________.
#
# See LICENSE.TXT for details.

import unittest
import datetime
from firebird.driver import *
import firebird.driver as driver
import sys, os
import threading
import time
import decimal
from re import finditer

from io import StringIO, BytesIO

FB30 = '3.0'

# Default server host
#FBTEST_HOST = ''
FBTEST_HOST = 'localhost'
# Default user
FBTEST_USER = 'SYSDBA'
# Default user password
FBTEST_PASSWORD = 'masterkey'

def linesplit_iter(string):
    return (m.group(2) for m in finditer('((.*)\n|(.+)$)', string))

def iter_class_properties(cls):
    """Iterator function.

    Args:
        cls (class): Class object.

    Yields:
        `name', 'property` pairs for all properties in class.
"""
    for varname in vars(cls):
        value = getattr(cls, varname)
        if isinstance(value, property):
            yield varname, value

def iter_class_variables(cls):
    """Iterator function.

    Args:
        cls (class): Class object.

    Yields:
        Names of all non-callable attributes in class.
"""
    for varname in vars(cls):
        value = getattr(cls, varname)
        if not (isinstance(value, property) or callable(value)) and not varname.startswith('_'):
            yield varname


class DriverTestBase(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.output = StringIO()
    def setUp(self) -> None:
        with connect_service(host=FBTEST_HOST, user=FBTEST_USER, password=FBTEST_PASSWORD) as svc:
            self.version = svc.version
        if self.version.startswith(FB30):
            self.FBTEST_DB = 'fbtest30.fdb'
            self.version = FB30
        else:
            raise Exception("Unsupported Firebird version (%s)" % self.version)
        #
        self.cwd = os.getcwd()
        self.dbpath = self.cwd if os.path.split(self.cwd)[1] == 'test' \
            else os.path.join(self.cwd, 'test')
    def clear_output(self) -> None:
        self.output.close()
        self.output = StringIO()
    def show_output(self) -> None:
        sys.stdout.write(self.output.getvalue())
        sys.stdout.flush()
    def printout(self, text: str = '', newline: bool = True, no_rstrip: bool = False) -> None:
        if no_rstrip:
            self.output.write(text)
        else:
            self.output.write(text.rstrip())
        if newline:
            self.output.write('\n')
        self.output.flush()
    def printData(self, cur, print_header=True):
        """Print data from open cursor to stdout."""
        if print_header:
            # Print a header.
            line = []
            for fieldDesc in cur.description:
                line.append(fieldDesc[DESCRIPTION_NAME].ljust(fieldDesc[DESCRIPTION_DISPLAY_SIZE]))
            self.printout(' '.join(line))
            line = []
            for fieldDesc in cur.description:
                line.append("-" * max((len(fieldDesc[DESCRIPTION_NAME]), fieldDesc[DESCRIPTION_DISPLAY_SIZE])))
            self.printout(' '.join(line))
        # For each row, print the value of each field left-justified within
        # the maximum possible width of that field.
        fieldIndices = range(len(cur.description))
        for row in cur:
            line = []
            for fieldIndex in fieldIndices:
                fieldValue = str(row[fieldIndex])
                fieldMaxWidth = max((len(cur.description[fieldIndex][DESCRIPTION_NAME]), cur.description[fieldIndex][DESCRIPTION_DISPLAY_SIZE]))
                line.append(fieldValue.ljust(fieldMaxWidth))
            self.printout(' '.join(line))

class TestCreateDrop(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, 'droptest.fdb')
        if os.path.exists(self.dbfile):
            os.remove(self.dbfile)
    def test_create_drop(self):
        with create_database(host=FBTEST_HOST, database=self.dbfile,
                             user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.sql_dialect, 3)
            self.assertEqual(con.charset, None)
            con.drop_database()
        #
        with create_database(host=FBTEST_HOST, port=3050, database=self.dbfile,
                             user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.sql_dialect, 3)
            self.assertEqual(con.charset, None)
            con.drop_database()
        #
        with create_database(host=FBTEST_HOST, database=self.dbfile,
                             user=FBTEST_USER, password=FBTEST_PASSWORD,
                             sql_dialect=1, charset='UTF8') as con:
            self.assertEqual(con.sql_dialect, 1)
            self.assertEqual(con.charset, 'UTF8')
            con.drop_database()

class TestConnection(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
    def tearDown(self):
        pass
    def test_connect(self):
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIsNotNone(con._att)
            dpb = [1, 0x1c, len(FBTEST_USER)]
            dpb.extend(ord(x) for x in FBTEST_USER)
            dpb.extend((0x1d, len(FBTEST_PASSWORD)))
            dpb.extend(ord(x) for x in FBTEST_PASSWORD)
            dpb.extend((ord('?'), 4, 3, 0, 0, 0))
            self.assertEqual(con._dpb, bytes(dpb))
        with connect(database=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIsNotNone(con._att)
        with connect(port=3050, database=self.dbfile,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIsNotNone(con._att)
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD,
                     no_gc=1, no_db_triggers=1) as con:
            dpb.extend([types.DPBItem.NO_GARBAGE_COLLECT, 4, 1, 0, 0, 0])
            dpb.extend([types.DPBItem.NO_DB_TRIGGERS, 4, 1, 0, 0, 0])
            self.assertEqual(con._dpb, bytes(dpb))
        # UTF-8 filenames (FB 2.5+)
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD, utf8filename=True) as con:
            self.assertIsNotNone(con._att)
            dpb = [1, 0x1c, len(FBTEST_USER)]
            dpb.extend(ord(x) for x in FBTEST_USER)
            dpb.extend((0x1d, len(FBTEST_PASSWORD)))
            dpb.extend(ord(x) for x in FBTEST_PASSWORD)
            dpb.extend((ord('?'), 4, 3, 0, 0, 0))
            dpb.extend((77, 4, 1, 0, 0, 0))
            self.assertEqual(con._dpb, bytes(dpb))
        # protocols
        with connect(protocol=NetProtocol.INET, database=self.dbfile,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIsNotNone(con._att)
    def test_properties(self):
        with connect(database=self.dbfile, host=FBTEST_HOST,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIn('Firebird', con.server_version)
            self.assertIn('Firebird', con.firebird_version)
            self.assertIsInstance(con.version, str)
            self.assertGreaterEqual(con.engine_version, 2.0)
            self.assertGreaterEqual(con.ods, 11.0)
            #self.assertIsNone(con.group)
            self.assertIsNone(con.charset)
            self.assertEqual(len(con.transactions), 2)
            self.assertIn(con.main_transaction, con.transactions)
            self.assertIn(con.query_transaction, con.transactions)
            self.assertEqual(con.default_tpb, ISOLATION_READ_COMMITED)
            self.assertFalse(con.is_closed())
            #
            self.assertEqual(con.sql_dialect, 3)
            self.assertEqual(con.page_size, 8192)
            self.assertGreater(con.attachment_id, 0)
            self.assertEqual(con.database_sql_dialect, 3)
            self.assertEqual(con.database_name, self.dbfile)
            self.assertIsInstance(con.site_name, str)
            self.assertIsInstance(con.implementation_id, int)
            self.assertIsInstance(con.provider_id, int)
            self.assertIsInstance(con.db_class_id, int)
            self.assertIsInstance(con.creation_date, datetime.date)
            self.assertGreaterEqual(con.ods_version, 11)
            self.assertGreaterEqual(con.ods_minor_version, 0)
            self.assertGreaterEqual(con.page_cache_size, 75)
            self.assertEqual(con.pages_allocated, 367)
            self.assertIn(con.pages_used, [332, 329, 343])
            self.assertIn(con.pages_free, [35, 38, 24])
            self.assertEqual(con.sweep_interval, 20000)
            self.assertTrue(con.space_reservation)
            self.assertTrue(con.forced_writes)
            self.assertIsInstance(con.io_stats, dict)
            self.assertGreaterEqual(con.max_memory, con.current_memory)
            self.assertLessEqual(con.oit, con.oat)
            self.assertLessEqual(con.oit, con.ost)
            self.assertLessEqual(con.oit, con.next_transaction)
            self.assertLessEqual(con.oat, con.next_transaction)
            self.assertLessEqual(con.ost, con.next_transaction)
            #
            self.assertIsInstance(con.is_compressed(), bool)
            self.assertIsInstance(con.is_encrypted(), bool)
    def test_connect_role(self):
        rolename = 'role'
        with connect(dsn=self.dbfile, user=FBTEST_USER,
                     password=FBTEST_PASSWORD, role=rolename) as con:
            self.assertIsNotNone(con._att)
            dpb = [1, 0x1c, len(FBTEST_USER)]
            dpb.extend(ord(x) for x in FBTEST_USER)
            dpb.extend((0x1d, len(FBTEST_PASSWORD)))
            dpb.extend(ord(x) for x in FBTEST_PASSWORD)
            dpb.extend((ord('<'), len(rolename)))
            dpb.extend(ord(x) for x in rolename)
            dpb.extend((ord('?'), 4, 3, 0, 0, 0))
            self.assertEqual(con._dpb, bytes(dpb))
    def test_transaction(self):
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIsNotNone(con.main_transaction)
            self.assertFalse(con.main_transaction.is_active())
            self.assertFalse(con.main_transaction.is_closed())
            self.assertEqual(con.main_transaction.default_action, DefaultAction.COMMIT)
            #self.assertEqual(len(con.main_transaction._connections), 1)
            self.assertEqual(con.main_transaction._connection(), con)
            con.begin()
            self.assertFalse(con.main_transaction.is_closed())
            con.commit()
            self.assertFalse(con.main_transaction.is_active())
            con.begin()
            con.rollback()
            self.assertFalse(con.main_transaction.is_active())
            con.begin()
            con.commit(retaining=True)
            self.assertTrue(con.main_transaction.is_active())
            con.rollback(retaining=True)
            self.assertTrue(con.main_transaction.is_active())
            tr = con.create_transaction()
            self.assertIsInstance(tr, driver.core.Transaction)
            self.assertFalse(con.main_transaction.is_closed())
            self.assertEqual(len(con.transactions), 3)
            tr.begin()
            self.assertFalse(tr.is_closed())
            con.begin()
            con.close()
            self.assertFalse(con.main_transaction.is_active())
            self.assertTrue(con.main_transaction.is_closed())
            self.assertFalse(tr.is_active())
            self.assertTrue(tr.is_closed())
    def test_execute_immediate(self):
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            #con.execute_immediate("recreate table t (c1 integer)")
            #con.commit()
            con.execute_immediate("delete from t")
            con.commit()
    def test_database_info(self):
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con._database_info(DbInfoCode.DB_READ_ONLY, driver.types.InfoItemType.INTEGER), 0)
            self.assertEqual(con._database_info(DbInfoCode.PAGE_SIZE, driver.types.InfoItemType.INTEGER), 8192)
            self.assertEqual(con._database_info(DbInfoCode.DB_SQL_DIALECT, driver.types.InfoItemType.INTEGER), 3)
    def test_db_info(self):
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            with con.create_transaction() as t1, con.create_transaction() as t2:
                self.assertListEqual(con.get_info(DbInfoCode.ACTIVE_TRANSACTIONS),
                                     [t1.transaction_id, t2.transaction_id])
            #
            self.assertEqual(len(con.get_page_contents(0)), con.page_size)
            #
            res = con.get_info([DbInfoCode.PAGE_SIZE, DbInfoCode.DB_READ_ONLY,
                               DbInfoCode.DB_SQL_DIALECT, DbInfoCode.USER_NAMES])
            self.assertDictEqual(res, {53: {'SYSDBA': 1}, 62: 3, 14: 8192, 63: 0})
            res = con.get_info(DbInfoCode.READ_SEQ_COUNT)
            self.assertDictEqual(res, {0: 106, 1: 2})
            #
            self.assertIsInstance(con.get_info(DbInfoCode.ALLOCATION), int)
            self.assertIsInstance(con.get_info(DbInfoCode.BASE_LEVEL), int)
            res = con.get_info(DbInfoCode.DB_ID)
            self.assertIsInstance(res, tuple)
            self.assertEqual(res[0].upper(), self.dbfile.upper())
            res = con.get_info(DbInfoCode.IMPLEMENTATION_OLD)
            self.assertIsInstance(res, tuple)
            self.assertEqual(len(res), 2)
            self.assertIsInstance(res[0], int)
            self.assertIsInstance(res[1], int)
            self.assertNotEqual(IMPLEMENTATION_NAMES.get(res[0], 'Unknown'), 'Unknown')
            self.assertIn('Firebird', con.get_info(DbInfoCode.VERSION))
            self.assertIn('Firebird', con.get_info(DbInfoCode.FIREBIRD_VERSION))
            self.assertIn(con.get_info(DbInfoCode.NO_RESERVE), (0, 1))
            self.assertIn(con.get_info(DbInfoCode.FORCED_WRITES), (0, 1))
            self.assertIsInstance(con.get_info(DbInfoCode.BASE_LEVEL), int)
            self.assertIsInstance(con.get_info(DbInfoCode.ODS_VERSION), int)
            self.assertIsInstance(con.get_info(DbInfoCode.ODS_MINOR_VERSION), int)
    def test_info_attributes(self):
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertGreater(con.attachment_id, 0)
            self.assertEqual(con.sql_dialect, 3)
            self.assertEqual(con.database_sql_dialect, 3)
            self.assertEqual(con.database_name.upper(), self.dbfile.upper())
            self.assertIsInstance(con.site_name, str)
            self.assertIn(con.implementation_id, IMPLEMENTATION_NAMES.keys())
            self.assertIn(con.provider_id, PROVIDER_NAMES.keys())
            self.assertIn(con.db_class_id, DB_CLASS_NAMES.keys())
            self.assertIsInstance(con.creation_date, datetime.datetime)
            self.assertIn(con.page_size, [4096, 8192, 16384])
            self.assertEqual(con.sweep_interval, 20000)
            self.assertTrue(con.space_reservation)
            self.assertTrue(con.forced_writes)
            self.assertGreater(con.current_memory, 0)
            self.assertGreater(con.max_memory, 0)
            self.assertGreater(con.oit, 0)
            self.assertGreater(con.oat, 0)
            self.assertGreater(con.ost, 0)
            self.assertGreater(con.next_transaction, 0)
            self.assertFalse(con.is_read_only())
            #
            io = con.io_stats
            self.assertEqual(len(io), 4)
            self.assertIsInstance(io, dict)
            s = con.get_table_access_stats()
            self.assertEqual(len(s), 6)
            self.assertIsInstance(s[0], driver.types.TableAccessStats)
            #
            with con.create_transaction() as t1, con.create_transaction() as t2:
                self.assertListEqual(con.get_active_transaction_ids(),
                                     [t1.transaction_id, t2.transaction_id])
                self.assertEqual(con.get_active_transaction_count(), 2)


class TestTransaction(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        #self.con.execute_immediate("recreate table t (c1 integer)")
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_cursor(self):
        tr = self.con.main_transaction
        tr.begin()
        cur = tr.cursor()
        cur.execute("insert into t (c1) values (1)")
        tr.commit()
        cur.execute("select * from t")
        rows = cur.fetchall()
        self.assertListEqual(rows, [(1,)])
        cur.execute("delete from t")
        tr.commit()
        self.assertEqual(len(tr.cursors), 1)
        self.assertIs(tr.cursors[0], cur)
    def test_context_manager(self):
        cur = self.con.cursor()
        with transaction(self.con):
            cur.execute("insert into t (c1) values (1)")

        cur.execute("select * from t")
        rows = cur.fetchall()
        self.assertListEqual(rows, [(1,)])

        try:
            with transaction(self.con):
                cur.execute("delete from t")
                raise Exception()
        except Exception as e:
            pass

        cur.execute("select * from t")
        rows = cur.fetchall()
        self.assertListEqual(rows, [(1,)])

        with transaction(self.con):
            cur.execute("delete from t")

        cur.execute("select * from t")
        rows = cur.fetchall()
        self.assertListEqual(rows, [])
    def test_savepoint(self):
        self.con.begin()
        tr = self.con.main_transaction
        self.con.execute_immediate("insert into t (c1) values (1)")
        tr.savepoint('test')
        self.con.execute_immediate("insert into t (c1) values (2)")
        tr.rollback(savepoint='test')
        tr.commit()
        cur = tr.cursor()
        cur.execute("select * from t")
        rows = cur.fetchall()
        self.assertListEqual(rows, [(1,)])
    def test_fetch_after_commit(self):
        self.con.execute_immediate("insert into t (c1) values (1)")
        self.con.commit()
        cur = self.con.cursor()
        cur.execute("select * from t")
        self.con.commit()
        with self.assertRaises(InterfaceError) as cm:
            rows = cur.fetchall()
        self.assertTupleEqual(cm.exception.args, ('Cannot fetch from cursor that did not executed a statement.',))
    def test_fetch_after_rollback(self):
        self.con.execute_immediate("insert into t (c1) values (1)")
        self.con.rollback()
        cur = self.con.cursor()
        cur.execute("select * from t")
        self.con.commit()
        with self.assertRaises(InterfaceError) as cm:
            rows = cur.fetchall()
        self.assertTupleEqual(cm.exception.args, ('Cannot fetch from cursor that did not executed a statement.',))
    def test_tpb(self):
        tpb = TPB(isolation=Isolation.READ_COMMITTED,
                         no_auto_undo=True)
        tpb.lock_timeout = 10
        tpb.reserve_table('COUNTRY', TableShareMode.PROTECTED, TableAccessMode.LOCK_WRITE)
        tpb_buffer = tpb.get_buffer()
        with self.con.create_transaction(tpb_buffer) as tr:
            info = tr.get_info(TraInfoCode.ISOLATION)
            self.assertEqual(info[0], TraInfoIsolation.READ_COMMITTED)
            self.assertEqual(info[1], TraInfoReadCommitted.RECORD_VERSION)
            self.assertEqual(tr.get_info(TraInfoCode.ACCESS), TraInfoAccess.READ_WRITE)
            self.assertEqual(tr.lock_timeout, 10)
        del tpb
        tpb = TPB()
        tpb.parse_buffer(tpb_buffer)
        self.assertEqual(tpb.access_mode, AccessMode.WRITE)
        self.assertEqual(tpb.isolation, Isolation.READ_COMMITTED)
        self.assertEqual(tpb.read_committed, ReadCommitted.RECORD_VERSION)
        self.assertEqual(tpb.lock_resolution, LockResolution.WAIT)
        self.assertEqual(tpb.lock_timeout, 10)
        self.assertFalse(tpb.auto_commit)
        self.assertTrue(tpb.no_auto_undo)
        self.assertFalse(tpb.ignore_limbo)
        self.assertListEqual(tpb._table_reservation, [('COUNTRY',
                                                       TableShareMode.PROTECTED,
                                                       TableAccessMode.LOCK_WRITE)])
    def test_transaction_info(self):
        self.con.begin()
        with self.con.main_transaction as tr:
            info = tr.get_info(TraInfoCode.ISOLATION)
            self.assertEqual(info[0], TraInfoIsolation.READ_COMMITTED)
            self.assertEqual(info[1], TraInfoReadCommitted.RECORD_VERSION)
            #
            self.assertGreater(tr.transaction_id, 0)
            self.assertGreater(tr.oit, 0)
            self.assertGreater(tr.oat, 0)
            self.assertGreater(tr.ost, 0)
            self.assertEqual(tr.lock_timeout, -1)
            self.assertTupleEqual(tr.isolation, (TraInfoIsolation.READ_COMMITTED,
                                                 TraInfoReadCommitted.RECORD_VERSION))

class TestDistributedTransaction(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.db1 = os.path.join(self.dbpath, 'fbtest-1.fdb')
        self.db2 = os.path.join(self.dbpath, 'fbtest-2.fdb')
        self.con1 = create_database(host=FBTEST_HOST, database=self.db1,
                                    user=FBTEST_USER,
                                    password=FBTEST_PASSWORD, overwrite=True)
        self.con1.execute_immediate("recreate table T (PK integer, C1 integer)")
        self.con1.commit()
        self.con2 = create_database(host=FBTEST_HOST, database=self.db2,
                                    user=FBTEST_USER,
                                    password=FBTEST_PASSWORD, overwrite=True)
        self.con2.execute_immediate("recreate table T (PK integer, C1 integer)")
        self.con2.commit()
    def tearDown(self):
        #if self.con1 and self.con1.group:
            ## We can't drop database via connection in group
            #self.con1.group.disband()
        if not self.con1:
            self.con1 = connect(host=FBTEST_HOST, database=self.db1,
                                user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con1.drop_database()
        self.con1.close()
        if not self.con2:
            self.con2 = connect(host=FBTEST_HOST, database=self.db2,
                                user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con2.drop_database()
        self.con2.close()
    def test_context_manager(self):
        self.skipTest('Not implemented yet')
        cg = ConnectionGroup((self.con1, self.con2))

        q = 'select * from T order by pk'
        c1 = cg.cursor(self.con1)
        cc1 = self.con1.cursor()
        p1 = cc1.prep(q)

        c2 = cg.cursor(self.con2)
        cc2 = self.con2.cursor()
        p2 = cc2.prep(q)

        # Distributed transaction: COMMIT
        with cg:
            c1.execute('insert into t (pk) values (1)')
            c2.execute('insert into t (pk) values (1)')

        self.con1.commit()
        cc1.execute(p1)
        result = cc1.fetchall()
        self.assertListEqual(result, [(1, None)])
        self.con2.commit()
        cc2.execute(p2)
        result = cc2.fetchall()
        self.assertListEqual(result, [(1, None)])

        # Distributed transaction: ROLLBACK
        try:
            with cg:
                c1.execute('insert into t (pk) values (2)')
                c2.execute('insert into t (pk) values (2)')
                raise Exception()
        except Exception as e:
            pass

        c1.execute(q)
        result = c1.fetchall()
        self.assertListEqual(result, [(1, None)])
        c2.execute(q)
        result = c2.fetchall()
        self.assertListEqual(result, [(1, None)])

        cg.disband()

    def test_simple_dt(self):
        self.skipTest('Not implemented yet')
        cg = ConnectionGroup((self.con1, self.con2))
        self.assertEqual(self.con1.group, cg)
        self.assertEqual(self.con2.group, cg)

        q = 'select * from T order by pk'
        c1 = cg.cursor(self.con1)
        cc1 = self.con1.cursor()
        p1 = cc1.prep(q)

        c2 = cg.cursor(self.con2)
        cc2 = self.con2.cursor()
        p2 = cc2.prep(q)

        # Distributed transaction: COMMIT
        c1.execute('insert into t (pk) values (1)')
        c2.execute('insert into t (pk) values (1)')
        cg.commit()

        self.con1.commit()
        cc1.execute(p1)
        result = cc1.fetchall()
        self.assertListEqual(result, [(1, None)])
        self.con2.commit()
        cc2.execute(p2)
        result = cc2.fetchall()
        self.assertListEqual(result, [(1, None)])

        # Distributed transaction: PREPARE+COMMIT
        c1.execute('insert into t (pk) values (2)')
        c2.execute('insert into t (pk) values (2)')
        cg.prepare()
        cg.commit()

        self.con1.commit()
        cc1.execute(p1)
        result = cc1.fetchall()
        self.assertListEqual(result, [(1, None), (2, None)])
        self.con2.commit()
        cc2.execute(p2)
        result = cc2.fetchall()
        self.assertListEqual(result, [(1, None), (2, None)])

        # Distributed transaction: SAVEPOINT+ROLLBACK to it
        c1.execute('insert into t (pk) values (3)')
        cg.savepoint('CG_SAVEPOINT')
        c2.execute('insert into t (pk) values (3)')
        cg.rollback(savepoint='CG_SAVEPOINT')

        c1.execute(q)
        result = c1.fetchall()
        self.assertListEqual(result, [(1, None), (2, None), (3, None)])
        c2.execute(q)
        result = c2.fetchall()
        self.assertListEqual(result, [(1, None), (2, None)])

        # Distributed transaction: ROLLBACK
        cg.rollback()

        self.con1.commit()
        cc1.execute(p1)
        result = cc1.fetchall()
        self.assertListEqual(result, [(1, None), (2, None)])
        self.con2.commit()
        cc2.execute(p2)
        result = cc2.fetchall()
        self.assertListEqual(result, [(1, None), (2, None)])

        # Distributed transaction: EXECUTE_IMMEDIATE
        cg.execute_immediate('insert into t (pk) values (3)')
        cg.commit()

        self.con1.commit()
        cc1.execute(p1)
        result = cc1.fetchall()
        self.assertListEqual(result, [(1, None), (2, None), (3, None)])
        self.con2.commit()
        cc2.execute(p2)
        result = cc2.fetchall()
        self.assertListEqual(result, [(1, None), (2, None), (3, None)])

        cg.disband()
        self.assertIsNone(self.con1.group)
        self.assertIsNone(self.con2.group)
    def test_limbo_transactions(self):
        self.skipTest('Not implemented yet')
        return
        cg = ConnectionGroup((self.con1, self.con2))
        svc = connect_service(host=FBTEST_HOST, password=FBTEST_PASSWORD)

        ids1 = svc.get_limbo_transaction_ids(self.db1)
        self.assertEqual(ids1, [])
        ids2 = svc.get_limbo_transaction_ids(self.db2)
        self.assertEqual(ids2, [])

        cg.execute_immediate('insert into t (pk) values (3)')
        cg.prepare()

        # Force out both connections
        self.con1._set_group(None)
        cg._cons.remove(self.con1)
        del self.con1
        self.con1 = None

        self.con2._set_group(None)
        cg._cons.remove(self.con2)
        del self.con2
        self.con2 = None

        # Disband will raise an error
        with self.assertRaises(DatabaseError) as cm:
            cg.disband()
        self.assertTupleEqual(cm.exception.args,
                              ('Error while rolling back transaction:\n- SQLCODE: -901\n- invalid transaction handle (expecting explicit transaction start)', -901, 335544332))

        ids1 = svc.get_limbo_transaction_ids(self.db1)
        id1 = ids1[0]
        ids2 = svc.get_limbo_transaction_ids(self.db2)
        id2 = ids2[0]

        # Data chould be blocked by limbo transaction
        if not self.con1:
            self.con1 = connect(dsn=self.db1, user=FBTEST_USER,
                                password=FBTEST_PASSWORD)
        if not self.con2:
            self.con2 = connect(dsn=self.db2, user=FBTEST_USER,
                                password=FBTEST_PASSWORD)
        c1 = self.con1.cursor()
        c1.execute('select * from t')
        with self.assertRaises(DatabaseError) as cm:
            row = c1.fetchall()
        self.assertTupleEqual(cm.exception.args,
                              ('Cursor.fetchone:\n- SQLCODE: -911\n- record from transaction %i is stuck in limbo' % id1, -911, 335544459))
        c2 = self.con2.cursor()
        c2.execute('select * from t')
        with self.assertRaises(DatabaseError) as cm:
            row = c2.fetchall()
        self.assertTupleEqual(cm.exception.args,
                              ('Cursor.fetchone:\n- SQLCODE: -911\n- record from transaction %i is stuck in limbo' % id2, -911, 335544459))

        # resolve via service
        svc = connect_service(host=FBTEST_HOST, password=FBTEST_PASSWORD)
        svc.commit_limbo_transaction(self.db1, id1)
        svc.rollback_limbo_transaction(self.db2, id2)

        # check the resolution
        c1 = self.con1.cursor()
        c1.execute('select * from t')
        row = c1.fetchall()
        self.assertListEqual(row, [(3, None)])
        c2 = self.con2.cursor()
        c2.execute('select * from t')
        row = c2.fetchall()
        self.assertListEqual(row, [])

        svc.close()

class TestCursor(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        #self.con.execute_immediate("recreate table t (c1 integer primary key)")
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_execute(self):
        cur = self.con.cursor()
        cur.execute('select * from country')
        row = cur.fetchone()
        self.assertTupleEqual(row, ('USA', 'Dollar'))
        # again the same SQL (should use the same Statement)
        stmt = cur._stmt
        cur.execute('select * from country')
        self.assertIs(stmt, cur._stmt)
        row = cur.fetchone()
        self.assertTupleEqual(row, ('USA', 'Dollar'))
        # prepared statement
        ps = cur.prepare('select * from country')
        cur.execute(ps)
        self.assertIsNot(stmt, cur._stmt)
        row = cur.fetchone()
        self.assertTupleEqual(row, ('USA', 'Dollar'))
    def test_executemany(self):
        cur = self.con.cursor()
        cur.executemany("insert into t values(?)", [(1,), (2,)])
        cur.executemany("insert into t values(?)", [(3,)])
        cur.executemany("insert into t values(?)", [(4,), (5,), (6,)])
        self.con.commit()
        p = cur.prepare("insert into t values(?)")
        cur.executemany(p, [(7,), (8,)])
        cur.executemany(p, [(9,)])
        cur.executemany(p, [(10,), (11,), (12,)])
        self.con.commit()
        cur.execute("select * from T order by c1")
        rows = cur.fetchall()
        self.assertListEqual(rows, [(1,), (2,), (3,), (4,),
                                    (5,), (6,), (7,), (8,),
                                    (9,), (10,), (11,), (12,)])
    def test_iteration(self):
        data = [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
                ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
                ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
                ('Hong Kong', 'HKDollar'), ('Netherlands', 'Euro'), ('Belgium', 'Euro'),
                ('Austria', 'Euro'), ('Fiji', 'FDollar'), ('Russia', 'Ruble'),
                ('Romania', 'RLeu')]
        cur = self.con.cursor()
        cur.execute('select * from country')
        rows = [row for row in cur]
        self.assertEqual(len(rows), len(data))
        self.assertListEqual(rows, data)
        cur.execute('select * from country')
        rows = []
        for row in cur:
            rows.append(row)
        self.assertEqual(len(rows), len(data))
        self.assertListEqual(rows, data)
        cur.execute('select * from country')
        i = 0
        for row in cur:
            i += 1
            self.assertIn(row, data)
        self.assertEqual(i, len(data))
    def test_description(self):
        cur = self.con.cursor()
        cur.execute('select * from country')
        self.assertEqual(len(cur.description), 2)
        self.assertEqual(repr(cur.description),
                         "(('COUNTRY', <class 'str'>, 15, 15, 0, 0, False), " \
                         "('CURRENCY', <class 'str'>, 10, 10, 0, 0, False))")
        cur.execute('select country as CT, currency as CUR from country')
        self.assertEqual(len(cur.description), 2)
        cur.execute('select * from customer')
        self.assertEqual(repr(cur.description),
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
                         "('ON_HOLD', <class 'str'>, 1, 1, 0, 0, True))")
        cur.execute('select * from job')
        self.assertEqual(repr(cur.description),
                         "(('JOB_CODE', <class 'str'>, 5, 5, 0, 0, False), " \
                         "('JOB_GRADE', <class 'int'>, 6, 2, 0, 0, False), " \
                         "('JOB_COUNTRY', <class 'str'>, 15, 15, 0, 0, False), " \
                         "('JOB_TITLE', <class 'str'>, 25, 25, 0, 0, False), " \
                         "('MIN_SALARY', <class 'decimal.Decimal'>, 20, 8, 10, -2, False), " \
                         "('MAX_SALARY', <class 'decimal.Decimal'>, 20, 8, 10, -2, False), " \
                         "('JOB_REQUIREMENT', <class 'str'>, 0, 8, 0, 1, True), " \
                         "('LANGUAGE_REQ', <class 'list'>, -1, 8, 0, 0, True))")
        cur.execute('select * from proj_dept_budget')
        self.assertEqual(repr(cur.description),
                         "(('FISCAL_YEAR', <class 'int'>, 11, 4, 0, 0, False), " \
                         "('PROJ_ID', <class 'str'>, 5, 5, 0, 0, False), " \
                         "('DEPT_NO', <class 'str'>, 3, 3, 0, 0, False), " \
                         "('QUART_HEAD_CNT', <class 'list'>, -1, 8, 0, 0, True), " \
                         "('PROJECTED_BUDGET', <class 'decimal.Decimal'>, 20, 8, 12, -2, True))")
        # Check for precision cache
        cur2 = self.con.cursor()
        cur2.execute('select * from proj_dept_budget')
        self.assertEqual(repr(cur2.description),
                         "(('FISCAL_YEAR', <class 'int'>, 11, 4, 0, 0, False), " \
                         "('PROJ_ID', <class 'str'>, 5, 5, 0, 0, False), " \
                         "('DEPT_NO', <class 'str'>, 3, 3, 0, 0, False), " \
                         "('QUART_HEAD_CNT', <class 'list'>, -1, 8, 0, 0, True), " \
                         "('PROJECTED_BUDGET', <class 'decimal.Decimal'>, 20, 8, 12, -2, True))")
    def test_exec_after_close(self):
        cur = self.con.cursor()
        cur.execute('select * from country')
        row = cur.fetchone()
        self.assertTupleEqual(row, ('USA', 'Dollar'))
        cur.close()
        cur.execute('select * from country')
        row = cur.fetchone()
        self.assertTupleEqual(row, ('USA', 'Dollar'))
    def test_fetchone(self):
        cur = self.con.cursor()
        cur.execute('select * from country')
        row = cur.fetchone()
        self.assertTupleEqual(row, ('USA', 'Dollar'))
    def test_fetchall(self):
        cur = self.con.cursor()
        cur.execute('select * from country')
        rows = cur.fetchall()
        self.assertListEqual(rows,
                             [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
                              ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
                              ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
                              ('Hong Kong', 'HKDollar'), ('Netherlands', 'Euro'),
                              ('Belgium', 'Euro'), ('Austria', 'Euro'), ('Fiji', 'FDollar'),
                              ('Russia', 'Ruble'), ('Romania', 'RLeu')])
    def test_fetchmany(self):
        cur = self.con.cursor()
        cur.execute('select * from country')
        rows = cur.fetchmany(10)
        self.assertListEqual(rows,
                             [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
                              ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
                              ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
                              ('Hong Kong', 'HKDollar')])
        rows = cur.fetchmany(10)
        self.assertListEqual(rows,
                             [('Netherlands', 'Euro'), ('Belgium', 'Euro'), ('Austria', 'Euro'),
                              ('Fiji', 'FDollar'), ('Russia', 'Ruble'), ('Romania', 'RLeu')])
        rows = cur.fetchmany(10)
        self.assertEqual(len(rows), 0)
    #def test_fetchonemap(self):
        #cur = self.con.cursor()
        #cur.execute('select * from country')
        #row = cur.fetchonemap()
        #self.assertListEqual(row.items(), [('COUNTRY', 'USA'), ('CURRENCY', 'Dollar')])
    #def test_fetchallmap(self):
        #cur = self.con.cursor()
        #cur.execute('select * from country')
        #rows = cur.fetchallmap()
        #self.assertListEqual([row.items() for row in rows],
                             #[[('COUNTRY', 'USA'), ('CURRENCY', 'Dollar')],
                              #[('COUNTRY', 'England'), ('CURRENCY', 'Pound')],
                              #[('COUNTRY', 'Canada'), ('CURRENCY', 'CdnDlr')],
                              #[('COUNTRY', 'Switzerland'), ('CURRENCY', 'SFranc')],
                              #[('COUNTRY', 'Japan'), ('CURRENCY', 'Yen')],
                              #[('COUNTRY', 'Italy'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'France'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Germany'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Australia'), ('CURRENCY', 'ADollar')],
                              #[('COUNTRY', 'Hong Kong'), ('CURRENCY', 'HKDollar')],
                              #[('COUNTRY', 'Netherlands'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Belgium'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Austria'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Fiji'), ('CURRENCY', 'FDollar')],
                              #[('COUNTRY', 'Russia'), ('CURRENCY', 'Ruble')],
                              #[('COUNTRY', 'Romania'), ('CURRENCY', 'RLeu')]])
    #def test_fetchmanymap(self):
        #cur = self.con.cursor()
        #cur.execute('select * from country')
        #rows = cur.fetchmanymap(10)
        #self.assertListEqual([row.items() for row in rows],
                             #[[('COUNTRY', 'USA'), ('CURRENCY', 'Dollar')],
                              #[('COUNTRY', 'England'), ('CURRENCY', 'Pound')],
                              #[('COUNTRY', 'Canada'), ('CURRENCY', 'CdnDlr')],
                              #[('COUNTRY', 'Switzerland'), ('CURRENCY', 'SFranc')],
                              #[('COUNTRY', 'Japan'), ('CURRENCY', 'Yen')],
                              #[('COUNTRY', 'Italy'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'France'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Germany'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Australia'), ('CURRENCY', 'ADollar')],
                              #[('COUNTRY', 'Hong Kong'), ('CURRENCY', 'HKDollar')]])
        #rows = cur.fetchmanymap(10)
        #self.assertListEqual([row.items() for row in rows],
                             #[[('COUNTRY', 'Netherlands'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Belgium'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Austria'), ('CURRENCY', 'Euro')],
                              #[('COUNTRY', 'Fiji'), ('CURRENCY', 'FDollar')],
                              #[('COUNTRY', 'Russia'), ('CURRENCY', 'Ruble')],
                              #[('COUNTRY', 'Romania'), ('CURRENCY', 'RLeu')]])
        #rows = cur.fetchmany(10)
        #self.assertEqual(len(rows), 0)
    def test_affected_rows(self):
        cur = self.con.cursor()
        self.assertEqual(cur.affected_rows, -1)
        cur.execute('select * from project')
        self.assertEqual(cur.affected_rows, 0)
        cur.fetchone()
        rcount = 1 if FBTEST_HOST == '' else 6
        self.assertEqual(cur.affected_rows, rcount)
    def test_name(self):
        def assign_name():
            cur.set_cursor_name('testx')
        cur = self.con.cursor()
        self.assertIsNone(cur.name)
        self.assertRaises(InterfaceError, assign_name)
        cur.execute('select * from country')
        cur.set_cursor_name('test')
        self.assertEqual(cur.name, 'test')
        self.assertRaises(InterfaceError, assign_name)
    def test_use_after_close(self):
        cmd = 'select * from country'
        cur = self.con.cursor()
        cur.execute(cmd)
        cur.close()
        with self.assertRaises(InterfaceError) as cm:
            row = cur.fetchone()
        self.assertTupleEqual(cm.exception.args, ('Cannot fetch from cursor that did not executed a statement.',))

class TestScrollableCursor(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        #self.con.execute_immediate("recreate table t (c1 integer primary key)")
        #self.con.execute_immediate("delete from t")
        #self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_scrollable(self):
        rows = [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
                ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
                ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
                ('Hong Kong', 'HKDollar'), ('Netherlands', 'Euro'),
                ('Belgium', 'Euro'), ('Austria', 'Euro'), ('Fiji', 'FDollar'),
                ('Russia', 'Ruble'), ('Romania', 'RLeu')]
        cur = self.con.cursor()
        cur.open('select * from country')
        self.assertTrue(cur.is_bof())
        self.assertFalse(cur.is_eof())
        self.assertTupleEqual(cur.fetch_first(), rows[0])
        self.assertTupleEqual(cur.fetch_next(), rows[1])
        self.assertTupleEqual(cur.fetch_prior(), rows[0])
        self.assertTupleEqual(cur.fetch_last(), rows[-1])
        self.assertFalse(cur.is_bof())
        self.assertIsNone(cur.fetch_next())
        self.assertTrue(cur.is_eof())
        self.assertTupleEqual(cur.fetch_absolute(7), rows[6])
        self.assertTupleEqual(cur.fetch_relative(-1), rows[5])
        self.assertTupleEqual(cur.fetchone(), rows[6])
        self.assertListEqual(cur.fetchall(), rows[7:])
        cur.fetch_absolute(7)
        self.assertListEqual(cur.fetchall(), rows[7:])

class TestPreparedStatement(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con2 = connect(host=FBTEST_HOST, database=self.dbfile,
                            user=FBTEST_USER, password=FBTEST_PASSWORD)
        #self.con.execute_immediate("recreate table t (c1 integer)")
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
        self.con2.close()
    def test_basic(self):
        cur = self.con.cursor()
        ps = cur.prepare('select * from country')
        self.assertEqual(ps._in_cnt, 0)
        self.assertEqual(ps._out_cnt, 2)
        self.assertEqual(ps.type, StatementType.SELECT)
        self.assertEqual(ps.sql, 'select * from country')
    def test_get_plan(self):
        cur = self.con.cursor()
        ps = cur.prepare('select * from job')
        self.assertEqual(ps.plan, "PLAN (JOB NATURAL)")
    def test_execution(self):
        cur = self.con.cursor()
        ps = cur.prepare('select * from country')
        cur.execute(ps)
        row = cur.fetchone()
        self.assertTupleEqual(row, ('USA', 'Dollar'))
    def test_wrong_cursor(self):
        cur = self.con.cursor()
        cur2 = self.con2.cursor()
        ps = cur.prepare('select * from country')
        with self.assertRaises(InterfaceError) as cm:
            cur2.execute(ps)
        self.assertTupleEqual(cm.exception.args,
                              ('Cannot execute Statement that was created by different Connection.',))


class TestArrays(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        tbl = """recreate table AR (c1 integer,
                                    c2 integer[1:4,0:3,1:2],
                                    c3 varchar(15)[0:5,1:2],
                                    c4 char(5)[5],
                                    c5 timestamp[2],
                                    c6 time[2],
                                    c7 decimal(10,2)[2],
                                    c8 numeric(10,2)[2],
                                    c9 smallint[2],
                                    c10 bigint[2],
                                    c11 float[2],
                                    c12 double precision[2],
                                    c13 decimal(10,1)[2],
                                    c14 decimal(10,5)[2],
                                    c15 decimal(18,5)[2]
                                    )
"""
        #
        self.c2 = [[[1, 1], [2, 2], [3, 3], [4, 4]], [[5, 5], [6, 6], [7, 7], [8, 8]], [[9, 9], [10, 10], [11, 11], [12, 12]], [[13, 13], [14, 14], [15, 15], [16, 16]]]
        self.c3 = [['a', 'a'], ['bb', 'bb'], ['ccc', 'ccc'], ['dddd', 'dddd'], ['eeeee', 'eeeee'], ['fffffff78901234', 'fffffff78901234']]
        self.c4 = ['a    ', 'bb   ', 'ccc  ', 'dddd ', 'eeeee']
        self.c5 = [datetime.datetime(2012, 11, 22, 12, 8, 24, 4748), datetime.datetime(2012, 11, 22, 12, 8, 24, 4748)]
        self.c6 = [datetime.time(12, 8, 24, 4748), datetime.time(12, 8, 24, 4748)]
        self.c7 = [decimal.Decimal('10.22'), decimal.Decimal('100000.33')]
        self.c8 = [decimal.Decimal('10.22'), decimal.Decimal('100000.33')]
        self.c9 = [1, 0]
        self.c10 = [5555555, 7777777]
        self.c11 = [3.140000104904175, 3.140000104904175]
        self.c12 = [3.14, 3.14]
        self.c13 = [decimal.Decimal('10.2'), decimal.Decimal('100000.3')]
        self.c14 = [decimal.Decimal('10.22222'), decimal.Decimal('100000.333')]
        self.c15 = [decimal.Decimal('1000000000000.22222'), decimal.Decimal('1000000000000.333')]
        self.c16 = [True, False, True]
        #self.con.execute_immediate(tbl)
        self.con.execute_immediate("delete from AR where c1>=100")
        self.con.commit()
        #cur = self.con.cursor()
        #cur.execute("insert into ar (c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11,c12) values (1,?,?,?,?,?,?,?,?,?,?,?)",
                    #[self.c2,self.c3,self.c4,self.c5,self.c6,self.c7,self.c8,self.c9,
                        #self.c10,self.c11,self.c12])
        #cur.execute("insert into ar (c1,c2) values (2,?)",[self.c2])
        #cur.execute("insert into ar (c1,c3) values (3,?)",[self.c3])
        #cur.execute("insert into ar (c1,c4) values (4,?)",[self.c4])
        #cur.execute("insert into ar (c1,c5) values (5,?)",[self.c5])
        #cur.execute("insert into ar (c1,c6) values (6,?)",[self.c6])
        #cur.execute("insert into ar (c1,c7) values (7,?)",[self.c7])
        #cur.execute("insert into ar (c1,c8) values (8,?)",[self.c8])
        #cur.execute("insert into ar (c1,c9) values (9,?)",[self.c9])
        #cur.execute("insert into ar (c1,c10) values (10,?)",[self.c10])
        #cur.execute("insert into ar (c1,c11) values (11,?)",[self.c11])
        #cur.execute("insert into ar (c1,c12) values (12,?)",[self.c12])
        #cur.execute("insert into ar (c1,c13) values (13,?)",[self.c13])
        #cur.execute("insert into ar (c1,c14) values (14,?)",[self.c14])
        #cur.execute("insert into ar (c1,c15) values (15,?)",[self.c15])
        #self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_basic(self):
        cur = self.con.cursor()
        cur.execute("select LANGUAGE_REQ from job "\
                    "where job_code='Eng' and job_grade=3 and job_country='Japan'")
        row = cur.fetchone()
        self.assertTupleEqual(row,
                              (['Japanese\n', 'Mandarin\n', 'English\n', '\n', '\n'],))
        cur.execute('select QUART_HEAD_CNT from proj_dept_budget')
        row = cur.fetchall()
        self.assertListEqual(row,
                             [([1, 1, 1, 0],), ([3, 2, 1, 0],), ([0, 0, 0, 1],), ([2, 1, 0, 0],),
                              ([1, 1, 0, 0],), ([1, 1, 0, 0],), ([1, 1, 1, 1],), ([2, 3, 2, 1],),
                              ([1, 1, 2, 2],), ([1, 1, 1, 2],), ([1, 1, 1, 2],), ([4, 5, 6, 6],),
                              ([2, 2, 0, 3],), ([1, 1, 2, 2],), ([7, 7, 4, 4],), ([2, 3, 3, 3],),
                              ([4, 5, 6, 6],), ([1, 1, 1, 1],), ([4, 5, 5, 3],), ([4, 3, 2, 2],),
                              ([2, 2, 2, 1],), ([1, 1, 2, 3],), ([3, 3, 1, 1],), ([1, 1, 0, 0],)])
    def test_read_full(self):
        with self.con.cursor() as cur:
            cur.execute("select c1,c2 from ar where c1=2")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c2)
            cur.execute("select c1,c3 from ar where c1=3")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c3)
            cur.execute("select c1,c4 from ar where c1=4")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c4)
            cur.execute("select c1,c5 from ar where c1=5")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c5)
            cur.execute("select c1,c6 from ar where c1=6")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c6)
            cur.execute("select c1,c7 from ar where c1=7")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c7)
            cur.execute("select c1,c8 from ar where c1=8")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c8)
            cur.execute("select c1,c9 from ar where c1=9")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c9)
            cur.execute("select c1,c10 from ar where c1=10")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c10)
            cur.execute("select c1,c11 from ar where c1=11")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c11)
            cur.execute("select c1,c12 from ar where c1=12")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c12)
            cur.execute("select c1,c13 from ar where c1=13")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c13)
            cur.execute("select c1,c14 from ar where c1=14")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c14)
            cur.execute("select c1,c15 from ar where c1=15")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c15)
    def test_write_full(self):
        with self.con.cursor() as cur:
            # INTEGER
            cur.execute("insert into ar (c1,c2) values (102,?)", [self.c2])
            self.con.commit()
            cur.execute("select c1,c2 from ar where c1=102")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c2)
            # VARCHAR
            cur.execute("insert into ar (c1,c3) values (103,?)", [self.c3])
            self.con.commit()
            cur.execute("select c1,c3 from ar where c1=103")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c3)
            # CHAR
            cur.execute("insert into ar (c1,c4) values (104,?)", [self.c4])
            self.con.commit()
            cur.execute("select c1,c4 from ar where c1=104")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c4)
            # TIMESTAMP
            cur.execute("insert into ar (c1,c5) values (105,?)", [self.c5])
            self.con.commit()
            cur.execute("select c1,c5 from ar where c1=105")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c5)
            # TIME OK
            cur.execute("insert into ar (c1,c6) values (106,?)", [self.c6])
            self.con.commit()
            cur.execute("select c1,c6 from ar where c1=106")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c6)
            # DECIMAL(10,2)
            cur.execute("insert into ar (c1,c7) values (107,?)", [self.c7])
            self.con.commit()
            cur.execute("select c1,c7 from ar where c1=107")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c7)
            # NUMERIC(10,2)
            cur.execute("insert into ar (c1,c8) values (108,?)", [self.c8])
            self.con.commit()
            cur.execute("select c1,c8 from ar where c1=108")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c8)
            # SMALLINT
            cur.execute("insert into ar (c1,c9) values (109,?)", [self.c9])
            self.con.commit()
            cur.execute("select c1,c9 from ar where c1=109")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c9)
            # BIGINT
            cur.execute("insert into ar (c1,c10) values (110,?)", [self.c10])
            self.con.commit()
            cur.execute("select c1,c10 from ar where c1=110")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c10)
            # FLOAT
            cur.execute("insert into ar (c1,c11) values (111,?)", [self.c11])
            self.con.commit()
            cur.execute("select c1,c11 from ar where c1=111")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c11)
            # DOUBLE PRECISION
            cur.execute("insert into ar (c1,c12) values (112,?)", [self.c12])
            self.con.commit()
            cur.execute("select c1,c12 from ar where c1=112")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c12)
            # DECIMAL(10,1) OK
            cur.execute("insert into ar (c1,c13) values (113,?)", [self.c13])
            self.con.commit()
            cur.execute("select c1,c13 from ar where c1=113")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c13)
            # DECIMAL(10,5)
            cur.execute("insert into ar (c1,c14) values (114,?)", [self.c14])
            self.con.commit()
            cur.execute("select c1,c14 from ar where c1=114")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c14)
            # DECIMAL(18,5)
            cur.execute("insert into ar (c1,c15) values (115,?)", [self.c15])
            self.con.commit()
            cur.execute("select c1,c15 from ar where c1=115")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c15)
            # BOOLEAN
            cur.execute("insert into ar (c1,c16) values (116,?)", [self.c16])
            self.con.commit()
            cur.execute("select c1,c16 from ar where c1=116")
            row = cur.fetchone()
            self.assertListEqual(row[1], self.c16)
    def test_write_wrong(self):
        with self.con.cursor() as cur:
            with self.assertRaises(ValueError) as cm:
                cur.execute("insert into ar (c1,c2) values (102,?)", [self.c3])
            self.assertTupleEqual(cm.exception.args, ('Incorrect ARRAY field value.',))
            with self.assertRaises(ValueError) as cm:
                cur.execute("insert into ar (c1,c2) values (102,?)", [self.c2[:-1]])
            self.assertTupleEqual(cm.exception.args, ('Incorrect ARRAY field value.',))

class TestInsertData(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con2 = connect(host=FBTEST_HOST, database=self.dbfile,
                            user=FBTEST_USER, password=FBTEST_PASSWORD,
                            charset='utf-8')
        #self.con.execute_immediate("recreate table t (c1 integer)")
        #self.con.commit()
        #self.con.execute_immediate("RECREATE TABLE T2 (C1 Smallint,C2 Integer,C3 Bigint,C4 Char(5),C5 Varchar(10),C6 Date,C7 Time,C8 Timestamp,C9 Blob sub_type 1,C10 Numeric(18,2),C11 Decimal(18,2),C12 Float,C13 Double precision,C14 Numeric(8,4),C15 Decimal(8,4))")
        self.con.execute_immediate("delete from t")
        self.con.execute_immediate("delete from t2")
        self.con.commit()
    def tearDown(self):
        self.con2.close()
        self.con.close()
    def test_insert_integers(self):
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)', [1, 1, 1])
        self.con.commit()
        cur.execute('select C1,C2,C3 from T2 where C1 = 1')
        rows = cur.fetchall()
        self.assertListEqual(rows, [(1, 1, 1)])
        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)',
                    [2, 1, 9223372036854775807])
        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)',
                    [2, 1, -9223372036854775807-1])
        self.con.commit()
        cur.execute('select C1,C2,C3 from T2 where C1 = 2')
        rows = cur.fetchall()
        self.assertListEqual(rows,
                             [(2, 1, 9223372036854775807), (2, 1, -9223372036854775808)])
    def test_insert_char_varchar(self):
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C4,C5) values (?,?,?)', [2, 'AA', 'AA'])
        self.con.commit()
        cur.execute('select C1,C4,C5 from T2 where C1 = 2')
        rows = cur.fetchall()
        self.assertListEqual(rows, [(2, 'AA   ', 'AA')])
        # Too long values
        with self.assertRaises(DatabaseError) as cm:
            cur.execute('insert into T2 (C1,C4) values (?,?)', [3, '123456'])
            self.con.commit()
        self.assertTupleEqual(cm.exception.args,
                              ('Dynamic SQL Error\n-SQL error code = -303\n-arithmetic exception, numeric overflow, or string truncation\n-string right truncation\n-expected length 5, actual 6',))
        with self.assertRaises(DatabaseError) as cm:
            cur.execute('insert into T2 (C1,C5) values (?,?)', [3, '12345678901'])
            self.con.commit()
            self.assertTupleEqual(cm.exception.args,
                                  ('Dynamic SQL Error\n-SQL error code = -303\n-arithmetic exception, numeric overflow, or string truncation\n-string right truncation\n-expected length 10, actual 11',))
    def test_insert_datetime(self):
        cur = self.con.cursor()
        now = datetime.datetime(2011, 11, 13, 15, 00, 1, 2000)
        cur.execute('insert into T2 (C1,C6,C7,C8) values (?,?,?,?)', [3, now.date(), now.time(), now])
        self.con.commit()
        cur.execute('select C1,C6,C7,C8 from T2 where C1 = 3')
        rows = cur.fetchall()
        self.assertListEqual(rows,
                             [(3, datetime.date(2011, 11, 13), datetime.time(15, 0, 1, 2000),
                               datetime.datetime(2011, 11, 13, 15, 0, 1, 2000))])

        cur.execute('insert into T2 (C1,C6,C7,C8) values (?,?,?,?)', [4, '2011-11-13', '15:0:1:200', '2011-11-13 15:0:1:2000'])
        self.con.commit()
        cur.execute('select C1,C6,C7,C8 from T2 where C1 = 4')
        rows = cur.fetchall()
        self.assertListEqual(rows,
                             [(4, datetime.date(2011, 11, 13), datetime.time(15, 0, 1, 2000),
                               datetime.datetime(2011, 11, 13, 15, 0, 1, 2000))])
    def test_insert_blob(self):
        cur = self.con.cursor()
        cur2 = self.con2.cursor()
        cur.execute('insert into T2 (C1,C9) values (?,?)', [4, 'This is a BLOB!'])
        cur.transaction.commit()
        cur.execute('select C1,C9 from T2 where C1 = 4')
        rows = cur.fetchall()
        self.assertListEqual(rows, [(4, 'This is a BLOB!')])
        # Non-textual BLOB
        blob_data = bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        cur.execute('insert into T2 (C1,C16) values (?,?)', [8, blob_data])
        cur.transaction.commit()
        cur.execute('select C1,C16 from T2 where C1 = 8')
        rows = cur.fetchall()
        self.assertListEqual(rows, [(8, blob_data)])
        # BLOB bigger than max. segment size
        big_blob = '123456789' * 10000
        cur.execute('insert into T2 (C1,C9) values (?,?)', [5, big_blob])
        cur.transaction.commit()
        cur.execute('select C1,C9 from T2 where C1 = 5')
        row = cur.fetchone()
        self.assertIsInstance(row[1], driver.core.BlobReader)
        #self.assertEqual(row[1].read(), big_blob)
        # Unicode in BLOB
        blob_text = 'This is a BLOB!'
        cur2.execute('insert into T2 (C1,C9) values (?,?)', [6, blob_text])
        cur2.transaction.commit()
        cur2.execute('select C1,C9 from T2 where C1 = 6')
        rows = cur2.fetchall()
        self.assertListEqual(rows, [(6, blob_text)])
        # Unicode non-textual BLOB
        with self.assertRaises(TypeError) as cm:
            cur2.execute('insert into T2 (C1,C16) values (?,?)', [7, blob_text])
        self.assertTupleEqual(cm.exception.args,
                              ("String value is not acceptable type for a non-textual BLOB column.",))
    def test_insert_float_double(self):
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C12,C13) values (?,?,?)', [5, 1.0, 1.0])
        self.con.commit()
        cur.execute('select C1,C12,C13 from T2 where C1 = 5')
        rows = cur.fetchall()
        self.assertListEqual(rows, [(5, 1.0, 1.0)])
        cur.execute('insert into T2 (C1,C12,C13) values (?,?,?)', [6, 1, 1])
        self.con.commit()
        cur.execute('select C1,C12,C13 from T2 where C1 = 6')
        rows = cur.fetchall()
        self.assertListEqual(rows, [(6, 1.0, 1.0)])
    def test_insert_numeric_decimal(self):
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C10,C11) values (?,?,?)', [6, 1.1, 1.1])
        cur.execute('insert into T2 (C1,C10,C11) values (?,?,?)', [6, decimal.Decimal('100.11'), decimal.Decimal('100.11')])
        self.con.commit()
        cur.execute('select C1,C10,C11 from T2 where C1 = 6')
        rows = cur.fetchall()
        self.assertListEqual(rows,
                             [(6, decimal.Decimal('1.1'), decimal.Decimal('1.1')),
                              (6, decimal.Decimal('100.11'), decimal.Decimal('100.11'))])
    def test_insert_returning(self):
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C10,C11) values (?,?,?) returning C1', [7, 1.1, 1.1])
        result = cur.fetchall()
        self.assertListEqual(result, [(7,)])
    def test_insert_boolean(self):
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C17) values (?,?) returning C1', [8, True])
        cur.execute('insert into T2 (C1,C17) values (?,?) returning C1', [8, False])
        cur.execute('select C1,C17 from T2 where C1 = 8')
        result = cur.fetchall()
        self.assertListEqual(result, [(8, True), (8, False)])

class TestStoredProc(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_callproc(self):
        cur = self.con.cursor()
        result = cur.callproc('sub_tot_budget', ['100'])
        self.assertTupleEqual(result, (decimal.Decimal('3800000'), decimal.Decimal('760000'),
                                       decimal.Decimal('500000'), decimal.Decimal('1500000')))
        #
        result = cur.callproc('sub_tot_budget', [100])
        self.assertTupleEqual(result, (decimal.Decimal('3800000'), decimal.Decimal('760000'),
                                       decimal.Decimal('500000'), decimal.Decimal('1500000')))
        #
        result = cur.callproc('proc_test', [10])
        self.assertIsNone(result)
        self.con.commit()
        cur.execute('select c1 from t')
        result = cur.fetchone()
        self.assertTupleEqual(result, tuple([10]))

class TestServices(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
    def test_attach(self):
        svc = connect_service(host=FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD)
        svc.close()
    def test_query(self):
        with connect_service(host=FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc:
            self.assertEqual(svc.get_service_manager_version(), 2)
            self.assertIn('Firebird', svc.get_server_version())
            self.assertIn('Firebird', svc.get_architecture())
            x = svc.get_home_directory()
            #self.assertEqual(x,'/opt/firebird/')
            self.assertIn('security3.fdb', svc.get_security_database_path())
            x = svc.get_lock_file_directory()
            #self.assertEqual(x,'/tmp/firebird/')
            x = svc.get_server_capabilities()
            self.assertIn(ServerCapability.REMOTE_HOP, x)
            self.assertNotIn(ServerCapability.NO_FORCED_WRITE, x)
            x = svc.get_message_file_directory()
            #self.assertEqual(x,'/opt/firebird/')
            with connect(host=FBTEST_HOST, database=self.dbfile,
                         user=FBTEST_USER, password=FBTEST_PASSWORD):
                with connect(host=FBTEST_HOST, database='employee',
                             user=FBTEST_USER, password=FBTEST_PASSWORD):
                    self.assertGreaterEqual(len(svc.get_attached_database_names()), 2, "Should work for Superserver, may fail with value 0 for Classic")
                    self.assertIn(self.dbfile.upper(),
                                  [s.upper() for s in svc.get_attached_database_names()])
                    self.assertGreaterEqual(svc.get_connection_count(), 2)
            # BAD request code
            with self.assertRaises(Error) as cm:
                svc._get_simple_info(255, driver.types.InfoItemType.BYTES)
            self.assertTupleEqual(cm.exception.args,
                                  ("feature is not supported",))

    def test_running(self):
        with connect_service(host=FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc:
            self.assertFalse(svc.is_running())
            svc.get_log()
            self.assertTrue(svc.is_running())
            # fetch materialized
            svc.readlines()
            self.assertFalse(svc.is_running())
    def test_wait(self):
        with connect_service(host=FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc:
            self.assertFalse(svc.is_running())
            svc.get_log()
            self.assertTrue(svc.is_running())
            svc.wait()
            self.assertFalse(svc.is_running())

class TestServices2(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.fbk = os.path.join(self.dbpath, 'test_employee.fbk')
        self.fbk2 = os.path.join(self.dbpath, 'test_employee.fbk2')
        self.rfdb = os.path.join(self.dbpath, 'test_employee.fdb')
        self.svc = connect_service(host=FBTEST_HOST, user='SYSDBA',
                                   password=FBTEST_PASSWORD)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con.execute_immediate("delete from t")
        self.con.commit()
        c = create_database(host=FBTEST_HOST, database=self.rfdb,
                                   user=FBTEST_USER, password=FBTEST_PASSWORD,
                                   overwrite=True)
        c.close()
    def tearDown(self):
        self.svc.close()
        self.con.close()
        if os.path.exists(self.rfdb):
            os.remove(self.rfdb)
        if os.path.exists(self.fbk):
            os.remove(self.fbk)
        if os.path.exists(self.fbk2):
            os.remove(self.fbk2)
    def test_log(self):
        def fetchline(line):
            output.append(line)

        self.svc.get_log()
        # fetch materialized
        log = self.svc.readlines()
        self.assertTrue(log)
        self.assertIsInstance(log, type(list()))
        # iterate over result
        self.svc.get_log()
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.get_log(callback=fetchline)
        self.assertGreater(len(output), 0)
        self.assertEqual(output, log)
    def test_get_limbo_transaction_ids(self):
        ids = self.svc.get_limbo_transaction_ids(database='employee')
        self.assertIsInstance(ids, type(list()))
    def test_get_statistics(self):
        def fetchline(line):
            output.append(line)

        #self.skipTest('Not implemented yet')
        self.svc.get_statistics(database='employee')
        self.assertTrue(self.svc.is_running())
        # fetch materialized
        stats = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertIsInstance(stats, type(list()))
        # iterate over result
        self.svc.get_statistics(database='employee',
                                flags=(SvcStatFlag.DEFAULT
                                       | SvcStatFlag.SYS_RELATIONS
                                       | SvcStatFlag.RECORD_VERSIONS))
        for line in self.svc:
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.get_statistics(database='employee', callback=fetchline)
        self.assertGreater(len(output), 0)
        # fetch only selected tables
        stats = self.svc.get_statistics(database='employee',
                                        flags=SvcStatFlag.DATA_PAGES,
                                        tables=['COUNTRY'])
        stats = '\n'.join(self.svc.readlines())
        self.assertIn('COUNTRY', stats)
        self.assertNotIn('JOB', stats)
        #
        stats = self.svc.get_statistics(database='employee',
                                        flags=SvcStatFlag.DATA_PAGES,
                                        tables=('COUNTRY', 'PROJECT'))
        stats = '\n'.join(self.svc.readlines())
        self.assertIn('COUNTRY', stats)
        self.assertIn('PROJECT', stats)
        self.assertNotIn('JOB', stats)
    def test_backup(self):
        def fetchline(line):
            output.append(line)

        #self.skipTest('Not implemented yet')
        self.svc.backup(database='employee', backup=self.fbk)
        self.assertTrue(self.svc.is_running())
        # fetch materialized
        report = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertTrue(os.path.exists(self.fbk))
        self.assertIsInstance(report, type(list()))
        self.assertListEqual(report, [])
        # iterate over result
        self.svc.backup(database='employee', backup=self.fbk,
                        flags=(SvcBackupFlag.CONVERT
                               | SvcBackupFlag.IGNORE_LIMBO
                               | SvcBackupFlag.IGNORE_CHECKSUMS
                               | SvcBackupFlag.METADATA_ONLY), verbose=True)
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.backup(database='employee', backup=self.fbk, callback=fetchline, verbose=True)
        self.assertGreater(len(output), 0)
        # Firebird 3.0 stats
        output = []
        self.svc.backup(database='employee', backup=self.fbk, callback=fetchline,
                        stats='TDRW', verbose=True)
        self.assertGreater(len(output), 0)
        self.assertIn('gbak: time     delta  reads  writes \n', output)
        # Skip data option
        self.svc.backup(database='employee', backup=self.fbk, skip_data='(sales|customer)')
        self.svc.wait()
        self.svc.restore(backup=self.fbk, database=self.rfdb, flags=SvcRestoreFlag.REPLACE)
        self.svc.wait()
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as rcon:
            with rcon.cursor() as c:
                c.execute('select * from sales')
                self.assertListEqual(c.fetchall(), [])
                c.execute('select * from country')
                self.assertGreater(len(c.fetchall()), 0)
    def test_restore(self):
        def fetchline(line):
            output.append(line)

        output = []
        self.svc.backup(database='employee', backup=self.fbk, callback=fetchline)
        self.assertTrue(os.path.exists(self.fbk))
        self.svc.restore(backup=self.fbk, database=self.rfdb, flags=SvcRestoreFlag.REPLACE)
        self.assertTrue(self.svc.is_running())
        # fetch materialized
        report = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertIsInstance(report, type(list()))
        # iterate over result
        self.svc.restore(backup=self.fbk, database=self.rfdb, flags=SvcRestoreFlag.REPLACE)
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.restore(backup=self.fbk, database=self.rfdb, flags=SvcRestoreFlag.REPLACE, callback=fetchline)
        self.assertGreater(len(output), 0)
        # Firebird 3.0 stats
        output = []
        self.svc.restore(backup=self.fbk, database=self.rfdb, flags=SvcRestoreFlag.REPLACE, callback=fetchline,
                         stats='TDRW')
        self.assertGreater(len(output), 0)
        self.assertIn('gbak: time     delta  reads  writes \n', output)
        # Skip data option
        self.svc.restore(backup=self.fbk, database=self.rfdb,
                         flags=SvcRestoreFlag.REPLACE, skip_data='(sales|customer)')
        self.svc.wait()
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as rcon:
            with rcon.cursor() as c:
                c.execute('select * from sales')
                self.assertListEqual(c.fetchall(), [])
                c.execute('select * from country')
                self.assertGreater(len(c.fetchall()), 0)
    def test_local_backup(self):
        self.svc.backup(database='employee', backup=self.fbk)
        self.svc.wait()
        with open(self.fbk, mode='rb') as f:
            f.seek(168) # Wee must skip after backup creation time that will differ
            bkp = f.read()
        backup_stream = BytesIO()
        self.svc.local_backup(database='employee', backup_stream=backup_stream)
        backup_stream.seek(168)
        self.assertEqual(bkp, backup_stream.read())
        del bkp
    def test_local_restore(self):
        backup_stream = BytesIO()
        self.svc.local_backup(database='employee', backup_stream=backup_stream)
        backup_stream.seek(0)
        self.svc.local_restore(backup_stream=backup_stream, database=self.rfdb,
                               flags=SvcRestoreFlag.REPLACE)
        self.assertTrue(os.path.exists(self.rfdb))
    def test_nbackup(self):
        self.svc.nbackup(database='employee', backup=self.fbk)
        self.assertTrue(os.path.exists(self.fbk))
        self.svc.nbackup(database='employee', backup=self.fbk2, level=1,
                         direct=True, flags=SvcNBackupFlag.NO_TRIGGERS)
        self.assertTrue(os.path.exists(self.fbk2))
    def test_nrestore(self):
        self.test_nbackup()
        if os.path.exists(self.rfdb):
            os.remove(self.rfdb)
        self.svc.nrestore(backups=[self.fbk], database=self.rfdb)
        self.assertTrue(os.path.exists(self.rfdb))
        if os.path.exists(self.rfdb):
            os.remove(self.rfdb)
        self.svc.nrestore(backups=[self.fbk, self.fbk2], database=self.rfdb,
                          direct=True, flags=SvcNBackupFlag.NO_TRIGGERS)
        self.assertTrue(os.path.exists(self.rfdb))
    def test_trace(self):
        #self.skipTest('Not implemented yet')
        trace_config = """database = %s
        {
          enabled = true
          log_statement_finish = true
          print_plan = true
          include_filter = %%SELECT%%
          exclude_filter = %%RDB$%%
          time_threshold = 0
          max_sql_length = 2048
        }
        """ % self.dbfile
        with connect_service(host=FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc2, \
             connect_service(host=FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svcx:
            # Start trace sessions
            trace1_id = self.svc.trace_start(config=trace_config, name='test_trace_1')
            trace2_id = svc2.trace_start(config=trace_config)
            # check sessions
            sessions = svcx.trace_list()
            self.assertIn(trace1_id, sessions)
            seq = list(sessions[trace1_id].keys())
            seq.sort()
            self.assertListEqual(seq,['date', 'flags', 'name', 'user'])
            self.assertIn(trace2_id, sessions)
            seq = list(sessions[trace2_id].keys())
            seq.sort()
            self.assertListEqual(seq,['date', 'flags', 'user'])
            self.assertListEqual(sessions[trace1_id]['flags'], ['active', ' trace'])
            self.assertListEqual(sessions[trace2_id]['flags'], ['active', ' trace'])
            # Pause session
            svcx.trace_suspend(session_id=trace2_id)
            self.assertIn('suspend', svcx.trace_list()[trace2_id]['flags'])
            # Resume session
            svcx.trace_resume(session_id=trace2_id)
            self.assertIn('active', svcx.trace_list()[trace2_id]['flags'])
            # Stop session
            svcx.trace_stop(session_id=trace2_id)
            self.assertNotIn(trace2_id, svcx.trace_list())
            # Finalize
            svcx.trace_stop(session_id=trace1_id)
    def test_set_default_page_buffers(self):
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertNotEqual(con.page_cache_size, 100)
        self.svc.set_default_page_buffers(database=self.rfdb, value=100)
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.page_cache_size, 100)
        self.svc.set_default_page_buffers(database=self.rfdb, value=5000)
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.page_cache_size, 5000)
    def test_set_sweep_interval(self):
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertNotEqual(con.sweep_interval, 10000)
        self.svc.set_sweep_interval(database=self.rfdb, value=10000)
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.sweep_interval, 10000)
    def test_shutdown_bring_online(self):
        #self.skipTest('Not implemented yet')
        # Shutdown database to single-user maintenance mode
        self.svc.shutdown(database=self.rfdb,mode=ShutdownMode.SINGLE,
                          method=ShutdownMethod.FORCED, timeout=0)
        self.svc.get_statistics(database=self.rfdb, flags=SvcStatFlag.HDR_PAGES)
        self.assertIn('single-user maintenance', ''.join(self.svc.readlines()))
        # Enable multi-user maintenance
        self.svc.bring_online(database=self.rfdb, mode=OnlineMode.MULTI)
        self.svc.get_statistics(database=self.rfdb, flags=SvcStatFlag.HDR_PAGES)
        self.assertIn('multi-user maintenance', ''.join(self.svc.readlines()))
        # Go to full shutdown mode, disabling new attachments during 5 seconds
        self.svc.shutdown(database=self.rfdb,
                          mode=ShutdownMode.FULL,
                          method=ShutdownMethod.DENNY_ATTACHMENTS, timeout=5)
        self.svc.get_statistics(database=self.rfdb, flags=SvcStatFlag.HDR_PAGES)
        self.assertIn('full shutdown', ''.join(self.svc.readlines()))
        # Enable single-user maintenance
        self.svc.bring_online(database=self.rfdb, mode=OnlineMode.SINGLE)
        self.svc.get_statistics(database=self.rfdb, flags=SvcStatFlag.HDR_PAGES)
        self.assertIn('single-user maintenance', ''.join(self.svc.readlines()))
        # Return to normal state
        self.svc.bring_online(database=self.rfdb)
    def test_set_space_reservation(self):
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertTrue(con.space_reservation)
        self.svc.set_space_reservation(database=self.rfdb, value=False)
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertFalse(con.space_reservation)
    def test_set_forced_writes(self):
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertTrue(con.forced_writes)
        self.svc.set_forced_writes(database=self.rfdb, value=False)
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertFalse(con.forced_writes)
    def test_set_read_only(self):
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertFalse(con.is_read_only())
        self.svc.set_read_only(database=self.rfdb, value=True)
        with connect(host=FBTEST_HOST, database=self.rfdb,
                     user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertTrue(con.is_read_only())
    def test_set_sql_dialect(self):
        with connect(host=FBTEST_HOST, database=self.rfdb,
                            user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.database_sql_dialect, 3)
        self.svc.set_sql_dialect(database=self.rfdb, value=1)
        with connect(host=FBTEST_HOST, database=self.rfdb,
                            user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.database_sql_dialect, 1)
    def test_activate_shadow(self):
        self.svc.activate_shadow(database=self.rfdb)
    def test_no_linger(self):
        self.svc.no_linger(database=self.rfdb)
    def test_sweep(self):
        self.svc.sweep(database=self.rfdb)
    def test_repair(self):
        self.svc.repair(database=self.rfdb, flags=SvcRepairFlag.CORRUPTION_CHECK)
        self.svc.repair(database=self.rfdb, flags=SvcRepairFlag.REPAIR)
    def test_validate(self):
        def fetchline(line):
            output.append(line)

        output = []
        self.svc.validate(database=self.dbfile)
        # fetch materialized
        report = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertIsInstance(report, type(list()))
        self.assertIn('Validation started', '/n'.join(report))
        self.assertIn('Validation finished', '/n'.join(report))
        # iterate over result
        self.svc.validate(database=self.dbfile)
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.validate(database=self.dbfile, callback=fetchline)
        self.assertGreater(len(output), 0)
        # Parameters
        self.svc.validate(database=self.dbfile, include_table='COUNTRY|SALES',
                          include_index='SALESTATX', lock_timeout=-1)
        report = '/n'.join(self.svc.readlines())
        self.assertNotIn('(JOB)', report)
        self.assertIn('(COUNTRY)', report)
        self.assertIn('(SALES)', report)
        self.assertIn('(SALESTATX)', report)
    def test_get_users(self):
        users = self.svc.get_users()
        self.assertIsInstance(users, type(list()))
        self.assertIsInstance(users[0], driver.core.UserInfo)
        self.assertEqual(users[0].user_name, 'SYSDBA')
    def test_manage_user(self):
        USER_NAME = 'DRIVER_TEST'
        try:
            self.svc.delete_user(USER_NAME)
        except DatabaseError as e:
            if e.sqlstate == '28000':
                pass
            else:
                raise
        # Add user
        self.svc.add_user(user_name=USER_NAME, password='DRIVER_TEST',
                          first_name='Firebird', middle_name='Driver', last_name='Test')
        self.assertTrue(self.svc.user_exists(USER_NAME))
        users = [u for u in self.svc.get_users() if u.user_name == USER_NAME]
        self.assertTrue(users)
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].first_name, 'Firebird')
        self.assertEqual(users[0].middle_name, 'Driver')
        self.assertEqual(users[0].last_name, 'Test')
        # Modify user
        self.svc.modify_user(USER_NAME, first_name='XFirebird', middle_name='XDriver', last_name='XTest')
        user = self.svc.get_user(USER_NAME)
        self.assertEqual(user.user_name, USER_NAME)
        self.assertEqual(user.first_name, 'XFirebird')
        self.assertEqual(user.middle_name, 'XDriver')
        self.assertEqual(user.last_name, 'XTest')
        # Delete user
        self.svc.delete_user(USER_NAME)
        self.assertFalse(self.svc.user_exists(USER_NAME))

class TestEvents(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, 'fbevents.fdb')
        if os.path.exists(self.dbfile):
            os.remove(self.dbfile)
        self.con = create_database(host=FBTEST_HOST, database=self.dbfile,
                                   user=FBTEST_USER, password=FBTEST_PASSWORD)
        c = self.con.cursor()
        c.execute("CREATE TABLE T (PK Integer, C1 Integer)")
        c.execute("""CREATE TRIGGER EVENTS_AU FOR T ACTIVE
BEFORE UPDATE POSITION 0
AS
BEGIN
    if (old.C1 <> new.C1) then
        post_event 'c1_updated' ;
END""")
        c.execute("""CREATE TRIGGER EVENTS_AI FOR T ACTIVE
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
        self.con.commit()
    def tearDown(self):
        self.con.drop_database()
        self.con.close()
    def test_one_event(self):
        def send_events(command_list):
            c = self.con.cursor()
            for cmd in command_list:
                c.execute(cmd)
            self.con.commit()

        e = {}
        timed_event = threading.Timer(3.0, send_events, args=[["insert into T (PK,C1) values (1,1)",]])
        with self.con.create_event_collector(['insert_1']) as events:
            timed_event.start()
            e = events.wait()
        timed_event.join()
        self.assertDictEqual(e, {'insert_1': 1})
    def test_multiple_events(self):
        def send_events(command_list):
            c = self.con.cursor()
            for cmd in command_list:
                c.execute(cmd)
            self.con.commit()

        cmds = ["insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",
                "insert into T (PK,C1) values (1,3)",
                "insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",]
        timed_event = threading.Timer(3.0, send_events, args=[cmds])
        with self.con.create_event_collector(['insert_1', 'insert_3']) as events:
            timed_event.start()
            e = events.wait()
        timed_event.join()
        self.assertDictEqual(e, {'insert_3': 1, 'insert_1': 2})
    def test_20_events(self):
        def send_events(command_list):
            c = self.con.cursor()
            for cmd in command_list:
                c.execute(cmd)
            self.con.commit()

        cmds = ["insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",
                "insert into T (PK,C1) values (1,3)",
                "insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",]
        self.e = {}
        timed_event = threading.Timer(1.0, send_events, args=[cmds])
        with self.con.create_event_collector(['insert_1', 'A', 'B', 'C', 'D',
                                     'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
                                     'N', 'O', 'P', 'Q', 'R', 'insert_3']) as events:
            timed_event.start()
            time.sleep(3)
            e = events.wait()
        timed_event.join()
        self.assertDictEqual(e,
                             {'A': 0, 'C': 0, 'B': 0, 'E': 0, 'D': 0, 'G': 0, 'insert_1': 2,
                              'I': 0, 'H': 0, 'K': 0, 'J': 0, 'M': 0, 'L': 0, 'O': 0, 'N': 0,
                              'Q': 0, 'P': 0, 'R': 0, 'insert_3': 1, 'F': 0})
    def test_flush_events(self):
        def send_events(command_list):
            c = self.con.cursor()
            for cmd in command_list:
                c.execute(cmd)
            self.con.commit()

        timed_event = threading.Timer(3.0, send_events, args=[["insert into T (PK,C1) values (1,1)",]])
        with self.con.create_event_collector(['insert_1']) as events:
            send_events(["insert into T (PK,C1) values (1,1)",
                         "insert into T (PK,C1) values (1,1)"])
            time.sleep(2)
            events.flush()
            timed_event.start()
            e = events.wait()
        timed_event.join()
        self.assertDictEqual(e, {'insert_1': 1})

class TestStreamBLOBs(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        #self.con.execute_immediate("recreate table t (c1 integer)")
        #self.con.commit()
        #self.con.execute_immediate("RECREATE TABLE T2 (C1 Smallint,C2 Integer,C3 Bigint,C4 Char(5),C5 Varchar(10),C6 Date,C7 Time,C8 Timestamp,C9 Blob sub_type 1,C10 Numeric(18,2),C11 Decimal(18,2),C12 Float,C13 Double precision,C14 Numeric(8,4),C15 Decimal(8,4))")
        self.con.execute_immediate("delete from t")
        self.con.execute_immediate("delete from t2")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def testBlobBasic(self):
        blob = """Firebird supports two types of blobs, stream and segmented.
The database stores segmented blobs in chunks.
Each chunk starts with a two byte length indicator followed by however many bytes of data were passed as a segment.
Stream blobs are stored as a continuous array of data bytes with no length indicators included."""
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C9) values (?,?)', [4, StringIO(blob)])
        self.con.commit()
        p = cur.prepare('select C1,C9 from T2 where C1 = 4')
        cur.stream_blobs.append('C9')
        cur.execute(p)
        row = cur.fetchone()
        blob_reader = row[1]
        ## Necessary to avoid bad BLOB handle on BlobReader.close in tearDown
        ## because BLOB handle is no longer valid after table purge
        with cur:
            self.assertEqual(blob_reader.read(20), 'Firebird supports tw')
            self.assertEqual(blob_reader.read(20), 'o types of blobs, st')
            self.assertEqual(blob_reader.read(400), 'ream and segmented.\nThe database stores segmented blobs in '
                             'chunks.\nEach chunk starts with a two byte length indicator '
                             'followed by however many bytes of data were passed as '
                             'a segment.\nStream blobs are stored as a continuous array '
                             'of data bytes with no length indicators included.')
            self.assertEqual(blob_reader.read(20), '')
            self.assertEqual(blob_reader.tell(), 318)
            blob_reader.seek(20)
            self.assertEqual(blob_reader.tell(), 20)
            self.assertEqual(blob_reader.read(20), 'o types of blobs, st')
            blob_reader.seek(0)
            self.assertEqual(blob_reader.tell(), 0)
            self.assertListEqual(blob_reader.readlines(), StringIO(blob).readlines())
            blob_reader.seek(0)
            for line in blob_reader:
                self.assertIn(line.rstrip('\n'), blob.split('\n'))
            blob_reader.seek(0)
            self.assertEqual(blob_reader.read(), blob)
            blob_reader.seek(-9, os.SEEK_END)
            self.assertEqual(blob_reader.read(), 'included.')
            blob_reader.seek(-20, os.SEEK_END)
            blob_reader.seek(11, os.SEEK_CUR)
            self.assertEqual(blob_reader.read(), 'included.')
            blob_reader.seek(60)
            self.assertEqual(blob_reader.readline(),
                             'The database stores segmented blobs in chunks.\n')
            self.assertIsInstance(blob_reader.blob_id, fbapi.ISC_QUAD)
            self.assertTrue(blob_reader.is_text)
            #self.assertEqual(blob_reader.blob_charset, None)
            #self.assertEqual(blob_reader.charset, 'UTF-8')
    def testBlobExtended(self):
        blob = """Firebird supports two types of blobs, stream and segmented.
The database stores segmented blobs in chunks.
Each chunk starts with a two byte length indicator followed by however many bytes of data were passed as a segment.
Stream blobs are stored as a continuous array of data bytes with no length indicators included."""
        cur = self.con.cursor()
        cur.execute('insert into T2 (C1,C9) values (?,?)', [1, StringIO(blob)])
        cur.execute('insert into T2 (C1,C9) values (?,?)', [2, StringIO(blob)])
        self.con.commit()
        p = cur.prepare('select C1,C9 from T2')
        cur.stream_blobs.append('C9')
        cur.execute(p)
        #rows = [row for row in cur]
        # Necessary to avoid bad BLOB handle on BlobReader.close in tearDown
        # because BLOB handle is no longer valid after table purge
        with cur:
            for row in cur:
                blob_reader = row[1]
                self.assertEqual(blob_reader.read(20), 'Firebird supports tw')
                self.assertEqual(blob_reader.read(20), 'o types of blobs, st')
                self.assertEqual(blob_reader.read(400), 'ream and segmented.\nThe database stores segmented blobs '
                                 'in chunks.\nEach chunk starts with a two byte length '
                                 'indicator followed by however many bytes of data were '
                                 'passed as a segment.\nStream blobs are stored as a '
                                 'continuous array of data bytes with no length indicators '
                                 'included.')
                self.assertEqual(blob_reader.read(20), '')
                self.assertEqual(blob_reader.tell(), 318)
                blob_reader.seek(20)
                self.assertEqual(blob_reader.tell(), 20)
                self.assertEqual(blob_reader.read(20), 'o types of blobs, st')
                blob_reader.seek(0)
                self.assertEqual(blob_reader.tell(), 0)
                self.assertListEqual(blob_reader.readlines(),
                                     StringIO(blob).readlines())
                blob_reader.seek(0)
                for line in blob_reader:
                    self.assertIn(line.rstrip('\n'), blob.split('\n'))
                blob_reader.seek(0)
                self.assertEqual(blob_reader.read(), blob)
                blob_reader.seek(-9, os.SEEK_END)
                self.assertEqual(blob_reader.read(), 'included.')
                blob_reader.seek(-20, os.SEEK_END)
                blob_reader.seek(11, os.SEEK_CUR)
                self.assertEqual(blob_reader.read(), 'included.')
                blob_reader.seek(60)
                self.assertEqual(blob_reader.readline(),
                                 'The database stores segmented blobs in chunks.\n')

class TestCharsetConversion(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(host=FBTEST_HOST, database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD,
                           charset='utf8')
        #self.con.execute_immediate("recreate table t (c1 integer)")
        #self.con.commit()
        #self.con.execute_immediate("RECREATE TABLE T2 (C1 Smallint,C2 Integer,C3 Bigint,C4 Char(5),C5 Varchar(10),C6 Date,C7 Time,C8 Timestamp,C9 Blob sub_type 1,C10 Numeric(18,2),C11 Decimal(18,2),C12 Float,C13 Double precision,C14 Numeric(8,4),C15 Decimal(8,4))")
        #self.con.commit()
        self.con.execute_immediate("delete from t3")
        self.con.execute_immediate("delete from t4")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_octets(self):
        bytestring = bytes([1, 2, 3, 4, 5])
        cur = self.con.cursor()
        cur.execute("insert into T4 (C1, C_OCTETS, V_OCTETS) values (?,?,?)",
                    (1, bytestring, bytestring))
        self.con.commit()
        cur.execute("select C1, C_OCTETS, V_OCTETS from T4 where C1 = 1")
        row = cur.fetchone()
        self.assertTupleEqual(row,
                              (1, b'\x01\x02\x03\x04\x05', b'\x01\x02\x03\x04\x05'))
    def test_utf82win1250(self):
        s5 = 'ěščřž'
        s30 = 'ěščřžýáíéúůďťňóĚŠČŘŽÝÁÍÉÚŮĎŤŇÓ'

        con1250 = connect(host=FBTEST_HOST, database=self.dbfile, user=FBTEST_USER,
                          password=FBTEST_PASSWORD, charset='win1250')
        c_utf8 = self.con.cursor()
        c_win1250 = con1250.cursor()

        # Insert unicode data
        c_utf8.execute("insert into T4 (C1, C_WIN1250, V_WIN1250, C_UTF8, V_UTF8)"
                       "values (?,?,?,?,?)",
                       (1, s5, s30, s5, s30))
        self.con.commit()

        # Should return the same unicode content when read from win1250 or utf8 connection
        c_win1250.execute("select C1, C_WIN1250, V_WIN1250,"
                          "C_UTF8, V_UTF8 from T4 where C1 = 1")
        row = c_win1250.fetchone()
        self.assertTupleEqual(row, (1, s5, s30, s5, s30))
        c_utf8.execute("select C1, C_WIN1250, V_WIN1250,"
                       "C_UTF8, V_UTF8 from T4 where C1 = 1")
        row = c_utf8.fetchone()
        self.assertTupleEqual(row, (1, s5, s30, s5, s30))

    def testCharVarchar(self):
        s = 'Introdução'
        self.assertEqual(len(s), 10)
        data = tuple([1, s, s])
        cur = self.con.cursor()
        cur.execute('insert into T3 (C1,C2,C3) values (?,?,?)', data)
        self.con.commit()
        cur.execute('select C1,C2,C3 from T3 where C1 = 1')
        row = cur.fetchone()
        self.assertEqual(row, data)
    def testBlob(self):
        s = """Introdução

Este artigo descreve como você pode fazer o InterBase e o Firebird 1.5
coehabitarem pacificamente seu computador Windows. Por favor, note que esta
solução não permitirá que o Interbase e o Firebird rodem ao mesmo tempo.
Porém você poderá trocar entre ambos com um mínimo de luta. """
        self.assertEqual(len(s), 292)
        data = tuple([2, s])
        b_data = tuple([3, b'bytestring'])
        cur = self.con.cursor()
        # Text BLOB
        cur.execute('insert into T3 (C1,C4) values (?,?)', data)
        self.con.commit()
        cur.execute('select C1,C4 from T3 where C1 = 2')
        row = cur.fetchone()
        self.assertEqual(row, data)
        # Insert Unicode into non-textual BLOB
        with self.assertRaises(TypeError) as cm:
            cur.execute('insert into T3 (C1,C5) values (?,?)', data)
            self.con.commit()
        self.assertTupleEqual(cm.exception.args,
                              ("String value is not acceptable type for a non-textual BLOB column.",))
        # Read binary from non-textual BLOB
        cur.execute('insert into T3 (C1,C5) values (?,?)', b_data)
        self.con.commit()
        cur.execute('select C1,C5 from T3 where C1 = 3')
        row = cur.fetchone()
        self.assertEqual(row, b_data)

class TestHooks(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
    def __hook_service_attached(self, con):
        self._svc = con
        return con
    def __hook_db_attached(self, con):
        self._db = con
        return con
    def __hook_db_attach_request_a(self, dsn, dpb):
        return None
    def __hook_db_attach_request_b(self, dsn, dpb):
        return self._hook_con
    def test_hook_db_attached(self):
        hooks.add_hook(HookType.DATABASE_ATTACHED, self.__hook_db_attached)
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIs(con, self._db)
        hooks.remove_hook(HookType.DATABASE_ATTACHED, self.__hook_db_attached)
    def test_hook_db_attach_request(self):
        self._hook_con = connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        hooks.add_hook(HookType.DATABASE_ATTACH_REQUEST, self.__hook_db_attach_request_a)
        hooks.add_hook(HookType.DATABASE_ATTACH_REQUEST, self.__hook_db_attach_request_b)
        self.assertListEqual([self.__hook_db_attach_request_a,
                              self.__hook_db_attach_request_b],
                             hooks.get_hooks(HookType.DATABASE_ATTACH_REQUEST))
        with connect(dsn=self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertIs(con, self._hook_con)
        self._hook_con.close()
        hooks.remove_hook(HookType.DATABASE_ATTACH_REQUEST, self.__hook_db_attach_request_a)
        hooks.remove_hook(HookType.DATABASE_ATTACH_REQUEST, self.__hook_db_attach_request_b)
    def test_hook_service_attached(self):
        hooks.add_hook(HookType.SERVICE_ATTACHED, self.__hook_service_attached)
        svc = connect_service(host=FBTEST_HOST, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.assertIs(svc, self._svc)
        svc.close()
        hooks.remove_hook(HookType.SERVICE_ATTACHED, self.__hook_service_attached)


if __name__ == '__main__':
    unittest.main()

