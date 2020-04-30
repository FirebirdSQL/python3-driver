#coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/core.py
# DESCRIPTION:    Main driver code (connection, transaction, cursor etc.)
# CREATED:        25.3.2020
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""firebird-driver - Main driver code (connection, transaction, cursor etc.)


"""

import typing as t
#import sys
import os
import weakref
import operator
import itertools
import threading
import contextlib
from queue import PriorityQueue
#from pathlib import Path
#from locale import getpreferredencoding
from . import fbapi as a
from .types import *
#from .types import _master, _util
from .hooks import hooks, HookType

# Translation tables

d = dir(a)
s = 'isc_info_db_impl_'
q = [x for x in d if x.startswith(s) and x[len(s):] != 'last_value']
#: Dictionary to map Implementation codes to names
IMPLEMENTATION_NAMES = dict(zip([getattr(a, x) for x in q], [x[len(s):] for x in q]))
s = 'isc_info_db_code_'
q = [x for x in d if x.startswith(s) and x[len(s):] != 'last_value']
#: Dictionary to map provider codes to names
PROVIDER_NAMES = dict(zip([getattr(a, x) for x in q], [x[len(s):] for x in q]))
s = 'isc_info_db_class_'
q = [x for x in d if x.startswith(s) and x[len(s):] != 'last_value']
#: Dictionary to map database class codes to names
DB_CLASS_NAMES = dict(zip([getattr(a, x) for x in q], [x[len(s):] for x in q]))

SHRT_MIN = -32768
SHRT_MAX = 32767
USHRT_MAX = 65535
INT_MIN = -2147483648
INT_MAX = 2147483647
UINT_MAX = 4294967295
LONG_MIN = -9223372036854775808
LONG_MAX = 9223372036854775807

_tenTo = [10 ** x for x in range(20)]
_i2name = {DbInfoCode.READ_SEQ_COUNT: 'sequential', DbInfoCode.READ_IDX_COUNT: 'indexed',
            DbInfoCode.INSERT_COUNT: 'inserts', DbInfoCode.UPDATE_COUNT: 'updates',
            DbInfoCode.DELETE_COUNT: 'deletes', DbInfoCode.BACKOUT_COUNT: 'backouts',
            DbInfoCode.PURGE_COUNT: 'purges', DbInfoCode.EXPUNGE_COUNT: 'expunges'}

_bpb_stream = bytes([1, BPBItem.TYPE, 1, BPBType.STREAM])
MAX_BLOB_SEGMENT_SIZE = 65535

CHARSET_MAP = {
    # DB CHAR SET NAME    :   PYTHON CODEC NAME (CANONICAL)
    None                  :   a.getpreferredencoding(),
    'NONE'                :   a.getpreferredencoding(),
    'OCTETS'              :   None,  # Allow to pass through unchanged.
    'UNICODE_FSS'         :   'utf_8',
    'UTF8'                :   'utf_8',  # (Firebird 2.0+)
    'ASCII'               :   'ascii',
    'SJIS_0208'           :   'shift_jis',
    'EUCJ_0208'           :   'euc_jp',
    'DOS737'              :   'cp737',
    'DOS437'              :   'cp437',
    'DOS850'              :   'cp850',
    'DOS865'              :   'cp865',
    'DOS860'              :   'cp860',
    'DOS863'              :   'cp863',
    'DOS775'              :   'cp775',
    'DOS862'              :   'cp862',
    'DOS864'              :   'cp864',
    'ISO8859_1'           :   'iso8859_1',
    'ISO8859_2'           :   'iso8859_2',
    'ISO8859_3'           :   'iso8859_3',
    'ISO8859_4'           :   'iso8859_4',
    'ISO8859_5'           :   'iso8859_5',
    'ISO8859_6'           :   'iso8859_6',
    'ISO8859_7'           :   'iso8859_7',
    'ISO8859_8'           :   'iso8859_8',
    'ISO8859_9'           :   'iso8859_9',
    'ISO8859_13'          :   'iso8859_13',
    'KSC_5601'            :   'euc_kr',
    'DOS852'              :   'cp852',
    'DOS857'              :   'cp857',
    'DOS858'              :   'cp858',
    'DOS861'              :   'cp861',
    'DOS866'              :   'cp866',
    'DOS869'              :   'cp869',
    'WIN1250'             :   'cp1250',
    'WIN1251'             :   'cp1251',
    'WIN1252'             :   'cp1252',
    'WIN1253'             :   'cp1253',
    'WIN1254'             :   'cp1254',
    'BIG_5'               :   'big5',
    'GB_2312'             :   'gb2312',
    'WIN1255'             :   'cp1255',
    'WIN1256'             :   'cp1256',
    'WIN1257'             :   'cp1257',
    'GB18030'             :   'gb18030',
    'GBK'                 :   'gbk',
    'KOI8R'               :   'koi8_r',  # (Firebird 2.0+)
    'KOI8U'               :   'koi8_u',  # (Firebird 2.0+)
    'WIN1258'             :   'cp1258',  # (Firebird 2.0+)
    }

# TPBs for Isolation Levels

ISOLATION_READ_COMMITED_LEGACY = bytes([TPBItem.VERSION3,
                                        AccessMode.WRITE,
                                        LockResolution.WAIT,
                                        Isolation.READ_COMMITTED,
                                        ReadCommitted.NO_RECORD_VERSION])
ISOLATION_READ_COMMITED = bytes([TPBItem.VERSION3,
                                 AccessMode.WRITE,
                                 LockResolution.WAIT,
                                 Isolation.READ_COMMITTED,
                                 ReadCommitted.RECORD_VERSION])
ISOLATION_REPEATABLE_READ = bytes([TPBItem.VERSION3,
                                   AccessMode.WRITE,
                                   LockResolution.WAIT,
                                   Isolation.CONCURRENCY])
ISOLATION_SNAPSHOT = ISOLATION_REPEATABLE_READ
ISOLATION_SERIALIZABLE = bytes([TPBItem.VERSION3,
                                AccessMode.WRITE,
                                LockResolution.WAIT,
                                Isolation.CONSISTENCY])
ISOLATION_SNAPSHOT_TABLE_STABILITY = ISOLATION_SERIALIZABLE
ISOLATION_READ_COMMITED_RO = bytes([TPBItem.VERSION3,
                                    AccessMode.READ,
                                    LockResolution.WAIT,
                                    Isolation.READ_COMMITTED,
                                    ReadCommitted.RECORD_VERSION])

def __api_loaded(api: a.FirebirdAPI) -> None:
    setattr(sys.modules[__name__], '_master', api.fb_get_master_interface())
    setattr(sys.modules[__name__], '_util', _master.get_util_interface())

hooks.add_hook(HookType.API_LOADED, __api_loaded)

def _create_blob_buffer(size: int=MAX_BLOB_SEGMENT_SIZE) -> t.Any:
    if size < MAX_BLOB_SEGMENT_SIZE:
        result = getattr(_thns, 'blob_buf', None)
        if result is None:
            result = c.create_string_buffer(MAX_BLOB_SEGMENT_SIZE)
            _thns.blob_buf = result
        else:
            c.memset(result, 0, MAX_BLOB_SEGMENT_SIZE)
    else:
        result = c.create_string_buffer(size)
    return result

def _encode_timestamp(v: t.Union[datetime.datetime, datetime.date]) -> bytes:
    # Convert datetime.datetime or datetime.date to BLR format timestamp
    if isinstance(v, datetime.datetime):
        return int_to_bytes(_util.encode_date(v.date()), 4) + int_to_bytes(_util.encode_time(v.time()), 4)
    elif isinstance(v, datetime.date):
        return int_to_bytes(_util.encode_date(v), 4) + int_to_bytes(_util.encode_time(datetime.time()), 4)
    else:
        raise ValueError("datetime.datetime or datetime.date expected")

def _is_fixed_point(dialect: int, datatype: SQLDataType, subtype: int,
                    scale: int) -> bool:
    return ((datatype in [SQLDataType.SHORT, SQLDataType.LONG, SQLDataType.INT64]
             and (subtype or scale)) or
            ((dialect < 3) and scale
             and (datatype in [SQLDataType.DOUBLE, SQLDataType.D_FLOAT])))

def _get_external_data_type_name(dialect: int, datatype: SQLDataType,
                                  subtype: int, scale: int) -> str:
    if datatype == SQLDataType.TEXT:
        return 'CHAR'
    elif datatype == SQLDataType.VARYING:
        return 'VARCHAR'
    elif _is_fixed_point(dialect, datatype, subtype, scale):
        if subtype == 1:
            return 'NUMERIC'
        elif subtype == 2:
            return 'DECIMAL'
        else:
            return 'NUMERIC/DECIMAL'
    elif datatype == SQLDataType.SHORT:
        return 'SMALLINT'
    elif datatype == SQLDataType.LONG:
        return 'INTEGER'
    elif datatype == SQLDataType.INT64:
        return 'BIGINT'
    elif datatype == SQLDataType.FLOAT:
        return 'FLOAT'
    elif datatype in [SQLDataType.DOUBLE, SQLDataType.D_FLOAT]:
        return 'DOUBLE'
    elif datatype == SQLDataType.TIMESTAMP:
        return 'TIMESTAMP'
    elif datatype == SQLDataType.DATE:
        return 'DATE'
    elif datatype == SQLDataType.TIME:
        return 'TIME'
    elif datatype == SQLDataType.BLOB:
        return 'BLOB'
    elif datatype == SQLDataType.BOOLEAN:
        return 'BOOLEAN'
    else:
        return 'UNKNOWN'

def _get_internal_data_type_name(data_type: SQLDataType) -> str:
    if data_type in [SQLDataType.DOUBLE, SQLDataType.D_FLOAT]:
        value = SQLDataType.DOUBLE
    else:
        value = data_type
    return value.name

def _check_integer_range(value: int, dialect: int, datatype: SQLDataType,
                         subtype: int, scale: int) -> None:
    if datatype == SQLDataType.SHORT:
        vmin = SHRT_MIN
        vmax = SHRT_MAX
    elif datatype == SQLDataType.LONG:
        vmin = INT_MIN
        vmax = INT_MAX
    elif datatype == SQLDataType.INT64:
        vmin = LONG_MIN
        vmax = LONG_MAX
    if (value < vmin) or (value > vmax):
        msg = """numeric overflow: value %s
(%s scaled for %d decimal places) is of
too great a magnitude to fit into its internal storage type %s,
which has range [%s,%s].""" % (str(value),
                            _get_external_data_type_name(dialect, datatype,
                                                         subtype, scale),
                            scale,
                            _get_internal_data_type_name(datatype),
                            str(vmin), str(vmax))
        raise ProgrammingError(msg, -802)

def _is_str_param(value: t.Any, datatype: SQLDataType) -> bool:
    return ((isinstance(value, str) and datatype != SQLDataType.BLOB) or
            datatype in [SQLDataType.TEXT, SQLDataType.VARYING])

def create_meta_descriptors(meta: iMessageMetadata) -> t.List[StatementMetadata]:
    result = []
    for i in range(meta.get_count()):
        result.append(StatementMetadata(field=meta.get_field(i),
                                        relation=meta.get_relation(i),
                                        owner=meta.get_owner(i),
                                        alias=meta.get_alias(i),
                                        datatype=meta.get_type(i),
                                        nullable=meta.is_nullable(i),
                                        subtype=meta.get_subtype(i),
                                        length=meta.get_length(i),
                                        scale=meta.get_scale(i),
                                        charset=meta.get_charset(i),
                                        offset=meta.get_offset(i),
                                        null_offset=meta.get_null_offset(i)
                                        ))
    return result

# Context managers

@contextlib.contextmanager
def transaction(transact_object: Transactional, tpb: bytes=None) -> Transactional:
    try:
        transact_object.begin(tpb)
        yield transact_object
    except:
        transact_object.rollback()
        raise
    else:
        transact_object.commit()

# Managers for Parameter buffers

class TPB:
    "Transaction Parameter Buffer"
    def __init__(self, *, access_mode: AccessMode = AccessMode.WRITE,
                 isolation: Isolation=Isolation.CONCURRENCY,
                 lock_resolution: LockResolution=LockResolution.WAIT,
                 lock_timeout: int=None, no_auto_undo: bool=False,
                 auto_commit: bool=False, ignore_limbo: bool=False):
        self.access_mode: AccessMode = access_mode
        self.isolation: Isolation = isolation
        self.read_committed: ReadCommitted = ReadCommitted.RECORD_VERSION
        self.lock_resolution: LockResolution = lock_resolution
        self.lock_timeout: t.Optional[int] = lock_timeout
        self.no_auto_undo: bool = no_auto_undo
        self.auto_commit: bool = auto_commit
        self.ignore_limbo: bool = ignore_limbo
        self._table_reservation: t.List[t.Tuple[str, TableShareMode, TableAccessMode]] = []
    def clear(self) -> None:
        self.access_mode = AccessMode.WRITE
        self.isolation = Isolation.CONCURRENCY
        self.read_committed = ReadCommitted.RECORD_VERSION
        self.lock_resolution = LockResolution.WAIT
        self.lock_timeout = None
        self.no_auto_undo = False
        self.auto_commit = False
        self.ignore_limbo = False
        self._table_reservation = []
    def parse_buffer(self, buffer: bytes) -> None:
        self.clear()
        api = a.get_api()
        with api.util.get_xpb_builder(XpbKind.TPB, buffer) as tpb:
            while not tpb.is_eof():
                tag = tpb.get_tag()
                if tag in AccessMode.get_value_map().keys():
                    self.access_mode = AccessMode(tag)
                elif tag in Isolation.get_value_map().keys():
                    self.isolation = Isolation(tag)
                elif tag in ReadCommitted.get_value_map().keys():
                    self.read_committed = ReadCommitted(tag)
                elif tag in LockResolution.get_value_map().keys():
                    self.lock_resolution = LockResolution(tag)
                elif tag == TPBItem.AUTOCOMMIT:
                    self.auto_commit = True
                elif tag == TPBItem.NO_AUTO_UNDO:
                    self.no_auto_undo = True
                elif tag == TPBItem.IGNORE_LIMBO:
                    self.ignore_limbo = True
                elif tag == TPBItem.LOCK_TIMEOUT:
                    self.lock_timeout = tpb.get_int()
                elif tag in TableAccessMode.get_value_map().keys():
                    tbl_access = TableAccessMode(tag)
                    tbl_name = tpb.get_string()
                    tpb.move_next()
                    if tpb.is_eof():
                        raise ValueError(f"Missing share mode value in table {tbl_name} reservation")
                    if (val := tpb.get_tag()) not in TableShareMode.get_value_map().keys():
                        raise ValueError(f"Missing share mode value in table {tbl_name} reservation")
                    tbl_share = TableShareMode(val)
                    self.reserve_table(tbl_name, tbl_share, tbl_access)
                tpb.move_next()
    def get_buffer(self) -> bytes:
        with a.get_api().util.get_xpb_builder(XpbKind.TPB) as tpb:
            tpb.insert_tag(self.access_mode)
            tpb.insert_tag(self.isolation)
            if self.isolation == Isolation.READ_COMMITTED:
                tpb.insert_tag(self.read_committed)
            tpb.insert_tag(self.lock_resolution)
            if self.lock_timeout is not None:
                tpb.insert_int(TPBItem.LOCK_TIMEOUT, self.lock_timeout)
            if self.auto_commit:
                tpb.insert_tag(TPBItem.AUTOCOMMIT)
            if self.no_auto_undo:
                tpb.insert_tag(TPBItem.NO_AUTO_UNDO)
            if self.ignore_limbo:
                tpb.insert_tag(TPBItem.IGNORE_LIMBO)
            for table in self._table_reservation:
                tpb.insert_string(table[2], table[0]) # Access mode + table name
                tpb.insert_tag(table[1]) # Share mode
            result = tpb.get_buffer()
        return result
    def reserve_table(self, name: str, share_mode: TableShareMode,
                      access_mode: TableAccessMode) -> None:
        self._table_reservation.append((name, share_mode, access_mode))

class DPB:
    "Database Parameter Buffer"
    def __init__(self, *, user: str=None, password: str=None, role: str=None,
                 trusted_auth: bool=False, sql_dialect: int=3, timeout: int=None,
                 charset: str='UTF8', cache_size: int=None, no_gc: bool=False,
                 no_db_triggers: bool=False, no_linger: bool=False,
                 utf8filename: bool=False, dbkey_scope: DBKeyScope=None,
                 dummy_packet_interval: int=None, overwrite: bool=False,
                 db_cache_size: int=None, forced_writes: bool=None,
                 reserve_space: bool=None, page_size: int=None,
                 read_only: bool=False, sweep_interval: int=None,
                 db_sql_dialect: int=None, db_charset: str=None,
                 config: str=None, auth_plugin_list: str=None):
        # Available options:
        # AuthClient, WireCryptPlugin, Providers, ConnectionTimeout, WireCrypt,
        # WireConpression, DummyPacketInterval, RemoteServiceName, RemoteServicePort,
        # RemoteAuxPort, TcpNoNagle, IpcName, RemotePipeName
        self.config: t.Optional[str] = config
        self.auth_plugin_list: str = auth_plugin_list
        # Connect
        self.trusted_auth: bool = trusted_auth # isc_dpb_trusted_auth
        self.user: str = user # isc_dpb_user_name
        self.password: str = password # isc_dpb_password
        self.role: str = role # isc_dpb_sql_role_name
        self.sql_dialect: int = sql_dialect # isc_dpb_sql_dialect
        self.charset: str = charset # isc_dpb_lc_ctype
        self.timeout: t.Optional[int] = timeout # isc_dpb_connect_timeout
        self.dummy_packet_interval: t.Optional[int] = dummy_packet_interval # isc_dpb_dummy_packet_interval
        self.cache_size: int = cache_size # isc_dpb_num_buffers
        self.no_gc: bool = no_gc # isc_dpb_no_garbage_collect
        self.no_db_triggers: bool = no_db_triggers # isc_dpb_no_db_triggers
        self.no_linger: bool = no_linger # isc_dpb_nolinger
        self.utf8filename: bool = utf8filename # isc_dpb_utf8_filename
        self.dbkey_scope: t.Optional[DBKeyScope] = dbkey_scope # isc_dpb_dbkey_scope
        # For db create
        self.page_size: t.Optional[int] = page_size # isc_dpb_page_size
        self.overwrite: bool = overwrite # isc_dpb_overwrite
        self.db_cache_size: t.Optional[int] = db_cache_size # isc_dpb_set_page_buffers
        self.forced_writes: t.Optional[bool] = forced_writes # isc_dpb_force_write
        self.reserve_space: t.Optional[bool] = reserve_space # isc_dpb_no_reserve
        self.read_only: bool = read_only # isc_dpb_set_db_readonly
        self.sweep_interval: t.Optional[int] = sweep_interval # isc_dpb_sweep_interval
        self.db_sql_dialect: t.Optional[int] = db_sql_dialect # isc_dpb_set_db_sql_dialect
        self.db_charset: t.Optional[str] = db_charset # isc_dpb_set_db_charset
    def clear(self) -> None:
        self.config = None
        # Connect
        self.trusted_auth = False
        self.user = None
        self.password = None
        self.role = None
        self.sql_dialect = 3
        self.charset = 'UTF8'
        self.timeout = None
        self.dummy_packet_interval = None
        self.cache_size = None
        self.no_gc = False
        self.no_db_triggers = False
        self.no_linger = False
        self.utf8filename = False
        self.dbkey_scope = None
        # For db create
        self.page_size = None
        self.overwrite = False
        self.db_buffers = None
        self.forced_writes = None
        self.reserve_space = None
        self.page_size = None
        self.read_only = False
        self.sweep_interval = None
        self.db_sql_dialect = None
        self.db_charset = None
    def parse_buffer(self, buffer: bytes) -> None:
        self.clear()
        api = a.get_api()
        with api.util.get_xpb_builder(XpbKind.DPB, buffer) as dpb:
            while not dpb.is_eof():
                tag = dpb.get_tag()
                if tag == DPBItem.CONFIG:
                    self.config = dpb.get_string()
                elif tag == DPBItem.AUTH_PLUGIN_LIST:
                    self.auth_plugin_list = dpb.get_string()
                elif tag == DPBItem.TRUSTED_AUTH:
                    self.trusted_auth = True
                elif tag == DPBItem.USER_NAME:
                    self.user = dpb.get_string()
                elif tag == DPBItem.PASSWORD:
                    self.password = dpb.get_string()
                elif tag == DPBItem.CONNECT_TIMEOUT:
                    self.timeout = dpb.get_int()
                elif tag == DPBItem.DUMMY_PACKET_INTERVAL:
                    self.dummy_packet_interval = dpb.get_int()
                elif tag == DPBItem.SQL_ROLE_NAME:
                    self.role = dpb.get_string()
                elif tag == DPBItem.SQL_DIALECT:
                    self.sql_dialect = dpb.get_int()
                elif tag == DPBItem.LC_CTYPE:
                    self.charset = dpb.get_string()
                elif tag == DPBItem.NUM_BUFFERS:
                    self.cache_size = dpb.get_int()
                elif tag == DPBItem.NO_GARBAGE_COLLECT:
                    self.no_gc = bool(dpb.get_int())
                elif tag == DPBItem.UTF8_FILENAME:
                    self.utf8filename = bool(dpb.get_int())
                elif tag == DPBItem.NO_DB_TRIGGERS:
                    self.no_db_triggers = bool(dpb.get_int())
                elif tag == DPBItem.NOLINGER:
                    self.no_linger = bool(dpb.get_int())
                elif tag == DPBItem.DBKEY_SCOPE:
                    self.dbkey_scope = DBKeyScope(dpb.get_int())
                elif tag == DPBItem.PAGE_SIZE:
                    self.page_size = dpb.get_int()
                elif tag == DPBItem.OVERWRITE:
                    self.overwrite = bool(dpb.get_int())
                elif tag == DPBItem.SET_PAGE_BUFFERS:
                    self.db_cache_size = dpb.get_int()
                elif tag == DPBItem.FORCE_WRITE:
                    self.forced_writes = bool(dpb.get_int())
                elif tag == DPBItem.NO_RESERVE:
                    self.reserve_space = not bool(dpb.get_int())
                elif tag == DPBItem.SET_DB_READONLY:
                    self.read_only = bool(dpb.get_int())
                elif tag == DPBItem.SWEEP_INTERVAL:
                    self.sweep_interval = dpb.get_int()
                elif tag == DPBItem.SET_DB_SQL_DIALECT:
                    self.db_sql_dialect = dpb.get_int()
                elif tag == DPBItem.SET_DB_CHARSET:
                    self.db_charset = dpb.get_string()
    def get_buffer(self, *, for_create: bool=False) -> bytes:
        with a.get_api().util.get_xpb_builder(XpbKind.DPB) as dpb:
            if self.config is not None:
                dpb.insert_string(DPBItem.CONFIG, self.config)
            if self.trusted_auth:
                dpb.insert_tag(DPBItem.TRUSTED_AUTH)
            else:
                if self.user:
                    dpb.insert_string(DPBItem.USER_NAME, self.user)
                if self.password:
                    dpb.insert_string(DPBItem.PASSWORD, self.password)
            if self.auth_plugin_list is not None:
                dpb.insert_string(DPBItem.AUTH_PLUGIN_LIST, self.auth_plugin_list)
            if self.timeout is not None:
                dpb.insert_int(DPBItem.CONNECT_TIMEOUT, self.timeout)
            if self.dummy_packet_interval is not None:
                dpb.insert_int(DPBItem.DUMMY_PACKET_INTERVAL, self.dummy_packet_interval)
            if self.role:
                dpb.insert_string(DPBItem.SQL_ROLE_NAME, self.role)
            if self.sql_dialect:
                dpb.insert_int(DPBItem.SQL_DIALECT, self.sql_dialect)
            if self.charset:
                dpb.insert_string(DPBItem.LC_CTYPE, self.charset)
                if for_create:
                    dpb.insert_string(DPBItem.SET_DB_CHARSET, self.charset)
            if self.cache_size is not None:
                dpb.insert_int(DPBItem.NUM_BUFFERS, self.cache_size)
            if self.no_gc:
                dpb.insert_int(DPBItem.NO_GARBAGE_COLLECT, 1)
            if self.utf8filename:
                dpb.insert_int(DPBItem.UTF8_FILENAME, 1)
            if self.no_db_triggers:
                dpb.insert_int(DPBItem.NO_DB_TRIGGERS, 1)
            if self.no_linger:
                dpb.insert_int(DPBItem.NOLINGER, 1)
            if self.dbkey_scope is not None:
                dpb.insert_int(DPBItem.DBKEY_SCOPE, self.dbkey_scope)
            if for_create:
                if self.page_size is not None:
                    dpb.insert_int(DPBItem.PAGE_SIZE, self.page_size)
                if self.overwrite:
                    dpb.insert_int(DPBItem.OVERWRITE, 1)
                if self.db_cache_size is not None:
                    dpb.insert_int(DPBItem.SET_PAGE_BUFFERS, self.db_cache_size)
                if self.forced_writes is not None:
                    dpb.insert_int(DPBItem.FORCE_WRITE, int(self.forced_writes))
                if self.reserve_space is not None:
                    dpb.insert_int(DPBItem.NO_RESERVE, int(not self.reserve_space))
                if self.read_only:
                    dpb.insert_int(DPBItem.SET_DB_READONLY, 1)
                if self.sweep_interval is not None:
                    dpb.insert_int(DPBItem.SWEEP_INTERVAL, self.sweep_interval)
                if self.db_sql_dialect is not None:
                    dpb.insert_int(DPBItem.SET_DB_SQL_DIALECT, self.db_sql_dialect)
                if self.db_charset is not None:
                    dpb.insert_string(DPBItem.SET_DB_CHARSET, self.db_charset)
            #
            result = dpb.get_buffer()
        return result

class SPB_ATTACH:
    "Service Parameter Buffer"
    def __init__(self, *, user: str=None, password: str=None,
                 trusted_auth: bool=False, config: str=None,
                 auth_plugin_list: str=None):
        self.user: str = user
        self.password: str = password
        self.trusted_auth: bool = trusted_auth
        self.config: str = config
        self.auth_plugin_list: str = auth_plugin_list
    def clear(self) -> None:
        self.user = None
        self.password = None
        self.trusted_auth = False
        self.config = None
    def parse_buffer(self, buffer: bytes) -> None:
        self.clear()
        api = a.get_api()
        with api.util.get_xpb_builder(XpbKind.SPB_ATTACH, buffer) as spb:
            while not spb.is_eof():
                tag = spb.get_tag()
                if tag == SPBItem.CONFIG:
                    self.config = spb.get_string()
                elif tag == SPBItem.AUTH_PLUGIN_LIST:
                    self.auth_plugin_list = spb.get_string()
                elif tag == SPBItem.TRUSTED_AUTH:
                    self.trusted_auth = True
                elif tag == SPBItem.USER_NAME:
                    self.user = spb.get_string()
                elif tag == SPBItem.PASSWORD:
                    self.password = spb.get_string()
    def get_buffer(self) -> bytes:
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_ATTACH) as spb:
            if self.config is not None:
                spb.insert_string(SPBItem.CONFIG, self.config)
            if self.trusted_auth:
                spb.insert_tag(SPBItem.TRUSTED_AUTH)
            else:
                if self.user is not None:
                    spb.insert_string(SPBItem.USER_NAME, self.user)
                if self.password is not None:
                    spb.insert_string(SPBItem.PASSWORD, self.password)
            if self.auth_plugin_list is not None:
                spb.insert_string(SPBItem.AUTH_PLUGIN_LIST, self.auth_plugin_list)
            result = spb.get_buffer()
        return result

class Buffer:
    "Generec buffer manager"
    def __init__(self, init: t.Union[int, bytes], size: int=None):
        self.content = c.create_string_buffer(init, size)
        self.pos: int = 0
    def _insert_num(self, tag: int, value: int, size: int) -> None:
        self.insert_tag(tag)
        self.content[self.pos:self.pos+size] = int_to_bytes(value, size)
        self.pos += size
    def _get_num(self, size: int) -> int:
        result = bytes_to_int(self.content[self.pos:self.pos+size], True)
        self.pos += size
        return result
    def clear(self) -> None:
        c.memset(self.content, 0, len(self.content))
        self.rewind()
    def resize(self, size: int) -> None:
        self.content = c.create_string_buffer(size)
        self.rewind()
    def rewind(self) -> None:
        self.pos = 0
    def get_buffer_length(self) -> int:
        return len(self.content)
    def insert_short(self, tag: int, value: int) -> None:
        self._insert_num(tag, value, c.sizeof(c.c_ushort))
    def insert_int(self, tag: int, value: int) -> None:
        self._insert_num(tag, value, c.sizeof(c.c_uint))
    def insert_int64(self, tag: int, value: int) -> None:
        self._insert_num(tag, value, c.sizeof(c.c_ulonglong))
    def insert_bytes(self, tag: int, value: bytes) -> None:
        size = len(value)
        self.insert_short(tag, size)
        self.content[self.pos:self.pos+size] = value
        self.pos += size
    def insert_string(self, tag: int, value: str, encoding='ascii') -> None:
        self.insert_bytes(tag, value.encode(encoding))
    def insert_tag(self, tag: int) -> None:
        self.content[self.pos] = bytes([tag])
        self.pos += 1
    def is_eof(self) -> bool:
        return ((self.pos >= len(self.content) - 1)
                or (ord(self.content[self.pos]) == isc_info_end))
    def is_truncated(self) -> bool:
        return ord(self.content[self.pos]) == isc_info_truncated
    def get_tag(self) -> int:
        result = ord(self.content[self.pos])
        self.pos += 1
        return result
    def get_short(self) -> int:
        return self._get_num(c.sizeof(c.c_ushort))
    def get_int(self) -> int:
        return self._get_num(c.sizeof(c.c_uint))
    def get_int64(self) -> int:
        return self._get_num(c.sizeof(c.c_ulonglong))
    def get_string(self, encoding = 'ascii') -> str:
        return self.get_bytes().decode(encoding)
    def get_bytes(self) -> bytes:
        size = self.get_short()
        result = self.content[self.pos:self.pos+size]
        self.pos += size
        return result

_OP_DIE = 1
_OP_RECORD_AND_REREGISTER = 2

class EventBlock(object):
    def __init__(self, queue, db_handle: a.FB_API_HANDLE, event_names: t.List[str]):
        self.__first = True
        def callback(result, length, updated):
            c.memmove(result, updated, length)
            self.__queue.put((_OP_RECORD_AND_REREGISTER, self))
            return 0

        self.__queue: PriorityQueue = weakref.proxy(queue)
        self._db_handle: a.FB_API_HANDLE = db_handle
        self._isc_status: a.ISC_STATUS_ARRAY = a.ISC_STATUS_ARRAY(0)
        self.event_names: t.List[str] = list(event_names)

        self.__results: a.RESULT_VECTOR = a.RESULT_VECTOR(0)
        self.__closed: bool = False
        self.__callback: a.ISC_EVENT_CALLBACK = a.ISC_EVENT_CALLBACK(callback)

        self.event_buf = c.pointer(a.ISC_UCHAR(0))
        self.result_buf = c.pointer(a.ISC_UCHAR(0))
        self.buf_length: int = 0
        self.event_id: a.ISC_LONG = a.ISC_LONG(0)

        self.buf_length = a.api.isc_event_block(c.pointer(self.event_buf),
                                                c.pointer(self.result_buf),
                                                *[x.encode() for x in event_names])

    def __del__(self):
        self.close()
    def __lt__(self, other):
        return self.event_id.value < other.event_id.value
    def __wait_for_events(self):
        a.api.isc_que_events(self._isc_status, self._db_handle, self.event_id,
                             self.buf_length, self.event_buf,
                             self.__callback, self.result_buf)
        if a.db_api_error(self._isc_status):
            self.close()
            raise a.exception_from_status(DatabaseError, self._isc_status,
                                          "Error while waiting for events:")
    def _begin(self):
        self.__wait_for_events()
    def count_and_reregister(self):
        "Count event occurences and reregister interest in futrther notifications."
        result = {}
        a.api.isc_event_counts(self.__results, self.buf_length,
                               self.event_buf, self.result_buf)
        if self.__first:
            # Ignore the first call, it's for setting up the table
            self.__first = False
            self.__wait_for_events()
            return None

        for i in range(len(self.event_names)):
            result[self.event_names[i]] = int(self.__results[i])
        self.__wait_for_events()
        return result
    def close(self):
        "Close this block canceling managed events."
        if not self.__closed:
            a.api.isc_cancel_events(self._isc_status, self._db_handle, self.event_id)
            self.__closed = True
            del self.__callback
            if a.db_api_error(self._isc_status):
                raise a.exception_from_status(DatabaseError, self._isc_status,
                                              "Error while canceling events:")
    def is_close(self) -> bool:
        return self.__closed


class EventCollector(object):
    def __init__(self, db_handle: a.FB_API_HANDLE, event_names: t.Sequence[str]):
        self._db_handle: a.FB_API_HANDLE = db_handle
        self._isc_status: a.ISC_STATUS_ARRAY = a.ISC_STATUS_ARRAY(0)
        self.__event_names: t.List[str] = list(event_names)
        self.__events: t.Dict[str, int] = dict.fromkeys(self.__event_names, 0)
        self.__event_blocks: t.List[EventBlock] = []
        self.__closed: bool = False
        self.__queue: PriorityQueue = PriorityQueue()
        self.__events_ready: threading.Event = threading.Event()
        self.__blocks: t.List[t.List[str]] = [[x for x in y if x] for y in itertools.zip_longest(*[iter(event_names)]*15)]
        self.__initialized: bool = False
    def __del__(self):
        self.close()
    def __enter__(self):
        self.begin()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    def begin(self) -> None:
        def event_process(queue: PriorityQueue):
            while True:
                operation, data = queue.get()
                if operation == _OP_RECORD_AND_REREGISTER:
                    events = data.count_and_reregister()
                    if events:
                        for key, value in events.items():
                            self.__events[key] += value
                        self.__events_ready.set()
                elif operation == _OP_DIE:
                    return

        self.__initialized = True
        self.__process_thread = threading.Thread(target=event_process, args=(self.__queue,))
        self.__process_thread.start()

        for block_events in self.__blocks:
            event_block = EventBlock(self.__queue, self._db_handle, block_events)
            self.__event_blocks.append(event_block)
            event_block._begin()
    def wait(self, timeout: int=None) -> t.Dict[str, int]:
        if not self.__initialized:
            raise InterfaceError("Event collection not initialized. "
                                 "It's necessary to call begin().")
        if not self.__closed:
            self.__events_ready.wait(timeout)
            return self.__events.copy()
    def flush(self) -> None:
        if not self.__closed:
            self.__events_ready.clear()
            self.__events = dict.fromkeys(self.__event_names, 0)
    def close(self) -> None:
        if not self.__closed:
            self.__queue.put((_OP_DIE, self))
            self.__process_thread.join()
            for block in self.__event_blocks:
                block.close()
            self.__closed = True
    def is_closed(self) -> bool:
        return self.__closed

class Connection(object):
    # PEP 249 (Python DB API 2.0) extensions
    Warning = Warning
    Error = Error
    InterfaceError = InterfaceError
    DatabaseError = DatabaseError
    DataError = DataError
    OperationalError = OperationalError
    IntegrityError = IntegrityError
    InternalError = InternalError
    ProgrammingError = ProgrammingError
    NotSupportedError = NotSupportedError
    def __init__(self, att: iAttachment, dpb: bytes=None, sql_dialect: int=3,
                 charset: str=None, isolation_level: bytes=ISOLATION_READ_COMMITED) -> None:
        self._att: iAttachment = att
        self.__charset: str = charset
        self.__precision_cache = {}
        self.__sqlsubtype_cache = {}
        self.__conduits: t.List[EventCollector] = []
        self._sql_dialect: int = sql_dialect
        self._py_charset: str = CHARSET_MAP.get(charset, 'ascii')
        self._att.charset = self._py_charset
        self._dpb: bytes = dpb
        self.default_tpb: bytes = isolation_level
        self._transactions: t.List[Transaction] = []
        self._statements: t.List[Statement] = []
        #
        self._tra_main: Transaction = Transaction(self, self.default_tpb)
        self._tra_qry: Transaction = Transaction(self, ISOLATION_READ_COMMITED_RO)
        # Cursor for internal use
        self.__ic = self.query_transaction.cursor()
        self.__ic._connection = weakref.proxy(self)
        #
        # Get Firebird engine version
        verstr: str = self.get_info(DbInfoCode.FIREBIRD_VERSION)
        x = verstr.split()
        if x[0].find('V') > 0:
            (x, self.__version) = x[0].split('V')
        elif x[0].find('T') > 0:
            (x, self.__version) = x[0].split('T')
        else:
            # Unknown version
            self.__version = '0.0.0.0'
        x = self.__version.split('.')
        self.__engine_version = float(f'{x[0]}.{x[1]}')
        self.__page_size: int = self.get_info(DbInfoCode.PAGE_SIZE)
    def __del__(self):
        if not self.is_closed():
            self.__ic.close()
            self.__close_transactions()
            self.main_transaction._close()
            self.query_transaction._close()
            self.__free_statements()
            self._att.detach()
    def __enter__(self) -> 'Connection':
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __get_transactions(self) -> t.List['Transaction']:
        result = [self.main_transaction, self.query_transaction]
        result.extend(self._transactions)
        return result
    def __close_transactions(self) -> None:
        self.main_transaction._finish(DefaultAction.ROLLBACK)
        self.query_transaction._finish(DefaultAction.ROLLBACK)
        while self._transactions:
            transaction = self._transactions.pop(0)
            transaction.default_action = DefaultAction.ROLLBACK # Required by Python DB API 2.0
            transaction._close()
    def __stmt_deleted(self, stmt) -> None:
        self._statements.remove(stmt)
    def __free_statements(self) -> None:
        for stmt in self._statements:
            s = stmt()
            if s is not None:
                s.free()
    def _prepare(self, sql: str, transaction: 'Transaction'=None) -> 'Statement':
        if transaction is None:
            transaction = self._tra_qry
        if not transaction.is_active():
            transaction.begin()
        stmt = self._att.prepare(transaction._tra, sql, self._sql_dialect)
        result = Statement(self, stmt, sql, self._sql_dialect)
        self._statements.append(weakref.ref(result, self.__stmt_deleted))
        return result
    def _determine_field_precision(self, meta: StatementMetadata) -> int:
        if (not meta.relation) or (not meta.field):
            # Either or both field name and relation name are not provided,
            # so we cannot determine field precision. It's normal situation
            # for example for queries with dynamically computed fields
            return 0
        # Special case for automatic RDB$DB_KEY fields.
        if (meta.field in ['DB_KEY', 'RDB$DB_KEY']):
            return 0
        precision = self.__precision_cache.get((meta.relation, meta.field))
        if precision is not None:
            return precision
        # First, try table
        self.__ic.execute("SELECT FIELD_SPEC.RDB$FIELD_PRECISION"
                          " FROM RDB$FIELDS FIELD_SPEC,"
                          " RDB$RELATION_FIELDS REL_FIELDS"
                          " WHERE"
                          " FIELD_SPEC.RDB$FIELD_NAME ="
                          " REL_FIELDS.RDB$FIELD_SOURCE"
                          " AND REL_FIELDS.RDB$RELATION_NAME = ?"
                          " AND REL_FIELDS.RDB$FIELD_NAME = ?",
                          (meta.relation, meta.field))
        result = self.__ic.fetchone()
        self.__ic.close()
        if result:
            self.__precision_cache[(meta.relation, meta.field)] = result[0]
            return result[0]
        # Next, try stored procedure output parameter
        self.__ic.execute("SELECT FIELD_SPEC.RDB$FIELD_PRECISION"
                          " FROM RDB$FIELDS FIELD_SPEC,"
                          " RDB$PROCEDURE_PARAMETERS REL_FIELDS"
                          " WHERE"
                          " FIELD_SPEC.RDB$FIELD_NAME ="
                          " REL_FIELDS.RDB$FIELD_SOURCE"
                          " AND RDB$PROCEDURE_NAME = ?"
                          " AND RDB$PARAMETER_NAME = ?"
                          " AND RDB$PARAMETER_TYPE = 1",
                          (meta.relation, meta.field))
        result = self.__ic.fetchone()
        self.__ic.close()
        if result:
            self.__precision_cache[(meta.relation, meta.field)] = result[0]
            return result[0]
        # We ran out of options
        return 0
    def _get_array_sqlsubtype(self, relation: bytes, column: bytes) -> t.Optional[int]:
        subtype = self.__sqlsubtype_cache.get((relation, column))
        if subtype is not None:
            return subtype
        with self.__ic.execute("SELECT FIELD_SPEC.RDB$FIELD_SUB_TYPE"
                               " FROM RDB$FIELDS FIELD_SPEC, RDB$RELATION_FIELDS REL_FIELDS"
                               " WHERE"
                               " FIELD_SPEC.RDB$FIELD_NAME = REL_FIELDS.RDB$FIELD_SOURCE"
                               " AND REL_FIELDS.RDB$RELATION_NAME = ?"
                               " AND REL_FIELDS.RDB$FIELD_NAME = ?",
                               (relation, column)):
            result = self.__ic.fetchone()
        if result:
            self.__sqlsubtype_cache[(relation, column)] = result[0]
            return result[0]
    def _database_info(self, info_code: DbInfoCode, result_type: InfoItemType,
                       page_number: int=None) -> t.Any:
        buf_size = 256 if info_code != DbInfoCode.PAGE_CONTENTS else self.page_size + 10
        rq_buf = bytes([info_code])
        if info_code == DbInfoCode.PAGE_CONTENTS:
            rq_buf += int_to_bytes(4, 2)
            rq_buf += int_to_bytes(page_number, 4)
        while True:
            res_buf = (0).to_bytes(buf_size, 'little')
            self._att.get_info(rq_buf, res_buf)
            i = buf_size - 1
            while i >= 0:
                if res_buf[i] != 0:
                    break
                else:
                    i -= 1
            if res_buf[i] == isc_info_truncated:
                if buf_size < SHRT_MAX:
                    buf_size *= 2
                    if buf_size > SHRT_MAX:
                        buf_size = SHRT_MAX
                    continue
                else:
                    raise InterfaceError("Result is too large to fit into"
                                         " buffer of size SHRT_MAX, yet underlying info "
                                         " function only accepts buffers with size <= SHRT_MAX.")
            else:
                break
        if res_buf[i] != isc_info_end:
            raise InterfaceError("Exited request loop sucessfuly, but res_buf[i] != isc_info_end.")
        if (rq_buf[0] != res_buf[0]) and (info_code != DbInfoCode.ACTIVE_TRANSACTIONS):
            # isc_info_active_transactions with no active transactions returns empty buffer
            # and does not follow this rule, so we'll report it only for other codes.
            raise InterfaceError("Result code does not match request code.")
        if result_type == InfoItemType.INTEGER:
            return bytes_to_int(res_buf[3:3 + bytes_to_int(res_buf[1:3])])
        elif (result_type == InfoItemType.BYTES
              and info_code in (DbInfoCode.USER_NAMES, DbInfoCode.PAGE_CONTENTS,
                                DbInfoCode.ACTIVE_TRANSACTIONS)):
            # The result buffers for a few request codes don't follow the generic
            # conventions, so we need to return their full contents rather than
            # omitting the initial infrastructural bytes.
            return c.string_at(res_buf, i)
        elif result_type == InfoItemType.BYTES:
            return c.string_at(res_buf[3:], bytes_to_int(res_buf[1:3]))
    def drop_database(self) -> None:
        self.__close_transactions()
        self._att.drop_database()
        self._att = None
        for hook in hooks.get_hooks(HookType.DATABASE_DROPPED):
            hook(self)
    def execute_immediate(self, sql: str) -> None:
        assert self._att is not None
        self.main_transaction.execute_immediate(sql)
    def get_info(self, request: t.Union[DbInfoCode, t.Sequence[DbInfoCode]]) -> t.Any:
        def _extract_database_info_counts(buf):
            # Extract a raw binary sequence
            # of (unsigned short, signed int) pairs into
            # a corresponding Python dictionary.
            ushort_size = struct.calcsize('<H')
            int_size = struct.calcsize('<i')
            pair_size = ushort_size + int_size
            pair_count = int(len(buf) / pair_size)

            counts = {}
            for i in range(pair_count):
                buf_for_this_pair = buf[i * pair_size:(i + 1) * pair_size]
                relation_id = struct.unpack('<H', buf_for_this_pair[:ushort_size])[0]
                count = struct.unpack('<i', buf_for_this_pair[ushort_size:])[0]
                counts[relation_id] = count
            return counts
        def unpack_num(buf, pos):
            return struct.unpack('B', int2byte(buf[pos]))[0]

        assert self._att is not None
        # We process request as a sequence of info codes, even if only one code
        # was supplied by the caller.
        request_is_singleton = isinstance(request, int)
        if request_is_singleton:
            request = (request,)
        results = {}
        int2byte = operator.methodcaller("to_bytes", 1, "big")
        for info_code in request:
            if info_code == DbInfoCode.BASE_LEVEL:
                results[info_code] = unpack_num(self._database_info(info_code, InfoItemType.BYTES), 1)
            elif info_code == DbInfoCode.DB_ID:
                buf = self._database_info(info_code, InfoItemType.BYTES)
                pos = 0
                items = []
                count = unpack_num(buf, pos)
                pos += 1
                while count > 0:
                    slen = unpack_num(buf, pos)
                    pos += 1
                    item = buf[pos:pos + slen]
                    pos += slen
                    items.append(item.decode(self._py_charset))
                    count -= 1
                results[info_code] = tuple(items)
            elif info_code == DbInfoCode.IMPLEMENTATION:
                buf = self._database_info(info_code, InfoItemType.BYTES)
                pos = 1
                cpu_id = unpack_num(buf, pos)
                pos += 1
                os_id = unpack_num(buf, pos)
                pos += 1
                compiler_id = unpack_num(buf, pos)
                pos += 1
                flags = unpack_num(buf, pos)
                pos += 1
                class_number = unpack_num(buf, pos)
                results[info_code] = (cpu_id, os_id, compiler_id, flags, class_number)
            elif info_code == DbInfoCode.IMPLEMENTATION_OLD:
                buf = self._database_info(info_code, InfoItemType.BYTES)
                pos = 1
                impl_number = unpack_num(buf, pos)
                pos += 1
                class_number = unpack_num(buf, pos)
                results[info_code] = (impl_number, class_number)
            elif info_code in (DbInfoCode.VERSION, DbInfoCode.FIREBIRD_VERSION):
                buf = self._database_info(info_code, InfoItemType.BYTES)
                pos = 1
                version_string_len = unpack_num(buf, pos)
                pos += 1
                results[info_code] = buf[pos:pos + version_string_len].decode(self._py_charset)
            elif info_code == DbInfoCode.USER_NAMES:
                # The isc_info_user_names results buffer does not exactly match
                # the format declared on page 54 of the IB 6 API Guide.
                #   The buffer is formatted as a sequence of clusters, each of
                # which begins with the byte isc_info_user_names, followed by a
                # two-byte cluster length, followed by a one-byte username
                # length, followed by a single username.
                #   I don't understand why the lengths are represented
                # redundantly (the two-byte cluster length is always one
                # greater than the one-byte username length), but perhaps it's
                # an attempt to adhere to the general format of an information
                # cluster declared on page 51 while also [trying, but failing
                # to] adhere to the isc_info_user_names-specific format
                # declared on page 54.
                buf = self._database_info(info_code, InfoItemType.BYTES)
                usernames = []
                pos = 0
                while pos < len(buf):
                    if buf[pos] != DbInfoCode.USER_NAMES:
                        raise InterfaceError(f'While trying to service'
                                             f' isc_info_user_names request, found unexpected'
                                             f' results buffer contents at position {pos} of [{buf}]')
                    pos += 1
                    # The two-byte cluster length:
                    #name_cluster_len = (struct.unpack('<H', buf[pos:pos + 2])[0])
                    pos += 2
                    # The one-byte username length:
                    name_len = buf[pos]
                    #assert name_len == name_cluster_len - 1
                    pos += 1
                    usernames.append(buf[pos:pos + name_len].decode(self._py_charset))
                    pos += name_len
                # The client-exposed return value is a dictionary mapping
                # username -> number of connections by that user.
                res = {}
                for un in usernames:
                    res[un] = res.get(un, 0) + 1

                results[info_code] = res
            elif info_code in (DbInfoCode.ACTIVE_TRANSACTIONS, DbInfoCode.LIMBO):
                buf = self._database_info(info_code, InfoItemType.BYTES)
                transactions = []
                ushort_size = struct.calcsize('<H')
                pos = 1 # Skip inital byte (info_code)
                while pos < len(buf):
                    tid_size = struct.unpack('<H', buf[pos:pos+ushort_size])[0]
                    fmt = '<I' if tid_size == 4 else '<L'
                    pos += ushort_size
                    transactions.append(struct.unpack(fmt, buf[pos:pos+tid_size])[0])
                    pos += tid_size
                    pos += 1 # Skip another info_code
                results[info_code] = transactions
            elif info_code in (DbInfoCode.ALLOCATION, DbInfoCode.NO_RESERVE,
                               DbInfoCode.DB_SQL_DIALECT, DbInfoCode.ODS_MINOR_VERSION,
                               DbInfoCode.ODS_VERSION, DbInfoCode.PAGE_SIZE,
                               DbInfoCode.CURRENT_MEMORY, DbInfoCode.FORCED_WRITES,
                               DbInfoCode.MAX_MEMORY, DbInfoCode.NUM_BUFFERS,
                               DbInfoCode.SWEEP_INTERVAL, DbInfoCode.ATTACHMENT_ID,
                               DbInfoCode.FETCHES, DbInfoCode.MARKS, DbInfoCode.READS,
                               DbInfoCode.WRITES, DbInfoCode.SET_PAGE_BUFFERS,
                               DbInfoCode.DB_READ_ONLY, DbInfoCode.DB_SIZE_IN_PAGES,
                               DbInfoCode.PAGE_ERRORS, DbInfoCode.RECORD_ERRORS,
                               DbInfoCode.BPAGE_ERRORS, DbInfoCode.DPAGE_ERRORS,
                               DbInfoCode.IPAGE_ERRORS, DbInfoCode.PPAGE_ERRORS,
                               DbInfoCode.TPAGE_ERRORS, DbInfoCode.ATT_CHARSET,
                               DbInfoCode.OLDEST_TRANSACTION, DbInfoCode.OLDEST_ACTIVE,
                               DbInfoCode.OLDEST_SNAPSHOT, DbInfoCode.NEXT_TRANSACTION,
                               DbInfoCode.ACTIVE_TRAN_COUNT, DbInfoCode.DB_CLASS,
                               DbInfoCode.DB_PROVIDER, DbInfoCode.PAGES_USED,
                               DbInfoCode.PAGES_FREE, DbInfoCode.CONN_FLAGS):
                results[info_code] = self._database_info(info_code, InfoItemType.INTEGER)
            elif info_code in (DbInfoCode.BACKOUT_COUNT, DbInfoCode.DELETE_COUNT,
                               DbInfoCode.EXPUNGE_COUNT, DbInfoCode.INSERT_COUNT,
                               DbInfoCode.PURGE_COUNT, DbInfoCode.READ_IDX_COUNT,
                               DbInfoCode.READ_SEQ_COUNT, DbInfoCode.UPDATE_COUNT):
                buf = self._database_info(info_code, InfoItemType.BYTES)
                counts_by_rel_id = _extract_database_info_counts(buf)
                # Decided not to convert the relation IDs to relation names
                # for two reasons:
                #  1) Performance + Principle of Least Surprise
                #     If the client program is trying to do some delicate
                #     performance measurements, it's not helpful for
                #     kinterbasdb to be issuing unexpected queries behind the
                #     scenes.
                #  2) Field RDB$RELATIONS.RDB$RELATION_NAME is a CHAR field,
                #     which means its values emerge from the database with
                #     trailing whitespace, yet it's not safe in general to
                #     strip that whitespace because actual relation names can
                #     have trailing whitespace (think
                #     'create table "table1 " (f1 int)').
                results[info_code] = counts_by_rel_id
            elif info_code in (DbInfoCode.CREATION_DATE,):
                buf = self._database_info(info_code, InfoItemType.BYTES)
                results[info_code] = datetime.datetime.combine(_util.decode_date(buf[:4]),
                                                               _util.decode_time(buf[4:]))
            else:
                raise ValueError(f'Unrecognized database info code {info_code}')
        if request_is_singleton:
            return results[request[0]]
        else:
            return results
    def create_event_collector(self, event_names: t.Sequence[str]) -> EventCollector:
        isc_status = a.ISC_STATUS_ARRAY()
        db_handle = a.FB_API_HANDLE(0)
        a.api.fb_get_database_handle(isc_status, db_handle, self._att)
        if a.db_api_error(isc_status):
            raise a.exception_from_status(InterfaceError,
                                         isc_status,
                                         "Error in Connection.get_events:fb_get_database_handle()")
        conduit = EventCollector(db_handle, event_names)
        self.__conduits.append(conduit)
        return conduit
    def close(self) -> None:
        if not self.is_closed():
            self.__ic.close()
            for conduit in self.__conduits:
                conduit.close()
            self.__close_transactions()
            self.__free_statements()
            retain = False
            for hook in hooks.get_hooks(HookType.DATABASE_DETACH_REQUEST):
                ret = hook(self)
                if ret and not retain:
                    retain = True
            #
            if not retain:
                try:
                    self.main_transaction._close()
                    self.query_transaction._close()
                    self._att.detach()
                finally:
                    self._att = None
                    #del self.__ic
                    for hook in hooks.get_hooks(HookType.DATABASE_CLOSED):
                        hook(self)
    def create_transaction(self, default_tpb: bytes=None,
                           default_action: DefaultAction=DefaultAction.COMMIT) -> 'Transaction':
        assert self._att is not None
        transaction = Transaction(self, default_tpb if default_tpb else self.default_tpb,
                                  default_action)
        self._transactions.append(transaction)
        return transaction
    def begin(self, tpb: bytes = None) -> None:
        assert self._att is not None
        self.main_transaction.begin(tpb)
    def savepoint(self, name: str) -> None:
        assert self._att is not None
        return self.main_transaction.savepoint(name)
    def commit(self, *, retaining: bool=False) -> None:
        assert self._att is not None
        self.main_transaction.commit(retaining=retaining)
    def rollback(self, *, retaining: bool=False, savepoint: str=None) -> None:
        assert self._att is not None
        self.main_transaction.rollback(retaining=retaining, savepoint=savepoint)
    def cursor(self) -> 'Cursor':
        assert self._att is not None
        return self.main_transaction.cursor()
    def get_page_contents(self, page_number: int) -> bytes:
        assert self._att is not None
        buf = self._database_info(DbInfoCode.PAGE_CONTENTS, InfoItemType.BYTES, page_number)
        str_len = bytes_to_int(buf[1:3], True)
        return buf[3:3 + str_len]
    def get_active_transaction_ids(self) -> t.List[int]:
        assert self._att is not None
        return self.get_info(DbInfoCode.ACTIVE_TRANSACTIONS)
    def get_active_transaction_count(self) -> int:
        assert self._att is not None
        return self.get_info(DbInfoCode.ACTIVE_TRAN_COUNT)
    def get_table_access_stats(self) -> t.List[TableAccessStats]:
        assert self._att is not None
        tables = {}
        info_codes = [DbInfoCode.READ_SEQ_COUNT, DbInfoCode.READ_IDX_COUNT,
                      DbInfoCode.INSERT_COUNT, DbInfoCode.UPDATE_COUNT,
                      DbInfoCode.DELETE_COUNT, DbInfoCode.BACKOUT_COUNT,
                      DbInfoCode.PURGE_COUNT, DbInfoCode.EXPUNGE_COUNT]
        stats = self.get_info(info_codes)
        for info_code in info_codes:
            stat: t.Mapping = stats[info_code]
            for table, count in stat.items():
                tables.setdefault(table, dict.fromkeys(info_codes))[info_code] = count
        return [TableAccessStats(table,**{_i2name[code]:count
                                          for code, count in tables[table].items()})
                for table in tables]
    def is_read_only(self) -> bool:
        return bool(self.get_info(DbInfoCode.DB_READ_ONLY))
    def is_closed(self) -> bool:
        return self._att is None
    def is_compressed(self) -> bool:
        return ConnectionFlag.COMPRESSED in ConnectionFlag(self.get_info(DbInfoCode.CONN_FLAGS))
    def is_encrypted(self) -> bool:
        return ConnectionFlag.ENCRYPTED in ConnectionFlag(self.get_info(DbInfoCode.CONN_FLAGS))
    charset: str = property(lambda self: self.__charset)
    sql_dialect: int = property(lambda self: self._sql_dialect)
    page_size: int = property(lambda self: self.__page_size, doc="Size of database pages")
    main_transaction: 'Transaction' = property(lambda self: self._tra_main)
    query_transaction: 'Transaction' = property(lambda self: self._tra_qry)
    transactions: t.List['Transaction'] = property(__get_transactions)
    attachment_id: int = property(lambda self: self.get_info(DbInfoCode.ATTACHMENT_ID))
    database_sql_dialect: int = property(lambda self: self.get_info(DbInfoCode.DB_SQL_DIALECT))
    database_name: str = property(lambda self: self.get_info(DbInfoCode.DB_ID)[0])
    site_name: str = property(lambda self: self.get_info(DbInfoCode.DB_ID)[1])
    server_version: str = property(lambda self: self.get_info(DbInfoCode.VERSION))
    firebird_version: str = property(lambda self: self.get_info(DbInfoCode.FIREBIRD_VERSION))
    version: str = property(lambda self: self.__version)
    engine_version: float = property(lambda self: self.__engine_version)
    implementation_id: int = property(lambda self: self.get_info(DbInfoCode.IMPLEMENTATION_OLD)[0])
    provider_id: int = property(lambda self: self.get_info(DbInfoCode.DB_PROVIDER))
    db_class_id: int = property(lambda self: self.get_info(DbInfoCode.DB_CLASS))
    creation_date: datetime.date = property(lambda self: self.get_info(DbInfoCode.CREATION_DATE))
    ods: float = property(lambda self: float(f'{self.ods_version}.{self.ods_minor_version}'))
    ods_version: int = property(lambda self: self.get_info(DbInfoCode.ODS_VERSION))
    ods_minor_version: int = property(lambda self: self.get_info(DbInfoCode.ODS_MINOR_VERSION))
    page_cache_size: int = property(lambda self: self.get_info(DbInfoCode.NUM_BUFFERS))
    pages_allocated: int = property(lambda self: self.get_info(DbInfoCode.ALLOCATION))
    pages_used: int = property(lambda self: self.get_info(DbInfoCode.PAGES_USED))
    pages_free: int = property(lambda self: self.get_info(DbInfoCode.PAGES_FREE))
    sweep_interval: int = property(lambda self: self.get_info(DbInfoCode.SWEEP_INTERVAL))
    space_reservation: bool = property(lambda self: not bool(self.get_info(DbInfoCode.NO_RESERVE)))
    forced_writes: bool = property(lambda self: bool(self.get_info(DbInfoCode.FORCED_WRITES)))
    io_stats: t.Dict[DbInfoCode, int] = property(lambda self: self.get_info([DbInfoCode.READS,
                                                                             DbInfoCode.WRITES,
                                                                             DbInfoCode.FETCHES,
                                                                             DbInfoCode.MARKS]))
    current_memory: int = property(lambda self: self.get_info(DbInfoCode.CURRENT_MEMORY))
    max_memory: int = property(lambda self: self.get_info(DbInfoCode.MAX_MEMORY))
    oit: int = property(lambda self: self.get_info(DbInfoCode.OLDEST_TRANSACTION))
    oat: int = property(lambda self: self.get_info(DbInfoCode.OLDEST_ACTIVE))
    ost: int = property(lambda self: self.get_info(DbInfoCode.OLDEST_SNAPSHOT))
    next_transaction: int = property(lambda self: self.get_info(DbInfoCode.NEXT_TRANSACTION))

def __connect_helper(dsn: str, host: str, port: int, database: str,
                     protocol: NetProtocol, user: str, password: str,
                     sql_dialect: int) -> t.Tuple[str, str, str]:
    if user is None:
        user = os.environ.get('ISC_USER', None)
    if password is None:
        password = os.environ.get('ISC_PASSWORD', None)
    if ((not dsn and not host and not database) or
            (dsn and (host or database)) or
            (host and not database)):
        raise InterfaceError("Must supply one of:\n"
                             " 1. keyword argument dsn='host:/path/to/database'\n"
                             " 2. both keyword arguments host='host' and"
                             " database='/path/to/database'\n"
                             " 3. only keyword argument database='/path/to/database'")
    if not dsn:
        if host and host.endswith(':'):
            raise InterfaceError(f"Host must not end with a colon. You should specify"
                                 f" host='{host[:-1]}' rather than host='{host}'.")
        elif host:
            if port:
                dsn = f'{host}/{port}:{database}'
            else:
                dsn = f'{host}:{database}'
        else:
            if port:
                dsn = f'localhost/{port}:{database}'
            else:
                dsn = database
        if protocol is not None:
            dsn = f'{protocol.name.lower()}://{dsn}'
    return (dsn, user, password)

def __make_connection(create: bool, dsn: str, utf8filename: bool, dpb: bytes,
                      sql_dialect: int, charset: str, default_tpb: bytes) -> Connection:
    with a.get_api().master.get_dispatcher() as provider:
        if create:
            att = provider.create_database(dsn, dpb, 'utf-8' if utf8filename else FS_ENCODING)
            con = Connection(att, dpb, sql_dialect, charset, default_tpb)
        else:
            con = None
            for hook in hooks.get_hooks(HookType.DATABASE_ATTACH_REQUEST):
                try:
                    con = hook(dsn, dpb)
                except Exception as e:
                    raise InterfaceError("Error in DATABASE_ATTACH_REQUEST hook.", *e.args)
                if con is not None:
                    break
            if con is None:
                att = provider.attach_database(dsn, dpb, 'utf-8' if utf8filename else FS_ENCODING)
                con = Connection(att, dpb, sql_dialect, charset, default_tpb)
    for hook in hooks.get_hooks(HookType.DATABASE_ATTACHED):
        hook(con)
    return con

def connect(*, dsn: str=None, host: str=None, port: int=None, database: str=None,
            utf8filename: bool=False, protocol: NetProtocol=None,
            user: str=None, password: str=None, trusted_auth: bool=False,
            role: str=None, charset: str=None, sql_dialect: int=3,
            timeout: int=None, default_tpb: bytes=ISOLATION_READ_COMMITED,
            no_gc: bool=None, no_db_triggers: bool=None, no_linger: bool=None,
            cache_size: int=None, dbkey_scope: DBKeyScope=None,
            dummy_packet_interval: int=None, config: str=None,
            auth_plugin_list: str=None) -> Connection:
    if charset:
        charset = charset.upper()
    dsn, user, password = __connect_helper(dsn, host, port, database, protocol,
                                           user, password, sql_dialect)
    dpb = DPB(user=user, password=password, role=role, trusted_auth=trusted_auth,
              sql_dialect=sql_dialect, timeout=timeout, charset=charset,
              cache_size=cache_size, no_gc=no_gc, no_db_triggers=no_db_triggers,
              no_linger=no_linger, utf8filename=utf8filename, dbkey_scope=dbkey_scope,
              dummy_packet_interval=dummy_packet_interval, config=config)
    return __make_connection(False, dsn, utf8filename, dpb.get_buffer(), sql_dialect, charset, default_tpb)

def create_database(*, dsn: str=None, host: str=None, port: int=None,
                    database: str=None, utf8filename: bool=False,
                    protocol: NetProtocol=None, user: str=None, password: str=None,
                    trusted_auth: bool=False, role: str=None, charset: str=None,
                    sql_dialect: int=3, timeout: int=None,
                    default_tpb: bytes=ISOLATION_READ_COMMITED, no_gc: bool=None,
                    no_db_triggers: bool=None, no_linger: bool=None,
                    cache_size: int=None, dbkey_scope: DBKeyScope=None,
                    dummy_packet_interval: int=None, config: str=None,
                    auth_plugin_list: str=None, overwrite: bool=False,
                    page_size: int=None, forced_writes: bool=None,
                    db_charset: str=None, db_cache_size: int=None,
                    sweep_interval: int=None, reserve_space: bool=None,
                    read_only: bool=False, db_sql_dialect: int=None) -> Connection:
    if charset:
        charset = charset.upper()
    dsn, user, password = __connect_helper(dsn, host, port, database, protocol,
                                           user, password, sql_dialect)
    dpb = DPB(user=user, password=password, role=role, trusted_auth=trusted_auth,
              sql_dialect=sql_dialect, timeout=timeout, charset=charset,
              cache_size=cache_size, no_gc=no_gc, no_db_triggers=no_db_triggers,
              no_linger=no_linger, utf8filename=utf8filename, dbkey_scope=dbkey_scope,
              dummy_packet_interval=dummy_packet_interval, config=config,
              auth_plugin_list=auth_plugin_list, overwrite=overwrite,
              db_cache_size=db_cache_size, forced_writes=forced_writes,
              reserve_space=reserve_space, page_size=page_size, read_only=read_only,
              sweep_interval=sweep_interval, db_sql_dialect=db_sql_dialect,
              db_charset=db_charset)
    return __make_connection(True, dsn, utf8filename, dpb.get_buffer(for_create=True),
                             sql_dialect, charset, default_tpb)

class Transaction(object):
    def __init__(self, connection: Connection, default_tpb: bytes,
                 default_action: DefaultAction=DefaultAction.COMMIT):
        self._connection: t.Callable[[], Connection] = weakref.ref(connection)
        self._py_charset: str = connection._py_charset
        self.default_tpb: bytes = default_tpb
        self.default_action: DefaultAction = default_action
        self._cursors: t.List = []  # Weak references to cursors
        self._tra: iTransaction = None
        self.__closed: bool = False
    def __enter__(self) -> 'Transaction':
        self.begin()
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._close()
    def __cursor_deleted(self, obj) -> None:
        self._cursors.remove(obj)
    def __close_cursors(self) -> None:
        for cursor in self._cursors:
            c = cursor()
            if c:
                c.close()
    def _finish(self, default_action: DefaultAction=None) -> None:
        try:
            if self._tra is not None:
                if default_action is None:
                    default_action = self.default_action
                if default_action == DefaultAction.COMMIT:
                    self.commit()
                else:
                    self.rollback()
        finally:
            self._tra = None
    def _close(self) -> None:
        if not self.__closed:
            try:
                self._finish()
            finally:
                if self in self._connection()._transactions:
                    self._connection()._transactions.remove(self)
                self._connection = None
                self.__closed = True
    def _transaction_info(self, info_code: TraInfoCode, result_type: InfoItemType) -> t.Any:
        assert not self.__closed
        if not self.is_active():
            raise InterfaceError("Transaction object is not active")
        request_buffer = bytes([info_code])
        buf_size = 256
        while True:
            result_buffer = (0).to_bytes(buf_size, 'little')
            self._tra.get_info(request_buffer, result_buffer)
            i = buf_size - 1
            while i >= 0:
                if result_buffer[i] != 0:
                    break
                else:
                    i -= 1
            if result_buffer[i] == isc_info_truncated:
                if buf_size < SHRT_MAX:
                    buf_size *= 2
                    if buf_size > SHRT_MAX:
                        buf_size = SHRT_MAX
                    continue
                else:
                    raise InterfaceError("Result is too large to fit into"
                                         " buffer of size SHRT_MAX, yet underlying info"
                                         " function only accepts buffers with size <= SHRT_MAX.")
            else:
                break
        if result_buffer[i] != isc_info_end:
            raise InterfaceError("Exited request loop sucessfuly, but"
                                 " res_buf[i] != sc_info_end.")
        if request_buffer[0] != result_buffer[0]:
            raise InterfaceError("Result code does not match request code.")
        if result_type == InfoItemType.INTEGER:
            return bytes_to_int(result_buffer[3:3 + bytes_to_int(result_buffer[1:3])])
        elif result_type == InfoItemType.BYTES:
            return c.string_at(result_buffer, i)
        else:
            raise ValueError("Unknown result type requested.")
    def get_info(self, request: t.Union[TraInfoCode, t.Sequence[TraInfoCode]]) -> t.Any:
        # We process request as a sequence of info codes, even if only one code
        # was supplied by the caller.
        request_is_singleton = isinstance(request, TraInfoCode)
        if request_is_singleton:
            request = (request,)
        results = {}
        for info_code in request:
            # The global().get(...) workaround is here because only recent
            # versions of FB expose constant isc_info_tra_isolation:
            if info_code == TraInfoCode.ISOLATION:
                buf = self._transaction_info(info_code, InfoItemType.BYTES)
                buf = buf[1 + struct.calcsize('h'):]
                if len(buf) == 1:
                    results[info_code] = TraInfoIsolation(bytes_to_int(buf, True))
                else:
                    # For isolation level isc_info_tra_read_committed, the
                    # first byte indicates the isolation level
                    # (isc_info_tra_read_committed), while the second indicates
                    # the record version flag (isc_info_tra_rec_version or
                    # isc_info_tra_no_rec_version).
                    isolation_level_byte, record_version_byte = struct.unpack('cc', buf)
                    isolation_level = TraInfoIsolation(bytes_to_int(isolation_level_byte, True))
                    record_version = TraInfoReadCommitted(bytes_to_int(record_version_byte, True))
                    results[info_code] = (isolation_level, record_version)
            elif info_code == TraInfoCode.ACCESS:
                results[info_code] = TraInfoAccess(self._transaction_info(info_code, InfoItemType.INTEGER))
            else:
                results[info_code] = self._transaction_info(info_code, InfoItemType.INTEGER)

        if request_is_singleton:
            return results[request[0]]
        else:
            return results
    def is_active(self) -> bool:
        return self._tra is not None
    def is_closed(self) -> bool:
        return self.__closed
    def execute_immediate(self, sql: str) -> None:
        assert not self.__closed
        if not self.is_active():
            self.begin()
        self._connection()._att.execute(self._tra, sql, self._connection()._sql_dialect)
    def begin(self, tpb: bytes=None) -> None:
        assert not self.__closed
        self._finish()  # Make sure that previous transaction (if any) is ended
        self._tra = self._connection()._att.start_transaction(tpb if tpb else self.default_tpb)
    def commit(self, *, retaining: bool=False) -> None:
        assert not self.__closed
        assert self.is_active()
        if retaining:
            self._tra.commit_retaining()
        else:
            self.__close_cursors()
            self._tra.commit()
        if not retaining:
            self._tra = None
    def rollback(self, *, retaining: bool=False, savepoint: str=None) -> None:
        assert not self.__closed
        assert self.is_active()
        if retaining and savepoint:
            raise InterfaceError("Can't rollback to savepoint while retaining context")
        if savepoint:
            self.execute_immediate(f'rollback to {savepoint}')
        else:
            if retaining:
                self._tra.rollback_retaining()
            else:
                self.__close_cursors()
                self._tra.rollback()
            if not retaining:
                self._tra = None
    def savepoint(self, name: str) -> None:
        self.execute_immediate(f'SAVEPOINT {name}')
    def cursor(self) -> 'Cursor':
        assert not self.__closed
        cur = Cursor(self._connection(), self)
        self._cursors.append(weakref.ref(cur, self.__cursor_deleted))
        return cur
    def is_readonly(self) -> bool:
        "Returns True if transaction is Read Only."
        assert not self.__closed
        return self.get_info(TraInfoCode.ACCESS) == TraInfoAccess.READ_ONLY

    transaction_id: int = property(lambda self: self.get_info(TraInfoCode.ID))
    cursors: t.List['Cursor'] = property(lambda self: [x() for x in self._cursors])
    oit: int = property(lambda self: self.get_info(TraInfoCode.OLDEST_INTERESTING))
    oat: int = property(lambda self: self.get_info(TraInfoCode.OLDEST_ACTIVE))
    ost: int = property(lambda self: self.get_info(TraInfoCode.OLDEST_SNAPSHOT))
    isolation: t.Tuple[TraInfoIsolation, TraInfoReadCommitted] = \
        property(lambda self: self.get_info(TraInfoCode.ISOLATION))
    lock_timeout: int = property(lambda self: self.get_info(TraInfoCode.LOCK_TIMEOUT))

class Statement:
    "Internal prepared SQL statement"
    def __init__(self, connection: Connection, stmt: iStatement, sql: str, dialect: int):
        self._connection: t.Callable[[], Connection] = weakref.ref(connection)
        self._dialect: int = dialect
        self.__sql: str = sql
        self._istmt: iStatement = stmt
        self._type: StatementType = stmt.get_type()
        self._flags: StatementFlag = stmt.get_flags()
        self._desc: DESCRIPTION = None
        # Input metadata
        meta = stmt.get_input_metadata()
        self._in_cnt: int = meta.get_count()
        self._in_meta: iMessageMetadata = None
        self._in_buffer: bytes = None
        if self._in_cnt == 0:
            meta.release()
        else:
            self._in_meta = meta
            self._in_buffer = c.create_string_buffer(meta.get_message_length())
        # Output metadata
        meta = stmt.get_output_metadata()
        self._out_meta: iMessageMetadata = None
        self._out_cnt: int = meta.get_count()
        self._out_buffer: bytes = None
        self._out_desc: t.List[StatementMetadata] = None
        if self._out_cnt == 0:
            meta.release()
            self._out_desc = []
        else:
            self._out_meta = meta
            self._out_buffer = c.create_string_buffer(meta.get_message_length())
            self._out_desc = create_meta_descriptors(meta)
    def __enter__(self) -> 'Statement':
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.free()
    def __del__(self):
        self.free()
    def __get_plan(self, detailed: bool) -> str:
        assert self._istmt is not None
        return self._istmt.get_plan(detailed).strip()
    def free(self) -> None:
        if self._in_meta is not None:
            self._in_meta.release()
            self._in_meta = None
        if self._out_meta is not None:
            self._out_meta.release()
            self._out_meta = None
        if self._istmt is not None:
            self._istmt.free()
            self._istmt = None
    def has_cursor(self) -> bool:
        assert self._istmt is not None
        return StatementFlag.HAS_CURSOR in self._flags
    def can_repeat(self) -> bool:
        assert self._istmt is not None
        return StatementFlag.REPEAT_EXECUTE in self._flags
    sql: str = property(lambda self: self.__sql)
    plan: str = property(lambda self: self.__get_plan(False))
    detailed_plan: str = property(lambda self: self.__get_plan(True))
    type: StatementType = property(lambda self: self._type)

class BlobReader:
    """BlobReader is a “file-like” class, so it acts much like a open file instance."""
    def __init__(self, blob: iBlob, blob_id: a.ISC_QUAD, sub_type: int,
                 length: int, segment_size: int, charset: str):
        self._blob: iBlob = blob
        self.sub_type: int = sub_type
        self._charset: str = charset
        self._blob_length: int = length
        self._segment_size: int = segment_size
        self.__blob_id: a.ISC_QUAD = blob_id
        self.__bytes_read = 0
        self.__pos = 0
        self.__index = 0
        self.__buf = c.create_string_buffer(self._segment_size)
        self.__buf_pos = 0
        self.__buf_data = 0
    def __next__(self):
        """Return the next line from the BLOB. Part of *iterator protocol*.

        Raises:
            StopIteration: If there are no further lines.
        """
        line = self.readline()
        if line:
            return line
        else:
            raise StopIteration
    def __iter__(self):
        return self
    def __reset_buffer(self) -> None:
        c.memset(self.__buf, 0, self._segment_size)
        self.__buf_pos = 0
        self.__buf_data = 0
    def __blob_get(self) -> None:
        self.__reset_buffer()
        # Load BLOB
        bytes_actually_read = a.Cardinal(0)
        self._blob.get_segment(self._segment_size, c.byref(self.__buf),
                               bytes_actually_read)
        self.__buf_data = bytes_actually_read.value
    def __enter__(self) -> 'BlobReader':
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __del__(self):
        self.close()
    def flush(self) -> None:
        """Flush the internal buffer. Like :meth:`file.flush`. Does nothing as
        it's pointless for reader."""
        pass
    def close(self) -> None:
        if self._blob is not None:
            self._blob.close()
            self._blob = None
    def read(self, size: int=-1) -> t.Union[str, bytes]:
        """Read at most size bytes from the file (less if the read hits EOF
        before obtaining size bytes). If the size argument is negative or omitted,
        read all data until EOF is reached. The bytes are returned as a string
        object. An empty string is returned when EOF is encountered immediately.
        Like :meth:`file.read`.

        Note:
           Performs automatic conversion to `str` for TEXT BLOBs.
        """
        assert self._blob is not None
        if size >= 0:
            to_read = min(size, self._blob_length - self.__pos)
        else:
            to_read = self._blob_length - self.__pos
        return_size = to_read
        result: bytes = c.create_string_buffer(return_size)
        pos = 0
        while to_read > 0:
            to_copy = min(to_read, self.__buf_data - self.__buf_pos)
            if to_copy == 0:
                self.__blob_get()
                to_copy = min(to_read, self.__buf_data - self.__buf_pos)
                if to_copy == 0:
                    # BLOB EOF
                    break
            c.memmove(c.byref(result, pos), c.byref(self.__buf, self.__buf_pos), to_copy)
            pos += to_copy
            self.__pos += to_copy
            self.__buf_pos += to_copy
            to_read -= to_copy
        result = result.raw[:return_size]
        if self.sub_type == 1:
            result = result.decode(self._charset)
        return result
    def readline(self) -> str:
        """Read one entire line from the file. A trailing newline character is
        kept in the string (but may be absent when a file ends with an incomplete
        line). An empty string is returned when EOF is encountered immediately.
        Like :meth:`file.readline`.

        Raises:
           InterfaceError: For non-textual BLOBs.
        """
        assert self._blob is not None
        if self.sub_type != 1:
            raise InterfaceError("Can't read line from binary BLOB")
        line = []
        to_read = self._blob_length - self.__pos
        #to_copy = 0
        found = False
        while to_read > 0 and not found:
            to_scan = min(to_read, self.__buf_data - self.__buf_pos)
            if to_scan == 0:
                self.__blob_get()
                to_scan = min(to_read, self.__buf_data - self.__buf_pos)
                if to_scan == 0:
                    # BLOB EOF
                    break
            pos = 0
            while pos < to_scan:
                if self.__buf[self.__buf_pos+pos] == b'\n':
                    found = True
                    pos += 1
                    break
                pos += 1
            line.append(c.string_at(c.byref(self.__buf, self.__buf_pos), pos).decode(self._charset))
            self.__buf_pos += pos
            self.__pos += pos
            to_read -= pos
        return ''.join(line)
    def readlines(self, sizehint=None) -> t.List[str]:
        """Read until EOF using :meth:`readline` and return a list containing
        the lines thus read. The optional sizehint argument (if present) is ignored.
        Like :meth:`file.readlines`.

        Raises:
           ProgrammingError: For non-textual BLOBs.
        """
        result = []
        line = self.readline()
        while line:
            result.append(line)
            line = self.readline()
        return result
    def seek(self, offset: int, whence=os.SEEK_SET) -> None:
        """Set the file’s current position, like stdio‘s `fseek()`.
        See :meth:`file.seek` details.

        Args:
            offset (int): Offset from specified position.

        Keyword Args:
            whence (int): Context for offset. Accepted values: os.SEEK_SET, os.SEEK_CUR or os.SEEK_END

        Warning:
           If BLOB was NOT CREATED as `stream` BLOB, this method raises
           :exc:`DatabaseError` exception. This constraint is set by Firebird.
        """
        assert self._blob is not None
        self.__pos = self._blob.seek(whence, offset)
        self.__reset_buffer()
    def tell(self) -> int:
        """Return current position in BLOB, like stdio‘s `ftell()`
        and :meth:`file.tell`."""
        return self.__pos
    def is_closed(self) -> bool:
        return self._blob is None
    mode = property(lambda self: 'rb' if self.sub_type != 1 else 'r', doc="File mode ('r' or 'rb')")
    blob_id = property(lambda self: self.__blob_id, doc="BLOB ID")
    is_text = property(lambda self: self.sub_type == 1, doc="True if BLOB is a text BLOB")

class Cursor:
    """Represents a database cursor, which is used to execute SQL statement and
    manage the context of a fetch operation."""
    def __init__(self, connection: Connection, transaction: Transaction):
        self._connection: Connection = connection
        self._dialect: int = connection.sql_dialect
        self._transaction: Transaction = transaction
        self._stmt: Statement = None
        self._py_charset: str = connection._py_charset
        self._result: iResultSet = None
        self._last_fetch_status: StateResult = None
        self._name: str = None
        self._executed: bool = False
        self._cursor_flags: CursorFlag = CursorFlag.NONE
        self.__output_cache: t.Tuple = None
        self.__internal: bool = False
        self.__blob_readers: t.List[BlobReader] = []
        self.stream_blobs: t.List[str] = []
        self.stream_blob_threshold: int = 65536
        self.arraysize: int = 1 # Required by Python DB API 2.0
    def __enter__(self) -> 'Cursor':
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __del__(self):
        self.close()
    def __next__(self):
        if (row := self.fetchone()) is not None:
            return row
        else:
            raise StopIteration
    def __iter__(self):
        return self
    def __get_desc(self) -> DESCRIPTION:
        if self._stmt is None:
            return []
        if self._stmt._desc is None:
            desc = []
            for meta in self._stmt._out_desc:
                scale = meta.scale
                precision = 0
                if meta.datatype in [SQLDataType.TEXT, SQLDataType.VARYING]:
                    vtype = str
                    if meta.subtype in (4, 69):  # UTF8 and GB18030
                        dispsize = meta.length // 4
                    elif meta.subtype == 3:  # UNICODE_FSS
                        dispsize = meta.length // 3
                    else:
                        dispsize = meta.length
                elif (meta.datatype in [SQLDataType.SHORT, SQLDataType.LONG, SQLDataType.INT64]
                      and (meta.subtype or meta.scale)):
                    vtype = decimal.Decimal
                    precision = self._connection._determine_field_precision(meta)
                    dispsize = 20
                elif meta.datatype == SQLDataType.SHORT:
                    vtype = int
                    dispsize = 6
                elif meta.datatype == SQLDataType.LONG:
                    vtype = int
                    dispsize = 11
                elif meta.datatype == SQLDataType.INT64:
                    vtype = int
                    dispsize = 20
                elif meta.datatype in [SQLDataType.FLOAT, SQLDataType.D_FLOAT, SQLDataType.DOUBLE]:
                    # Special case, dialect 1 DOUBLE/FLOAT
                    # could be Fixed point
                    if (self._stmt._dialect < 3) and meta.scale:
                        vtype = decimal.Decimal
                        precision = self._connection._determine_field_precision(meta)
                    else:
                        vtype = float
                    dispsize = 17
                elif meta.datatype == SQLDataType.BLOB:
                    vtype = str if meta.subtype == 1 else bytes
                    scale = meta.subtype
                    dispsize = 0
                elif meta.datatype == SQLDataType.TIMESTAMP:
                    vtype = datetime.datetime
                    dispsize = 22
                elif meta.datatype == SQLDataType.DATE:
                    vtype = datetime.date
                    dispsize = 10
                elif meta.datatype == SQLDataType.TIME:
                    vtype = datetime.time
                    dispsize = 11
                elif meta.datatype == SQLDataType.ARRAY:
                    vtype = list
                    dispsize = -1
                elif meta.datatype == SQLDataType.BOOLEAN:
                    vtype = bool
                    dispsize = 5
                else:
                    vtype = None
                    dispsize = -1
                desc.append(tuple([meta.field if meta.field == meta.alias else meta.alias,
                                  vtype, dispsize, meta.length, precision,
                                  scale, meta.nullable]))
            self._stmt._desc = tuple(desc)
        return self._stmt._desc
    def __get_affected(self) -> int:
        if self._stmt is None:
            return -1
        result = -1
        if (self._executed and self._stmt.type in [StatementType.SELECT,
                                                   StatementType.INSERT,
                                                   StatementType.UPDATE,
                                                   StatementType.DELETE]):
            info = c.create_string_buffer(64)
            self._stmt._istmt.get_info(bytes([23, 1]), info) # bytes(isc_info_sql_records, isc_info_end)
            if ord(info[0]) != 23: # isc_info_sql_records
                raise InterfaceError("Cursor.affected_rows:\n"
                                     "first byte must be 'isc_info_sql_records'")
            res_walk = 3
            short_size = c.sizeof(c.c_short)
            while ord(info[res_walk]) != isc_info_end:
                cur_count_type = ord(info[res_walk])
                res_walk += 1
                size = bytes_to_int(info[res_walk:res_walk + short_size], True)
                res_walk += short_size
                count = bytes_to_int(info[res_walk:res_walk + size], True)
                if ((cur_count_type == 13 and self._stmt.type == StatementType.SELECT)
                    or (cur_count_type == 14 and self._stmt.type == StatementType.INSERT)
                    or (cur_count_type == 15 and self._stmt.type == StatementType.UPDATE)
                    or (cur_count_type == 16 and self._stmt.type == StatementType.DELETE)):
                    result = count
                res_walk += size
        return result
    def _extract_db_array_to_list(self, esize: int, dtype: int, subtype: int,
                                  scale: int, dim: int, dimensions: t.List[int],
                                  buf: t.Any, bufpos: int) -> t.Tuple[t.Any, int]:
        value = []
        if dim == len(dimensions)-1:
            for _ in range(dimensions[dim]):
                if dtype in (a.blr_text, a.blr_text2):
                    val = c.string_at(buf[bufpos:bufpos+esize], esize)
                    ### Todo: verify handling of P version differences
                    if subtype != 1:   # non OCTETS
                        val = val.decode(self._py_charset)
                    # CHAR with multibyte encoding requires special handling
                    if subtype in (4, 69):  # UTF8 and GB18030
                        reallength = esize // 4
                    elif subtype == 3:  # UNICODE_FSS
                        reallength = esize // 3
                    else:
                        reallength = esize
                    val = val[:reallength]
                elif dtype in (a.blr_varying, a.blr_varying2):
                    val = c.string_at(buf[bufpos:bufpos+esize])
                    if subtype != 1:   # non OCTETS
                        val = val.decode(self._py_charset)
                elif dtype in (a.blr_short, a.blr_long, a.blr_int64):
                    val = bytes_to_int(buf[bufpos:bufpos+esize])
                    if subtype or scale:
                        val = decimal.Decimal(val) / _tenTo[abs(256-scale)]
                elif dtype == a.blr_bool:
                    val = bytes_to_int(buf[bufpos:bufpos+esize]) == 1
                elif dtype == a.blr_float:
                    val = struct.unpack('f', buf[bufpos:bufpos+esize])[0]
                elif dtype in (a.blr_d_float, a.blr_double):
                    val = struct.unpack('d', buf[bufpos:bufpos+esize])[0]
                elif dtype == a.blr_timestamp:
                    val = datetime.datetime.combine(_util.decode_date(buf[bufpos:bufpos+4]),
                                                    _util.decode_time(buf[bufpos+4:bufpos+esize]))
                elif dtype == a.blr_sql_date:
                    val = _util.decode_date(buf[bufpos:bufpos+esize])
                elif dtype == a.blr_sql_time:
                    val = _util.decode_time(buf[bufpos:bufpos+esize])
                else:
                    raise InterfaceError(f"Unsupported Firebird ARRAY subtype: {dtype}")
                value.append(val)
                bufpos += esize
        else:
            for _ in range(dimensions[dim]):
                (val, bufpos) = self._extract_db_array_to_list(esize, dtype, subtype,
                                                               scale, dim + 1,
                                                               dimensions,
                                                               buf, bufpos)
                value.append(val)
        return (value, bufpos)
    def _copy_list_to_db_array(self, esize: int, dtype: int, subtype: int,
                               scale: int, dim: int, dimensions: t.List[int],
                               value: t.Any, buf: t.Any, bufpos: int) -> None:
        """Copies Python list(s) to ARRRAY column data buffer.
        """
        valuebuf = None
        if dtype in (a.blr_text, a.blr_text2):
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        elif dtype in (a.blr_varying, a.blr_varying2):
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        elif dtype in (a.blr_short, a.blr_long, a.blr_int64):
            if esize == 2:
                valuebuf = a.ISC_SHORT(0)
            elif esize == 4:
                valuebuf = a.ISC_LONG(0)
            elif esize == 8:
                valuebuf = a.ISC_INT64(0)
            else:
                raise InterfaceError("Unsupported number type")
        elif dtype == a.blr_float:
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        elif dtype in (a.blr_d_float, a.blr_double):
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_timestamp:
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_sql_date:
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_sql_time:
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_bool:
            valuebuf = c.create_string_buffer(bytes([0]), esize)
        else:
            raise InterfaceError("Unsupported Firebird ARRAY subtype: %i" % dtype)
        self._fill_db_array_buffer(esize, dtype,
                                   subtype, scale,
                                   dim, dimensions,
                                   value, valuebuf,
                                   buf, bufpos)
    def _fill_db_array_buffer(self, esize: int, dtype: int, subtype: int,
                              scale: int, dim: int, dimensions: t.List[int],
                              value: t.Any, valuebuf: t.Any, buf: t.Any, bufpos: int) -> int:
        if dim == len(dimensions)-1:
            for i in range(dimensions[dim]):
                if dtype in (a.blr_text, a.blr_text2,
                             a.blr_varying, a.blr_varying2):
                    val = value[i]
                    if isinstance(val, str):
                        val = val.encode(self._py_charset)
                    if len(val) > esize:
                        raise ValueError(f"ARRAY value of parameter is too long,"
                                         f" expected {esize}, found {len(val)}")
                    valuebuf.value = val
                    c.memmove(c.byref(buf, bufpos), valuebuf, esize)
                elif dtype in (a.blr_short, a.blr_long, a.blr_int64):
                    if subtype or scale:
                        val = value[i]
                        if isinstance(val, decimal.Decimal):
                            val = int((val * _tenTo[256-abs(scale)]).to_integral())
                        elif isinstance(val, (int, float)):
                            val = int(val * _tenTo[256-abs(scale)])
                        else:
                            raise TypeError(f'Objects of type {type(val)} are not '
                                            f' acceptable input for'
                                            f' a fixed-point column.')
                        valuebuf.value = val
                    else:
                        if esize == 2:
                            valuebuf.value = value[i]
                        elif esize == 4:
                            valuebuf.value = value[i]
                        elif esize == 8:
                            valuebuf.value = value[i]
                        else:
                            raise InterfaceError("Unsupported type")
                    c.memmove(c.byref(buf, bufpos),
                                   c.byref(valuebuf),
                                   esize)
                elif dtype == a.blr_bool:
                    valuebuf.value = int_to_bytes(1 if value[i] else 0, 1)
                    c.memmove(c.byref(buf, bufpos),
                                   c.byref(valuebuf),
                                   esize)
                elif dtype == a.blr_float:
                    valuebuf.value = struct.pack('f', value[i])
                    c.memmove(c.byref(buf, bufpos), valuebuf, esize)
                elif dtype in (a.blr_d_float, a.blr_double):
                    valuebuf.value = struct.pack('d', value[i])
                    c.memmove(c.byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_timestamp:
                    valuebuf.value = _encode_timestamp(value[i])
                    c.memmove(c.byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_sql_date:
                    valuebuf.value = int_to_bytes(_util.encode_date(value[i]), 4)
                    c.memmove(c.byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_sql_time:
                    valuebuf.value = int_to_bytes(_util.encode_time(value[i]), 4)
                    c.memmove(c.byref(buf, bufpos), valuebuf, esize)
                else:
                    raise InterfaceError(f"Unsupported Firebird ARRAY subtype: {dtype}")
                bufpos += esize
        else:
            for i in range(dimensions[dim]):
                bufpos = self._fill_db_array_buffer(esize, dtype, subtype,
                                                    scale, dim+1,
                                                    dimensions, value[i],
                                                    valuebuf, buf, bufpos)
        return bufpos
    def _validate_array_value(self, dim: int, dimensions: t.List[int],
                              value_type: int, sqlsubtype: int,
                              value_scale: int, value: t.Any) -> bool:
        """Validates whether Python list(s) passed as ARRAY column value matches
        column definition (length, structure and value types).
        """
        ok = isinstance(value, (list, tuple))
        ok = ok and (len(value) == dimensions[dim])
        if not ok:
            return False
        for i in range(dimensions[dim]):
            if dim == len(dimensions) - 1:
                # leaf: check value type
                if value_type in (a.blr_text, a.blr_text2, a.blr_varying, a.blr_varying2):
                    ok = isinstance(value[i], str)
                elif value_type in (a.blr_short, a.blr_long, a.blr_int64):
                    if sqlsubtype or value_scale:
                        ok = isinstance(value[i], decimal.Decimal)
                    else:
                        ok = isinstance(value[i], int)
                elif value_type == a.blr_float:
                    ok = isinstance(value[i], float)
                elif value_type in (a.blr_d_float, a.blr_double):
                    ok = isinstance(value[i], float)
                elif value_type == a.blr_timestamp:
                    ok = isinstance(value[i], datetime.datetime)
                elif value_type == a.blr_sql_date:
                    ok = isinstance(value[i], datetime.date)
                elif value_type == a.blr_sql_time:
                    ok = isinstance(value[i], datetime.time)
                elif value_type == a.blr_bool:
                    ok = isinstance(value[i], bool)
                else:
                    ok = False
            else:
                # non-leaf: recurse down
                ok = ok and self._validate_array_value(dim + 1, dimensions,
                                                       value_type, sqlsubtype,
                                                       value_scale, value[i])
            if not ok:
                return False
        return ok
    def _pack_input(self, meta: iMessageMetadata, buffer: bytes,
                    parameters: t.Sequence) -> t.Tuple[iMessageMetadata, bytes]:
        in_cnt = meta.get_count()
        if len(parameters) != in_cnt:
            raise InterfaceError(f"Statement parameter sequence contains"
                                 f" {len(parameters),} items,"
                                 f"but exactly {in_cnt} are required")
        #
        buf_size = len(buffer)
        c.memset(buffer, 0, buf_size)
        # Adjust metadata where needed
        with meta.get_builder() as builder:
            for i in range(in_cnt):
                value = parameters[i]
                if _is_str_param(value, meta.get_type(i)):
                    builder.set_type(i, SQLDataType.TEXT)
                    if not isinstance(value, (str, bytes, bytearray)):
                        value = str(value)
                    builder.set_length(i, len(value.encode(self._py_charset)) if isinstance(value, str) else len(value))
            in_meta = builder.get_metadata()
            new_size = in_meta.get_message_length()
            in_buffer = c.create_string_buffer(new_size) if buf_size < new_size else buffer
        buf_addr = c.addressof(in_buffer)
        with in_meta:
            for i in range(in_cnt):
                value = parameters[i]
                datatype = in_meta.get_type(i)
                length = in_meta.get_length(i)
                offset = in_meta.get_offset(i)
                # handle NULL value
                in_buffer[in_meta.get_null_offset(i)] = 1 if value is None else 0
                # store parameter value
                if _is_str_param(value, datatype):
                    # Implicit conversion to string
                    if not isinstance(value, (str, bytes, bytearray)):
                        value = str(value)
                    if isinstance(value, str):
                        value = value.encode(self._py_charset)
                    if (datatype in [SQLDataType.TEXT, SQLDataType.VARYING]
                        and len(value) > length):
                        raise ValueError(f"Value of parameter ({i}) is too long,"
                                         f" expected {length}, found {len(value)}")
                    c.memmove(buf_addr + offset, value, len(value))
                elif datatype in [SQLDataType.SHORT, SQLDataType.LONG, SQLDataType.INT64]:
                    # It's scalled integer?
                    scale = in_meta.get_scale(i)
                    if in_meta.get_subtype(i) or scale:
                        if isinstance(value, decimal.Decimal):
                            value = int((value * _tenTo[abs(scale)]).to_integral())
                        elif isinstance(value, (int, float)):
                            value = int(value * _tenTo[abs(scale)])
                        else:
                            raise TypeError(f'Objects of type {type(value)} are not '
                                            f' acceptable input for'
                                            f' a fixed-point column.')
                    _check_integer_range(value, self._dialect, datatype,
                                         in_meta.get_subtype(i), scale)
                    c.memmove(buf_addr + offset, int_to_bytes(value, length), length)
                elif datatype == SQLDataType.DATE:
                    c.memmove(buf_addr + offset, int_to_bytes(_util.encode_date(value), length), length)
                elif datatype == SQLDataType.TIME:
                    c.memmove(buf_addr + offset, int_to_bytes(_util.encode_time(value), length), length)
                elif datatype == SQLDataType.TIMESTAMP:
                    c.memmove(buf_addr + offset, _encode_timestamp(value), length)
                elif datatype == SQLDataType.FLOAT:
                    c.memmove(buf_addr + offset, struct.pack('f', value), length)
                elif datatype == SQLDataType.DOUBLE:
                    c.memmove(buf_addr + offset, struct.pack('d', value), length)
                elif datatype == SQLDataType.BOOLEAN:
                    c.memmove(buf_addr + offset, int_to_bytes(1 if value else 0, length), length)
                elif datatype == SQLDataType.BLOB:
                    blobid = a.ISC_QUAD(0, 0)
                    if hasattr(value, 'read'):
                        # It seems we've got file-like object, use stream BLOB
                        blob_buf = _create_blob_buffer()
                        blob: iBlob = self._connection._att.create_blob(self._transaction._tra,
                                                                        blobid, _bpb_stream)
                        try:
                            c.memmove(buf_addr + offset, c.addressof(blobid), length)
                            while value_chunk := value.read(MAX_BLOB_SEGMENT_SIZE):
                                blob_buf.raw = value_chunk.encode(self._py_charset) if isinstance(value_chunk, str) else value_chunk
                                blob.put_segment(len(value_chunk), blob_buf)
                                c.memset(blob_buf, 0, MAX_BLOB_SEGMENT_SIZE)
                        finally:
                            blob.close()
                            del blob_buf
                    else:
                        # Non-stream BLOB
                        if isinstance(value, str):
                            if in_meta.get_subtype(i) == 1:
                                value = value.encode(self._py_charset)
                            else:
                                raise TypeError('String value is not'
                                                ' acceptable type for'
                                                ' a non-textual BLOB column.')
                        blob_buf = c.create_string_buffer(value)
                        blob: iBlob = self._connection._att.create_blob(self._transaction._tra,
                                                                        blobid)
                        try:
                            c.memmove(buf_addr + offset, c.addressof(blobid), length)
                            total_size = len(value)
                            bytes_written_so_far = 0
                            bytes_to_write_this_time = MAX_BLOB_SEGMENT_SIZE
                            while bytes_written_so_far < total_size:
                                if (total_size - bytes_written_so_far) < MAX_BLOB_SEGMENT_SIZE:
                                    bytes_to_write_this_time = (total_size - bytes_written_so_far)
                                blob.put_segment(bytes_to_write_this_time,
                                                 c.addressof(blob_buf) + bytes_written_so_far)
                                bytes_written_so_far += bytes_to_write_this_time
                        finally:
                            blob.close()
                            del blob_buf
                elif datatype == SQLDataType.ARRAY:
                    arrayid = a.ISC_QUAD(0, 0)
                    arrayid_ptr = c.pointer(arrayid)
                    arraydesc = a.ISC_ARRAY_DESC(0)
                    isc_status = a.ISC_STATUS_ARRAY()
                    db_handle = a.FB_API_HANDLE(0)
                    tr_handle = a.FB_API_HANDLE(0)
                    relname = in_meta.get_relation(i).encode(self._py_charset)
                    sqlname = in_meta.get_field(i).encode(self._py_charset)
                    api = a.get_api()
                    api.fb_get_database_handle(isc_status, db_handle, self._connection._att)
                    if a.db_api_error(isc_status):
                        raise a.exception_from_status(InterfaceError,
                                                     isc_status,
                                                     "Error in Cursor._pack_input:fb_get_database_handle()")
                    api.fb_get_transaction_handle(isc_status, tr_handle, self._transaction._tra)
                    if a.db_api_error(isc_status):
                        raise a.exception_from_status(InterfaceError,
                                                     isc_status,
                                                     "Error in Cursor._pack_input:fb_get_transaction_handle()")
                    sqlsubtype = self._connection._get_array_sqlsubtype(relname, sqlname)
                    api.isc_array_lookup_bounds(isc_status, db_handle, tr_handle,
                                                relname, sqlname, arraydesc)
                    if a.db_api_error(isc_status):
                        raise a.exception_from_status(InterfaceError,
                                                     isc_status,
                                                     "Error in Cursor._pack_input:isc_array_lookup_bounds()")
                    value_type = arraydesc.array_desc_dtype
                    value_scale = arraydesc.array_desc_scale
                    value_size = arraydesc.array_desc_length
                    if value_type in (a.blr_varying, a.blr_varying2):
                        value_size += 2
                    dimensions = []
                    total_num_elements = 1
                    for dimension in range(arraydesc.array_desc_dimensions):
                        bounds = arraydesc.array_desc_bounds[dimension]
                        dimensions.append((bounds.array_bound_upper + 1) - bounds.array_bound_lower)
                        total_num_elements *= dimensions[dimension]
                    total_size = total_num_elements * value_size
                    # Validate value to make sure it matches the array structure
                    if not self._validate_array_value(0, dimensions, value_type,
                                                       sqlsubtype, value_scale, value):
                        raise ValueError("Incorrect ARRAY field value.")
                    value_buffer = c.create_string_buffer(total_size)
                    tsize = a.ISC_LONG(total_size)
                    self._copy_list_to_db_array(value_size, value_type,
                                                sqlsubtype, value_scale,
                                                0, dimensions,
                                                value, value_buffer, 0)
                    api.isc_array_put_slice(isc_status, db_handle, tr_handle,
                                            arrayid_ptr, arraydesc,
                                            value_buffer, tsize)
                    if a.db_api_error(isc_status):
                        raise a.exception_from_status(InterfaceError,
                                                     isc_status,
                                                     "Error in Cursor._pack_input:/isc_array_put_slice()")
                    c.memmove(buf_addr + offset, c.addressof(arrayid), length)
            #
            in_meta.add_ref() # Everything went just fine, so we keep the metadata past 'with'
        return (in_meta, in_buffer)
    def _unpack_output(self) -> t.Tuple:
        values = []
        buffer = self._stmt._out_buffer
        buf_addr = c.addressof(buffer)
        for desc in self._stmt._out_desc:
            value: t.Any = '<NOT_IMPLEMENTED>'
            if bytes_to_int(buffer[desc.null_offset]) != 0:
                value = None
            else:
                datatype = desc.datatype
                offset = desc.offset
                length = desc.length
                if datatype == SQLDataType.TEXT:
                    value = c.string_at(buf_addr + offset, length)
                    if desc.charset != 1:
                        value = value.decode(self._py_charset)
                    # CHAR with multibyte encoding requires special handling
                    if desc.charset in (4, 69):  # UTF8 and GB18030
                        reallength = length // 4
                    elif desc.charset == 3:  # UNICODE_FSS
                        reallength = length // 3
                    else:
                        reallength = length
                    value = value[:reallength]
                elif datatype == SQLDataType.VARYING:
                    size = bytes_to_int(c.string_at(buf_addr + offset, 2), True)
                    value = c.string_at(buf_addr + offset + 2, size)
                    if desc.charset != 1:
                        value = value.decode(self._py_charset)
                elif datatype == SQLDataType.BOOLEAN:
                    value = bool(bytes_to_int(buffer[offset]))
                elif datatype in [SQLDataType.SHORT, SQLDataType.LONG, SQLDataType.INT64]:
                    value = bytes_to_int(buffer[offset:offset+length])
                    # It's scalled integer?
                    if desc.subtype or desc.scale:
                        value = decimal.Decimal(value) / _tenTo[abs(desc.scale)]
                elif datatype == SQLDataType.DATE:
                    value = _util.decode_date(buffer[offset:offset+length])
                elif datatype == SQLDataType.TIME:
                    value = _util.decode_time(buffer[offset:offset+length])
                elif datatype == SQLDataType.TIMESTAMP:
                    value = datetime.datetime.combine(_util.decode_date(buffer[offset:offset+4]),
                                                      _util.decode_time(buffer[offset+4:offset+length]))
                elif datatype == SQLDataType.FLOAT:
                    value = struct.unpack('f', buffer[offset:offset+length])[0]
                elif datatype == SQLDataType.DOUBLE:
                    value = struct.unpack('d', buffer[offset:offset+length])[0]
                elif datatype == SQLDataType.BLOB:
                    val = buffer[offset:offset+length]
                    blobid = a.ISC_QUAD(bytes_to_int(val[:4], True),
                                        bytes_to_int(val[4:], True))
                    blob = self._connection._att.open_blob(self._transaction._tra, blobid, _bpb_stream)
                    # Get BLOB total length and max. size of segment
                    blob_length = blob.get_info2(BlobInfoCode.TOTAL_LENGTH)
                    segment_size = blob.get_info2(BlobInfoCode.MAX_SEGMENT)
                    # Check if stream BLOB is requested instead materialized one
                    if ((self.stream_blobs and (desc.alias if desc.alias != desc.field else desc.field) in self.stream_blobs)
                        or (self.stream_blob_threshold and (blob_length > self.stream_blob_threshold))):
                        # Stream BLOB
                        value = BlobReader(blob, blobid, desc.subtype, blob_length,
                                           segment_size, self._py_charset)
                        self.__blob_readers.append(value)
                    else:
                        # Materialized BLOB
                        blob_value = c.create_string_buffer(blob_length)
                        try:
                            # Load BLOB
                            bytes_read = 0
                            bytes_actually_read = a.Cardinal(0)
                            while bytes_read < blob_length:
                                blob.get_segment(min(segment_size, blob_length - bytes_read),
                                                 c.byref(blob_value, bytes_read),
                                                 bytes_actually_read)
                                bytes_read += bytes_actually_read.value
                            # Finalize value
                            value = blob_value.raw
                            if desc.subtype == 1:
                                value = value.decode(self._py_charset)
                        finally:
                            blob.close()
                            del blob_value
                elif datatype == SQLDataType.ARRAY:
                    value = []
                    val = buffer[offset:offset+length]
                    arrayid = a.ISC_QUAD(bytes_to_int(val[:4], True),
                                         bytes_to_int(val[4:], True))
                    arraydesc = a.ISC_ARRAY_DESC(0)
                    isc_status = a.ISC_STATUS_ARRAY()
                    db_handle = a.FB_API_HANDLE(0)
                    tr_handle = a.FB_API_HANDLE(0)
                    relname = desc.relation.encode(self._py_charset)
                    sqlname = desc.field.encode(self._py_charset)
                    api = a.get_api()
                    api.fb_get_database_handle(isc_status, db_handle, self._connection._att)
                    if a.db_api_error(isc_status):
                        raise a.exception_from_status(InterfaceError,
                                                     isc_status,
                                                     "Error in Cursor._unpack_output:fb_get_database_handle()")
                    api.fb_get_transaction_handle(isc_status, tr_handle, self._transaction._tra)
                    if a.db_api_error(isc_status):
                        raise a.exception_from_status(InterfaceError,
                                                     isc_status,
                                                     "Error in Cursor._unpack_output:fb_get_transaction_handle()")
                    sqlsubtype = self._connection._get_array_sqlsubtype(relname, sqlname)
                    api.isc_array_lookup_bounds(isc_status, db_handle, tr_handle,
                                                relname, sqlname, arraydesc)
                    if a.db_api_error(isc_status):
                        raise a.exception_from_status(InterfaceError,
                                                     isc_status,
                                                     "Error in Cursor._unpack_output:isc_array_lookup_bounds()")
                    value_type = arraydesc.array_desc_dtype
                    value_scale = arraydesc.array_desc_scale
                    value_size = arraydesc.array_desc_length
                    if value_type in (a.blr_varying, a.blr_varying2):
                        value_size += 2
                    dimensions = []
                    total_num_elements = 1
                    for dimension in range(arraydesc.array_desc_dimensions):
                        bounds = arraydesc.array_desc_bounds[dimension]
                        dimensions.append((bounds.array_bound_upper + 1) - bounds.array_bound_lower)
                        total_num_elements *= dimensions[dimension]
                    total_size = total_num_elements * value_size
                    value_buffer = c.create_string_buffer(total_size)
                    tsize = a.ISC_LONG(total_size)
                    api.isc_array_get_slice(isc_status, db_handle, tr_handle,
                                            arrayid, arraydesc,
                                            value_buffer, tsize)
                    if a.db_api_error(isc_status):
                        raise InterfaceError("Error in Cursor._unpack_output:isc_array_get_slice()")
                    (value, bufpos) = self._extract_db_array_to_list(value_size,
                                                                     value_type,
                                                                     sqlsubtype,
                                                                     value_scale,
                                                                     0, dimensions,
                                                                     value_buffer, 0)
            values.append(value)
        return tuple(values)
    def _fetchone(self) -> t.Optional[t.Tuple]:
        if self._executed:
            if self._stmt._out_cnt == 0:
                return None
                #raise DatabaseError("Attempt to fetch row of results after statement"
                                    #" that does not produce result set.", sqlstate='02000')
            if self._last_fetch_status == StateResult.NO_DATA:
                return None
            if self.__output_cache is not None:
                result = self.__output_cache
                self._last_fetch_status = StateResult.NO_DATA
                self.__output_cache = None
                return result
            else:
                self._last_fetch_status = self._result.fetch_next(self._stmt._out_buffer)
                if self._last_fetch_status == StateResult.OK:
                    return self._unpack_output()
                else:
                    return None
        raise InterfaceError("Cannot fetch from cursor that did not executed a statement.")
    def _execute(self, operation: t.Union[str, Statement],
                 parameters: t.Sequence=None, flags: CursorFlag=CursorFlag.NONE) -> None:
        if not self._transaction.is_active():
            self._transaction.begin()
        if isinstance(operation, Statement):
            if operation._connection() != self._connection:
                raise InterfaceError('Cannot execute Statement that was created by different Connection.')
            self.close()
            self._stmt = operation
            self.__internal = False
        elif self._stmt is not None and self._stmt.sql == operation:
            # We should execute the same SQL string again
            self._clear()
        else:
            self.close()
            self._stmt = self._connection._prepare(operation, self._transaction)
            self.__internal = True
        self._cursor_flags = flags
        in_meta = None
        # Execute the statement
        try:
            if self._stmt._in_cnt > 0:
                in_meta, self._stmt._in_buffer = self._pack_input(self._stmt._in_meta,
                                                                  self._stmt._in_buffer,
                                                                  parameters)
            if self._stmt.has_cursor():
                # Statement returns multiple rows
                self._result = self._stmt._istmt.open_cursor(self._transaction._tra,
                                                            in_meta, self._stmt._in_buffer,
                                                            self._stmt._out_meta,
                                                            flags)
            else:
                # Statement may return single row
                self._stmt._istmt.execute(self._transaction._tra, in_meta,
                                         self._stmt._in_buffer,
                                         self._stmt._out_meta, self._stmt._out_buffer)
                if self._stmt._out_buffer is not None:
                    self.__output_cache = self._unpack_output()
            self._executed = True
            self._last_fetch_status = None
        finally:
            if in_meta is not None:
                in_meta.release()
    def _clear(self) -> None:
        if self._result is not None:
            self._result.close()
            self._result = None
        self._name = None
        self._last_fetch_status = None
        self._executed = False
        self.__output_cache = None
        while self.__blob_readers:
            self.__blob_readers.pop().close()
    def callproc(self, proc_name: str, parameters: t.Sequence=None) -> t.Optional[t.Tuple]:
        params = [] if parameters is None else parameters
        sql = ('EXECUTE PROCEDURE ' + proc_name + ' '
               + ','.join('?' * len(params)))
        self.execute(sql, params)
        return self.fetchone() if self._stmt._out_cnt > 0 else None
    def set_cursor_name(self, name: str) -> None:
        if not self._executed:
            raise InterfaceError("Cannot set name for cursor has not yet "
                                   "executed a statement")
        if self._name:
            raise InterfaceError("Cursor's name has already been declared in"
                                 " context of currently executed statement")
        self._stmt._istmt.set_cursor_name(name)
        self._name = name
    def prepare(self, operation: str) -> Statement:
        return self._connection._prepare(operation, self._transaction)
    def open(self, operation: t.Union[str, Statement], parameters: t.Sequence=None) -> None:
        self._execute(operation, parameters, CursorFlag.SCROLLABLE)
    def execute(self, operation: t.Union[str, Statement], parameters: t.Sequence=None) -> 'Cursor':
        self._execute(operation, parameters)
        return self
    def executemany(self, operation: t.Union[str, Statement],
                    seq_of_parameters: t.Sequence[t.Sequence]) -> None:
        for parameters in seq_of_parameters:
            self.execute(operation, parameters)
    def close(self) -> None:
        self._clear()
        if self._stmt is not None:
            if self.__internal:
                self._stmt.free()
            self._stmt = None
    def fetchone(self) -> t.Tuple:
        if self._stmt:
            return self._fetchone()
        else:
            raise InterfaceError("Cannot fetch from cursor that did not executed a statement.")
    def fetchmany(self, size: int=None) -> t.List[t.Tuple]:
        if size is None:
            size = self.arraysize
        result = []
        for _ in range(size):
            if (row := self.fetchone()) is not None:
                result.append(row)
            else:
                break
        return result
    def fetchall(self) -> t.List[t.Tuple]:
        return [row for row in self]
    def fetch_next(self) -> t.Optional[t.Tuple]:
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_next(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_prior(self) -> t.Optional[t.Tuple]:
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_prior(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_first(self) -> t.Optional[t.Tuple]:
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_first(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_last(self) -> t.Optional[t.Tuple]:
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_last(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_absolute(self, possition: int) -> t.Optional[t.Tuple]:
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_absolute(possition, self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_relative(self, offset: int) -> t.Optional[t.Tuple]:
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_relative(offset, self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def setinputsizes(self, sizes: t.Sequence[t.Type]) -> None:
        """Required by Python DB API 2.0, but pointless for Firebird, so it does nothing."""
        pass
    def setoutputsize(self, size: int, column: int=None) -> None:
        """Required by Python DB API 2.0, but pointless for Firebird, so it does nothing."""
        pass
    def is_closed(self) -> bool:
        return self._stmt is None
    def is_eof(self) -> bool:
        assert self._result is not None
        return self._result.is_eof()
    def is_bof(self) -> bool:
        assert self._result is not None
        return self._result.is_bof()
    statement: Statement = property(lambda self: self._stmt)
    description: DESCRIPTION = property(__get_desc)
    affected_rows: int = property(__get_affected)
    transaction: Transaction = property(lambda self: self._transaction)
    name: str = property(lambda self: self._name)

class Service:
    """Represents connection to Firebird Service Manager."""
    def __init__(self, svc: iService, spb: bytes, host: str):
        self._svc: iService = svc
        self.spb: bytes = spb
        self.host: str = host
        self.result_buffer: Buffer = Buffer(USHRT_MAX)
        #self.result_buffer: Buffer = Buffer(100)
        self.__eof: bool = False
        self.__line_buffer: t.List[str] = []
        # Get Firebird engine version
        verstr = self.get_server_version()
        x = verstr.split()
        self.__version: str = '0.0.0.0'
        if x[0].find('V') > 0:
            (x, self.__version) = x[0].split('V')
        elif x[0].find('T') > 0:
            (x, self.__version) = x[0].split('T')
        x = self.__version.split('.')
        self.__engine_version: float = float('%s.%s' % (x[0], x[1]))
    def __enter__(self) -> 'Service':
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __del__(self):
        self.close()
    def __next__(self):
        if (line := self.readline()) is not None:
            return line
        else:
            raise StopIteration
    def __iter__(self):
        return self
    def _reset_output(self) -> None:
        self.__eof = False
        self.__line_buffer.clear()
    def _get_simple_info(self, info_code: SvcInfoCode, result_type: InfoItemType,
                         timeout: int=-1) -> t.Any:
        if timeout == -1:
            send = None
        else:
            send = bytes([SvcInfoCode.TIMEOUT, int_to_bytes(4, 2, True),
                          int_to_bytes(timeout, 4, True), isc_info_end])
        receive = bytes([info_code])
        self.result_buffer.clear()
        self._svc.query(send, receive, self.result_buffer.content)
        if self.result_buffer.is_truncated():
            raise InterfaceError("Requested data can't fint into largest possible buffer")
        tag = self.result_buffer.get_tag()
        if tag == SvcInfoCode.TIMEOUT:
            return None
        if tag != info_code:
            raise InterfaceError(f"Unknown result code {tag}")
        if result_type == InfoItemType.INTEGER:
            result = self.result_buffer.get_short()
        elif result_type == InfoItemType.BIGINT:
            result = self.result_buffer.get_int()
        elif result_type == InfoItemType.BYTES:
            result = self.result_buffer.get_bytes()
        elif result_type == InfoItemType.STRING:
            result = self.result_buffer.get_string()
        else:
            result = None
        if self.result_buffer.get_tag() != isc_info_end:
            raise InterfaceError("Malformed result buffer (missing isc_info_end item)")
        return result
    def _fetch_complex_info(self, request: bytes, timeout: int=-1) -> None:
        if timeout == -1:
            send = None
        else:
            send = bytes([SvcInfoCode.TIMEOUT, int_to_bytes(4, 2, True),
                          int_to_bytes(timeout, 4, True), isc_info_end])
        self.result_buffer.clear()
        self._svc.query(send, request, self.result_buffer.content)
        if self.result_buffer.is_truncated():
            raise InterfaceError("Requested data can't fint into largest possible buffer")
    def _fetch_line(self, timeout: int=-1) -> t.Optional[str]:
        self._fetch_complex_info(bytes([SvcInfoCode.LINE]))
        result = None
        while not self.result_buffer.is_eof():
            tag = self.result_buffer.get_tag()
            if tag == SvcInfoCode.TIMEOUT:
                return None
            elif tag == SvcInfoCode.LINE:
                result = self.result_buffer.get_string()
        if self.result_buffer.get_tag() != isc_info_end:
            raise InterfaceError("Malformed result buffer (missing isc_info_end item)")
        return result
    def _read_output(self, *, init: str='', timeout: int=-1) -> None:
        assert self._svc is not None
        if timeout == -1:
            send = None
        else:
            send = bytes([SvcInfoCode.TIMEOUT, int_to_bytes(4, 2, True),
                          int_to_bytes(timeout, 4, True), isc_info_end])
        self.result_buffer.clear()
        self._svc.query(send, bytes([SvcInfoCode.TO_EOF]), self.result_buffer.content)
        tag = self.result_buffer.get_tag()
        if tag != SvcInfoCode.TO_EOF:
            raise InterfaceError(f"Service responded with error code: {tag}")
        init += self.result_buffer.get_string()
        self.__line_buffer = init.splitlines(keepends=True)
        self.__eof = self.result_buffer.get_tag() == isc_info_end
    def _read_all_binary_output(self, *, timeout: int=-1) -> bytes:
        assert self._svc is not None
        if timeout == -1:
            send = None
        else:
            send = bytes([SvcInfoCode.TIMEOUT, int_to_bytes(4, 2, True),
                          int_to_bytes(timeout, 4, True), isc_info_end])
        result = b''
        eof = False
        while not eof:
            self.result_buffer.clear()
            self._svc.query(send, bytes([SvcInfoCode.TO_EOF]), self.result_buffer.content)
            tag = self.result_buffer.get_tag()
            if tag != SvcInfoCode.TO_EOF:
                raise InterfaceError(f"Service responded with error code: {tag}")
            result += self.result_buffer.get_bytes()
            eof = self.result_buffer.get_tag() == isc_info_end
        return result
    def _read_next_binary_output(self, *, timeout: int=-1) -> bytes:
        assert self._svc is not None
        result = None
        if not self.__eof:
            self.result_buffer.clear()
            if timeout == -1:
                send = None
            else:
                send = bytes([SvcInfoCode.TIMEOUT, int_to_bytes(4, 2, True),
                              int_to_bytes(timeout, 4, True), isc_info_end])
            self._svc.query(send, bytes([SvcInfoCode.TO_EOF]), self.result_buffer.content)
            tag = self.result_buffer.get_tag()
            if tag != SvcInfoCode.TO_EOF:
                raise InterfaceError(f"Service responded with error code: {tag}")
            result = self.result_buffer.get_bytes()
            self.__eof = self.result_buffer.get_tag() == isc_info_end
        return result
    def _get_svr_db_info(self) -> t.Tuple[int, t.List]:
        self._fetch_complex_info(bytes([SvcInfoCode.SRV_DB_INFO]))
        num_attachments = -1
        databases = []
        while not self.result_buffer.is_eof():
            tag = self.result_buffer.get_tag()
            if tag == SvcInfoCode.TIMEOUT:
                return None
            elif tag == SvcDbInfoOption.ATT:
                num_attachments = self.result_buffer.get_short()
            elif tag == SPBItem.DBNAME:
                databases.append(self.result_buffer.get_string())
            elif tag == SvcDbInfoOption.DB:
                self.result_buffer.get_short()
        if self.result_buffer.get_tag() != isc_info_end:
            raise InterfaceError("Malformed result buffer (missing isc_info_end item)")
        return (num_attachments, databases)
    def get_service_manager_version(self) -> int:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.VERSION, InfoItemType.BIGINT)
    def get_server_version(self) -> str:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.SERVER_VERSION, InfoItemType.STRING)
    def get_architecture(self) -> str:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.IMPLEMENTATION, InfoItemType.STRING)
    def get_home_directory(self) -> str:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.GET_ENV, InfoItemType.STRING)
    def get_security_database_path(self) -> str:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.USER_DBPATH, InfoItemType.STRING)
    def get_lock_file_directory(self) -> str:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.GET_ENV_LOCK, InfoItemType.STRING)
    def get_message_file_directory(self) -> str:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.GET_ENV_MSG, InfoItemType.STRING)
    def get_server_capabilities(self) -> ServerCapability:
        assert self._svc is not None
        return ServerCapability(self._get_simple_info(SvcInfoCode.CAPABILITIES, InfoItemType.BIGINT))
    def get_connection_count(self) -> int:
        assert self._svc is not None
        return self._get_svr_db_info()[0]
    def get_attached_database_names(self) -> t.List[str]:
        assert self._svc is not None
        return self._get_svr_db_info()[1]
    def get_limbo_transaction_ids(self, *, database: str) -> t.List[int]:
        assert self._svc is not None
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SPBItem.OPTIONS, SvcRepairFlag.LIST_LIMBO_TRANS)
            self._svc.start(spb.get_buffer())
        self._reset_output()
        trans_ids = []
        data = Buffer(self._read_all_binary_output())
        while not data.is_eof():
            tag = data.get_tag()
            if tag in [SvcRepairOption.SINGLE_TRA_ID, SvcRepairOption.MULTI_TRA_ID]:
                trans_ids.append(data.get_int())
            elif tag in [SvcRepairOption.SINGLE_TRA_ID_64, SvcRepairOption.MULTI_TRA_ID_64]:
                trans_ids.append(data.get_int64())
            else:
                raise InterfaceError(f"Unrecognized result clumplet: {tag}")
        return trans_ids
    def commit_limbo_transaction(self, database: str, transaction_id: int) -> None:
        assert self._svc is not None
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, database)
            if transaction_id <= USHRT_MAX:
                spb.insert_int(SvcRepairOption.COMMIT_TRANS, transaction_id)
            else:
                spb.insert_bigint(SvcRepairOption.COMMIT_TRANS_64, transaction_id)
            self._svc.start(spb.get_buffer())
        self._read_all_binary_output()
    def rollback_limbo_transaction(self, database: str, transaction_id: int) -> None:
        assert self._svc is not None
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, database)
            if transaction_id <= USHRT_MAX:
                spb.insert_int(SvcRepairOption.ROLLBACK_TRANS, transaction_id)
            else:
                spb.insert_bigint(SvcRepairOption.ROLLBACK_TRANS_64, transaction_id)
            self._svc.start(spb.get_buffer())
        self._read_all_binary_output()
    def get_log(self, callback: CB_OUTPUT_LINE=None) -> None:
        assert self._svc is not None
        self._reset_output()
        self._svc.start(bytes([ServiceAction.GET_FB_LOG]))
        if callback:
            for line in self:
                callback(line)
    def get_statistics(self, *, database: str,
                       flags: SvcStatFlag=SvcStatFlag.DEFAULT,
                       tables: t.Sequence[str]=None,
                       callback: CB_OUTPUT_LINE=None) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.DB_STATS)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SPBItem.OPTIONS, flags)
            if tables is not None:
                cmdline = ['-t']
                cmdline.extend(tables)
                spb.insert_string(SPBItem.COMMAND_LINE, ' '.join(cmdline))
            self._svc.start(spb.get_buffer())
        if callback:
            for line in self:
                callback(line)
    def backup(self, *, database: str, backup: t.Union[str, t.Sequence[str]],
               backup_file_sizes: t.Sequence[int]=(),
               flags: SvcBackupFlag=SvcBackupFlag.NONE,
               callback: CB_OUTPUT_LINE=None, stats: str=None,
               verbose: bool=False, skip_data: str=None) -> None:
        assert self._svc is not None
        if isinstance(backup, str):
            backup = [backup]
            assert len(backup_file_sizes) == 0
        else:
            assert len(backup) >= 1
            assert len(backup) == len(backup_file_sizes) - 1
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.BACKUP)
            spb.insert_string(SPBItem.DBNAME, database)
            for filename, size in itertools.zip_longest(backup, backup_file_sizes):
                spb.insert_string(SvcBackupOption.FILE, filename)
                if size is not None:
                    spb.insert_int(SvcBackupOption.LENGTH, size)
            if skip_data is not None:
                spb.insert_string(SvcBackupOption.SKIP_DATA, skip_data)
            spb.insert_int(SPBItem.OPTIONS, flags)
            if verbose:
                spb.insert_tag(SPBItem.VERBOSE)
            if stats:
                spb.insert_string(SvcBackupOption.STAT, stats)
            self._svc.start(spb.get_buffer())
        if callback:
            for line in self:
                callback(line)
    def local_backup(self, *, database: str, backup_stream: t.BinaryIO,
                     flags: SvcBackupFlag=SvcBackupFlag.NONE) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.BACKUP)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_string(SvcBackupOption.FILE, 'stdout')
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._svc.start(spb.get_buffer())
        while not self.__eof:
            backup_stream.write(self._read_next_binary_output())
    def restore(self, *, backup: t.Union[str, t.Sequence[str]],
                database: t.Union[str, t.Sequence[str]],
                db_file_pages: t.Sequence[int]=(),
                flags: SvcRestoreFlag=SvcRestoreFlag.CREATE,
                callback: CB_OUTPUT_LINE=None, stats: str=None,
                verbose: bool=True, skip_data: str=None, page_size: int=None,
                buffers: int=None, access_mode: PrpAccessMode=PrpAccessMode.READ_WRITE) -> None:
        assert self._svc is not None
        if isinstance(backup, str):
            backup = [backup]
        if isinstance(database, str):
            database = [database]
            assert len(db_file_pages) == 0
        else:
            assert len(database) >= 1
            assert len(database) == len(db_file_pages) - 1
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.RESTORE)
            for filename in backup:
                spb.insert_string(SvcRestoreOption.FILE, filename)
            for filename, size in itertools.zip_longest(database, db_file_pages):
                spb.insert_string(SPBItem.DBNAME, filename)
                if size is not None:
                    spb.insert_int(SvcRestoreOption.LENGTH, size)
            if page_size is not None:
                spb.insert_int(SvcRestoreOption.PAGE_SIZE, page_size)
            if buffers is not None:
                spb.insert_int(SvcRestoreOption.BUFFERS, buffers)
            spb.insert_bytes(SvcRestoreOption.ACCESS_MODE, bytes([access_mode]))
            if skip_data is not None:
                spb.insert_string(SvcRestoreOption.SKIP_DATA, skip_data)
            spb.insert_int(SPBItem.OPTIONS, flags)
            if verbose:
                spb.insert_tag(SPBItem.VERBOSE)
            if stats:
                spb.insert_string(SvcBackupOption.STAT, stats)
            self._svc.start(spb.get_buffer())
        if callback:
            for line in self:
                callback(line)
    def local_restore(self, *, backup_stream: t.BinaryIO,
                      database: t.Union[str, t.Sequence[str]],
                      db_file_pages: t.Sequence[int]=(),
                      flags: SvcRestoreFlag=SvcRestoreFlag.CREATE,
                      page_size: int=None, buffers: int=None,
                      access_mode: PrpAccessMode=PrpAccessMode.READ_WRITE) -> None:
        assert self._svc is not None
        if isinstance(database, str):
            database = [database]
            assert len(db_file_pages) == 0
        else:
            assert len(database) >= 1
            assert len(database) == len(db_file_pages) - 1
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.RESTORE)
            spb.insert_string(SvcRestoreOption.FILE, 'stdin')
            for filename, size in itertools.zip_longest(database, db_file_pages):
                spb.insert_string(SPBItem.DBNAME, filename)
                if size is not None:
                    spb.insert_int(SvcRestoreOption.LENGTH, size)
            if page_size is not None:
                spb.insert_int(SvcRestoreOption.PAGE_SIZE, page_size)
            if buffers is not None:
                spb.insert_int(SvcRestoreOption.BUFFERS, buffers)
            spb.insert_bytes(SvcRestoreOption.ACCESS_MODE, bytes([access_mode]))
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._svc.start(spb.get_buffer())
        #
        request_length = 0
        line = ''
        keep_going = True
        while keep_going:
            no_data = False
            self.result_buffer.clear()
            if request_length > 0:
                request_length = min([request_length, 65500])
                raw = backup_stream.read(request_length)
                send = bytes([SvcInfoCode.LINE]) + int_to_bytes(len(raw), 2, True) + raw + bytes([isc_info_end])
            else:
                send = None
            self._svc.query(send, bytes([SvcInfoCode.STDIN, SvcInfoCode.LINE]), self.result_buffer.content)
            tag = self.result_buffer.get_tag()
            while tag != isc_info_end:
                if tag == SvcInfoCode.STDIN:
                    request_length = self.result_buffer.get_int()
                elif tag == SvcInfoCode.LINE:
                    line = self.result_buffer.get_string()
                elif tag == isc_info_data_not_ready:
                    no_data = True
                else:
                    raise InterfaceError(f"Service responded with error code: {tag}")
                tag = self.result_buffer.get_tag()
            keep_going = no_data or request_length != 0 or len(line) > 0
    def nbackup(self, *, database: str, backup: str, level: int=0,
                direct: bool=False, flags: SvcNBackupFlag=SvcNBackupFlag.NONE) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.NBAK)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_string(SvcNBackupOption.FILE, backup)
            spb.insert_int(SvcNBackupOption.LEVEL, level)
            if direct:
                spb.insert_string(SvcNBackupOption.DIRECT, 'ON')
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._svc.start(spb.get_buffer())
        self.wait()
    def nrestore(self, *, backups: t.Sequence[str], database: str,
                 direct: bool=False, flags: SvcNBackupFlag=SvcNBackupFlag.NONE) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.NREST)
            spb.insert_string(SPBItem.DBNAME, database)
            for backup in backups:
                spb.insert_string(SvcNBackupOption.FILE, backup)
            if direct:
                spb.insert_string(SvcNBackupOption.DIRECT, 'ON')
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._svc.start(spb.get_buffer())
        self.wait()
    def trace_start(self, *, config: str, name: str=None) -> int:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.TRACE_START)
            if name is not None:
                spb.insert_string(SvcTraceOption.NAME, name)
            spb.insert_string(SvcTraceOption.CONFIG, config)
            self._svc.start(spb.get_buffer())
        response = self._fetch_line()
        if response.startswith('Trace session ID'):
            return int(response.split()[3])
        else:
            # response should contain the error message
            raise DatabaseError(response)
    def __trace_action(self, action: ServiceAction, label: str, session_id: int) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(action)
            spb.insert_int(SvcTraceOption.ID, session_id)
            self._svc.start(spb.get_buffer())
        response = self._fetch_line()
        if not response.startswith(f"Trace session ID {session_id} {label}"):
            # response should contain the error message
            raise DatabaseError(response)
    def trace_stop(self, *, session_id: int) -> None:
        self.__trace_action(ServiceAction.TRACE_STOP, 'stopped', session_id)
    def trace_suspend(self, *, session_id: int) -> None:
        self.__trace_action(ServiceAction.TRACE_SUSPEND, 'paused', session_id)
    def trace_resume(self, *, session_id: int) -> None:
        self.__trace_action(ServiceAction.TRACE_RESUME, 'resumed', session_id)
    def trace_list(self) -> t.Dict[int, t.Dict[str, t.Any]]:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.TRACE_LIST)
            self._svc.start(spb.get_buffer())
        result = {}
        for line in self:
            if not line.strip():
                session_id = None
            elif line.startswith('Session ID:'):
                session_id = int(line.split(':')[1].strip())
                result[session_id] = dict()
            elif line.lstrip().startswith('name:'):
                result[session_id]['name'] = line.split(':')[1].strip()
            elif line.lstrip().startswith('user:'):
                result[session_id]['user'] = line.split(':')[1].strip()
            elif line.lstrip().startswith('date:'):
                result[session_id]['date'] = datetime.datetime.strptime(
                    line.split(':', 1)[1].strip(),
                    '%Y-%m-%d %H:%M:%S')
            elif line.lstrip().startswith('flags:'):
                result[session_id]['flags'] = line.split(':')[1].strip().split(',')
            else:
                raise InterfaceError(f"Unexpected line in trace session list: {line}")
        return result
    def set_default_page_buffers(self, *, database: str, value: int) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SvcPropertiesOption.PAGE_BUFFERS, value)
            self._svc.start(spb.get_buffer())
    def set_sweep_interval(self, *, database: str, value: int) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SvcPropertiesOption.SWEEP_INTERVAL, value)
            self._svc.start(spb.get_buffer())
    def set_space_reservation(self, *, database: str, value: bool) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_bytes(SvcPropertiesOption.RESERVE_SPACE,
                             bytes([PrpSpaceReservation.RESERVE if value else PrpSpaceReservation.USE_FULL]))
            self._svc.start(spb.get_buffer())
    def set_forced_writes(self, *, database: str, value: bool) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_bytes(SvcPropertiesOption.WRITE_MODE,
                             bytes([PrpWriteMode.SYNC if value else PrpWriteMode.ASYNC]))
            self._svc.start(spb.get_buffer())
    def set_read_only(self, *, database: str, value: bool) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_bytes(SvcPropertiesOption.ACCESS_MODE,
                             bytes([PrpAccessMode.READ_ONLY if value else PrpAccessMode.READ_WRITE]))
            self._svc.start(spb.get_buffer())
    def set_sql_dialect(self, *, database: str, value: int) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SvcPropertiesOption.SET_SQL_DIALECT, value)
            self._svc.start(spb.get_buffer())
    def activate_shadow(self, *, database: str) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SPBItem.OPTIONS, SvcPropertiesFlag.ACTIVATE)
            self._svc.start(spb.get_buffer())
    def no_linger(self, *, database: str) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SPBItem.OPTIONS, SvcPropertiesFlag.NOLINGER)
            self._svc.start(spb.get_buffer())
    def shutdown(self, *, database: str, mode: ShutdownMode,
                 method: ShutdownMethod, timeout: int) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_bytes(SvcPropertiesOption.SHUTDOWN_MODE, bytes([mode]))
            spb.insert_int(method, timeout)
            self._svc.start(spb.get_buffer())
    def bring_online(self, *, database: str, mode: OnlineMode=OnlineMode.NORMAL) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_bytes(SvcPropertiesOption.ONLINE_MODE, bytes([mode]))
            self._svc.start(spb.get_buffer())
    def sweep(self, *, database: str) -> None:
        assert self._svc is not None
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SPBItem.OPTIONS, SvcRepairFlag.SWEEP_DB)
            self._svc.start(spb.get_buffer())
        self._reset_output()
        self.wait()
    def repair(self, *, database: str, flags: SvcRepairFlag=SvcRepairFlag.REPAIR) -> bytes:
        assert self._svc is not None
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._svc.start(spb.get_buffer())
        self._reset_output()
        self.wait()
    def validate(self, *, database: str, include_table: str=None,
                 exclude_table: str=None, include_index: str=None,
                 exclude_index: str=None, lock_timeout: int=None,
                 callback: CB_OUTPUT_LINE=None) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.VALIDATE)
            spb.insert_string(SPBItem.DBNAME, database)
            if include_table is not None:
                spb.insert_string(SvcValidateOption.INCLUDE_TABLE, include_table)
            if exclude_table is not None:
                spb.insert_string(SvcValidateOption.EXCLUDE_TABLE, exclude_table)
            if include_index is not None:
                spb.insert_string(SvcValidateOption.INCLUDE_INDEX, include_index)
            if exclude_index is not None:
                spb.insert_string(SvcValidateOption.EXCLUDE_INDEX, exclude_index)
            if lock_timeout is not None:
                spb.insert_int(SvcValidateOption.LOCK_TIMEOUT, lock_timeout)
            self._svc.start(spb.get_buffer())
        if callback:
            for line in self:
                callback(line)
    def __fetch_users(self, data: Buffer) -> t.List[UserInfo]:
        users = []
        user = {}
        while not data.is_eof():
            tag = data.get_tag()
            if tag == SvcUserOption.USER_NAME:
                if user:
                    users.append(UserInfo(**user))
                    user.clear()
                user['user_name'] = data.get_string()
            elif tag == SvcUserOption.USER_ID:
                user['user_id'] = data.get_int()
            elif tag == SvcUserOption.GROUP_ID:
                user['group_id'] = data.get_int()
            elif tag == SvcUserOption.PASSWORD:
                user['password'] = data.get_bytes()
            elif tag == SvcUserOption.GROUP_NAME:
                user['group_name'] = data.get_string()
            elif tag == SvcUserOption.FIRST_NAME:
                user['first_name'] = data.get_string()
            elif tag == SvcUserOption.MIDDLE_NAME:
                user['middle_name'] = data.get_string()
            elif tag == SvcUserOption.LAST_NAME:
                user['last_name'] = data.get_string()
            elif tag == SvcUserOption.ADMIN:
                user['admin'] = bool(data.get_int())
            else:
                raise InterfaceError(f"Unrecognized result clumplet: {tag}")
        if user:
            users.append(UserInfo(**user))
        return users
    def get_users(self, *, database: str=None, sql_role: str=None) -> t.List[UserInfo]:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.DISPLAY_USER_ADM)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, database)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role)
            self._svc.start(spb.get_buffer())
        return self.__fetch_users(Buffer(self._read_all_binary_output()))
    def get_user(self, user_name: str, *, database: str=None, sql_role: str=None) -> t.Optional[UserInfo]:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.DISPLAY_USER_ADM)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_string(SvcUserOption.USER_NAME, user_name)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role)
            self._svc.start(spb.get_buffer())
        users = self.__fetch_users(Buffer(self._read_all_binary_output()))
        return users[0] if users else None
    def add_user(self, *, user_name: str, password: str, user_id: int=None,
                 group_id: int=None, first_name: str=None, middle_name: str=None,
                 last_name: str=None, admin: bool=None, database: str=None,
                 sql_role: str=None) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.ADD_USER)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, database)
            spb.insert_string(SvcUserOption.USER_NAME, user_name)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role)
            spb.insert_string(SvcUserOption.PASSWORD, password)
            if user_id is not None:
                spb.insert_int(SvcUserOption.USER_ID, user_id)
            if group_id is not None:
                spb.insert_int(SvcUserOption.GROUP_ID, group_id)
            if first_name is not None:
                spb.insert_string(SvcUserOption.FIRST_NAME, first_name)
            if middle_name is not None:
                spb.insert_string(SvcUserOption.MIDDLE_NAME, middle_name)
            if last_name is not None:
                spb.insert_string(SvcUserOption.LAST_NAME, last_name)
            if admin is not None:
                spb.insert_int(SvcUserOption.ADMIN, 1 if admin else 0)
            self._svc.start(spb.get_buffer())
        self.wait()
    def modify_user(self, user_name: str, *, password: str=None,
                    user_id: int=None, group_id: int=None,
                    first_name: str=None, middle_name: str=None,
                    last_name: str=None, admin: bool=None) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.MODIFY_USER)
            spb.insert_string(SvcUserOption.USER_NAME, user_name)
            if password is not None:
                spb.insert_string(SvcUserOption.PASSWORD, password)
            if user_id is not None:
                spb.insert_int(SvcUserOption.USER_ID, user_id)
            if group_id is not None:
                spb.insert_int(SvcUserOption.GROUP_ID, group_id)
            if first_name is not None:
                spb.insert_string(SvcUserOption.FIRST_NAME, first_name)
            if middle_name is not None:
                spb.insert_string(SvcUserOption.MIDDLE_NAME, middle_name)
            if last_name is not None:
                spb.insert_string(SvcUserOption.LAST_NAME, last_name)
            if admin is not None:
                spb.insert_int(SvcUserOption.ADMIN, 1 if admin else 0)
            self._svc.start(spb.get_buffer())
        self.wait()
    def delete_user(self, user_name: str, *, database: str=None, sql_role: str=None) -> None:
        assert self._svc is not None
        self._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServiceAction.DELETE_USER)
            spb.insert_string(SvcUserOption.USER_NAME, user_name)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, database)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role)
            self._svc.start(spb.get_buffer())
        self.wait()
    def user_exists(self, user_name: str, *, database: str=None, sql_role: str=None) -> bool:
        return self.get_user(user_name, database=database, sql_role=sql_role) is not None
    def is_running(self) -> bool:
        assert self._svc is not None
        return self._get_simple_info(SvcInfoCode.RUNNING, InfoItemType.BIGINT) > 0
    def readline(self) -> t.Optional[str]:
        if self.__eof and not self.__line_buffer:
            return None
        if not self.__line_buffer:
            self._read_output()
        elif len(self.__line_buffer) == 1:
            line = self.__line_buffer.pop(0)
            if self.__eof:
                return line
            self._read_output(init=line)
        if self.__line_buffer:
            return self.__line_buffer.pop(0)
        return None
    def readlines(self) -> t.List[str]:
        return [line for line in self]
    def wait(self) -> None:
        while self.is_running():
            for _ in self:
                pass
    def close(self) -> None:
        if self._svc is not None:
            self._svc.detach()
            self._svc = None
    version = property(lambda self: self.__version)
    engine_version = property(lambda self: self.__engine_version)

def connect_service(*, host: str='', trusted_auth: bool=False, user: str=None,
                    password: str=None, config: str=None) -> Service:
    if not host.endswith('service_mgr'):
        if host and not host.endswith(':'):
            host += ':'
        host += 'service_mgr'
    if user is None:
        user = os.environ.get('ISC_USER', None)
    if password is None:
        password = os.environ.get('ISC_PASSWORD', None)
    spb = SPB_ATTACH(trusted_auth=trusted_auth, user=user, password=password, config=config)
    spb_buf = spb.get_buffer()
    svc = a.get_api().master.get_dispatcher().attach_service_manager(host, spb_buf)
    con = Service(svc, spb_buf, host)
    for hook in hooks.get_hooks(HookType.SERVICE_ATTACHED):
        hook(con)
    return con

