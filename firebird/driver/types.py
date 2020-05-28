# coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/types.py
# DESCRIPTION:    Types for Firebird driver
# CREATED:        4.3.2020
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

"""firebird-driver - Types for Firebird driver
"""

from __future__ import annotations
from typing import Union, Type, Any, List, Tuple, Callable, Protocol, Optional, ByteString
import sys
import threading
import time
import datetime
import decimal
from enum import IntEnum, IntFlag
from ctypes import memmove, create_string_buffer, cast, byref, string_at, \
     c_char_p, c_void_p, c_byte, c_ulong
from dataclasses import dataclass
from firebird.base.types import Error, Sentinel, UNLIMITED, ByteOrder
from firebird.base.buffer import MemoryBuffer, BufferFactory, BytesBufferFactory, \
     CTypesBufferFactory, safe_ord
from . import fbapi as a
from .hooks import APIHook, HookManager

# Exceptions required by Python Database API 2.0

class InterfaceError(Error):
    """Exception raised for errors that are reported by the driver rather than
the Firebird itself.
"""

class DatabaseError(Error):
    """Exception raised for all errors reported by Firebird."""

    #: Returned SQLSTATE or None
    sqlstate: str = None
    #: Returned SQLCODE or None
    sqlcode: int = None
    #: Tuple with all returned GDS error codes
    gds_codes: Tuple[int] = tuple()

class DataError(DatabaseError):
    """Exception raised for errors that are due to problems with the processed
data like division by zero, numeric value out of range, etc.

Important:
    This exceptions is never directly thrown by Firebird driver.
"""

class OperationalError(DatabaseError):
    """Exception raised for errors that are related to the database's operation
and not necessarily under the control of the programmer, e.g. an unexpected
disconnect occurs, the data source name is not found, a transaction could not
be processed, a memory allocation error occurred during processing, etc.

Important:
    This exceptions is never directly thrown by Firebird driver.
"""

class IntegrityError(DatabaseError):
    """Exception raised when the relational integrity of the database is affected,
e.g. a foreign key check fails.

Important:
    This exceptions is never directly thrown by Firebird driver.
"""

class InternalError(DatabaseError):
    """Exception raised when the database encounters an internal error, e.g. the
cursor is not valid anymore, the transaction is out of sync, etc.

Important:
    This exceptions is never directly thrown by Firebird driver.
"""

class ProgrammingError(DatabaseError):
    """Exception raised for programming errors, e.g. table not found or already
exists, syntax error in the SQL statement, wrong number of parameters specified,
etc.

Important:
    This exceptions is never directly thrown by Firebird driver.
"""

class NotSupportedError(DatabaseError):
    """Exception raised in case a method or database API was used which is not
supported by the database

Important:
    This exceptions is never directly thrown by Firebird driver.
"""

# Enums

class NetProtocol(IntEnum):
    "Network protocol options available for connection"
    XNET = 1
    INET = 2
    INET4 = 3
    WNET = 4

class DirectoryCode(IntEnum):
    "IConfigManager directory codes"
    DIR_BIN = 0
    DIR_SBIN = 1
    DIR_CONF = 2
    DIR_LIB = 3
    DIR_INC = 4
    DIR_DOC = 5
    DIR_UDF = 6
    DIR_SAMPLE = 7
    DIR_SAMPLEDB = 8
    DIR_HELP = 9
    DIR_INTL = 10
    DIR_MISC = 11
    DIR_SECDB = 12
    DIR_MSG = 13
    DIR_LOG = 14
    DIR_GUARD = 15
    DIR_PLUGINS = 16

class XpbKind(IntEnum):
    "Xpb builder kinds"
    DPB = 1
    SPB_ATTACH = 2
    SPB_START = 3
    TPB = 4

class StateResult(IntEnum):
    "IState result codes"
    ERROR = -1
    OK = 0
    NO_DATA = 1
    SEGMENT = 2

class PageSize(IntEnum):
    "Supported database page sizes"
    PAGE_4K = 4096
    PAGE_8K = 8192
    PAGE_16K = 16384
    PAGE_32K = 32768  # Firebird 4

class DBKeyScope(IntEnum):
    "Scope of DBKey context"
    TRANSACTION = 0
    ATTACHMENT = 1

class InfoItemType(IntEnum):
    "Data type of information item"
    BYTE = 1
    INTEGER = 2
    BIGINT = 3
    BYTES = 4
    RAW_BYTES = 5
    STRING = 6

class SvcInfoCode(IntEnum):
    "Service information (isc_info_svc_*) codes"
    SRV_DB_INFO = 50
    GET_CONFIG = 53
    VERSION = 54
    SERVER_VERSION = 55
    IMPLEMENTATION = 56
    CAPABILITIES = 57
    USER_DBPATH = 58
    GET_ENV = 59
    GET_ENV_LOCK = 60
    GET_ENV_MSG = 61
    LINE = 62
    TO_EOF = 63
    TIMEOUT = 64
    LIMBO_TRANS = 66
    RUNNING = 67
    GET_USERS = 68
    AUTH_BLOCK = 69
    STDIN = 78

class BlobInfoCode(IntEnum):
    "BLOB information (isc_info_blob_*) codes"
    NUM_SEGMENTS = 4
    MAX_SEGMENT = 5
    TOTAL_LENGTH = 6
    TYPE = 7

class DbInfoCode(IntEnum):
    "Database information (isc_info_*) codes"
    DB_ID = 4
    READS = 5
    WRITES = 6
    FETCHES = 7
    MARKS = 8
    IMPLEMENTATION_OLD = 11
    VERSION = 12
    BASE_LEVEL = 13
    PAGE_SIZE = 14
    NUM_BUFFERS = 15
    LIMBO = 16
    CURRENT_MEMORY = 17
    MAX_MEMORY = 18
    # Obsolete 19-20
    ALLOCATION = 21
    ATTACHMENT_ID = 22
    READ_SEQ_COUNT = 23
    READ_IDX_COUNT = 24
    INSERT_COUNT = 25
    UPDATE_COUNT = 26
    DELETE_COUNT = 27
    BACKOUT_COUNT = 28
    PURGE_COUNT = 29
    EXPUNGE_COUNT = 30
    SWEEP_INTERVAL = 31
    ODS_VERSION = 32
    ODS_MINOR_VERSION = 33
    NO_RESERVE = 34
    # Obsolete 35-51
    FORCED_WRITES = 52
    USER_NAMES = 53
    PAGE_ERRORS = 54
    RECORD_ERRORS = 55
    BPAGE_ERRORS = 56
    DPAGE_ERRORS = 57
    IPAGE_ERRORS = 58
    PPAGE_ERRORS = 59
    TPAGE_ERRORS = 60
    SET_PAGE_BUFFERS = 61
    DB_SQL_DIALECT = 62
    DB_READ_ONLY = 63
    DB_SIZE_IN_PAGES = 64
    # Values 65 -100 unused to avoid conflict with InterBase
    ATT_CHARSET = 101
    DB_CLASS = 102
    FIREBIRD_VERSION = 103
    OLDEST_TRANSACTION = 104
    OLDEST_ACTIVE = 105
    OLDEST_SNAPSHOT = 106
    NEXT_TRANSACTION = 107
    DB_PROVIDER = 108
    ACTIVE_TRANSACTIONS = 109
    ACTIVE_TRAN_COUNT = 110
    CREATION_DATE = 111
    DB_FILE_SIZE = 112
    PAGE_CONTENTS = 113
    IMPLEMENTATION = 114
    PAGE_WARNS = 115
    RECORD_WARNS = 116
    BPAGE_WARNS = 117
    DPAGE_WARNS = 118
    IPAGE_WARNS = 119
    PPAGE_WARNS = 120
    TPAGE_WARNS = 121
    PIP_ERRORS = 122
    PIP_WARNS = 123
    PAGES_USED = 124
    PAGES_FREE = 125
    SES_IDLE_TIMEOUT_DB = 129  # Firebird 4
    SES_IDLE_TIMEOUT_ATT = 130  # Firebird 4
    SES_IDLE_TIMEOUT_RUN = 131  # Firebird 4
    CONN_FLAGS = 132
    # Firebird 4
    STMT_TIMEOUT_DB = 135
    STMT_TIMEOUT_ATT = 136
    PROTOCOL_VERSION = 137
    CRYPT_PLUGIN = 138
    CREATION_TIMESTAMP_TZ = 139

class StmtInfoCode(IntEnum):
    "Statement information (isc_info_sql_*) codes"
    SELECT = 4
    BIND = 5
    NUM_VARIABLES = 6
    DESCRIBE_VARS = 7
    DESCRIBE_END = 8
    SQLDA_SEQ = 9
    MESSAGE_SEQ = 10
    TYPE = 11
    SUB_TYPE = 12
    SCALE = 13
    LENGTH = 14
    NULL_IND = 15
    FIELD = 16
    RELATION = 17
    OWNER = 18
    ALIAS = 19
    SQLDA_START = 20
    STMT_TYPE = 21
    GET_PLAN = 22
    RECORDS = 23
    BATCH_FETCH = 24
    RELATION_ALIAS = 25
    EXPLAIN_PLAN = 26
    FLAGS = 27
    # Firebird 4
    TIMEOUT_USER = 28
    TIMEOUT_RUN = 29
    BLOB_ALIGN = 30

class TraInfoCode(IntEnum):
    "Transaction information (isc_info_tra_*) codes"
    ID = 4
    OLDEST_INTERESTING = 5
    OLDEST_SNAPSHOT = 6
    OLDEST_ACTIVE = 7
    ISOLATION = 8
    ACCESS = 9
    LOCK_TIMEOUT = 10
    DBPATH = 11

class TraInfoIsolation(IntEnum):
    "Transaction isolation response"
    CONSISTENCY = 1
    CONCURRENCY = 2
    READ_COMMITTED = 3

class TraInfoReadCommitted(IntEnum):
    "Transaction isolation Read Committed response"
    NO_RECORD_VERSION = 0
    RECORD_VERSION = 1
    READ_CONSISTENCY = 2  # Firebird 4

class TraInfoAccess(IntEnum):
    "Transaction isolation access mode response"
    READ_ONLY = 0
    READ_WRITE = 1

class TraAccessMode(IntEnum):
    "Transaction Access Mode TPB parameters"
    READ = 8
    WRITE = 9

class TraIsolation(IntEnum):
    "Transaction Isolation TPB paremeters"
    CONSISTENCY = 1
    CONCURRENCY = 2
    READ_COMMITTED = 15

class TraReadCommitted(IntEnum):
    "Read Committed Isolation TPB paremeters"
    RECORD_VERSION = 17
    NO_RECORD_VERSION = 18

class Isolation(IntEnum):
    "Transaction Isolation TPB parameters"
    READ_COMMITTED = -1
    SERIALIZABLE = 1
    SNAPSHOT = 2
    READ_COMMITTED_NO_RECORD_VERSION = 3
    READ_COMMITTED_RECORD_VERSION = 4
    # Aliases
    REPEATABLE_READ = SNAPSHOT
    CONCURRENCY = SNAPSHOT
    CONSISTENCY = SERIALIZABLE

class TraLockResolution(IntEnum):
    "Transaction Lock resolution TPB parameters"
    WAIT = 6
    NO_WAIT = 7

class TableShareMode(IntEnum):
    "Transaction table share mode TPB parameters"
    SHARED = 3
    PROTECTED = 4
    EXCLUSIVE = 5

class TableAccessMode(IntEnum):
    "Transaction Access Mode TPB parameters"
    LOCK_READ = 10
    LOCK_WRITE = 11

class DefaultAction(IntEnum):
    "Default action when transaction is ended automatically"
    COMMIT = 1
    ROLLBACK = 2

class StatementType(IntEnum):
    "Statement type"
    SELECT = 1
    INSERT = 2
    UPDATE = 3
    DELETE = 4
    DDL = 5
    GET_SEGMENT = 6
    PUT_SEGMENT = 7
    EXEC_PROCEDURE = 8
    START_TRANS = 9
    COMMIT = 10
    ROLLBACK = 11
    SELECT_FOR_UPD = 12
    SET_GENERATOR = 13
    SAVEPOINT = 14

class SQLDataType(IntEnum):
    "SQL data type"
    TEXT = 452
    VARYING = 448
    SHORT = 500
    LONG = 496
    FLOAT = 482
    DOUBLE = 480
    D_FLOAT = 530
    TIMESTAMP = 510
    BLOB = 520
    ARRAY = 540
    QUAD = 550
    TIME = 560
    DATE = 570
    INT64 = 580
    TIMESTAMP_TZ = 32754  # Firebird 4
    TIME_TZ = 32756  # Firebird 4
    DEC_FIXED = 32758  # Firebird 4
    DEC16 = 32760  # Firebird 4
    DEC34 = 32762  # Firebird 4
    BOOLEAN = 32764
    NULL = 32766

class DPBItem(IntEnum):
    "isc_dpb_* items (VERSION2)"
    PAGE_SIZE = 4
    NUM_BUFFERS = 5
    DBKEY_SCOPE = 13
    NO_GARBAGE_COLLECT = 16
    SWEEP_INTERVAL = 22
    FORCE_WRITE = 24
    NO_RESERVE = 27
    USER_NAME = 28
    PASSWORD = 29
    LC_CTYPE = 48
    RESERVED = 53
    OVERWRITE = 54
    CONNECT_TIMEOUT = 57
    DUMMY_PACKET_INTERVAL = 58
    SQL_ROLE_NAME = 60
    SET_PAGE_BUFFERS = 61
    WORKING_DIRECTORY = 62
    SQL_DIALECT = 63
    SET_DB_READONLY = 64
    SET_DB_SQL_DIALECT = 65
    SET_DB_CHARSET = 68
    ADDRESS_PATH = 70
    PROCESS_ID = 71
    NO_DB_TRIGGERS = 72
    TRUSTED_AUTH = 73
    PROCESS_NAME = 74
    TRUSTED_ROLE = 75
    ORG_FILENAME = 76
    UTF8_FILENAME = 77
    EXT_CALL_DEPTH = 78
    AUTH_BLOCK = 79
    CLIENT_VERSION = 80
    REMOTE_PROTOCOL = 81
    HOST_NAME = 82
    OS_USER = 83
    SPECIFIC_AUTH_DATA = 84
    AUTH_PLUGIN_LIST = 85
    AUTH_PLUGIN_NAME = 86
    CONFIG = 87
    NOLINGER = 88
    RESET_ICU = 89
    MAP_ATTACH = 90
    # Firebird 4
    SESSION_TIME_ZONE = 91
    SET_DB_REPLICA = 92

class TPBItem(IntEnum):
    "isc_tpb_* items"
    VERSION3 = 3
    IGNORE_LIMBO = 14
    AUTOCOMMIT = 16
    NO_AUTO_UNDO = 20
    LOCK_TIMEOUT = 21

class SPBItem(IntEnum):
    "isc_spb_* items"
    USER_NAME = 28
    PASSWORD = 29
    CONNECT_TIMEOUT = 57
    DUMMY_PACKET_INTERVAL = 58
    SQL_ROLE_NAME = 60
    COMMAND_LINE = 105
    DBNAME = 106
    VERBOSE = 107
    OPTIONS = 108
    TRUSTED_AUTH = 111
    TRUSTED_ROLE = 113
    VERBINT = 114
    AUTH_BLOCK = 115
    AUTH_PLUGIN_NAME = 116
    AUTH_PLUGIN_LIST = 117
    UTF8_FILENAME = 118
    CONFIG = 123

class BPBItem(IntEnum):
    "isc_bpb_* items"
    SOURCE_TYPE = 1
    TARGET_TYPE = 2
    TYPE = 3
    SOURCE_INTERP = 4
    TARGET_INTERP = 5
    FILTER_PARAMETER = 6
    STORAGE = 7

class BlobType(IntEnum):
    "Blob type"
    SEGMENTED = 0x0
    STREAM = 0x1

class BlobStorage(IntEnum):
    "Blob storage"
    MAIN = 0x0
    TEMP = 0x2

class ServiceAction(IntEnum):
    "isc_action_svc_* items"
    BACKUP = 1
    RESTORE = 2
    REPAIR = 3
    ADD_USER = 4
    DELETE_USER = 5
    MODIFY_USER = 6
    DISPLAY_USER = 7
    PROPERTIES = 8
    DB_STATS = 11
    GET_FB_LOG = 12
    NBAK = 20
    NREST = 21
    TRACE_START = 22
    TRACE_STOP = 23
    TRACE_SUSPEND = 24
    TRACE_RESUME = 25
    TRACE_LIST = 26
    SET_MAPPING = 27
    DROP_MAPPING = 28
    DISPLAY_USER_ADM = 29
    VALIDATE = 30

class SvcDbInfoOption(IntEnum):
    "Parameters for SvcInfoCode.SRV_DB_INFO"
    ATT = 5
    DB = 6

class SvcRepairOption(IntEnum):
    "Parameters for ServiceAction.REPAIR"
    COMMIT_TRANS = 15
    ROLLBACK_TRANS = 34
    RECOVER_TWO_PHASE = 17
    TRA_ID = 18
    SINGLE_TRA_ID = 19
    MULTI_TRA_ID = 20
    TRA_STATE = 21
    TRA_STATE_LIMBO = 22
    TRA_STATE_COMMIT = 23
    TRA_STATE_ROLLBACK = 24
    TRA_STATE_UNKNOWN = 25
    TRA_HOST_SITE = 26
    TRA_REMOTE_SITE = 27
    TRA_DB_PATH = 28
    TRA_ADVISE = 29
    TRA_ADVISE_COMMIT = 30
    TRA_ADVISE_ROLLBACK = 31
    TRA_ADVISE_UNKNOWN = 33
    TRA_ID_64 = 46
    SINGLE_TRA_ID_64 = 47
    MULTI_TRA_ID_64 = 48
    COMMIT_TRANS_64 = 49
    ROLLBACK_TRANS_64 = 50
    RECOVER_TWO_PHASE_64 = 51

class SvcBackupOption(IntEnum):
    "Parameters for ServiceAction.BACKUP"
    FILE = 5
    FACTOR = 6
    LENGTH = 7
    SKIP_DATA = 8
    STAT = 15
    # Firebird 4
    KEYHOLDER = 16
    KEYNAME = 17
    CRYPT = 18

class SvcRestoreOption(IntEnum):
    "Parameters for ServiceAction.RESTORE"
    FILE = 5
    SKIP_DATA = 8
    BUFFERS = 9
    PAGE_SIZE = 10
    LENGTH = 11
    ACCESS_MODE = 12
    FIX_FSS_DATA = 13
    FIX_FSS_METADATA = 14
    STAT = 15
    # Firebird 4
    KEYHOLDER = 16
    KEYNAME = 17
    CRYPT = 18

class SvcNBackupOption(IntEnum):
    "Parameters for ServiceAction.NBAK"
    LEVEL = 5
    FILE = 6
    DIRECT = 7
    # Firebird 4
    GUID = 8

class SvcTraceOption(IntEnum):
    "Parameters for ServiceAction.TRACE_*"
    ID = 1
    NAME = 2
    CONFIG = 3

class SvcPropertiesOption(IntEnum):
    "Parameters for ServiceAction.PROPERTIES"
    PAGE_BUFFERS = 5
    SWEEP_INTERVAL = 6
    SHUTDOWN_DB = 7
    DENY_NEW_ATTACHMENTS = 9
    DENY_NEW_TRANSACTIONS = 10
    RESERVE_SPACE = 11
    WRITE_MODE = 12
    ACCESS_MODE = 13
    SET_SQL_DIALECT = 14
    FORCE_SHUTDOWN = 41
    ATTACHMENTS_SHUTDOWN = 42
    TRANSACTIONS_SHUTDOWN = 43
    SHUTDOWN_MODE = 44
    ONLINE_MODE = 45

class SvcValidateOption(IntEnum):
    "Parameters for ServiceAction.VALIDATE"
    INCLUDE_TABLE = 1
    EXCLUDE_TABLE = 2
    INCLUDE_INDEX = 3
    EXCLUDE_INDEX = 4
    LOCK_TIMEOUT = 5

class SvcUserOption(IntEnum):
    "Parameters for ServiceAction.ADD_USER|DELETE_USER|MODIFY_USER|DISPLAY_USER"
    USER_ID = 5
    GROUP_ID = 6
    USER_NAME = 7
    PASSWORD = 8
    GROUP_NAME = 9
    FIRST_NAME = 10
    MIDDLE_NAME = 11
    LAST_NAME = 12
    ADMIN = 13

class DbAccessMode(IntEnum):
    "Values for isc_spb_prp_access_mode"
    READ_ONLY = 39
    READ_WRITE = 40

class DbSpaceReservation(IntEnum):
    "Values for isc_spb_prp_reserve_space"
    USE_FULL = 35
    RESERVE = 36

class DbWriteMode(IntEnum):
    "Values for isc_spb_prp_write_mode"
    ASYNC = 37
    SYNC = 38

class ShutdownMode(IntEnum):
    "Values for isc_spb_prp_shutdown_mode"
    MULTI = 1
    SINGLE = 2
    FULL = 3

class OnlineMode(IntEnum):
    "Values for isc_spb_prp_online_mode"
    NORMAL = 0
    MULTI = 1
    SINGLE = 2

class ShutdownMethod(IntEnum):
    "Database shutdown method options"
    FORCED = 41
    DENNY_ATTACHMENTS = 42
    DENNY_TRANSACTIONS = 43

class TransactionState(IntEnum):
    "Transaction state"
    UNKNOWN = 0
    COMMIT = 1
    ROLLBACK = 2
    LIMBO = 3

class DbProvider(IntEnum):
    "Database Providers"
    RDB_ELN = 1
    RDB_VMS = 2
    INTERBASE = 3
    FIREBIRD = 4

class DbClass(IntEnum):
    "Database Classes"
    UNKNOWN = 0
    ACCESS = 1
    Y_VALVE = 2
    REM_INT = 3
    REM_SRVR = 4
    PIPE_INT = 7
    PIPE_SRVR = 8
    SAM_INT = 9
    SAM_SRVR = 10
    GATEWAY = 11
    CACHE = 12
    CLASSIC_ACCESS = 13
    SERVER_ACCESS = 14

class Implementation(IntEnum):
    "Implementation - Legacy format"
    RDB_VMS = 1
    RDB_ELN = 2
    RDB_ELN_DEV = 3
    RDB_VMS_Y = 4
    RDB_ELN_Y = 5
    JRI = 6
    JSV = 7
    ISC_APL_68K = 25
    ISC_VAX_ULTR = 26
    ISC_VMS = 27
    ISC_SUN_68K = 28
    ISC_OS2 = 29
    ISC_SUN4 = 30
    ISC_HP_UX = 31
    ISC_SUN_386I = 32
    ISC_VMS_ORCL = 33
    ISC_MAC_AUX = 34
    ISC_RT_AIX = 35
    ISC_MIPS_ULT = 36
    ISC_XENIX = 37
    ISC_DG = 38
    ISC_HP_MPEXL = 39
    ISC_HP_UX68K = 40
    ISC_SGI = 41
    ISC_SCO_UNIX = 42
    ISC_CRAY = 43
    ISC_IMP = 44
    ISC_DELTA = 45
    ISC_NEXT = 46
    ISC_DOS = 47
    M88K = 48
    UNIXWARE = 49
    ISC_WINNT_X86 = 50
    ISC_EPSON = 51
    ALPHA_OSF = 52
    ALPHA_VMS = 53
    NETWARE_386 = 54
    WIN_ONLY = 55
    NCR_3000 = 56
    WINNT_PPC = 57
    DG_X86 = 58
    SCO_EV = 59
    I386 = 60
    FREEBSD = 61
    NETBSD = 62
    DARWIN_PPC = 63
    SINIXZ = 64
    LINUX_SPARC = 65
    LINUX_AMD64 = 66
    FREEBSD_AMD64 = 67
    WINNT_AMD64 = 68
    LINUX_PPC = 69
    DARWIN_X86 = 70
    LINUX_MIPSEL = 71
    LINUX_MIPS = 72
    DARWIN_X64 = 73
    SUN_AMD64 = 74
    LINUX_ARM = 75
    LINUX_IA64 = 76
    DARWIN_PPC64 = 77
    LINUX_S390X = 78
    LINUX_S390 = 79
    LINUX_SH = 80
    LINUX_SHEB = 81
    LINUX_HPPA = 82
    LINUX_ALPHA = 83
    LINUX_ARM64 = 84
    LINUX_PPC64EL = 85
    LINUX_PPC64 = 86
    LINUX_M68K = 87
    LINUX_RISCV64 = 88

class ImpCPU(IntEnum):
    "Implementation - CPU"
    INTEL386 = 0
    AMD_INTEL_X64 = 1
    ULTRA_SPARC = 2
    POWER_PC = 3
    POWER_PC64 = 4
    MIPSEL = 5
    MIPS = 6
    ARM = 7
    IA64 = 8
    S390 = 9
    S390X = 10
    SH = 11
    SHEB = 12
    HPPA = 13
    ALPHA = 14
    ARM64 = 15
    POWER_PC64EL = 16
    M68K = 17

class ImpOS(IntEnum):
    "Implementation - CPU"
    WINDOWS = 0
    LINUX = 1
    DARWIN = 2
    SOLARIS = 3
    HPUX = 4
    AIX = 5
    MMS = 6
    FREE_BSD = 7
    NET_BSD = 8

class ImpCompiler(IntEnum):
    "Implementation - Compiler"
    MSVC = 0
    GCC = 1
    XLC = 2
    ACC = 3
    SUN_STUDIO = 4
    ICC = 5

# Flags

class StateFlag(IntFlag):
    "IState flags"
    NONE = 0
    WARNINGS = 1
    ERRORS = 2

class PreparePrefetchFlag(IntFlag):
    "Flags for Statement Prefetch"
    NONE = 0
    TYPE = 1
    INPUT_PARAMETERS = 2
    OUTPUT_PARAMETERS = 4
    LEGACY_PLAN = 8
    DETAILED_PLAN = 16
    AFFECTED_RECORDS = 32
    FLAGS = 64
    METADATA = TYPE | FLAGS | INPUT_PARAMETERS | OUTPUT_PARAMETERS
    ALL = METADATA | LEGACY_PLAN | DETAILED_PLAN | AFFECTED_RECORDS

class StatementFlag(IntFlag):
    "Statement flags"
    NONE = 0
    HAS_CURSOR = 1
    REPEAT_EXECUTE = 2

class CursorFlag(IntFlag):
    "Cursor flags"
    NONE = 0
    SCROLLABLE = 1

class ConnectionFlag(IntFlag):
    "Flags returned for DbInfoCode.CONN_FLAGS"
    NONE = 0
    COMPRESSED = 0x01
    ENCRYPTED = 0x02

class ServerCapability(IntFlag):
    "Server capabilities (returned by isc_info_svc_capabilities)"
    NONE = 0
    WAL = 0b00000000001
    MULTI_CLIENT = 0b00000000010
    REMOTE_HOP = 0b00000000100
    NO_SRV_STATS = 0b00000001000
    NO_DB_STATS = 0b00000010000
    LOCAL_ENGINE = 0b00000100000
    NO_FORCED_WRITE = 0b00001000000
    NO_SHUTDOWN = 0b00010000000
    NO_SERVER_SHUTDOWN = 0b00100000000
    SERVER_CONFIG = 0b01000000000
    QUOTED_FILENAME = 0b10000000000

class SvcRepairFlag(IntFlag):
    "isc_spb_rpr_* flags for ServiceAction.REPAIR"
    VALIDATE_DB = 0x01
    SWEEP_DB = 0x02
    MEND_DB = 0x04
    LIST_LIMBO_TRANS = 0x08
    CHECK_DB = 0x10
    IGNORE_CHECKSUM = 0x20
    KILL_SHADOWS = 0x40
    FULL = 0x80
    ICU = 0x0800
    #
    CORRUPTION_CHECK = VALIDATE_DB | CHECK_DB | FULL | IGNORE_CHECKSUM
    REPAIR = MEND_DB | FULL | IGNORE_CHECKSUM

class SvcStatFlag(IntFlag):
    "isc_spb_sts_* flags for ServiceAction.DB_STATS"
    NONE = 0
    DATA_PAGES = 0x01
    DB_LOG = 0x02
    HDR_PAGES = 0x04
    IDX_PAGES = 0x08
    SYS_RELATIONS = 0x10
    RECORD_VERSIONS = 0x20
    NOCREATION = 0x80
    ENCRYPTION = 0x100  # Firebird 3.0
    DEFAULT = DATA_PAGES | IDX_PAGES

class SvcBackupFlag(IntFlag):
    "isc_spb_bkp_* flags for ServiceAction.BACKUP"
    NONE = 0
    IGNORE_CHECKSUMS = 0x01
    IGNORE_LIMBO = 0x02
    METADATA_ONLY = 0x04
    NO_GARBAGE_COLLECT = 0x08
    OLD_DESCRIPTIONS = 0x10
    NON_TRANSPORTABLE = 0x20
    CONVERT = 0x40
    EXPAND = 0x80
    NO_TRIGGERS = 0x8000
    # Firebird 4
    ZIP = 0x010000

class SvcRestoreFlag(IntFlag):
    "isc_spb_res_* flags for ServiceAction.RESTORE"
    METADATA_ONLY = 0x04
    DEACTIVATE_IDX = 0x0100
    NO_SHADOW = 0x0200
    NO_VALIDITY = 0x0400
    ONE_AT_A_TIME = 0x0800
    REPLACE = 0x1000
    CREATE = 0x2000
    USE_ALL_SPACE = 0x4000
    NO_TRIGGERS = 0x8000

class SvcNBackupFlag(IntFlag):
    "isc_spb_nbk_* flags for ServiceAction.NBAK"
    NONE = 0
    NO_TRIGGERS = 0x01
    # Firebird 4
    IN_PLACE = 0x02

class SvcPropertiesFlag(IntFlag):
    "isc_spb_prp_* flags for ServiceAction.PROPERTIES"
    ACTIVATE = 0x0100
    DB_ONLINE = 0x0200
    NOLINGER = 0x0400

class ImpFlags(IntFlag):
    "Implementation - Endianness"
    LITTLE_ENDIAN = 0
    BIG_ENDIAN = 1

# Dataclasses

@dataclass(frozen=True)
class ItemMetadata:
    """Information for single item from `iMessageMetadata`.

This `dataclass` is used internally, and it's not intended for general use.

Attributes:
    field (str): Field name
    relation (str): Relation name
    owner (str): Owner name
    alias (str): Field alias
    datatype (SQLDataType): Data type
    nullable (bool): Whether NULLs are allowed
    subtype (int): Data sub-type
    length (int): Size of raw field data in message buffer
    scale (int): Field scale
    charset (int): Character set
    offset (int): Offset of raw field data in message buffer
    null_offset (int): Offset of null flag in message buffer
"""
    field: str
    relation: str
    owner: str
    alias: str
    datatype: SQLDataType
    nullable: bool
    subtype: int
    length: int
    scale: int
    charset: int
    offset: int
    null_offset: int

@dataclass
class TableAccessStats:
    """Table access statistics.

Data structure returned by `.Connection.get_table_access_stats()`.

Attributes:
    table_id (int): Relation ID
    sequential (int): Number of sequential table scans (row reads)
    indexed (int): Number of reads done via an index
    inserts (int): Number of inserts
    updates (int): Number of updates
    deletes (int): Number of deleted
    backouts (int): Number of removals of a version of a record
    purges (int): Number of removals of old versions of fully mature records (records that
                  are committed, so that older ancestor versions are no longer needed)
    expunges (int): Number of removals of a record and all of its ancestors, for records
                    whose deletions have been committed
"""
    table_id: int
    sequential: int = None
    indexed: int = None
    inserts: int = None
    updates: int = None
    deletes: int = None
    backouts: int = None
    purges: int = None
    expunges: int = None

@dataclass
class UserInfo:
    """Information about Firebird user

Data structure returned by `.Service.get_user()` and `.Service.get_users()`.

Attributes:
    user_name (str): User (login) name
    password (str): User password
    first_name (str): First name
    middle_name (str): Middle name
    last_name (str): Last name
    user_id (int): User ID
    group_id (int): User Group ID
    group_name (str): Group name
    admin (bool): True is user has admin priviledges
"""
    user_name: str
    password: str = None
    first_name: str = None
    middle_name: str = None
    last_name: str = None
    user_id: int = None
    group_id: int = None
    group_name: str = None
    admin: bool = None

# Constants required by Python DB API 2.0 specification

#: String constant stating the supported DB API level.
apilevel: str = '2.0'
#: Integer constant stating the level of thread safety the interface supports.
#: Curretly `1` = Threads may share the module, but not connections.
threadsafety: int = 1
#: String constant stating the type of parameter marker formatting expected by
#: the interface. `'qmark'` = Question mark style, e.g. '...WHERE name=?'
paramstyle: str = 'qmark'

# Named positional constants to be used as indices into the description
# attribute of a cursor.

DESCRIPTION_NAME = 0
DESCRIPTION_TYPE_CODE = 1
DESCRIPTION_DISPLAY_SIZE = 2
DESCRIPTION_INTERNAL_SIZE = 3
DESCRIPTION_PRECISION = 4
DESCRIPTION_SCALE = 5
DESCRIPTION_NULL_OK = 6

# Types Required by Python DB-API 2.0

#: This callable constructs an object holding a date value.
Date = datetime.date
#: This callable constructs an object holding a time value.
Time = datetime.time
#: This callable constructs an object holding a time stamp value.
Timestamp = datetime.datetime

def DateFromTicks(ticks: float) -> Date:
    """Constructs an object holding a date value from the given ticks value
(number of seconds since the epoch)."""
    return Date(time.localtime(ticks)[:3])

def TimeFromTicks(ticks: float) -> Time:
    """Constructs an object holding a time value from the given ticks value
(number of seconds since the epoch)."""
    return Time(time.localtime(ticks)[3:6])

def TimestampFromTicks(ticks: float) -> Timestamp:
    """Constructs an object holding a time stamp value from the given ticks value
(number of seconds since the epoch)."""
    return Timestamp(time.localtime(ticks)[:6])

#: This callable constructs an object capable of holding a binary (long) string value.
Binary = memoryview

class DBAPITypeObject:
    "Python DB API 2.0 - type support"
    def __init__(self, *values):
        self.values = values
    def __cmp__(self, other):
        if other in self.values:
            return 0
        if other < self.values:
            return 1
        return -1

#: This type object is used to describe columns in a database that are string-based (e.g. CHAR).
STRING = DBAPITypeObject(str)
#: This type object is used to describe (long) binary columns in a database (e.g. LONG, RAW, BLOBs).
BINARY = DBAPITypeObject(bytes, bytearray)
#: This type object is used to describe numeric columns in a database.
NUMBER = DBAPITypeObject(int, float, decimal.Decimal)
#: This type object is used to describe date/time columns in a database.
DATETIME = DBAPITypeObject(datetime.datetime, datetime.date, datetime.time)
#: This type object is used to describe the "Row ID" column in a database.
ROWID = DBAPITypeObject()

# Types for type hints

#: DB API 2.0 Cursor DESCRIPTION
DESCRIPTION = Tuple[str, type, int, int, int, int, bool]
#: Callback that accepts line of text output
CB_OUTPUT_LINE = Callable[[str], None]

class Transactional(Protocol):  # pragma: no cover
    """Protocol type for object that supports transactional processing."""
    def begin(self, tpb: bytes = None) -> None:
        "Begin transaction."
        ...
    def commit(self, *, retaining: bool = False) -> None:
        "Commit transaction."
        ...
    def rollback(self, *, retaining: bool = False, savepoint: str = None) -> None:
        "Rollback transaction."
        ...
    def is_active(self) -> bool:
        "Returns true if transaction is active"
        ...

FS_ENCODING = sys.getfilesystemencoding()

# Info structural codes
isc_info_end = 1
isc_info_truncated = 2
isc_info_error = 3
isc_info_data_not_ready = 4

# Internal
_master = None
_util = None
_thns = threading.local()

# Managers for Parameter buffers

class TPB:
    "Transaction Parameter Buffer"

    def __init__(self, *, access_mode: TraAccessMode = TraAccessMode.WRITE,
                 isolation: Isolation = Isolation.SNAPSHOT,
                 lock_timeout: int = -1, no_auto_undo: bool = False,
                 auto_commit: bool = False, ignore_limbo: bool = False):
        self.access_mode: TraAccessMode = access_mode
        self.isolation: Isolation = isolation
        self.lock_timeout: int = lock_timeout
        self.no_auto_undo: bool = no_auto_undo
        self.auto_commit: bool = auto_commit
        self.ignore_limbo: bool = ignore_limbo
        self._table_reservation: List[Tuple[str, TableShareMode, TableAccessMode]] = []
    def clear(self) -> None:
        "Clear all information."
        self.access_mode = TraAccessMode.WRITE
        self.isolation = Isolation.SNAPSHOT
        self.lock_timeout = -1
        self.no_auto_undo = False
        self.auto_commit = False
        self.ignore_limbo = False
        self._table_reservation = []
    def parse_buffer(self, buffer: bytes) -> None:
        "Load information from TPB."
        self.clear()
        api = a.get_api()
        with api.util.get_xpb_builder(XpbKind.TPB, buffer) as tpb:
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
                elif tag in TableAccessMode._value2member_map_:
                    tbl_access = TableAccessMode(tag)
                    tbl_name = tpb.get_string()
                    tpb.move_next()
                    if tpb.is_eof():
                        raise ValueError(f"Missing share mode value in table {tbl_name} reservation")
                    if (val := tpb.get_tag()) not in TableShareMode._value2member_map_:
                        raise ValueError(f"Missing share mode value in table {tbl_name} reservation")
                    tbl_share = TableShareMode(val)
                    self.reserve_table(tbl_name, tbl_share, tbl_access)
                tpb.move_next()
    def get_buffer(self) -> bytes:
        "Create TPB from stored information."
        with a.get_api().util.get_xpb_builder(XpbKind.TPB) as tpb:
            tpb.insert_tag(self.access_mode)
            isolation = (Isolation.READ_COMMITTED_RECORD_VERSION
                         if self.isolation == Isolation.READ_COMMITTED
                         else self.isolation)
            if isolation in [Isolation.SNAPSHOT, Isolation.SERIALIZABLE]:
                tpb.insert_tag(isolation)
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
            for table in self._table_reservation:
                # Access mode + table name
                tpb.insert_string(table[2], table[0])
                tpb.insert_tag(table[1])  # Share mode
            result = tpb.get_buffer()
        return result
    def reserve_table(self, name: str, share_mode: TableShareMode, access_mode: TableAccessMode) -> None:
        "Set information about table reservation"
        self._table_reservation.append((name, share_mode, access_mode))

class DPB:
    "Database Parameter Buffer"

    def __init__(self, *, user: str = None, password: str = None, role: str = None,
                 trusted_auth: bool = False, sql_dialect: int = 3, timeout: int = None,
                 charset: str = 'UTF8', cache_size: int = None, no_gc: bool = False,
                 no_db_triggers: bool = False, no_linger: bool = False,
                 utf8filename: bool = False, dbkey_scope: DBKeyScope = None,
                 dummy_packet_interval: int = None, overwrite: bool = False,
                 db_cache_size: int = None, forced_writes: bool = None,
                 reserve_space: bool = None, page_size: int = None, read_only: bool = False,
                 sweep_interval: int = None, db_sql_dialect: int = None, db_charset: str = None,
                 config: str = None, auth_plugin_list: str = None):
        # Available options:
        # AuthClient, WireCryptPlugin, Providers, ConnectionTimeout, WireCrypt,
        # WireConpression, DummyPacketInterval, RemoteServiceName, RemoteServicePort,
        # RemoteAuxPort, TcpNoNagle, IpcName, RemotePipeName
        self.config: Optional[str] = config
        self.auth_plugin_list: str = auth_plugin_list
        # Connect
        self.trusted_auth: bool = trusted_auth
        self.user: str = user
        self.password: str = password
        self.role: str = role
        self.sql_dialect: int = sql_dialect
        self.charset: str = charset
        self.timeout: Optional[int] = timeout
        self.dummy_packet_interval: Optional[int] = dummy_packet_interval
        self.cache_size: int = cache_size
        self.no_gc: bool = no_gc
        self.no_db_triggers: bool = no_db_triggers
        self.no_linger: bool = no_linger
        self.utf8filename: bool = utf8filename
        self.dbkey_scope: Optional[DBKeyScope] = dbkey_scope
        # For db create
        self.page_size: Optional[int] = page_size
        self.overwrite: bool = overwrite
        self.db_buffers = None
        self.db_cache_size: Optional[int] = db_cache_size
        self.forced_writes: Optional[bool] = forced_writes
        self.reserve_space: Optional[bool] = reserve_space
        self.read_only: bool = read_only
        self.sweep_interval: Optional[int] = sweep_interval
        self.db_sql_dialect: Optional[int] = db_sql_dialect
        self.db_charset: Optional[str] = db_charset
    def clear(self) -> None:
        "Clear all information."
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
        "Load information from DPB."
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
    def get_buffer(self, *, for_create: bool = False) -> bytes:
        "Create DPB from stored information."
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

    def __init__(self, *, user: str = None, password: str = None, trusted_auth: bool = False,
                 config: str = None, auth_plugin_list: str = None):
        self.user: str = user
        self.password: str = password
        self.trusted_auth: bool = trusted_auth
        self.config: str = config
        self.auth_plugin_list: str = auth_plugin_list
    def clear(self) -> None:
        "Clear all information."
        self.user = None
        self.password = None
        self.trusted_auth = False
        self.config = None
    def parse_buffer(self, buffer: bytes) -> None:
        "Load information from SPB_ATTACH."
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
        "Create SPB_ATTACH from stored information."
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


class Buffer(MemoryBuffer):
    "MemoryBuffer with extensions"
    def __init__(self, init: Union[int, bytes], size: int = None, *,
                 factory: Type[BufferFactory]=BytesBufferFactory,
                 max_size: Union[int, Sentinel]=UNLIMITED, byteorder: ByteOrder=ByteOrder.LITTLE):
        super().__init__(init, size, factory=factory, eof_marker=isc_info_end,
                         max_size=max_size, byteorder=byteorder)
    def seek_last_data(self) -> int:
        "Set the position in buffer to first non-zero byte when searched from the end of buffer."
        self.pos = self.last_data
    def get_tag(self) -> int:
        "Read 1 byte number (c_ubyte)"
        return self.read_byte()
    def rewind(self) -> None:
        "Set current position in buffer to beginning."
        self.pos = 0
    def is_truncated(self) -> bool:
        "Return True when positioned on `isc_info_truncated` tag"
        return safe_ord(self.raw[self.pos]) == isc_info_truncated

class CBuffer(Buffer):
    "ctypes MemoryBuffer with extensions"
    def __init__(self, init: Union[int, bytes], size: int = None, *,
                 max_size: Union[int, Sentinel]=UNLIMITED, byteorder: ByteOrder=ByteOrder.LITTLE):
        super().__init__(init, size, factory=CTypesBufferFactory, max_size=max_size, byteorder=byteorder)

# ------------------------------------------------------------------------------
# Interface wrappers
# ------------------------------------------------------------------------------
# IVersioned(1)
class iVersioned:
    "IVersioned interface wrapper"
    VERSION = 1
    def __init__(self, intf):
        self._as_parameter_ = intf
        if intf and self.vtable.version < self.VERSION:  # pragma: no cover
            raise InterfaceError(f"Wrong interface version {self.vtable.version}, expected {self.VERSION}")
    def __get_status(self) -> iStatus:
        result = getattr(_thns, 'status', None)
        if result is None:
            result = _master.get_status()
            _thns.status = result
        return result
    def __report(self, cls: Union[Error, Warning], vector_ptr: a.ISC_STATUS_ARRAY_PTR) -> None:
        msg = _util.format_status(self.status)
        sqlstate = create_string_buffer(6)
        a.api.fb_sqlstate(sqlstate, vector_ptr)
        i = 0
        gds_codes = []
        sqlcode = a.api.isc_sqlcode(vector_ptr)
        while vector_ptr[i] != 0:
            if vector_ptr[i] == 1:
                i += 1
                if (vector_ptr[i] & 0x14000000) == 0x14000000:
                    gds_codes.append(vector_ptr[i])
                    if (vector_ptr[i] == 335544436) and (vector_ptr[i + 1] == 4):
                        i += 2
                        sqlcode = vector_ptr[i]
            i += 1
        self.status.init()
        return cls(msg, sqlstate=sqlstate.value.decode(),
                   gds_codes=tuple(gds_codes), sqlcode=sqlcode,)
    def _check(self) -> None:
        state = self.status.get_state()
        if StateFlag.ERRORS in state:
            raise self.__report(DatabaseError, self.status.get_errors())
        if StateFlag.WARNINGS in state:  # pragma: no cover
            raise self.__report(Warning, self.status.get_warning())
    vtable = property(lambda self: self._as_parameter_.contents.vtable.contents)
    status: iStatus = property(__get_status)

# IReferenceCounted(2)
class iReferenceCounted(iVersioned):
    "IReferenceCounted interface wrapper"
    VERSION = 2
    def __init__(self, intf):
        super().__init__(intf)
        self._refcnt: int = 1
    def __del__(self):
        if self._refcnt > 0:
            self.release()
    def __enter__(self) -> iReferenceCounted:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()
    def add_ref(self) -> None:
        "Increase the reference by one"
        self._refcnt += 1
        self.vtable.addRef(cast(self, a.IReferenceCounted))
    def release(self) -> int:
        "Decrease the reference by one"
        self._refcnt -= 1
        result = self.vtable.release(cast(self, a.IReferenceCounted))
        return result

# IDisposable(2)
class iDisposable(iVersioned):
    "IDisposable interface wrapper"
    VERSION = 2
    def __init__(self, intf):
        super().__init__(intf)
        self._disposed: bool = False
    def __del__(self):
        if not self._disposed:
            self.dispose()
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.dispose()
    def dispose(self) -> None:
        "Dispose the interfaced object"
        if not self._disposed:
            self.vtable.dispose(cast(self, a.IDisposable))
        self._disposed = True

# IStatus(3) : Disposable
class iStatus(iDisposable):
    "Class that wraps IStatus interface for use from Python"
    VERSION = 3
    def init(self) -> None:
        "Cleanup interface, set it to initial state"
        self.vtable.init(self)
    def get_state(self) -> StateFlag:
        "Returns state flags, may be OR-ed."
        return StateFlag(self.vtable.getState(self))
    def set_errors2(self, length: int, value: ByteString) -> None:
        "Set contents of errors vector with length explicitly specified in a call"
        self.vtable.setErrors2(self, length, value)
    def set_warning2(self, length: int, value: ByteString) -> None:
        "Set contents of warnings vector with length explicitly specified in a call"
        self.vtable.setWarnings2(self, length, value)
    def set_errors(self, value: ByteString) -> None:
        "Set contents of errors vector, length is defined by value context"
        self.vtable.setErrors(self, value)
    def set_warnings(self, value: ByteString) -> None:
        "Set contents of warnings vector, length is defined by value context"
        self.vtable.setWarnings(self, value)
    def get_errors(self) -> a.ISC_STATUS_ARRAY_PTR:
        "Returns errors vector"
        return self.vtable.getErrors(self)
    def get_warning(self) -> a.ISC_STATUS_ARRAY_PTR:
        "Returns warnings vector"
        return self.vtable.getWarnings(self)
    def clone(self) -> iStatus:
        "Create clone of current interface"
        return iStatus(self.vtable.clone(self))

# IPluginBase(3) : ReferenceCounted
class iPluginBase(iReferenceCounted):
    "IPluginBase interface wrapper"
    VERSION = 3
    def set_owner(self, r: iReferenceCounted) -> None:
        "Set the owner"
        self.vtable.setOwner(self, r)
    def get_owner(self) -> iReferenceCounted:
        "Returns owner"
        return iReferenceCounted(self.vtable.getOwner(self))

# IConfigEntry(3) : ReferenceCounted
class iConfigEntry(iReferenceCounted):
    "Class that wraps IConfigEntry interface for use from Python"
    VERSION = 3
    def get_name(self) -> str:
        "Returns key name"
        return self.vtable.getName(self).decode()
    def get_value(self) -> str:
        "Returnd value string value"
        return self.vtable.getValue(self).decode()
    def get_int_value(self) -> int:
        "Returns value as integer"
        return self.vtable.getIntValue(self).value
    def get_bool_value(self) -> bool:
        "Returns value as boolean"
        return self.vtable.getBoolValue(self).value
    def get_sub_config(self, status: iStatus) -> iConfig:
        "Treats sub-entries as separate configuration file and returns IConfig interface for it"
        result = iConfig(self.vtable.getSubConfig(self, status))
        return result

# IConfig(3) : ReferenceCounted
class iConfig(iReferenceCounted):
    "Class that wraps IConfig interface for use from Python"
    VERSION = 3
    def find(self, name: str) -> iConfigEntry:
        "Find entry by name"
        result = self.vtable.find(self, self.status, name.encode())
        self._check()
        return iConfigEntry(result)
    def find_value(self, name: str, value: str) -> iConfigEntry:
        "Find entry by name and value"
        result = self.vtable.findValue(self, self.status, name.encode(), value.encode())
        self._check()
        return iConfigEntry(result)
    def find_pos(self, name: str, pos: int) -> iConfigEntry:
        """Find entry by name and position.
If configuration file contains lines::

  Db=DBA
  Db=DBB
  Db=DBC

call to `find_pos(status, “Db”, 2)` will return entry with value DBB.
"""
        result = self.vtable.findPos(self, self.status, name, pos)
        self._check()
        return iConfigEntry(result)

# IFirebirdConf(3) : ReferenceCounted
class iFirebirdConf(iReferenceCounted):
    "Class that wraps IFirebirdConf interface for use from Python"
    VERSION = 3
    def get_key(self, name: str) -> int:
        """Returns key for configuration parameter.

Note:
    If parameter with given name does not exists, returns 0xffffffff.
"""
        return self.vtable.getKey(self, name.encode())
    def as_integer(self, key: int) -> int:
        "Returns integer value of conf. parameter"
        return self.vtable.asInteger(self, key)
    def as_string(self, key: int) -> str:
        "Returns string value of conf. parameter"
        value = self.vtable.asString(self, key)
        if value is not None:
            value = value.decode()
        return value
    def as_boolean(self, key: str) -> bool:
        "Returns boolean value of conf. parameter"
        return self.vtable.asBoolean(self, key)

# IPluginManager(2) : Versioned
class iPluginManager(iVersioned):
    "IPluginManager interface wrapper. This is only STUB."
    VERSION = 2

# IConfigManager(2) : Versioned
class iConfigManager(iVersioned):
    "Class that wraps IConfigManager interface for use from Python"
    VERSION = 2
    def get_directory(self, dirspec: DirectoryCode) -> str:
        "Returns location of appropriate directory in current firebird instance"
        return self.vtable.getDirectory(self, a.Cardinal(dirspec)).decode()
    def get_firebird_conf(self) -> iFirebirdConf:
        "Returns interface to access default configuration values (from firebird.conf)"
        return iFirebirdConf(self.vtable.getFirebirdConf(self))
    def get_database_conf(self, database: str) -> iFirebirdConf:
        """Returns interface to access db-specific configuration.
Takes into an account firebird.conf and appropriate part of databases.conf."""
        return iFirebirdConf(self.vtable.getDatabaseConf(self, database.encode()))
    def get_plugin_config(self, plugin: str) -> iConfig:
        "Returns interface to access named plugin configuration"
        return iConfig(self.vtable.getPluginConfig(self, plugin.encode()))
    def get_install_directory(self) -> str:
        "Returns directory where firebird is installed"
        return self.vtable.getInstallDirectory(self).decode()
    def get_root_directory(self) -> str:
        "Returns root directory of current instance, in single-instance case usually matches install directory"
        return self.vtable.getRootDirectory(self).decode()

# IBlob(3) : ReferenceCounted
class iBlob(iReferenceCounted):
    "Class that wraps IBlob interface for use from Python"
    VERSION = 3
    def get_info(self, items: bytes, buffer: bytes) -> None:
        "Replaces `isc_blob_info()`"
        self.vtable.getInfo(self, self.status, len(items), items, len(buffer), buffer)
        self._check()
    def get_segment(self, size: int, buffer: a.c_void_p, bytes_read: a.Cardinal) -> StateResult:
        """Replaces `isc_get_segment()`. Unlike it never returns `isc_segstr_eof`
and `isc_segment` errors (that are actually not errors), instead returns completion
codes IStatus::RESULT_NO_DATA and IStatus::RESULT_SEGMENT, normal return is IStatus::RESULT_OK."""
        result = self.vtable.getSegment(self, self.status, size, buffer, bytes_read)
        self._check()
        return StateResult(result)
    def put_segment(self, length: int, buffer: Any) -> None:
        "Replaces `isc_put_segment()`"
        self.vtable.putSegment(self, self.status, length, buffer)
        self._check()
    def cancel(self) -> None:
        "Replaces `isc_cancel_blob()`. On success releases interface."
        self.vtable.cancel(self, self.status)
        self._check()
        self._refcnt -= 1
    def close(self) -> None:
        "Replaces `isc_close_blob()`. On success releases interface."
        self.vtable.close(self, self.status)
        self._check()
        self._refcnt -= 1
    def seek(self, mode: int, offset: int) -> int:
        "Replaces isc_seek_blob()"
        result = self.vtable.seek(self, self.status, mode, offset)
        self._check()
        return result
    def get_info2(self, code: BlobInfoCode) -> Any:
        "Returns information about BLOB"
        blob_info = (0).to_bytes(10, 'little')
        self.get_info(bytes([code]), blob_info)
        i = 0
        while blob_info[i] != isc_info_end:
            _code = blob_info[i]
            i += 1
            if _code == code:
                size = (0).from_bytes(blob_info[i: i + 2], 'little')
                result = (0).from_bytes(blob_info[i + 2: i + 2 + size], 'little')
                i += size + 2
        return result

# ITransaction(3) : ReferenceCounted
class iTransaction(iReferenceCounted):
    "Class that wraps ITransaction interface for use from Python"
    VERSION = 3
    def get_info(self, items: bytes, buffer: bytes) -> None:
        "Replaces `isc_transaction_info()`"
        self.vtable.getInfo(self, self.status, len(items), items, len(buffer), buffer)
        self._check()
    def prepare(self, message: bytes = None) -> None:
        "Replaces `isc_prepare_transaction2()`"
        self.vtable.prepare(self, self.status, 0 if message is None else len(message), message)
        self._check()
    def commit(self) -> None:
        "Replaces `isc_commit_transaction()`"
        self.vtable.commit(self, self.status)
        self._check()
        self._refcnt -= 1
    def commit_retaining(self) -> None:
        "Replaces `isc_commit_retaining()`"
        self.vtable.commitRetaining(self, self.status)
        self._check()
    def rollback(self) -> None:
        "Replaces `isc_rollback_transaction()`"
        self.vtable.rollback(self, self.status)
        self._check()
        self._refcnt -= 1
    def rollback_retaining(self) -> None:
        "Replaces `isc_rollback_retaining()`"
        self.vtable.rollbackRetaining(self, self.status)
        self._check()
    def disconnect(self) -> None:
        "Replaces `fb_disconnect_transaction()`"
        self.vtable.disconnect(self, self.status)
        self._check()
    def join(self, transaction: iTransaction) -> iTransaction:
        """Joins current transaction and passed as parameter transaction into
single distributed transaction (using Dtc). On success both current transaction
and passed as parameter transaction are released and should not be used any more."""
        result = self.vtable.join(self, self.status, transaction)
        self._check()
        self._refcnt -= 1
        transaction._refcnt -= 1
        return iTransaction(result)
    def validate(self, attachment: iAttachment) -> iTransaction:
        "This method is used to support distributed transactions coordinator"
        result = self.vtable.validate(self, self.status, attachment)
        self._check()
        return self if result is not None else None
    def enter_dtc(self) -> iTransaction:  # pragma: no cover
        "This method is used to support distributed transactions coordinator"
        raise InterfaceError("Method not supported")

# IMessageMetadata(3) : ReferenceCounted
class iMessageMetadata(iReferenceCounted):
    "Class that wraps IMessageMetadata interface for use from Python"
    VERSION = 3
    def get_count(self) -> int:
        """Returns number of fields/parameters in a message. In all calls,
containing index parameter, it's value should be: 0 <= index < getCount()."""
        result = self.vtable.getCount(self, self.status)
        self._check()
        return result
    def get_field(self, index: int) -> str:
        "Returns field name"
        result = self.vtable.getField(self, self.status, index).decode()
        self._check()
        return result
    def get_relation(self, index: int) -> str:
        "Returns relation name (from which given field is selected)"
        result = self.vtable.getRelation(self, self.status, index).decode()
        self._check()
        return result
    def get_owner(self, index: int) -> str:
        "Returns relation's owner name"
        result = self.vtable.getOwner(self, self.status, index).decode()
        self._check()
        return result
    def get_alias(self, index: int) -> str:
        "Returns field alias"
        result = self.vtable.getAlias(self, self.status, index).decode()
        self._check()
        return result
    def get_type(self, index: int) -> SQLDataType:
        "Returns field SQL type"
        result = self.vtable.getType(self, self.status, index)
        self._check()
        return SQLDataType(result)
    def is_nullable(self, index: int) -> bool:
        "Returns True if field is nullable"
        result = self.vtable.isNullable(self, self.status, index)
        self._check()
        return result
    def get_subtype(self, index: int) -> int:
        "Returns blob field subtype (0 – binary, 1 – text, etc.)"
        result = self.vtable.getSubType(self, self.status, index)
        self._check()
        return result
    def get_length(self, index: int) -> int:
        "Returns maximum field length"
        result = self.vtable.getLength(self, self.status, index)
        self._check()
        return result
    def get_scale(self, index: int) -> int:
        "Returns scale factor for numeric field"
        result = self.vtable.getScale(self, self.status, index)
        self._check()
        return result
    def get_charset(self, index: int) -> int:
        "Returns character set for character field and text blob"
        result = self.vtable.getCharSet(self, self.status, index)
        self._check()
        return result
    def get_offset(self, index: int) -> int:
        "Returns offset of field data in message buffer (use it to access data in message buffer)"
        result = self.vtable.getOffset(self, self.status, index)
        self._check()
        return result
    def get_null_offset(self, index: int) -> int:
        "Returns offset of null indicator for a field in message buffer"
        result = self.vtable.getNullOffset(self, self.status, index)
        self._check()
        return result
    def get_builder(self) -> iMetadataBuilder:
        "Returns MetadataBuilder interface initialized with this message metadata"
        result = iMetadataBuilder(self.vtable.getBuilder(self, self.status))
        self._check()
        return result
    def get_message_length(self) -> int:
        "Returns length of message buffer (use it to allocate memory for the buffer)"
        result = self.vtable.getMessageLength(self, self.status)
        self._check()
        return result

# IMetadataBuilder(3) : ReferenceCounted
class iMetadataBuilder(iReferenceCounted):
    "Class that wraps IMetadataBuilder interface for use from Python"
    VERSION = 3
    def set_type(self, index: int, field_type: SQLDataType) -> None:
        "Set SQL type of a field"
        self.vtable.setType(self, self.status, index, field_type)
        self._check()
    def set_subtype(self, index: int, subtype: int) -> None:
        "Set blob field subtype"
        self.vtable.setSubType(self, self.status, index, subtype)
        self._check()
    def set_length(self, index: int, length: int) -> None:
        "Set maximum length of character field"
        self.vtable.setLength(self, self.status, index, length)
        self._check()
    def set_charset(self, index: int, charset: int) -> None:
        "Set character set for character field and text blob"
        self.vtable.setCharSet(self, self.status, index, charset)
        self._check()
    def set_scale(self, index: int, scale: int) -> None:
        "Set scale factor for numeric field"
        self.vtable.setScale(self, self.status, index, scale)
        self._check()
    def truncate(self, count: int) -> None:
        "Truncate message to contain not more than count fields"
        self.vtable.truncate(self, self.status, count)
        self._check()
    def move_name_to_index(self, name: str, index: int) -> None:
        "Reorganize fields in a message – move field “name” to given position"
        self.vtable.moveNameToIndex(self, self.status, name.encode(), index)
        self._check()
    def remove(self, index: int) -> None:
        "Remove field"
        self.vtable.remove(self, self.status, index)
        self._check()
    def add_field(self) -> int:
        "Add field"
        result = self.vtable.addField(self, self.status)
        self._check()
        return result
    def get_metadata(self) -> iMessageMetadata:
        "Returns MessageMetadata interface built by this builder"
        result = iMessageMetadata(self.vtable.getMetadata(self, self.status))
        self._check()
        return result

# IResultSet(3) : ReferenceCounted
class iResultSet(iReferenceCounted):
    "Class that wraps IResultSet interface for use from Python"
    VERSION = 3
    def fetch_next(self, message: bytes) -> StateResult:
        """Fetch next record, replaces isc_dsql_fetch(). This method (and other
fetch methods) returns completion code Status::RESULT_NO_DATA when EOF is reached,
Status::RESULT_OK on success."""
        result = self.vtable.fetchNext(self, self.status, message)
        self._check()
        return StateResult(result)
    def fetch_prior(self, message: bytes) -> StateResult:
        "Fetch previous record"
        result = self.vtable.fetchPrior(self, self.status, message)
        self._check()
        return StateResult(result)
    def fetch_first(self, message: bytes) -> StateResult:
        "Fetch first record"
        result = self.vtable.fetchFirst(self, self.status, message)
        self._check()
        return StateResult(result)
    def fetch_last(self, message: bytes) -> StateResult:
        "Fetch last record"
        result = self.vtable.fetchLast(self, self.status, message)
        self._check()
        return StateResult(result)
    def fetch_absolute(self, position: int, message: bytes) -> StateResult:
        "Fetch record by it's absolute position in result set"
        result = self.vtable.fetchAbsolute(self, self.status, position, message)
        self._check()
        return StateResult(result)
    def fetch_relative(self, offset: int, message: bytes) -> StateResult:
        "Fetch record by position relative to current"
        result = self.vtable.fetchRelative(self, self.status, offset, message)
        self._check()
        return StateResult(result)
    def is_eof(self) -> bool:
        "Check for EOF"
        result = self.vtable.isEof(self, self.status)
        self._check()
        return result
    def is_bof(self) -> bool:
        "Check for BOF"
        result = self.vtable.isBof(self, self.status)
        self._check()
        return result
    def get_metadata(self) -> iMessageMetadata:
        """Get metadata for messages in result set, specially useful when result
set is opened by IAttachment::openCursor() call with NULL output metadata format
parameter (this is the only way to obtain message format in this case)"""
        result = self.vtable.getMetadata(self, self.status)
        self._check()
        return iMessageMetadata(result)
    def close(self) -> None:
        "Close result set, releases interface on success"
        self.vtable.close(self, self.status)
        self._check()
        self._refcnt -= 1
    def set_delayed_output_format(self, fmt: iMessageMetadata) -> None:
        "Information not available"
        self.vtable.setDelayedOutputFormat(self, self.status, fmt)
        self._check()

# IStatement(3) : ReferenceCounted
class iStatement(iReferenceCounted):
    "Class that wraps IStatement interface for use from Python"
    VERSION = 3
    def get_info(self, items: bytes, buffer: bytes) -> None:
        "Replaces `isc_dsql_sql_info()`"
        self.vtable.getInfo(self, self.status, len(items), items, len(buffer), buffer)
        self._check()
    def get_type(self) -> StatementType:
        "Statement type, currently can be found only in firebird sources in `dsql/dsql.h`"
        result = self.vtable.getType(self, self.status)
        self._check()
        return StatementType(result)
    def get_plan(self, detailed: bool) -> str:
        "Returns statement execution plan"
        result = self.vtable.getPlan(self, self.status, detailed)
        self._check()
        return result.decode() if result else result
    def get_affected_records(self) -> int:
        "Returns number of records affected by statement"
        result = self.vtable.getAffectedRecords(self, self.status)
        self._check()
        return result
    def get_input_metadata(self) -> iMessageMetadata:
        "Returns parameters metadata"
        result = self.vtable.getInputMetadata(self, self.status)
        self._check()
        return iMessageMetadata(result)
    def get_output_metadata(self) -> iMessageMetadata:
        "Returns output values metadata"
        result = self.vtable.getOutputMetadata(self, self.status)
        self._check()
        return iMessageMetadata(result)
    def execute(self, transaction: iTransaction, in_meta: iMessageMetadata, in_buffer: bytes,
                out_meta: iMessageMetadata, out_buffer: bytes) -> None:
        """Executes any SQL statement except returning multiple rows of data.
Partial analogue of `isc_dsql_execute2()` - in and out XSLQDAs replaced with input
and output messages with appropriate buffers."""
        result = self.vtable.execute(self, self.status, transaction, in_meta, in_buffer, out_meta, out_buffer)
        self._check()
        transaction._as_parameter_ = result
    def open_cursor(self, transaction: iTransaction, in_meta: iMessageMetadata, in_buffer: bytes,
                    out_meta: iMessageMetadata, flags: CursorFlag) -> iResultSet:
        """Executes SQL statement potentially returning multiple rows of data.
Returns ResultSet interface which should be used to fetch that data. Format of
output data is defined by outMetadata parameter, leaving it NULL default format
may be used. Parameter flags is needed to open bidirectional cursor setting it's
value to IStatement::CURSOR_TYPE_SCROLLABLE."""
        result = self.vtable.openCursor(self, self.status, transaction, in_meta, in_buffer, out_meta, flags)
        self._check()
        return iResultSet(result)
    def set_cursor_name(self, name: str) -> None:
        "Replaces `isc_dsql_set_cursor_name()`"
        self.vtable.setCursorName(self, self.status, name.encode())
        self._check()
    def free(self) -> None:
        "Free statement, releases interface on success"
        self.vtable.free(self, self.status)
        self._check()
        self._refcnt -= 1
    def get_flags(self) -> StatementFlag:
        "Returns flags describing how this statement should be executed, simplified replacement of getType() method"
        result = self.vtable.getFlags(self, self.status)
        self._check()
        return StatementFlag(result)

# IRequest(3) : ReferenceCounted
class iRequest(iReferenceCounted):
    "Class that wraps IRequest interface for use from Python"
    VERSION = 3
    def receive(self, level: int, msg_type: int, message: bytes) -> None:
        "Information not available"
        self.vtable.receive(self, self.status, level, msg_type, len(message), message)
        self._check()
    def send(self, level: int, msg_type: int, message: bytes) -> None:
        "Information not available"
        self.vtable.send(self, self.status, level, msg_type, len(message), message)
        self._check()
    def get_info(self, level: int, items: bytes, buffer: bytes) -> None:
        "Information not available"
        self.vtable.getInfo(self, self.status, level, len(items), items, len(buffer), buffer)
        self._check()
    def start(self, transaction: iTransaction, level: int) -> None:
        "Information not available"
        self.vtable.start(self, self.status, transaction, level)
        self._check()
    def start_and_send(self, transaction: iTransaction, level: int, msg_type: int, message: bytes) -> None:
        "Information not available"
        self.vtable.startAndSend(self, self.status, transaction, level, msg_type, len(message), message)
        self._check()
    def unwind(self, level: int) -> None:
        "Information not available"
        self.vtable.unwind(self, self.status, level)
        self._check()
    def free(self) -> None:
        "Information not available"
        self.vtable.free(self, self.status)
        self._check()
        self._refcnt -= 1

# IEvents(3) : ReferenceCounted
class iEvents(iReferenceCounted):
    "Class that wraps IEvents interface for use from Python"
    VERSION = 3
    def cancel(self) -> None:
        "Cancels events monitoring started by IAttachment::queEvents()"
        self.vtable.cancel(self, self.status)
        self._check()

# IAttachment(3) : ReferenceCounted
class iAttachment(iReferenceCounted):
    "Class that wraps IAttachment interface for use from Python"
    VERSION = 3
    def __init__(self, intf):
        super().__init__(intf)
        self.charset: str = 'ascii'
    def get_info(self, items: bytes, buffer: bytes) -> None:
        "Replaces `isc_database_info()`"
        self.vtable.getInfo(self, self.status, len(items), items, len(buffer), buffer)
        self._check()
    def start_transaction(self, tpb: bytes) -> iTransaction:
        """Partially replaces `isc_start_multiple()`, to start >1 transaction
distributed transactions coordinator should be used, also possible to join 2
transactions into single distributed transaction"""
        result = self.vtable.startTransaction(self, self.status, len(tpb), tpb)
        self._check()
        return iTransaction(result)
    def reconnect_transaction(self, id_: bytes) -> iTransaction:
        """Makes it possible to connect to a transaction in limbo. Id parameter
contains transaction number in network format of given length."""
        result = self.vtable.reconnectTransaction(self, self.status, len(id_), id_)
        self._check()
        return iTransaction(result)
    def compile_request(self, blr: bytes) -> iRequest:
        "Support of ISC API"
        result = self.vtable.compileRequest(self, self.status, len(blr), blr)
        self._check()
        return iRequest(result)
    def transact_request(self, transaction: iTransaction, blr: bytes, in_msg: bytes, out_msg: bytes) -> None:
        "Support of ISC API"
        self.vtable.transactRequest(self, self.status, transaction, len(blr), blr,
                                    len(in_msg), in_msg, len(out_msg), out_msg)
        self._check()
    def create_blob(self, transaction: iTransaction, id_: a.ISC_QUAD, bpb: bytes = None) -> iBlob:
        "Creates new blob, stores it's identifier in id, replaces `isc_create_blob2()`"
        result = self.vtable.createBlob(self, self.status, transaction, byref(id_),
                                        len(bpb) if bpb is not None else 0, bpb)
        self._check()
        return iBlob(result)
    def open_blob(self, transaction: iTransaction, id_: a.ISC_QUAD, bpb: bytes = None) -> iBlob:
        "Opens existing blob, replaces `isc_open_blob2()`"
        result = self.vtable.openBlob(self, self.status, transaction, byref(id_),
                                      len(bpb) if bpb is not None else 0, bpb)
        self._check()
        return iBlob(result)
    def get_slice(self, transaction: iTransaction, id_: a.ISC_QUAD, sdl: bytes,
                  param: bytes, slice_: bytes) -> int:
        "Support of ISC API"
        result = self.vtable.getSlice(self, self.status, transaction, byref(id_),
                                      len(sdl), sdl, len(param), param, len(slice_), slice_)
        self._check()
        return result
    def put_slice(self, transaction: iTransaction, id_: a.ISC_QUAD, sdl: bytes,
                  param: bytes, slice_: bytes) -> None:
        "Support of ISC API"
        self.vtable.putSlice(self, self.status, transaction, byref(id_),
                             len(sdl), sdl, len(param), param, len(slice_), slice_)
        self._check()
    def execute_dyn(self, transaction: iTransaction, dyn: bytes) -> None:
        "Support of ISC API"
        self.vtable.executeDyn(self, self.status, transaction, len(dyn), dyn)
        self._check()
    def prepare(self, transaction: iTransaction, stmt: str, dialect: int,
                flags: PreparePrefetchFlag = PreparePrefetchFlag.METADATA) -> iStatement:
        """Replaces `isc_dsql_prepare()`. Additional parameter flags makes it
possible to control what information will be preloaded from engine at once
(i.e. in single network packet for remote operation)."""
        b_stmt: bytes = stmt.encode(self.charset)
        result = self.vtable.prepare(self, self.status, transaction, len(b_stmt), b_stmt,
                                     dialect, flags)
        self._check()
        return iStatement(result)
    def execute(self, transaction: iTransaction, stmt: str, dialect: int,
                in_metadata: iMessageMetadata = None, in_buffer: bytes = None,
                out_metadata: iMessageMetadata = None, out_buffer: bytes = None) -> iTransaction:
        """Executes any SQL statement except returning multiple rows of data.
Partial analogue of `isc_dsql_execute2()` - in and out XSLQDAs replaced with
input and output messages with appropriate buffers."""
        b_stmt: bytes = stmt.encode(self.charset)
        result = self.vtable.execute(self, self.status, transaction, len(b_stmt), b_stmt,
                                     dialect, in_metadata, in_buffer, out_metadata, out_buffer)
        self._check()
        transaction._as_parameter_ = result
    def open_cursor(self, transaction: iTransaction, stmt: str, dialect: int,
                    in_metadata: iMessageMetadata, in_buffer: bytes,
                    out_metadata: iMessageMetadata, cursor_name: str, cursor_flags: int) -> iResultSet:
        """Executes SQL statement potentially returning multiple rows of data.
Returns iResultSet interface which should be used to fetch that data. Format of
output data is defined by out_metadata parameter, leaving it NULL default format
may be used. Parameter cursor_name specifies name of opened cursor (analogue of
`isc_dsql_set_cursor_name()`). Parameter cursor_flags is needed to open
bidirectional cursor setting it's value to Istatement::CURSOR_TYPE_SCROLLABLE."""
        b_stmt: bytes = stmt.encode(self.charset)
        result = self.vtable.openCursor(self, self.status, transaction, len(b_stmt), b_stmt,
                                        dialect, in_metadata, in_buffer, out_metadata,
                                        cursor_name.encode(self.charset), cursor_flags)
        self._check()
        return iResultSet(result)
    def que_events(self, callback: iEventCallbackImpl, events: bytes) -> iEvents:
        """Replaces `isc_que_events()` call. Instead callback function with
void* parameter callback interface is used."""
        result = self.vtable.queEvents(self, self.status, callback, len(events), events)
        self._check()
        return iEvents(result)
    def cancel_operation(self, option: int) -> None:
        "Replaces `fb_cancel_operation()`"
        self.vtable.cancelOperation(self, self.status, option)
        self._check()
    def ping(self) -> None:
        """Checks connection status. If test fails the only operation possible
with attachment is to close it."""
        self.vtable.ping(self, self.status)
        self._check()
    def detach(self) -> None:
        "Replaces `isc_detach_database()`. On success releases interface."
        self.vtable.detach(self, self.status)
        self._check()
    def drop_database(self) -> None:
        "Replaces `isc_drop_database()`. On success releases interface."
        self.vtable.dropDatabase(self, self.status)
        self._check()

# IService(3) : ReferenceCounted
class iService(iReferenceCounted):
    "Class that wraps IService interface for use from Python"
    VERSION = 3
    def detach(self) -> None:
        """Close attachment to services manager, on success releases interface.
Replaces `isc_service_detach()`."""
        self.vtable.detach(self, self.status)
        self._check()
        self._refcnt -= 1
    def query(self, send: bytes, receive: bytes, buffer: bytes) -> None:
        """Send and request information to/from service, with different `receive`
may be used for both running services and to obtain various server-wide information.
Replaces `isc_service_query()`."""
        self.vtable.query(self, self.status, 0 if send is None else len(send),
                          send, len(receive), receive, len(buffer), buffer)
        self._check()
    def start(self, spb: bytes) -> None:
        "Start utility in services manager. Replaces `isc_service_start()`."
        self.vtable.start(self, self.status, len(spb), spb)
        self._check()

# IProvider(4) : PluginBase
class iProvider(iPluginBase):
    "Class that wraps IProvider interface for use from Python"
    VERSION = 4
    def attach_database(self, filename: str, dpb: Optional[bytes] = None, encoding: str = 'ascii') -> iAttachment:
        "Replaces `isc_attach_database()`"
        result = self.vtable.attachDatabase(self, self.status, filename.encode(encoding),
                                            0 if dpb is None else len(dpb), dpb)
        self._check()
        return iAttachment(result)
    def create_database(self, filename: str, dpb: bytes, encoding: str = 'ascii') -> iAttachment:
        "Replaces `isc_create_database()`"
        result = self.vtable.createDatabase(self, self.status, filename.encode(encoding), len(dpb), dpb)
        self._check()
        return iAttachment(result)
    def attach_service_manager(self, service: str, spb: bytes) -> iService:
        "Replaces `isc_service_attach()`"
        result = self.vtable.attachServiceManager(self, self.status, service.encode(), len(spb), spb)
        self._check()
        return iService(result)
    def shutdown(self, timeout: int, reason: int) -> None:
        "Replaces `fb_shutdown()`"
        self.vtable.shutdown(self, self.status, timeout, reason)
        self._check()
    def set_dbcrypt_callback(self, callback: iCryptKeyCallbackImpl) -> None:
        "Sets database encryption callback interface that will be used for following database and service attachments"
        self.vtable.setDbCryptCallback(self, self.status, callback)
        self._check()

# IDtcStart(3) : Disposable
class iDtcStart(iDisposable):
    "Class that wraps IDtcStart interface for use from Python"
    VERSION = 3
    def add_attachment(self, attachment: iAttachment) -> None:
        "Adds attachment, transaction for it will be started with default TPB"
        self.vtable.addAttachment(self, self.status, attachment)
        self._check()
    def add_with_tpb(self, attachment: iAttachment, tpb: bytes) -> None:
        "Adds attachment and TPB which will be used to start transaction for this attachment"
        self.vtable.addWithTpb(self, self.status, attachment, len(tpb), tpb)
        self._check()
    def start(self) -> iTransaction:
        """Start distributed transaction for accumulated attachments.
On successful return DtcStart interface is disposed automatically."""
        result = self.vtable.start(self, self.status)
        self._check()
        self._disposed = True
        return iTransaction(result)

# IDtc(2) : Versioned
class iDtc(iVersioned):
    "Class that wraps IDtc interface for use from Python"
    VERSION = 2
    def join(self, one: iTransaction, two: iTransaction) -> iTransaction:
        """Joins 2 independent transactions into distributed transaction.
On success both transactions passed to join() are released and pointers to them
should not be used any more."""
        result = self.vtable.join(self, self.status, one, two)
        self._check()
        one._refcnt -= 1
        two._refcnt -= 1
        return iTransaction(result)
    def start_builder(self) -> iDtcStart:
        "Returns DtcStart interface"
        result = self.vtable.startBuilder(self, self.status)
        self._check()
        return iDtcStart(result)

# ITimerControl(2) : Versioned
class iTimerControl(iVersioned):
    "Class that wraps ITimerControl interface for use from Python"
    VERSION = 2
    def start(self, timer: iTimerImpl, microseconds: int) -> None:
        """Start ITimer to alarm after given delay (in microseconds, 10-6 seconds).
        Timer will be waked up only once after this call."""
        self.vtable.start(self, self.status, timer, microseconds)
        self._check()
    def stop(self, timer: iTimerImpl) -> None:
        """Stop ITimer. It's not an error to stop not started timer thus avoiding problems
        with races between stop() and timer alarm."""
        self.vtable.stop(self, self.status, timer)
        self._check()

# IXpbBuilder(3) : Disposable
class iXpbBuilder(iDisposable):
    "Class that wraps IXpbBuilder interface for use from Python"
    VERSION = 3
    def clear(self) -> None:
        "Reset builder to empty state."
        self.vtable.clear(self, self.status)
        self._check()
    def remove_current(self) -> None:
        "Removes current clumplet."
        self.vtable.removeCurrent(self, self.status)
        self._check()
    def insert_int(self, tag: int, value: int) -> None:
        "Inserts a clumplet with value representing integer in network format."
        self.vtable.insertInt(self, self.status, tag, value)
        self._check()
    def insert_bigint(self, tag: int, value: int) -> None:
        "Inserts a clumplet with value representing integer in network format."
        self.vtable.insertBigInt(self, self.status, tag, value)
        self._check()
    def insert_bytes(self, tag: int, value: bytes) -> None:
        "Inserts a clumplet with value containing passed bytes."
        self.vtable.insertBytes(self, self.status, tag, value, len(value))
        self._check()
    def insert_string(self, tag: int, value: str, encoding='ascii') -> None:
        "Inserts a clumplet with value containing passed string."
        self.vtable.insertString(self, self.status, tag, value.encode(encoding))
        self._check()
    def insert_tag(self, tag: int) -> None:
        "Inserts a clumplet without a value."
        self.vtable.insertTag(self, self.status, tag)
        self._check()
    def is_eof(self) -> bool:
        "Checks that there is no current clumplet."
        result = self.vtable.isEof(self, self.status)
        self._check()
        return result
    def move_next(self) -> None:
        "Moves to next clumplet."
        self.vtable.moveNext(self, self.status)
        self._check()
    def rewind(self) -> None:
        "Moves to first clumplet."
        self.vtable.rewind(self, self.status)
        self._check()
    def find_first(self, tag: int) -> bool:
        "Finds first clumplet with given tag."
        result = self.vtable.findFirst(self, self.status, tag)
        self._check()
        return result
    def find_next(self) -> bool:
        "Finds next clumplet with given tag."
        result = self.vtable.findNext(self, self.status)
        self._check()
        return result
    def get_tag(self) -> int:
        "Returns tag for current clumplet."
        result = self.vtable.getTag(self, self.status)
        self._check()
        return result
    def get_length(self) -> int:
        "Returns length of current clumplet value."
        result = self.vtable.getLength(self, self.status)
        self._check()
        return result
    def get_int(self) -> int:
        "Returns value of current clumplet as integer."
        result = self.vtable.getInt(self, self.status)
        self._check()
        return result
    def get_bigint(self) -> int:
        "Returns value of current clumplet as 64-bit integer."
        result = self.vtable.getBigInt(self, self.status)
        self._check()
        return result
    def get_string(self) -> str:
        "Returns value of current clumplet as string."
        result = self.vtable.getString(self, self.status)
        self._check()
        return string_at(result).decode()
    def get_bytes(self) -> bytes:
        "Returns value of current clumplet as bytes."
        buffer = self.vtable.getBytes(self, self.status)
        self._check()
        size = self.vtable.getLength(self, self.status)
        self._check()
        return string_at(buffer, size)
    def get_buffer_length(self) -> int:
        "Returns length of parameters block."
        result = self.vtable.getBufferLength(self, self.status)
        self._check()
        return result
    def get_buffer(self) -> bytes:
        "Returns the parameters block."
        buffer = self.vtable.getBuffer(self, self.status)
        self._check()
        size = self.get_buffer_length()
        self._check()
        return string_at(buffer, size)

# IUtil(2) : Versioned
class iUtil(iVersioned):
    "Class that wraps IUtil interface for use from Python"
    VERSION = 2
    def get_fb_version(self, attachment: iAttachment, callback: iVersionCallbackImpl) -> None:
        """Produce long and beautiful report about firebird version used.
It may be seen in ISQL when invoked with -Z switch."""
        self.vtable.getFbVersion(self, self.status, attachment, callback)
        self._check()
    def load_blob(self, blob_id: a.ISC_QUAD, attachment: iAttachment,
                  transaction: iTransaction, filename: str, is_text: bool) -> None:
        "Load blob from file"
        self.vtable.loadBlob(self, self.status, byref(blob_id), attachment,
                             transaction, filename.encode(), is_text)
        self._check()
    def dump_blob(self, blob_id: a.ISC_QUAD, attachment: iAttachment,
                  transaction: iTransaction, filename: str, is_text: bool) -> None:
        "Save blob to file"
        self.vtable.dumpBlob(self, self.status, byref(blob_id), attachment,
                             transaction, filename.encode(), is_text)
        self._check()
    def get_perf_counters(self, attachment: iAttachment, counters_set: str) -> int:
        "Get statistics for given attachment"
        result = a.Int64(0)
        self.vtable.getPerfCounters(self, self.status, attachment, counters_set.encode(),
                                    byref(result))
        self._check()
        return result
    def execute_create_database(self, stmt: str, dialect: int) -> iAttachment:
        """Execute “CREATE DATABASE ...” statement – ISC trick with NULL statement
handle does not work with interfaces."""
        b_stmt: bytes = stmt.encode()
        result = self.vtable.executeCreateDatabase(self, self.status, len(b_stmt), b_stmt,
                                                   dialect, byref(c_byte(1)))
        self._check()
        return iAttachment(result)
    def decode_date(self, date: Union[a.ISC_DATE, bytes]) -> datetime.date:
        "Replaces `isc_decode_sql_date()`"
        if isinstance(date, bytes):
            date = a.ISC_DATE.from_buffer_copy(date)
        year = a.Cardinal(0)
        month = a.Cardinal(0)
        day = a.Cardinal(0)
        self.vtable.decodeDate(self, date, byref(year), byref(month), byref(day))
        return datetime.date(year.value, month.value, day.value)
    def decode_time(self, atime: Union[a.ISC_TIME, bytes]) -> datetime.time:
        "Replaces `isc_decode_sql_time()`"
        if isinstance(atime, bytes):
            atime = a.ISC_TIME.from_buffer_copy(atime)
        hours = a.Cardinal(0)
        minutes = a.Cardinal(0)
        seconds = a.Cardinal(0)
        fractions = a.Cardinal(0)
        self.vtable.decodeTime(self, atime, byref(hours), byref(minutes),
                               byref(seconds), byref(fractions))
        return datetime.time(hours.value, minutes.value, seconds.value, fractions.value)
    def encode_date(self, date: datetime.date) -> a.ISC_DATE:
        "Replaces `isc_encode_sql_date()`"
        return self.vtable.encodeDate(self, date.year, date.month, date.day)
    def encode_time(self, atime: datetime.time) -> a.ISC_TIME:
        "Replaces isc_encode_sql_time()"
        return self.vtable.encodeTime(self, atime.hour, atime.minute, atime.second, atime.microsecond)
    def format_status(self, status: iStatus) -> str:
        "Replaces `fb_interpret()`. Size of buffer, passed into this method, should not be less than 50 bytes."
        buffer = create_string_buffer(1024)
        self.vtable.formatStatus(self, buffer, 1024, status)
        return buffer.value.decode()
    def get_client_version(self) -> int:
        "Returns integer, containing major version in byte 0 and minor version in byte 1"
        return self.vtable.getClientVersion(self)
    def get_xpb_builder(self, kind: XpbKind, buffer: bytes = None) -> iXpbBuilder:
        "Returns XpbBuilder interface."
        if buffer is None:
            result = self.vtable.getXpbBuilder(self, self.status, kind, None, 0)
        else:
            result = self.vtable.getXpbBuilder(self, self.status, kind, buffer, len(buffer))
        self._check()
        return iXpbBuilder(result)
    def set_offsets(self, metadata: iMessageMetadata, callback: iOffsetsCallbackImp) -> int:
        "Sets valid offsets in MessageMetadata. Performs calls to callback in OffsetsCallback for each field/parameter."
        result = self.vtable.setOffsets(self, self.status, metadata, callback)
        self._check()
        return result

# IMaster(2) : Versioned
class iMaster(iVersioned):
    "Class that wraps IMaster interface for use from Python"
    VERSION = 2
    def get_status(self) -> iStatus:
        "Get instance if `iStatus` interface."
        return iStatus(self.vtable.getStatus(self))
    def get_dispatcher(self) -> iProvider:
        "Get instance of `iProvider` interface, implemented by yValve (main provider instance)."
        return iProvider(self.vtable.getDispatcher(self))
    def get_plugin_manager(self) -> iPluginManager:
        "Get instance of `iPluginManager` interface."
        return iPluginManager(self.vtable.getPluginManager(self))
    def get_timer_control(self) -> iTimerControl:
        "Get instance of `iTimerControl` interface."
        return iTimerControl(self.vtable.getTimerControl(self))
    def get_dtc(self) -> iDtc:
        "Get instance of `iDtc` interface."
        return iDtc(self.vtable.getDtc(self))
    def register_attachment(self, provider: iProvider, attachment: iAttachment) -> iAttachment:
        "Information not available"
        return iAttachment(self.vtable.registerAttachment(self, provider, attachment))
    def register_transaction(self, attachment: iAttachment, transaction: iTransaction) -> iTransaction:
        "Information not available"
        return iTransaction(self.vtable.registerTransaction(self, attachment, transaction))
    def get_metadata_builder(self, fieldCount: int) -> iMetadataBuilder:
        "Get instance of `iMetadataBuilder` interface."
        if self.status is None:
            self.status = self.get_status()
        result = self.vtable.getMetadataBuilder(self, self.status, fieldCount)
        self._check()
        return iMetadataBuilder(result)
    def server_mode(self, mode: int) -> int:
        "Information not available"
        return self.vtable.serverMode(self, mode).value
    def get_util_interface(self) -> iUtil:
        "Get instance of `iUtil` interface."
        return iUtil(self.vtable.getUtilInterface(self))
    def get_config_manager(self) -> iConfigManager:
        "Get instance of `iConfigManager` interface."
        return iConfigManager(self.vtable.getConfigManager(self))
    def get_process_exiting(self) -> bool:
        "Information not available"
        return self.vtable.getProcessExiting(self).value

# ------------------------------------------------------------------------------
# Interface implementations
# ------------------------------------------------------------------------------

class iVersionedImpl:
    "Base class for objects that implement IVersioned interface"
    VERSION = 1
    def __init__(self):
        vt, vt_p, intf_s, intf = self._get_intf()
        self.__vtable = vt()
        self.__intf = intf_s(vtable=vt_p(self.__vtable))
        self._as_parameter_ = intf(self.__intf)
        self.vtable.version = c_ulong(self.VERSION)
    def _get_intf(self):
        return (a.IVersioned_VTable,
                a.IVersioned_VTablePtr,
                a.IVersioned_struct,
                a.IVersioned)
    vtable = property(lambda self: self._as_parameter_.contents.vtable.contents)

class iReferenceCountedImpl(iVersionedImpl):
    "IReferenceCounted interface wrapper"
    VERSION = 2

    def __init__(self):
        super().__init__()
        self.vtable.addRef = a.IReferenceCounted_addRef(self.add_ref)
        self.vtable.release = a.IReferenceCounted_release(self.release)
    def _get_intf(self):
        return (a.IReferenceCounted_VTable,
                a.IReferenceCounted_VTablePtr,
                a.IReferenceCounted_struct,
                a.IReferenceCounted)
    def add_ref(self) -> None:
        "Increase the reference by one"
    def release(self) -> int:
        "Decrease the reference by one"

class iDisposableImpl(iVersionedImpl):
    "IDisposable interface wrapper"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.dispose = a.IDisposable_dispose(self.dispose)
    def _get_intf(self):
        return (a.IDisposable_VTable,
                a.IDisposable_VTablePtr,
                a.IDisposable_struct,
                a.IDisposable)
    def dispose(self) -> None:
        "Dispose the interfaced object"

class iVersionCallbackImpl(iVersionedImpl):
    "Class that wraps IVersionCallback interface for use from Python"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.callback = a.IVersionCallback_callback(self.__callback)
    def _get_intf(self):
        return (a.IVersionCallback_VTable,
                a.IVersionCallback_VTablePtr,
                a.IVersionCallback_struct,
                a.IVersionCallback)
    def __callback(self, this: a.IVersionCallback, status: a.IStatus, text: c_char_p):
        try:
            self.callback(text.decode())
        except Exception:
            pass
    def callback(self, text: str) -> None:
        "Method called by engine"

class iCryptKeyCallbackImpl(iVersionedImpl):
    "Class that wraps ICryptKeyCallback interface for use from Python"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.callback = a.ICryptKeyCallback_callback(self.__callback)
    def _get_intf(self):
        return (a.ICryptKeyCallback_VTable,
                a.ICryptKeyCallback_VTablePtr,
                a.ICryptKeyCallback_struct,
                a.ICryptKeyCallback)
    def __callback(self, this: a.ICryptKeyCallback, data_length: a.Cardinal, data: c_void_p,
                   buffer_length: a.Cardinal, buffer: c_void_p) -> a.Cardinal:
        try:
            key = self.get_crypt_key(data[:data_length], buffer_length)
            key_size = min(len(key), buffer_length)
            memmove(buffer, key, key_size)
            return key_size
        except Exception:
            pass
    def get_crypt_key(self, data: bytes, max_key_size: int) -> bytes:
        "Should return crypt key"
        return b''

class iOffsetsCallbackImp(iVersionedImpl):
    "Class that wraps IOffsetsCallback interface for use from Python"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.callback = a.IVersionCallback_callback(self.__callback)
    def _get_intf(self):
        return (a.IOffsetsCallback_VTable,
                a.IOffsetsCallback_VTablePtr,
                a.IOffsetsCallback_struct,
                a.IOffsetsCallback)
    def __callback(self, this: a.IOffsetsCallback, status: a.IStatus, index: a.Cardinal,
                   offset: a.Cardinal, nullOffset: a.Cardinal) -> None:
        try:
            self.set_offset(index, offset, nullOffset)
        except Exception:
            pass
    def set_offset(self, index: int, offset: int, nullOffset: int) -> None:
        "Method called by engine"

class iEventCallbackImpl(iReferenceCountedImpl):
    "IEventCallback interface wrapper"
    VERSION = 3
    def __init__(self):
        super().__init__()
        self.vtable.eventCallbackFunction = a.IEventCallback_eventCallbackFunction(self.__callback)
    def _get_intf(self):
        return (a.IEventCallback_VTable,
                a.IEventCallback_VTablePtr,
                a.IEventCallback_struct,
                a.IEventCallback)
    def __callback(self, this: a.IVersionCallback, length: a.Cardinal, events: a.BytePtr) -> None:
        try:
            self.events_arrived(string_at(events, length))
        except Exception:
            pass
    def events_arrived(self, events: bytes) -> None:
        "Method called by engine"

class iTimerImpl(iReferenceCountedImpl):
    "Class that wraps ITimer interface for use from Python"
    VERSION = 3
    def __init__(self):
        super().__init__()
        self.vtable.handler = a.ITimer_handler(self.__callback)
    def _get_intf(self):
        return (a.ITimer_VTable, a.ITimer_VTablePtr, a.ITimer_struct, a.ITimer)
    def __callback(self, this: a.ITimer) -> None:
        try:
            self.handler()
        except Exception:
            pass
    def handler(self) -> None:
        "Timer callback handler"

# API_LOADED hook

def __augment_api(api: a.FirebirdAPI) -> None:
    def wrap(result, func=None, arguments=None) -> iMaster:
        return iMaster(result)

    api.fb_get_master_interface.errcheck = wrap
    setattr(sys.modules[__name__], '_master', api.fb_get_master_interface())
    setattr(sys.modules[__name__], '_util', _master.get_util_interface())
    api.master: iMaster = _master
    api.util: iUtil = _util

HookManager().add_hook(APIHook.LOADED, a.FirebirdAPI, __augment_api)
