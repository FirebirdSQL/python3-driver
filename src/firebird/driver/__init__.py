#coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/__init__.py
# DESCRIPTION:    The Firebird driver for Python 3
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

"""firebird-driver - The Firebird driver for Python 3


"""
from .config import driver_config, ServerConfig, DatabaseConfig, DriverConfig
from .fbapi import load_api, get_api
from .types import (Error, InterfaceError, DatabaseError, DataError,
     OperationalError, IntegrityError, InternalError, ProgrammingError,
     NotSupportedError, FirebirdWarning,
     NetProtocol, DirectoryCode, PageSize, DBKeyScope, DbInfoCode, Features, ReplicaMode,
     StmtInfoCode, TraInfoCode, TraInfoIsolation, TraInfoReadCommitted,
     TraInfoAccess, TraIsolation, TraReadCommitted, TraLockResolution, TraAccessMode,
     TableShareMode, TableAccessMode, Isolation, DefaultAction, StatementType, BlobType,
     DbAccessMode, DbSpaceReservation, DbWriteMode, ShutdownMode, OnlineMode,
     ShutdownMethod,
     CancelType, DecfloatRound, DecfloatTraps,
     ServerCapability, SrvRepairFlag, SrvStatFlag, SrvBackupFlag,
     SrvRestoreFlag, SrvNBackupFlag, SrvInfoCode, ConnectionFlag, EncryptionFlag,
     apilevel, threadsafety, paramstyle, DESCRIPTION_NAME, DESCRIPTION_TYPE_CODE,
     DESCRIPTION_DISPLAY_SIZE, DESCRIPTION_INTERNAL_SIZE, DESCRIPTION_PRECISION,
     DESCRIPTION_SCALE, DESCRIPTION_NULL_OK, Date, Time, Timestamp, DateFromTicks,
     TimeFromTicks, TimestampFromTicks, STRING, BINARY, NUMBER, DATETIME, ROWID,
     get_timezone)
from .core import (connect, create_database, connect_server, transaction, temp_database,
     tpb, TPB, CHARSET_MAP, TIMEOUT, DistributedTransactionManager, Connection, Cursor,
     Server, Statement)

#: Current driver version, SEMVER string.
__VERSION__ = '1.8.0'
