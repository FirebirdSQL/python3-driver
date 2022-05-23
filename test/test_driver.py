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
from unittest.mock import patch
import datetime
import sys
import os
from logging import getLogger, DEBUG, Formatter, StreamHandler
from firebird.base.logging import logging_manager, ANY, install_null_logger, \
     LoggingIdMixin
from firebird.driver import *
from firebird.driver.hooks import ConnectionHook, ServerHook, hook_manager, add_hook
import firebird.driver as driver
import sys, os
import threading
import time
import decimal
from re import finditer

from io import StringIO, BytesIO

FB30 = '3.0'
FB40 = '4.0'

# Default server host
#FBTEST_HOST = ''
FBTEST_HOST = 'localhost'
# Default user
FBTEST_USER = 'SYSDBA'
# Default user password
FBTEST_PASSWORD = 'masterkey'

cfg = driver_config.register_server('FBTEST_HOST')
cfg.host.value = FBTEST_HOST
cfg.user.value = FBTEST_USER
cfg.password.value = FBTEST_PASSWORD

trace = False

if not sys.warnoptions:
    import warnings
    warnings.simplefilter("always") # Change the filter in this process
    #os.environ["PYTHONWARNINGS"] = "default" # Also affect subprocesses

def os_environ_get_mock(key, default):
    return f'MOCK_{key}'

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


class DriverTestBase(unittest.TestCase, LoggingIdMixin):
    def setUp(self) -> None:
        super().setUp()
        self.output = StringIO()
        install_null_logger()
        if trace or os.getenv('DRIVER_TRACE') is not None:
            self.mngr = logging_manager
            #self.mngr.trace |= TraceFlag.BEFORE
            #self.mngr.trace |= TraceFlag.AFTER
            self.mngr.bind_logger(ANY, ANY, '', 'trace')
            sh = StreamHandler(sys.stdout)
            sh.setFormatter(Formatter('[%(context)s] %(agent)s: %(message)s'))
            logger = getLogger()
            logger.setLevel(DEBUG)
            logger.addHandler(sh)
        #
        with connect_server(FBTEST_HOST, user=FBTEST_USER, password=FBTEST_PASSWORD) as svc:
            self.version = svc.info.version
        if self.version.startswith(FB30):
            self.FBTEST_DB = 'fbtest30.fdb'
            self.version = FB30
        elif self.version.startswith(FB40):
            self.FBTEST_DB = 'fbtest40.fdb'
            self.version = FB40
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
    def test_create_drop_dsn(self):
        with create_database(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.dsn, self.dbfile)
            self.assertEqual(con.sql_dialect, 3)
            self.assertEqual(con.charset, None)
            con.drop_database()
        # Overwrite
        with create_database(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            self.assertEqual(con.dsn, self.dbfile)
            self.assertEqual(con.sql_dialect, 3)
            self.assertEqual(con.charset, None)
        with self.assertRaises(DatabaseError) as cm:
            create_database(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.assertTrue('exist' in cm.exception.args[0])
        with create_database(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD, overwrite=True) as con:
            self.assertEqual(con.dsn, self.dbfile)
            con.drop_database()
    def test_create_drop_config(self):
        db_config = f"""
        [test_db2]
        database = {self.dbfile}
        user = {FBTEST_USER}
        password = {FBTEST_PASSWORD}
        utf8filename = true
        charset = UTF8
        sql_dialect = 1
        page_size = {types.PageSize.PAGE_16K}
        db_charset = UTF8
        db_sql_dialect = 1
        sweep_interval = 0
        """
        driver_config.register_database('test_db2', db_config)
        #
        with create_database('test_db2') as con:
            self.assertEqual(con.sql_dialect, 1)
            self.assertEqual(con.charset, 'UTF8')
            self.assertEqual(con.info.page_size, 16384)
            self.assertEqual(con.info.sql_dialect, 1)
            self.assertEqual(con.info.charset, 'UTF8')
            self.assertEqual(con.info.sweep_interval, 0)
            con.drop_database()

class TestConnection(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
    def tearDown(self):
        pass
    def test_connect_helper(self):
        DB_LINUX_PATH = '/path/to/db/employee.fdb'
        DB_WIN_PATH = 'C:\\path\\to\\db\\employee.fdb'
        DB_ALIAS = 'employee'
        HOST = 'localhost'
        NPIPE_HOST = '\\\\MyServer'
        IP = '127.0.0.1'
        PORT = '3051'
        SVC_NAME = 'fb_srv'
        # Classic DSN (without protocol)
        # 1. Local connection
        dsn = driver.core._connect_helper(None, None, None, DB_ALIAS, None)
        self.assertEqual(dsn, DB_ALIAS)
        dsn = driver.core._connect_helper(None, None, None, DB_LINUX_PATH, None)
        self.assertEqual(dsn, DB_LINUX_PATH)
        dsn = driver.core._connect_helper(None, None, None, DB_WIN_PATH, None)
        self.assertEqual(dsn, DB_WIN_PATH)
        # 2. TCP/IP
        dsn = driver.core._connect_helper(None, HOST, None, DB_ALIAS, None)
        self.assertEqual(dsn, f'{HOST}:{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, IP, None, DB_LINUX_PATH, None)
        self.assertEqual(dsn, f'{IP}:{DB_LINUX_PATH}')
        dsn = driver.core._connect_helper(None, HOST, None, DB_WIN_PATH, None)
        self.assertEqual(dsn, f'{HOST}:{DB_WIN_PATH}')
        # 3. TCP/IP with Port
        dsn = driver.core._connect_helper(None, HOST, PORT, DB_ALIAS, None)
        self.assertEqual(dsn, f'{HOST}/{PORT}:{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, IP, PORT, DB_LINUX_PATH, None)
        self.assertEqual(dsn, f'{IP}/{PORT}:{DB_LINUX_PATH}')
        dsn = driver.core._connect_helper(None, HOST, SVC_NAME, DB_WIN_PATH, None)
        self.assertEqual(dsn, f'{HOST}/{SVC_NAME}:{DB_WIN_PATH}')
        # 4. Named pipes
        dsn = driver.core._connect_helper(None, NPIPE_HOST, None, DB_ALIAS, None)
        self.assertEqual(dsn, f'{NPIPE_HOST}\\{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, NPIPE_HOST, SVC_NAME, DB_WIN_PATH, None)
        self.assertEqual(dsn, f'{NPIPE_HOST}@{SVC_NAME}\\{DB_WIN_PATH}')
        # URL-Style Connection Strings (with protocol)
        # 1. Loopback connection
        dsn = driver.core._connect_helper(None, None, None, DB_ALIAS, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, None, None, DB_LINUX_PATH, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{DB_LINUX_PATH}')
        dsn = driver.core._connect_helper(None, None, None, DB_WIN_PATH, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{DB_WIN_PATH}')
        dsn = driver.core._connect_helper(None, None, None, DB_ALIAS, NetProtocol.WNET)
        self.assertEqual(dsn, f'wnet://{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, None, None, DB_ALIAS, NetProtocol.XNET)
        self.assertEqual(dsn, f'xnet://{DB_ALIAS}')
        # 2. TCP/IP
        dsn = driver.core._connect_helper(None, HOST, None, DB_ALIAS, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{HOST}/{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, IP, None, DB_LINUX_PATH, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{IP}/{DB_LINUX_PATH}')
        dsn = driver.core._connect_helper(None, HOST, None, DB_WIN_PATH, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{HOST}/{DB_WIN_PATH}')
        # 3. TCP/IP with Port
        dsn = driver.core._connect_helper(None, HOST, PORT, DB_ALIAS, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{HOST}:{PORT}/{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, IP, PORT, DB_LINUX_PATH, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{IP}:{PORT}/{DB_LINUX_PATH}')
        dsn = driver.core._connect_helper(None, HOST, SVC_NAME, DB_WIN_PATH, NetProtocol.INET)
        self.assertEqual(dsn, f'inet://{HOST}:{SVC_NAME}/{DB_WIN_PATH}')
        # 4. Named pipes
        dsn = driver.core._connect_helper(None, NPIPE_HOST, None, DB_ALIAS, NetProtocol.WNET)
        self.assertEqual(dsn,f'wnet://{NPIPE_HOST}/{DB_ALIAS}')
        dsn = driver.core._connect_helper(None, NPIPE_HOST, SVC_NAME, DB_WIN_PATH, NetProtocol.WNET)
        self.assertEqual(dsn, f'wnet://{NPIPE_HOST}:{SVC_NAME}/{DB_WIN_PATH}')
    def test_connect_dsn(self):
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertIsNotNone(con._att)
            dpb = [1, 0x1c, len(FBTEST_USER)]
            dpb.extend(ord(x) for x in FBTEST_USER)
            dpb.extend((0x1d, len(FBTEST_PASSWORD)))
            dpb.extend(ord(x) for x in FBTEST_PASSWORD)
            dpb.extend((ord('?'), 4, 3, 0, 0, 0))
            self.assertEqual(con._dpb, bytes(dpb))
            self.assertEqual(con.dsn, self.dbfile)
    def test_connect_config(self):
        srv_config = f"""
        [server.local]
        host = {FBTEST_HOST}
        user = {FBTEST_USER}
        password = {FBTEST_PASSWORD}
        port = 3050
        """
        db_config = f"""
        [test_db1]
        server = server.local
        database = {self.dbfile}
        user = {FBTEST_USER}
        password = {FBTEST_PASSWORD}
        utf8filename = true
        charset = UTF8
        sql_dialect = 3
        """
        driver_config.register_server('server.local', srv_config)
        driver_config.register_database('test_db1', db_config)
        #
        with connect('test_db1') as con:
            con._logging_id_ = self.__class__.__name__
            self.assertIsNotNone(con._att)
            dpb = [1, 0x1c, len(FBTEST_USER)]
            dpb.extend(ord(x) for x in FBTEST_USER)
            dpb.extend((0x1d, len(FBTEST_PASSWORD)))
            dpb.extend(ord(x) for x in FBTEST_PASSWORD)
            dpb.extend((ord('?'), 4, 3, 0, 0, 0))
            dpb.extend((ord('0'), 4, ord('U'), ord('T'), ord('F'), ord('8')))
            dpb.extend((77, 4, 1, 0, 0, 0))
            self.assertEqual(con._dpb, bytes(dpb))
            self.assertEqual(con.dsn, f'{FBTEST_HOST}/3050:{self.dbfile}')
        with connect('test_db1', no_gc=1, no_db_triggers=1) as con:
            con._logging_id_ = self.__class__.__name__
            dpb = [1, 0x1c, len(FBTEST_USER)]
            dpb.extend(ord(x) for x in FBTEST_USER)
            dpb.extend((0x1d, len(FBTEST_PASSWORD)))
            dpb.extend(ord(x) for x in FBTEST_PASSWORD)
            dpb.extend((ord('?'), 4, 3, 0, 0, 0))
            dpb.extend((ord('0'), 4, ord('U'), ord('T'), ord('F'), ord('8')))
            dpb.extend([types.DPBItem.NO_GARBAGE_COLLECT, 4, 1, 0, 0, 0])
            dpb.extend((types.DPBItem.UTF8_FILENAME, 4, 1, 0, 0, 0))
            dpb.extend([types.DPBItem.NO_DB_TRIGGERS, 4, 1, 0, 0, 0])
            self.assertEqual(con._dpb, bytes(dpb))
            self.assertEqual(con.dsn, f'{FBTEST_HOST}/3050:{self.dbfile}')
        # protocols
        cfg = driver_config.get_database('test_db1')
        cfg.protocol.value = NetProtocol.INET
        with connect('test_db1') as con:
            con._logging_id_ = self.__class__.__name__
            self.assertIsNotNone(con._att)
            self.assertEqual(con.dsn, f'inet://{FBTEST_HOST}:3050/{self.dbfile}')
        cfg.protocol.value = NetProtocol.INET4
        with connect('test_db1') as con:
            con._logging_id_ = self.__class__.__name__
            self.assertIsNotNone(con._att)
            self.assertEqual(con.dsn, f'inet4://{FBTEST_HOST}:3050/{self.dbfile}')
    def test_properties(self):
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            if con.info.engine_version >= 3.0:
                self.assertIsInstance(con.info, driver.core.DatabaseInfoProvider3)
            if con.info.engine_version >= 4.0:
                self.assertIsInstance(con.info, driver.core.DatabaseInfoProvider)
            self.assertIsNone(con.charset)
            self.assertEqual(con.sql_dialect, 3)
            self.assertIn(con.main_transaction, con.transactions)
            self.assertIn(con.query_transaction, con.transactions)
            self.assertEqual(len(con.transactions), 2)
            self.assertEqual(con.default_tpb, tpb(Isolation.SNAPSHOT))
            self.assertFalse(con.is_active())
            self.assertFalse(con.is_closed())
    def test_connect_role(self):
        rolename = 'role'
        with connect(self.dbfile, user=FBTEST_USER,
                     password=FBTEST_PASSWORD, role=rolename) as con:
            con._logging_id_ = self.__class__.__name__
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
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
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
            tr = con.transaction_manager()
            self.assertIsInstance(tr, driver.core.TransactionManager)
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
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            #con.execute_immediate("recreate table t (c1 integer)")
            #con.commit()
            con.execute_immediate("delete from t")
            con.commit()
    def test_db_info(self):
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            # Resize response buffer
            con.info.response.resize(5)
            self.assertEqual(len(con.info.response.raw), 5)
            con.info.get_info(DbInfoCode.USER_NAMES)
            self.assertGreater(len(con.info.response.raw), 5)
            # Properties
            self.assertIn('Firebird', con.info.server_version)
            self.assertIn('Firebird', con.info.firebird_version)
            self.assertIsInstance(con.info.version, str)
            self.assertGreaterEqual(con.info.engine_version, 3.0)
            self.assertGreaterEqual(con.info.ods, 12.0)
            #
            self.assertEqual(con.info.page_size, 8192)
            self.assertGreater(con.info.id, 0)
            self.assertEqual(con.info.sql_dialect, 3)
            self.assertEqual(con.info.name.upper(), self.dbfile.upper())
            self.assertIsInstance(con.info.site, str)
            self.assertIsInstance(con.info.implementation, driver.types.Implementation)
            self.assertIsInstance(con.info.provider, driver.types.DbProvider)
            self.assertIsInstance(con.info.db_class, driver.types.DbClass)
            self.assertIsInstance(con.info.creation_date, datetime.date)
            self.assertGreaterEqual(con.info.ods_version, 11)
            self.assertGreaterEqual(con.info.ods_minor_version, 0)
            self.assertGreaterEqual(con.info.page_cache_size, 75)
            if self.version == FB30:
                self.assertEqual(con.info.pages_allocated, 367)
            else:
                self.assertEqual(con.info.pages_allocated, 389)
            self.assertGreater(con.info.pages_used, 300)
            self.assertGreaterEqual(con.info.pages_free, 0)
            self.assertEqual(con.info.sweep_interval, 20000)
            self.assertEqual(con.info.access_mode, DbAccessMode.READ_WRITE)
            self.assertEqual(con.info.space_reservation, DbSpaceReservation.RESERVE)
            self.assertEqual(con.info.write_mode, DbWriteMode.SYNC)
            self.assertGreater(con.info.current_memory, 0)
            self.assertGreater(con.info.max_memory, 0)
            self.assertGreaterEqual(con.info.max_memory, con.info.current_memory)
            self.assertGreater(con.info.oit, 1)
            self.assertGreater(con.info.oat, 1)
            self.assertGreater(con.info.ost, 1)
            self.assertGreater(con.info.next_transaction, 1)
            self.assertLessEqual(con.info.oit, con.info.oat)
            self.assertLessEqual(con.info.oit, con.info.ost)
            self.assertLessEqual(con.info.oit, con.info.next_transaction)
            self.assertLessEqual(con.info.oat, con.info.next_transaction)
            self.assertLessEqual(con.info.ost, con.info.next_transaction)
            #
            self.assertIsInstance(con.info.reads, int)
            self.assertIsInstance(con.info.fetches, int)
            self.assertIsInstance(con.info.writes, int)
            self.assertIsInstance(con.info.marks, int)
            self.assertIsInstance(con.info.cache_hit_ratio, float)
            # Functions
            self.assertEqual(len(con.info.get_page_content(0)), con.info.page_size)
            self.assertIsInstance(con.info.is_compressed(), bool)
            self.assertIsInstance(con.info.is_encrypted(), bool)
            self.assertListEqual(con.info.get_active_transaction_ids(), [])
            with con.transaction_manager() as t1, con.transaction_manager() as t2:
                self.assertListEqual(con.info.get_active_transaction_ids(),
                                     [t1.info.id, t2.info.id])
                self.assertEqual(con.info.get_active_transaction_count(), 2)
            s = con.info.get_table_access_stats()
            self.assertIn(len(s), [6,12])
            self.assertIsInstance(s[0], driver.types.TableAccessStats)
            # Low level info calls
            with con.transaction_manager() as t1, con.transaction_manager() as t2:
                self.assertListEqual(con.info.get_info(DbInfoCode.ACTIVE_TRANSACTIONS),
                                     [t1.info.id, t2.info.id])
            #
            self.assertEqual(con.info.get_info(DbInfoCode.PAGE_SIZE), 8192)
            self.assertEqual(con.info.get_info(DbInfoCode.DB_READ_ONLY), 0)
            self.assertEqual(con.info.get_info(DbInfoCode.DB_SQL_DIALECT), 3)
            res = con.info.get_info(DbInfoCode.USER_NAMES)
            self.assertDictEqual(res, {'SYSDBA': 1})
            res = con.info.get_info(DbInfoCode.READ_SEQ_COUNT)
            self.assertListEqual(list(res), [0, 1])
            #
            self.assertIsInstance(con.info.get_info(DbInfoCode.ALLOCATION), int)
            self.assertIsInstance(con.info.get_info(DbInfoCode.BASE_LEVEL), int)
            res = con.info.get_info(DbInfoCode.DB_ID)
            self.assertIsInstance(res, list)
            self.assertEqual(res[0].upper(), self.dbfile.upper())
            res = con.info.get_info(DbInfoCode.IMPLEMENTATION)
            self.assertIsInstance(res, tuple)
            self.assertEqual(len(res), 4)
            self.assertIsInstance(res[0], driver.types.ImpCPU)
            self.assertIsInstance(res[1], driver.types.ImpOS)
            self.assertIsInstance(res[2], driver.types.ImpCompiler)
            self.assertIsInstance(res[3], driver.types.ImpFlags)
            res = con.info.get_info(DbInfoCode.IMPLEMENTATION_OLD)
            self.assertIsInstance(res, tuple)
            self.assertEqual(len(res), 2)
            self.assertIsInstance(res[0], int)
            self.assertIsInstance(res[1], int)
            self.assertIn(res[0], driver.types.Implementation._value2member_map_)
            self.assertIn('Firebird', con.info.get_info(DbInfoCode.VERSION))
            self.assertIn('Firebird', con.info.get_info(DbInfoCode.FIREBIRD_VERSION))
            self.assertIn(con.info.get_info(DbInfoCode.NO_RESERVE), (0, 1))
            self.assertIn(con.info.get_info(DbInfoCode.FORCED_WRITES), (0, 1))
            self.assertIsInstance(con.info.get_info(DbInfoCode.BASE_LEVEL), int)
            self.assertIsInstance(con.info.get_info(DbInfoCode.ODS_VERSION), int)
            self.assertIsInstance(con.info.get_info(DbInfoCode.ODS_MINOR_VERSION), int)
            #


class TestTransaction(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(f'{FBTEST_HOST}:{self.dbfile}', user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        #self.con.execute_immediate("recreate table t (c1 integer)")
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_cursor(self):
        with self.con:
            tr = self.con.main_transaction
            tr.begin()
            with tr.cursor() as cur:
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
        with self.con.cursor() as cur:
            with transaction(self.con):
                cur.execute("insert into t (c1) values (1)")

            cur.execute("select * from t")
            rows = cur.fetchall()
            self.assertListEqual(rows, [(1,)])

            try:
                with transaction(self.con):
                    cur.execute("delete from t")
                    raise Exception()
            except Exception:
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
        with tr.cursor() as cur:
            cur.execute("select * from t")
            rows = cur.fetchall()
        self.assertListEqual(rows, [(1,)])
    def test_fetch_after_commit(self):
        self.con.execute_immediate("insert into t (c1) values (1)")
        self.con.commit()
        with self.con.cursor() as cur:
            cur.execute("select * from t")
            self.con.commit()
            with self.assertRaises(InterfaceError) as cm:
                cur.fetchall()
            self.assertTupleEqual(cm.exception.args, ('Cannot fetch from cursor that did not executed a statement.',))
    def test_fetch_after_rollback(self):
        self.con.execute_immediate("insert into t (c1) values (1)")
        self.con.rollback()
        with self.con.cursor() as cur:
            cur.execute("select * from t")
            self.con.commit()
            with self.assertRaises(InterfaceError) as cm:
                cur.fetchall()
            self.assertTupleEqual(cm.exception.args, ('Cannot fetch from cursor that did not executed a statement.',))
    def test_tpb(self):
        tpb = TPB(isolation=Isolation.READ_COMMITTED, no_auto_undo=True)
        tpb.lock_timeout = 10
        tpb.reserve_table('COUNTRY', TableShareMode.PROTECTED, TableAccessMode.LOCK_WRITE)
        tpb_buffer = tpb.get_buffer()
        with self.con.transaction_manager(tpb_buffer) as tr:
            info = tr.info.get_info(TraInfoCode.ISOLATION)
            if self.version == FB40:
                self.assertIn(info, [Isolation.READ_COMMITTED_READ_CONSISTENCY,
                                     Isolation.READ_COMMITTED_RECORD_VERSION])
            else:
                self.assertEqual(info, Isolation.READ_COMMITTED_RECORD_VERSION)
            self.assertEqual(tr.info.get_info(TraInfoCode.ACCESS), TraInfoAccess.READ_WRITE)
            self.assertEqual(tr.info.lock_timeout, 10)
        del tpb
        tpb = TPB()
        tpb.parse_buffer(tpb_buffer)
        self.assertEqual(tpb.access_mode, TraAccessMode.WRITE)
        self.assertEqual(tpb.isolation, Isolation.READ_COMMITTED_RECORD_VERSION)
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
            self.assertTrue(tr.is_active())
            self.assertIn(self.dbfile, tr.info.database)
            self.assertEqual(tr.info.isolation, Isolation.SNAPSHOT)
            #
            self.assertGreater(tr.info.id, 0)
            self.assertGreater(tr.info.oit, 0)
            self.assertGreater(tr.info.oat, 0)
            self.assertGreater(tr.info.ost, 0)
            self.assertEqual(tr.info.lock_timeout, -1)  # NO_WAIT (WAIT = 0xffffffff)
            self.assertEqual(tr.info.isolation, Isolation.SNAPSHOT)

class TestDistributedTransaction(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.db1 = os.path.join(self.dbpath, 'fbtest-1.fdb')
        cfg = driver_config.get_database('dts-1')
        if cfg is None:
            cfg = driver_config.register_database('dts-1')
        cfg.server.value = 'FBTEST_HOST'
        cfg.database.value = self.db1
        cfg.no_linger.value = True
        self.con1 = create_database('dts-1', user=FBTEST_USER, password=FBTEST_PASSWORD, overwrite=True)
        self.con1._logging_id_ = self.__class__.__name__
        self.con1.execute_immediate("recreate table T (PK integer, C1 integer)")
        self.con1.commit()

        self.db2 = os.path.join(self.dbpath, 'fbtest-2.fdb')
        cfg = driver_config.get_database('dts-2')
        if cfg is None:
            cfg = driver_config.register_database('dts-2')
        cfg.server.value = 'FBTEST_HOST'
        cfg.database.value = self.db2
        cfg.no_linger.value = True
        self.con2 = create_database('dts-2', user=FBTEST_USER, password=FBTEST_PASSWORD, overwrite=True)
        self.con2._logging_id_ = self.__class__.__name__
        self.con2.execute_immediate("recreate table T (PK integer, C1 integer)")
        self.con2.commit()
    def tearDown(self):
        #if self.con1 and self.con1.group:
            ## We can't drop database via connection in group
            #self.con1.group.disband()
        if self.con1 is not None:
            self.con1.close()
        if self.con2 is not None:
            self.con2.close()
        #
        with connect_server('FBTEST_HOST') as srv:
            srv.database.shutdown(database=self.db1, mode=ShutdownMode.FULL,
                                  method=ShutdownMethod.FORCED, timeout=0)
            srv.database.bring_online(database=self.db1)
        with connect('dts-1') as con:
            con.drop_database()
        #
        with connect_server('FBTEST_HOST') as srv:
            srv.database.shutdown(database=self.db2, mode=ShutdownMode.FULL,
                                  method=ShutdownMethod.FORCED, timeout=0)
            srv.database.bring_online(database=self.db2)
        with connect('dts-2') as con:
            con.drop_database()
    def test_context_manager(self):
        with DistributedTransactionManager((self.con1, self.con2)) as dt:
            q = 'select * from T order by pk'
            with dt.cursor(self.con1) as c1, self.con1.cursor() as cc1, \
                 dt.cursor(self.con2) as c2, self.con2.cursor() as cc2:

                # Distributed transaction: COMMIT
                with transaction(dt):
                    c1.execute('insert into t (pk) values (1)')
                    c2.execute('insert into t (pk) values (1)')

                with transaction(self.con1):
                    cc1.execute(q)
                    result = cc1.fetchall()
                self.assertListEqual(result, [(1, None)])
                with transaction(self.con2):
                    cc2.execute(q)
                    result = cc2.fetchall()
                self.assertListEqual(result, [(1, None)])

                # Distributed transaction: ROLLBACK
                try:
                    with transaction(dt):
                        c1.execute('insert into t (pk) values (2)')
                        c2.execute('insert into t (pk) values (2)')
                        raise Exception()
                except Exception:
                    pass

                c1.execute(q)
                result = c1.fetchall()
                self.assertListEqual(result, [(1, None)])
                c2.execute(q)
                result = c2.fetchall()
                self.assertListEqual(result, [(1, None)])
    def test_simple_dt(self):
        with DistributedTransactionManager((self.con1, self.con2)) as dt:
            q = 'select * from T order by pk'
            with dt.cursor(self.con1) as c1, self.con1.cursor() as cc1, \
                 dt.cursor(self.con2) as c2, self.con2.cursor() as cc2:
                # Distributed transaction: COMMIT
                c1.execute('insert into t (pk) values (1)')
                c2.execute('insert into t (pk) values (1)')
                dt.commit()

                with transaction(self.con1):
                    cc1.execute(q)
                    result = cc1.fetchall()
                self.assertListEqual(result, [(1, None)])
                with transaction(self.con2):
                    cc2.execute(q)
                    result = cc2.fetchall()
                self.assertListEqual(result, [(1, None)])

                # Distributed transaction: PREPARE+COMMIT
                c1.execute('insert into t (pk) values (2)')
                c2.execute('insert into t (pk) values (2)')
                dt.prepare()
                dt.commit()

                with transaction(self.con1):
                    cc1.execute(q)
                    result = cc1.fetchall()
                self.assertListEqual(result, [(1, None), (2, None)])
                with transaction(self.con2):
                    cc2.execute(q)
                    result = cc2.fetchall()
                self.assertListEqual(result, [(1, None), (2, None)])

                # Distributed transaction: SAVEPOINT+ROLLBACK to it
                c1.execute('insert into t (pk) values (3)')
                dt.savepoint('CG_SAVEPOINT')
                c2.execute('insert into t (pk) values (3)')
                dt.rollback(savepoint='CG_SAVEPOINT')

                c1.execute(q)
                result = c1.fetchall()
                self.assertListEqual(result, [(1, None), (2, None), (3, None)])
                c2.execute(q)
                result = c2.fetchall()
                self.assertListEqual(result, [(1, None), (2, None)])

                # Distributed transaction: ROLLBACK
                dt.rollback()

                with transaction(self.con1):
                    cc1.execute(q)
                    result = cc1.fetchall()
                self.assertListEqual(result, [(1, None), (2, None)])
                with transaction(self.con2):
                    cc2.execute(q)
                    result = cc2.fetchall()
                self.assertListEqual(result, [(1, None), (2, None)])

                # Distributed transaction: EXECUTE_IMMEDIATE
                dt.execute_immediate('insert into t (pk) values (3)')
                dt.commit()

                with transaction(self.con1):
                    cc1.execute(q)
                    result = cc1.fetchall()
                self.assertListEqual(result, [(1, None), (2, None), (3, None)])
                with transaction(self.con2):
                    cc2.execute(q)
                    result = cc2.fetchall()
                self.assertListEqual(result, [(1, None), (2, None), (3, None)])
    def test_limbo_transactions(self):
        self.skipTest('Not implemented yet')
        #return
        #with connect_server('FBTEST_HOST') as svc:
            #dt = DistributedTransactionManager([self.con1, self.con2])
            #ids1 = svc.database.get_limbo_transaction_ids(database=self.db1)
            #self.assertEqual(ids1, [])
            #ids2 = svc.database.get_limbo_transaction_ids(database=self.db2)
            #self.assertEqual(ids2, [])
            #dt.execute_immediate('insert into t (pk) values (3)')
            #dt.prepare()
            ## Force out both connections
            #dt._tra.release()
            #dt._tra = None
            #dt.close()
            #self.con1.close()
            #self.con2.close()
            ##
            #self.con1 = connect('dts-1')
            #self.con2 = connect('dts-2')
            #ids1 = svc.database.get_limbo_transaction_ids(database=self.db1)
            #id1 = ids1[0]
            #ids2 = svc.database.get_limbo_transaction_ids(database=self.db2)
            #id2 = ids2[0]
            ## Data should be blocked by limbo transaction
            #c1 = self.con1.cursor()
            #c1.execute('select * from t')
            #with self.assertRaises(DatabaseError) as cm:
                #row = c1.fetchall()
            #self.assertTupleEqual(cm.exception.args,
                                  #('Cursor.fetchone:\n- SQLCODE: -911\n- record from transaction %i is stuck in limbo' % id1, -911, 335544459))
            #c2 = self.con2.cursor()
            #c2.execute('select * from t')
            #with self.assertRaises(DatabaseError) as cm:
                #row = c2.fetchall()
            #self.assertTupleEqual(cm.exception.args,
                                  #('Cursor.fetchone:\n- SQLCODE: -911\n- record from transaction %i is stuck in limbo' % id2, -911, 335544459))
            ## resolve via service
            #svc = connect_server(host=FBTEST_HOST, password=FBTEST_PASSWORD)
            #svc.database.commit_limbo_transaction(database=self.db1, transaction_id=id1)
            #svc.database.rollback_limbo_transaction(database=self.db2, transaction_id=id2)

            ## check the resolution
            #c1 = self.con1.cursor()
            #c1.execute('select * from t')
            #row = c1.fetchall()
            #self.assertListEqual(row, [(3, None)])
            #c2 = self.con2.cursor()
            #c2.execute('select * from t')
            #row = c2.fetchall()
            #self.assertListEqual(row, [])

class TestCursor(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        #self.con.execute_immediate("recreate table t (c1 integer primary key)")
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_execute(self):
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur2:
            cur2.execute('select * from proj_dept_budget')
            self.assertEqual(repr(cur2.description),
                             "(('FISCAL_YEAR', <class 'int'>, 11, 4, 0, 0, False), " \
                             "('PROJ_ID', <class 'str'>, 5, 5, 0, 0, False), " \
                             "('DEPT_NO', <class 'str'>, 3, 3, 0, 0, False), " \
                             "('QUART_HEAD_CNT', <class 'list'>, -1, 8, 0, 0, True), " \
                             "('PROJECTED_BUDGET', <class 'decimal.Decimal'>, 20, 8, 12, -2, True))")
    def test_exec_after_close(self):
        with self.con.cursor() as cur:
            cur.execute('select * from country')
            row = cur.fetchone()
            self.assertTupleEqual(row, ('USA', 'Dollar'))
            cur.close()
            cur.execute('select * from country')
            row = cur.fetchone()
            self.assertTupleEqual(row, ('USA', 'Dollar'))
    def test_fetchone(self):
        with self.con.cursor() as cur:
            cur.execute('select * from country')
            row = cur.fetchone()
            self.assertTupleEqual(row, ('USA', 'Dollar'))
    def test_fetchall(self):
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
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
    def test_affected_rows(self):
        with self.con.cursor() as cur:
            self.assertEqual(cur.affected_rows, -1)
            cur.execute('select * from project')
            self.assertEqual(cur.affected_rows, 0)
            cur.fetchone()
            if sys.platform == 'win32':
                rcount = 6
            else:
                rcount = 1
            self.assertEqual(cur.affected_rows, rcount)
            self.assertEqual(cur.rowcount, rcount)
    def test_name(self):
        def assign_name():
            cur.set_cursor_name('testx')
        with self.con.cursor() as cur:
            self.assertIsNone(cur.name)
            self.assertRaises(InterfaceError, assign_name)
            cur.execute('select * from country')
            cur.set_cursor_name('test')
            self.assertEqual(cur.name, 'test')
            self.assertRaises(InterfaceError, assign_name)
    def test_use_after_close(self):
        cmd = 'select * from country'
        with self.con.cursor() as cur:
            cur.execute(cmd)
            cur.close()
            with self.assertRaises(InterfaceError) as cm:
                cur.fetchone()
            self.assertTupleEqual(cm.exception.args, ('Cannot fetch from cursor that did not executed a statement.',))

class TestScrollableCursor(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(database=self.dbfile,
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        #self.con.execute_immediate("recreate table t (c1 integer primary key)")
        #self.con.execute_immediate("delete from t")
        #self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_scrollable(self):
        if sys.platform == 'win32':
            self.skipTest('Does not work on Windows')
        rows = [('USA', 'Dollar'), ('England', 'Pound'), ('Canada', 'CdnDlr'),
                ('Switzerland', 'SFranc'), ('Japan', 'Yen'), ('Italy', 'Euro'),
                ('France', 'Euro'), ('Germany', 'Euro'), ('Australia', 'ADollar'),
                ('Hong Kong', 'HKDollar'), ('Netherlands', 'Euro'),
                ('Belgium', 'Euro'), ('Austria', 'Euro'), ('Fiji', 'FDollar'),
                ('Russia', 'Ruble'), ('Romania', 'RLeu')]
        with self.con.cursor() as cur:
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
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        self.con2 = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con2._logging_id_ = self.__class__.__name__
        #self.con.execute_immediate("recreate table t (c1 integer)")
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
        self.con2.close()
    def test_basic(self):
        self.assertListEqual(self.con._statements, [])
        with self.con.cursor() as cur:
            ps = cur.prepare('select * from country')
            self.assertEqual(len(self.con._statements), 1)
            self.assertEqual(ps._in_cnt, 0)
            self.assertEqual(ps._out_cnt, 2)
            self.assertEqual(ps.type, StatementType.SELECT)
            self.assertEqual(ps.sql, 'select * from country')
            self.con.close()
            self.assertEqual(self.con._statements, [])
    def test_get_plan(self):
        with self.con.cursor() as cur:
            ps = cur.prepare('select * from job')
            self.assertEqual(ps.plan, "PLAN (JOB NATURAL)")
    def test_execution(self):
        with self.con.cursor() as cur:
            ps = cur.prepare('select * from country')
            cur.execute(ps)
            row = cur.fetchone()
            self.assertTupleEqual(row, ('USA', 'Dollar'))
    def test_wrong_cursor(self):
        with self.con.cursor() as cur:
            with self.con2.cursor() as cur2:
                ps = cur.prepare('select * from country')
                with self.assertRaises(InterfaceError) as cm:
                    cur2.execute(ps)
                self.assertTupleEqual(cm.exception.args,
                                      ('Cannot execute Statement that was created by different Connection.',))

class TestArrays(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
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
        self.c5 = [datetime.datetime(2012, 11, 22, 12, 8, 24, 474800), datetime.datetime(2012, 11, 22, 12, 8, 24, 474800)]
        self.c6 = [datetime.time(12, 8, 24, 474800), datetime.time(12, 8, 24, 474800)]
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
        with self.con.cursor() as cur:
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
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        self.con2 = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD, charset='utf-8')
        self.con2._logging_id_ = self.__class__.__name__
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
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
            now = datetime.datetime(2011, 11, 13, 15, 00, 1, 200000)
            cur.execute('insert into T2 (C1,C6,C7,C8) values (?,?,?,?)', [3, now.date(), now.time(), now])
            self.con.commit()
            cur.execute('select C1,C6,C7,C8 from T2 where C1 = 3')
            rows = cur.fetchall()
            self.assertListEqual(rows,
                                 [(3, datetime.date(2011, 11, 13), datetime.time(15, 0, 1, 200000),
                                   datetime.datetime(2011, 11, 13, 15, 0, 1, 200000))])

            cur.execute('insert into T2 (C1,C6,C7,C8) values (?,?,?,?)', [4, '2011-11-13', '15:0:1:200', '2011-11-13 15:0:1:2000'])
            self.con.commit()
            cur.execute('select C1,C6,C7,C8 from T2 where C1 = 4')
            rows = cur.fetchall()
            self.assertListEqual(rows,
                                 [(4, datetime.date(2011, 11, 13), datetime.time(15, 0, 1, 200000),
                                   datetime.datetime(2011, 11, 13, 15, 0, 1, 200000))])
    def test_insert_blob(self):
        with self.con.cursor() as cur, self.con2.cursor() as cur2:
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
            # BLOB bigger than stream_blob_threshold
            big_blob = '123456789' * 10000
            cur.execute('insert into T2 (C1,C9) values (?,?)', [5, big_blob])
            cur.transaction.commit()
            cur.execute('select C1,C9 from T2 where C1 = 5')
            row = cur.fetchone()
            self.assertIsInstance(row[1], driver.core.BlobReader)
            #self.assertEqual(row[1].read(), big_blob)
            # Unicode in BLOB
            blob_text = 'This is a BLOB with characters beyond ascii: ěščřžýáíé'
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
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
            cur.execute('insert into T2 (C1,C10,C11) values (?,?,?)', [6, 1.1, 1.1])
            cur.execute('insert into T2 (C1,C10,C11) values (?,?,?)', [6, decimal.Decimal('100.11'), decimal.Decimal('100.11')])
            self.con.commit()
            cur.execute('select C1,C10,C11 from T2 where C1 = 6')
            rows = cur.fetchall()
            self.assertListEqual(rows,
                                 [(6, decimal.Decimal('1.1'), decimal.Decimal('1.1')),
                                  (6, decimal.Decimal('100.11'), decimal.Decimal('100.11'))])
    def test_insert_returning(self):
        with self.con.cursor() as cur:
            cur.execute('insert into T2 (C1,C10,C11) values (?,?,?) returning C1', [7, 1.1, 1.1])
            result = cur.fetchall()
            self.assertListEqual(result, [(7,)])
    def test_insert_boolean(self):
        with self.con.cursor() as cur:
            cur.execute('insert into T2 (C1,C17) values (?,?) returning C1', [8, True])
            cur.statement._logging_id_ = 'Stmt[1]'
            cur.execute('insert into T2 (C1,C17) values (?,?) returning C1', [8, False])
            cur.execute('select C1,C17 from T2 where C1 = 8')
            cur.statement._logging_id_ = 'Stmt[2]'
            result = cur.fetchall()
            self.assertListEqual(result, [(8, True), (8, False)])

class TestStoredProc(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        self.con.execute_immediate("delete from t")
        self.con.commit()
    def tearDown(self):
        self.con.close()
    def test_callproc(self):
        with self.con.cursor() as cur:
            cur.callproc('sub_tot_budget', ['100'])
            result = cur.fetchone()
            self.assertTupleEqual(result, (decimal.Decimal('3800000'), decimal.Decimal('760000'),
                                           decimal.Decimal('500000'), decimal.Decimal('1500000')))
            #
            cur.callproc('sub_tot_budget', [100])
            result = cur.fetchone()
            self.assertTupleEqual(result, (decimal.Decimal('3800000'), decimal.Decimal('760000'),
                                           decimal.Decimal('500000'), decimal.Decimal('1500000')))
            #
            cur.callproc('proc_test', [10])
            result = cur.fetchone()
            self.assertIsNone(result)
            self.con.commit()
            cur.execute('select c1 from t')
            result = cur.fetchone()
            self.assertTupleEqual(result, tuple([10]))

class TestServerStandard(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
    def test_attach(self):
        svc = connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD)
        svc.close()
    def test_query(self):
        with connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc:
            self.assertEqual(svc.info.manager_version, 2)
            self.assertTrue(svc.info.version.startswith(self.version))
            self.assertGreaterEqual(float(self.version), svc.info.engine_version)
            self.assertIn('Firebird', svc.info.architecture)
            x = svc.info.home_directory
            # On Windows it returns 'security.db', a bug?
            #self.assertIn('security.db', svc.info.security_database)
            if self.version == FB40:
                self.assertIn('security4.fdb'.upper(), svc.info.security_database.upper())
            else:
                self.assertIn('security3.fdb', svc.info.security_database)
            x = svc.info.lock_directory
            x = svc.info.capabilities
            self.assertIn(ServerCapability.REMOTE_HOP, x)
            self.assertNotIn(ServerCapability.NO_FORCED_WRITE, x)
            x = svc.info.message_directory
            with connect(f"{FBTEST_HOST}:{self.dbfile}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con1:
                con1._logging_id_ = self.__class__.__name__
                with connect(f'{FBTEST_HOST}:employee', user=FBTEST_USER, password=FBTEST_PASSWORD) as con2:
                    con2._logging_id_ = self.__class__.__name__
                    self.assertGreaterEqual(len(svc.info.attached_databases), 2,
                                            "Should work for Superserver, may fail with value 0 for Classic")
                    self.assertIn(self.dbfile.upper(),
                                  [s.upper() for s in svc.info.attached_databases])
                    self.assertGreaterEqual(svc.info.connection_count, 2)
            # BAD request code
            with self.assertRaises(Error) as cm:
                svc.info.get_info(255)
            self.assertTupleEqual(cm.exception.args,
                                  ("feature is not supported",))

    def test_running(self):
        with connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc:
            self.assertFalse(svc.is_running())
            svc.info.get_log()
            self.assertTrue(svc.is_running())
            # fetch materialized
            print(''.join(svc.readlines()))
            self.assertFalse(svc.is_running())
    def test_wait(self):
        with connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc:
            self.assertFalse(svc.is_running())
            svc.info.get_log()
            self.assertTrue(svc.is_running())
            svc.wait()
            self.assertFalse(svc.is_running())

class TestServerServices(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.fbk = os.path.join(self.dbpath, 'test_employee.fbk')
        self.fbk2 = os.path.join(self.dbpath, 'test_employee.fbk2')
        self.rfdb = os.path.join(self.dbpath, 'test_employee.fdb')
        self.svc = connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD)
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        self.con.execute_immediate("delete from t")
        self.con.commit()
        c = create_database(f"{FBTEST_HOST}:{self.rfdb}",
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
    def test_01_output_by_line(self):
        self.svc.mode = SrvInfoCode.LINE
        self.test_03_log()
    def test_02_output_to_eof(self):
        self.svc.mode = SrvInfoCode.TO_EOF
        self.test_03_log()
    def test_03_log(self):
        def fetchline(line):
            output.append(line)

        self.svc.info.get_log()
        # fetch materialized
        log = self.svc.readlines()
        self.assertTrue(log)
        self.assertIsInstance(log, type(list()))
        # iterate over result
        self.svc.info.get_log()
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.info.get_log(callback=fetchline)
        self.assertGreater(len(output), 0)
        self.assertEqual(output, log)
    def test_04_get_limbo_transaction_ids(self):
        #self.skipTest('Not implemented yet')
        ids = self.svc.database.get_limbo_transaction_ids(database='employee')
        self.assertIsInstance(ids, type(list()))
    def test_05_trace(self):
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
        with connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svc2, \
             connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD) as svcx:
            # Start trace sessions
            trace1_id = self.svc.trace.start(config=trace_config, name='test_trace_1')
            trace2_id = svc2.trace.start(config=trace_config)
            # check sessions
            sessions = svcx.trace.sessions
            self.assertIn(trace1_id, sessions)
            self.assertEqual(sessions[trace1_id].name, 'test_trace_1')
            self.assertEqual(sessions[trace2_id].name, '')
            # Windows returns SYSDBA
            #if sys.platform == 'win32':
                #self.assertEqual(sessions[trace1_id].user, 'SYSDBA')
                #self.assertEqual(sessions[trace2_id].user, 'SYSDBA')
            #else:
                #self.assertEqual(sessions[trace1_id].user, '')
                #self.assertEqual(sessions[trace2_id].user, '')
            self.assertEqual(sessions[trace1_id].user, 'SYSDBA')
            self.assertEqual(sessions[trace2_id].user, 'SYSDBA')
            self.assertIn(trace2_id, sessions)
            self.assertListEqual(sessions[trace1_id].flags, ['active', ' trace'])
            self.assertListEqual(sessions[trace2_id].flags, ['active', ' trace'])
            # Pause session
            svcx.trace.suspend(session_id=trace2_id)
            self.assertIn('suspend', svcx.trace.sessions[trace2_id].flags)
            # Resume session
            svcx.trace.resume(session_id=trace2_id)
            self.assertIn('active', svcx.trace.sessions[trace2_id].flags)
            # Stop session
            svcx.trace.stop(session_id=trace2_id)
            self.assertNotIn(trace2_id, svcx.trace.sessions)
            # Finalize
            svcx.trace.stop(session_id=trace1_id)
    def test_06_get_users(self):
        users = self.svc.user.get_all()
        self.assertIsInstance(users, type(list()))
        self.assertIsInstance(users[0], driver.core.UserInfo)
        self.assertEqual(users[0].user_name, 'SYSDBA')
    def test_07_manage_user(self):
        USER_NAME = 'DRIVER_TEST'
        try:
            self.svc.user.delete(USER_NAME)
        except DatabaseError as e:
            if e.sqlstate == '28000':
                pass
            else:
                raise
        # Add user
        self.svc.user.add(user_name=USER_NAME, password='DRIVER_TEST',
                          first_name='Firebird', middle_name='Driver', last_name='Test')
        self.assertTrue(self.svc.user.exists(USER_NAME))
        users = [u for u in self.svc.user.get_all() if u.user_name == USER_NAME]
        self.assertTrue(users)
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].first_name, 'Firebird')
        self.assertEqual(users[0].middle_name, 'Driver')
        self.assertEqual(users[0].last_name, 'Test')
        # Modify user
        self.svc.user.update(USER_NAME, first_name='XFirebird', middle_name='XDriver', last_name='XTest')
        user = self.svc.user.get(USER_NAME)
        self.assertEqual(user.user_name, USER_NAME)
        self.assertEqual(user.first_name, 'XFirebird')
        self.assertEqual(user.middle_name, 'XDriver')
        self.assertEqual(user.last_name, 'XTest')
        # Delete user
        self.svc.user.delete(USER_NAME)
        self.assertFalse(self.svc.user.exists(USER_NAME))

class TestServerDatabaseServices(DriverTestBase):
    def setUp(self):
        super().setUp()
        # f"{FBTEST_HOST}:{os.path.join(self.dbpath, 'test_employee.fdb')}"
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.fbk = os.path.join(self.dbpath, 'test_employee.fbk')
        self.fbk2 = os.path.join(self.dbpath, 'test_employee.fbk2')
        self.rfdb = os.path.join(self.dbpath, 'test_employee.fdb')
        self.svc = connect_server(FBTEST_HOST, user='SYSDBA', password=FBTEST_PASSWORD)
        self.con = connect(f"{FBTEST_HOST}:{self.dbfile}",
                           user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        self.con.execute_immediate("delete from t")
        self.con.commit()
        c = create_database(f"{FBTEST_HOST}:{self.rfdb}",
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
    def test_get_statistics(self):
        def fetchline(line):
            output.append(line)

        #self.skipTest('Not implemented yet')
        self.svc.database.get_statistics(database='employee')
        self.assertTrue(self.svc.is_running())
        # fetch materialized
        stats = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertIsInstance(stats, type(list()))
        # iterate over result
        self.svc.database.get_statistics(database='employee',
                                         flags=(SrvStatFlag.DEFAULT
                                                | SrvStatFlag.SYS_RELATIONS
                                                | SrvStatFlag.RECORD_VERSIONS))
        for line in self.svc:
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.database.get_statistics(database='employee', callback=fetchline)
        self.assertGreater(len(output), 0)
        # fetch only selected tables
        stats = self.svc.database.get_statistics(database='employee',
                                                 flags=SrvStatFlag.DATA_PAGES,
                                                 tables=['COUNTRY'])
        stats = '\n'.join(self.svc.readlines())
        self.assertIn('COUNTRY', stats)
        self.assertNotIn('JOB', stats)
        #
        stats = self.svc.database.get_statistics(database='employee',
                                                 flags=SrvStatFlag.DATA_PAGES,
                                                 tables=('COUNTRY', 'PROJECT'))
        stats = '\n'.join(self.svc.readlines())
        self.assertIn('COUNTRY', stats)
        self.assertIn('PROJECT', stats)
        self.assertNotIn('JOB', stats)
    def test_backup(self):
        def fetchline(line):
            output.append(line)

        #self.skipTest('Not implemented yet')
        self.svc.database.backup(database='employee', backup=self.fbk)
        self.assertTrue(self.svc.is_running())
        # fetch materialized
        report = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertTrue(os.path.exists(self.fbk))
        self.assertIsInstance(report, type(list()))
        self.assertListEqual(report, [])
        # iterate over result
        self.svc.database.backup(database='employee', backup=self.fbk,
                                 flags=(SrvBackupFlag.CONVERT
                                        | SrvBackupFlag.IGNORE_LIMBO
                                        | SrvBackupFlag.IGNORE_CHECKSUMS
                                        | SrvBackupFlag.METADATA_ONLY), verbose=True)
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.database.backup(database='employee', backup=self.fbk, callback=fetchline,
                                 verbose=True)
        self.assertGreater(len(output), 0)
        # Firebird 3.0 stats
        output = []
        self.svc.database.backup(database='employee', backup=self.fbk, callback=fetchline,
                                 stats='TDRW', verbose=True)
        self.assertGreater(len(output), 0)
        self.assertIn('gbak: time     delta  reads  writes \n', output)
        # Skip data option
        self.svc.database.backup(database='employee', backup=self.fbk, skip_data='(sales|customer)')
        self.svc.wait()
        self.svc.database.restore(backup=self.fbk, database=self.rfdb, flags=SrvRestoreFlag.REPLACE)
        self.svc.wait()
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as rcon:
            rcon._logging_id_ = self.__class__.__name__
            with rcon.cursor() as c:
                c.execute('select * from sales')
                self.assertListEqual(c.fetchall(), [])
                c.execute('select * from country')
                self.assertGreater(len(c.fetchall()), 0)
    def test_restore(self):
        def fetchline(line):
            output.append(line)

        output = []
        self.svc.database.backup(database='employee', backup=self.fbk, callback=fetchline)
        self.assertTrue(os.path.exists(self.fbk))
        self.svc.database.restore(backup=self.fbk, database=self.rfdb, flags=SrvRestoreFlag.REPLACE)
        self.assertTrue(self.svc.is_running())
        # fetch materialized
        report = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertIsInstance(report, type(list()))
        # iterate over result
        self.svc.database.restore(backup=self.fbk, database=self.rfdb, flags=SrvRestoreFlag.REPLACE)
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.database.restore(backup=self.fbk, database=self.rfdb, verbose=True,
                                  flags=SrvRestoreFlag.REPLACE, callback=fetchline)
        self.assertGreater(len(output), 0)
        # Firebird 3.0 stats
        output = []
        self.svc.database.restore(backup=self.fbk, database=self.rfdb,
                                  flags=SrvRestoreFlag.REPLACE, callback=fetchline,
                                  stats='TDRW', verbose=True)
        self.assertGreater(len(output), 0)
        self.assertIn('gbak: time     delta  reads  writes \n', output)
        # Skip data option
        self.svc.database.restore(backup=self.fbk, database=self.rfdb,
                                  flags=SrvRestoreFlag.REPLACE, skip_data='(sales|customer)')
        self.svc.wait()
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as rcon:
            rcon._logging_id_ = self.__class__.__name__
            with rcon.cursor() as c:
                c.execute('select * from sales')
                self.assertListEqual(c.fetchall(), [])
                c.execute('select * from country')
                self.assertGreater(len(c.fetchall()), 0)
    def test_local_backup(self):
        self.svc.database.backup(database='employee', backup=self.fbk)
        self.svc.wait()
        with open(self.fbk, mode='rb') as f:
            f.seek(68)  # Wee must skip after backup creation time (68) that will differ
            bkp = f.read()
        backup_stream = BytesIO()
        self.svc.database.local_backup(database='employee', backup_stream=backup_stream)
        backup_stream.seek(68)
        lbkp = backup_stream.read()
        stop = min(len(bkp), len(lbkp))
        i = 0
        while i < stop:
            self.assertEqual(bkp[i], lbkp[i], f"bytes differ at {i} ({i+68})")
            i += 1
        del bkp
    def test_local_restore(self):
        backup_stream = BytesIO()
        self.svc.database.local_backup(database='employee', backup_stream=backup_stream)
        backup_stream.seek(0)
        self.svc.database.local_restore(backup_stream=backup_stream, database=self.rfdb,
                                        flags=SrvRestoreFlag.REPLACE)
        self.assertTrue(os.path.exists(self.rfdb))
    def test_nbackup(self):
        self.svc.database.nbackup(database='employee', backup=self.fbk)
        self.assertTrue(os.path.exists(self.fbk))
        self.svc.database.nbackup(database='employee', backup=self.fbk2, level=1,
                                  direct=True, flags=SrvNBackupFlag.NO_TRIGGERS)
        self.assertTrue(os.path.exists(self.fbk2))
    def test_nrestore(self):
        self.test_nbackup()
        if os.path.exists(self.rfdb):
            os.remove(self.rfdb)
        self.svc.database.nrestore(backups=[self.fbk], database=self.rfdb)
        self.assertTrue(os.path.exists(self.rfdb))
        if os.path.exists(self.rfdb):
            os.remove(self.rfdb)
        self.svc.database.nrestore(backups=[self.fbk, self.fbk2], database=self.rfdb,
                          direct=True, flags=SrvNBackupFlag.NO_TRIGGERS)
        self.assertTrue(os.path.exists(self.rfdb))
    def test_set_default_cache_size(self):
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertNotEqual(con.info.page_cache_size, 100)
        self.svc.database.set_default_cache_size(database=self.rfdb, size=100)
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.page_cache_size, 100)
        self.svc.database.set_default_cache_size(database=self.rfdb, size=5000)
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.page_cache_size, 5000)
    def test_set_sweep_interval(self):
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertNotEqual(con.info.sweep_interval, 10000)
        self.svc.database.set_sweep_interval(database=self.rfdb, interval=10000)
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.sweep_interval, 10000)
    def test_shutdown_bring_online(self):
        #self.skipTest('Not implemented yet')
        # Shutdown database to single-user maintenance mode
        self.svc.database.shutdown(database=self.rfdb,mode=ShutdownMode.SINGLE,
                                   method=ShutdownMethod.FORCED, timeout=0)
        self.svc.database.get_statistics(database=self.rfdb, flags=SrvStatFlag.HDR_PAGES)
        self.assertIn('single-user maintenance', ''.join(self.svc.readlines()))
        # Enable multi-user maintenance
        self.svc.database.bring_online(database=self.rfdb, mode=OnlineMode.MULTI)
        self.svc.database.get_statistics(database=self.rfdb, flags=SrvStatFlag.HDR_PAGES)
        self.assertIn('multi-user maintenance', ''.join(self.svc.readlines()))
        # Go to full shutdown mode, disabling new attachments during 5 seconds
        self.svc.database.shutdown(database=self.rfdb, mode=ShutdownMode.FULL,
                                   method=ShutdownMethod.DENY_ATTACHMENTS, timeout=5)
        self.svc.database.get_statistics(database=self.rfdb, flags=SrvStatFlag.HDR_PAGES)
        self.assertIn('full shutdown', ''.join(self.svc.readlines()))
        # Enable single-user maintenance
        self.svc.database.bring_online(database=self.rfdb, mode=OnlineMode.SINGLE)
        self.svc.database.get_statistics(database=self.rfdb, flags=SrvStatFlag.HDR_PAGES)
        self.assertIn('single-user maintenance', ''.join(self.svc.readlines()))
        # Return to normal state
        self.svc.database.bring_online(database=self.rfdb)
    def test_set_space_reservation(self):
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.space_reservation, DbSpaceReservation.RESERVE)
        self.svc.database.set_space_reservation(database=self.rfdb, mode=DbSpaceReservation.USE_FULL)
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.space_reservation, DbSpaceReservation.USE_FULL)
    def test_set_write_mode(self):
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.write_mode, DbWriteMode.SYNC)
        self.svc.database.set_write_mode(database=self.rfdb, mode=DbWriteMode.ASYNC)
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.write_mode, DbWriteMode.ASYNC)
    def test_set_access_mode(self):
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.access_mode, DbAccessMode.READ_WRITE)
        self.svc.database.set_access_mode(database=self.rfdb, mode=DbAccessMode.READ_ONLY)
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.access_mode, DbAccessMode.READ_ONLY)
    def test_set_sql_dialect(self):
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.sql_dialect, 3)
        self.svc.database.set_sql_dialect(database=self.rfdb, dialect=1)
        with connect(f"{FBTEST_HOST}:{self.rfdb}", user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertEqual(con.info.sql_dialect, 1)
    def test_activate_shadow(self):
        self.svc.database.activate_shadow(database=self.rfdb)
    def test_no_linger(self):
        self.svc.database.no_linger(database=self.rfdb)
    def test_sweep(self):
        self.svc.database.sweep(database=self.rfdb)
    def test_repair(self):
        self.svc.database.repair(database=self.rfdb, flags=SrvRepairFlag.CORRUPTION_CHECK)
        self.svc.database.repair(database=self.rfdb, flags=SrvRepairFlag.REPAIR)
    def test_validate(self):
        def fetchline(line):
            output.append(line)

        output = []
        self.svc.database.validate(database=self.dbfile)
        # fetch materialized
        report = self.svc.readlines()
        self.assertFalse(self.svc.is_running())
        self.assertIsInstance(report, type(list()))
        self.assertIn('Validation started', '/n'.join(report))
        self.assertIn('Validation finished', '/n'.join(report))
        # iterate over result
        self.svc.database.validate(database=self.dbfile)
        for line in self.svc:
            self.assertIsNotNone(line)
            self.assertIsInstance(line, str)
        # callback
        output = []
        self.svc.database.validate(database=self.dbfile, callback=fetchline)
        self.assertGreater(len(output), 0)
        # Parameters
        self.svc.database.validate(database=self.dbfile, include_table='COUNTRY|SALES',
                          include_index='SALESTATX', lock_timeout=-1)
        report = '/n'.join(self.svc.readlines())
        self.assertNotIn('(JOB)', report)
        self.assertIn('(COUNTRY)', report)
        self.assertIn('(SALES)', report)
        if self.version != FB40:
            self.assertIn('(SALESTATX)', report)

class TestEvents(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, 'fbevents.fdb')
        if os.path.exists(self.dbfile):
            os.remove(self.dbfile)
        self.con = create_database(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        with self.con.cursor() as cur:
            cur.execute("CREATE TABLE T (PK Integer, C1 Integer)")
            cur.execute("""CREATE TRIGGER EVENTS_AU FOR T ACTIVE
    BEFORE UPDATE POSITION 0
    AS
    BEGIN
        if (old.C1 <> new.C1) then
            post_event 'c1_updated' ;
    END""")
            cur.execute("""CREATE TRIGGER EVENTS_AI FOR T ACTIVE
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
            with self.con.cursor() as cur:
                for cmd in command_list:
                    cur.execute(cmd)
                self.con.commit()

        e = {}
        timed_event = threading.Timer(3.0, send_events, args=[["insert into T (PK,C1) values (1,1)",]])
        with self.con.event_collector(['insert_1']) as events:
            timed_event.start()
            e = events.wait()
        timed_event.join()
        self.assertDictEqual(e, {'insert_1': 1})
    def test_multiple_events(self):
        def send_events(command_list):
            with self.con.cursor() as cur:
                for cmd in command_list:
                    cur.execute(cmd)
                self.con.commit()

        cmds = ["insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",
                "insert into T (PK,C1) values (1,3)",
                "insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",]
        timed_event = threading.Timer(3.0, send_events, args=[cmds])
        with self.con.event_collector(['insert_1', 'insert_3']) as events:
            timed_event.start()
            e = events.wait()
        timed_event.join()
        self.assertDictEqual(e, {'insert_3': 1, 'insert_1': 2})
    def test_20_events(self):
        def send_events(command_list):
            with self.con.cursor() as cur:
                for cmd in command_list:
                    cur.execute(cmd)
                self.con.commit()

        cmds = ["insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",
                "insert into T (PK,C1) values (1,3)",
                "insert into T (PK,C1) values (1,1)",
                "insert into T (PK,C1) values (1,2)",]
        self.e = {}
        timed_event = threading.Timer(1.0, send_events, args=[cmds])
        with self.con.event_collector(['insert_1', 'A', 'B', 'C', 'D',
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
            with self.con.cursor() as cur:
                for cmd in command_list:
                    cur.execute(cmd)
                self.con.commit()

        timed_event = threading.Timer(3.0, send_events, args=[["insert into T (PK,C1) values (1,1)",]])
        with self.con.event_collector(['insert_1']) as events:
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
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
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
        blob_lines = StringIO(blob).readlines()
        with self.con.cursor() as cur:
            cur.execute('insert into T2 (C1,C9) values (?,?)', [4, StringIO(blob)])
            self.con.commit()
            p = cur.prepare('select C1,C9 from T2 where C1 = 4')
            cur.stream_blobs.append('C9')
            cur.execute(p)
            row = cur.fetchone()
            blob_reader = row[1]
            with blob_reader:
                self.assertIsInstance(blob_reader.blob_id, fbapi.ISC_QUAD)
                self.assertEqual(blob_reader.blob_type, BlobType.STREAM)
                self.assertTrue(blob_reader.is_text)
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
                    self.assertIn(line, blob_lines)
                blob_reader.seek(0)
                self.assertListEqual(blob_reader.readlines(3), blob_lines[:3])
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
                blob_reader.seek(0)
                self.assertEqual(blob_reader.readline(20), 'Firebird supports tw')
                self.assertEqual(blob_reader.readline(), 'o types of blobs, stream and segmented.\n')
                blob_reader.seek(0)
                blob_reader.newline = '\r\n'
                self.assertEqual(blob_reader.readline(), 'Firebird supports two types of blobs, stream and segmented.\r\n')
    def testBlobExtended(self):
        blob = """Firebird supports two types of blobs, stream and segmented.
The database stores segmented blobs in chunks.
Each chunk starts with a two byte length indicator followed by however many bytes of data were passed as a segment.
Stream blobs are stored as a continuous array of data bytes with no length indicators included."""
        with self.con.cursor() as cur:
            cur.execute('insert into T2 (C1,C9) values (?,?)', [1, StringIO(blob)])
            cur.execute('insert into T2 (C1,C9) values (?,?)', [2, StringIO(blob)])
            self.con.commit()
            p = cur.prepare('select C1,C9 from T2')
            cur.stream_blobs.append('C9')
            cur.execute(p)
            for row in cur:
                blob_reader = row[1]
                with blob_reader:
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
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD, charset='utf8')
        self.con._logging_id_ = self.__class__.__name__
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
        with self.con.cursor() as cur:
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

        with connect(self.dbfile, user=FBTEST_USER,
                     password=FBTEST_PASSWORD, charset='win1250') as con1250:
            con1250._logging_id_ = self.__class__.__name__
            with self.con.cursor() as c_utf8, con1250.cursor() as c_win1250:
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
        with self.con.cursor() as cur:
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
        with self.con.cursor() as cur:
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
        hook_manager.remove_all_hooks()
        self._db = None
        self._svc = None
        self._hook_con = None
    def tearDown(self):
        for item in [self._db, self._svc, self._hook_con]:
            if item:
                item.close()
    def __hook_service_attached(self, con):
        self._svc = con
        return con
    def __hook_db_attached(self, con):
        self._db = con
        return con
    def __hook_db_closed(self, con):
        self._db = con
    def __hook_db_detach_request_a(self, con):
        # retain
        self._db = con
        return True
    def __hook_db_detach_request_b(self, con):
        # no retain
        self._db = con
        return False
    def __hook_db_attach_request_a(self, dsn, dpb):
        return None
    def __hook_db_attach_request_b(self, dsn, dpb):
        return self._hook_con
    def test_hook_db_attached(self):
        add_hook(ConnectionHook.ATTACHED, driver.Connection, self.__hook_db_attached)
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertIs(con, self._db)
    def test_hook_db_attach_request(self):
        self._hook_con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self._hook_con._logging_id_ = self.__class__.__name__
        add_hook(ConnectionHook.ATTACH_REQUEST, driver.Connection, self.__hook_db_attach_request_a)
        add_hook(ConnectionHook.ATTACH_REQUEST, driver.Connection, self.__hook_db_attach_request_b)
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            self.assertIs(con, self._hook_con)
        self._hook_con.close()
    def test_hook_db_closed(self):
        with connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD) as con:
            con._logging_id_ = self.__class__.__name__
            add_hook(ConnectionHook.CLOSED, con, self.__hook_db_closed)
        self.assertIs(con, self._db)
    def test_hook_db_detach_request(self):
        # reject detach
        con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        con._logging_id_ = self.__class__.__name__
        add_hook(ConnectionHook.DETACH_REQUEST, con, self.__hook_db_detach_request_a)
        con.close()
        self.assertIs(con, self._db)
        self.assertFalse(con.is_closed())
        hook_manager.remove_hook(ConnectionHook.DETACH_REQUEST, con, self.__hook_db_detach_request_a)
        # accept close
        self._db = None
        add_hook(ConnectionHook.DETACH_REQUEST, con, self.__hook_db_detach_request_b)
        con.close()
        self.assertIs(con, self._db)
        self.assertTrue(con.is_closed())
    def test_hook_service_attached(self):
        add_hook(ServerHook.ATTACHED, driver.Server, self.__hook_service_attached)
        with connect_server(FBTEST_HOST, user=FBTEST_USER, password=FBTEST_PASSWORD) as svc:
            self.assertIs(svc, self._svc)


class TestFB4(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        #
        if self.con.info.engine_version < 4.0:
            self.skipTest('Requires Firebird 4.0+')
        #
        self.con2 = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD, charset='utf-8')
        self.con2._logging_id_ = self.__class__.__name__
        #self.con.execute_immediate("CREATE TABLE FB4 (PK integer,T_TZ TIME WITH TIME ZONE,TS_TZ timestamp with time zone,T time,TS timestamp,DF decfloat,DF16 decfloat(16),DF34 decfloat(34),N128 numeric(34,6),D128 decimal(34,6))")
        #self.con.execute_immediate("delete from T")
        self.con.execute_immediate("delete from FB4")
        self.con.commit()
    def tearDown(self):
        self.con2.close()
        self.con.close()
    def test_01_select_with_timezone_region(self):
        data = {1: (2020, 1, 31, 11, 55, 35, 123400, 'Europe/Prague'),
                2: (2020, 6, 1, 1, 55, 35, 123400, 'Europe/Prague'),
                3: (2020, 12, 31, 23, 55, 35, 123400, 'Europe/Prague'),}
        with self.con.cursor() as cur:
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (1, '11:55:35.1234 Europe/Prague', '2020-01-31 11:55:35.1234 Europe/Prague')")
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (2, '01:55:35.1234 Europe/Prague', '2020-06-01 01:55:35.1234 Europe/Prague')")
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (3, '23:55:35.1234 Europe/Prague', '2020-12-31 23:55:35.1234 Europe/Prague')")
            self.con.commit()
            cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
            for pk, t_tz, ts_tz in cur:
                d = data[pk]
                self.assertIsInstance(t_tz, datetime.time)
                self.assertIsNotNone(t_tz.tzinfo)
                self.assertIsNotNone(getattr(t_tz.tzinfo, '_timezone_'))
                self.assertEqual(t_tz.hour, d[3])
                self.assertEqual(t_tz.minute, d[4])
                self.assertEqual(t_tz.second, d[5])
                self.assertEqual(t_tz.microsecond, d[6])
                self.assertEqual(t_tz.tzinfo._timezone_, d[7])
                #
                self.assertIsInstance(ts_tz, datetime.datetime)
                self.assertIsNotNone(ts_tz.tzinfo)
                self.assertIsNotNone(getattr(ts_tz.tzinfo, '_timezone_'))
                self.assertEqual(ts_tz.year, d[0])
                self.assertEqual(ts_tz.month, d[1])
                self.assertEqual(ts_tz.day, d[2])
                self.assertEqual(ts_tz.hour, d[3])
                self.assertEqual(ts_tz.minute, d[4])
                self.assertEqual(ts_tz.second, d[5])
                self.assertEqual(ts_tz.microsecond, d[6])
                self.assertEqual(ts_tz.tzinfo._timezone_, d[7])
    def test_02_select_with_timezone_offset(self):
        data = {1: (2020, 1, 31, 11, 55, 35, 123400, '+01:00'),
                2: (2020, 6, 1, 1, 55, 35, 123400, '+02:00'),
                3: (2020, 12, 31, 23, 55, 35, 123400, '+01:00'),}
        with self.con.cursor() as cur:
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (1, '11:55:35.1234 +01:00', '2020-01-31 11:55:35.1234 +01:00')")
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (2, '01:55:35.1234 +02:00', '2020-06-01 01:55:35.1234 +02:00')")
            cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (3, '23:55:35.1234 +01:00', '2020-12-31 23:55:35.1234 +01:00')")
            self.con.commit()
            cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
            for pk, t_tz, ts_tz in cur:
                d = data[pk]
                self.assertIsInstance(t_tz, datetime.time)
                self.assertIsNotNone(t_tz.tzinfo)
                self.assertIsNotNone(getattr(t_tz.tzinfo, '_timezone_', None))
                self.assertEqual(t_tz.hour, d[3])
                self.assertEqual(t_tz.minute, d[4])
                self.assertEqual(t_tz.second, d[5])
                self.assertEqual(t_tz.microsecond, d[6])
                self.assertEqual(t_tz.tzinfo._timezone_, d[7])
                #
                self.assertIsInstance(ts_tz, datetime.datetime)
                self.assertIsNotNone(ts_tz.tzinfo)
                self.assertIsNotNone(getattr(ts_tz.tzinfo, '_timezone_', None))
                self.assertEqual(ts_tz.year, d[0])
                self.assertEqual(ts_tz.month, d[1])
                self.assertEqual(ts_tz.day, d[2])
                self.assertEqual(ts_tz.hour, d[3])
                self.assertEqual(ts_tz.minute, d[4])
                self.assertEqual(ts_tz.second, d[5])
                self.assertEqual(ts_tz.microsecond, d[6])
                self.assertEqual(ts_tz.tzinfo._timezone_, d[7])
    def test_03_insert_with_timezone_region(self):
        data = {1: (2020, 1, 31, 11, 55, 35, 123400, 'Europe/Prague'),
                2: (2020, 6, 1, 1, 55, 35, 123400, 'Europe/Prague'),
                3: (2020, 12, 31, 23, 55, 35, 123400, 'Europe/Prague'),}
        with self.con.cursor() as cur:
            for pk, d in data.items():
                zone = get_timezone(d[7])
                ts = datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5], d[6], zone)
                cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (?, ?, ?)", (pk, ts.timetz(), ts))
                self.con.commit()
            cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
            for pk, t_tz, ts_tz in cur:
                d = data[pk]
                self.assertIsInstance(t_tz, datetime.time)
                self.assertIsNotNone(t_tz.tzinfo)
                self.assertIsNotNone(getattr(t_tz.tzinfo, '_timezone_'))
                self.assertEqual(t_tz.hour, d[3])
                self.assertEqual(t_tz.minute, d[4])
                self.assertEqual(t_tz.second, d[5])
                self.assertEqual(t_tz.microsecond, d[6])
                self.assertEqual(t_tz.tzinfo._timezone_, d[7])
                #
                self.assertIsInstance(ts_tz, datetime.datetime)
                self.assertIsNotNone(ts_tz.tzinfo)
                self.assertIsNotNone(getattr(ts_tz.tzinfo, '_timezone_'))
                self.assertEqual(ts_tz.year, d[0])
                self.assertEqual(ts_tz.month, d[1])
                self.assertEqual(ts_tz.day, d[2])
                self.assertEqual(ts_tz.hour, d[3])
                self.assertEqual(ts_tz.minute, d[4])
                self.assertEqual(ts_tz.second, d[5])
                self.assertEqual(ts_tz.microsecond, d[6])
                self.assertEqual(ts_tz.tzinfo._timezone_, d[7])
    def test_04_insert_with_timezone_offset(self):
        data = {1: (2020, 1, 31, 11, 55, 35, 123400, '+01:00'),
                2: (2020, 6, 1, 1, 55, 35, 123400, '+02:00'),
                3: (2020, 12, 31, 23, 55, 35, 123400, '+01:00'),}
        with self.con.cursor() as cur:
            for pk, d in data.items():
                zone = get_timezone(d[7])
                ts = datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5], d[6], zone)
                cur.execute("insert into FB4 (PK,T_TZ,TS_TZ) values (?, ?, ?)", (pk, ts.timetz(), ts))
                self.con.commit()
            cur.execute('select PK,T_TZ,TS_TZ from FB4 where PK between 1 and 3 order by PK')
            for pk, t_tz, ts_tz in cur:
                d = data[pk]
                self.assertIsInstance(t_tz, datetime.time)
                self.assertIsNotNone(t_tz.tzinfo)
                self.assertIsNotNone(getattr(t_tz.tzinfo, '_timezone_'))
                self.assertEqual(t_tz.hour, d[3])
                self.assertEqual(t_tz.minute, d[4])
                self.assertEqual(t_tz.second, d[5])
                self.assertEqual(t_tz.microsecond, d[6])
                self.assertEqual(t_tz.tzinfo._timezone_, d[7])
                #
                self.assertIsInstance(ts_tz, datetime.datetime)
                self.assertIsNotNone(ts_tz.tzinfo)
                self.assertIsNotNone(getattr(ts_tz.tzinfo, '_timezone_'))
                self.assertEqual(ts_tz.year, d[0])
                self.assertEqual(ts_tz.month, d[1])
                self.assertEqual(ts_tz.day, d[2])
                self.assertEqual(ts_tz.hour, d[3])
                self.assertEqual(ts_tz.minute, d[4])
                self.assertEqual(ts_tz.second, d[5])
                self.assertEqual(ts_tz.microsecond, d[6])
                self.assertEqual(ts_tz.tzinfo._timezone_, d[7])
    def test_05_select_defloat(self):
        data = {4: (decimal.Decimal('1111111111222222222233333333334444'),
                    decimal.Decimal('1111111111222222'),
                    decimal.Decimal('1111111111222222222233333333334444')),
                }
        with self.con.cursor() as cur:
            cur.execute("insert into FB4 (PK,DF,DF16,DF34) values (4, 1111111111222222222233333333334444, 1111111111222222, 1111111111222222222233333333334444)")
            self.con.commit()
            cur.execute('select PK,DF,DF16,DF34 from FB4 where PK = 4')
            for pk, df, df16, df34 in cur:
                d = data[pk]
                self.assertIsInstance(df, decimal.Decimal)
                self.assertEqual(df, d[0])
                self.assertIsInstance(df16, decimal.Decimal)
                self.assertEqual(df16, d[1])
                self.assertIsInstance(df34, decimal.Decimal)
                self.assertEqual(df34, d[2])
    def test_06_insert_defloat(self):
        data = {4: (decimal.Decimal('1111111111222222222233333333334444'),
                    decimal.Decimal('1111111111222222'),
                    decimal.Decimal('1111111111222222222233333333334444')),
                }
        with self.con.cursor() as cur:
            for pk, d in data.items():
                cur.execute("insert into FB4 (PK,DF,DF16,DF34) values (?, ?, ?, ?)", (pk, d[0], d[1], d[2]))
                self.con.commit()
            cur.execute('select PK,DF,DF16,DF34 from FB4 where PK = 4')
            for pk, df, df16, df34 in cur:
                d = data[pk]
                self.assertIsInstance(df, decimal.Decimal)
                self.assertEqual(df, d[0])
                self.assertIsInstance(df16, decimal.Decimal)
                self.assertEqual(df16, d[1])
                self.assertIsInstance(df34, decimal.Decimal)
                self.assertEqual(df34, d[2])
    def test_07_select_int128(self):
        data = {5: decimal.Decimal('1111111111222222222233333333.334444'),
                6: decimal.Decimal('111111111122222222223333333333.4444'),
                7: decimal.Decimal('111111111122222222223333333333.444455'),
                8: decimal.Decimal('111111111122222222223333333333.444456'),
                }
        with self.con.cursor() as cur:
            cur.execute("insert into FB4 (PK,N128,D128) values (5, 1111111111222222222233333333.334444, 1111111111222222222233333333.334444)")
            cur.execute("insert into FB4 (PK,N128,D128) values (6, 111111111122222222223333333333.4444, 111111111122222222223333333333.4444)")
            cur.execute("insert into FB4 (PK,N128,D128) values (7, 111111111122222222223333333333.444455, 111111111122222222223333333333.444455)")
            cur.execute("insert into FB4 (PK,N128,D128) values (8, 111111111122222222223333333333.4444559, 111111111122222222223333333333.4444559)")
            self.con.commit()
            cur.execute('select PK,N128,D128 from FB4 where PK between 5 and 8 order by pk')
            for pk, n128, d128 in cur:
                d = data[pk]
                self.assertIsInstance(n128, decimal.Decimal)
                self.assertEqual(n128, d)
                self.assertIsInstance(d128, decimal.Decimal)
                self.assertEqual(d128, d)
    def test_08_select_int128(self):
        data = {5: (decimal.Decimal('1111111111222222222233333333.334444'),decimal.Decimal('1111111111222222222233333333.334444')),
                6: (decimal.Decimal('111111111122222222223333333333.4444'),decimal.Decimal('111111111122222222223333333333.4444')),
                7: (decimal.Decimal('111111111122222222223333333333.444455'),decimal.Decimal('111111111122222222223333333333.444455')),
                8: (decimal.Decimal('111111111122222222223333333333.4444559'),decimal.Decimal('111111111122222222223333333333.444456')),
                }
        with self.con.cursor() as cur:
            for pk, d in data.items():
                cur.execute("insert into FB4 (PK,N128,D128) values (?, ?, ?)", (pk, d[0], d[0]))
                self.con.commit()
            cur.execute('select PK,N128,D128 from FB4 where PK between 5 and 8 order by pk')
            for pk, n128, d128 in cur:
                d = data[pk]
                self.assertIsInstance(n128, decimal.Decimal)
                self.assertEqual(n128, d[1])
                self.assertIsInstance(d128, decimal.Decimal)
                self.assertEqual(d128, d[1])

class TestIssues(DriverTestBase):
    def setUp(self):
        super().setUp()
        self.dbfile = os.path.join(self.dbpath, self.FBTEST_DB)
        self.con = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD)
        self.con._logging_id_ = self.__class__.__name__
        self.con2 = connect(self.dbfile, user=FBTEST_USER, password=FBTEST_PASSWORD, charset='utf-8')
        self.con2._logging_id_ = self.__class__.__name__
        #self.con.execute_immediate("recreate table t (c1 integer)")
        #self.con.commit()
        #self.con.execute_immediate("RECREATE TABLE T2 (C1 Smallint,C2 Integer,C3 Bigint,C4 Char(5),C5 Varchar(10),C6 Date,C7 Time,C8 Timestamp,C9 Blob sub_type 1,C10 Numeric(18,2),C11 Decimal(18,2),C12 Float,C13 Double precision,C14 Numeric(8,4),C15 Decimal(8,4))")
        self.con.execute_immediate("delete from t")
        self.con.execute_immediate("delete from t2")
        self.con.commit()
    def tearDown(self):
        self.con2.close()
        self.con.close()
    def test_issue_02(self):
        with self.con.cursor() as cur:
            cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)', [1, None, 1])
            self.con.commit()
            cur.execute('select C1,C2,C3 from T2 where C1 = 1')
            rows = cur.fetchall()
            self.assertListEqual(rows, [(1, None, 1)])

if __name__ == '__main__':
    unittest.main()

