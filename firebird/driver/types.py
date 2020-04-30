#coding:utf-8
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

import typing as t
import sys
import threading
import time
import ctypes as c
import datetime
import decimal
import struct
import enum
from dataclasses import dataclass
from . import fbapi as a
from .hooks import hooks, HookType

# Exceptions required by Python Database API 2.0

class Warning(Exception):
    """Exception raised for important warnings like data truncations while
inserting, etc.

Uses `kwargs` to set attributes on exception instance."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        #self.sqlstate: str = None
        #self.gds_codes: str = tuple()
        for name, value in kwargs.items():
            setattr(self, name, value)

class Error(Exception):
    """Exception that is the base class of all other error
exceptions. You can use this to catch all errors with one
single 'except' statement. Warnings are not considered
errors and thus should not use this class as base.

Uses `kwargs` to set attributes on exception instance."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        #self.sqlstate: str = None
        #self.gds_codes: str = tuple()
        for name, value in kwargs.items():
            setattr(self, name, value)

class InterfaceError(Error):
    """Exception raised for errors that are related to the database interface
rather than the database itself."""

class DatabaseError(Error):
    "Exception raised for errors that are related to the database."
    gds_codes: t.List[int] = []
    sqlstate: str = None
    sqlcode: int = None

class DataError(DatabaseError):
    """Exception raised for errors that are due to problems with the processed
data like division by zero, numeric value out of range, etc."""

class OperationalError(DatabaseError):
    """Exception raised for errors that are related to the database's operation
and not necessarily under the control of the programmer, e.g. an unexpected
disconnect occurs, the data source name is not found, a transaction could not
be processed, a memory allocation error occurred during processing, etc."""

class IntegrityError(DatabaseError):
    """Exception raised when the relational integrity of the database is affected,
e.g. a foreign key check fails."""

class InternalError(DatabaseError):
    """Exception raised when the database encounters an internal error, e.g. the
cursor is not valid anymore, the transaction is out of sync, etc."""

class ProgrammingError(DatabaseError):
    """Exception raised for programming errors, e.g. table not found or already
exists, syntax error in the SQL statement, wrong number of parameters specified,
etc."""

class NotSupportedError(DatabaseError):
    """Exception raised in case a method or database API was used which is not
supported by the database"""

# Enums

class Enum(enum.IntEnum):
    """Extended enumeration type."""
    @classmethod
    def get_member_map(cls) -> t.Dict[str, 'Enum']:
        """Returns dictionary that maps Enum member names to Enum values (instances)."""
        return cls._member_map_
    @classmethod
    def get_value_map(cls) -> t.Dict[int, 'Enum']:
        """Returns dictionary that maps int values to Enum values (instances)."""
        return cls._value2member_map_
    @classmethod
    def auto(cls) -> int:
        """Returns int for new Enum value."""
        return enum.auto()
    def __repr__(self):
        return f"{self.__class__.__name__}.{self._name_}"

class NetProtocol(Enum):
    "Network protocol options available for connection"
    XNET = 1
    INET = 2
    INET4 = 3
    WNET = 4

class DirectoryCode(Enum):
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

class XpbKind(Enum):
    "Xpb builder kinds"
    DPB = 1
    SPB_ATTACH = 2
    SPB_START = 3
    TPB = 4

class StateResult(Enum):
    "IState result codes"
    ERROR = -1
    OK = 0
    NO_DATA = 1
    SEGMENT = 2

class DBKeyScope(Enum):
    "Scope of DBKey context"
    TRANSACTION = 0
    ATTACHMENT = 1

class InfoItemType(Enum):
    "Data type of information item"
    INTEGER = 1
    BIGINT = 2
    BYTES = 3
    STRING = 4

class SvcInfoCode(Enum):
    "Service information (isc_info_svc_*) codes"
    SRV_DB_INFO = 50    # Retrieves the number of attachments and databases */
    GET_CONFIG = 53     # Retrieves the parameters and values for IB_CONFIG */
    VERSION = 54        # Retrieves the version of the services manager */
    SERVER_VERSION = 55 # Retrieves the version of the Firebird server */
    IMPLEMENTATION = 56 # Retrieves the implementation of the Firebird server */
    CAPABILITIES = 57   # Retrieves a bitmask representing the server's capabilities */
    USER_DBPATH = 58    # Retrieves the path to the security database in use by the server */
    GET_ENV = 59        # Retrieves the setting of $FIREBIRD */
    GET_ENV_LOCK = 60   # Retrieves the setting of $FIREBIRD_LCK */
    GET_ENV_MSG = 61    # Retrieves the setting of $FIREBIRD_MSG */
    LINE = 62           # Retrieves 1 line of service output per call */
    TO_EOF = 63         # Retrieves as much of the server output as will fit in the supplied buffer */
    TIMEOUT = 64        # Sets / signifies a timeout value for reading service information */
    LIMBO_TRANS = 66    # Retrieve the limbo transactions */
    RUNNING = 67        # Checks to see if a service is running on an attachment */
    GET_USERS = 68      # Returns the user information from isc_action_svc_display_users */
    AUTH_BLOCK = 69     # FB 3.0: Sets authentication block for service query() call */
    STDIN = 78          # Returns maximum size of data, needed as stdin for service */

class BlobInfoCode(Enum):
    "BLOB information (isc_info_blob_*) codes"
    NUM_SEGMENTS = 4
    MAX_SEGMENT = 5
    TOTAL_LENGTH = 6
    TYPE = 7

class DbInfoCode(Enum):
    "Database information (isc_info_*) codes"
    DB_ID = 4  # [db_filename,site_name[,site_name...]]
    READS = 5  # number of page reads
    WRITES = 6  # number of page writes
    FETCHES = 7  # number of reads from the memory buffer cache
    MARKS = 8  # number of writes to the memory buffer cache
    IMPLEMENTATION_OLD = 11  # (implementation code, implementation class)
    VERSION = 12  # interbase server version identification string
    BASE_LEVEL = 13  # capability version of the server
    PAGE_SIZE = 14
    NUM_BUFFERS = 15  # number of memory buffers currently allocated
    LIMBO = 16
    CURRENT_MEMORY = 17  # amount of server memory (in bytes) currently in use
    MAX_MEMORY = 18  # maximum amount of memory (in bytes) used at one time since the first process attached to the database
    # Obsolete 19-20
    ALLOCATION = 21  # number of last database page allocated
    ATTACHMENT_ID = 22  # attachment id number
    # all *_count codes below return {[table_id]=operation_count,...}; table IDs are in the system table RDB$RELATIONS.
    READ_SEQ_COUNT = 23  # number of sequential table scans (row reads) done on each table since the database was last attached
    READ_IDX_COUNT = 24  # number of reads done via an index since the database was last attached
    INSERT_COUNT = 25  # number of inserts into the database since the database was last attached
    UPDATE_COUNT = 26  # number of database updates since the database was last attached
    DELETE_COUNT = 27  # number of database deletes since the database was last attached
    BACKOUT_COUNT = 28  # number of removals of a version of a record
    PURGE_COUNT = 29  # number of removals of old versions of fully mature records (records that are committed, so that older ancestor versions are no longer needed)
    EXPUNGE_COUNT = 30  # number of removals of a record and all of its ancestors, for records whose deletions have been committed
    SWEEP_INTERVAL = 31  # number of transactions that are committed between sweeps to remove database record versions that are no longer needed
    ODS_VERSION = 32  # On-disk structure (ODS) minor major version number
    ODS_MINOR_VERSION = 33  # On-disk structure (ODS) minor version number
    NO_RESERVE = 34  # 20% page space reservation for holding backup versions of modified records: 0=yes, 1=no
    # Obsolete 35-51
    FORCED_WRITES = 52  # mode in which database writes are performed: 0=sync, 1=async
    USER_NAMES = 53  # array of names of all the users currently attached to the database
    PAGE_ERRORS = 54  # number of page level errors validate found
    RECORD_ERRORS = 55  # number of record level errors validate found
    BPAGE_ERRORS = 56  # number of blob page errors validate found
    DPAGE_ERRORS = 57  # number of data page errors validate found
    IPAGE_ERRORS = 58  # number of index page errors validate found
    PPAGE_ERRORS = 59  # number of pointer page errors validate found
    TPAGE_ERRORS = 60  # number of transaction page errors validate found
    SET_PAGE_BUFFERS = 61  # number of memory buffers that should be allocated
    DB_SQL_DIALECT = 62  # dialect of currently attached database
    DB_READ_ONLY = 63  # whether the database is read-only (1) or not (0)
    DB_SIZE_IN_PAGES = 64  # number of allocated pages
    # Values 65 -100 unused to avoid conflict with InterBase
    ATT_CHARSET = 101  # charset of current attachment
    DB_CLASS = 102  # server architecture
    FIREBIRD_VERSION = 103  # firebird server version identification string
    OLDEST_TRANSACTION = 104  # ID of oldest transaction
    OLDEST_ACTIVE = 105  # ID of oldest active transaction
    OLDEST_SNAPSHOT = 106  # ID of oldest snapshot transaction
    NEXT_TRANSACTION = 107  # ID of next transaction
    DB_PROVIDER = 108  # for firebird is 'db_code_firebird'
    ACTIVE_TRANSACTIONS = 109  # array of active transaction IDs
    ACTIVE_TRAN_COUNT = 110  # number of active transactions
    CREATION_DATE = 111  # time_t struct representing database creation date & time
    DB_FILE_SIZE = 112 # added in FB 2.1, nbackup-related - size (in pages) of locked db
    PAGE_CONTENTS = 113 # added in FB 2.5, get raw page contents; takes page_number as parameter;
    # Added in Firebird 3.0
    IMPLEMENTATION = 114  # (cpu code, OS code, compiler code, flags, implementation class)
    PAGE_WARNS = 115  # number of page level warnings validate found
    RECORD_WARNS = 116  # number of record level warnings validate found
    BPAGE_WARNS = 117  # number of blob page level warnings validate found
    DPAGE_WARNS = 118  # number of data page level warnings validate found
    IPAGE_WARNS = 119  # number of index page level warnings validate found
    PPAGE_WARNS = 120  # number of pointer page level warnings validate found
    TPAGE_WARNS = 121  # number of trabsaction page level warnings validate found
    PIP_ERRORS = 122  # number of pip page level errors validate found
    PIP_WARNS = 123  # number of pip page level warnings validate found
    PAGES_USED = 124 # number of used database pages
    PAGES_FREE = 125 # number of free database pages
    CONN_FLAGS = 132 # Connection flags, currently compression & encryption

class TraInfoCode(Enum):
    "Transaction information (isc_info_tra_*) codes"
    ID = 4
    OLDEST_INTERESTING = 5
    OLDEST_SNAPSHOT = 6
    OLDEST_ACTIVE = 7
    ISOLATION = 8
    ACCESS = 9
    LOCK_TIMEOUT = 10
    DBPATH = 11

class TraInfoIsolation(Enum):
    "Transaction isolation response"
    CONSISTENCY = 1
    CONCURRENCY = 2
    READ_COMMITTED = 3

class TraInfoReadCommitted(Enum):
    NO_RECORD_VERSION = 0
    RECORD_VERSION = 1

class TraInfoAccess(Enum):
    READ_ONLY = 0
    READ_WRITE = 1


class Isolation(Enum):
    CONSISTENCY = 1
    CONCURRENCY = 2
    READ_COMMITTED = 15

class ReadCommitted(Enum):
    RECORD_VERSION = 17
    NO_RECORD_VERSION = 18

class LockResolution(Enum):
    WAIT = 6
    NO_WAIT = 7

class AccessMode(Enum):
    READ = 8
    WRITE = 9

class TableShareMode(Enum):
    SHARED = 3
    PROTECTED = 4
    EXCLUSIVE = 5

class TableAccessMode(Enum):
    LOCK_READ = 10
    LOCK_WRITE = 11

class DefaultAction(Enum):
    "Default action when transaction is ended automatically"
    COMMIT = 1
    ROLLBACK = 2

class StatementType(Enum):
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

class SQLDataType(Enum):
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
    BOOLEAN = 32764
    NULL = 32766

class DPBItem(Enum):
    "isc_dpb_* items"
    VERSION2 = 2 # Firebird 3
    PAGE_SIZE = 4 # [create db] int
    NUM_BUFFERS = 5 # !!! int
    DBKEY_SCOPE = 13 # int
    NO_GARBAGE_COLLECT = 16
    SWEEP_INTERVAL = 22 # [create db] int
    FORCE_WRITE = 24 # [create db] int (0=False)
    NO_RESERVE = 27 # [create db] int (0=False)
    USER_NAME = 28
    PASSWORD = 29
    LC_CTYPE = 48 # str
    RESERVED = 53 # !!! str ('YES' for True) Sets the database to single user if su
    OVERWRITE = 54 # [create db] int (0=False) On create, allow overwriting existing file
    CONNECT_TIMEOUT = 57 # int
    DUMMY_PACKET_INTERVAL = 58 # !!! int
    SQL_ROLE_NAME = 60 # str
    SET_PAGE_BUFFERS = 61 # [create db] int
    WORKING_DIRECTORY = 62 # !!! str
    SQL_DIALECT = 63
    SET_DB_READONLY = 64 # [create db] int (0=False)
    SET_DB_SQL_DIALECT = 65 # [create db] int
    SET_DB_CHARSET = 68 # [create db] str
    ADDRESS_PATH = 70 # ???
    PROCESS_ID = 71
    NO_DB_TRIGGERS = 72 # int (0=False)
    TRUSTED_AUTH = 73 # !!! str
    PROCESS_NAME = 74
    TRUSTED_ROLE = 75
    ORG_FILENAME = 76
    UTF8_FILENAME = 77
    EXT_CALL_DEPTH = 78 # !!! int
    AUTH_BLOCK = 79
    CLIENT_VERSION = 80
    REMOTE_PROTOCOL = 81
    HOST_NAME = 82
    OS_USER = 83
    SPECIFIC_AUTH_DATA = 84
    AUTH_PLUGIN_LIST = 85 # str
    AUTH_PLUGIN_NAME = 86 # str
    CONFIG = 87 # str
    NOLINGER = 88
    RESET_ICU = 89
    MAP_ATTACH = 90

class TPBItem(Enum):
    "isc_tpb_* items"
    VERSION3 = 3
    IGNORE_LIMBO = 14
    AUTOCOMMIT = 16
    NO_AUTO_UNDO = 20
    LOCK_TIMEOUT = 21

class SPBItem(Enum):
    "isc_spb_* items"
    USER_NAME = 28
    PASSWORD = 29
    CONNECT_TIMEOUT = 57 # int
    DUMMY_PACKET_INTERVAL = 58 # !!! int
    SQL_ROLE_NAME = 60 # str
    COMMAND_LINE = 105 # str
    DBNAME = 106 # str
    VERBOSE = 107 # none
    OPTIONS = 108 # int
    TRUSTED_AUTH = 111 # Wide
    TRUSTED_ROLE = 113
    VERBINT = 114 # int ???
    AUTH_BLOCK = 115 # Wide
    AUTH_PLUGIN_NAME = 116 # Wide
    AUTH_PLUGIN_LIST = 117 # Wide
    UTF8_FILENAME = 118
    CONFIG = 123

class BPBItem(Enum):
    "isc_bpb_* items"
    SOURCE_TYPE = 1
    TARGET_TYPE = 2
    TYPE = 3
    SOURCE_INTERP = 4
    TARGET_INTERP = 5
    FILTER_PARAMETER = 6
    STORAGE = 7

class BPBType(Enum):
    SEGMENTED = 0x0
    STREAM = 0x1

class BPBStorage(Enum):
    MAIN = 0x0
    TEMP = 0x2

class ServiceAction(Enum):
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

class SvcDbInfoOption(Enum):
    "Parameters for SvcInfoCode.SRV_DB_INFO"
    ATT = 5
    DB = 6

class SvcRepairOption(Enum):
    "Parameters for ServiceAction.REPAIR"
    COMMIT_TRANS = 15 # int
    ROLLBACK_TRANS = 34 # int
    RECOVER_TWO_PHASE = 17 # int
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
    # Added in Firebird 3.0
    TRA_ID_64 = 46
    SINGLE_TRA_ID_64 = 47 # bigint
    MULTI_TRA_ID_64 = 48 # bigint
    COMMIT_TRANS_64 = 49 # bigint
    ROLLBACK_TRANS_64 = 50 # bigint
    RECOVER_TWO_PHASE_64 = 51 # bigint

class SvcBackupOption(Enum):
    "Parameters for ServiceAction.BACKUP"
    FILE = 5 # str
    FACTOR = 6 # int ???
    LENGTH = 7 # int
    SKIP_DATA = 8 # str
    STAT = 15 # str

class SvcRestoreOption(Enum):
    "Parameters for ServiceAction.RESTORE"
    FILE = 5 # str
    SKIP_DATA = 8 # str
    BUFFERS = 9 #  int
    PAGE_SIZE = 10 # int
    LENGTH = 11 # int
    ACCESS_MODE = 12 # byte
    FIX_FSS_DATA = 13 # str
    FIX_FSS_METADATA = 14 # str
    STAT = 15 # str

class SvcNBackupOption(Enum):
    "Parameters for ServiceAction.NBAK"
    LEVEL = 5 # int
    FILE = 6 # str
    DIRECT = 7 # str

class SvcTraceOption(Enum):
    "Parameters for ServiceAction.TRACE_*"
    ID = 1 # int
    NAME = 2 # str
    CONFIG = 3 # str

class SvcPropertiesOption(Enum):
    "Parameters for ServiceAction.PROPERTIES"
    PAGE_BUFFERS = 5 # int
    SWEEP_INTERVAL = 6 # int
    SHUTDOWN_DB = 7 # int
    DENY_NEW_ATTACHMENTS = 9 # int
    DENY_NEW_TRANSACTIONS = 10 # int
    RESERVE_SPACE = 11 # byte
    WRITE_MODE = 12 # byte
    ACCESS_MODE = 13 # byte
    SET_SQL_DIALECT = 14 # int
    FORCE_SHUTDOWN = 41 # int
    ATTACHMENTS_SHUTDOWN = 42 # int
    TRANSACTIONS_SHUTDOWN = 43 # int
    SHUTDOWN_MODE = 44 # byte
    ONLINE_MODE = 45 # byte

class SvcValidateOption(Enum):
    "Parameters for ServiceAction.VALIDATE"
    INCLUDE_TABLE = 1 # str
    EXCLUDE_TABLE = 2 # str
    INCLUDE_INDEX = 3 # str
    EXCLUDE_INDEX = 4 # str
    LOCK_TIMEOUT = 5 # int

class SvcUserOption(Enum):
    "Parameters for ServiceAction.ADD_USER|DELETE_USER|MODIFY_USER|DISPLAY_USER"
    USER_ID = 5 # int
    GROUP_ID = 6 # int
    USER_NAME = 7 # str
    PASSWORD = 8 # str
    GROUP_NAME = 9 # str
    FIRST_NAME = 10 # str
    MIDDLE_NAME = 11 # str
    LAST_NAME = 12 # str
    ADMIN = 13 # int

class PrpAccessMode(Enum):
    "Values for isc_spb_prp_access_mode"
    READ_ONLY = 39
    READ_WRITE = 40

class PrpSpaceReservation(Enum):
    "Values for isc_spb_prp_reserve_space"
    USE_FULL = 35
    RESERVE = 36

class PrpWriteMode(Enum):
    "Values for isc_spb_prp_write_mode"
    ASYNC = 37
    SYNC = 38

class ShutdownMode(Enum):
    "Values for isc_spb_prp_shutdown_mode"
    MULTI = 1
    SINGLE = 2
    FULL = 3

class OnlineMode(Enum):
    "Values for isc_spb_prp_online_mode"
    NORMAL = 0
    MULTI = 1
    SINGLE = 2

class ShutdownMethod(Enum):
    "Database shutdown method options"
    FORCED = 41
    DENNY_ATTACHMENTS = 42
    DENNY_TRANSACTIONS = 43

# Flags

class Flag(enum.IntFlag):
    """Extended flag type."""
    def get_flags(self) -> t.List['Flag']:
        """Returns list with all flag values defined by this type"""
        return [flag for flag in self._member_map_.values()
                if flag.value != 0 and flag in self]
    def get_flag_names(self) -> t.List[str]:
        """Returns list with names of all flags defined by this type"""
        return [flag.name for flag in self._member_map_.values()
                if flag.value != 0 and flag in self]

class StateFlag(Flag):
    "IState flags"
    NONE = 0
    WARNINGS = 1
    ERRORS = 2

class PreparePrefetchFlag(Flag):
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

class StatementFlag(Flag):
    NONE = 0
    HAS_CURSOR = 1
    REPEAT_EXECUTE = 2

class CursorFlag(Flag):
    NONE = 0
    SCROLLABLE = 1

class ConnectionFlag(Flag):
    "Flags returned for DbInfoCode.CONN_FLAGS"
    NONE = 0
    COMPRESSED = 0x01
    ENCRYPTED = 0x02

class ServerCapability(Flag):
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

class SvcRepairFlag(Flag):
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
    CORRUPTION_CHECK = VALIDATE_DB | CHECK_DB| FULL | IGNORE_CHECKSUM
    REPAIR = MEND_DB| FULL | IGNORE_CHECKSUM

class SvcStatFlag(Flag):
    "isc_spb_sts_* flags for ServiceAction.DB_STATS"
    NONE = 0
    DATA_PAGES = 0x01
    DB_LOG = 0x02
    HDR_PAGES = 0x04
    IDX_PAGES = 0x08
    SYS_RELATIONS = 0x10
    RECORD_VERSIONS = 0x20
    #TABLE = 0x40
    NOCREATION = 0x80
    ENCRYPTION = 0x100 # Firebird 3.0
    DEFAULT = DATA_PAGES | IDX_PAGES

class SvcBackupFlag(Flag):
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

class SvcRestoreFlag(Flag):
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

class SvcNBackupFlag(Flag):
    "isc_spb_nbk_* flags for ServiceAction.NBAK"
    NONE = 0
    NO_TRIGGERS = 0x01

class SvcPropertiesFlag(Flag):
    "isc_spb_prp_* flags for ServiceAction.PROPERTIES"
    ACTIVATE = 0x0100
    DB_ONLINE = 0x0200
    NOLINGER = 0x0400

# Dataclasses

@dataclass
class StatementMetadata:
    ""
    #index: int
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
    "Table access statistics"
    #table_name: str
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
    "Information about Firebird user"
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

apilevel = '2.0'
threadsafety = 1
paramstyle = 'qmark'

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

Date = datetime.date
Time = datetime.time
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

Binary = memoryview

class DBAPITypeObject:
    def __init__(self, *values):
        self.values = values

    def __cmp__(self, other):
        if other in self.values:
            return 0
        if other < self.values:
            return 1
        else:
            return -1

STRING = DBAPITypeObject(str)
BINARY = DBAPITypeObject(bytes, bytearray)
NUMBER = DBAPITypeObject(int, float, decimal.Decimal)
DATETIME = DBAPITypeObject(datetime.datetime, datetime.date, datetime.time)
ROWID = DBAPITypeObject()

# Types for type hints

DESCRIPTION = t.Tuple[str, type, int, int, int, int, bool]
CB_OUTPUT_LINE = t.Callable[[str], None]

class Transactional(t.Protocol):
    def begin(self, tpb: bytes=None) -> None:
        ...
    def commit(self, *, retaining: bool=False) -> None:
        ...
    def rollback(self, *, retaining: bool=False, savepoint: str=None) -> None:
        ...

# ODS constants

ODS_FB_30 = 12.0

FS_ENCODING = sys.getfilesystemencoding()

# Info structural codes
isc_info_end = 1
isc_info_truncated = 2
isc_info_error = 3
isc_info_data_not_ready = 4

_master = None
_util = None
_thns = threading.local()

# ------------------------------------------------------------------------------
# Interface wrappers
# ------------------------------------------------------------------------------
# IVersioned(1)
class iVersioned:
    "IVersioned interface wrapper"
    VERSION = 1
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iVersioned':
        return iVersioned(result)
    def __init__(self, intf):
        self._as_parameter_ = intf
        if intf and self.vtable.version < self.VERSION:
            raise InterfaceError(f"Wrong interface version {self.vtable.version}, expected {self.VERSION}")
    def __get_status(self) -> 'iStatus':
        result = getattr(_thns, 'status', None)
        if result is None:
            result = _master.get_status()
            _thns.status = result
        return result
    def __report(self, cls: t.Union[Error, Warning],
                 vector_ptr: a.ISC_STATUS_ARRAY_PTR) -> None:
        msg = _util.format_status(self.status)
        sqlstate = c.create_string_buffer(6)
        a.api.fb_sqlstate(sqlstate, vector_ptr)
        i = 0
        gds_codes = []
        sqlcode = a.api.isc_sqlcode(vector_ptr)
        while vector_ptr[i] != 0:
            if vector_ptr[i] == 1:
                i += 1
                if (vector_ptr[i] & 0x14000000) == 0x14000000:
                    gds_codes.append(vector_ptr[i])
                    if (vector_ptr[i] == 335544436) and (vector_ptr[i+1] == 4):
                        i += 2
                        sqlcode = vector_ptr[i]
            i += 1
        self.status.init()
        return cls(msg, sqlstate=sqlstate.value.decode(),
                   gds_codes=tuple(gds_codes), sqlcode=sqlcode)
    def _check(self) -> None:
        state = self.status.get_state()
        if StateFlag.ERRORS in state:
            raise self.__report(DatabaseError, self.status.get_errors())
        elif StateFlag.WARNINGS in state:
            raise self.__report(Warning, self.status.get_warning())
    vtable = property(lambda self: self._as_parameter_.contents.vtable.contents)
    status: 'iStatus' = property(__get_status)
# IReferenceCounted(2)
class iReferenceCounted(iVersioned):
    "IReferenceCounted interface wrapper"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iReferenceCounted':
        return iReferenceCounted(result)
    def __init__(self, intf):
        super().__init__(intf)
        self._refcnt: int = 1
    def __del__(self):
        if self._refcnt > 0:
            self.release()
    def __enter__(self) -> 'iReferenceCounted':
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()
    def add_ref(self) -> None:
        "Increase the reference by one"
        self._refcnt += 1
        self.vtable.addRef(c.cast(self, a.IReferenceCounted))
    def release(self) -> int:
        "Decrease the reference by one"
        self._refcnt -= 1
        result = self.vtable.release(c.cast(self, a.IReferenceCounted))
        return result
# IDisposable(2)
class iDisposable(iVersioned):
    "IDisposable interface wrapper"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iDisposable':
        return iDisposable(result)
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
            self.vtable.dispose(c.cast(self, a.IDisposable))
        self._disposed = True
# IStatus(3) : Disposable
class iStatus(iDisposable):
    "Class that wraps IStatus interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iStatus':
        return iStatus(result)
    def init(self) -> None:
        "Cleanup interface, set it to initial state"
        self.vtable.init(self)
    def get_state(self) -> StateFlag:
        "Returns state flags, may be OR-ed."
        return StateFlag(self.vtable.getState(self))
    def set_errors2(self, length: int, value: t.ByteString) -> None:
        "Set contents of errors vector with length explicitly specified in a call"
        self.vtable.setErrors2(self, length, value)
    def set_warning2(self, length: int, value: t.ByteString) -> None:
        "Set contents of warnings vector with length explicitly specified in a call"
        self.vtable.setWarnings2(self, length, value)
    def set_errors(self, value: t.ByteString) -> None:
        "Set contents of errors vector, length is defined by value context"
        self.vtable.setErrors(self, value)
    def set_warnings(self, value: t.ByteString) -> None:
        "Set contents of warnings vector, length is defined by value context"
        self.vtable.setWarnings(self, value)
    def get_errors(self) -> a.ISC_STATUS_ARRAY_PTR:
        "Returns errors vector"
        return self.vtable.getErrors(self)
    def get_warning(self) -> a.ISC_STATUS_ARRAY_PTR:
        "Returns warnings vector"
        return self.vtable.getWarnings(self)
    def clone(self) -> 'iStatus':
        "Create clone of current interface"
        return iStatus(self.vtable.clone(self))
# IPluginBase(3) : ReferenceCounted
class iPluginBase(iReferenceCounted):
    "IPluginBase interface wrapper"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iPluginBase':
        return iPluginBase(result)
    def set_owner(self, r: iReferenceCounted) -> None:
        "Set the owner"
        self.vtable.setOwner(self, r)
    def get_owner(self) -> iReferenceCounted:
        "Returns owner"
        return iReferenceCounted(self.vtable.getOwner(self))
#? IPluginSet(3) : ReferenceCounted
# IConfigEntry(3) : ReferenceCounted
class iConfigEntry(iReferenceCounted):
    "Class that wraps IConfigEntry interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iConfigEntry':
        return iConfigEntry(result)
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
    def get_sub_config(self, status: iStatus) -> 'iConfig':
        "Treats sub-entries as separate configuration file and returns IConfig interface for it"
        result = iConfig(self.vtable.getSubConfig(self, status))
        return result
# IConfig(3) : ReferenceCounted
class iConfig(iReferenceCounted):
    "Class that wraps IConfig interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iConfig':
        return iConfig(result)
    def find(self, status: iStatus, name: str) -> iConfigEntry:
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
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iFirebirdConf':
        return iFirebirdConf(result)
    def get_key(self, name: str) -> int:
        "Returns key for configuration parameter"
        return self.vtable.getKey(self, name.encode()).value
    def as_integer(self, key: int) -> int:
        "Returns integer value of conf. parameter"
        return self.vtable.asInteger(self, key).value
    def as_string(self, key: int) -> str:
        "Returns string value of conf. parameter"
        return self.vtable.asString(self, key).decode()
    def as_boolean(self, key: str) -> bool:
        "Returns boolean value of conf. parameter"
        return self.vtable.asBoolean(self, key).value
#? IPluginConfig(3) : ReferenceCounted
#? IPluginFactory(2) : Versioned
#? IPluginModule(3) : Versioned
# IPluginManager(2) : Versioned
class iPluginManager(iVersioned):
    "IPluginManager interface wrapper. This is only STUB."
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iPluginManager':
        return iPluginManager(result)
#? ICryptKey(2) : Versioned
# IConfigManager(2) : Versioned
class iConfigManager(iVersioned):
    "Class that wraps IConfigManager interface for use from Python"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iConfigManager':
        return iConfigManager(result)
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
# IEventCallback(3) : ReferenceCounted
class iEventCallback(iReferenceCounted):
    "Class that wraps IEventCallback interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iEventCallback':
        return iEventCallback(result)
# IBlob(3) : ReferenceCounted
class iBlob(iReferenceCounted):
    "Class that wraps IBlob interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iBlob':
        return iBlob(result)
    def get_info(self, items: bytes, buffer: bytes) -> None:
        "Replaces `isc_blob_info()`"
        self.vtable.getInfo(self, self.status, len(items), items, len(buffer), buffer)
        self._check()
    def get_segment(self, size: int, buffer: c.c_void_p, bytes_read: a.Cardinal) -> StateResult:
        """Replaces `isc_get_segment()`. Unlike it never returns `isc_segstr_eof`
and `isc_segment` errors (that are actually not errors), instead returns completion
codes IStatus::RESULT_NO_DATA and IStatus::RESULT_SEGMENT, normal return is IStatus::RESULT_OK."""
        result = self.vtable.getSegment(self, self.status, size, buffer, bytes_read)
        self._check()
        return StateResult(result)
    def put_segment(self, length: int, buffer: t.Any) -> None:
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
    def get_info2(self, code: BlobInfoCode) -> t.Any:
        "Returns information about BLOB"
        blob_info = (0).to_bytes(10, 'little')
        self.get_info(bytes([code]), blob_info)
        i = 0
        while blob_info[i] != isc_info_end:
            _code = blob_info[i]
            i += 1
            if _code == code:
                size = bytes_to_int(blob_info[i:i+2], True)
                result = bytes_to_int(blob_info[i+2:i+2+size], True)
                i += size + 2
        return result

# ITransaction(3) : ReferenceCounted
class iTransaction(iReferenceCounted):
    "Class that wraps ITransaction interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iTransaction':
        return iTransaction(result)
    def get_info(self, items: bytes, buffer: bytes) -> None:
        "Replaces `isc_transaction_info()`"
        self.vtable.getInfo(self, self.status, len(items), items, len(buffer), buffer)
        self._check()
    def prepare(self, message: bytes) -> None:
        "Replaces `isc_prepare_transaction2()`"
        self.vtable.prepare(self, self.status, len(message, message))
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
    def join(self, transaction: 'iTransaction') -> 'iTransaction':
        """Joins current transaction and passed as parameter transaction into
single distributed transaction (using Dtc). On success both current transaction
and passed as parameter transaction are released and should not be used any more."""
        result = self.vtable.join(self, self.status, transaction)
        self._check()
        self._refcnt -= 1
        transaction._refcnt -= 1
        return iTransaction(result)
    def validate(self, attachment: 'iAttachment') -> 'iTransaction':
        "This method is used to support distributed transactions coordinator"
        result = self.vtable.validate(self, self.status, attachment)
        self._check()
        return self if result is not None else None
    def enter_dtc(self) -> 'iTransaction':
        "This method is used to support distributed transactions coordinator"
        raise InterfaceError("Method not supported")
# IMessageMetadata(3) : ReferenceCounted
class iMessageMetadata(iReferenceCounted):
    "Class that wraps IMessageMetadata interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iMessageMetadata':
        return iMessageMetadata(result)
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
    def get_builder(self) -> 'iMetadataBuilder':
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
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iMetadataBuilder':
        return iMetadataBuilder(result)
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
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iResultSet':
        return iResultSet(result)
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
    def fetch_absolute(self, possition: int, message: bytes) -> StateResult:
        "Fetch record by it's absolute position in result set"
        result = self.vtable.fetchAbsolute(self, self.status, possition, message)
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
        self.vtable.setDelayedOutputFormat(self, self.status, fmt)
        self._check()
# IStatement(3) : ReferenceCounted
class iStatement(iReferenceCounted):
    "Class that wraps IStatement interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iStatement':
        return iStatement(result)
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
        result = self.vtable.execute(self, self.status, transaction, in_meta,
                                     in_buffer, out_meta, out_buffer)
        self._check()
        transaction._as_parameter_ = result
    def open_cursor(self, transaction: iTransaction, in_meta: iMessageMetadata,
                    in_buffer: bytes, out_meta: iMessageMetadata, flags: CursorFlag) -> iResultSet:
        """Executes SQL statement potentially returning multiple rows of data.
Returns ResultSet interface which should be used to fetch that data. Format of
output data is defined by outMetadata parameter, leaving it NULL default format
may be used. Parameter flags is needed to open bidirectional cursor setting it's
value to IStatement::CURSOR_TYPE_SCROLLABLE."""
        result = self.vtable.openCursor(self, self.status, transaction, in_meta,
                                        in_buffer, out_meta, flags)
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
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iRequest':
        return iRequest(result)
    def receive(self, level: int, msg_type: int, message: bytes) -> None:
        self.vtable.receive(self, self.status, level, msg_type, len(message), message)
        self._check()
    def send(self, level: int, msg_type: int, message: bytes) -> None:
        self.vtable.send(self, self.status, level, msg_type, len(message), message)
        self._check()
    def get_info(self, level: int, items: bytes, buffer: bytes) -> None:
        self.vtable.getInfo(self, self.status, level, len(items), items, len(buffer), buffer)
        self._check()
    def start(self, transaction: iTransaction, level: int) -> None:
        self.vtable.start(self, self.status, transaction, level)
        self._check()
    def start_and_send(self, transaction: iTransaction, level: int, msg_type: int, message: bytes) -> None:
        self.vtable.startAndSend(self, self.status, transaction, level, msg_type, len(message), message)
        self._check()
    def unwind(self, level: int) -> None:
        self.vtable.unwind(self, self.status, level)
        self._check()
    def free(self) -> None:
        self.vtable.free(self, self.status)
        self._check()
        self._refcnt -= 1
# IEvents(3) : ReferenceCounted
class iEvents(iReferenceCounted):
    "Class that wraps IEvents interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iEvents':
        return iEvents(result)
    def cancel(self) -> None:
        "Cancels events monitoring started by IAttachment::queEvents()"
        self.vtable.cancel(self, self.status)
        self._check()
# IAttachment(3) : ReferenceCounted
class iAttachment(iReferenceCounted):
    "Class that wraps IAttachment interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iAttachment':
        return iAttachment(result)
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
    def transact_request(self, transaction: iTransaction, blr: bytes,
                         in_msg: bytes, out_msg: bytes) -> None:
        "Support of ISC API"
        self.vtable.transactRequest(self, self.status, transaction, len(blr), blr,
                                    len(in_msg), in_msg, len(out_msg), out_msg)
        self._check()
    def create_blob(self, transaction: iTransaction, id_: a.ISC_QUAD, bpb: bytes = None) -> iBlob:
        "Creates new blob, stores it's identifier in id, replaces `isc_create_blob2()`"
        result = self.vtable.createBlob(self, self.status, transaction, c.byref(id_),
                                        len(bpb) if bpb is not None else 0, bpb)
        self._check()
        return iBlob(result)
    def open_blob(self, transaction: iTransaction, id_: a.ISC_QUAD, bpb: bytes = None) -> iBlob:
        "Opens existing blob, replaces `isc_open_blob2()`"
        result = self.vtable.openBlob(self, self.status, transaction, c.byref(id_),
                                      len(bpb) if bpb is not None else 0, bpb)
        self._check()
        return iBlob(result)
    def get_slice(self, transaction: iTransaction, id_: a.ISC_QUAD, sdl: bytes,
                  param: bytes, slice_: bytes) -> int:
        "Support of ISC API"
        result = self.vtable.getSlice(self, self.status, transaction, c.byref(id_),
                                      len(sdl), sdl, len(param), param, len(slice_),
                                      slice_)
        self._check()
        return result
    def put_slice(self, transaction: iTransaction, id_: a.ISC_QUAD, sdl: bytes,
                  param: bytes, slice_: bytes) -> None:
        "Support of ISC API"
        self.vtable.putSlice(self, self.status, transaction, c.byref(id_), len(sdl),
                             sdl, len(param), param, len(slice_), slice_)
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
        result = self.vtable.prepare(self, self.status, transaction, len(b_stmt),
                                     b_stmt, dialect, flags)
        self._check()
        return iStatement(result)
    def execute(self, transaction: iTransaction, stmt: str, dialect: int,
                in_metadata: iMessageMetadata = None, in_buffer: bytes = None,
                out_metadata: iMessageMetadata = None, out_buffer: bytes = None) -> iTransaction:
        """Executes any SQL statement except returning multiple rows of data.
Partial analogue of `isc_dsql_execute2()` - in and out XSLQDAs replaced with
input and output messages with appropriate buffers."""
        b_stmt: bytes = stmt.encode(self.charset)
        result = self.vtable.execute(self, self.status, transaction, len(b_stmt),
                                     b_stmt, dialect, in_metadata, in_buffer,
                                     out_metadata, out_buffer)
        self._check()
        transaction._as_parameter_ = result
    def open_cursor(self, transaction: iTransaction, stmt: str, dialect: int,
                    in_metadata: iMessageMetadata, in_buffer: bytes,
                    out_metadata: iMessageMetadata, cursor_name: str,
                    cursor_flags: int) -> iResultSet:
        """Executes SQL statement potentially returning multiple rows of data.
Returns iResultSet interface which should be used to fetch that data. Format of
output data is defined by out_metadata parameter, leaving it NULL default format
may be used. Parameter cursor_name specifies name of opened cursor (analogue of
`isc_dsql_set_cursor_name()`). Parameter cursor_flags is needed to open
bidirectional cursor setting it's value to Istatement::CURSOR_TYPE_SCROLLABLE."""
        b_stmt: bytes = stmt.encode(self.charset)
        result = self.vtable.openCursor(self, self.status, transaction, len(b_stmt),
                                        b_stmt, dialect, in_metadata, in_buffer,
                                        out_metadata, cursor_name.encode(self.charset),
                                        cursor_flags)
        self._check()
        return iResultSet(result)
    def que_events(self, callback: iEventCallback, events: bytes) -> iEvents:
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
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iService':
        return iService(result)
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
        self.vtable.query(self, self.status, 0 if send is None else len(send), send, len(receive), receive,
                          len(buffer), buffer)
        self._check()
    def start(self, spb: bytes) -> None:
        "Start utility in services manager. Replaces `isc_service_start()`."
        self.vtable.start(self, self.status, len(spb), spb)
        self._check()
# IProvider(4) : PluginBase
class iProvider(iPluginBase):
    "Class that wraps IProvider interface for use from Python"
    VERSION = 4
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iProvider':
        return iProvider(result)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
    def attach_database(self, filename: str, dpb: t.Optional[bytes] = None,
                        encoding: str = 'ascii') -> iAttachment:
        "Replaces `isc_attach_database()`"
        if dpb is None:
            result = self.vtable.attachDatabase(self, self.status, filename.encode(encoding), 0, None)
        else:
            result = self.vtable.attachDatabase(self, self.status, filename.encode(encoding), len(dpb), dpb)
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
    def set_dbcrypt_callback(self, callback: 'iCryptKeyCallback') -> None:
        "Sets database encryption callback interface that will be used for following database and service attachments"
        self.vtable.setDbCryptCallback(self, self.status, callback)
        self._check()
# IDtcStart(3) : Disposable
class iDtcStart(iDisposable):
    "Class that wraps IDtcStart interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iDtcStart':
        return iDtcStart(result)
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
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iDtc':
        return iDtc(result)
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
#? IAuth(4) : PluginBase
#? IWriter(2) : Versioned
#? IServerBlock(2) : Versioned
#? IClientBlock(4) : ReferenceCounted
#? IServer(6) : Auth
#? IClient(5) : Auth
#? IUserField(2) : Versioned
#? ICharUserField(3) : IUserField
#? IIntUserField(3) : IUserField
#? IUser(2) : Versioned
#? IListUsers(2) : Versioned
#? ILogonInfo(2) : Versioned
#? IManagement(4) : PluginBase
#? IAuthBlock(2) : Versioned
#? IWireCryptPlugin(4) : PluginBase
# ICryptKeyCallback(2) : Versioned
class iCryptKeyCallback(iVersioned):
    "Class that wraps ICryptKeyCallback interface for use from Python"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iCryptKeyCallback':
        return iCryptKeyCallback(result)
#? IKeyHolderPlugin(5) : PluginBase
#? IDbCryptInfo(3) : ReferenceCounted
#? IDbCryptPlugin(5) : PluginBase
#? IExternalContext(2) : Versioned
#? IExternalResultSet(3) : Disposable
#? IExternalFunction(3) : Disposable
#? IExternalProcedure(3) : Disposable
#? IExternalTrigger(3) : Disposable
#? IRoutineMetadata(2) : Versioned
#? IExternalEngine(4) : PluginBase
# ITimer(3) : ReferenceCounted
class iTimer(iReferenceCounted):
    "Class that wraps ITimer interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iTimer':
        return iTimer(result)
# ITimerControl(2) : Versioned
class iTimerControl(iVersioned):
    "Class that wraps ITimerControl interface for use from Python"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iTimerControl':
        return iTimerControl(result)
    def start(self, timer: iTimer, microseconds: int) -> None:
        self.vtable.start(self, self.status, timer, microseconds)
        self._check()
    def stop(self, timer: iTimer) -> None:
        self.vtable.stop(self, self.status, timer)
        self._check()
# IVersionCallback(2) : Versioned
class iVersionCallback(iVersioned):
    "Class that wraps IVersionCallback interface for use from Python"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iVersionCallback':
        return iVersionCallback(result)
# IOffsetsCallback(2) : Versioned
class iOffsetsCallback(iVersioned):
    "Class that wraps IOffsetsCallback interface for use from Python"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iOffsetsCallback':
        return iOffsetsCallback(result)
# IXpbBuilder(3) : Disposable
class iXpbBuilder(iDisposable):
    "Class that wraps IXpbBuilder interface for use from Python"
    VERSION = 3
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iXpbBuilder':
        return iXpbBuilder(result)
    def clear(self) -> None:
        self.vtable.clear(self, self.status)
        self._check()
    def remove_current(self) -> None:
        self.vtable.removeCurrent(self, self.status)
        self._check()
    def insert_int(self, tag: int, value: int) -> None:
        self.vtable.insertInt(self, self.status, tag, value)
        self._check()
    def insert_bigint(self, tag: int, value: int) -> None:
        self.vtable.insertBigInt(self, self.status, tag, value)
        self._check()
    def insert_bytes(self, tag: int, value: bytes) -> None:
        self.vtable.insertBytes(self, self.status, tag, value, len(value))
        self._check()
    def insert_string(self, tag: int, value: str, encoding = 'ascii') -> None:
        self.vtable.insertString(self, self.status, tag, value.encode(encoding))
        self._check()
    def insert_tag(self, tag: int) -> None:
        self.vtable.insertTag(self, self.status, tag)
        self._check()
    def is_eof(self) -> bool:
        result = self.vtable.isEof(self, self.status)
        self._check()
        return result
    def move_next(self) -> None:
        self.vtable.moveNext(self, self.status)
        self._check()
    def rewind(self) -> None:
        self.vtable.rewind(self, self.status)
        self._check()
    def find_first(self, tag: int) -> bool:
        result = self.vtable.findFirst(self, self.status, tag)
        self._check()
        return result
    def find_next(self) -> bool:
        result = self.vtable.findNext(self, self.status)
        self._check()
        return result
    def get_tag(self) -> int:
        result = self.vtable.getTag(self, self.status)
        self._check()
        return result
    def get_length(self) -> int:
        result = self.vtable.getLength(self, self.status)
        self._check()
        return result
    def get_int(self) -> int:
        result = self.vtable.getInt(self, self.status)
        self._check()
        return result
    def get_bigint(self) -> int:
        result = self.vtable.getBigInt(self, self.status)
        self._check()
        return result
    def get_string(self) -> str:
        result = self.vtable.getString(self, self.status)
        self._check()
        return c.string_at(result).decode()
    def get_bytes(self) -> bytes:
        buffer = self.vtable.getBytes(self, self.status)
        self._check()
        size = self.vtable.getLength(self, self.status)
        self._check()
        return c.string_at(buffer, size)
    def get_buffer_length(self) -> int:
        result = self.vtable.getBufferLength(self, self.status)
        self._check()
        return result
    def get_buffer(self) -> bytes:
        buffer = self.vtable.getBuffer(self, self.status)
        self._check()
        size = self.get_buffer_length()
        self._check()
        return c.string_at(buffer, size)
# IUtil(2) : Versioned
class iUtil(iVersioned):
    "Class that wraps IUtil interface for use from Python"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iUtil':
        return iUtil(result)
    def get_fb_version(self, attachment: iAttachment, callback: iVersionCallback) -> None:
        """Produce long and beautiful report about firebird version used.
It may be seen in ISQL when invoked with -Z switch."""
        self.vtable.getFbVersion(self, self.status, attachment, callback)
        self._check()
    def load_blob(self, status: iStatus, blob_id: a.ISC_QUAD, attachment: iAttachment, transaction: iTransaction, filename: str, is_text: bool) -> None:
        "Load blob from file"
        self.vtable.loadBlob(self, self.status, c.byref(blob_id), attachment, transaction, filename.encode(), is_text)
        self._check()
    def dump_blob(self, blob_id: a.ISC_QUAD, attachment: iAttachment, transaction: iTransaction, filename: str, is_text: bool) -> None:
        "Save blob to file"
        self.vtable.dumpBlob(self, self.status, c.byref(blob_id), attachment, transaction, filename.encode(), is_text)
        self._check()
    def get_perf_counters(self, attachment: iAttachment, counters_set: str) -> int:
        "Get statistics for given attachment"
        result = a.Int64(0)
        self.vtable.getPerfCounters(self, self.status, attachment, counters_set.encode(), c.byref(result))
        self._check()
        return result
    def execute_create_database(self, stmt: str, dialect: int) -> iAttachment:
        """Execute “CREATE DATABASE ...” statement – ISC trick with NULL statement
handle does not work with interfaces."""
        b_stmt: bytes = stmt.encode()
        result = self.vtable.executeCreateDatabase(self, self.status, len(b_stmt), b_stmt, dialect, c.byref(c.c_byte(1)))
        self._check()
        return iAttachment(result)
    def decode_date(self, date: t.Union[a.ISC_DATE, bytes]) -> datetime.date:
        "Replaces `isc_decode_sql_date()`"
        if isinstance(date, bytes):
            date = a.ISC_DATE.from_buffer_copy(date)
        year = a.Cardinal(0)
        month = a.Cardinal(0)
        day = a.Cardinal(0)
        self.vtable.decodeDate(self, date, c.byref(year), c.byref(month), c.byref(day))
        return datetime.date(year.value, month.value, day.value)
    def decode_time(self, time: t.Union[a.ISC_TIME, bytes]) -> datetime.time:
        "Replaces `isc_decode_sql_time()`"
        if isinstance(time, bytes):
            time = a.ISC_TIME.from_buffer_copy(time)
        hours = a.Cardinal(0)
        minutes = a.Cardinal(0)
        seconds = a.Cardinal(0)
        fractions = a.Cardinal(0)
        self.vtable.decodeTime(self, time, c.byref(hours), c.byref(minutes), c.byref(seconds), c.byref(fractions))
        return datetime.time(hours.value, minutes.value, seconds.value, fractions.value)
    def encode_date(self, date: datetime.date) -> a.ISC_DATE:
        "Replaces `isc_encode_sql_date()`"
        return self.vtable.encodeDate(self, date.year, date.month, date.day)
    def encode_time(self, time: datetime.time) -> a.ISC_TIME:
        "Replaces isc_encode_sql_time()"
        return self.vtable.encodeTime(self, time.hour, time.minute, time.second, time.microsecond)
    def format_status(self, status: iStatus) -> str:
        "Replaces `fb_interpret()`. Size of buffer, passed into this method, should not be less than 50 bytes."
        buffer = c.create_string_buffer(1024)
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
    def set_offsets(self, metadata: iMessageMetadata, callback: iOffsetsCallback) -> int:
        "Sets valid offsets in MessageMetadata. Performs calls to callback in OffsetsCallback for each field/parameter."
        result = self.vtable.setOffsets(self, self.status, metadata, callback)
        self._check()
        return result
#? ITraceDatabaseConnection(3) : TraceConnection
#? ITraceTransaction(3) : Versioned
#? ITraceParams(3) : Versioned
#? ITraceStatement(2) : Versioned
#? ITraceSQLStatement(3) : TraceStatement
#? ITraceBLRStatement(3) : TraceStatement
#? ITraceDYNRequest(2) : Versioned
#? ITraceContextVariable(2) : Versioned
#? ITraceProcedure(2) : Versioned
#? ITraceFunction(2) : Versioned
#? ITraceTrigger(2) : Versioned
#? ITraceServiceConnection(3) : TraceConnection
#? ITraceStatusVector(2) : Versioned
#? ITraceSweepInfo(2) : Versioned
#? ITraceLogWriter(4) : ReferenceCounted
#? ITraceInitInfo(2) : Versioned
#? ITracePlugin(3) : ReferenceCounted
#? ITraceFactory(4) : PluginBase
#? IUdrFunctionFactory(3) : Disposable
#? IUdrProcedureFactory(3) : Disposable
#? IUdrTriggerFactory(3) : Disposable
#? IUdrPlugin(2) : Versioned
# IMaster(2) : Versioned
class iMaster(iVersioned):
    "Class that wraps IMaster interface for use from Python"
    VERSION = 2
    @classmethod
    def wrap(cls, result, func=None, arguments=None) -> 'iMaster':
        return iMaster(result)
    def get_status(self) -> iStatus:
        return iStatus(self.vtable.getStatus(self))
    def get_dispatcher(self) -> iProvider:
        return iProvider(self.vtable.getDispatcher(self))
    def get_plugin_manager(self) -> iPluginManager:
        return iPluginManager(self.vtable.getPluginManager(self))
    def get_timer_control(self) -> iTimerControl:
        return iTimerControl(self.vtable.getTimerControl(self))
    def get_dtc(self) -> iDtc:
        return iDtc(self.vtable.getDtc(self))
    def register_attachment(self, provider: iProvider, attachment: iAttachment) -> iAttachment:
        return iAttachment(self.vtable.registerAttachment(self, provider, attachment))
    def register_transaction(self, attachment: iAttachment, transaction: iTransaction) -> iTransaction:
        return iTransaction(self.vtable.registerTransaction(self, attachment, transaction))
    def get_metadata_builder(self, fieldCount: int) -> iMetadataBuilder:
        if self.status in None:
            self.status = self.get_status()
        result = self.vtable.getMetadataBuilder(self, self.status, fieldCount)
        self._check()
        return iMetadataBuilder(result)
    def server_mode(self, mode: int) -> int:
        return self.vtable.serverMode(self, mode).value
    def get_util_interface(self) -> iUtil:
        return iUtil(self.vtable.getUtilInterface(self))
    def get_config_manager(self) -> iConfigManager:
        return iConfigManager(self.vtable.getConfigManager(self))
    def get_process_exiting(self) -> bool:
        return self.vtable.getProcessExiting(self).value


# ------------------------------------------------------------------------------
# Interface implementations
# ------------------------------------------------------------------------------

class IVersionedImpl:
    "Base class for objects that implement IVersioned interface"
    VERSION = 1
    def __init__(self):
        vt, vt_p, intf_s, intf = self._get_intf()
        self.__vtable = vt()
        self.__intf = intf_s(vtable=vt_p(self.__vtable))
        self._as_parameter_ = intf(self.__intf)
        self.vtable.version = c.c_ulong(self.VERSION)
    def _get_intf(self):
        return (a.IVersioned_VTable, a.IVersioned_VTablePtr, a.IVersioned_struct,
                a.IVersioned)
    vtable = property(lambda self: self._as_parameter_.contents.vtable.contents)

class IReferenceCountedImpl(IVersionedImpl):
    "IReferenceCounted interface wrapper"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.addRef = a.IReferenceCounted_addRef(self.add_ref)
        self.vtable.release = a.IReferenceCounted_release(self.release)
    def _get_intf(self):
        return (a.IReferenceCounted_VTable, a.IReferenceCounted_VTablePtr,
                a.IReferenceCounted_struct, a.IReferenceCounted)
    def add_ref(self) -> None:
        "Increase the reference by one"
    def release(self) -> int:
        "Decrease the reference by one"

class IDisposableImpl(IVersionedImpl):
    "IDisposable interface wrapper"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.dispose = a.IDisposable_dispose(self.dispose)
    def _get_intf(self):
        return (a.IDisposable_VTable, a.IDisposable_VTablePtr,
                a.IDisposable_struct, a.IDisposable)
    def dispose(self) -> None:
        "Dispose the interfaced object"

class IVersionCallbackImpl(IVersionedImpl):
    "Class that wraps IVersionCallback interface for use from Python"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.callback = a.IVersionCallback_callback(self.__callback)
    def _get_intf(self):
        return (a.IVersionCallback_VTable, a.IVersionCallback_VTablePtr,
                a.IVersionCallback_struct, a.IVersionCallback)
    def __callback(self, this: a.IVersionCallback, status: a.IStatus,
                   text: c.c_char_p):
        try:
            self.callback(text.decode())
        except:
            pass
    def callback(self, text: str) -> None:
        "Method called by engine"

class ICryptKeyCallbackImpl(IVersionedImpl):
    "Class that wraps ICryptKeyCallback interface for use from Python"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.callback = a.ICryptKeyCallback_callback(self.__callback)
    def _get_intf(self):
        return (a.ICryptKeyCallback_VTable, a.ICryptKeyCallback_VTablePtr,
                a.ICryptKeyCallback_struct, a.ICryptKeyCallback)
    def __callback(self, this: a.ICryptKeyCallback,
                   data_length: a.Cardinal, data: c.c_void_p,
                   buffer_length: a.Cardinal, buffer: c.c_void_p) -> a.Cardinal:
        try:
            key = self.get_crypt_key(data[:data_length], buffer_length)
            key_size = min(len(key), buffer_length)
            c.memmove(buffer, key, key_size)
            return key_size
        except:
            pass
    def get_crypt_key(self, data: bytes, max_key_size: int) -> bytes:
        "Should return crypt key"

class IOffsetsCallbackImp(IVersionedImpl):
    "Class that wraps IOffsetsCallback interface for use from Python"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.callback = a.IVersionCallback_callback(self.__callback)
    def _get_intf(self):
        return (a.IOffsetsCallback_VTable, a.IOffsetsCallback_VTablePtr,
                a.IOffsetsCallback_struct, a.IOffsetsCallback)
    def __callback(self, this: a.IOffsetsCallback, status: a.IStatus,
                   index: a.Cardinal, offset: a.Cardinal, nullOffset: a.Cardinal) -> None:
        try:
            self.set_offset(index, offset, nullOffset)
        except:
            pass
    def set_offset(self, index: int, offset: int, nullOffset: int) -> None:
        "Method called by engine"

class IEventCallbackImpl(IReferenceCountedImpl):
    "IEventCallback interface wrapper"
    VERSION = 2
    def __init__(self):
        super().__init__()
        self.vtable.eventCallbackFunction = a.IEventCallback_eventCallbackFunction(self.__callback)
    def _get_intf(self):
        return (a.IEventCallback_VTable, a.IEventCallback_VTablePtr,
                a.IEventCallback_struct, a.IEventCallback)
    def __callback(self, this: a.IVersionCallback, length: a.Cardinal, events: a.BytePtr) -> None:
        try:
            self.events_arrived(c.string_at(events, length))
        except:
            pass
    def events_arrived(self, events: bytes) -> None:
        "Method called by engine"

# API_LOADED hook

def __wrap_master(api: a.FirebirdAPI) -> None:
    api.fb_get_master_interface.errcheck = iMaster.wrap
    setattr(sys.modules[__name__], '_master', api.fb_get_master_interface())
    setattr(sys.modules[__name__], '_util', _master.get_util_interface())
    api.master: iMaster = _master
    api.util: iUtil = _util

hooks.add_hook(HookType.API_LOADED, __wrap_master)

def int_to_bytes(value: int, nbytes: int, unsigned: bool = False) -> bytes:
    "Convert int value to little endian bytes."
    if nbytes == 1:
        fmt = 'b'
    elif nbytes == 2:
        fmt = '<h'
    elif nbytes == 4:
        fmt = '<l'
    elif nbytes == 8:
        fmt = '<q'
    else:
        raise InternalError
    if unsigned:
        fmt = fmt.upper()
    return struct.pack(fmt, value)

def bytes_to_int(buffer: bytes, unsigned: bool = False) -> int:
    "Read as little endian"
    len_b = len(buffer)
    if len_b == 1:
        fmt = 'b'
    elif len_b == 2:
        fmt = '<h'
    elif len_b == 4:
        fmt = '<l'
    elif len_b == 8:
        fmt = '<q'
    else:
        raise InternalError
    if unsigned:
        fmt = fmt.upper()
    return struct.unpack(fmt, buffer)[0]
