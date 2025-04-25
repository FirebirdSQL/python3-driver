# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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
from .config import DatabaseConfig, DriverConfig, ServerConfig, driver_config
from .core import (
    CHARSET_MAP,
    TIMEOUT,
    TPB,
    Connection,
    Cursor,
    DistributedTransactionManager,
    Server,
    Statement,
    TransactionManager,
    connect,
    connect_server,
    create_database,
    temp_database,
    tpb,
    transaction,
)
from .fbapi import get_api, load_api
from .types import (
    BINARY,
    DATETIME,
    DESCRIPTION_DISPLAY_SIZE,
    DESCRIPTION_INTERNAL_SIZE,
    DESCRIPTION_NAME,
    DESCRIPTION_NULL_OK,
    DESCRIPTION_PRECISION,
    DESCRIPTION_SCALE,
    DESCRIPTION_TYPE_CODE,
    NUMBER,
    ROWID,
    STRING,
    BlobType,
    CancelType,
    ConnectionFlag,
    DatabaseError,
    DataError,
    Date,
    DateFromTicks,
    DbAccessMode,
    DbInfoCode,
    DBKeyScope,
    DbSpaceReservation,
    DbWriteMode,
    DecfloatRound,
    DecfloatTraps,
    DefaultAction,
    DirectoryCode,
    EncryptionFlag,
    Error,
    Features,
    FirebirdWarning,
    IntegrityError,
    InterfaceError,
    InternalError,
    Isolation,
    NetProtocol,
    NotSupportedError,
    OnlineMode,
    OperationalError,
    PageSize,
    ProgrammingError,
    ReplicaMode,
    ResultSetInfoCode,
    ServerCapability,
    ShutdownMethod,
    ShutdownMode,
    SrvBackupFlag,
    SrvInfoCode,
    SrvNBackupFlag,
    SrvRepairFlag,
    SrvRestoreFlag,
    SrvStatFlag,
    StatementType,
    StmtInfoCode,
    TableAccessMode,
    TableShareMode,
    Time,
    TimeFromTicks,
    Timestamp,
    TimestampFromTicks,
    TraAccessMode,
    TraInfoAccess,
    TraInfoCode,
    TraInfoIsolation,
    TraInfoReadCommitted,
    TraIsolation,
    TraLockResolution,
    TraReadCommitted,
    apilevel,
    get_timezone,
    paramstyle,
    threadsafety,
)

#: Current driver version, SEMVER string.
__VERSION__ = '2.0.0'
