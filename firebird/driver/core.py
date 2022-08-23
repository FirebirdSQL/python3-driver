# coding:utf-8
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

from __future__ import annotations
from typing import Any, Type, Union, Dict, Set, List, Tuple, Sequence, Mapping, Optional, \
     BinaryIO, Callable
import sys
import os
import weakref
import itertools
import threading
import io
import contextlib
import struct
from abc import ABC, abstractmethod
from warnings import warn
from queue import PriorityQueue
from ctypes import memset, memmove, create_string_buffer, byref, string_at, addressof, pointer
from firebird.base.types import Sentinel, UNLIMITED, ByteOrder
from firebird.base.logging import LoggingIdMixin, UNDEFINED
from firebird.base.buffer import MemoryBuffer, BufferFactory, BytesBufferFactory, \
     CTypesBufferFactory, safe_ord
from . import fbapi as a
from .types import *
from .interfaces import iAttachment, iTransaction, iStatement, iMessageMetadata, iBlob, \
     iResultSet, iDtc, iService, iCryptKeyCallbackImpl
from .hooks import APIHook, ConnectionHook, ServerHook, register_class, get_callbacks, add_hook
from .config import driver_config

SHRT_MIN = -32768
SHRT_MAX = 32767
USHRT_MAX = 65535
INT_MIN = -2147483648
INT_MAX = 2147483647
UINT_MAX = 4294967295
LONG_MIN = -9223372036854775808
LONG_MAX = 9223372036854775807
MAX_BLOB_SEGMENT_SIZE = 65535

FS_ENCODING = sys.getfilesystemencoding()

#: Python dictionary that maps Firebird character set names (key) to Python character sets (value).
CHARSET_MAP = {None: a.getpreferredencoding(), 'NONE': a.getpreferredencoding(),
               'OCTETS': None, 'UNICODE_FSS': 'utf_8', 'UTF8': 'utf_8', 'UTF-8': 'utf_8',
               'ASCII': 'ascii', 'SJIS_0208': 'shift_jis', 'EUCJ_0208': 'euc_jp',
               'DOS737': 'cp737', 'DOS437': 'cp437', 'DOS850': 'cp850',
               'DOS865': 'cp865', 'DOS860': 'cp860', 'DOS863': 'cp863',
               'DOS775': 'cp775', 'DOS862': 'cp862', 'DOS864': 'cp864',
               'ISO8859_1': 'iso8859_1', 'ISO8859_2': 'iso8859_2',
               'ISO8859_3': 'iso8859_3', 'ISO8859_4': 'iso8859_4',
               'ISO8859_5': 'iso8859_5', 'ISO8859_6': 'iso8859_6',
               'ISO8859_7': 'iso8859_7', 'ISO8859_8': 'iso8859_8',
               'ISO8859_9': 'iso8859_9', 'ISO8859_13': 'iso8859_13',
               'KSC_5601': 'euc_kr', 'DOS852': 'cp852', 'DOS857': 'cp857',
               'DOS858': 'cp858', 'DOS861': 'cp861', 'DOS866': 'cp866',
               'DOS869': 'cp869', 'WIN1250': 'cp1250', 'WIN1251': 'cp1251',
               'WIN1252': 'cp1252', 'WIN1253': 'cp1253', 'WIN1254': 'cp1254',
               'BIG_5': 'big5', 'GB_2312': 'gb2312', 'WIN1255': 'cp1255',
               'WIN1256': 'cp1256', 'WIN1257': 'cp1257', 'GB18030': 'gb18030',
               'GBK': 'gbk', 'KOI8R': 'koi8_r', 'KOI8U': 'koi8_u',
               'WIN1258': 'cp1258',
               }

# Internal
_master = None
_util = None
_thns = threading.local()

_tenTo = [10 ** x for x in range(20)]
_i2name = {DbInfoCode.READ_SEQ_COUNT: 'sequential', DbInfoCode.READ_IDX_COUNT: 'indexed',
           DbInfoCode.INSERT_COUNT: 'inserts', DbInfoCode.UPDATE_COUNT: 'updates',
           DbInfoCode.DELETE_COUNT: 'deletes', DbInfoCode.BACKOUT_COUNT: 'backouts',
           DbInfoCode.PURGE_COUNT: 'purges', DbInfoCode.EXPUNGE_COUNT: 'expunges'}

_bpb_stream = bytes([1, BPBItem.TYPE, 1, BlobType.STREAM])

# Info structural codes
isc_info_end = 1
isc_info_truncated = 2
isc_info_error = 3
isc_info_data_not_ready = 4

def __api_loaded(api: a.FirebirdAPI) -> None:
    setattr(sys.modules[__name__], '_master', api.fb_get_master_interface())
    setattr(sys.modules[__name__], '_util', _master.get_util_interface())

add_hook(APIHook.LOADED, a.FirebirdAPI, __api_loaded)

def _create_blob_buffer(size: int=MAX_BLOB_SEGMENT_SIZE) -> Any:
    if size < MAX_BLOB_SEGMENT_SIZE:
        result = getattr(_thns, 'blob_buf', None)
        if result is None:
            result = create_string_buffer(MAX_BLOB_SEGMENT_SIZE)
            _thns.blob_buf = result
        else:
            memset(result, 0, MAX_BLOB_SEGMENT_SIZE)
    else:
        result = create_string_buffer(size)
    return result

def _encode_timestamp(v: Union[datetime.datetime, datetime.date]) -> bytes:
    # Convert datetime.datetime or datetime.date to BLR format timestamp
    if isinstance(v, datetime.datetime):
        return _util.encode_date(v.date()).to_bytes(4, 'little') + _util.encode_time(v.time()).to_bytes(4, 'little')
    elif isinstance(v, datetime.date):
        return _util.encode_date(v.date()).to_bytes(4, 'little') + _util.encode_time(datetime.time()).to_bytes(4, 'little')
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
        raise ValueError(msg)

def _is_str_param(value: Any, datatype: SQLDataType) -> bool:
    return ((isinstance(value, str) and datatype != SQLDataType.BLOB) or
            datatype in [SQLDataType.TEXT, SQLDataType.VARYING])

def create_meta_descriptors(meta: iMessageMetadata) -> List[ItemMetadata]:
    result = []
    for i in range(meta.get_count()):
        result.append(ItemMetadata(field=meta.get_field(i),
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
def transaction(transact_object: Transactional, *, tpb: bytes=None,
                bypass: bool=False) -> Transactional:
    """Context manager for `~firebird.driver.types.Transactional` objects.

    Starts new transaction when context is entered. On exit calls `rollback()` when
    exception was raised, or `commit()` if there was no error. Exception raised
    in managed context is NOT suppressed.

    Arguments:
        transact_object: Managed transactional object.
        tpb: Transaction parameter buffer used to start the transaction.
        bypass: When both `bypass` and `transact_object.is_active()` are `True` when
                context is entered, the context manager does nothing on exit.
    """
    if bypass and transact_object.is_active():
        yield transact_object
    else:
        try:
            transact_object.begin(tpb)
            yield transact_object
        except:
            transact_object.rollback()
            raise
        else:
            transact_object.commit()

@contextlib.contextmanager
def temp_database(*args, **kwargs) -> Connection:
    """Context manager for temporary databases. Creates new database when context
    is entered, and drops it on exit. Exception raised in managed context is NOT suppressed.

    All positional and keyword arguments are passed to `create_database`.
    """
    con = create_database(*args, **kwargs)
    try:
        yield con
    except:
        con.drop_database()
        raise
    else:
        con.drop_database()

_OP_DIE = object()
_OP_RECORD_AND_REREGISTER = object()

# Managers for Parameter buffers
class TPB:
    """Transaction Parameter Buffer.
    """
    def __init__(self, *, access_mode: TraAccessMode = TraAccessMode.WRITE,
                 isolation: Isolation = Isolation.SNAPSHOT,
                 lock_timeout: int = -1, no_auto_undo: bool = False,
                 auto_commit: bool = False, ignore_limbo: bool = False,
                 at_snapshot_number: int=None, encoding: str='ascii'):
        self.encoding: str = encoding
        self.access_mode: TraAccessMode = access_mode
        self.isolation: Isolation = isolation
        self.lock_timeout: int = lock_timeout
        self.no_auto_undo: bool = no_auto_undo
        self.auto_commit: bool = auto_commit
        self.ignore_limbo: bool = ignore_limbo
        self._table_reservation: List[Tuple[str, TableShareMode, TableAccessMode]] = []
        # Firebird 4
        self.at_snapshot_number: int = at_snapshot_number
    def clear(self) -> None:
        """Clear all information.
        """
        self.access_mode = TraAccessMode.WRITE
        self.isolation = Isolation.SNAPSHOT
        self.lock_timeout = -1
        self.no_auto_undo = False
        self.auto_commit = False
        self.ignore_limbo = False
        self._table_reservation = []
        # Firebird 4
        self.at_snapshot_number = None
    def parse_buffer(self, buffer: bytes) -> None:
        """Load information from TPB.
        """
        self.clear()
        with a.get_api().util.get_xpb_builder(XpbKind.TPB, buffer) as tpb:
            while not tpb.is_eof():
                tag = tpb.get_tag()
                if tag in TraAccessMode._value2member_map_:
                    self.access_mode = TraAccessMode(tag)
                elif tag in TraIsolation._value2member_map_:
                    isolation = TraIsolation(tag)
                    if isolation != TraIsolation.READ_COMMITTED:
                        self.isolation = Isolation(isolation)
                elif tag in TraReadCommitted._value2member_map_:
                    isolation = TraReadCommitted(tag)
                    if isolation == TraReadCommitted.RECORD_VERSION:
                        self.isolation = Isolation.READ_COMMITTED_RECORD_VERSION
                    else:
                        self.isolation = Isolation.READ_COMMITTED_NO_RECORD_VERSION
                elif tag in TraLockResolution._value2member_map_:
                    self.lock_timeout = -1 if TraLockResolution(tag).WAIT else 0
                elif tag == TPBItem.AUTOCOMMIT:
                    self.auto_commit = True
                elif tag == TPBItem.NO_AUTO_UNDO:
                    self.no_auto_undo = True
                elif tag == TPBItem.IGNORE_LIMBO:
                    self.ignore_limbo = True
                elif tag == TPBItem.LOCK_TIMEOUT:
                    self.lock_timeout = tpb.get_int()
                elif tag == TPBItem.AT_SNAPSHOT_NUMBER:
                    self.at_snapshot_number = tpb.get_bigint()
                elif tag in TableAccessMode._value2member_map_:
                    tbl_access = TableAccessMode(tag)
                    tbl_name = tpb.get_string(encoding=self.encoding)
                    tpb.move_next()
                    if tpb.is_eof():
                        raise ValueError(f"Missing share mode value in table {tbl_name} reservation")
                    if (val := tpb.get_tag()) not in TableShareMode._value2member_map_:
                        raise ValueError(f"Missing share mode value in table {tbl_name} reservation")
                    tbl_share = TableShareMode(val)
                    self.reserve_table(tbl_name, tbl_share, tbl_access)
                tpb.move_next()
    def get_buffer(self) -> bytes:
        """Create TPB from stored information.
        """
        with a.get_api().util.get_xpb_builder(XpbKind.TPB) as tpb:
            tpb.insert_tag(self.access_mode)
            isolation = (Isolation.READ_COMMITTED_RECORD_VERSION
                         if self.isolation == Isolation.READ_COMMITTED
                         else self.isolation)
            if isolation in [Isolation.SNAPSHOT, Isolation.SERIALIZABLE]:
                tpb.insert_tag(isolation)
            elif isolation == Isolation.READ_COMMITTED_READ_CONSISTENCY:
                tpb.insert_tag(TPBItem.READ_CONSISTENCY)
            else:
                tpb.insert_tag(TraIsolation.READ_COMMITTED)
                tpb.insert_tag(TraReadCommitted.RECORD_VERSION
                               if isolation == Isolation.READ_COMMITTED_RECORD_VERSION
                               else TraReadCommitted.NO_RECORD_VERSION)
            tpb.insert_tag(TraLockResolution.NO_WAIT if self.lock_timeout == 0 else TraLockResolution.WAIT)
            if self.lock_timeout > 0:
                tpb.insert_int(TPBItem.LOCK_TIMEOUT, self.lock_timeout)
            if self.auto_commit:
                tpb.insert_tag(TPBItem.AUTOCOMMIT)
            if self.no_auto_undo:
                tpb.insert_tag(TPBItem.NO_AUTO_UNDO)
            if self.ignore_limbo:
                tpb.insert_tag(TPBItem.IGNORE_LIMBO)
            if self.at_snapshot_number is not None:
                tpb.insert_bigint(TPBItem.AT_SNAPSHOT_NUMBER, self.at_snapshot_number)
            for table in self._table_reservation:
                # Access mode + table name
                tpb.insert_string(table[2], table[0], encoding=self.encoding)
                tpb.insert_tag(table[1])  # Share mode
            result = tpb.get_buffer()
        return result
    def reserve_table(self, name: str, share_mode: TableShareMode, access_mode: TableAccessMode) -> None:
        """Set information about table reservation.
        """
        self._table_reservation.append((name, share_mode, access_mode))

class DPB:
    """Database Parameter Buffer.
    """
    def __init__(self, *, user: str=None, password: str=None, role: str=None,
                 trusted_auth: bool=False, sql_dialect: int=3, timeout: int=None,
                 charset: str='UTF8', cache_size: int=None, no_gc: bool=False,
                 no_db_triggers: bool=False, no_linger: bool=False,
                 utf8filename: bool=False, dbkey_scope: DBKeyScope=None,
                 dummy_packet_interval: int=None, overwrite: bool=False,
                 db_cache_size: int=None, forced_writes: bool=None,
                 reserve_space: bool=None, page_size: int=None, read_only: bool=False,
                 sweep_interval: int=None, db_sql_dialect: int=None, db_charset: str=None,
                 config: str=None, auth_plugin_list: str=None, session_time_zone: str=None,
                 set_db_replica: ReplicaMode=None, set_bind: str=None,
                 decfloat_round: DecfloatRound=None,
                 decfloat_traps: List[DecfloatTraps]=None
                 ):
        # Available options:
        # AuthClient, WireCryptPlugin, Providers, ConnectionTimeout, WireCrypt,
        # WireCompression, DummyPacketInterval, RemoteServiceName, RemoteServicePort,
        # RemoteAuxPort, TcpNoNagle, IpcName, RemotePipeName, ClientBatchBuffer [FB4+]
        #: Configuration override
        self.config: Optional[str] = config
        #: List of authentication plugins override
        self.auth_plugin_list: str = auth_plugin_list
        # Connect
        #: Use trusted authentication
        self.trusted_auth: bool = trusted_auth
        #: User name
        self.user: str = user
        #: User password
        self.password: str = password
        #: User role
        self.role: str = role
        #: SQL Dialect for database connection
        self.sql_dialect: int = sql_dialect
        #: Character set for database connection
        self.charset: str = charset
        #: Connection timeout
        self.timeout: Optional[int] = timeout
        #: Dummy packet interval for this database connection
        self.dummy_packet_interval: Optional[int] = dummy_packet_interval
        #: Page cache size override for database connection
        self.cache_size: int = cache_size
        #: Disable garbage collection for database connection
        self.no_gc: bool = no_gc
        #: Disable database triggers for database connection
        self.no_db_triggers: bool = no_db_triggers
        #: Do not use linger for database connection
        self.no_linger: bool = no_linger
        #: Database filename passed in UTF8
        self.utf8filename: bool = utf8filename
        #: Scope for RDB$DB_KEY values
        self.dbkey_scope: Optional[DBKeyScope] = dbkey_scope
        #: Session time zone [Firebird 4]
        self.session_time_zone: Optional[str] = session_time_zone
        #: Set replica mode [Firebird 4]
        self.set_db_replica: Optional[ReplicaMode] = set_db_replica
        #: Set BIND [Firebird 4]
        self.set_bind: Optional[str] = set_bind
        #: Set DECFLOAT ROUND [Firebird 4]
        self.decfloat_round: Optional[DecfloatRound] = decfloat_round
        #: Set DECFLOAT TRAPS [Firebird 4]
        self.decfloat_traps: Optional[List[DecfloatTraps]] = \
            None if decfloat_traps is None else list(decfloat_traps)
        # For db create
        #: Database page size [db create only]
        self.page_size: Optional[int] = page_size
        #: Overwrite existing database [db create only]
        self.overwrite: bool = overwrite
        #: Number of pages in database cache [db create only]
        self.db_buffers = None
        #: Database cache size [db create only]
        self.db_cache_size: Optional[int] = db_cache_size
        #: Database write mode (True = sync/False = async) [db create only]
        self.forced_writes: Optional[bool] = forced_writes
        #: Database data page space usage (True = reserve space, False = Use all space) [db create only]
        self.reserve_space: Optional[bool] = reserve_space
        #: Database access mode (True = read-only/False = read-write) [db create only]
        self.read_only: bool = read_only
        #: Sweep interval for the database [db create only]
        self.sweep_interval: Optional[int] = sweep_interval
        #: SQL dialect for the database [db create only]
        self.db_sql_dialect: Optional[int] = db_sql_dialect
        #: Character set for the database [db create only]
        self.db_charset: Optional[str] = db_charset
    def clear(self) -> None:
        """Clear all information.
        """
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
        self.session_time_zone = None
        self.set_db_replica = None
        self.set_bind = None
        self.decfloat_round = None
        self.decfloat_traps = None
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
        """Load information from DPB.
        """
        _py_charset: str = CHARSET_MAP.get(self.charset, 'ascii')
        self.clear()
        with a.get_api().util.get_xpb_builder(XpbKind.DPB, buffer) as dpb:
            while not dpb.is_eof():
                tag = dpb.get_tag()
                if tag == DPBItem.CONFIG:
                    self.config = dpb.get_string(encoding=_py_charset)
                elif tag == DPBItem.AUTH_PLUGIN_LIST:
                    self.auth_plugin_list = dpb.get_string()
                elif tag == DPBItem.TRUSTED_AUTH:
                    self.trusted_auth = True
                elif tag == DPBItem.USER_NAME:
                    self.user = dpb.get_string(encoding=_py_charset)
                elif tag == DPBItem.PASSWORD:
                    self.password = dpb.get_string(encoding=_py_charset)
                elif tag == DPBItem.CONNECT_TIMEOUT:
                    self.timeout = dpb.get_int()
                elif tag == DPBItem.DUMMY_PACKET_INTERVAL:
                    self.dummy_packet_interval = dpb.get_int()
                elif tag == DPBItem.SQL_ROLE_NAME:
                    self.role = dpb.get_string(encoding=_py_charset)
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
                elif tag == DPBItem.SESSION_TIME_ZONE:
                    self.session_time_zone = dpb.get_string()
                elif tag == DPBItem.SET_DB_REPLICA:
                    self.set_db_replica = ReplicaMode(dpb.get_int())
                elif tag == DPBItem.SET_BIND:
                    self.set_bind = dpb.get_string()
                elif tag == DPBItem.DECFLOAT_ROUND:
                    self.decfloat_round = DecfloatRound(dpb.get_string())
                elif tag == DPBItem.DECFLOAT_TRAPS:
                    self.decfloat_traps = [DecfloatTraps(v.strip())
                                           for v in dpb.get_string().split(',')]
    def get_buffer(self, *, for_create: bool = False) -> bytes:
        """Create DPB from stored information.
        """
        _py_charset: str = CHARSET_MAP.get(self.charset, 'ascii')
        with a.get_api().util.get_xpb_builder(XpbKind.DPB) as dpb:
            if self.config is not None:
                dpb.insert_string(DPBItem.CONFIG, self.config, encoding=_py_charset)
            if self.trusted_auth:
                dpb.insert_tag(DPBItem.TRUSTED_AUTH)
            else:
                if self.user:
                    dpb.insert_string(DPBItem.USER_NAME, self.user, encoding=_py_charset)
                if self.password:
                    dpb.insert_string(DPBItem.PASSWORD, self.password, encoding=_py_charset)
            if self.auth_plugin_list is not None:
                dpb.insert_string(DPBItem.AUTH_PLUGIN_LIST, self.auth_plugin_list)
            if self.timeout is not None:
                dpb.insert_int(DPBItem.CONNECT_TIMEOUT, self.timeout)
            if self.dummy_packet_interval is not None:
                dpb.insert_int(DPBItem.DUMMY_PACKET_INTERVAL, self.dummy_packet_interval)
            if self.role:
                dpb.insert_string(DPBItem.SQL_ROLE_NAME, self.role, encoding=_py_charset)
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
            if self.session_time_zone is not None:
                dpb.insert_string(DPBItem.SESSION_TIME_ZONE, self.session_time_zone)
            if self.set_db_replica is not None:
                dpb.insert_int(DPBItem.SET_DB_REPLICA, self.set_db_replica)
            if self.set_bind is not None:
                dpb.insert_string(DPBItem.SET_BIND, self.set_bind)
            if self.decfloat_round is not None:
                dpb.insert_string(DPBItem.DECFLOAT_ROUND, self.decfloat_round.value)
            if self.decfloat_traps is not None:
                dpb.insert_string(DPBItem.DECFLOAT_TRAPS, ','.join(e.value for e in
                                                                   self.decfloat_traps))
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
    """Service Parameter Buffer.
    """
    def __init__(self, *, user: str = None, password: str = None, trusted_auth: bool = False,
                 config: str = None, auth_plugin_list: str = None, expected_db: str=None,
                 encoding: str='ascii', errors: str='strict', role: str=None):
        self.encoding: str = encoding
        self.errors: str = errors
        self.user: str = user
        self.password: str = password
        self.trusted_auth: bool = trusted_auth
        self.config: str = config
        self.auth_plugin_list: str = auth_plugin_list
        self.expected_db: str = expected_db
        self.role: str = role
    def clear(self) -> None:
        """Clear all information.
        """
        self.user = None
        self.password = None
        self.trusted_auth = False
        self.config = None
        self.expected_db = None
    def parse_buffer(self, buffer: bytes) -> None:
        """Load information from SPB_ATTACH.
        """
        self.clear()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_ATTACH, buffer) as spb:
            while not spb.is_eof():
                tag = spb.get_tag()
                if tag == SPBItem.CONFIG:
                    self.config = spb.get_string(encoding=self.encoding, errors=self.errors)
                elif tag == SPBItem.AUTH_PLUGIN_LIST:
                    self.auth_plugin_list = spb.get_string()
                elif tag == SPBItem.TRUSTED_AUTH:
                    self.trusted_auth = True
                elif tag == SPBItem.USER_NAME:
                    self.user = spb.get_string(encoding=self.encoding, errors=self.errors)
                elif tag == SPBItem.PASSWORD:
                    self.password = spb.get_string(encoding=self.encoding, errors=self.errors)
                elif tag == SPBItem.SQL_ROLE_NAME:
                    self.role = spb.get_string(encoding=self.encoding, errors=self.errors)
                elif tag == SPBItem.EXPECTED_DB:
                    self.expected_db = spb.get_string(encoding=self.encoding, errors=self.errors)
    def get_buffer(self) -> bytes:
        """Create SPB_ATTACH from stored information.
        """
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_ATTACH) as spb:
            if self.config is not None:
                spb.insert_string(SPBItem.CONFIG, self.config, encoding=self.encoding,
                                  errors=self.errors)
            if self.trusted_auth:
                spb.insert_tag(SPBItem.TRUSTED_AUTH)
            else:
                if self.user is not None:
                    spb.insert_string(SPBItem.USER_NAME, self.user, encoding=self.encoding,
                                      errors=self.errors)
                if self.password is not None:
                    spb.insert_string(SPBItem.PASSWORD, self.password,
                                      encoding=self.encoding, errors=self.errors)
            if self.role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, self.role, encoding=self.encoding,
                                  errors=self.errors)
            if self.auth_plugin_list is not None:
                spb.insert_string(SPBItem.AUTH_PLUGIN_LIST, self.auth_plugin_list)
            if self.expected_db is not None:
                spb.insert_string(SPBItem.EXPECTED_DB, self.expected_db,
                                  encoding=self.encoding, errors=self.errors)
            result = spb.get_buffer()
        return result


class Buffer(MemoryBuffer):
    """MemoryBuffer with extensions.
    """
    def __init__(self, init: Union[int, bytes], size: int = None, *,
                 factory: Type[BufferFactory]=BytesBufferFactory,
                 max_size: Union[int, Sentinel]=UNLIMITED, byteorder: ByteOrder=ByteOrder.LITTLE):
        super().__init__(init, size, factory=factory, eof_marker=isc_info_end,
                         max_size=max_size, byteorder=byteorder)
    def seek_last_data(self) -> int:
        """Set the position in buffer to first non-zero byte when searched from
        the end of buffer.
        """
        self.pos = self.last_data
    def get_tag(self) -> int:
        """Read 1 byte number (c_ubyte).
        """
        return self.read_byte()
    def rewind(self) -> None:
        """Set current position in buffer to beginning.
        """
        self.pos = 0
    def is_truncated(self) -> bool:
        """Return True when positioned on `isc_info_truncated` tag.
        """
        return safe_ord(self.raw[self.pos]) == isc_info_truncated

class CBuffer(Buffer):
    """ctypes MemoryBuffer with extensions.
    """
    def __init__(self, init: Union[int, bytes], size: int = None, *,
                 max_size: Union[int, Sentinel]=UNLIMITED, byteorder: ByteOrder=ByteOrder.LITTLE):
        super().__init__(init, size, factory=CTypesBufferFactory, max_size=max_size, byteorder=byteorder)

class EventBlock:
    """Used internally by `EventCollector`.
    """
    def __init__(self, queue, db_handle: a.FB_API_HANDLE, event_names: List[str]):
        self.__first = True
        def callback(result, length, updated):
            memmove(result, updated, length)
            self.__queue.put((_OP_RECORD_AND_REREGISTER, self))
            return 0

        self.__queue: PriorityQueue = weakref.proxy(queue)
        self._db_handle: a.FB_API_HANDLE = db_handle
        self._isc_status: a.ISC_STATUS_ARRAY = a.ISC_STATUS_ARRAY(0)
        self.event_names: List[str] = list(event_names)

        self.__results: a.RESULT_VECTOR = a.RESULT_VECTOR(0)
        self.__closed: bool = False
        self.__callback: a.ISC_EVENT_CALLBACK = a.ISC_EVENT_CALLBACK(callback)

        self.event_buf = pointer(a.ISC_UCHAR(0))
        self.result_buf = pointer(a.ISC_UCHAR(0))
        self.buf_length: int = 0
        self.event_id: a.ISC_LONG = a.ISC_LONG(0)

        self.buf_length = a.api.isc_event_block(pointer(self.event_buf),
                                                pointer(self.result_buf),
                                                *[x.encode() for x in event_names])
    def __del__(self):
        if not self.__closed:
            warn(f"EventBlock disposed without prior close()", ResourceWarning)
            self.close()
    def __lt__(self, other):
        return self.event_id.value < other.event_id.value
    def __wait_for_events(self) -> None:
        a.api.isc_que_events(self._isc_status, self._db_handle, self.event_id,
                             self.buf_length, self.event_buf,
                             self.__callback, self.result_buf)
        if a.db_api_error(self._isc_status):  # pragma: no cover
            self.close()
            raise a.exception_from_status(DatabaseError, self._isc_status,
                                          "Error while waiting for events.")
    def _begin(self) -> None:
        self.__wait_for_events()
    def count_and_reregister(self) -> Dict[str, int]:
        """Count event occurences and re-register interest in further notifications.
        """
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
    def close(self) -> None:
        """Close this block canceling managed events.
        """
        if not self.__closed:
            a.api.isc_cancel_events(self._isc_status, self._db_handle, self.event_id)
            self.__closed = True
            del self.__callback
            if a.db_api_error(self._isc_status):  # pragma: no cover
                raise a.exception_from_status(DatabaseError, self._isc_status,
                                              "Error while canceling events.")
    def is_closed(self) -> bool:
        """Returns True if event block is closed.
        """
        return self.__closed


class EventCollector:
    """Collects database event notifications.

    Notifications of events are not accumulated until `.begin()` method is called.

    From the moment the `.begin()` is called, notifications of any events that occur
    will accumulate asynchronously within the conduit’s internal queue until the collector
    is closed either explicitly (via the `.close()` method) or implicitly
    (via garbage collection).

    Note:

        `EventCollector` implements context manager protocol to call method `.begin()`
        and `.close()` automatically.

    Example::

       with connection.event_collector(['event_a', 'event_b']) as collector:
           events = collector.wait()
           process_events(events)

    Important:

       DO NOT create instances of this class directly! Use only
       `Connection.event_collector` to get EventCollector instances.
    """
    def __init__(self, db_handle: a.FB_API_HANDLE, event_names: Sequence[str]):
        self._db_handle: a.FB_API_HANDLE = db_handle
        self._isc_status: a.ISC_STATUS_ARRAY = a.ISC_STATUS_ARRAY(0)
        self.__event_names: List[str] = list(event_names)
        self.__events: Dict[str, int] = dict.fromkeys(self.__event_names, 0)
        self.__event_blocks: List[EventBlock] = []
        self.__closed: bool = False
        self.__queue: PriorityQueue = PriorityQueue()
        self.__events_ready: threading.Event = threading.Event()
        self.__blocks: List[List[str]] = [[x for x in y if x] for y in itertools.zip_longest(*[iter(event_names)]*15)]
        self.__initialized: bool = False
    def __del__(self):
        if not self.__closed:
            warn(f"EventCollector disposed without prior close()", ResourceWarning)
            self.close()
    def __enter__(self):
        self.begin()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    def begin(self) -> None:
        """Starts listening for events.

        Must be called directly or through context manager interface.
        """
        def event_process(queue: PriorityQueue):
            while True:
                operation, data = queue.get()
                if operation is _OP_RECORD_AND_REREGISTER:
                    events = data.count_and_reregister()
                    if events:
                        for key, value in events.items():
                            self.__events[key] += value
                        self.__events_ready.set()
                elif operation is _OP_DIE:
                    return

        self.__initialized = True
        self.__process_thread = threading.Thread(target=event_process, args=(self.__queue,))
        self.__process_thread.start()

        for block_events in self.__blocks:
            event_block = EventBlock(self.__queue, self._db_handle, block_events)
            self.__event_blocks.append(event_block)
            event_block._begin()
    def wait(self, timeout: Union[int, float]=None) -> Dict[str, int]:
        """Wait for events.

        Blocks the calling thread until at least one of the events occurs, or
        the specified timeout (if any) expires.

        Arguments:
            timeout: Number of seconds (use a float to indicate fractions of
                seconds). If not even one of the relevant events has
                occurred after timeout seconds, this method will unblock
                and return None. The default timeout is infinite.

        Returns:
            `None` if the wait timed out, otherwise a dictionary that maps
            `event_name -> event_occurrence_count`.

        Example::

           >>> collector = connection.event_collector(['event_a', 'event_b'])
           >>> collector.begin()
           >>> collector.wait()
           {
            'event_a': 1,
            'event_b': 0
           }

        In the example above `event_a` occurred once and `event_b` did not occur
        at all.

        Raises:
            InterfaceError: When collector does not listen for events.
        """
        if not self.__initialized:
            raise InterfaceError("Event collection not initialized (begin() not called).")
        if not self.__closed:
            self.__events_ready.wait(timeout)
            return self.__events.copy()
    def flush(self) -> None:
        """Clear any event notifications that have accumulated in the collector’s
        internal queue.
        """
        if not self.__closed:
            self.__events_ready.clear()
            self.__events = dict.fromkeys(self.__event_names, 0)
    def close(self) -> None:
        """Cancels the standing request for this collector to be notified of events.

        After this method has been called, this EventCollector instance is useless,
        and should be discarded.
        """
        if not self.__closed:
            self.__queue.put((_OP_DIE, self))
            self.__process_thread.join()
            for block in self.__event_blocks:
                block.close()
            self.__closed = True
    def is_closed(self) -> bool:
        """Returns True if collector is closed.
        """
        return self.__closed

class InfoProvider(ABC):
    """Abstract base class for embedded information providers.

    Attributes:
        response (CBuffer): Internal buffer for response packet acquired via Firebird API.
        request (Buffer): Internal buffer for information request packet needed by Firebird API.
    """
    def __init__(self, charset: str, buffer_size: int=256):
        self._charset: str = charset
        self.response: CBuffer = CBuffer(buffer_size)
        self.request: Buffer = Buffer(10)
        self._cache: Dict = {}
    def _raise_not_supported(self) -> None:
        raise NotSupportedError("Requested functionality is not supported by used Firebird version.")
    @abstractmethod
    def _close(self) -> None:
        """Close the information source.
        """
    @abstractmethod
    def _acquire(self, request: bytes) -> None:
        """Acquire information specified by parameter. Information must be stored in
        `response` buffer.

        Arguments:
            request: Data specifying the required information.
        """
    def _get_data(self, request: bytes, max_size: int=SHRT_MAX) -> None:
        """Helper function that aquires information specified by parameter into internal
        `response` buffer. If information source couldn't store all required data because
        the buffer is too small, this function tries to `.acquire()` the information again
        with buffer of doubled size.

        Arguments:
            request: Data specifying the required information.
            max_size: Maximum response size.

        Raises:
            InterfaceError: If information cannot be successfuly stored into buffer
                of `max_size`, or response is ivalid.
        """
        while True:
            self._acquire(request)
            if self.response.is_truncated():
                if (buf_size := len(self.response.raw)) < max_size:
                    buf_size = min(buf_size * 2, max_size)
                    self.response.resize(buf_size)
                    continue
                else:  # pragma: no cover
                    raise InterfaceError("Response too large")
            else:
                break
        self.response.seek_last_data()
        if not self.response.is_eof():  # pragma: no cover
            raise InterfaceError("Invalid response format")
        self.response.rewind()

class EngineVersionProvider(InfoProvider):
    """Engine version provider for internal use by driver.
    """
    def __init__(self, charset: str):
        super().__init__(charset)
        self.con = None
    def _close(self) -> None:
        pass
    def _acquire(self, request: bytes) -> None:
        """Acquires information from associated attachment. Information is stored in native
        format in `response` buffer.

        Arguments:
            request: Data specifying the required information.
        """
        if isinstance(self.con(), Connection):
            self.con()._att.get_info(request, self.response.raw)
        else:
            self.con()._svc.query(None, request, self.response.raw)
    def get_server_version(self, con: Union[Connection, Server]) -> str:
        self.con = con
        info_code = DbInfoCode.FIREBIRD_VERSION if isinstance(con(), Connection) \
            else SrvInfoCode.SERVER_VERSION
        self._get_data(bytes([info_code]))
        tag = self.response.get_tag()
        if (tag != info_code.value):
            if tag == isc_info_error:  # pragma: no cover
                raise InterfaceError("An error response was received")
            else:  # pragma: no cover
                raise InterfaceError("Result code does not match request code")
        if isinstance(con(), Connection):
            self.response.read_byte()  # Cluster length
            self.response.read_short()  # number of strings
        verstr: str = self.response.read_pascal_string()
        x = verstr.split()
        if x[0].find('V') > 0:
            (x, result) = x[0].split('V')
        elif x[0].find('T') > 0:  # pragma: no cover
            (x, result) = x[0].split('T')
        else: # pragma: no cover
            # Unknown version
            result = '0.0.0.0'
        self.response.rewind()
        self.con = None
        return result
    def get_engine_version(self, con: Union[Connection, Server]) -> float:
        x = self.get_server_version(con).split('.')
        return float(f'{x[0]}.{x[1]}')

_engine_version_provider: EngineVersionProvider = EngineVersionProvider('utf8')

class DatabaseInfoProvider3(InfoProvider):
    """Provides access to information about attached database [Firebird 3+].

    Important:
       Do NOT create instances of this class directly! Use `Connection.info` property to
       access the instance already bound to attached database.

    """
    def __init__(self, connection: Connection):
        super().__init__(connection._encoding)
        self._con: Connection = weakref.ref(connection)
        self._handlers: Dict[DbInfoCode, Callable] = \
            {DbInfoCode.BASE_LEVEL: self.response.get_tag,
             DbInfoCode.DB_ID: self.__db_id,
             DbInfoCode.IMPLEMENTATION: self.__implementation,
             DbInfoCode.IMPLEMENTATION_OLD: self.__implementation_old,
             DbInfoCode.VERSION: self._info_string,
             DbInfoCode.FIREBIRD_VERSION: self._info_string,
             DbInfoCode.CRYPT_KEY: self._info_string,
             DbInfoCode.USER_NAMES: self.__user_names,
             DbInfoCode.ACTIVE_TRANSACTIONS: self.__tra_active,
             DbInfoCode.LIMBO: self.__tra_limbo,
             DbInfoCode.ALLOCATION: self.response.read_sized_int,
             DbInfoCode.NO_RESERVE: self.response.read_sized_int,
             DbInfoCode.DB_SQL_DIALECT: self.response.read_sized_int,
             DbInfoCode.ODS_MINOR_VERSION: self.response.read_sized_int,
             DbInfoCode.ODS_VERSION: self.response.read_sized_int,
             DbInfoCode.PAGE_SIZE: self.response.read_sized_int,
             DbInfoCode.CURRENT_MEMORY: self.response.read_sized_int,
             DbInfoCode.FORCED_WRITES: self.response.read_sized_int,
             DbInfoCode.MAX_MEMORY: self.response.read_sized_int,
             DbInfoCode.NUM_BUFFERS: self.response.read_sized_int,
             DbInfoCode.SWEEP_INTERVAL: self.response.read_sized_int,
             DbInfoCode.ATTACHMENT_ID: self.response.read_sized_int,
             DbInfoCode.FETCHES: self.response.read_sized_int,
             DbInfoCode.MARKS: self.response.read_sized_int,
             DbInfoCode.READS: self.response.read_sized_int,
             DbInfoCode.WRITES: self.response.read_sized_int,
             DbInfoCode.SET_PAGE_BUFFERS: self.response.read_sized_int,
             DbInfoCode.DB_READ_ONLY: self.response.read_sized_int,
             DbInfoCode.DB_SIZE_IN_PAGES: self.response.read_sized_int,
             DbInfoCode.PAGE_ERRORS: self.response.read_sized_int,
             DbInfoCode.RECORD_ERRORS: self.response.read_sized_int,
             DbInfoCode.BPAGE_ERRORS: self.response.read_sized_int,
             DbInfoCode.DPAGE_ERRORS: self.response.read_sized_int,
             DbInfoCode.IPAGE_ERRORS: self.response.read_sized_int,
             DbInfoCode.PPAGE_ERRORS: self.response.read_sized_int,
             DbInfoCode.TPAGE_ERRORS: self.response.read_sized_int,
             DbInfoCode.ATT_CHARSET: self.response.read_sized_int,
             DbInfoCode.OLDEST_TRANSACTION: self.response.read_sized_int,
             DbInfoCode.OLDEST_ACTIVE: self.response.read_sized_int,
             DbInfoCode.OLDEST_SNAPSHOT: self.response.read_sized_int,
             DbInfoCode.NEXT_TRANSACTION: self.response.read_sized_int,
             DbInfoCode.ACTIVE_TRAN_COUNT: self.response.read_sized_int,
             DbInfoCode.DB_CLASS: self.response.read_sized_int,
             DbInfoCode.DB_PROVIDER: self.response.read_sized_int,
             DbInfoCode.PAGES_USED: self.response.read_sized_int,
             DbInfoCode.PAGES_FREE: self.response.read_sized_int,
             DbInfoCode.CRYPT_KEY: self._info_string,
             DbInfoCode.CRYPT_STATE: self.__crypt_state,
             DbInfoCode.CONN_FLAGS: self.__con_state,
             DbInfoCode.BACKOUT_COUNT: self.__tbl_perf_count,
             DbInfoCode.DELETE_COUNT: self.__tbl_perf_count,
             DbInfoCode.EXPUNGE_COUNT: self.__tbl_perf_count,
             DbInfoCode.INSERT_COUNT: self.__tbl_perf_count,
             DbInfoCode.PURGE_COUNT: self.__tbl_perf_count,
             DbInfoCode.READ_IDX_COUNT: self.__tbl_perf_count,
             DbInfoCode.READ_SEQ_COUNT: self.__tbl_perf_count,
             DbInfoCode.UPDATE_COUNT: self.__tbl_perf_count,
             DbInfoCode.CREATION_DATE: self.__creation_date,
             DbInfoCode.PAGE_CONTENTS: self.response.read_bytes,
             }
        # Page size
        self.__page_size = self.get_info(DbInfoCode.PAGE_SIZE)  # prefetch it
        # Get Firebird engine version
        self.__version = _engine_version_provider.get_server_version(self._con)
        x = self.__version.split('.')
        self.__engine_version = float(f'{x[0]}.{x[1]}')
    def __db_id(self) -> List:
        result = []
        self.response.read_short()  # Cluster length
        count = self.response.read_byte()
        while count > 0:
            result.append(self.response.read_pascal_string(encoding=self._charset))
            count -= 1
        return result
    def __implementation(self) -> Tuple[ImpCPU, ImpOS, ImpCompiler, ImpFlags]:
        self.response.read_short()  # Cluster length
        cpu_id = ImpCPU(self.response.read_byte())
        os_id = ImpOS(self.response.read_byte())
        compiler_id = ImpCompiler(self.response.read_byte())
        flags = ImpFlags(self.response.read_byte())
        return (cpu_id, os_id, compiler_id, flags)
    def __implementation_old(self) -> Tuple[int, int]:
        self.response.read_short()  # Cluster length
        impl_number = self.response.read_byte()
        class_number = self.response.read_byte()
        return (impl_number, class_number)
    def _info_string(self) -> str:
        self.response.read_byte()  # Cluster length
        self.response.read_short()  # number of strings
        return self.response.read_pascal_string()
    def __user_names(self) -> Dict[str, str]:
        self.response.rewind() # necessary to process names separated by info tag
        usernames = []
        while not self.response.is_eof():
            self.response.get_tag() # DbInfoCode.USER_NAMES
            self.response.read_short()  # cluster length
            usernames.append(self.response.read_pascal_string(encoding=self._charset))
        # The client-exposed return value is a dictionary mapping
        # username -> number of connections by that user.
        result = {}
        for name in usernames:
            result[name] = result.get(name, 0) + 1
        return result
    def __tra_active(self) -> List:
        result = []
        while not self.response.is_eof():
            self.response.get_tag()  # DbInfoCode.ACTIVE_TRANSACTIONS
            tid_size = self.response.read_short()
            if tid_size == 4:
                tra_id = self.response.read_int()
            elif tid_size == 8:
                tra_id = self.response.read_bigint()
            else:  # pragma: no cover
                raise InterfaceError(f"Wrong transaction ID size {tid_size}")
            result.append(tra_id)
        return result
    def __tra_limbo(self) -> List:
        result = []
        self.response.read_short()  # Total data length
        while not self.response.is_eof():
            self.response.get_tag()
            tid_size = self.response.read_short()
            if tid_size == 4:
                tra_id = self.response.read_int()
            elif tid_size == 8:
                tra_id = self.response.read_bigint()
            else:  # pragma: no cover
                raise InterfaceError(f"Wrong transaction ID size {tid_size}")
            result.append(tra_id)
        return result
    def __crypt_state(self) -> EncryptionFlag:
        return EncryptionFlag(self.response.read_sized_int())
    def __con_state(self) -> ConnectionFlag:
        return ConnectionFlag(self.response.read_sized_int())
    def __tbl_perf_count(self) -> Dict[int, int]:
        result = {}
        clen = self.response.read_short()  # Cluster length
        while clen > 0:
            relation_id = self.response.read_short()
            result[relation_id] = self.response.read_int()
            clen -= 6
        return result
    def __creation_date(self) -> datetime.datetime:
        value = self.response.read_bytes()
        return datetime.datetime.combine(_util.decode_date(value[:4]),
                                         _util.decode_time(value[4:]))
    def _close(self) -> None:
        """Drops the association with attached database.
        """
        self._con = None
    def _acquire(self, request: bytes) -> None:
        """Acquires information from associated attachment. Information is stored in native
        format in `response` buffer.

        Arguments:
            request: Data specifying the required information.
        """
        self._con()._att.get_info(request, self.response.raw)
    def get_info(self, info_code: DbInfoCode, page_number: int=None) -> Any:
        """Returns requested information from associated attachment.

        Arguments:
            info_code: A code specifying the required information.
            page_number: A page number for `DbInfoCode.PAGE_CONTENTS` request. Ignored for other requests.

        Returns:
            The data type of returned value depends on information required.
        """
        if info_code in self._cache:
            return self._cache[info_code]
        if info_code not in self._handlers:
            raise NotSupportedError(f"Info code {info_code} not supported by engine version {self.__engine_version}")
        self.response.clear()
        request = bytes([info_code])
        if info_code == DbInfoCode.PAGE_CONTENTS:
            request += (4).to_bytes(2, 'little')
            request += page_number.to_bytes(4, 'little')
            if len(self.response.raw) < self.page_size + 10:
                self.response.resize(self.page_size + 10)
        self._get_data(request)
        tag = self.response.get_tag()
        if (request[0] != tag):
            if info_code == DbInfoCode.ACTIVE_TRANSACTIONS:
                # isc_info_active_transactions with no active transactions returns empty buffer
                # and does not follow this rule
                pass
            elif tag == isc_info_error:  # pragma: no cover
                raise InterfaceError("An error response was received")
            else:  # pragma: no cover
                raise InterfaceError("Result code does not match request code")
        if info_code == DbInfoCode.ACTIVE_TRANSACTIONS:
            # we'll rewind back, otherwise it will break the repeating cluster processing
            self.response.rewind()
        #
        result = self._handlers[info_code]()
        # cache
        if info_code in (DbInfoCode.CREATION_DATE, DbInfoCode.DB_CLASS, DbInfoCode.DB_PROVIDER,
                         DbInfoCode.DB_SQL_DIALECT, DbInfoCode.ODS_MINOR_VERSION,
                         DbInfoCode.ODS_VERSION, DbInfoCode.PAGE_SIZE, DbInfoCode.VERSION,
                         DbInfoCode.FIREBIRD_VERSION, DbInfoCode.IMPLEMENTATION_OLD,
                         DbInfoCode.IMPLEMENTATION, DbInfoCode.DB_ID, DbInfoCode.BASE_LEVEL,
                         DbInfoCode.ATTACHMENT_ID):
            self._cache[info_code] = result
        return result
    # Functions
    def get_page_content(self, page_number: int) -> bytes:
        """Returns content of single database page.

        Arguments:
           page_number: Sequence number of database page to be fetched from server.
        """
        return self.get_info(DbInfoCode.PAGE_CONTENTS, page_number)
    def get_active_transaction_ids(self) -> List[int]:
        """Returns list of IDs of active transactions.
        """
        return self.get_info(DbInfoCode.ACTIVE_TRANSACTIONS)
    def get_active_transaction_count(self) -> int:
        """Returns number of active transactions.
        """
        return self.get_info(DbInfoCode.ACTIVE_TRAN_COUNT)
    def get_table_access_stats(self) -> List[TableAccessStats]:
        """Returns actual table access statistics.
        """
        tables = {}
        info_codes = [DbInfoCode.READ_SEQ_COUNT, DbInfoCode.READ_IDX_COUNT,
                      DbInfoCode.INSERT_COUNT, DbInfoCode.UPDATE_COUNT,
                      DbInfoCode.DELETE_COUNT, DbInfoCode.BACKOUT_COUNT,
                      DbInfoCode.PURGE_COUNT, DbInfoCode.EXPUNGE_COUNT]
        #stats = self.get_info(info_codes)
        for info_code in info_codes:
            stat: Mapping = self.get_info(info_code)
            for table, count in stat.items():
                tables.setdefault(table, dict.fromkeys(info_codes))[info_code] = count
        return [TableAccessStats(table, **{_i2name[code]:count
                                           for code, count in tables[table].items()})
                for table in tables]
    def is_compressed(self) -> bool:
        """Returns True if connection to the server uses data compression.
        """
        return ConnectionFlag.COMPRESSED in ConnectionFlag(self.get_info(DbInfoCode.CONN_FLAGS))
    def is_encrypted(self) -> bool:
        """Returns True if connection to the server uses data encryption.
        """
        return ConnectionFlag.ENCRYPTED in ConnectionFlag(self.get_info(DbInfoCode.CONN_FLAGS))
    # Properties
    @property
    def id(self) -> int:
        """Attachment ID.
        """
        return self.get_info(DbInfoCode.ATTACHMENT_ID)
    @property
    def charset(self) -> str:
        """Database character set.
        """
        if -1 not in self._cache:
            with transaction(self._con()._tra_qry, bypass=True):
                with self._con()._ic.execute("SELECT RDB$CHARACTER_SET_NAME FROM RDB$DATABASE"):
                    self._cache[-1] = self._con()._ic.fetchone()[0].strip()
        return self._cache[-1]
    @property
    def page_size(self) -> int:
        """Page size (in bytes).
        """
        return self.__page_size
    @property
    def sql_dialect(self) -> int:
        """SQL dialect used by connected database.
        """
        return self.get_info(DbInfoCode.DB_SQL_DIALECT)
    @property
    def name(self) -> str:
        """Database name (filename or alias).
        """
        return self.get_info(DbInfoCode.DB_ID)[0]
    @property
    def site(self) -> str:
        """Database site name.
        """
        return self.get_info(DbInfoCode.DB_ID)[1]
    @property
    def server_version(self) -> str:
        """Firebird server version (compatible with InterBase version).
        """
        return self.get_info(DbInfoCode.VERSION)
    @property
    def firebird_version(self) -> str:
        """Firebird server version.
        """
        return self.get_info(DbInfoCode.FIREBIRD_VERSION)
    @property
    def implementation(self) -> Implementation:
        """Implementation (old format).
        """
        return Implementation(self.get_info(DbInfoCode.IMPLEMENTATION_OLD)[0])
    @property
    def provider(self) -> DbProvider:
        """Database Provider.
        """
        return DbProvider(self.get_info(DbInfoCode.DB_PROVIDER))
    @property
    def db_class(self) -> DbClass:
        """Database Class.
        """
        return DbClass(self.get_info(DbInfoCode.DB_CLASS))
    @property
    def creation_date(self) -> datetime.date:
        """Date when database was created.
        """
        return self.get_info(DbInfoCode.CREATION_DATE)
    @property
    def ods(self) -> float:
        """Database On-Disk Structure version (<major>.<minor>).
        """
        return float(f'{self.ods_version}.{self.ods_minor_version}')
    @property
    def ods_version(self) -> int:
        """Database On-Disk Structure MAJOR version.
        """
        return self.get_info(DbInfoCode.ODS_VERSION)
    @property
    def ods_minor_version(self) -> int:
        """Database On-Disk Structure MINOR version.
        """
        return self.get_info(DbInfoCode.ODS_MINOR_VERSION)
    @property
    def page_cache_size(self) -> int:
        """Size of page cache used by connection.
        """
        return self.get_info(DbInfoCode.NUM_BUFFERS)
    @property
    def pages_allocated(self) -> int:
        """Number of pages allocated for database.
        """
        return self.get_info(DbInfoCode.ALLOCATION)
    @property
    def size_in_pages(self) -> int:
        """Database size in pages.
        """
        return self.get_info(DbInfoCode.DB_SIZE_IN_PAGES)
    @property
    def pages_used(self) -> int:
        """Number of database pages in active use.
        """
        return self.get_info(DbInfoCode.PAGES_USED)
    @property
    def pages_free(self) -> int:
        """Number of free allocated pages in database.
        """
        return self.get_info(DbInfoCode.PAGES_FREE)
    @property
    def sweep_interval(self) -> int:
        """Sweep interval.
        """
        return self.get_info(DbInfoCode.SWEEP_INTERVAL)
    @property
    def space_reservation(self) -> DbSpaceReservation:
        """Data page space usage (USE_FULL or RESERVE).
        """
        return DbSpaceReservation.USE_FULL if self.get_info(DbInfoCode.NO_RESERVE) else DbSpaceReservation.RESERVE
    @property
    def write_mode(self) -> DbWriteMode:
        """Database write mode (SYNC or ASYNC).
        """
        return DbWriteMode.SYNC if self.get_info(DbInfoCode.FORCED_WRITES) else DbWriteMode.ASYNC
    @property
    def access_mode(self) -> DbAccessMode:
        """Database access mode (READ_ONLY or READ_WRITE).
        """
        return DbAccessMode.READ_ONLY if self.get_info(DbInfoCode.DB_READ_ONLY) else DbAccessMode.READ_WRITE
    @property
    def reads(self) -> int:
        """Current I/O statistics - Reads from disk to page cache.
        """
        return self.get_info(DbInfoCode.READS)
    @property
    def fetches(self) -> int:
        """Current I/O statistics - Fetches from page cache.
        """
        return self.get_info(DbInfoCode.FETCHES)
    @property
    def cache_hit_ratio(self) -> float:
        """Cache hit ratio = 1 - (reads / fetches).
        """
        return (1 - (self.reads / self.fetches)) if self.fetches else 1.0
    @property
    def writes(self) -> int:
        """Current I/O statistics - Writes from page cache to disk.
        """
        return self.get_info(DbInfoCode.WRITES)
    @property
    def marks(self) -> int:
        """Current I/O statistics - Writes to page in cache.
        """
        return self.get_info(DbInfoCode.MARKS)
    @property
    def current_memory(self) -> int:
        """Total amount of memory curretly used by database engine.
        """
        return self.get_info(DbInfoCode.CURRENT_MEMORY)
    @property
    def max_memory(self) -> int:
        """Max. total amount of memory so far used by database engine.
        """
        return self.get_info(DbInfoCode.MAX_MEMORY)
    @property
    def oit(self) -> int:
        """ID of Oldest Interesting Transaction.
        """
        return self.get_info(DbInfoCode.OLDEST_TRANSACTION)
    @property
    def oat(self) -> int:
        """ID of Oldest Active Transaction.
        """
        return self.get_info(DbInfoCode.OLDEST_ACTIVE)
    @property
    def ost(self) -> int:
        """ID of Oldest Snapshot Transaction.
        """
        return self.get_info(DbInfoCode.OLDEST_SNAPSHOT)
    @property
    def next_transaction(self) -> int:
        """ID for next transaction.
        """
        return self.get_info(DbInfoCode.NEXT_TRANSACTION)
    @property
    def version(self) -> str:
        """Firebird version as SEMVER string.
        """
        return self.__version
    @property
    def engine_version(self) -> float:
        """Firebird version as <major>.<minor> float number.
        """
        return self.__engine_version

class DatabaseInfoProvider(DatabaseInfoProvider3):
    """Provides access to information about attached database [Firebird 4+].

    Important:
       Do NOT create instances of this class directly! Use `Connection.info` property to
       access the instance already bound to attached database.
    """
    def __init__(self, connection: Connection):
        super().__init__(connection)
        self._handlers.update({
            DbInfoCode.SES_IDLE_TIMEOUT_DB: self.response.read_sized_int,
            DbInfoCode.SES_IDLE_TIMEOUT_ATT: self.response.read_sized_int,
            DbInfoCode.SES_IDLE_TIMEOUT_RUN: self.response.read_sized_int,
            DbInfoCode.STMT_TIMEOUT_DB: self.response.read_sized_int,
            DbInfoCode.STMT_TIMEOUT_ATT: self.response.read_sized_int,
            DbInfoCode.PROTOCOL_VERSION: self.response.read_sized_int,
            DbInfoCode.CRYPT_PLUGIN: self._info_string,
            DbInfoCode.CREATION_TIMESTAMP_TZ: self.__creation_tstz,
            DbInfoCode.WIRE_CRYPT: self._info_string,
            DbInfoCode.FEATURES: self.__features,
            DbInfoCode.NEXT_ATTACHMENT: self.response.read_sized_int,
            DbInfoCode.NEXT_STATEMENT: self.response.read_sized_int,
            DbInfoCode.DB_GUID: self._info_string,
            DbInfoCode.DB_FILE_ID: self._info_string,
            DbInfoCode.REPLICA_MODE: self.__replica_mode,
        })
    def __creation_tstz(self) -> datetime.datetime:
        value = self.response.read_bytes()
        return _util.decode_timestamp_tz(value)
    def __features(self) -> List[Features]:
        value = self.response.read_bytes()
        return [Features(x) for x in value]
    def __replica_mode(self) -> ReplicaMode:
        return ReplicaMode(self.response.read_sized_int())
    @property
    def idle_timeout(self) -> int:
        """Attachment idle timeout.
        """
        return self._con()._att.get_idle_timeout()
    @idle_timeout.setter
    def __idle_timeout(self, value: int) -> None:
        self._con()._att.set_idle_timeout(value)
    @property
    def statement_timeout(self) -> int:
        """Statement timeout.
        """
        return self._con()._att.get_statement_timeout()
    @statement_timeout.setter
    def __statement_timeout(self, value: int) -> None:
        self._con()._att.set_statement_timeout(value)

class Connection(LoggingIdMixin):
    """Connection to the database.

    Note:
        Implements context manager protocol to call `.close()` automatically.

    Attributes:
        default_tpb (bytes): Default Transaction parameter buffer for started transactions.
            Default is set to SNAPSHOT isolation with WAIT lock resolution (infinite lock timeout).
    """
    # PEP 249 (Python DB API 2.0) extension
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
    def __init__(self, att: iAttachment, dsn: str, dpb: bytes=None, sql_dialect: int=3,
                 charset: str=None) -> None:
        self._att: iAttachment = att
        self.__str: str = f'Connection[{self._get_db_handle()}]'
        self.__charset: str = charset
        self.__precision_cache = {}
        self.__sqlsubtype_cache = {}
        self.__ecollectors: List[EventCollector] = []
        self.__dsn: str = dsn
        self.__sql_dialect: int = sql_dialect
        self._encoding: str = CHARSET_MAP.get(charset, 'ascii')
        self._att.encoding = self._encoding
        self._dpb: bytes = dpb
        #: Default TPB for newly created transaction managers
        self.default_tpb: bytes = tpb(Isolation.SNAPSHOT)
        self._transactions: List[TransactionManager] = []
        self._statements: List[Statement] = []
        #
        self.__ev: float = None
        self.__info: DatabaseInfoProvider = None
        self._tra_main: TransactionManager = TransactionManager(self, self.default_tpb)
        self._tra_main._logging_id_ = 'Transaction.Main'
        self._tra_qry: TransactionManager = TransactionManager(self,
                                                               tpb(Isolation.READ_COMMITTED_RECORD_VERSION,
                                                                   access_mode=TraAccessMode.READ))
        self._tra_qry._logging_id_ = 'Transaction.Query'
        # Cursor for internal use
        self._ic = self.query_transaction.cursor()
        self._ic._connection = weakref.proxy(self, self._ic._dead_con)
        self._ic._logging_id_ = 'Cursor.internal'
        # firebird.lib extensions
        self.__schema = None
        self.__monitor = None
        self.__FIREBIRD_LIB__ = None
    def __del__(self):
        if not self.is_closed():
            warn(f"Connection '{self.logging_id}' disposed without prior close()", ResourceWarning)
            self._close()
            self._close_internals()
            self._att.detach()
    def __enter__(self) -> Connection:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __repr__(self):
        return self.__str
    def _get_db_handle(self) -> int:
        isc_status = a.ISC_STATUS_ARRAY()
        db_handle = a.FB_API_HANDLE(0)
        api = a.get_api()
        api.fb_get_database_handle(isc_status, db_handle, self._att)
        if a.db_api_error(isc_status):  # pragma: no cover
            raise a.exception_from_status(DatabaseError,
                                          isc_status,
                                          "Error in Cursor._unpack_output:fb_get_database_handle()")
        return db_handle.value
    def __stmt_deleted(self, stmt) -> None:
        self._statements.remove(stmt)
    def _close(self) -> None:
        if self.__schema is not None:
            self.__schema._set_internal(False)
            self.__schema.close()
        if self.__monitor is not None:
            self.__monitor._set_internal(False)
            self.__monitor.close()
        self._ic.close()
        for collector in self.__ecollectors:
            collector.close()
        self.main_transaction._finish(DefaultAction.ROLLBACK)
        self.query_transaction._finish(DefaultAction.ROLLBACK)
        while self._transactions:
            transaction = self._transactions.pop(0)
            transaction.default_action = DefaultAction.ROLLBACK  # Required by Python DB API 2.0
            transaction.close()
        while self._statements:
            s = self._statements.pop()()
            if s is not None:
                s.free()
    def _close_internals(self) -> None:
        self.main_transaction.close()
        self.query_transaction.close()
        if self.__info is not None:
            self.__info._close()
    def _engine_version(self) -> float:
        if self.__ev is None:
            self.__ev = _engine_version_provider.get_engine_version(weakref.ref(self))
        return self.__ev
    def _prepare(self, sql: str, transaction: TransactionManager) -> Statement:
        if _commit := not transaction.is_active():
            transaction.begin()
        stmt = self._att.prepare(transaction._tra, sql, self.__sql_dialect)
        result = Statement(self, stmt, sql, self.__sql_dialect)
        self._statements.append(weakref.ref(result, self.__stmt_deleted))
        if _commit:
            transaction.commit()
        return result
    def _determine_field_precision(self, meta: ItemMetadata) -> int:
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
        with transaction(self._tra_qry, bypass=True):
            with self._ic.execute("SELECT FIELD_SPEC.RDB$FIELD_PRECISION"
                                   " FROM RDB$FIELDS FIELD_SPEC,"
                                   " RDB$RELATION_FIELDS REL_FIELDS"
                                   " WHERE"
                                   " FIELD_SPEC.RDB$FIELD_NAME ="
                                   " REL_FIELDS.RDB$FIELD_SOURCE"
                                   " AND REL_FIELDS.RDB$RELATION_NAME = ?"
                                   " AND REL_FIELDS.RDB$FIELD_NAME = ?",
                                   (meta.relation, meta.field)):
                result = self._ic.fetchone()
            if result is None:
                # Next, try stored procedure output parameter
                with self._ic.execute("SELECT FIELD_SPEC.RDB$FIELD_PRECISION"
                                       " FROM RDB$FIELDS FIELD_SPEC,"
                                       " RDB$PROCEDURE_PARAMETERS REL_FIELDS"
                                       " WHERE"
                                       " FIELD_SPEC.RDB$FIELD_NAME ="
                                       " REL_FIELDS.RDB$FIELD_SOURCE"
                                       " AND RDB$PROCEDURE_NAME = ?"
                                       " AND RDB$PARAMETER_NAME = ?"
                                       " AND RDB$PARAMETER_TYPE = 1",
                                       (meta.relation, meta.field)):
                    result = self._ic.fetchone()
            if result:
                self.__precision_cache[(meta.relation, meta.field)] = result[0]
                return result[0]
        # We ran out of options
        return 0
    def _get_array_sqlsubtype(self, relation: bytes, column: bytes) -> Optional[int]:
        subtype = self.__sqlsubtype_cache.get((relation, column))
        if subtype is not None:
            return subtype
        with transaction(self._tra_qry, bypass=True):
            with self._ic.execute("SELECT FIELD_SPEC.RDB$FIELD_SUB_TYPE"
                                   " FROM RDB$FIELDS FIELD_SPEC, RDB$RELATION_FIELDS REL_FIELDS"
                                   " WHERE"
                                   " FIELD_SPEC.RDB$FIELD_NAME = REL_FIELDS.RDB$FIELD_SOURCE"
                                   " AND REL_FIELDS.RDB$RELATION_NAME = ?"
                                   " AND REL_FIELDS.RDB$FIELD_NAME = ?",
                                   (relation, column)):
                result = self._ic.fetchone()
        if result:
            self.__sqlsubtype_cache[(relation, column)] = result[0]
            return result[0]
    def drop_database(self) -> None:
        """Drops the connected database.

        Note:

            Closes all event collectors, transaction managers (with rollback) and statements
            associated with this connection before attempt to drop the database.

        Hooks:
            Event `.ConnectionHook.DROPPED`: Executed after database is sucessfuly dropped.
            Hook must have signature::

                hook_func(connection: Connection) -> None

            Any value returned by hook is ignored.
        """
        self._close()
        self._close_internals()
        try:
            self._att.drop_database()
        finally:
            self._att = None
            for hook in get_callbacks(ConnectionHook.DROPPED, self):
                hook(self)
    def execute_immediate(self, sql: str) -> None:
        """Executes SQL statement.

        Important:

            The statement MUST NOT return any result. The statement is executed in the
            context of `.main_transaction`.

        Arguments:
           sql: SQL statement to be executed.
        """
        assert self._att is not None
        self.main_transaction.execute_immediate(sql)
    def event_collector(self, event_names: Sequence[str]) -> EventCollector:
        """Create new `EventCollector` instance for this connection.

        Arguments:
            event_names: Sequence of database event names to whom the collector should be subscribed.
        """
        isc_status = a.ISC_STATUS_ARRAY()
        db_handle = a.FB_API_HANDLE(0)
        a.api.fb_get_database_handle(isc_status, db_handle, self._att)
        if a.db_api_error(isc_status):  # pragma: no cover
            raise a.exception_from_status(DatabaseError,
                                          isc_status,
                                          "Error in Connection.get_events:fb_get_database_handle()")
        conduit = EventCollector(db_handle, event_names)
        self.__ecollectors.append(conduit)
        return conduit
    def close(self) -> None:
        """Close the connection and release all associated resources.

        Closes all event collectors, transaction managers (with rollback) and statements
        associated with this connection before attempt (see Hooks) to close the
        connection itself.

        Hooks:
            Event `.ConnectionHook.DETACH_REQUEST`: Executed before connection
            is closed. Hook must have signature::

                hook_func(connection: Connection) -> bool

            .. note::

               If any hook function returns True, connection is NOT closed.

            Event `.ConnectionHook.CLOSED`: Executed after connection is closed.
            Hook must have signature::

                hook_func(connection: Connection) -> None

            Any value returned by hook is ignored.

        Important:
            Closed connection SHALL NOT be used anymore.
        """
        if not self.is_closed():
            retain = False
            try:
                self._close()
            except DatabaseError:
                self._att = None
                raise
            for hook in get_callbacks(ConnectionHook.DETACH_REQUEST, self):
                ret = hook(self)
                if ret and not retain:
                    retain = True
            #
            if not retain:
                try:
                    self._close_internals()
                    self._att.detach()
                finally:
                    self._att = None
                    for hook in get_callbacks(ConnectionHook.CLOSED, self):
                        hook(self)
    def transaction_manager(self, default_tpb: bytes=None,
                            default_action: DefaultAction=DefaultAction.COMMIT) -> TransactionManager:
        """Create new `TransactionManager` instance for this connection.

        Arguments:
            default_tpb: Default Transaction parameter buffer.
            default_action: Default action to be performed on implicit transaction end.
        """
        assert self._att is not None
        transaction = TransactionManager(self, default_tpb if default_tpb else self.default_tpb,
                                         default_action)
        self._transactions.append(transaction)
        return transaction
    def begin(self, tpb: bytes=None) -> None:
        """Starts new transaction managed by `.main_transaction`.

        Arguments:
            tpb: Transaction parameter buffer with transaction parameters. If not specified,
                 the `.default_tpb` is used.
        """
        assert self._att is not None
        self.main_transaction.begin(tpb)
    def savepoint(self, name: str) -> None:
        """Creates a new savepoint for transaction managed by `.main_transaction`.

        Arguments:
            name: Name for the savepoint
        """
        assert self._att is not None
        return self.main_transaction.savepoint(name)
    def commit(self, *, retaining: bool=False) -> None:
        """Commits the transaction managed by `.main_transaction`.

        Arguments:
            retaining: When True, the transaction context is retained after commit.
        """
        assert self._att is not None
        self.main_transaction.commit(retaining=retaining)
    def rollback(self, *, retaining: bool=False, savepoint: str=None) -> None:
        """Rolls back the transaction managed by `.main_transaction`.

        Arguments:
            retaining: When True, the transaction context is retained after rollback.
            savepoint: When specified, the transaction is rolled back to savepoint with given name.
        """
        assert self._att is not None
        self.main_transaction.rollback(retaining=retaining, savepoint=savepoint)
    def cursor(self) -> Cursor:
        """Returns new `Cursor` instance associated with `.main_transaction`.
        """
        assert self._att is not None
        return self.main_transaction.cursor()
    def ping(self) -> None:
        """Checks connection status. If test fails the only operation possible
        with connection is to close it.

        Raises:
          DatabaseError: When connection is dead.
        """
        assert self._att is not None
        self._att.ping()
    def is_active(self) -> bool:
        """Returns True if `.main_transaction` has active transaction.
        """
        return self._tra_main.is_active()
    def is_closed(self) -> bool:
        """Returns True if connection to the database is closed.

        Important:
            Closed connection SHALL NOT be used anymore.
        """
        return self._att is None
    @property
    def dsn(self) -> str:
        """Connection string.
        """
        return self.__dsn
    @property
    def info(self) -> Union[DatabaseInfoProvider3, DatabaseInfoProvider]:
        """Access to various information about attached database.
        """
        if self.__info is None:
            self.__info = DatabaseInfoProvider(self) if self._engine_version() >= 4.0 \
                else DatabaseInfoProvider3(self)
        return self.__info
    @property
    def charset(self) -> str:
        """Connection character set.
        """
        return self.__charset
    @property
    def sql_dialect(self) -> int:
        """Connection SQL dialect.
        """
        return self.__sql_dialect
    @property
    def main_transaction(self) -> TransactionManager:
        """Main transaction manager for this connection.
        """
        return self._tra_main
    @property
    def query_transaction(self) -> TransactionManager:
        """Transaction manager for Read-committed Read-only query transactions.
        """
        return self._tra_qry
    @property
    def transactions(self) -> List[TransactionManager]:
        """List of all transaction managers associated with connection.

        Note:
            The first two are always `.main_transaction` and `.query_transaction` managers.
        """
        result = [self.main_transaction, self.query_transaction]
        result.extend(self._transactions)
        return result
    @property
    def schema(self) -> 'firebird.lib.schema.Schema':
        """Access to database schema. Requires firebird.lib package.
        """
        if self.__schema is None:
            import firebird.lib.schema
            self.__schema = firebird.lib.schema.Schema()
            self.__schema.bind(self)
            self.__schema._set_internal(True)
        return self.__schema
    @property
    def monitor(self) -> 'firebird.lib.monitor.Monitor':
        """Access to database monitoring tables. Requires firebird.lib package.
        """
        if self.__monitor is None:
            import firebird.lib.monitor
            self.__monitor = firebird.lib.monitor.Monitor(self)
            self.__monitor._set_internal(True)
        return self.__monitor

def tpb(isolation: Isolation, lock_timeout: int=-1, access_mode: TraAccessMode=TraAccessMode.WRITE) -> bytes:
    """Helper function to costruct simple TPB.

    Arguments:
        isolation: Isolation level.
        lock_timeout: Lock timeout (-1 = Infinity)
        access: Access mode.
    """
    return TPB(isolation=isolation, lock_timeout=lock_timeout, access_mode=access_mode).get_buffer()

def _connect_helper(dsn: str, host: str, port: str, database: str, protocol: NetProtocol) -> str:
    if ((not dsn and not host and not database) or
            (dsn and (host or database)) or
            (host and not database)):
        raise InterfaceError("Must supply one of:\n"
                             " 1. keyword argument dsn='host:/path/to/database'\n"
                             " 2. both keyword arguments host='host' and"
                             " database='/path/to/database'\n"
                             " 3. only keyword argument database='/path/to/database'")
    if not dsn:
        if protocol is not None:
            dsn = f'{protocol.name.lower()}://'
            if host and port:
                dsn += f'{host}:{port}/'
            elif host:
                dsn += f'{host}/'
        else:
            dsn = ''
            if host and host.startswith('\\\\'): # Windows Named Pipes
                if port:
                    dsn += f'{host}@{port}\\'
                else:
                    dsn += f'{host}\\'
            elif host and port:
                dsn += f'{host}/{port}:'
            elif host:
                dsn += f'{host}:'
        dsn += database
    return dsn

def __make_connection(create: bool, dsn: str, utf8filename: bool, dpb: bytes,
                      sql_dialect: int, charset: str,
                      crypt_callback: iCryptKeyCallbackImpl) -> Connection:
    with a.get_api().master.get_dispatcher() as provider:
        if crypt_callback is not None:
            provider.set_dbcrypt_callback(crypt_callback)
        if create:
            att = provider.create_database(dsn, dpb, 'utf-8' if utf8filename else FS_ENCODING)
            con = Connection(att, dsn, dpb, sql_dialect, charset)
        else:
            con = None
            for hook in get_callbacks(ConnectionHook.ATTACH_REQUEST, Connection):
                try:
                    con = hook(dsn, dpb)
                except Exception as e:
                    raise InterfaceError("Error in DATABASE_ATTACH_REQUEST hook.", *e.args) from e
                if con is not None:
                    break
            if con is None:
                att = provider.attach_database(dsn, dpb, 'utf-8' if utf8filename else FS_ENCODING)
                con = Connection(att, dsn, dpb, sql_dialect, charset)
    for hook in get_callbacks(ConnectionHook.ATTACHED, con):
        hook(con)
    return con

def connect(database: str, *, user: str=None, password: str=None, role: str=None,
            no_gc: bool=None, no_db_triggers: bool=None, dbkey_scope: DBKeyScope=None,
            crypt_callback: iCryptKeyCallbackImpl=None, charset: str=None,
            auth_plugin_list: str=None, session_time_zone: str=None) -> Connection:
    """Establishes a connection to the database.

    Arguments:
        database: DSN or Database configuration name.
        user: User name.
        password: User password.
        role: User role.
        no_gc: Do not perform garbage collection for this connection.
        no_db_triggers: Do not execute database triggers for this connection.
        dbkey_scope: DBKEY scope override for connection.
        crypt_callback: Callback that provides encryption key for the database.
        charset: Character set for connection.
        auth_plugin_list: List of authentication plugins override
        session_time_zone: Session time zone [Firebird 4]

    Hooks:
        Event `.ConnectionHook.ATTACH_REQUEST`: Executed after all parameters
        are preprocessed and before `Connection` is created. Hook
        must have signature::

            hook_func(dsn: str, dpb: bytes) -> Optional[Connection]

        Hook may return `Connection` instance or None.
        First instance returned by any hook will become the return value
        of this function and other hooks are not called.

        Event `.ConnectionHook.ATTACHED`: Executed before `Connection` instance is
        returned. Hook must have signature::

            hook_func(connection: Connection) -> None

        Any value returned by hook is ignored.
    """
    db_config = driver_config.get_database(database)
    if db_config is None:
        db_config = driver_config.db_defaults
    else:
        database = db_config.database.value
    if db_config.server.value is None:
        srv_config = driver_config.server_defaults
    else:
        srv_config = driver_config.get_server(db_config.server.value)
        if srv_config is None:
            raise ValueError(f"Configuration for server '{db_config.server.value}' not found")
    if user is None:
        user = db_config.user.value
        if user is None:
            user = srv_config.user.value
    if password is None:
        password = db_config.password.value
        if password is None:
            password = srv_config.password.value
    if role is None:
        role = db_config.role.value
    if charset is None:
        charset = db_config.charset.value
    if charset:
        charset = charset.upper()
    if auth_plugin_list is None:
        auth_plugin_list = db_config.auth_plugin_list.value
    if session_time_zone is None:
        session_time_zone = db_config.session_time_zone.value
    dsn = _connect_helper(db_config.dsn.value, srv_config.host.value, srv_config.port.value,
                          database, db_config.protocol.value)
    dpb = DPB(user=user, password=password, role=role, trusted_auth=db_config.trusted_auth.value,
              sql_dialect=db_config.sql_dialect.value, timeout=db_config.timeout.value,
              charset=charset, cache_size=db_config.cache_size.value,
              no_linger=db_config.no_linger.value, utf8filename=db_config.utf8filename.value,
              no_gc=no_gc, no_db_triggers=no_db_triggers, dbkey_scope=dbkey_scope,
              dummy_packet_interval=db_config.dummy_packet_interval.value,
              config=db_config.config.value, auth_plugin_list=auth_plugin_list,
              session_time_zone=session_time_zone, set_bind=db_config.set_bind.value,
              decfloat_round=db_config.decfloat_round.value,
              decfloat_traps=db_config.decfloat_traps.value)
    return __make_connection(False, dsn, db_config.utf8filename.value, dpb.get_buffer(),
                             db_config.sql_dialect.value, charset, crypt_callback)

def create_database(database: str, *, user: str=None, password: str=None, role: str=None,
                    no_gc: bool=None, no_db_triggers: bool=None, dbkey_scope: DBKeyScope=None,
                    crypt_callback: iCryptKeyCallbackImpl=None, charset: str=None,
                    overwrite: bool=False, auth_plugin_list=None,
                    session_time_zone: str=None) -> Connection:
    """Creates new database.

    Arguments:
        database: DSN or Database configuration name.
        user: User name.
        password: User password.
        role: User role.
        no_gc: Do not perform garbage collection for this connection.
        no_db_triggers: Do not execute database triggers for this connection.
        dbkey_scope: DBKEY scope override for connection.
        crypt_callback: Callback that provides encryption key for the database.
        charset: Character set for connection.
        overwrite: Overwite the existing database.
        auth_plugin_list: List of authentication plugins override
        session_time_zone: Session time zone [Firebird 4]

    Hooks:
        Event `.ConnectionHook.ATTACHED`: Executed before `Connection` instance is
        returned. Hook must have signature::

            hook_func(connection: Connection) -> None

        Any value returned by hook is ignored.
    """
    db_config = driver_config.get_database(database)
    if db_config is None:
        db_config = driver_config.db_defaults
        db_config.database.value = database
        if db_config.server.value is None:
            srv_config = driver_config.server_defaults
        else:
            srv_config = driver_config.get_server(db_config.server.value)
            if srv_config is None:
                raise ValueError(f"Configuration for server '{db_config.server.value}' not found")
    else:
        if db_config.server.value is None:
            srv_config = driver_config.server_defaults
        else:
            srv_config = driver_config.get_server(db_config.server.value)
            if srv_config is None:
                raise ValueError(f"Configuration for server '{db_config.server.value}' not found")
    if user is None:
        user = db_config.user.value
        if user is None:
            user = srv_config.user.value
    if password is None:
        password = db_config.password.value
        if password is None:
            password = srv_config.password.value
    if role is None:
        role = db_config.role.value
    if charset is None:
        charset = db_config.charset.value
    if charset:
        charset = charset.upper()
    if auth_plugin_list is None:
        auth_plugin_list = db_config.auth_plugin_list.value
    if session_time_zone is None:
        session_time_zone = db_config.session_time_zone.value
    dsn = _connect_helper(db_config.dsn.value, srv_config.host.value, srv_config.port.value,
                          db_config.database.value, db_config.protocol.value)
    dpb = DPB(user=user, password=password, role=role, trusted_auth=db_config.trusted_auth.value,
              sql_dialect=db_config.db_sql_dialect.value, timeout=db_config.timeout.value,
              charset=charset, cache_size=db_config.cache_size.value,
              no_linger=db_config.no_linger.value, utf8filename=db_config.utf8filename.value,
              no_gc=no_gc, no_db_triggers=no_db_triggers, dbkey_scope=dbkey_scope,
              dummy_packet_interval=db_config.dummy_packet_interval.value,
              config=db_config.config.value, auth_plugin_list=auth_plugin_list,
              session_time_zone=session_time_zone, set_bind=db_config.set_bind.value,
              decfloat_round=db_config.decfloat_round.value,
              decfloat_traps=db_config.decfloat_traps.value,
              overwrite=overwrite, db_cache_size=db_config.db_cache_size.value,
              forced_writes=db_config.forced_writes.value, page_size=db_config.page_size.value,
              reserve_space=db_config.reserve_space.value, sweep_interval=db_config.sweep_interval.value,
              db_sql_dialect=db_config.db_sql_dialect.value, db_charset=db_config.db_charset.value)
    return __make_connection(True, dsn, db_config.utf8filename.value,
                             dpb.get_buffer(for_create=True), db_config.sql_dialect.value,
                             charset, crypt_callback)

class TransactionInfoProvider3(InfoProvider):
    """Provides access to information about transaction [Firebird 3+].

    Important:
       Do NOT create instances of this class directly! Use `TransactionManager.info`
       property to access the instance already bound to transaction context.
    """
    def __init__(self, charset: str, tra: TransactionManager):
        super().__init__(charset)
        self._mngr: TransactionManager = weakref.ref(tra)
        self._handlers: Dict[DbInfoCode, Callable] = \
            {TraInfoCode.ISOLATION: self.__isolation,
             TraInfoCode.ACCESS: self.__access,
             TraInfoCode.DBPATH: self.response.read_sized_string,
             TraInfoCode.LOCK_TIMEOUT: self.__lock_timeout,
             TraInfoCode.ID: self.response.read_sized_int,
             TraInfoCode.OLDEST_INTERESTING: self.response.read_sized_int,
             TraInfoCode.OLDEST_SNAPSHOT: self.response.read_sized_int,
             TraInfoCode.OLDEST_ACTIVE: self.response.read_sized_int,
            }
    def __isolation(self) -> Isolation:
        cnt = self.response.read_short()
        if cnt == 1:
            # The value is `TraInfoIsolation` that maps to `Isolation`
            return Isolation(self.response.read_byte())
        else:
            # The values are `TraInfoIsolation` + `TraInfoReadCommitted` that maps to `Isolation`
            return Isolation(self.response.read_byte() + self.response.read_byte())
    def __access(self) -> TraInfoAccess:
        return TraInfoAccess(self.response.read_sized_int())
    def __lock_timeout(self) -> int:
        return self.response.read_sized_int(signed=True)
    def _acquire(self, request: bytes) -> None:
        assert self._mngr is not None
        if not self._mngr().is_active():
            raise InterfaceError("TransactionManager is not active")
        self._mngr()._tra.get_info(request, self.response.raw)
    def _close(self) -> None:
        self._mngr = None
    def get_info(self, info_code: TraInfoCode) -> Any:
        if info_code not in self._handlers:
            raise NotSupportedError(f"Info code {info_code} not supported by engine version {self._mngr()._connection()._engine_version()}")
        request = bytes([info_code])
        self._get_data(request)
        tag = self.response.get_tag()
        if (request[0] != tag):
            if tag == isc_info_error:  # pragma: no cover
                raise InterfaceError("An error response was received")
            else:  # pragma: no cover
                raise InterfaceError("Result code does not match request code")
        #
        return self._handlers[info_code]()
    # Functions
    def is_read_only(self) -> bool:
        """Returns True if transaction is Read Only.
        """
        return self.get_info(TraInfoCode.ACCESS) == TraInfoAccess.READ_ONLY
    # Properties
    @property
    def id(self) -> int:
        """Transaction ID.
        """
        return self.get_info(TraInfoCode.ID)
    @property
    def oit(self) -> int:
        """ID of Oldest Interesting Transaction at the time this transaction started.
        """
        return self.get_info(TraInfoCode.OLDEST_INTERESTING)
    @property
    def oat(self) -> int:
        """ID of Oldest Active Transaction at the time this transaction started.
        """
        return self.get_info(TraInfoCode.OLDEST_ACTIVE)
    @property
    def ost(self) -> int:
        """ID of Oldest Snapshot Transaction at the time this transaction started.
        """
        return self.get_info(TraInfoCode.OLDEST_SNAPSHOT)
    @property
    def isolation(self) -> Isolation:
        """Isolation level.
        """
        return self.get_info(TraInfoCode.ISOLATION)
    @property
    def lock_timeout(self) -> int:
        """Lock timeout.
        """
        return self.get_info(TraInfoCode.LOCK_TIMEOUT)
    @property
    def database(self) -> str:
        """Database filename.
        """
        return self.get_info(TraInfoCode.DBPATH)
    @property
    def snapshot_number(self) -> int:
        """Snapshot number for this transaction.

        Raises:
            NotSupportedError: Requires Firebird 4+
        """
        self._raise_not_supported()

class TransactionInfoProvider(TransactionInfoProvider3):
    """Provides access to information about transaction [Firebird 4+].

    Important:
       Do NOT create instances of this class directly! Use `TransactionManager.info`
       property to access the instance already bound to transaction context.
    """
    def __init__(self, charset: str, tra: TransactionManager):
        super().__init__(charset, tra)
        self._handlers.update({TraInfoCode.SNAPSHOT_NUMBER: self.response.read_sized_int,})
    @property
    def snapshot_number(self) -> int:
        """Snapshot number for this transaction.
        """
        return self.get_info(TraInfoCode.SNAPSHOT_NUMBER)

class TransactionManager(LoggingIdMixin):
    """Transaction manager.

    Note:
        Implements context manager protocol to call `.close()` automatically.

    Attributes:
        default_tpb (bytes): Default Transaction parameter buffer.
        default_action (DefaultAction): Default action for implicit transaction end.
    """
    def __init__(self, connection: Connection, default_tpb: bytes,
                 default_action: DefaultAction=DefaultAction.COMMIT):
        self._connection: Callable[[], Connection] = weakref.ref(connection, self.__dead_con)
        #: Default Transaction Parameter Block used to start transaction
        self.default_tpb: bytes = default_tpb
        #: Default action (commit/rollback) to be performed when transaction is closed.
        self.default_action: DefaultAction = default_action
        self.__info: Union[TransactionInfoProvider, TransactionInfoProvider3] = None
        self._cursors: List = []  # Weak references to cursors
        self._tra: iTransaction = None
        self.__closed: bool = False
        self._logging_id_ = 'Transaction'
    def __enter__(self) -> TransactionManager:
        self.begin()
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __del__(self):
        if self._tra is not None:
            warn(f"Transaction '{self.logging_id}' disposed while active", ResourceWarning)
            self._finish()
    def __dead_con(self, obj) -> None:
        self._connection = None
    def _close_cursors(self) -> None:
        for cursor in self._cursors:
            c = cursor()
            if c:
                c.close()
    def _cursor_deleted(self, obj) -> None:
        self._cursors.remove(obj)
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
    def close(self) -> None:
        """Close the transaction manager and release all associated resources.

        Important:
            Closed instance SHALL NOT be used anymore.
        """
        if not self.__closed:
            try:
                self._finish()
            finally:
                con = self._connection()
                if con is not None and self in con._transactions:
                    con._transactions.remove(self)
                self._connection = None
                self.__closed = True
                if self.__info is not None:
                    self.__info._close()
    def execute_immediate(self, sql: str) -> None:
        """Executes SQL statement. The statement MUST NOT return any result.

        Arguments:
           sql: SQL statement to be executed.
        """
        assert not self.__closed
        if not self.is_active():
            self.begin()
        self._connection()._att.execute(self._tra, sql, self._connection().sql_dialect)
    def begin(self, tpb: bytes=None) -> None:
        """Starts new transaction managed by this instance.

        Arguments:
            tpb: Transaction parameter buffer with transaction's parameters. If not specified,
                 the `.default_tpb` is used.
        """
        assert not self.__closed
        self._finish()  # Make sure that previous transaction (if any) is ended
        self._tra = self._connection()._att.start_transaction(tpb if tpb else self.default_tpb)
    def commit(self, *, retaining: bool=False) -> None:
        """Commits the transaction managed by this instance.

        Arguments:
            retaining: When True, the transaction context is retained after commit.
        """
        assert not self.__closed
        assert self.is_active()
        if retaining:
            self._tra.commit_retaining()
        else:
            self._close_cursors()
            self._tra.commit()
        if not retaining:
            self._tra = None
    def rollback(self, *, retaining: bool=False, savepoint: str=None) -> None:
        """Rolls back the transaction managed by this instance.

        Arguments:
            retaining: When True, the transaction context is retained after rollback.
            savepoint: When specified, the transaction is rolled back to savepoint with given name.

        Raises:
            InterfaceError: When both retaining and savepoint parameters are specified.
        """
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
                self._close_cursors()
                self._tra.rollback()
            if not retaining:
                self._tra = None
    def savepoint(self, name: str) -> None:
        """Creates a new savepoint for transaction managed by this instance.

        Arguments:
            name: Name for the savepoint
        """
        self.execute_immediate(f'SAVEPOINT {name}')
    def cursor(self) -> Cursor:
        """Returns new `Cursor` instance associated with this instance.
        """
        assert not self.__closed
        cur = Cursor(self._connection(), self)
        self._cursors.append(weakref.ref(cur, self._cursor_deleted))
        return cur
    def is_active(self) -> bool:
        """Returns True if transaction is active.
        """
        return self._tra is not None
    def is_closed(self) -> bool:
        """Returns True if this transaction manager is closed.
        """
        return self.__closed
    # Properties
    @property
    def info(self) -> Union[TransactionInfoProvider3, TransactionInfoProvider]:
        """Access to various information about active transaction.
        """
        if self.__info is None:
            cls = TransactionInfoProvider if self._connection()._engine_version() >= 4.0 \
                else TransactionInfoProvider3
            self.__info = cls(self._connection()._encoding, self)
        return self.__info
    @property
    def log_context(self) -> Connection:
        if self._connection is None:
            return 'Connection.GC'
        return self._connection()
    @property
    def cursors(self) -> List[Cursor]:
        """Cursors associated with this transaction.
        """
        return [x() for x in self._cursors]

class DistributedTransactionManager(TransactionManager):
    """Manages distributed transaction over multiple connections that use two-phase
    commit protocol.

    Note:
        Implements context manager protocol to call `.close()` automatically.

    Attributes:
        default_tpb (bytes): Default Transaction parameter buffer
        default_action (DefaultAction): Default action for implicit transaction end
    """
    def __init__(self, connections: Sequence[Connection], default_tpb: bytes=None,
                 default_action: DefaultAction=DefaultAction.COMMIT):
        self._connections: List[Connection] = list(connections)
        self.default_tpb: bytes = default_tpb if default_tpb is not None else tpb(Isolation.SNAPSHOT)
        self.default_action: DefaultAction = default_action
        self._cursors: List = []  # Weak references to cursors
        self._tra: iTransaction = None
        self._dtc: iDtc = _master.get_dtc()
        self.__closed: bool = False
        self._logging_id_ = 'DTransaction'
    def close(self) -> None:
        """Close the distributed transaction manager and release all associated
        resources.

        Important:
            Closed instance SHALL NOT be used anymore.
        """
        if not self.__closed:
            try:
                self._finish()
            finally:
                self._connections.clear()
                self.__closed = True
    def execute_immediate(self, sql: str) -> None:
        """Executes SQL statement on all connections in distributed transaction.
        The statement MUST NOT return any result.

        Arguments:
           sql: SQL statement to be executed.
        """
        assert not self.__closed
        if not self.is_active():
            self.begin()
        for connection in self._connections:
            connection._att.execute(self._tra, sql, connection.sql_dialect)
    def begin(self, tpb: bytes=None) -> None:
        """Starts new distributed transaction managed by this instance.

        Arguments:
            tpb: Transaction parameter buffer with transaction's parameters. If not specified,
                 the `.default_tpb` is used.
        """
        assert not self.__closed
        self._finish()  # Make sure that previous transaction (if any) is ended
        with self._dtc.start_builder() as builder:
            for con in self._connections:
                builder.add_with_tpb(con._att, tpb if tpb else self.default_tpb)
            self._tra = builder.start()
    def prepare(self) -> None:
        """Manually triggers the first phase of a two-phase commit (2PC).

        Note:
           Direct use of this method is optional; if preparation is not triggered
           manually, it will be performed implicitly by `.commit()` in a 2PC.
        """
        assert not self.__closed
        assert self.is_active()
        self._tra.prepare()
    def commit(self, *, retaining: bool=False) -> None:
        """Commits the distributed transaction managed by this instance.

        Arguments:
            retaining: When True, the transaction context is retained after commit.
        """
        assert not self.__closed
        assert self.is_active()
        if retaining:
            self._tra.commit_retaining()
        else:
            self._close_cursors()
            self._tra.commit()
        if not retaining:
            self._tra = None
    def rollback(self, *, retaining: bool=False, savepoint: str=None) -> None:
        """Rolls back the distributed transaction managed by this instance.

        Arguments:
            retaining: When True, the transaction context is retained after rollback.
            savepoint: When specified, the transaction is rolled back to savepoint with given name.

        Raises:
            InterfaceError: When both retaining and savepoint parameters are specified.
        """
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
                self._close_cursors()
                self._tra.rollback()
            if not retaining:
                self._tra = None
    def savepoint(self, name: str) -> None:
        """Creates a new savepoint for distributed transaction managed by this instance.

        Arguments:
            name: Name for the savepoint
        """
        self.execute_immediate(f'SAVEPOINT {name}')
    def cursor(self, connection: Connection) -> Cursor:
        """Returns new `Cursor` instance associated with specified connection and
        this distributed transaction manager.

        Raises:
            InterfaceError: When specified connection is not associated with distributed
                            connection manager.
        """
        assert not self.__closed
        if connection not in self._connections:
            raise InterfaceError("Cannot create cursor for connection that does "
                                 "not belong to this distributed transaction")
        cur = Cursor(connection, self)
        self._cursors.append(weakref.ref(cur, self._cursor_deleted))
        return cur

    @property
    def log_context(self) -> Connection:
        return UNDEFINED

class Statement(LoggingIdMixin):
    """Prepared SQL statement.

    Note:
        Implements context manager protocol to call `.free()` automatically.
    """
    def __init__(self, connection: Connection, stmt: iStatement, sql: str, dialect: int):
        self._connection: Callable[[], Connection] = weakref.ref(connection, self.__dead_con)
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
            self._in_buffer = create_string_buffer(meta.get_message_length())
        # Output metadata
        meta = stmt.get_output_metadata()
        self._out_meta: iMessageMetadata = None
        self._out_cnt: int = meta.get_count()
        self._out_buffer: bytes = None
        self._out_desc: List[ItemMetadata] = None
        if self._out_cnt == 0:
            meta.release()
            self._out_desc = []
        else:
            self._out_meta = meta
            self._out_buffer = create_string_buffer(meta.get_message_length())
            self._out_desc = create_meta_descriptors(meta)
    def __enter__(self) -> Statement:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.free()
    def __del__(self):
        if self._in_meta or self._out_meta or self._istmt:
            warn(f"Statement '{self.logging_id}' disposed without prior free()", ResourceWarning)
            self.free()
    def __str__(self):
        return f'{self.logging_id}[{self.sql}]'
    def __repr__(self):
        return str(self)
    def __dead_con(self, obj) -> None:
        self._connection = None
    def __get_plan(self, detailed: bool) -> str:
        assert self._istmt is not None
        result = self._istmt.get_plan(detailed)
        return result if result is None else result.strip()
    def free(self) -> None:
        """Release the statement and all associated resources.

        Important:
            The statement SHALL NOT be used after call to this method.
        """
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
        """Returns True if statement has cursor (can return multiple rows).
        """
        assert self._istmt is not None
        return StatementFlag.HAS_CURSOR in self._flags
    def can_repeat(self) -> bool:
        """Returns True if statement could be executed repeatedly.
        """
        assert self._istmt is not None
        return StatementFlag.REPEAT_EXECUTE in self._flags
    # Properties
    @property
    def log_context(self) -> Connection:
        if self._connection is None:
            return 'Connection.GC'
        return self._connection()
    @property
    def plan(self) -> str:
        """Execution plan in classic format.
        """
        return self.__get_plan(False)
    @property
    def detailed_plan(self) -> str:
        """Execution plan in new format (explained).
        """
        return self.__get_plan(True)
    @property
    def sql(self) -> str:
        """SQL statement.
        """
        return self.__sql
    @property
    def type(self) -> StatementType:
        """Statement type.
        """
        return self._type
    @property
    def timeout(self) -> int:
        """Statement timeout.
        """
        if self._connection()._engine_version() >= 4.0:
            return self._istmt.get_timeout()
        raise NotSupportedError(f"Statement timeout not supported by engine version {self._connection()._engine_version()}")
    @timeout.setter
    def _timeout(self, value: int) -> None:
        if self._connection()._engine_version() >= 4.0:
            return self._istmt.set_timeout(value)
        raise NotSupportedError(f"Statement timeout not supported by engine version {self._connection()._engine_version()}")

class BlobReader(io.IOBase, LoggingIdMixin):
    """Handler for large BLOB values returned by server.

    The BlobReader is a “file-like” class, so it acts much like an open file instance.

    Attributes:
        sub_type (int): BLOB sub-type
        newline (str): Sequence used as line terminator, default `'\\\\n'`

    Note:
        Implements context manager protocol to call `.close()` automatically.

    Attributes:
        sub_type (int): BLOB sub-type
    """
    def __init__(self, blob: iBlob, blob_id: a.ISC_QUAD, sub_type: int,
                 length: int, segment_size: int, charset: str, owner: Any=None):
        self._blob: iBlob = blob
        self.newline: str = '\n'
        self.sub_type: int = sub_type
        self._owner: Any = weakref.ref(owner)
        self._charset: str = charset
        self._blob_length: int = length
        self._segment_size: int = segment_size
        self.__blob_id: a.ISC_QUAD = blob_id
        self.__bytes_read = 0
        self.__pos = 0
        self.__index = 0
        self.__buf = create_string_buffer(self._segment_size)
        self.__buf_pos = 0
        self.__buf_data = 0
    def __next__(self):
        line = self.readline()
        if line:
            return line
        else:
            raise StopIteration
    def __iter__(self):
        return self
    def __reset_buffer(self) -> None:
        memset(self.__buf, 0, self._segment_size)
        self.__buf_pos = 0
        self.__buf_data = 0
    def __blob_get(self) -> None:
        self.__reset_buffer()
        # Load BLOB
        bytes_actually_read = a.Cardinal(0)
        self._blob.get_segment(self._segment_size, byref(self.__buf),
                               bytes_actually_read)
        self.__buf_data = bytes_actually_read.value
    def __enter__(self) -> BlobReader:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __del__(self):
        if self._blob is not None:
            warn(f"BlobReader '{self.logging_id}' disposed without prior close()", ResourceWarning)
            self.close()
    def __repr__(self):
        return f'{self.logging_id}[size={self.length}]'
    def flush(self) -> None:
        """Does nothing.
        """
        pass
    def close(self) -> None:
        """Close the BlobReader.
        """
        if self._blob is not None:
            self._blob.close()
            self._blob = None
    def read(self, size: int=-1) -> Union[str, bytes]:
        """Read at most size bytes from the file (less if the read hits EOF
        before obtaining size bytes). If the size argument is negative or omitted,
        read all data until EOF is reached. The bytes are returned as a string
        object. An empty string is returned when EOF is encountered immediately.
        Like `file.read()`.

        Note:
           Performs automatic conversion to `str` for TEXT BLOBs.
        """
        assert self._blob is not None
        if size >= 0:
            to_read = min(size, self._blob_length - self.__pos)
        else:
            to_read = self._blob_length - self.__pos
        return_size = to_read
        result: bytes = create_string_buffer(return_size)
        pos = 0
        while to_read > 0:
            to_copy = min(to_read, self.__buf_data - self.__buf_pos)
            if to_copy == 0:
                self.__blob_get()
                to_copy = min(to_read, self.__buf_data - self.__buf_pos)
                if to_copy == 0:
                    # BLOB EOF
                    break
            memmove(byref(result, pos), byref(self.__buf, self.__buf_pos), to_copy)
            pos += to_copy
            self.__pos += to_copy
            self.__buf_pos += to_copy
            to_read -= to_copy
        result = result.raw[:return_size]
        if self.sub_type == 1:
            result = result.decode(self._charset)
        return result
    def readline(self, size: int=-1) -> str:
        """Read and return one line from the BLOB. If size is specified, at most size bytes
        will be read.

        Uses `newline` as the line terminator.

        Raises:
           InterfaceError: For non-textual BLOBs.
        """
        assert self._blob is not None
        if self.sub_type != 1:
            raise InterfaceError("Can't read line from binary BLOB")
        line = []
        to_read = self._blob_length - self.__pos
        if size >= 0:
            to_read = min(to_read, size)
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
            line.append(string_at(byref(self.__buf, self.__buf_pos), pos).decode(self._charset))
            self.__buf_pos += pos
            self.__pos += pos
            to_read -= pos
        result = ''.join(line)
        if self.newline != '\n':
            result = result.replace('\n', self.newline)
        return result
    def readlines(self, hint: int=-1) -> List[str]:
        """Read and return a list of lines from the stream. `hint` can be specified to
        control the number of lines read: no more lines will be read if the total size
        (in bytes/characters) of all lines so far exceeds hint.

        Note:
            It’s already possible to iterate on BLOB using `for line in blob:` ... without
            calling `.readlines()`.

        Raises:
           InterfaceError: For non-textual BLOBs.
        """
        result = []
        line = self.readline()
        while line:
            if hint >= 0 and len(result) == hint:
                break
            result.append(line)
            line = self.readline()
        return result
    def seek(self, offset: int, whence: int=os.SEEK_SET) -> None:
        """Set the file’s current position, like stdio‘s `fseek()`.

        See:
            :meth:`io.IOBase.seek()` for details.

        Arguments:
            offset: Offset from specified position.
            whence: Context for offset. Accepted values: os.SEEK_SET, os.SEEK_CUR or os.SEEK_END

        Warning:
           If BLOB was NOT CREATED as `stream` BLOB, this method raises `DatabaseError`
           exception. This constraint is set by Firebird.
        """
        assert self._blob is not None
        self.__pos = self._blob.seek(whence, offset)
        self.__reset_buffer()
    def tell(self) -> int:
        """Return current position in BLOB.

        See:
            :meth:`io.IOBase.tell()` for details.
        """
        return self.__pos
    def is_text(self) -> bool:
        """True if BLOB is a text BLOB.
        """
        return self.sub_type == 1
    # Properties
    @property
    def log_context(self) -> Any:
        if self._owner is None:
            return UNDEFINED
        if (r := self._owner()) is not None:
            return r
        return 'Owner.GC'
    @property
    def length(self) -> int:
        """BLOB length.
        """
        return self._blob_length
    @property
    def closed(self) -> bool:
        """True if the BLOB is closed.
        """
        return self._blob is None
    @property
    def mode(self) -> str:
        """File mode ('r' or 'rb').
        """
        return 'rb' if self.sub_type != 1 else 'r'
    @property
    def blob_id(self) -> a.ISC_QUAD:
        """BLOB ID.
        """
        return self.__blob_id
    @property
    def blob_type(self) -> BlobType:
        """BLOB type.
        """
        result = self._blob.get_info2(BlobInfoCode.TYPE)
        return BlobType(result)

class Cursor(LoggingIdMixin):
    """Represents a database cursor, which is used to execute SQL statement and
    manage the context of a fetch operation.

    Note:
        Implements context manager protocol to call `.close()` automatically.
    """
    #: This read/write attribute specifies the number of rows to fetch at a time with
    #: .fetchmany(). It defaults to 1 meaning to fetch a single row at a time.
    #:
    #: Required by Python DB API 2.0
    arraysize: int = 1
    def __init__(self, connection: Connection, transaction: TransactionManager):
        self._connection: Connection = connection
        self._dialect: int = connection.sql_dialect
        self._transaction: TransactionManager = transaction
        self._stmt: Statement = None
        self._encoding: str = connection._encoding
        self._result: iResultSet = None
        self._last_fetch_status: StateResult = None
        self._name: str = None
        self._executed: bool = False
        self._cursor_flags: CursorFlag = CursorFlag.NONE
        self.__output_cache: Tuple = None
        self.__internal: bool = False
        self.__blob_readers: Set = weakref.WeakSet()
        #: Names of columns that should be returned as `BlobReader`.
        self.stream_blobs: List[str] = []
        #: BLOBs greater than threshold are returned as `BlobReader` instead in materialized form.
        self.stream_blob_threshold = driver_config.stream_blob_threshold.value
    def __enter__(self) -> Cursor:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __del__(self):
        if self._result is not None or self._stmt is not None or self.__blob_readers:
            warn(f"Cursor '{self.logging_id}' disposed without prior close()", ResourceWarning)
            self.close()
    def __next__(self):
        if (row := self.fetchone()) is not None:
            return row
        else:
            raise StopIteration
    def __iter__(self):
        return self
    def _dead_con(self, obj) -> None:
        self._connection = None
    def _extract_db_array_to_list(self, esize: int, dtype: int, subtype: int,
                                  scale: int, dim: int, dimensions: List[int],
                                  buf: Any, bufpos: int) -> Tuple[Any, int]:
        value = []
        if dim == len(dimensions)-1:
            for _ in range(dimensions[dim]):
                if dtype in (a.blr_text, a.blr_text2):
                    val = string_at(buf[bufpos:bufpos+esize], esize)
                    ### Todo: verify handling of P version differences
                    if subtype != 1:   # non OCTETS
                        val = val.decode(self._encoding)
                    # CHAR with multibyte encoding requires special handling
                    if subtype in (4, 69):  # UTF8 and GB18030
                        reallength = esize // 4
                    elif subtype == 3:  # UNICODE_FSS
                        reallength = esize // 3
                    else:
                        reallength = esize
                    val = val[:reallength]
                elif dtype in (a.blr_varying, a.blr_varying2):
                    val = string_at(buf[bufpos:bufpos+esize])
                    if subtype != a.OCTETS:
                        val = val.decode(self._encoding)
                elif dtype in (a.blr_short, a.blr_long, a.blr_int64):
                    val = (0).from_bytes(buf[bufpos:bufpos + esize], 'little', signed=True)
                    if subtype or scale:
                        val = decimal.Decimal(val) / _tenTo[abs(256-scale)]
                elif dtype == a.blr_bool:
                    val = (0).from_bytes(buf[bufpos:bufpos + esize], 'little') == 1
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
                elif dtype == a.blr_sql_time_tz:
                    val = _util.decode_time_tz(buf[bufpos:bufpos+esize])
                elif dtype == a.blr_timestamp_tz:
                    val = _util.decode_timestamp_tz(buf[bufpos:bufpos+esize])
                elif dtype == a.blr_int128:
                    val = decimal.Decimal(_util.get_int128().to_str(a.FB_I128.from_buffer_copy(buf[bufpos:bufpos+esize]), scale))
                elif dtype == a.blr_dec64:
                    val = decimal.Decimal(_util.get_decfloat16().to_str(a.FB_DEC16.from_buffer_copy(buf[bufpos:bufpos+esize])))
                elif dtype == a.blr_dec128:
                    val = decimal.Decimal(_util.get_decfloat34().to_str(a.FB_DEC34.from_buffer_copy(buf[bufpos:bufpos+esize])))
                else:  # pragma: no cover
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
                               scale: int, dim: int, dimensions: List[int],
                               value: Any, buf: Any, bufpos: int) -> None:
        valuebuf = None
        if dtype in (a.blr_text, a.blr_text2):
            valuebuf = create_string_buffer(bytes([0]), esize)
        elif dtype in (a.blr_varying, a.blr_varying2):
            valuebuf = create_string_buffer(bytes([0]), esize)
        elif dtype in (a.blr_short, a.blr_long, a.blr_int64):
            if esize == 2:
                valuebuf = a.ISC_SHORT(0)
            elif esize == 4:
                valuebuf = a.ISC_LONG(0)
            elif esize == 8:
                valuebuf = a.ISC_INT64(0)
            else:  # pragma: no cover
                raise InterfaceError("Unsupported number type")
        elif dtype == a.blr_float:
            valuebuf = create_string_buffer(bytes([0]), esize)
        elif dtype in (a.blr_d_float, a.blr_double):
            valuebuf = create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_timestamp:
            valuebuf = create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_sql_date:
            valuebuf = create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_sql_time:
            valuebuf = create_string_buffer(bytes([0]), esize)
        elif dtype == a.blr_bool:
            valuebuf = create_string_buffer(bytes([0]), esize)
        else:  # pragma: no cover
            raise InterfaceError(f"Unsupported Firebird ARRAY subtype: {dtype}")
        self._fill_db_array_buffer(esize, dtype,
                                   subtype, scale,
                                   dim, dimensions,
                                   value, valuebuf,
                                   buf, bufpos)
    def _fill_db_array_buffer(self, esize: int, dtype: int, subtype: int,
                              scale: int, dim: int, dimensions: List[int],
                              value: Any, valuebuf: Any, buf: Any, bufpos: int) -> int:
        if dim == len(dimensions)-1:
            for i in range(dimensions[dim]):
                if dtype in (a.blr_text, a.blr_text2,
                             a.blr_varying, a.blr_varying2):
                    val = value[i]
                    if isinstance(val, str):
                        val = val.encode(self._encoding)
                    if len(val) > esize:
                        raise ValueError(f"ARRAY value of parameter is too long,"
                                         f" expected {esize}, found {len(val)}")
                    valuebuf.value = val
                    memmove(byref(buf, bufpos), valuebuf, esize)
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
                        else:  # pragma: no cover
                            raise InterfaceError("Unsupported type")
                    memmove(byref(buf, bufpos),
                                   byref(valuebuf),
                                   esize)
                elif dtype == a.blr_bool:
                    valuebuf.value = (1 if value[i] else 0).to_bytes(1, 'little')
                    memmove(byref(buf, bufpos),
                                   byref(valuebuf),
                                   esize)
                elif dtype == a.blr_float:
                    valuebuf.value = struct.pack('f', value[i])
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype in (a.blr_d_float, a.blr_double):
                    valuebuf.value = struct.pack('d', value[i])
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_timestamp:
                    valuebuf.value = _encode_timestamp(value[i])
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_sql_date:
                    valuebuf.value = _util.encode_date(value[i]).to_bytes(4, 'little')
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_sql_time:
                    valuebuf.value = _util.encode_time(value[i]).to_bytes(4, 'little')
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_sql_time_tz:
                    valuebuf.value = _util.encode_time_tz(value[i]).to_bytes(esize, 'little')
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_timestamp_tz:
                    valuebuf.value = _util.encode_timestamp_tz(value[i])
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_dec64:
                    valuebuf.value = _util.get_decfloat16().from_str(str(value[i]))
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_dec128:
                    valuebuf.value = _util.get_decfloat34().from_str(str(value[i]))
                    memmove(byref(buf, bufpos), valuebuf, esize)
                elif dtype == a.blr_int128:
                    valuebuf.value = _util.get_int128().from_str(str(value), scale)
                    memmove(byref(buf, bufpos), valuebuf, esize)
                else:  # pragma: no cover
                    raise InterfaceError(f"Unsupported Firebird ARRAY subtype: {dtype}")
                bufpos += esize
        else:
            for i in range(dimensions[dim]):
                bufpos = self._fill_db_array_buffer(esize, dtype, subtype,
                                                    scale, dim+1,
                                                    dimensions, value[i],
                                                    valuebuf, buf, bufpos)
        return bufpos
    def _validate_array_value(self, dim: int, dimensions: List[int],
                              value_type: int, sqlsubtype: int,
                              value_scale: int, value: Any) -> bool:
        ok = isinstance(value, (list, tuple))
        ok = ok and (len(value) == dimensions[dim])
        if not ok:
            return False
        for i in range(dimensions[dim]):
            if dim == len(dimensions) - 1:
                # leaf: check value type
                if value_type in (a.blr_text, a.blr_text2, a.blr_varying, a.blr_varying2):
                    ok = isinstance(value[i], str)
                elif value_type in (a.blr_short, a.blr_long, a.blr_int64, a.blr_int128):
                    if sqlsubtype or value_scale:
                        ok = isinstance(value[i], decimal.Decimal)
                    else:
                        ok = isinstance(value[i], int)
                elif value_type in (a.blr_dec64, a.blr_dec128):
                    ok = isinstance(value[i], decimal.Decimal)
                elif value_type == a.blr_float:
                    ok = isinstance(value[i], float)
                elif value_type in (a.blr_d_float, a.blr_double):
                    ok = isinstance(value[i], float)
                elif value_type in (a.blr_timestamp, a.blr_timestamp_tz):
                    ok = isinstance(value[i], datetime.datetime)
                elif value_type == a.blr_sql_date:
                    ok = isinstance(value[i], datetime.date)
                elif value_type in (a.blr_sql_time, a.blr_sql_time_tz):
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
            if not ok: # Fail early
                return False
        return ok
    def _pack_input(self, meta: iMessageMetadata, buffer: bytes,
                    parameters: Sequence) -> Tuple[iMessageMetadata, bytes]:
        in_cnt = meta.get_count()
        if len(parameters) != in_cnt:
            raise InterfaceError(f"Statement parameter sequence contains"
                                 f" {len(parameters)} items,"
                                 f" but exactly {in_cnt} are required")
        #
        buf_size = len(buffer)
        memset(buffer, 0, buf_size)
        # Adjust metadata where needed
        with meta.get_builder() as builder:
            for i in range(in_cnt):
                value = parameters[i]
                if _is_str_param(value, meta.get_type(i)):
                    builder.set_type(i, SQLDataType.TEXT)
                    if not isinstance(value, (str, bytes, bytearray)):
                        value = str(value)
                    builder.set_length(i, len(value.encode(self._encoding)) if isinstance(value, str) else len(value))
            in_meta = builder.get_metadata()
            new_size = in_meta.get_message_length()
            in_buffer = create_string_buffer(new_size) if buf_size < new_size else buffer
        buf_addr = addressof(in_buffer)
        with in_meta:
            for i in range(in_cnt):
                value = parameters[i]
                datatype = in_meta.get_type(i)
                length = in_meta.get_length(i)
                offset = in_meta.get_offset(i)
                # handle NULL value
                in_buffer[in_meta.get_null_offset(i)] = 1 if value is None else 0
                if value is None:
                    continue
                # store parameter value
                if _is_str_param(value, datatype):
                    # Implicit conversion to string
                    if not isinstance(value, (str, bytes, bytearray)):
                        value = str(value)
                    if isinstance(value, str) and self._encoding:
                        value = value.encode(self._encoding)
                    if (datatype in [SQLDataType.TEXT, SQLDataType.VARYING]
                        and len(value) > length):
                        raise ValueError(f"Value of parameter ({i}) is too long,"
                                         f" expected {length}, found {len(value)}")
                    memmove(buf_addr + offset, value, len(value))
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
                    memmove(buf_addr + offset, value.to_bytes(length, 'little', signed=True), length)
                elif datatype == SQLDataType.DATE:
                    memmove(buf_addr + offset, _util.encode_date(value).to_bytes(length, 'little'), length)
                elif datatype == SQLDataType.TIME:
                    memmove(buf_addr + offset, _util.encode_time(value).to_bytes(length, 'little'), length)
                elif datatype == SQLDataType.TIME_TZ:
                    memmove(buf_addr + offset, _util.encode_time_tz(value), length)
                elif datatype == SQLDataType.TIMESTAMP:
                    memmove(buf_addr + offset, _encode_timestamp(value), length)
                elif datatype == SQLDataType.TIMESTAMP_TZ:
                    memmove(buf_addr + offset, _util.encode_timestamp_tz(value), length)
                elif datatype == SQLDataType.DEC16:
                    memmove(buf_addr + offset, byref(_util.get_decfloat16().from_str(str(value))), length)
                elif datatype == SQLDataType.DEC34:
                    memmove(buf_addr + offset, _util.get_decfloat34().from_str(str(value)), length)
                elif datatype == SQLDataType.INT128:
                    memmove(buf_addr + offset, _util.get_int128().from_str(str(value), in_meta.get_scale(i)), length)
                elif datatype == SQLDataType.FLOAT:
                    memmove(buf_addr + offset, struct.pack('f', value), length)
                elif datatype == SQLDataType.DOUBLE:
                    memmove(buf_addr + offset, struct.pack('d', value), length)
                elif datatype == SQLDataType.BOOLEAN:
                    memmove(buf_addr + offset, (1 if value else 0).to_bytes(length, 'little'), length)
                elif datatype == SQLDataType.BLOB:
                    blobid = a.ISC_QUAD(0, 0)
                    if hasattr(value, 'read'):
                        # It seems we've got file-like object, use stream BLOB
                        blob_buf = _create_blob_buffer()
                        blob: iBlob = self._connection._att.create_blob(self._transaction._tra,
                                                                        blobid, _bpb_stream)
                        try:
                            memmove(buf_addr + offset, addressof(blobid), length)
                            while value_chunk := value.read(MAX_BLOB_SEGMENT_SIZE):
                                blob_buf.raw = value_chunk.encode(self._encoding) if isinstance(value_chunk, str) else value_chunk
                                blob.put_segment(len(value_chunk), blob_buf)
                                memset(blob_buf, 0, MAX_BLOB_SEGMENT_SIZE)
                        finally:
                            blob.close()
                            del blob_buf
                    else:
                        # Non-stream BLOB
                        if isinstance(value, str):
                            if in_meta.get_subtype(i) == 1:
                                value = value.encode(self._encoding)
                            else:
                                raise TypeError('String value is not'
                                                ' acceptable type for'
                                                ' a non-textual BLOB column.')
                        blob_buf = create_string_buffer(value)
                        blob: iBlob = self._connection._att.create_blob(self._transaction._tra,
                                                                        blobid)
                        try:
                            memmove(buf_addr + offset, addressof(blobid), length)
                            total_size = len(value)
                            bytes_written_so_far = 0
                            bytes_to_write_this_time = MAX_BLOB_SEGMENT_SIZE
                            while bytes_written_so_far < total_size:
                                if (total_size - bytes_written_so_far) < MAX_BLOB_SEGMENT_SIZE:
                                    bytes_to_write_this_time = (total_size - bytes_written_so_far)
                                blob.put_segment(bytes_to_write_this_time,
                                                 addressof(blob_buf) + bytes_written_so_far)
                                bytes_written_so_far += bytes_to_write_this_time
                        finally:
                            blob.close()
                            del blob_buf
                elif datatype == SQLDataType.ARRAY:
                    arrayid = a.ISC_QUAD(0, 0)
                    arrayid_ptr = pointer(arrayid)
                    arraydesc = a.ISC_ARRAY_DESC(0)
                    isc_status = a.ISC_STATUS_ARRAY()
                    db_handle = a.FB_API_HANDLE(0)
                    tr_handle = a.FB_API_HANDLE(0)
                    relname = in_meta.get_relation(i).encode(self._encoding)
                    sqlname = in_meta.get_field(i).encode(self._encoding)
                    api = a.get_api()
                    api.fb_get_database_handle(isc_status, db_handle, self._connection._att)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
                                                      isc_status,
                                                      "Error in Cursor._pack_input:fb_get_database_handle()")
                    api.fb_get_transaction_handle(isc_status, tr_handle, self._transaction._tra)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
                                                      isc_status,
                                                      "Error in Cursor._pack_input:fb_get_transaction_handle()")
                    sqlsubtype = self._connection._get_array_sqlsubtype(relname, sqlname)
                    api.isc_array_lookup_bounds(isc_status, db_handle, tr_handle,
                                                relname, sqlname, arraydesc)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
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
                    value_buffer = create_string_buffer(total_size)
                    tsize = a.ISC_LONG(total_size)
                    self._copy_list_to_db_array(value_size, value_type,
                                                sqlsubtype, value_scale,
                                                0, dimensions,
                                                value, value_buffer, 0)
                    api.isc_array_put_slice(isc_status, db_handle, tr_handle,
                                            arrayid_ptr, arraydesc,
                                            value_buffer, tsize)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
                                                      isc_status,
                                                      "Error in Cursor._pack_input:/isc_array_put_slice()")
                    memmove(buf_addr + offset, addressof(arrayid), length)
            #
            in_meta.add_ref() # Everything went just fine, so we keep the metadata past 'with'
        return (in_meta, in_buffer)
    def _unpack_output(self) -> Tuple:
        values = []
        buffer = self._stmt._out_buffer
        buf_addr = addressof(buffer)
        for desc in self._stmt._out_desc:
            value: Any = '<NOT_IMPLEMENTED>'
            if ord(buffer[desc.null_offset]) != 0:
                value = None
            else:
                datatype = desc.datatype
                offset = desc.offset
                length = desc.length
                if datatype == SQLDataType.TEXT:
                    value = string_at(buf_addr + offset, length)
                    if desc.charset != a.OCTETS:
                        value = value.decode(self._encoding)
                    # CHAR with multibyte encoding requires special handling
                    if desc.charset in (4, 69):  # UTF8 and GB18030
                        reallength = length // 4
                    elif desc.charset == 3:  # UNICODE_FSS
                        reallength = length // 3
                    else:
                        reallength = length
                    value = value[:reallength]
                elif datatype == SQLDataType.VARYING:
                    size = (0).from_bytes(string_at(buf_addr + offset, 2), 'little')
                    value = string_at(buf_addr + offset + 2, size)
                    if desc.charset != 1:
                        value = value.decode(self._encoding)
                elif datatype == SQLDataType.BOOLEAN:
                    value = bool((0).from_bytes(buffer[offset], 'little'))
                elif datatype in [SQLDataType.SHORT, SQLDataType.LONG, SQLDataType.INT64]:
                    value = (0).from_bytes(buffer[offset:offset + length], 'little', signed=True)
                    # It's scalled integer?
                    if desc.subtype or desc.scale:
                        value = decimal.Decimal(value) / _tenTo[abs(desc.scale)]
                elif datatype == SQLDataType.DATE:
                    value = _util.decode_date(buffer[offset:offset+length])
                elif datatype == SQLDataType.TIME:
                    value = _util.decode_time(buffer[offset:offset+length])
                elif datatype == SQLDataType.TIME_TZ:
                    value = _util.decode_time_tz(buffer[offset:offset+length])
                elif datatype == SQLDataType.TIMESTAMP:
                    value = datetime.datetime.combine(_util.decode_date(buffer[offset:offset+4]),
                                                      _util.decode_time(buffer[offset+4:offset+length]))
                elif datatype == SQLDataType.TIMESTAMP_TZ:
                    value = _util.decode_timestamp_tz(buffer[offset:offset+length])
                elif datatype == SQLDataType.INT128:
                    value = decimal.Decimal(_util.get_int128().to_str(a.FB_I128.from_buffer_copy(buffer[offset:offset+length]), desc.scale))
                elif datatype == SQLDataType.DEC16:
                    value = decimal.Decimal(_util.get_decfloat16().to_str(a.FB_DEC16.from_buffer_copy(buffer[offset:offset+length])))
                elif datatype == SQLDataType.DEC34:
                    value = decimal.Decimal(_util.get_decfloat34().to_str(a.FB_DEC34.from_buffer_copy(buffer[offset:offset+length])))
                elif datatype == SQLDataType.FLOAT:
                    value = struct.unpack('f', buffer[offset:offset+length])[0]
                elif datatype == SQLDataType.DOUBLE:
                    value = struct.unpack('d', buffer[offset:offset+length])[0]
                elif datatype == SQLDataType.BLOB:
                    val = buffer[offset:offset+length]
                    blobid = a.ISC_QUAD((0).from_bytes(val[:4], 'little'),
                                        (0).from_bytes(val[4:], 'little'))
                    blob = self._connection._att.open_blob(self._transaction._tra, blobid, _bpb_stream)
                    # Get BLOB total length and max. size of segment
                    blob_length = blob.get_info2(BlobInfoCode.TOTAL_LENGTH)
                    segment_size = blob.get_info2(BlobInfoCode.MAX_SEGMENT)
                    # Check if stream BLOB is requested instead materialized one
                    if ((self.stream_blobs and (desc.alias if desc.alias != desc.field else desc.field) in self.stream_blobs)
                        or (blob_length > self.stream_blob_threshold)):
                        # Stream BLOB
                        value = BlobReader(blob, blobid, desc.subtype, blob_length,
                                           segment_size, self._encoding, self)
                        self.__blob_readers.add(value)
                    else:
                        # Materialized BLOB
                        try:
                            # Load BLOB
                            blob_value = create_string_buffer(blob_length)
                            bytes_read = 0
                            bytes_actually_read = a.Cardinal(0)
                            while bytes_read < blob_length:
                                blob.get_segment(min(segment_size, blob_length - bytes_read),
                                                 byref(blob_value, bytes_read),
                                                 bytes_actually_read)
                                bytes_read += bytes_actually_read.value
                            # Finalize value
                            value = blob_value.raw
                            if desc.subtype == 1:
                                value = value.decode(self._encoding)
                        finally:
                            blob.close()
                            del blob_value
                elif datatype == SQLDataType.ARRAY:
                    value = []
                    val = buffer[offset:offset+length]
                    arrayid = a.ISC_QUAD((0).from_bytes(val[:4], 'little'),
                                         (0).from_bytes(val[4:], 'little'))
                    arraydesc = a.ISC_ARRAY_DESC(0)
                    isc_status = a.ISC_STATUS_ARRAY()
                    db_handle = a.FB_API_HANDLE(0)
                    tr_handle = a.FB_API_HANDLE(0)
                    relname = desc.relation.encode(self._encoding)
                    sqlname = desc.field.encode(self._encoding)
                    api = a.get_api()
                    api.fb_get_database_handle(isc_status, db_handle, self._connection._att)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
                                                      isc_status,
                                                      "Error in Cursor._unpack_output:fb_get_database_handle()")
                    api.fb_get_transaction_handle(isc_status, tr_handle, self._transaction._tra)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
                                                      isc_status,
                                                      "Error in Cursor._unpack_output:fb_get_transaction_handle()")
                    sqlsubtype = self._connection._get_array_sqlsubtype(relname, sqlname)
                    api.isc_array_lookup_bounds(isc_status, db_handle, tr_handle,
                                                relname, sqlname, arraydesc)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
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
                    value_buffer = create_string_buffer(total_size)
                    tsize = a.ISC_LONG(total_size)
                    api.isc_array_get_slice(isc_status, db_handle, tr_handle,
                                            arrayid, arraydesc,
                                            value_buffer, tsize)
                    if a.db_api_error(isc_status):  # pragma: no cover
                        raise a.exception_from_status(DatabaseError,
                                                      isc_status,
                                                      "Error in Cursor._unpack_output:isc_array_get_slice()")
                    (value, bufpos) = self._extract_db_array_to_list(value_size,
                                                                     value_type,
                                                                     sqlsubtype,
                                                                     value_scale,
                                                                     0, dimensions,
                                                                     value_buffer, 0)
            values.append(value)
        return tuple(values)
    def _fetchone(self) -> Optional[Tuple]:
        if self._executed:
            if self._stmt._out_cnt == 0:
                return None
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
    def _execute(self, operation: Union[str, Statement],
                 parameters: Sequence=None, flags: CursorFlag=CursorFlag.NONE) -> None:
        if not self._transaction.is_active():
            self._transaction.begin()
        if isinstance(operation, Statement):
            if operation._connection() is not self._connection:
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
    def callproc(self, proc_name: str, parameters: Sequence=None) -> None:
        """Executes a stored procedure with the given name.

        Arguments:
            proc_name: Stored procedure name.
            parameters: Sequence of parameters. Must contain one entry for each argument
                        that the procedure expects.

        .. note::

           If stored procedure does have output parameters, you must retrieve their values
           saparatelly by `.Cursor.fetchone()` call. This method is not very convenient,
           but conforms to Python DB API 2.0. If you don't require conformance to Python
           DB API, it's recommended to use more convenient method `.Cursor.call_procedure()`
           instead.
        """
        params = [] if parameters is None else parameters
        sql = ('EXECUTE PROCEDURE ' + proc_name + ' '
               + ','.join('?' * len(params)))
        self.execute(sql, params)
    def call_procedure(self, proc_name: str, parameters: Sequence=None) -> Optional[Tuple]:
        """Executes a stored procedure with the given name.

        Arguments:
            proc_name: Stored procedure name.
            parameters: Sequence of parameters. Must contain one entry for each argument
                        that the procedure expects.

        Returns:
            None or tuple with values returned by stored procedure.
        """
        self.callproc(proc_name, parameters)
        return self.fetchone() if self._stmt._out_cnt > 0 else None
    def set_cursor_name(self, name: str) -> None:
        """Sets name for the SQL cursor.

        Arguments:
            name: Cursor name.
        """
        if not self._executed:
            raise InterfaceError("Cannot set name for cursor has not yet "
                                 "executed a statement")
        if self._name:
            raise InterfaceError("Cursor's name has already been declared in"
                                 " context of currently executed statement")
        self._stmt._istmt.set_cursor_name(name)
        self._name = name
    def prepare(self, operation: str) -> Statement:
        """Creates prepared statement for repeated execution.

        Arguments:
            operation: SQL command.
        """
        return self._connection._prepare(operation, self._transaction)
    def open(self, operation: Union[str, Statement], parameters: Sequence[Any]=None) -> Cursor:
        """Executes SQL command or prepared `Statement` as scrollable.

        Starts new transaction if transaction manager associated with cursor is not active.

        Arguments:
            operation: SQL command or prepared `Statement`.
            parameters: Sequence of parameters. Must contain one entry for each argument
                        that the operation expects.

        Note:
            If `operation` is a string with SQL command that is exactly the same as the
            last executed command, the internally prepared `Statement` from last execution
            is reused.

            If cursor is open, it's closed before new statement is executed.
        """
        self._execute(operation, parameters, CursorFlag.SCROLLABLE)
    def execute(self, operation: Union[str, Statement], parameters: Sequence[Any]=None) -> Cursor:
        """Executes SQL command or prepared `Statement`.

        Starts new transaction if transaction manager associated with cursor is not active.

        Arguments:
            operation: SQL command or prepared `Statement`.
            parameters: Sequence of parameters. Must contain one entry for each argument
                        that the operation expects.

        Returns:
            `self` so call to execute could be used as iterator over returned rows.

        Note:
            If `operation` is a string with SQL command that is exactly the same as the
            last executed command, the internally prepared `Statement` from last execution
            is reused.

            If cursor is open, it's closed before new statement is executed.
        """
        self._execute(operation, parameters)
        return self
    def executemany(self, operation: Union[str, Statement],
                    seq_of_parameters: Sequence[Sequence[Any]]) -> None:
        """Executes SQL command or prepared statement against all parameter
        sequences found in the sequence `seq_of_parameters`.

        Starts new transaction if transaction manager associated with cursor is not active.

        Arguments:
            operation: SQL command or prepared `Statement`.
            seq_of_parameters: Sequence of sequences of parameters. Must contain
                               one sequence of parameters for each execution
                               that has one entry for each argument that the
                               operation expects.

        Note:
            This function simply calls `.execute` in a loop, feeding it with
            parameters from `seq_of_parameters`. Because `.execute` reuses the statement,
            calling `executemany` is equally efective as direct use of prepared `Statement`
            and calling `execute` in a loop directly in application.
        """
        for parameters in seq_of_parameters:
            self.execute(operation, parameters)
    def close(self) -> None:
        """Close the cursor and release all associated resources.

        The result set (if any) from last executed statement is released, and if executed
        `Statement` was not supplied externally, it's released as well.

        Note:
            The closed cursor could be used to execute further SQL commands.
        """
        self._clear()
        if self._stmt is not None:
            if self.__internal:
                self._stmt.free()
            self._stmt = None
    def fetchone(self) -> Tuple:
        """Fetch the next row of a query result set.
        """
        if self._stmt:
            return self._fetchone()
        else:
            raise InterfaceError("Cannot fetch from cursor that did not executed a statement.")
    def fetchmany(self, size: int=None) -> List[Tuple]:
        """Fetch the next set of rows of a query result, returning a sequence of
        sequences (e.g. a list of tuples).

        An empty sequence is returned when no more rows are available. The number of rows
        to fetch per call is specified by the parameter. If it is not given, the cursor’s
        `.arraysize` determines the number of rows to be fetched. The method does try to
        fetch as many rows as indicated by the size parameter. If this is not possible due
        to the specified number of rows not being available, fewer rows may be returned.

        Arguments:
            size: The number of rows to fetch.
        """
        if size is None:
            size = self.arraysize
        result = []
        for _ in range(size):
            if (row := self.fetchone()) is not None:
                result.append(row)
            else:
                break
        return result
    def fetchall(self) -> List[Tuple]:
        """Fetch all remaining rows of a query result set.
        """
        return [row for row in self]
    def fetch_next(self) -> Optional[Tuple]:
        """Fetch the next row of a scrollable query result set.

        Returns None if there is no row to be fetched.
        """
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_next(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_prior(self) -> Optional[Tuple]:
        """Fetch the previous row of a scrollable query result set.

        Returns None if there is no row to be fetched.
        """
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_prior(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_first(self) -> Optional[Tuple]:
        """Fetch the first row of a scrollable query result set.

        Returns None if there is no row to be fetched.
        """
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_first(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_last(self) -> Optional[Tuple]:
        """Fetch the last row of a scrollable query result set.

        Returns None if there is no row to be fetched.
        """
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_last(self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_absolute(self, position: int) -> Optional[Tuple]:
        """Fetch the row of a scrollable query result set specified by absolute position.

        Returns None if there is no row to be fetched.

        Arguments:
            position: Absolute position number of row in result set.
        """
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_absolute(position, self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def fetch_relative(self, offset: int) -> Optional[Tuple]:
        """Fetch the row of a scrollable query result set specified by relative position.

        Returns None if there is no row to be fetched.

        Arguments:
            offset: Relative position number of row in result set. Negative value refers
                    to previous row, positive to next row.
        """
        assert self._result is not None
        self._last_fetch_status = self._result.fetch_relative(offset, self._stmt._out_buffer)
        if self._last_fetch_status == StateResult.OK:
            return self._unpack_output()
        else:
            return None
    def setinputsizes(self, sizes: Sequence[Type]) -> None:
        """Required by Python DB API 2.0, but pointless for Firebird, so it does nothing.
        """
        pass
    def setoutputsize(self, size: int, column: int=None) -> None:
        """Required by Python DB API 2.0, but pointless for Firebird, so it does nothing.
        """
        pass
    def is_closed(self) -> bool:
        """Returns True if cursor is closed.
        """
        return self._stmt is None
    def is_eof(self) -> bool:
        """Returns True is scrollable cursor is positioned at the end.
        """
        assert self._result is not None
        return self._result.is_eof()
    def is_bof(self) -> bool:
        """Returns True is scrollable cursor is positioned at the beginning.
        """
        assert self._result is not None
        return self._result.is_bof()
    # Properties
    @property
    def connection(self) -> Connection:
        """Connection associated with cursor.
        """
        return self._connection
    @property
    def log_context(self) -> Connection:
        return self._connection
    @property
    def statement(self) -> Statement:
        """Executed `Statement` or None if cursor does not executed a statement yet.
        """
        return self._stmt
    @property
    def description(self) -> Tuple[DESCRIPTION]:
        """Tuple of DESCRIPTION tuples (with 7-items).

        Each of these tuples contains information describing one result column:
        (name, type_code, display_size, internal_size, precision, scale, null_ok)
        """
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
    @property
    def affected_rows(self) -> int:
        """Specifies the number of rows that the last `.execute` or `.open`
        produced (for DQL statements like select) or affected (for DML statements
        like update or insert ).

        The attribute is -1 in case no statement was executed on the cursor
        or the rowcount of the last operation is not determinable by the interface.

        Note:
            The database engine's own support for the determination of
            “rows affected”/”rows selected” is quirky. The database engine only
            supports the determination of rowcount for INSERT, UPDATE, DELETE,
            and SELECT statements. When stored procedures become involved, row
            count figures are usually not available to the client.
        """
        if self._stmt is None:
            return -1
        result = -1
        if (self._executed and self._stmt.type in [StatementType.SELECT,
                                                   StatementType.INSERT,
                                                   StatementType.UPDATE,
                                                   StatementType.DELETE]):
            info = create_string_buffer(64)
            self._stmt._istmt.get_info(bytes([23, 1]), info) # bytes(isc_info_sql_records, isc_info_end)
            if ord(info[0]) != 23:  # pragma: no cover
                raise InterfaceError("Cursor.affected_rows:\n"
                                     "first byte must be 'isc_info_sql_records'")
            res_walk = 3
            while ord(info[res_walk]) != isc_info_end:
                cur_count_type = ord(info[res_walk])
                res_walk += 1
                size = (0).from_bytes(info[res_walk:res_walk + 2], 'little')
                res_walk += 2
                count = (0).from_bytes(info[res_walk:res_walk + size], 'little')
                if ((cur_count_type == 13 and self._stmt.type == StatementType.SELECT)
                    or (cur_count_type == 14 and self._stmt.type == StatementType.INSERT)
                    or (cur_count_type == 15 and self._stmt.type == StatementType.UPDATE)
                    or (cur_count_type == 16 and self._stmt.type == StatementType.DELETE)):
                    result = count
                res_walk += size
        return result
    rowcount = affected_rows
    @property
    def transaction(self) -> TransactionManager:
        """Transaction manager associated with cursor.
        """
        return self._transaction
    @property
    def name(self) -> str:
        """Name set for cursor.
        """
        return self._name

class ServerInfoProvider(InfoProvider):
    """Provides access to information about attached server.

    Important:
       Do NOT create instances of this class directly! Use `Server.info` property to access
       the instance already bound to connectected server.
    """
    def __init__(self, charset: str, server: Server):
        super().__init__(charset)
        self._srv: Server = weakref.ref(server)
        # Get Firebird engine version
        self.__version = _engine_version_provider.get_server_version(self._srv)
        x = self.__version.split('.')
        self.__engine_version = float(f'{x[0]}.{x[1]}')
    def _close(self) -> None:
        """Drops the association with attached server.
        """
        self._srv = None
    def _acquire(self, request: bytes) -> None:
        """Acquires information from associated attachment. Information is stored in native
        format in `response` buffer.

        Arguments:
            request: Data specifying the required information.
        """
        self._srv()._svc.query(None, request, self.response.raw)
    def get_info(self, info_code: SrvInfoCode) -> Any:
        """Returns requested information from connected server.

        Arguments:
            info_code: A code specifying the required information.

        Returns:
            The data type of returned value depends on information required.
        """
        if info_code in self._cache:
            return self._cache[info_code]
        self.response.clear()
        request = bytes([info_code])
        self._get_data(request)
        tag = self.response.get_tag()
        if (tag != info_code.value):
            if tag == isc_info_error:  # pragma: no cover
                raise InterfaceError("An error response was received")
            else:  # pragma: no cover
                raise InterfaceError("Result code does not match request code")
        #
        if info_code in (SrvInfoCode.VERSION, SrvInfoCode.CAPABILITIES, SrvInfoCode.RUNNING):
            result = self.response.read_int()
        elif info_code in (SrvInfoCode.SERVER_VERSION, SrvInfoCode.IMPLEMENTATION,
                           SrvInfoCode.GET_ENV, SrvInfoCode.GET_ENV_MSG,
                           SrvInfoCode.GET_ENV_LOCK, SrvInfoCode.USER_DBPATH):
            result = self.response.read_sized_string(encoding=self._srv().encoding)
        elif info_code == SrvInfoCode.SRV_DB_INFO:
            num_attachments = -1
            databases = []
            while not self.response.is_eof():
                tag = self.response.get_tag()
                if tag == SrvInfoCode.TIMEOUT:
                    return None
                elif tag == SrvDbInfoOption.ATT:
                    num_attachments = self.response.read_short()
                elif tag == SPBItem.DBNAME:
                    databases.append(self.response.read_sized_string(encoding=self._srv().encoding))
                elif tag == SrvDbInfoOption.DB:
                    self.response.read_short()
            result = (num_attachments, databases)
        if self.response.get_tag() != isc_info_end:  # pragma: no cover
            raise InterfaceError("Malformed result buffer (missing isc_info_end item)")
        # cache
        if info_code in (SrvInfoCode.SERVER_VERSION, SrvInfoCode.VERSION,
                         SrvInfoCode.IMPLEMENTATION, SrvInfoCode.GET_ENV,
                         SrvInfoCode.USER_DBPATH, SrvInfoCode.GET_ENV_LOCK,
                         SrvInfoCode.GET_ENV_MSG, SrvInfoCode.CAPABILITIES):
            self._cache[info_code] = result
        return result
    def get_log(self, callback: CB_OUTPUT_LINE=None) -> None:
        """Request content of Firebird Server log. **(ASYNC service)**

        Arguments:
            callback: Function to call back with each output line.
        """
        assert self._srv()._svc is not None
        self._srv()._reset_output()
        self._srv()._svc.start(bytes([ServerAction.GET_FB_LOG]))
        if callback:
            for line in self._srv():
                callback(line)
    @property
    def version(self) -> str:
        """Firebird version as SEMVER string.
        """
        return self.__version
    @property
    def engine_version(self) -> float:
        """Firebird version as <major>.<minor> float number.
        """
        return self.__engine_version
    @property
    def manager_version(self) -> int:
        """Service manager version.
        """
        return self.get_info(SrvInfoCode.VERSION)
    @property
    def architecture(self) -> str:
        """Server implementation description.
        """
        return self.get_info(SrvInfoCode.IMPLEMENTATION)
    @property
    def home_directory(self) -> str:
        """Server home directory.
        """
        return self.get_info(SrvInfoCode.GET_ENV)
    @property
    def security_database(self) -> str:
        """Path to security database.
        """
        return self.get_info(SrvInfoCode.USER_DBPATH)
    @property
    def lock_directory(self) -> str:
        """Directory with lock file(s).
        """
        return self.get_info(SrvInfoCode.GET_ENV_LOCK)
    @property
    def message_directory(self) -> str:
        """Directory with message file(s).
        """
        return self.get_info(SrvInfoCode.GET_ENV_MSG)
    @property
    def capabilities(self) -> ServerCapability:
        """Server capabilities.
        """
        return ServerCapability(self.get_info(SrvInfoCode.CAPABILITIES))
    @property
    def connection_count(self) -> int:
        """Number of database attachments.
        """
        return self.get_info(SrvInfoCode.SRV_DB_INFO)[0]
    @property
    def attached_databases(self) -> List[str]:
        """List of attached databases.
        """
        return self.get_info(SrvInfoCode.SRV_DB_INFO)[1]

class ServerServiceProvider:
    """Base class for server service providers.
    """
    def __init__(self, server: Server):
        self._srv: Server = weakref.ref(server)
    def _close(self) -> None:
        self._srv = None

class ServerDbServices3(ServerServiceProvider):
    """Database-related actions and services [Firebird 3+].
    """
    def get_statistics(self, *, database: FILESPEC,
                       flags: SrvStatFlag=SrvStatFlag.DEFAULT, role: str=None,
                       tables: Sequence[str]=None, callback: CB_OUTPUT_LINE=None) -> None:
        """Return database statistics produced by gstat utility. **(ASYNC service)**

        Arguments:
            database: Database specification or alias.
            flags: Flags indicating which statistics shall be collected.
            role: SQL ROLE name passed to gstat.
            tables: List of database tables whose statistics are to be collected.
            callback: Function to call back with each output line.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.DB_STATS)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            spb.insert_int(SPBItem.OPTIONS, flags)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            if tables is not None:
                for table in tables:
                    spb.insert_string(64, table, encoding=self._srv().encoding) # isc_spb_sts_table = 64
            self._srv()._svc.start(spb.get_buffer())
        if callback:
            for line in self._srv():
                callback(line)
    def backup(self, *, database: FILESPEC, backup: Union[FILESPEC, Sequence[FILESPEC]],
               backup_file_sizes: Sequence[int]=(),
               flags: SrvBackupFlag=SrvBackupFlag.NONE, role: str=None,
               callback: CB_OUTPUT_LINE=None, stats: str=None,
               verbose: bool=False, verbint: int=None, skip_data: str=None,
               include_data: str=None, keyhoder: str=None, keyname: str=None,
               crypt: str=None) -> None:
        """Request logical (GBAK) database backup. **(ASYNC service)**

        Arguments:
            database: Database file specification or alias.
            backup: Backup filespec, or list of backup file specifications.
            backup_file_sizes: List of file sizes for backup files.
            flags: Backup options.
            role: SQL ROLE name passed to gbak.
            callback: Function to call back with each output line.
            stats: Backup statistic options (TDWR).
            verbose: Whether output should be verbose or not.
            verbint: Verbose information with explicit interval (number of records)
            skip_data: String with table names whose data should be excluded from backup.
            include_data: String with table names whose data should be included into backup [Firebird 4].
            keyholder: Keyholder name [Firebird 4]
            keyname: Key name [Firebird 4]
            crypt: Encryption specification [Firebird 4]
        """
        if isinstance(backup, (str, Path)):
            backup = [backup]
            assert len(backup_file_sizes) == 0
        else:
            assert len(backup) >= 1
            assert len(backup) == len(backup_file_sizes) - 1
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.BACKUP)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            for filename, size in itertools.zip_longest(backup, backup_file_sizes):
                spb.insert_string(SrvBackupOption.FILE, str(filename), encoding=self._srv().encoding)
                if size is not None:
                    spb.insert_int(SrvBackupOption.LENGTH, size)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            if skip_data is not None:
                spb.insert_string(SrvBackupOption.SKIP_DATA, skip_data)
            if include_data is not None:
                spb.insert_string(SrvBackupOption.INCLUDE_DATA, include_data)
            if keyhoder is not None:
                spb.insert_string(SrvBackupOption.KEYHOLDER, keyhoder)
            if keyname is not None:
                spb.insert_string(SrvBackupOption.KEYNAME, keyname)
            if crypt is not None:
                spb.insert_string(SrvBackupOption.CRYPT, crypt)
            spb.insert_int(SPBItem.OPTIONS, flags)
            if verbose:
                spb.insert_tag(SPBItem.VERBOSE)
            if verbint is not None:
                spb.insert_int(SPBItem.VERBINT, verbint)
            if stats:
                spb.insert_string(SrvBackupOption.STAT, stats)
            self._srv()._svc.start(spb.get_buffer())
        if callback:
            for line in self._srv():
                callback(line)
    def restore(self, *, backup: Union[FILESPEC, Sequence[FILESPEC]],
                database: Union[FILESPEC, Sequence[FILESPEC]],
                db_file_pages: Sequence[int]=(),
                flags: SrvRestoreFlag=SrvRestoreFlag.CREATE, role: str=None,
                callback: CB_OUTPUT_LINE=None, stats: str=None,
                verbose: bool=False, verbint: int=None, skip_data: str=None,
                page_size: int=None, buffers: int=None,
                access_mode: DbAccessMode=DbAccessMode.READ_WRITE, include_data: str=None,
                keyhoder: str=None, keyname: str=None, crypt: str=None,
                replica_mode: ReplicaMode=None) -> None:
        """Request database restore from logical (GBAK) backup. **(ASYNC service)**

        Arguments:
            backup: Backup filespec, or list of backup file specifications.
            database: Database specification or alias, or list of those.
            db_file_pages: List of database file sizes (in pages).
            flags: Restore options.
            role: SQL ROLE name passed to gbak.
            callback: Function to call back with each output line.
            stats: Restore statistic options (TDWR).
            verbose: Whether output should be verbose or not.
            verbint: Verbose information with explicit interval (number of records)
            skip_data: String with table names whose data should be excluded from restore.
            page_size: Page size for restored database.
            buffers: Cache size for restored database.
            access_mode: Restored database access mode (R/W or R/O).
            include_data: String with table names whose data should be included into backup [Firebird 4].
            keyholder: Keyholder name [Firebird 4]
            keyname: Key name [Firebird 4]
            crypt: Encryption specification [Firebird 4]
            replica_mode: Replica mode for restored database [Firebird 4]
        """
        if isinstance(backup, (str, Path)):
            backup = [backup]
        if isinstance(database, (str, Path)):
            database = [database]
            assert len(db_file_pages) == 0
        else:
            assert len(database) >= 1
            assert len(database) - 1 == len(db_file_pages)
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.RESTORE)
            for filename in backup:
                spb.insert_string(SrvRestoreOption.FILE, str(filename), encoding=self._srv().encoding)
            for filename, size in itertools.zip_longest(database, db_file_pages):
                spb.insert_string(SPBItem.DBNAME, str(filename), encoding=self._srv().encoding)
                if size is not None:
                    spb.insert_int(SrvRestoreOption.LENGTH, size)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            if page_size is not None:
                spb.insert_int(SrvRestoreOption.PAGE_SIZE, page_size)
            if buffers is not None:
                spb.insert_int(SrvRestoreOption.BUFFERS, buffers)
            spb.insert_bytes(SrvRestoreOption.ACCESS_MODE, bytes([access_mode]))
            if skip_data is not None:
                spb.insert_string(SrvRestoreOption.SKIP_DATA, skip_data, encoding=self._srv().encoding)
            if include_data is not None:
                spb.insert_string(SrvRestoreOption.INCLUDE_DATA, include_data, encoding=self._srv().encoding)
            if keyhoder is not None:
                spb.insert_string(SrvRestoreOption.KEYHOLDER, keyhoder)
            if keyname is not None:
                spb.insert_string(SrvRestoreOption.KEYNAME, keyname)
            if crypt is not None:
                spb.insert_string(SrvRestoreOption.CRYPT, crypt)
            if replica_mode is not None:
                spb.insert_int(SrvRestoreOption.REPLICA_MODE, replica_mode.value)
            spb.insert_int(SPBItem.OPTIONS, flags)
            if verbose:
                spb.insert_tag(SPBItem.VERBOSE)
            if verbint is not None:
                spb.insert_int(SPBItem.VERBINT, verbint)
            if stats:
                spb.insert_string(SrvRestoreOption.STAT, stats)
            self._srv()._svc.start(spb.get_buffer())
        if callback:
            for line in self._srv():
                callback(line)
    def local_backup(self, *, database: FILESPEC, backup_stream: BinaryIO,
                     flags: SrvBackupFlag=SrvBackupFlag.NONE, role: str=None,
                     skip_data: str=None, include_data: str=None, keyhoder: str=None,
                     keyname: str=None, crypt: str=None) -> None:
        """Request logical (GBAK) database backup into local byte stream. **(SYNC service)**

        Arguments:
            database: Database specification or alias.
            backup_stream: Binary stream to which the backup is to be written.
            flags: Backup options.
            role: SQL ROLE name passed to gbak.
            skip_data: String with table names whose data should be excluded from backup.
            include_data: String with table names whose data should be included into backup [Firebird 4].
            keyholder: Keyholder name [Firebird 4]
            keyname: Key name [Firebird 4]
            crypt: Encryption specification [Firebird 4]
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.BACKUP)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            spb.insert_string(SrvBackupOption.FILE, 'stdout')
            spb.insert_int(SPBItem.OPTIONS, flags)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            if skip_data is not None:
                spb.insert_string(SrvBackupOption.SKIP_DATA, skip_data,
                                  encoding=self._srv().encoding)
            if include_data is not None:
                spb.insert_string(SrvBackupOption.INCLUDE_DATA, include_data,
                                  encoding=self._srv().encoding)
            if keyhoder is not None:
                spb.insert_string(SrvBackupOption.KEYHOLDER, keyhoder)
            if keyname is not None:
                spb.insert_string(SrvBackupOption.KEYNAME, keyname)
            if crypt is not None:
                spb.insert_string(SrvBackupOption.CRYPT, crypt)
            self._srv()._svc.start(spb.get_buffer())
        while not self._srv()._eof:
            backup_stream.write(self._srv()._read_next_binary_output())
    def local_restore(self, *, backup_stream: BinaryIO,
                      database: Union[FILESPEC, Sequence[FILESPEC]],
                      db_file_pages: Sequence[int]=(),
                      flags: SrvRestoreFlag=SrvRestoreFlag.CREATE, role: str=None,
                      skip_data: str=None, page_size: int=None, buffers: int=None,
                      access_mode: DbAccessMode=DbAccessMode.READ_WRITE,
                      include_data: str=None, keyhoder: str=None, keyname: str=None,
                      crypt: str=None, replica_mode: ReplicaMode=None) -> None:
        """Request database restore from logical (GBAK) backup stored in local byte stream.
        **(SYNC service)**

        Arguments:
            backup_stream: Binary stream with the backup.
            database: Database specification or alias, or list of those.
            db_file_pages: List of database file sizes (in pages).
            flags: Restore options.
            role: SQL ROLE name passed to gbak.
            skip_data: String with table names whose data should be excluded from restore.
            page_size: Page size for restored database.
            buffers: Cache size for restored database.
            access_mode: Restored database access mode (R/W or R/O).
            include_data: String with table names whose data should be included into backup [Firebird 4].
            keyholder: Keyholder name [Firebird 4]
            keyname: Key name [Firebird 4]
            crypt: Encryption specification [Firebird 4]
            replica_mode: Replica mode for restored database [Firebird 4]
        """
        if isinstance(database, (str, Path)):
            database = [database]
            assert len(db_file_pages) == 0
        else:
            assert len(database) >= 1
            assert len(database) == len(db_file_pages) - 1
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.RESTORE)
            spb.insert_string(SrvRestoreOption.FILE, 'stdin')
            for filename, size in itertools.zip_longest(database, db_file_pages):
                spb.insert_string(SPBItem.DBNAME, str(filename), encoding=self._srv().encoding)
                if size is not None:
                    spb.insert_int(SrvRestoreOption.LENGTH, size)
            if page_size is not None:
                spb.insert_int(SrvRestoreOption.PAGE_SIZE, page_size)
            if buffers is not None:
                spb.insert_int(SrvRestoreOption.BUFFERS, buffers)
            spb.insert_bytes(SrvRestoreOption.ACCESS_MODE, bytes([access_mode]))
            if skip_data is not None:
                spb.insert_string(SrvRestoreOption.SKIP_DATA, skip_data,
                                  encoding=self._srv().encoding)
            if include_data is not None:
                spb.insert_string(SrvRestoreOption.INCLUDE_DATA, include_data,
                                  encoding=self._srv().encoding)
            if keyhoder is not None:
                spb.insert_string(SrvRestoreOption.KEYHOLDER, keyhoder)
            if keyname is not None:
                spb.insert_string(SrvRestoreOption.KEYNAME, keyname)
            if crypt is not None:
                spb.insert_string(SrvRestoreOption.CRYPT, crypt)
            if replica_mode is not None:
                spb.insert_int(SrvRestoreOption.REPLICA_MODE, replica_mode.value)
            spb.insert_int(SPBItem.OPTIONS, flags)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            self._srv()._svc.start(spb.get_buffer())
        #
        request_length = 0
        line = ''
        keep_going = True
        while keep_going:
            no_data = False
            self._srv().response.clear()
            if request_length > 0:
                request_length = min([request_length, 65500])
                raw = backup_stream.read(request_length)
                send = b''.join([SrvInfoCode.LINE.to_bytes(1, 'little'),
                                 len(raw).to_bytes(2, 'little'), raw,
                                 isc_info_end.to_bytes(1, 'little')])
            else:
                send = None
            self._srv()._svc.query(send, bytes([SrvInfoCode.STDIN, SrvInfoCode.LINE]),
                                   self._srv().response.raw)
            tag = self._srv().response.get_tag()
            while tag != isc_info_end:
                if tag == SrvInfoCode.STDIN:
                    request_length = self._srv().response.read_int()
                elif tag == SrvInfoCode.LINE:
                    line = self._srv().response.read_sized_string(encoding=self._srv().encoding)
                elif tag == isc_info_data_not_ready:
                    no_data = True
                else:  # pragma: no cover
                    raise InterfaceError(f"Service responded with error code: {tag}")
                tag = self._srv().response.get_tag()
            keep_going = no_data or request_length != 0 or len(line) > 0
    def nbackup(self, *, database: FILESPEC, backup: FILESPEC, level: int=0,
                direct: bool=None, flags: SrvNBackupFlag=SrvNBackupFlag.NONE,
                role: str=None, guid: str=None) -> None:
        """Perform physical (NBACKUP) database backup. **(SYNC service)**

        Arguments:
            database: Database specification or alias.
            backup: Backup file specification.
            level: Backup level.
            direct: Direct I/O override.
            flags: Backup options.
            role: SQL ROLE name passed to nbackup.
            guid: Database backup GUID.

        Important:
            Parameters `level` and `guid` are mutually exclusive. If `guid` is specified,
            then `level` value is ignored.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.NBAK)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            spb.insert_string(SrvNBackupOption.FILE, str(backup), encoding=self._srv().encoding)
            if guid is not None:
                spb.insert_string(SrvNBackupOption.GUID, guid)
            else:
                spb.insert_int(SrvNBackupOption.LEVEL, level)
            if direct is not None:
                spb.insert_string(SrvNBackupOption.DIRECT, 'ON' if direct else 'OFF')
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def nrestore(self, *, backups: Sequence[FILESPEC], database: FILESPEC,
                 direct: bool=False, flags: SrvNBackupFlag=SrvNBackupFlag.NONE,
                 role: str=None) -> None:
        """Perform restore from physical (NBACKUP) database backup.  **(SYNC service)**

        Arguments:
            backups: Backup file(s) specification.
            database: Database specification or alias.
            direct: Direct I/O override.
            flags: Restore options.
            role: SQL ROLE name passed to nbackup.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.NREST)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            for backup in backups:
                spb.insert_string(SrvNBackupOption.FILE, str(backup), encoding=self._srv().encoding)
            if direct is not None:
                spb.insert_string(SrvNBackupOption.DIRECT, 'ON' if direct else 'OFF')
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def set_default_cache_size(self, *, database: FILESPEC, size: int, role: str=None) -> None:
        """Set individual page cache size for database.

        Arguments:
            database: Database specification or alias.
            size: New value.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SrvPropertiesOption.PAGE_BUFFERS, size)
            self._srv()._svc.start(spb.get_buffer())
    def set_sweep_interval(self, *, database: FILESPEC, interval: int, role: str=None) -> None:
        """Set database sweep interval.

        Arguments:
            database: Database specification or alias.
            interval: New value.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SrvPropertiesOption.SWEEP_INTERVAL, interval)
            self._srv()._svc.start(spb.get_buffer())
    def set_space_reservation(self, *, database: FILESPEC, mode: DbSpaceReservation,
                              role: str=None) -> None:
        """Set space reservation for database.

        Arguments:
            database: Database specification or alias.
            mode: New value.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_bytes(SrvPropertiesOption.RESERVE_SPACE,
                             bytes([mode]))
            self._srv()._svc.start(spb.get_buffer())
    def set_write_mode(self, *, database: FILESPEC, mode: DbWriteMode, role: str=None) -> None:
        """Set database write mode (SYNC/ASYNC).

        Arguments:
            database: Database specification or alias.
            mode: New value.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_bytes(SrvPropertiesOption.WRITE_MODE,
                             bytes([mode]))
            self._srv()._svc.start(spb.get_buffer())
    def set_access_mode(self, *, database: FILESPEC, mode: DbAccessMode, role: str=None) -> None:
        """Set database access mode (R/W or R/O).

        Arguments:
            database: Database specification or alias.
            mode: New value.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_bytes(SrvPropertiesOption.ACCESS_MODE, bytes([mode]))
            self._srv()._svc.start(spb.get_buffer())
    def set_sql_dialect(self, *, database: FILESPEC, dialect: int, role: str=None) -> None:
        """Set database SQL dialect.

        Arguments:
            database: Database specification or alias.
            dialect: New value.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SrvPropertiesOption.SET_SQL_DIALECT, dialect)
            self._srv()._svc.start(spb.get_buffer())
    def activate_shadow(self, *, database: FILESPEC, role: str=None) -> None:
        """Activate database shadow.

        Arguments:
            database: Database specification or alias.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SPBItem.OPTIONS, SrvPropertiesFlag.ACTIVATE)
            self._srv()._svc.start(spb.get_buffer())
    def no_linger(self, *, database: FILESPEC, role: str=None) -> None:
        """Set one-off override for database linger.

        Arguments:
            database: Database specification or alias.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SPBItem.OPTIONS, SrvPropertiesFlag.NOLINGER)
            self._srv()._svc.start(spb.get_buffer())
    def shutdown(self, *, database: FILESPEC, mode: ShutdownMode,
                 method: ShutdownMethod, timeout: int, role: str=None) -> None:
        """Database shutdown.

        Arguments:
            database: Database specification or alias.
            mode: Shutdown mode.
            method: Shutdown method.
            timeout: Timeout for shutdown.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_bytes(SrvPropertiesOption.SHUTDOWN_MODE, bytes([mode]))
            spb.insert_int(method, timeout)
            self._srv()._svc.start(spb.get_buffer())
    def bring_online(self, *, database: FILESPEC, mode: OnlineMode=OnlineMode.NORMAL,
                     role: str=None) -> None:
        """Bring previously shut down database back online.

        Arguments:
            database: Database specification or alias.
            mode: Online mode.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_bytes(SrvPropertiesOption.ONLINE_MODE, bytes([mode]))
            self._srv()._svc.start(spb.get_buffer())
    def sweep(self, *, database: FILESPEC, role: str=None) -> None:
        """Perform database sweep operation.

        Arguments:
            database: Database specification or alias.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SPBItem.OPTIONS, SrvRepairFlag.SWEEP_DB)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def repair(self, *, database: FILESPEC, flags: SrvRepairFlag=SrvRepairFlag.REPAIR,
               role: str=None) -> bytes:
        """Perform database repair operation.  **(SYNC service)**

        Arguments:
            database: Database specification or alias.
            flags: Repair flags.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def validate(self, *, database: FILESPEC, include_table: str=None,
                 exclude_table: str=None, include_index: str=None,
                 exclude_index: str=None, lock_timeout: int=None, role: str=None,
                 callback: CB_OUTPUT_LINE=None) -> None:
        """Perform database validation. **(ASYNC service)**

        Arguments:
            database: Database specification or alias.
            flags: Repair flags.
            include_table: Regex pattern for table names to include in validation run.
            exclude_table: Regex pattern for table names to exclude in validation run.
            include_index: Regex pattern for index names to include in validation run.
            exclude_index: Regex pattern for index names to exclude in validation run.
            lock_timeout: Lock timeout (seconds), used to acquire locks for table to validate,
              default is 10 secs. 0 is no-wait, -1 is infinite wait.
            role: SQL ROLE name passed to gfix.
            callback: Function to call back with each output line.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.VALIDATE)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if include_table is not None:
                spb.insert_string(SrvValidateOption.INCLUDE_TABLE, include_table,
                                  encoding=self._srv().encoding)
            if exclude_table is not None:
                spb.insert_string(SrvValidateOption.EXCLUDE_TABLE, exclude_table,
                                  encoding=self._srv().encoding)
            if include_index is not None:
                spb.insert_string(SrvValidateOption.INCLUDE_INDEX, include_index,
                                  encoding=self._srv().encoding)
            if exclude_index is not None:
                spb.insert_string(SrvValidateOption.EXCLUDE_INDEX, exclude_index,
                                  encoding=self._srv().encoding)
            if lock_timeout is not None:
                spb.insert_int(SrvValidateOption.LOCK_TIMEOUT, lock_timeout)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            self._srv()._svc.start(spb.get_buffer())
        if callback:
            for line in self._srv():
                callback(line)
    def get_limbo_transaction_ids(self, *, database: FILESPEC) -> List[int]:
        """Returns list of transactions in limbo.

        Arguments:
            database: Database specification or alias.
        """
        #raise NotImplementedError
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction .REPAIR)
            spb.insert_string(SPBItem.DBNAME, str(database))
            spb.insert_int(SPBItem.OPTIONS, SrvRepairFlag.LIST_LIMBO_TRANS)
            self._srv()._svc.start(spb.get_buffer())
        self._srv()._reset_output()
        self._srv()._fetch_complex_info(bytes([SrvInfoCode.LIMBO_TRANS]))
        trans_ids = []
        while not self._srv().response.is_eof():
            tag = self._srv().response.get_tag()
            if tag == SrvInfoCode.TIMEOUT:
                return None
            elif tag == SrvInfoCode.LIMBO_TRANS:
                size = self._srv().response.read_short()
                while not self._srv().response.is_eof() and self._srv().response.pos < size:
                    tag = self._srv().response.get_tag()
                    if tag == SvcRepairOption.TRA_HOST_SITE:
                        site = self._srv().response.get_string()
                    elif tag == SvcRepairOption.TRA_STATE:
                        tag = self._srv().response.get_tag()
                        if tag == SvcRepairOption.TRA_STATE_LIMBO:
                            state = TransactionState.LIMBO
                        elif tag == SvcRepairOption.TRA_STATE_COMMIT:
                            state = TransactionState.COMMIT
                        elif tag == SvcRepairOption.TRA_STATE_ROLLBACK:
                            state = TransactionState.ROLLBACK
                        elif tag == SvcRepairOption.TRA_STATE_UNKNOWN:
                            state = TransactionState.UNKNOWN
                        else:
                            raise InterfaceError(f"Unknown transaction state {tag}")
                    elif tag == SvcRepairOption.TRA_REMOTE_SITE:
                        remote_site = self._srv().response.get_string()
                    elif tag == SvcRepairOption.TRA_DB_PATH:
                        db_path = self._srv().response.get_string()
                    elif tag == SvcRepairOption.TRA_ADVISE:
                        tag = self._srv().response.get_tag()
                        if tag == SvcRepairOption.TRA_ADVISE_COMMIT:
                            advise = TransactionState.COMMIT
                        elif tag == SvcRepairOption.TRA_ADVISE_ROLLBACK:
                            advise = TransactionState.ROLLBACK
                        elif tag == SvcRepairOption.TRA_ADVISE_UNKNOWN:
                            advise = TransactionState.UNKNOWN
                        else:
                            raise InterfaceError(f"Unknown transaction state {tag}")
                    elif tag == SvcRepairOption.MULTI_TRA_ID:
                        multi_id = self._srv().response.get_int()
                    elif tag == SvcRepairOption.SINGLE_TRA_ID:
                        single_id = self._srv().response.get_int()
                    elif tag == SvcRepairOption.TRA_ID:
                        tra_id = self._srv().response.get_int()
                    elif tag == SvcRepairOption.MULTI_TRA_ID_64:
                        multi_id = self._srv().response.get_int64()
                    elif tag == SvcRepairOption.SINGLE_TRA_ID_64:
                        single_id = self._srv().response.get_int64()
                    elif tag == SvcRepairOption.TRA_ID_64:
                        tra_id = self._srv().response.get_int64()
                    else:
                        raise InterfaceError(f"Unknown transaction state {tag}")
                    trans_ids.append(None)
        if self._srv().response.get_tag() != isc_info_end:
            raise InterfaceError("Malformed result buffer (missing isc_info_end item)")
        return trans_ids
    def commit_limbo_transaction(self, *, database: FILESPEC, transaction_id: int) -> None:
        """Resolve limbo transaction with commit.

        Arguments:
            database: Database specification or alias.
            transaction_id: ID of Transaction to resolve.
        """
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if transaction_id <= USHRT_MAX:
                spb.insert_int(SrvRepairOption.COMMIT_TRANS, transaction_id)
            else:
                spb.insert_bigint(SrvRepairOption.COMMIT_TRANS_64, transaction_id)
            self._srv()._svc.start(spb.get_buffer())
        self._srv()._read_all_binary_output()
    def rollback_limbo_transaction(self, *, database: FILESPEC, transaction_id: int) -> None:
        """Resolve limbo transaction with rollback.

        Arguments:
            database: Database specification or alias.
            transaction_id: ID of Transaction to resolve.
        """
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.REPAIR)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if transaction_id <= USHRT_MAX:
                spb.insert_int(SrvRepairOption.ROLLBACK_TRANS, transaction_id)
            else:
                spb.insert_bigint(SrvRepairOption.ROLLBACK_TRANS_64, transaction_id)
            self._srv()._svc.start(spb.get_buffer())
        self._srv()._read_all_binary_output()

class ServerDbServices(ServerDbServices3):
    """Database-related actions and services [Firebird 4+].
    """
    def nfix_database(self, *, database: FILESPEC, role: str=None,
                      flags: SrvNBackupFlag=SrvNBackupFlag.NONE) -> None:
        """Fixup database after filesystem copy.

        Arguments:
            database: Database specification or alias.
            role: SQL ROLE name passed to nbackup.
            flags: Backup options.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_tag(ServerAction.NFIX)
            spb.insert_int(SPBItem.OPTIONS, flags)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def set_replica_mode(self, *, database: FILESPEC, mode: ReplicaMode, role: str=None) -> None:
        """Manage replica database.

        Arguments:
            database: Database specification or alias.
            mode: New replication mode.
            role: SQL ROLE name passed to gfix.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.PROPERTIES)
            spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, role, encoding=self._srv().encoding)
            spb.insert_bytes(SrvPropertiesOption.REPLICA_MODE, bytes([mode]))
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()

class ServerUserServices(ServerServiceProvider):
    """User-related actions and services.
    """
    def __fetch_users(self, data: Buffer) -> List[UserInfo]:
        users = []
        user = {}
        while not data.is_eof():
            tag = data.get_tag()
            if tag == SrvUserOption.USER_NAME:
                if user:
                    users.append(UserInfo(**user))
                    user.clear()
                user['user_name'] = data.read_sized_string(encoding=self._srv().encoding)
            elif tag == SrvUserOption.USER_ID:
                user['user_id'] = data.read_int()
            elif tag == SrvUserOption.GROUP_ID:
                user['group_id'] = data.read_int()
            elif tag == SrvUserOption.PASSWORD:  # pragma: no cover
                user['password'] = data.read_bytes()
            elif tag == SrvUserOption.GROUP_NAME:  # pragma: no cover
                user['group_name'] = data.read_sized_string(encoding=self._srv().encoding)
            elif tag == SrvUserOption.FIRST_NAME:
                user['first_name'] = data.read_sized_string(encoding=self._srv().encoding)
            elif tag == SrvUserOption.MIDDLE_NAME:
                user['middle_name'] = data.read_sized_string(encoding=self._srv().encoding)
            elif tag == SrvUserOption.LAST_NAME:
                user['last_name'] = data.read_sized_string(encoding=self._srv().encoding)
            elif tag == SrvUserOption.ADMIN:
                user['admin'] = bool(data.read_int())
            else:  # pragma: no cover
                raise InterfaceError(f"Unrecognized result clumplet: {tag}")
        if user:
            users.append(UserInfo(**user))
        return users
    def get_all(self, *, database: FILESPEC=None, sql_role: str=None) -> List[UserInfo]:
        """Get information about users.

        Arguments:
            database: Database specification or alias.
            sql_role: SQL role name.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.DISPLAY_USER_ADM)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role,
                                  encoding=self._srv().encoding)
            self._srv()._svc.start(spb.get_buffer())
        return self.__fetch_users(Buffer(self._srv()._read_all_binary_output()))
    def get(self, user_name: str, *, database: FILESPEC=None, sql_role: str=None) -> Optional[UserInfo]:
        """Get information about user.

        Arguments:
            user_name: User name.
            database: Database specification or alias.
            sql_role: SQL role name.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.DISPLAY_USER_ADM)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            spb.insert_string(SrvUserOption.USER_NAME, user_name, encoding=self._srv().encoding)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role, encoding=self._srv().encoding)
            self._srv()._svc.start(spb.get_buffer())
        users = self.__fetch_users(Buffer(self._srv()._read_all_binary_output()))
        return users[0] if users else None
    def add(self, *, user_name: str, password: str, user_id: int=None,
                 group_id: int=None, first_name: str=None, middle_name: str=None,
                 last_name: str=None, admin: bool=None, database: FILESPEC=None,
                 sql_role: str=None) -> None:
        """Add new user.

        Arguments:
            user_name: User name.
            password: User password.
            user_id: User ID.
            group_id: Group ID.
            firest_name: User's first name.
            middle_name: User's middle name.
            last_name: User's last name.
            admin: Admin flag.
            database: Database specification or alias.
            sql_role: SQL role name.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.ADD_USER)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            spb.insert_string(SrvUserOption.USER_NAME, user_name, encoding=self._srv().encoding)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role, encoding=self._srv().encoding)
            spb.insert_string(SrvUserOption.PASSWORD, password,
                              encoding=self._srv().encoding)
            if user_id is not None:
                spb.insert_int(SrvUserOption.USER_ID, user_id)
            if group_id is not None:
                spb.insert_int(SrvUserOption.GROUP_ID, group_id)
            if first_name is not None:
                spb.insert_string(SrvUserOption.FIRST_NAME, first_name,
                                  encoding=self._srv().encoding)
            if middle_name is not None:
                spb.insert_string(SrvUserOption.MIDDLE_NAME, middle_name,
                                  encoding=self._srv().encoding)
            if last_name is not None:
                spb.insert_string(SrvUserOption.LAST_NAME, last_name,
                                  encoding=self._srv().encoding)
            if admin is not None:
                spb.insert_int(SrvUserOption.ADMIN, 1 if admin else 0)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def update(self, user_name: str, *, password: str=None,
                    user_id: int=None, group_id: int=None,
                    first_name: str=None, middle_name: str=None,
                    last_name: str=None, admin: bool=None, database: FILESPEC=None) -> None:
        """Update user information.

        Arguments:
            user_name: User name.
            password: User password.
            user_id: User ID.
            group_id: Group ID.
            firest_name: User's first name.
            middle_name: User's middle name.
            last_name: User's last name.
            admin: Admin flag.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.MODIFY_USER)
            spb.insert_string(SrvUserOption.USER_NAME, user_name,
                              encoding=self._srv().encoding)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if password is not None:
                spb.insert_string(SrvUserOption.PASSWORD, password,
                                  encoding=self._srv().encoding)
            if user_id is not None:
                spb.insert_int(SrvUserOption.USER_ID, user_id)
            if group_id is not None:
                spb.insert_int(SrvUserOption.GROUP_ID, group_id)
            if first_name is not None:
                spb.insert_string(SrvUserOption.FIRST_NAME, first_name,
                                  encoding=self._srv().encoding)
            if middle_name is not None:
                spb.insert_string(SrvUserOption.MIDDLE_NAME, middle_name,
                                  encoding=self._srv().encoding)
            if last_name is not None:
                spb.insert_string(SrvUserOption.LAST_NAME, last_name,
                                  encoding=self._srv().encoding)
            if admin is not None:
                spb.insert_int(SrvUserOption.ADMIN, 1 if admin else 0)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def delete(self, user_name: str, *, database: FILESPEC=None, sql_role: str=None) -> None:
        """Delete user.

        Arguments:
            user_name: User name.
            database: Database specification or alias.
            sql_role: SQL role name.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.DELETE_USER)
            spb.insert_string(SrvUserOption.USER_NAME, user_name, encoding=self._srv().encoding)
            if database is not None:
                spb.insert_string(SPBItem.DBNAME, str(database), encoding=self._srv().encoding)
            if sql_role is not None:
                spb.insert_string(SPBItem.SQL_ROLE_NAME, sql_role, encoding=self._srv().encoding)
            self._srv()._svc.start(spb.get_buffer())
        self._srv().wait()
    def exists(self, user_name: str, *, database: FILESPEC=None, sql_role: str=None) -> bool:
        """Returns True if user exists.

        Arguments:
            user_name: User name.
            database: Database specification or alias.
            sql_role: SQL role name.
        """
        return self.get(user_name, database=database, sql_role=sql_role) is not None

class ServerTraceServices(ServerServiceProvider):
    """Trace session actions and services.
    """
    def __action(self, action: ServerAction, label: str, session_id: int) -> str:
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(action)
            spb.insert_int(SrvTraceOption.ID, session_id)
            self._srv()._svc.start(spb.get_buffer())
        response = self._srv()._fetch_line()
        if not response.startswith(f"Trace session ID {session_id} {label}"):  # pragma: no cover
            # response should contain the error message
            raise DatabaseError(response)
        return response
    def start(self, *, config: str, name: str=None) -> int:
        """Start new trace session. **(ASYNC service)**

        Arguments:
            config: Trace session configuration.
            name: Trace session name.

        Returns:
            Trace session ID.
        """
        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.TRACE_START)
            if name is not None:
                spb.insert_string(SrvTraceOption.NAME, name)
            spb.insert_string(SrvTraceOption.CONFIG, config, encoding=self._srv().encoding)
            self._srv()._svc.start(spb.get_buffer())
        response = self._srv()._fetch_line()
        if response.startswith('Trace session ID'):
            return int(response.split()[3])
        else:  # pragma: no cover
            # response should contain the error message
            raise DatabaseError(response)
    def stop(self, *, session_id: int) -> str:
        """Stop trace session.

        Arguments:
            session_id: Trace session ID.

        Returns:
           Text message 'Trace session ID <x> stopped'.
        """
        return self.__action(ServerAction.TRACE_STOP, 'stopped', session_id)
    def suspend(self, *, session_id: int) -> str:
        """Suspend trace session.

        Arguments:
            session_id: Trace session ID.

        Returns:
           Text message 'Trace session ID <x> paused'.
        """
        return self.__action(ServerAction.TRACE_SUSPEND, 'paused', session_id)
    def resume(self, *, session_id: int) -> str:
        """Resume trace session.

        Arguments:
            session_id: Trace session ID.

        Returns:
           Text message 'Trace session ID <x> resumed'.
        """
        return self.__action(ServerAction.TRACE_RESUME, 'resumed', session_id)
    @property
    def sessions(self) -> Dict[int, TraceSession]:
        """Dictionary with active trace sessions.
        """
        def store():
            if current:
                session = TraceSession(**current)
                result[session.id] = session
                current.clear()

        self._srv()._reset_output()
        with a.get_api().util.get_xpb_builder(XpbKind.SPB_START) as spb:
            spb.insert_tag(ServerAction.TRACE_LIST)
            self._srv()._svc.start(spb.get_buffer())
        result = {}
        current = {}
        for line in self._srv():
            if not line.strip():
                store()
            elif line.startswith('Session ID:'):
                store()
                current['id'] = int(line.split(':')[1].strip())
            elif line.lstrip().startswith('name:'):
                current['name'] = line.split(':')[1].strip()
            elif line.lstrip().startswith('user:'):
                current['user'] = line.split(':')[1].strip()
            elif line.lstrip().startswith('date:'):
                current['timestamp'] = datetime.datetime.strptime(
                    line.split(':', 1)[1].strip(),
                    '%Y-%m-%d %H:%M:%S')
            elif line.lstrip().startswith('flags:'):
                current['flags'] = line.split(':')[1].strip().split(',')
            else:  # pragma: no cover
                raise InterfaceError(f"Unexpected line in trace session list: {line}")
        store()
        return result

class Server(LoggingIdMixin):
    """Represents connection to Firebird Service Manager.

    Note:
        Implements context manager protocol to call `.close()` automatically.
    """
    def __init__(self, svc: iService, spb: bytes, host: str, encoding: str,
                 encoding_errors: str):
        self._svc: iService = svc
        #: Service Parameter Buffer (SPB) used to connect the service manager
        self.spb: bytes = spb
        #: Server host
        self.host: str = host
        #: Service output mode (line or eof)
        self.mode: SrvInfoCode = SrvInfoCode.TO_EOF
        #: Response buffer used to comunicate with service
        self.response: CBuffer = CBuffer(USHRT_MAX)
        self._eof: bool = False
        self.__line_buffer: List[str] = []
        #: Encoding used for text data exchange with server
        self.encoding: str = encoding
        #: Handler used for encoding errors. See: `codecs#error-handlers`
        self.encoding_errors: str = encoding_errors
        #
        self.__ev: float = None
        self.__info: ServerInfoProvider = None
        self.__dbsvc: Union[ServerDbServices, ServerDbServices3] = None
        self.__trace: ServerTraceServices = None
        self.__user: ServerUserServices = None
    def __enter__(self) -> Server:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
    def __del__(self):
        if self._svc is not None:
            warn(f"Server '{self.logging_id}' disposed without prior close()", ResourceWarning)
            self.close()
    def __next__(self):
        if (line := self.readline()) is not None:
            return line
        else:
            raise StopIteration
    def __iter__(self):
        return self
    def __str__(self):
        return f'Server[v{self.info.version}@{self.host.replace(":service_mgr","")}]'
    def _engine_version(self) -> float:
        if self.__ev is None:
            self.__ev = _engine_version_provider.get_engine_version(weakref.ref(self))
        return self.__ev
    def _reset_output(self) -> None:
        self._eof = False
        self.__line_buffer.clear()
    def _make_request(self, timeout: int) -> bytes:
        if timeout == -1:
            return None
        else:
            return b''.join([SrvInfoCode.TIMEOUT.to_bytes(1, 'little'),
                             (4).to_bytes(2, 'little'),
                             timeout.to_bytes(4, 'little'), isc_info_end.to_bytes(1, 'little')])
    def _fetch_complex_info(self, request: bytes, timeout: int=-1) -> None:
        send = self._make_request(timeout)
        self.response.clear()
        self._svc.query(send, request, self.response.raw)
        if self.response.is_truncated():  # pragma: no cover
            raise InterfaceError("Requested data can't fint into largest possible buffer")
    def _fetch_line(self, timeout: int=-1) -> Optional[str]:
        self._fetch_complex_info(bytes([SrvInfoCode.LINE]))
        result = None
        while not self.response.is_eof():
            tag = self.response.get_tag()
            if tag == SrvInfoCode.TIMEOUT:
                return None
            elif tag == SrvInfoCode.LINE:
                result = self.response.read_sized_string(encoding=self.encoding)
        if self.response.get_tag() != isc_info_end:  # pragma: no cover
            raise InterfaceError("Malformed result buffer (missing isc_info_end item)")
        return result
    def _query_output(self, timeout: int) -> None:
        assert self._svc is not None
        self.response.clear()
        self._svc.query(self._make_request(timeout), bytes([self.mode]), self.response.raw)
        tag = self.response.get_tag()
        if tag != self.mode:  # pragma: no cover
            raise InterfaceError(f"Service responded with error code: {tag}")
        return self.response.read_sized_string(encoding=self.encoding, errors=self.encoding_errors)
    def _read_output(self, *, init: str='', timeout: int=-1) -> None:
        data = self._query_output(timeout)
        if self.mode is SrvInfoCode.TO_EOF:
            self._eof = self.response.get_tag() == isc_info_end
        else: # LINE mode
            self._eof = not data
            while (tag := self.response.get_tag()) == isc_info_truncated:
                data += self._query_output(timeout)
            if tag != isc_info_end:  # pragma: no cover
                raise InterfaceError("Malformed result buffer (missing isc_info_end item)")
        init += data
        if data and self.mode is SrvInfoCode.LINE:
            init += '\n'
        self.__line_buffer = init.splitlines(keepends=True)
    def _read_all_binary_output(self, *, timeout: int=-1) -> bytes:
        assert self._svc is not None
        send = self._make_request(timeout)
        result = []
        eof = False
        while not eof:
            self.response.clear()
            self._svc.query(send, bytes([SrvInfoCode.TO_EOF]), self.response.raw)
            if (tag := self.response.get_tag()) != SrvInfoCode.TO_EOF:  # pragma: no cover
                raise InterfaceError(f"Service responded with error code: {tag}")
            result.append(self.response.read_bytes())
            eof = self.response.get_tag() == isc_info_end
        return b''.join(result)
    def _read_next_binary_output(self, *, timeout: int=-1) -> bytes:
        assert self._svc is not None
        result = None
        if not self._eof:
            send = self._make_request(timeout)
            self.response.clear()
            self._svc.query(send, bytes([SrvInfoCode.TO_EOF]), self.response.raw)
            if (tag := self.response.get_tag()) != SrvInfoCode.TO_EOF:  # pragma: no cover
                raise InterfaceError(f"Service responded with error code: {tag}")
            result = self.response.read_bytes()
            self._eof = self.response.get_tag() == isc_info_end
        return result
    def is_running(self) -> bool:
        """Returns True if service is running.

        Note:
           Some services like `~.ServerDbServices.backup()` or `~.ServerDbServices.sweep()`
           may take time to comlete, so they're called asynchronously. Until they're finished,
           no other async service could be started.
        """
        assert self._svc is not None
        return self.info.get_info(SrvInfoCode.RUNNING) > 0
    def readline(self) -> Optional[str]:
        """Get next line of textual output from last service query.
        """
        if self._eof and not self.__line_buffer:
            return None
        if not self.__line_buffer:
            self._read_output()
        elif len(self.__line_buffer) == 1:
            line = self.__line_buffer.pop(0)
            if self._eof:
                return line
            self._read_output(init=line)
            while not self.__line_buffer[0].endswith('\n'):
                self._read_output(init=self.__line_buffer.pop(0))
        if self.__line_buffer:
            return self.__line_buffer.pop(0)
        return None
    def readlines(self) -> List[str]:
        """Get list of remaining output lines from last service query.
        """
        return [line for line in self]
    def wait(self) -> None:
        """Wait until running service completes, i.e. stops sending data.
        """
        while self.is_running():
            for _ in self:
                pass
    def close(self) -> None:
        """Close the server connection now (rather than whenever `__del__` is called).
        The instance will be unusable from this point forward; an `.Error`
        (or subclass) exception will be raised if any operation is attempted
        with the instance.
        """
        if self.__info is not None:
            self.__info._close()
            self.__info = None
        if self.__dbsvc is not None:
            self.__dbsvc._close()
            self.__dbsvc = None
        if self.__trace is not None:
            self.__trace._close()
            self.__trace = None
        if self.__user is not None:
            self.__user._close()
            self.__user = None
        if self._svc is not None:
            # try..finally is necessary to shield from crashed server
            # Otherwise close() will be called from __del__ which may crash Python
            try:
                self._svc.detach()
            finally:
                self._svc = None
    # Properties
    @property
    def info(self) -> ServerInfoProvider:
        """Access to various information about attached server.
        """
        if self.__info is None:
            self.__info = ServerInfoProvider(self.encoding, self)
        return self.__info
    @property
    def database(self) -> Union[ServerDbServices3, ServerDbServices]:
        """Access to various database-related actions and services.
        """
        if self.__dbsvc is None:
            cls = ServerDbServices if self._engine_version() >= 4.0 \
                else ServerDbServices3
            self.__dbsvc = cls(self)
        return self.__dbsvc
    @property
    def trace(self) -> ServerTraceServices:
        """Access to various database-related actions and services.
        """
        if self.__trace is None:
            self.__trace = ServerTraceServices(self)
        return self.__trace
    @property
    def user(self) -> ServerUserServices:
        """Access to various user-related actions and services.
        """
        if self.__user is None:
            self.__user = ServerUserServices(self)
        return self.__user

def connect_server(server: str, *, user: str=None, password: str=None,
                   crypt_callback: iCryptKeyCallbackImpl=None,
                   expected_db: str=None, role: str=None, encoding: str=None,
                   encoding_errors: str=None) -> Server:
    """Establishes a connection to server's service manager.

    Arguments:
        server: Server host machine or Server configuration name.
        user: User name.
        password: User password.
        crypt_callback: Callback that provides encryption key.
        expected_db: Database that would be accessed (for using services with non-default
                     security database)
        role: SQL role used for connection.
        encoding: Encoding for string values passed in parameter buffer. Default is
           `.ServerConfig.encoding`.
        encoding_errors: Error handler used for encoding errors. Default is
           `.ServerConfig.encoding_errors`.

    Hooks:
        Event `.ServerHook.ATTACHED`: Executed before `Service` instance is
        returned. Hook must have signature::

            hook_func(server: Server) -> None

        Any value returned by hook is ignored.
    """
    srv_config = driver_config.get_server(server)
    if srv_config is None:
        srv_config = driver_config.server_defaults
        host = server if server else None
    else:
        host = srv_config.host.value
    if host is None:
        host = 'service_mgr'
    if not host.endswith('service_mgr'):
        if host and not host.endswith(':'):
            host += ':'
        host += 'service_mgr'
    if user is None:
        user = srv_config.user.value
    if password is None:
        password = srv_config.password.value
    spb = SPB_ATTACH(user=user, password=password, config=srv_config.config.value,
                     trusted_auth=srv_config.trusted_auth.value,
                     auth_plugin_list=srv_config.auth_plugin_list.value,
                     expected_db=expected_db, role=role)
    spb_buf = spb.get_buffer()
    with a.get_api().master.get_dispatcher() as provider:
        if crypt_callback is not None:
            provider.set_dbcrypt_callback(crypt_callback)
        svc = provider.attach_service_manager(host, spb_buf)
    con = Server(svc, spb_buf, host, srv_config.encoding.value if encoding is None else encoding,
                 srv_config.encoding_errors.value if encoding_errors is None else encoding_errors)
    for hook in get_callbacks(ServerHook.ATTACHED, con):
        hook(con)
    return con

# Register hookable classes
register_class(Connection, ConnectionHook)
register_class(Server, ServerHook)
del register_class
del add_hook
