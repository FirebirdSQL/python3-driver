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
from typing import Tuple, List, Callable, Protocol, Union
import time
import datetime
import decimal
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum, IntEnum, IntFlag
from dateutil import tz
from firebird.base.types import Error

# Exceptions required by Python Database API 2.0

class InterfaceError(Error):
    """Exception raised for errors that are reported by the driver rather than
    the Firebird itself.
    """

class DatabaseError(Error):
    """Exception raised for all errors reported by Firebird.
    """

    #: Returned SQLSTATE or None
    sqlstate: str = None
    #: Returned SQLCODE or None
    sqlcode: int = None
    #: Tuple with all returned GDS error codes
    gds_codes: Tuple[int] = ()

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
    supported by the database.
    """

# Firebird engine warning via Python Warning mechanism

class FirebirdWarning(UserWarning):
    """Warning from Firebird engine.

    The important difference from `Warning` class is that `FirebirdWarning` accepts keyword
    arguments, that are stored into instance attributes with the same name.

    Important:
        Attribute lookup on this class never fails, as all attributes that are not actually
        set, have `None` value.

    Example::

        try:
            if condition:
                raise FirebirdWarning("Error message", err_code=1)
            else:
                raise FirebirdWarning("Unknown error")
        except FirebirdWarning as e:
            if e.err_code is None:
                ...
            elif e.err_code == 1:
                ...

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        for name, value in kwargs.items():
            setattr(self, name, value)
    def __getattr__(self, name):
        return None

# Enums

class NetProtocol(IntEnum):
    """Network protocol options available for connection.
    """
    XNET = 1
    INET = 2
    INET4 = 3
    WNET = 4

class DirectoryCode(IntEnum):
    """IConfigManager directory codes.
    """
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
    DIR_TZDATA = 17 # >>> Firebird 4

class XpbKind(IntEnum):
    """Xpb builder kinds.
    """
    DPB = 1
    SPB_ATTACH = 2
    SPB_START = 3
    TPB = 4
    # Firebird 4 amd 3.5.6+
    BATCH = 5
    BPB = 6
    SPB_SEND = 7
    SPB_RECEIVE = 8
    SPB_RESPONSE = 9


class StateResult(IntEnum):
    """IState result codes.
    """
    ERROR = -1
    OK = 0
    NO_DATA = 1
    SEGMENT = 2

class PageSize(IntEnum):
    """Supported database page sizes.
    """
    PAGE_4K = 4096
    PAGE_8K = 8192
    PAGE_16K = 16384
    PAGE_32K = 32768  # Firebird 4

class DBKeyScope(IntEnum):
    """Scope of DBKey context.
    """
    TRANSACTION = 0
    ATTACHMENT = 1

class InfoItemType(IntEnum):
    """Data type of information item.
    """
    BYTE = 1
    INTEGER = 2
    BIGINT = 3
    BYTES = 4
    RAW_BYTES = 5
    STRING = 6

class SrvInfoCode(IntEnum):
    """Service information (isc_info_svc_*) codes.
    """
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
    """BLOB information (isc_info_blob_*) codes.
    """
    NUM_SEGMENTS = 4
    MAX_SEGMENT = 5
    TOTAL_LENGTH = 6
    TYPE = 7

class DbInfoCode(IntEnum):
    """Database information (isc_info_*) codes.
    """
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
    CRYPT_KEY = 133
    CRYPT_STATE = 134
    # Firebird 4
    STMT_TIMEOUT_DB = 135
    STMT_TIMEOUT_ATT = 136
    PROTOCOL_VERSION = 137
    CRYPT_PLUGIN = 138
    CREATION_TIMESTAMP_TZ = 139
    WIRE_CRYPT = 140
    FEATURES = 141
    NEXT_ATTACHMENT = 142
    NEXT_STATEMENT = 143
    DB_GUID = 144
    DB_FILE_ID = 145
    REPLICA_MODE = 146

class Features(IntEnum):
    """Firebird features (Response to DbInfoCode.FEATURES).
    """
    MULTI_STATEMENTS = 1    # Multiple prepared statements in single attachment
    MULTI_TRANSACTIONS = 2  # Multiple concurrent transaction in single attachment
    NAMED_PARAMETERS = 3    # Query parameters can be named
    SESSION_RESET = 4       # ALTER SESSION RESET is supported
    READ_CONSISTENCY = 5    # Read consistency TIL is supported
    STATEMENT_TIMEOUT = 6   # Statement timeout is supported
    STATEMENT_LONG_LIFE = 7 # Prepared statements are not dropped on transaction end

class ReplicaMode(IntEnum):
    """Replica modes. Response to DbInfoCode.REPLICA_MODE or as value for
    DPBItem.SET_DB_REPLICA.
    """
    NONE = 0
    READ_ONLY = 1
    READ_WRITE = 2

class StmtInfoCode(IntEnum):
    """Statement information (isc_info_sql_*) codes.
    """
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
    """Transaction information (isc_info_tra_*) codes.
    """
    ID = 4
    OLDEST_INTERESTING = 5
    OLDEST_SNAPSHOT = 6
    OLDEST_ACTIVE = 7
    ISOLATION = 8
    ACCESS = 9
    LOCK_TIMEOUT = 10
    DBPATH = 11
    SNAPSHOT_NUMBER = 12

class TraInfoIsolation(IntEnum):
    """Transaction isolation response.
    """
    CONSISTENCY = 1
    CONCURRENCY = 2
    READ_COMMITTED = 3

class TraInfoReadCommitted(IntEnum):
    """Transaction isolation Read Committed response.
    """
    NO_RECORD_VERSION = 0
    RECORD_VERSION = 1
    READ_CONSISTENCY = 2  # Firebird 4

class TraInfoAccess(IntEnum):
    """Transaction isolation access mode response.
    """
    READ_ONLY = 0
    READ_WRITE = 1

class TraAccessMode(IntEnum):
    """Transaction Access Mode TPB parameters.
    """
    READ = 8
    WRITE = 9

class TraIsolation(IntEnum):
    """Transaction Isolation TPB paremeters.
    """
    CONSISTENCY = 1
    CONCURRENCY = 2
    READ_COMMITTED = 15

class TraReadCommitted(IntEnum):
    """Read Committed Isolation TPB paremeters.
    """
    RECORD_VERSION = 17
    NO_RECORD_VERSION = 18

class Isolation(IntEnum):
    """Transaction Isolation TPB parameters.
    """
    READ_COMMITTED = -1
    SERIALIZABLE = 1
    SNAPSHOT = 2
    READ_COMMITTED_NO_RECORD_VERSION = 3
    READ_COMMITTED_RECORD_VERSION = 4
    READ_COMMITTED_READ_CONSISTENCY = 5 # Firebird 4
    # Aliases
    REPEATABLE_READ = SNAPSHOT
    CONCURRENCY = SNAPSHOT
    CONSISTENCY = SERIALIZABLE

class TraLockResolution(IntEnum):
    """Transaction Lock resolution TPB parameters.
    """
    WAIT = 6
    NO_WAIT = 7

class TableShareMode(IntEnum):
    """Transaction table share mode TPB parameters.
    """
    SHARED = 3
    PROTECTED = 4
    EXCLUSIVE = 5

class TableAccessMode(IntEnum):
    """Transaction Access Mode TPB parameters.
    """
    LOCK_READ = 10
    LOCK_WRITE = 11

class DefaultAction(IntEnum):
    """Default action when transaction is ended automatically.
    """
    COMMIT = 1
    ROLLBACK = 2

class StatementType(IntEnum):
    """Statement type.
    """
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
    """SQL data type.
    """
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
    TIMESTAMP_TZ_EX = 32748  # Firebird 4
    TIME_TZ_EX = 32750  # Firebird 4
    INT128 = 32752 # Firebird 4
    TIMESTAMP_TZ = 32754  # Firebird 4
    TIME_TZ = 32756  # Firebird 4
    DEC16 = 32760  # Firebird 4
    DEC34 = 32762  # Firebird 4
    BOOLEAN = 32764
    NULL = 32766

class DPBItem(IntEnum):
    """isc_dpb_* items (VERSION2).
    """
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
    SET_BIND = 93
    DECFLOAT_ROUND = 94
    DECFLOAT_TRAPS = 95

class TPBItem(IntEnum):
    """isc_tpb_* items.
    """
    VERSION3 = 3
    IGNORE_LIMBO = 14
    AUTOCOMMIT = 16
    NO_AUTO_UNDO = 20
    LOCK_TIMEOUT = 21
    # Firebird 4
    READ_CONSISTENCY = 22
    AT_SNAPSHOT_NUMBER = 23

class SPBItem(IntEnum):
    """isc_spb_* items.
    """
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
    EXPECTED_DB = 124

class BPBItem(IntEnum):
    """isc_bpb_* items.
    """
    SOURCE_TYPE = 1
    TARGET_TYPE = 2
    TYPE = 3
    SOURCE_INTERP = 4
    TARGET_INTERP = 5
    FILTER_PARAMETER = 6
    STORAGE = 7

class BlobType(IntEnum):
    """Blob type.
    """
    SEGMENTED = 0x0
    STREAM = 0x1

class BlobStorage(IntEnum):
    """Blob storage.
    """
    MAIN = 0x0
    TEMP = 0x2

class ServerAction(IntEnum):
    """isc_action_svc_* items.
    """
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
    NFIX = 31 # Firebird 4

class SrvDbInfoOption(IntEnum):
    """Parameters for SvcInfoCode.SRV_DB_INFO.
    """
    ATT = 5
    DB = 6

class SrvRepairOption(IntEnum):
    """Parameters for ServerAction.REPAIR.
    """
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

class SrvBackupOption(IntEnum):
    """Parameters for ServerAction.BACKUP.
    """
    FILE = 5
    FACTOR = 6
    LENGTH = 7
    SKIP_DATA = 8
    STAT = 15
    # Firebird 4
    KEYHOLDER = 16
    KEYNAME = 17
    CRYPT = 18
    INCLUDE_DATA = 19

class SrvRestoreOption(IntEnum):
    """Parameters for ServerAction.RESTORE.
    """
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
    INCLUDE_DATA = 19
    REPLICA_MODE = 20

class SrvNBackupOption(IntEnum):
    """Parameters for ServerAction.NBAK.
    """
    LEVEL = 5
    FILE = 6
    DIRECT = 7
    # Firebird 4
    GUID = 8

class SrvTraceOption(IntEnum):
    """Parameters for ServerAction.TRACE_*.
    """
    ID = 1
    NAME = 2
    CONFIG = 3

class SrvPropertiesOption(IntEnum):
    """Parameters for ServerAction.PROPERTIES.
    """
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
    REPLICA_MODE = 46 # Firebird 4

class SrvValidateOption(IntEnum):
    """Parameters for ServerAction.VALIDATE.
    """
    INCLUDE_TABLE = 1
    EXCLUDE_TABLE = 2
    INCLUDE_INDEX = 3
    EXCLUDE_INDEX = 4
    LOCK_TIMEOUT = 5

class SrvUserOption(IntEnum):
    """Parameters for ServerAction.ADD_USER|DELETE_USER|MODIFY_USER|DISPLAY_USER.
    """
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
    """Values for isc_spb_prp_access_mode.
    """
    READ_ONLY = 39
    READ_WRITE = 40

class DbSpaceReservation(IntEnum):
    """Values for isc_spb_prp_reserve_space.
    """
    USE_FULL = 35
    RESERVE = 36

class DbWriteMode(IntEnum):
    """Values for isc_spb_prp_write_mode.
    """
    ASYNC = 37
    SYNC = 38

class ShutdownMode(IntEnum):
    """Values for isc_spb_prp_shutdown_mode.
    """
    NORMAL = 0
    MULTI = 1
    SINGLE = 2
    FULL = 3

class OnlineMode(IntEnum):
    """Values for isc_spb_prp_online_mode.
    """
    NORMAL = 0
    MULTI = 1
    SINGLE = 2

class ShutdownMethod(IntEnum):
    """Database shutdown method options.
    """
    FORCED = 41
    DENY_ATTACHMENTS = 42
    DENY_TRANSACTIONS = 43

class TransactionState(IntEnum):
    """Transaction state.
    """
    UNKNOWN = 0
    COMMIT = 1
    ROLLBACK = 2
    LIMBO = 3

class DbProvider(IntEnum):
    """Database Providers.
    """
    RDB_ELN = 1
    RDB_VMS = 2
    INTERBASE = 3
    FIREBIRD = 4

class DbClass(IntEnum):
    """Database Classes.
    """
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
    """Implementation - Legacy format.
    """
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
    """Implementation - CPU.
    """
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
    """Implementation - CPU.
    """
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
    """Implementation - Compiler.
    """
    MSVC = 0
    GCC = 1
    XLC = 2
    ACC = 3
    SUN_STUDIO = 4
    ICC = 5

class CancelType(IntEnum):
    """Cancel types for `Connection.cancel_operation()`
    """
    DISABLE = 1
    ENABLE = 2
    RAISE = 3
    ABORT = 4

class DecfloatRound(Enum):
    """DECFLOAT ROUND options.
    """
    CEILING = 'CEILING'
    UP = 'UP'
    HALF_UP = 'HALF_UP'
    HALF_EVEN = 'HALF_EVEN'
    HALF_DOWN = 'HALF_DOWN'
    DOWN = 'DOWN'
    FLOOR = 'FLOOR'
    REROUND = 'REROUND'

class DecfloatTraps(Enum):
    """DECFLOAT TRAPS options.
    """
    DIVISION_BY_ZERO = 'Division_by_zero'
    INEXACT = 'Inexact'
    INVALID_OPERATION = 'Invalid_operation'
    OVERFLOW = 'Overflow'
    UNDERFLOW = 'Underflow'

# Flags

class StateFlag(IntFlag):
    """IState flags.
    """
    NONE = 0
    WARNINGS = 1
    ERRORS = 2

class PreparePrefetchFlag(IntFlag):
    """Flags for Statement Prefetch.
    """
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
    """Statement flags.
    """
    NONE = 0
    HAS_CURSOR = 1
    REPEAT_EXECUTE = 2

class CursorFlag(IntFlag):
    """Cursor flags.
    """
    NONE = 0
    SCROLLABLE = 1

class ConnectionFlag(IntFlag):
    """Flags returned for DbInfoCode.CONN_FLAGS.
    """
    NONE = 0
    COMPRESSED = 0x01
    ENCRYPTED = 0x02

class EncryptionFlag(IntFlag):
    """Crypto status (Response to DbInfoCode.CRYPT_STATE).
    """
    ENCRYPTED = 0x01
    PROCESS = 0x02

class ServerCapability(IntFlag):
    """Server capabilities (returned by isc_info_svc_capabilities).
    """
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

class SrvRepairFlag(IntFlag):
    """isc_spb_rpr_* flags for ServerAction.REPAIR.
    """
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

class SrvStatFlag(IntFlag):
    """isc_spb_sts_* flags for ServerAction.DB_STATS.
    """
    NONE = 0
    DATA_PAGES = 0x01
    DB_LOG = 0x02
    HDR_PAGES = 0x04
    IDX_PAGES = 0x08
    SYS_RELATIONS = 0x10
    RECORD_VERSIONS = 0x20
    NOCREATION = 0x80
    ENCRYPTION = 0x100
    DEFAULT = DATA_PAGES | IDX_PAGES

class SrvBackupFlag(IntFlag):
    """isc_spb_bkp_* flags for ServerAction.BACKUP.
    """
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
    ZIP = 0x010000 # Firebird 4

class SrvRestoreFlag(IntFlag):
    """isc_spb_res_* flags for ServerAction.RESTORE.
    """
    METADATA_ONLY = 0x04
    DEACTIVATE_IDX = 0x0100
    NO_SHADOW = 0x0200
    NO_VALIDITY = 0x0400
    ONE_AT_A_TIME = 0x0800
    REPLACE = 0x1000
    CREATE = 0x2000
    USE_ALL_SPACE = 0x4000
    NO_TRIGGERS = 0x8000

class SrvNBackupFlag(IntFlag):
    """isc_spb_nbk_* flags for ServerAction.NBAK.
    """
    NONE = 0
    NO_TRIGGERS = 0x01
    # Firebird 4
    IN_PLACE = 0x02
    SEQUENCE = 0x04

class SrvPropertiesFlag(IntFlag):
    """isc_spb_prp_* flags for ServerAction.PROPERTIES.
    """
    ACTIVATE = 0x0100
    DB_ONLINE = 0x0200
    NOLINGER = 0x0400

class ImpFlags(IntFlag):
    """Implementation - Endianness.
    """
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
    """Information about Firebird user.

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

@dataclass
class BCD:
    """BCD number.

    Attributes:
        sign (int): Sign
        number (bytes): Number
        exp (int): Exponent
    """
    sign: int
    number: bytes
    exp: int

@dataclass
class TraceSession:
    """Information about active trace session.

    Attributes:
        id (int): Session ID number
        user (str): User name
        timestamp (datetime.datetime): Session start timestamp
        name (str): Session name (if defined)
        flags (list): List with session flag names
    """
    id: int
    user: str
    timestamp: datetime.datetime
    name: str = ''
    flags: List = field(default_factory=list)

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

def DateFromTicks(ticks: float) -> Date: # pragma: no cover
    """Constructs an object holding a date value from the given ticks value
    (number of seconds since the epoch).
    """
    return Date(time.localtime(ticks)[:3])

def TimeFromTicks(ticks: float) -> Time: # pragma: no cover
    """Constructs an object holding a time value from the given ticks value
    (number of seconds since the epoch).
    """
    return Time(time.localtime(ticks)[3:6])

def TimestampFromTicks(ticks: float) -> Timestamp: # pragma: no cover
    """Constructs an object holding a time stamp value from the given ticks value
    (number of seconds since the epoch).
    """
    return Timestamp(time.localtime(ticks)[:6])

#: This callable constructs an object capable of holding a binary (long) string value.
Binary = memoryview

class DBAPITypeObject:
    """Python DB API 2.0 - type support.
    """
    def __init__(self, *values):
        self.values = values
    def __cmp__(self, other): # pragma: no cover
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
#: File name (incl. path) specification
FILESPEC = Union[str, Path]

class Transactional(Protocol):  # pragma: no cover
    """Protocol type for object that supports transactional processing."""
    def begin(self, tpb: bytes = None) -> None:
        """Begin transaction.
        """
    def commit(self, *, retaining: bool = False) -> None:
        """Commit transaction.
        """
    def rollback(self, *, retaining: bool = False, savepoint: str = None) -> None:
        """Rollback transaction.
        """
    def is_active(self) -> bool:
        """Returns True if transaction is active.
        """

# timezone

def get_timezone(timezone: str=None) -> datetime.tzinfo:
    """Returns `datetime.tzinfo` for specified time zone.

    This is preferred method to obtain timezone information for construction of timezone-aware
    `datetime.datetime` and `datetime.time` objects. Current implementation uses `dateutil.tz`
    for timezone tzinfo objects, but adds metadata neccessary to store timezone regions into
    database instead zoned time, and to handle offset-based timezones in format required by
    Firebird.
    """
    if timezone[0] in ('+', '-'):
        timezone = 'UTC' + timezone
    result = tz.gettz(timezone)
    if result is not None and not hasattr(result, '_timezone_'):
        setattr(result, '_timezone_', timezone[3:] if timezone.startswith('UTC') and len(timezone) > 3 else timezone)
    return result
