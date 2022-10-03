# coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/fbapi.py
# DESCRIPTION:    New Firebird API
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

"""firebird-driver - New Firebird API
"""
from typing import Union
import sys
import decimal
import ctypes
from ctypes import c_byte, c_ubyte, c_char, c_bool, c_short, c_ushort, c_int, c_uint, \
    c_long, c_ulong, c_longlong, c_ulonglong, c_char_p, c_void_p, \
    POINTER, CFUNCTYPE, Structure, create_string_buffer, cast, addressof
from ctypes.util import find_library
from locale import getpreferredencoding
from pathlib import Path
from contextlib import suppress
import platform
from .config import driver_config
from .hooks import APIHook, register_class, get_callbacks

# Constants

OCTETS = 1  # Character set ID

# Blob Subtypes
isc_blob_untyped = 0
# internal subtypes
isc_blob_text = 1
isc_blob_blr = 2
isc_blob_acl = 3
isc_blob_ranges = 4
isc_blob_summary = 5
isc_blob_format = 6
isc_blob_tra = 7
isc_blob_extfile = 8
isc_blob_debug_info = 9
isc_blob_max_predefined_subtype = 10

# Type codes

SQL_TEXT = 452
SQL_VARYING = 448
SQL_SHORT = 500
SQL_LONG = 496
SQL_FLOAT = 482
SQL_DOUBLE = 480
SQL_D_FLOAT = 530
SQL_TIMESTAMP = 510
SQL_BLOB = 520
SQL_ARRAY = 540
SQL_QUAD = 550
SQL_TYPE_TIME = 560
SQL_TYPE_DATE = 570
SQL_INT64 = 580
SQL_BOOLEAN = 32764  # Firebird 3
SQL_NULL = 32766

SUBTYPE_NUMERIC = 1
SUBTYPE_DECIMAL = 2

# Internal type codes (for example used by ARRAY descriptor)

blr_text = 14
blr_text2 = 15
blr_short = 7
blr_long = 8
blr_quad = 9
blr_float = 10
blr_double = 27
blr_d_float = 11
blr_timestamp = 35
blr_varying = 37
blr_varying2 = 38
blr_blob = 261
blr_cstring = 40
blr_cstring2 = 41
blr_blob_id = 45
blr_sql_date = 12
blr_sql_time = 13
blr_int64 = 16
blr_blob2 = 17
blr_domain_name = 18
blr_domain_name2 = 19
blr_not_nullable = 20
blr_column_name = 21
blr_column_name2 = 22
blr_bool = 23
# Added in FB 4.0
blr_dec64 = 24 # DECFLOAT(16)
blr_dec128 = 25 # DECFLOAT(34)
blr_int128 = 26 # INT128
blr_sql_time_tz = 28
blr_timestamp_tz = 29
blr_ex_time_tz = 30
blr_ex_timestamp_tz = 31

# Masks for fb_shutdown_callback
fb_shut_confirmation = 1
fb_shut_preproviders = 2
fb_shut_postproviders = 4
fb_shut_finish = 8
fb_shut_exit = 16

# Shutdown reasons, used by engine
fb_shutrsn_svc_stopped = -1
fb_shutrsn_no_connection = -2
fb_shutrsn_app_stopped = -3
fb_shutrsn_signal = -5
fb_shutrsn_services = -6
fb_shutrsn_exit_called = -7
fb_shutrsn_emergency = -8

if platform.architecture() == ('64bit', 'WindowsPE'):  # pragma: no cover
    intptr_t = c_longlong
    uintptr_t = c_ulonglong
else:
    intptr_t = c_long
    uintptr_t = c_ulong

# Firebird configuration parameters (for use in iFirebirdConf.get_key())

config_items = {
    'DatabaseAccess': str,
    'RemoteAccess': bool,
    'ExternalFileAccess': str,
    'UdfAccess': str,
    'TempDirectories': str,
    'AuditTraceConfigFile': str,
    'MaxUserTraceLogSize': int,
    'DefaultDbCachePages': int,
    'DatabaseGrowthIncrement': int,
    'FileSystemCacheThreshold': int,
    'FileSystemCacheSize': int,
    'RemoteFileOpenAbility': bool,
    'TempBlockSize': int,
    'TempCacheLimit': int,
    'AuthServer': str,
    'AuthClient': str,
    'UserManager': str,
    'TracePlugin': str,
    'WireCryptPlugin': str,
    'KeyHolderPlugin': str,
    'AllowEncryptedSecurityDatabase': bool,
    'Providers': str,
    'DeadlockTimeout': int,
    'MaxUnflushedWrites': int,
    'MaxUnflushedWriteTime': int,
    'BugcheckAbort': bool,
    'RelaxedAliasChecking': bool,
    'ConnectionTimeout': int,
    'WireCrypt': str,
    'WireCompression': bool,
    'DummyPacketInterval': int,
    'RemoteServiceName': str,
    'RemoteServicePort': int,
    'RemoteAuxPort': int,
    'TcpRemoteBufferSize': int,
    'TcpNoNagle': bool,
    'IPv6V6Only': bool,
    'RemoteBindAddress': str,
    'LockMemSize': int,
    'LockAcquireSpins': int,
    'LockHashSlots': int,
    'EventMemSize': int,
    'CpuAffinityMask': int,
    'GCPolicy': str,
    'SecurityDatabase': str,
    'GuardianOption': bool,
    'ProcessPriorityLevel': int,
    'IpcName': str,
    'RemotePipeName': str,
    'Redirection': bool,
    'ServerMode': str,
    'MaxIdentifierByteLength': int, # This and next are for Firebird 4
    'MaxIdentifierCharLength': int,
    'StatementTimeout': int,
    'ConnectionIdleTimeout': int,
    'ReadConsistency': bool,
    'DefaultTimeZone': str,
    'SnapshotsMemSize': int,
    'TipCacheBlockSize': int,
    'OutputRedirectionFile': str,
    'ExtConnPoolSize': int,
    'ExtConnPoolLifeTime': int,
}

# Types

Int = c_int
IntPtr = POINTER(Int)
Int64 = c_long
Int64Ptr = POINTER(Int64)
QWord = c_ulong
STRING = c_char_p
ISC_DATE = c_int
ISC_TIME = c_uint
ISC_UCHAR = c_ubyte
ISC_SHORT = c_short
ISC_USHORT = c_ushort
ISC_LONG = c_int
ISC_LONG_PTR = POINTER(ISC_LONG)
ISC_ULONG = c_uint
ISC_INT64 = c_longlong
ISC_UINT64 = c_ulonglong
# >>> Firebird 4
FB_DEC16 = c_ulonglong
FB_DEC16Ptr = POINTER(FB_DEC16)
FB_DEC34 = c_ulonglong * 2
FB_DEC34Ptr = POINTER(FB_DEC34)
FB_I128 = c_ulonglong * 2
FB_I128Ptr = POINTER(FB_I128)
# <<< FB4

class ISC_QUAD(Structure):
    "ISC_QUAD"
    _fields_ = [('high', ISC_LONG), ('low', ISC_ULONG)]

ISC_QUAD_PTR = POINTER(ISC_QUAD)
ISC_STATUS = intptr_t
ISC_STATUS_PTR = POINTER(ISC_STATUS)
ISC_STATUS_ARRAY = ISC_STATUS * 20
ISC_STATUS_ARRAY_PTR = POINTER(ISC_STATUS_ARRAY)
FB_API_HANDLE = c_uint
FB_API_HANDLE_PTR = POINTER(FB_API_HANDLE)

RESULT_VECTOR = ISC_ULONG * 15
ISC_EVENT_CALLBACK = CFUNCTYPE(None, POINTER(ISC_UCHAR), c_ushort, POINTER(ISC_UCHAR))
FB_SHUTDOWN_CALLBACK = CFUNCTYPE(c_int, c_int, c_int, c_void_p)

# >>> Firebird 4
class ISC_TIME_TZ(Structure):
    "ISC_TIME_TZ"
    _fields_ = [('utc_time', ISC_TIME), ('time_zone', ISC_USHORT)]
ISC_TIME_TZ_PTR = POINTER(ISC_TIME_TZ)

class ISC_TIME_TZ_EX(Structure):
    "ISC_TIME_TZ_EX"
    _fields_ = [('utc_time', ISC_TIME), ('time_zone', ISC_USHORT), ('ext_offset', ISC_SHORT)]
ISC_TIME_TZ_EX_PTR = POINTER(ISC_TIME_TZ_EX)

class ISC_TIMESTAMP(Structure):
    "ISC_TIMESTAMP"
    _fields_ = [('timestamp_date', ISC_DATE), ('timestamp_time', ISC_TIME)]
ISC_TIMESTAMP_PTR = POINTER(ISC_TIMESTAMP)

class ISC_TIMESTAMP_TZ(Structure):
    "ISC_TIMESTAMP_TZ"
    _fields_ = [('utc_timestamp', ISC_TIMESTAMP), ('time_zone', ISC_USHORT)]
ISC_TIMESTAMP_TZ_PTR = POINTER(ISC_TIMESTAMP_TZ)

class ISC_TIMESTAMP_TZ_EX(Structure):
    "ISC_TIMESTAMP_TZ_EX"
    _fields_ = [('utc_timestamp', ISC_TIMESTAMP), ('time_zone', ISC_USHORT), ('ext_offset', ISC_SHORT)]
ISC_TIMESTAMP_TZ_EX_PTR = POINTER(ISC_TIMESTAMP_TZ_EX)
# <<< Firebird 4

class ISC_ARRAY_BOUND(Structure):
    "ISC_ARRAY_BOUND"
    _fields_ = [('array_bound_lower', c_short), ('array_bound_upper', c_short)]

class ISC_ARRAY_DESC(Structure):
    "ISC_ARRAY_DESC"
    _fields_ = [
        ('array_desc_dtype', c_ubyte),
        ('array_desc_scale', c_ubyte),  # was ISC_SCHAR),
        ('array_desc_length', c_ushort),
        ('array_desc_field_name', c_char * 32),
        ('array_desc_relation_name', c_char * 32),
        ('array_desc_dimensions', c_short),
        ('array_desc_flags', c_short),
        ('array_desc_bounds', ISC_ARRAY_BOUND * 16)]
ISC_ARRAY_DESC_PTR = POINTER(ISC_ARRAY_DESC)

class TraceCounts(Structure):
    "Trace counters for table"
    _fields_ = [('relation_id', c_int), ('relation_name', c_char_p), ('counters', Int64Ptr)]
TraceCountsPtr = POINTER(TraceCounts)

class PerformanceInfo(Structure):
    "Performance info"
    _fields_ = [
        ('time', c_long),
        ('counters', Int64Ptr),
        ('count', c_uint),
        ('tables', TraceCountsPtr),
        ('records_fetched', c_long)]

#class Dsc(Structure):
    #"Field descriptor"
#Dsc._fields_ = [
    #('dtype', c_byte),
    #('scale', c_byte),
    #('length', c_short),
    #('sub_type', c_short),
    #('flags', c_short),
    #('address', POINTER(c_byte)),
#]

BooleanPtr = POINTER(c_byte)
BytePtr = POINTER(c_char)
Cardinal = c_uint
CardinalPtr = POINTER(Cardinal)
NativeInt = intptr_t
NativeIntPtr = POINTER(NativeInt)
PerformanceInfoPtr = POINTER(PerformanceInfo)
#dscPtr = POINTER(Dsc)
func_ptr = c_ulong

# ------------------------------------------------------------------------------
# Interface - Forward definitions
# ------------------------------------------------------------------------------

# IVersioned(1)
class IVersioned_VTable(Structure):
    "Interface virtual method table"
IVersioned_VTablePtr = POINTER(IVersioned_VTable)
class IVersioned_struct(Structure):
    "Fiebird Interface data structure"
    _fields_ = [('dummy', c_void_p), ('vtable', IVersioned_VTablePtr)]
IVersioned = POINTER(IVersioned_struct)
# IReferenceCounted(2)
class IReferenceCounted_VTable(Structure):
    "IReferenceCounted virtual method table"
IReferenceCounted_VTablePtr = POINTER(IReferenceCounted_VTable)
class IReferenceCounted_struct(Structure):
    "IReferenceCounted data structure"
    _fields_ = [('dummy', c_void_p), ('vtable', IReferenceCounted_VTablePtr)]
IReferenceCounted = POINTER(IReferenceCounted_struct)
# IDisposable(2)
class IDisposable_VTable(Structure):
    "IDisposable virtual method table"
IDisposable_VTablePtr = POINTER(IDisposable_VTable)
class IDisposable_struct(Structure):
    "IDisposable data structure"
    _fields_ = [('dummy', c_void_p), ('vtable', IDisposable_VTablePtr)]
IDisposable = POINTER(IDisposable_struct)
# IStatus(3) : Disposable
class IStatus_VTable(Structure):
    "IStatus VTable"
IStatus_VTablePtr = POINTER(IStatus_VTable)
class IStatus_struct(Structure):
    "IStatus interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IStatus_VTablePtr)]
IStatus = POINTER(IStatus_struct)
# IMaster(2) : Versioned
class IMaster_VTable(Structure):
    "IMaster virtual method table"
IMaster_VTablePtr = POINTER(IMaster_VTable)
class IMaster_struct(Structure):
    "IMaster interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IMaster_VTablePtr)]
IMaster = POINTER(IMaster_struct)
# IPluginBase(3) : ReferenceCounted
class IPluginBase_VTable(Structure):
    "IPluginBase virtual method table"
IPluginBase_VTablePtr = POINTER(IPluginBase_VTable)
class IPluginBase_struct(Structure):
    "IPluginBase interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IPluginBase_VTablePtr)]
IPluginBase = POINTER(IPluginBase_struct)
# IPluginSet(3) : ReferenceCounted
class IPluginSet_VTable(Structure):
    "IPluginSet virtual method table"
IPluginSet_VTablePtr = POINTER(IPluginSet_VTable)
class IPluginSet_struct(Structure):
    "IPluginSet interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IPluginSet_VTablePtr)]
IPluginSet = POINTER(IPluginSet_struct)
# IConfigEntry(3) : ReferenceCounted
class IConfigEntry_VTable(Structure):
    "IConfigEntry virtual method table"
IConfigEntry_VTablePtr = POINTER(IConfigEntry_VTable)
class IConfigEntry_struct(Structure):
    "IConfigEntry interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IConfigEntry_VTablePtr)]
IConfigEntry = POINTER(IConfigEntry_struct)
# IConfig(3) : ReferenceCounted
class IConfig_VTable(Structure):
    "IConfig virtual method table"
IConfig_VTablePtr = POINTER(IConfig_VTable)
class IConfig_struct(Structure):
    "IConfig interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IConfig_VTablePtr)]
IConfig = POINTER(IConfig_struct)
# IFirebirdConf(3) : ReferenceCounted
class IFirebirdConf_VTable(Structure):
    "IFirebirdConf virtual method table"
IFirebirdConf_VTablePtr = POINTER(IFirebirdConf_VTable)
class IFirebirdConf_struct(Structure):
    "IFirebirdConf interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IFirebirdConf_VTablePtr)]
IFirebirdConf = POINTER(IFirebirdConf_struct)
# IPluginConfig(3) : ReferenceCounted
# IPluginFactory(2) : Versioned
# IPluginModule(3) : Versioned
# IPluginManager(2) : Versioned
class IPluginManager_VTable(Structure):
    "IPluginManager virtual method table"
IPluginManager_VTablePtr = POINTER(IPluginManager_VTable)
class IPluginManager_struct(Structure):
    "IPluginManager interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IPluginManager_VTablePtr)]
IPluginManager = POINTER(IPluginManager_struct)
# ICryptKey(2) : Versioned
# IConfigManager(2) : Versioned
class IConfigManager_VTable(Structure):
    "IConfigManager virtual method table"
IConfigManager_VTablePtr = POINTER(IConfigManager_VTable)
class IConfigManager_struct(Structure):
    "IConfigManager interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IConfigManager_VTablePtr)]
IConfigManager = POINTER(IConfigManager_struct)
# IEventCallback(3) : ReferenceCounted
class IEventCallback_VTable(Structure):
    "IEventCallback virtual method table"
IEventCallback_VTablePtr = POINTER(IEventCallback_VTable)
class IEventCallback_struct(Structure):
    "IEventCallback interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IEventCallback_VTablePtr)]
IEventCallback = POINTER(IEventCallback_struct)
# IBlob(3) : ReferenceCounted
class IBlob_VTable(Structure):
    "IBlob virtual method table"
IBlob_VTablePtr = POINTER(IBlob_VTable)
class IBlob_struct(Structure):
    "IBlob interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IBlob_VTablePtr)]
IBlob = POINTER(IBlob_struct)
# ITransaction(3) : ReferenceCounted
class ITransaction_VTable(Structure):
    "ITransaction virtual method table"
ITransaction_VTablePtr = POINTER(ITransaction_VTable)
class ITransaction_struct(Structure):
    "ITransaction interface"
    _fields_ = [('dummy', c_void_p), ('vtable', ITransaction_VTablePtr)]
ITransaction = POINTER(ITransaction_struct)
# IMessageMetadata(3) : ReferenceCounted
class IMessageMetadata_VTable(Structure):
    "IMessageMetadata virtual method table"
IMessageMetadata_VTablePtr = POINTER(IMessageMetadata_VTable)
class IMessageMetadata_struct(Structure):
    "IMessageMetadata interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IMessageMetadata_VTablePtr)]
IMessageMetadata = POINTER(IMessageMetadata_struct)
# IMetadataBuilder(3) : ReferenceCounted
class IMetadataBuilder_VTable(Structure):
    "IMetadataBuilder virtual method table"
IMetadataBuilder_VTablePtr = POINTER(IMetadataBuilder_VTable)
class IMetadataBuilder_struct(Structure):
    "IMetadataBuilder interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IMetadataBuilder_VTablePtr)]
IMetadataBuilder = POINTER(IMetadataBuilder_struct)
# IResultSet(3) : ReferenceCounted
class IResultSet_VTable(Structure):
    "IResultSet virtual method table"
IResultSet_VTablePtr = POINTER(IResultSet_VTable)
class IResultSet_struct(Structure):
    "IResultSet interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IResultSet_VTablePtr)]
IResultSet = POINTER(IResultSet_struct)
# IStatement(3) : ReferenceCounted
class IStatement_VTable(Structure):
    "IStatement virtual method table"
IStatement_VTablePtr = POINTER(IStatement_VTable)
class IStatement_struct(Structure):
    "IStatement interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IStatement_VTablePtr)]
IStatement = POINTER(IStatement_struct)
# >>> Firebird 4
# IBatch(3) : ReferenceCounted
class IBatch_VTable(Structure):
    "IBatch virtual method table"
IBatch_VTablePtr = POINTER(IBatch_VTable)
class IBatch_struct(Structure):
    "IBatch interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IBatch_VTablePtr)]
IBatch = POINTER(IBatch_struct)
# IBatchCompletionState(3) : Disposable
class IBatchCompletionState_VTable(Structure):
    "IBatchCompletionState virtual method table"
IBatchCompletionState_VTablePtr = POINTER(IBatchCompletionState_VTable)
class IBatchCompletionState_struct(Structure):
    "IBatchCompletionState interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IBatchCompletionState_VTablePtr)]
IBatchCompletionState = POINTER(IBatchCompletionState_struct)
# IReplicator(3) : ReferenceCounted
# <<< Firebird 4
# IRequest(3) : ReferenceCounted
class IRequest_VTable(Structure):
    "IRequest virtual method table"
IRequest_VTablePtr = POINTER(IRequest_VTable)
class IRequest_struct(Structure):
    "IRequest interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IRequest_VTablePtr)]
IRequest = POINTER(IRequest_struct)
# IEvents(3) : ReferenceCounted
class IEvents_VTable(Structure):
    "IEvents virtual method table"
IEvents_VTablePtr = POINTER(IEvents_VTable)
class IEvents_struct(Structure):
    "IEvents interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IEvents_VTablePtr)]
IEvents = POINTER(IEvents_struct)
# IAttachment(3) : ReferenceCounted
class IAttachment_VTable(Structure):
    "IAttachment virtual method table"
IAttachment_VTablePtr = POINTER(IAttachment_VTable)
class IAttachment_struct(Structure):
    "IAttachment interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IAttachment_VTablePtr)]
IAttachment = POINTER(IAttachment_struct)
# IService(3) : ReferenceCounted
class IService_VTable(Structure):
    "IService virtual method table"
IService_VTablePtr = POINTER(IService_VTable)
class IService_struct(Structure):
    "IService interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IService_VTablePtr)]
IService = POINTER(IService_struct)
# IProvider(4) : PluginBase
class IProvider_VTable(Structure):
    "IProvider virtual method table"
IProvider_VTablePtr = POINTER(IProvider_VTable)
class IProvider_struct(Structure):
    "IProvider interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IProvider_VTablePtr)]
IProvider = POINTER(IProvider_struct)
# IDtcStart(3) : Disposable
class IDtcStart_VTable(Structure):
    "IDtcStart virtual method table"
IDtcStart_VTablePtr = POINTER(IDtcStart_VTable)
class IDtcStart_struct(Structure):
    "IDtcStart interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IDtcStart_VTablePtr)]
IDtcStart = POINTER(IDtcStart_struct)
# IDtc(2) : Versioned
class IDtc_VTable(Structure):
    "IDtc virtual method table"
IDtc_VTablePtr = POINTER(IDtc_VTable)
class IDtc_struct(Structure):
    "IDtc interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IDtc_VTablePtr)]
IDtc = POINTER(IDtc_struct)
# IAuth(4) : PluginBase
# IWriter(2) : Versioned
# IServerBlock(2) : Versioned
# IClientBlock(4) : ReferenceCounted
# IServer(6) : Auth
# IClient(5) : Auth
# IUserField(2) : Versioned
# ICharUserField(3) : IUserField
# IIntUserField(3) : IUserField
# IUser(2) : Versioned
# IListUsers(2) : Versioned
# ILogonInfo(2) : Versioned
# IManagement(4) : PluginBase
# IAuthBlock(2) : Versioned
# IWireCryptPlugin(4) : PluginBase
# ICryptKeyCallback(2) : Versioned
class ICryptKeyCallback_VTable(Structure):
    "ICryptKeyCallback virtual method table"
ICryptKeyCallback_VTablePtr = POINTER(ICryptKeyCallback_VTable)
class ICryptKeyCallback_struct(Structure):
    "ICryptKeyCallback interface"
    _fields_ = [('dummy', c_void_p), ('vtable', ICryptKeyCallback_VTablePtr)]
ICryptKeyCallback = POINTER(ICryptKeyCallback_struct)
# IKeyHolderPlugin(5) : PluginBase
# IDbCryptInfo(3) : ReferenceCounted
# IDbCryptPlugin(5) : PluginBase
# IExternalContext(2) : Versioned
# IExternalResultSet(3) : Disposable
# IExternalFunction(3) : Disposable
# IExternalProcedure(3) : Disposable
# IExternalTrigger(3) : Disposable
# IRoutineMetadata(2) : Versioned
# IExternalEngine(4) : PluginBase
# ITimer(3) : ReferenceCounted
class ITimer_VTable(Structure):
    "ITimer virtual method table"
ITimer_VTablePtr = POINTER(ITimer_VTable)
class ITimer_struct(Structure):
    "ITimer interface"
    _fields_ = [('dummy', c_void_p), ('vtable', ITimer_VTablePtr)]
ITimer = POINTER(ITimer_struct)
# ITimerControl(2) : Versioned
class ITimerControl_VTable(Structure):
    "ITimerControl virtual method table"
ITimerControl_VTablePtr = POINTER(ITimerControl_VTable)
class ITimerControl_struct(Structure):
    "ITimerControl interface"
    _fields_ = [('dummy', c_void_p), ('vtable', ITimerControl_VTablePtr)]
ITimerControl = POINTER(ITimerControl_struct)
# IVersionCallback(2) : Versioned
class IVersionCallback_VTable(Structure):
    "IVersionCallback virtual method table"
IVersionCallback_VTablePtr = POINTER(IVersionCallback_VTable)
class IVersionCallback_struct(Structure):
    "IVersionCallback interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IVersionCallback_VTablePtr)]
IVersionCallback = POINTER(IVersionCallback_struct)
# IUtil(2) : Versioned
class IUtil_VTable(Structure):
    "IUtil virtual method table"
IUtil_VTablePtr = POINTER(IUtil_VTable)
class IUtil_struct(Structure):
    "IUtil interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IUtil_VTablePtr)]
IUtil = POINTER(IUtil_struct)
# IOffsetsCallback(2) : Versioned
class IOffsetsCallback_VTable(Structure):
    "IOffsetsCallback virtual method table"
IOffsetsCallback_VTablePtr = POINTER(IOffsetsCallback_VTable)
class IOffsetsCallback_struct(Structure):
    "IOffsetsCallback interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IOffsetsCallback_VTablePtr)]
IOffsetsCallback = POINTER(IOffsetsCallback_struct)
# IXpbBuilder(3) : Disposable
class IXpbBuilder_VTable(Structure):
    "IXpbBuilder virtual method table"
IXpbBuilder_VTablePtr = POINTER(IXpbBuilder_VTable)
class IXpbBuilder_struct(Structure):
    "IXpbBuilder interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IXpbBuilder_VTablePtr)]
IXpbBuilder = POINTER(IXpbBuilder_struct)
# ITraceConnection(2) : Versioned
# ITraceDatabaseConnection(3) : TraceConnection
# ITraceTransaction(3) : Versioned
# ITraceParams(3) : Versioned
# ITraceStatement(2) : Versioned
# ITraceSQLStatement(3) : TraceStatement
# ITraceBLRStatement(3) : TraceStatement
# ITraceDYNRequest(2) : Versioned
# ITraceContextVariable(2) : Versioned
# ITraceProcedure(2) : Versioned
# ITraceFunction(2) : Versioned
# ITraceTrigger(2) : Versioned
# ITraceServiceConnection(3) : TraceConnection
# ITraceStatusVector(2) : Versioned
# ITraceSweepInfo(2) : Versioned
# ITraceLogWriter(4) : ReferenceCounted
# ITraceInitInfo(2) : Versioned
# ITracePlugin(3) : ReferenceCounted
# ITraceFactory(4) : PluginBase
# IUdrFunctionFactory(3) : Disposable
# IUdrProcedureFactory(3) : Disposable
# IUdrTriggerFactory(3) : Disposable
# IUdrPlugin(2) : Versioned
# >>> Firebird 4
# IDecFloat16(2) : Versioned
class IDecFloat16_VTable(Structure):
    "IDecFloat16 virtual method table"
IDecFloat16_VTablePtr = POINTER(IDecFloat16_VTable)
class IDecFloat16_struct(Structure):
    "IDecFloat16 interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IDecFloat16_VTablePtr)]
IDecFloat16 = POINTER(IDecFloat16_struct)
# IDecFloat34(2) : Versioned
class IDecFloat34_VTable(Structure):
    "IDecFloat34 virtual method table"
IDecFloat34_VTablePtr = POINTER(IDecFloat34_VTable)
class IDecFloat34_struct(Structure):
    "IDecFloat34 interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IDecFloat34_VTablePtr)]
IDecFloat34 = POINTER(IDecFloat34_struct)
# IInt128(2) : Versioned
class IInt128_VTable(Structure):
    "IInt128 virtual method table"
IInt128_VTablePtr = POINTER(IInt128_VTable)
class IInt128_struct(Structure):
    "IInt128 interface"
    _fields_ = [('dummy', c_void_p), ('vtable', IInt128_VTablePtr)]
IInt128 = POINTER(IInt128_struct)
# IReplicatedRecord(2) : Versioned
# IReplicatedBlob(2) : Versioned
# IReplicatedTransaction(3) : Disposable
# IReplicatedSession(3) : Disposable

# ====================
# Interfaces - Methods
# ====================
#
# IReferenceCounted(2)
# --------------------
# procedure addRef(this: IReferenceCounted)
IReferenceCounted_addRef = CFUNCTYPE(None, IReferenceCounted)
# function release(this: IReferenceCounted): Integer
IReferenceCounted_release = CFUNCTYPE(c_int, IReferenceCounted)
#
# IDisposable(2)
# --------------
# procedure dispose(this: IDisposable)
IDisposable_dispose = CFUNCTYPE(None, IDisposable)
#
# IStatus(3) : Disposable
# -----------------------
# procedure init(this: IStatus)
IStatus_init = CFUNCTYPE(None, IStatus)
# function getState(this: IStatus): Cardinal
IStatus_getState = CFUNCTYPE(Cardinal, IStatus)
# procedure setErrors2(this: IStatus; length: Cardinal; value: NativeIntPtr)
IStatus_setErrors2 = CFUNCTYPE(None, IStatus, Cardinal, NativeIntPtr)
# procedure setWarnings2(this: IStatus; length: Cardinal; value: NativeIntPtr)
IStatus_setWarnings2 = CFUNCTYPE(None, IStatus, Cardinal, NativeIntPtr)
# procedure setErrors(this: IStatus; value: NativeIntPtr)
IStatus_setErrors = CFUNCTYPE(None, IStatus, NativeIntPtr)
# procedure setWarnings(this: IStatus; value: NativeIntPtr)
IStatus_setWarnings = CFUNCTYPE(None, IStatus, NativeIntPtr)
# function getErrors(this: IStatus): NativeIntPtr
IStatus_getErrors = CFUNCTYPE(NativeIntPtr, IStatus)
# function getWarnings(this: IStatus): NativeIntPtr
IStatus_getWarnings = CFUNCTYPE(NativeIntPtr, IStatus)
# function clone(this: IStatus): IStatus
IStatus_clone = CFUNCTYPE(IStatus, IStatus)
#
# IMaster(2) : Versioned
# ----------------------
# function getStatus(this: IMaster): IStatus
IMaster_getStatus = CFUNCTYPE(IStatus, IMaster)
# function getDispatcher(this: IMaster): IProvider
IMaster_getDispatcher = CFUNCTYPE(IProvider, IMaster)
# function getPluginManager(this: IMaster): IPluginManager
IMaster_getPluginManager = CFUNCTYPE(IPluginManager, IMaster)
# function getTimerControl(this: IMaster): ITimerControl
IMaster_getTimerControl = CFUNCTYPE(ITimerControl, IMaster)
# function getDtc(this: IMaster): IDtc
IMaster_getDtc = CFUNCTYPE(IDtc, IMaster)
# function registerAttachment(this: IMaster; provider: IProvider; attachment: IAttachment): IAttachment
IMaster_registerAttachment = CFUNCTYPE(IAttachment, IMaster, IProvider, IAttachment)
# function registerTransaction(this: IMaster; attachment: IAttachment; transaction: ITransaction): ITransaction
IMaster_registerTransaction = CFUNCTYPE(ITransaction, IMaster, IAttachment, ITransaction)
# function getMetadataBuilder(this: IMaster; status: IStatus; fieldCount: Cardinal): IMetadataBuilder
IMaster_getMetadataBuilder = CFUNCTYPE(IMetadataBuilder, IMaster, IStatus, c_uint)
# function serverMode(this: IMaster; mode: Integer): Integer
IMaster_serverMode = CFUNCTYPE(c_int, IMaster, c_int)
# function getUtilInterface(this: IMaster): IUtil
IMaster_getUtilInterface = CFUNCTYPE(IUtil, IMaster)
# function getConfigManager(this: IMaster): IConfigManager
IMaster_getConfigManager = CFUNCTYPE(IConfigManager, IMaster)
# function getProcessExiting(this: IMaster): Boolean
IMaster_getProcessExiting = CFUNCTYPE(c_bool, IMaster)
#
# IPluginBase(3) : ReferenceCounted
# ---------------------------------
# procedure setOwner(this: IPluginBase; r: IReferenceCounted)
IPluginBase_setOwner = CFUNCTYPE(None, IPluginBase, IReferenceCounted)
# function getOwner(this: IPluginBase): IReferenceCounted
IPluginBase_getOwner = CFUNCTYPE(IReferenceCounted, IPluginBase)
#
# IConfigEntry(3) : ReferenceCounted
# ----------------------------------
# function getName(this: IConfigEntry): PAnsiChar
IConfigEntry_getName = CFUNCTYPE(c_char_p, IConfigEntry)
# function getValue(this: IConfigEntry): PAnsiChar
IConfigEntry_getValue = CFUNCTYPE(c_char_p, IConfigEntry)
# function getIntValue(this: IConfigEntry): Int64
IConfigEntry_getIntValue = CFUNCTYPE(Int64, IConfigEntry)
# function getBoolValue(this: IConfigEntry): Boolean
IConfigEntry_getBoolValue = CFUNCTYPE(c_bool, IConfigEntry)
# function getSubConfig(this: IConfigEntry; status: IStatus): IConfig
IConfigEntry_getSubConfig = CFUNCTYPE(IConfig, IConfigEntry, IStatus)
#
# IConfig(3) : ReferenceCounted
# -----------------------------
# function find(this: IConfig; status: IStatus; name: PAnsiChar): IConfigEntry
IConfig_find = CFUNCTYPE(IConfigEntry, IConfig, IStatus, c_char_p)
# function findValue(this: IConfig; status: IStatus; name: PAnsiChar; value: PAnsiChar): IConfigEntry
IConfig_findValue = CFUNCTYPE(IConfigEntry, IConfig, IStatus, c_char_p, c_char_p)
# function findPos(this: IConfig; status: IStatus; name: PAnsiChar; pos: Cardinal): IConfigEntry
IConfig_findPos = CFUNCTYPE(IConfigEntry, IConfig, IStatus, c_char_p, Cardinal)
#
# IFirebirdConf(3) : ReferenceCounted
# -----------------------------------
# function getKey(this: IFirebirdConf; name: PAnsiChar): Cardinal
IFirebirdConf_getKey = CFUNCTYPE(Cardinal, IFirebirdConf, c_char_p)
# function asInteger(this: IFirebirdConf; key: Cardinal): Int64
IFirebirdConf_asInteger = CFUNCTYPE(Int64, IFirebirdConf, Cardinal)
# function asString(this: IFirebirdConf; key: Cardinal): PAnsiChar
IFirebirdConf_asString = CFUNCTYPE(c_char_p, IFirebirdConf, Cardinal)
# function asBoolean(this: IFirebirdConf; key: Cardinal): Boolean
IFirebirdConf_asBoolean = CFUNCTYPE(c_bool, IFirebirdConf, Cardinal)
# >>> Firebird 4
# IFirebirdConf(4)
# function getVersion(this: IFirebirdConf; status: IStatus): Cardinal
IFirebirdConf_getVersion = CFUNCTYPE(Cardinal, IFirebirdConf, IStatus)
#
# IConfigManager(2) : Versioned
# -----------------------------
# function getDirectory(this: IConfigManager; code: Cardinal): PAnsiChar
IConfigManager_getDirectory = CFUNCTYPE(c_char_p, IConfigManager, Cardinal)
# function getFirebirdConf(this: IConfigManager): IFirebirdConf
IConfigManager_getFirebirdConf = CFUNCTYPE(IFirebirdConf, IConfigManager)
# function getDatabaseConf(this: IConfigManager; dbName: PAnsiChar): IFirebirdConf
IConfigManager_getDatabaseConf = CFUNCTYPE(IFirebirdConf, IConfigManager, c_char_p)
# function getPluginConfig(this: IConfigManager; configuredPlugin: PAnsiChar): IConfig
IConfigManager_getPluginConfig = CFUNCTYPE(IConfig, IConfigManager, c_char_p)
# function getInstallDirectory(this: IConfigManager): PAnsiChar
IConfigManager_getInstallDirectory = CFUNCTYPE(c_char_p, IConfigManager)
# function getRootDirectory(this: IConfigManager): PAnsiChar
IConfigManager_getRootDirectory = CFUNCTYPE(c_char_p, IConfigManager)
# >>> Firebird 4
# IConfigManager(3) : IConfigManager(2)
# function getDefaultSecurityDb(this: IConfigManager): PAnsiChar
IConfigManager_getDefaultSecurityDb = CFUNCTYPE(c_char_p, IConfigManager)
#
# IEventCallback(3) : ReferenceCounted
# ------------------------------------
# procedure eventCallbackFunction(this: IEventCallback; length: Cardinal; events: BytePtr)
IEventCallback_eventCallbackFunction = CFUNCTYPE(None, IEventCallback, Cardinal, BytePtr)
#
# IBlob(3) : ReferenceCounted
# ---------------------------
# procedure getInfo(this: IBlob; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IBlob_getInfo = CFUNCTYPE(None, IBlob, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# function getSegment(this: IBlob; status: IStatus; bufferLength: Cardinal; buffer: Pointer; segmentLength: CardinalPtr): Integer
IBlob_getSegment = CFUNCTYPE(c_int, IBlob, IStatus, Cardinal, c_void_p, CardinalPtr)
# procedure putSegment(this: IBlob; status: IStatus; length: Cardinal; buffer: Pointer)
IBlob_putSegment = CFUNCTYPE(None, IBlob, IStatus, Cardinal, c_void_p)
# procedure cancel(this: IBlob; status: IStatus)
IBlob_cancel = CFUNCTYPE(None, IBlob, IStatus)
# procedure close(this: IBlob; status: IStatus)
IBlob_close = CFUNCTYPE(None, IBlob, IStatus)
# function seek(this: IBlob; status: IStatus; mode: Integer; offset: Integer): Integer
IBlob_seek = CFUNCTYPE(c_int, IBlob, IStatus, c_int, c_int)
#
# ITransaction(3) : ReferenceCounted
# ----------------------------------
# procedure getInfo(this: ITransaction; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
ITransaction_getInfo = CFUNCTYPE(None, ITransaction, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# procedure prepare(this: ITransaction; status: IStatus; msgLength: Cardinal; message: BytePtr)
ITransaction_prepare = CFUNCTYPE(None, ITransaction, IStatus, Cardinal, BytePtr)
# procedure commit(this: ITransaction; status: IStatus)
ITransaction_commit = CFUNCTYPE(None, ITransaction, IStatus)
# procedure commitRetaining(this: ITransaction; status: IStatus)
ITransaction_commitRetaining = CFUNCTYPE(None, ITransaction, IStatus)
# procedure rollback(this: ITransaction; status: IStatus)
ITransaction_rollback = CFUNCTYPE(None, ITransaction, IStatus)
# procedure rollbackRetaining(this: ITransaction; status: IStatus)
ITransaction_rollbackRetaining = CFUNCTYPE(None, ITransaction, IStatus)
# procedure disconnect(this: ITransaction; status: IStatus)
ITransaction_disconnect = CFUNCTYPE(None, ITransaction, IStatus)
# function join(this: ITransaction; status: IStatus; transaction: ITransaction): ITransaction
ITransaction_join = CFUNCTYPE(ITransaction, ITransaction, IStatus, ITransaction)
# function validate(this: ITransaction; status: IStatus; attachment: IAttachment): ITransaction
ITransaction_validate = CFUNCTYPE(ITransaction, ITransaction, IStatus, IAttachment)
# function enterDtc(this: ITransaction; status: IStatus): ITransaction
ITransaction_enterDtc = CFUNCTYPE(ITransaction, ITransaction, IStatus)
#
# IMessageMetadata(3) : ReferenceCounted
# --------------------------------------
# function getCount(this: IMessageMetadata; status: IStatus): Cardinal
IMessageMetadata_getCount = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus)
# function getField(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getField = CFUNCTYPE(c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getRelation(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getRelation = CFUNCTYPE(c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getOwner(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getOwner = CFUNCTYPE(c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getAlias(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getAlias = CFUNCTYPE(c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getType(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getType = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function isNullable(this: IMessageMetadata; status: IStatus; index: Cardinal): Boolean
IMessageMetadata_isNullable = CFUNCTYPE(c_bool, IMessageMetadata, IStatus, Cardinal)
# function getSubType(this: IMessageMetadata; status: IStatus; index: Cardinal): Integer
IMessageMetadata_getSubType = CFUNCTYPE(c_int, IMessageMetadata, IStatus, Cardinal)
# function getLength(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getLength = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getScale(this: IMessageMetadata; status: IStatus; index: Cardinal): Integer
IMessageMetadata_getScale = CFUNCTYPE(c_int, IMessageMetadata, IStatus, Cardinal)
# function getCharSet(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getCharSet = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getOffset(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getOffset = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getNullOffset(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getNullOffset = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getBuilder(this: IMessageMetadata; status: IStatus): IMetadataBuilder
IMessageMetadata_getBuilder = CFUNCTYPE(IMetadataBuilder, IMessageMetadata, IStatus)
# function getMessageLength(this: IMessageMetadata; status: IStatus): Cardinal
IMessageMetadata_getMessageLength = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus)
# >>> Firebird 4
# IMessageMetadata(4) : IMessageMetadata(3)
# function getAlignment(this: IMessageMetadata; status: IStatus): Cardinal
IMessageMetadata_getAlignment = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus)
# function getAlignedLength(this: IMessageMetadata; status: IStatus): Cardinal
IMessageMetadata_getAlignedLength = CFUNCTYPE(Cardinal, IMessageMetadata, IStatus)
#
# IMetadataBuilder(3) : ReferenceCounted
# --------------------------------------
# procedure setType(this: IMetadataBuilder; status: IStatus; index: Cardinal; type_: Cardinal)
IMetadataBuilder_setType = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, Cardinal)
# procedure setSubType(this: IMetadataBuilder; status: IStatus; index: Cardinal; subType: Integer)
IMetadataBuilder_setSubType = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c_int)
# procedure setLength(this: IMetadataBuilder; status: IStatus; index: Cardinal; length: Cardinal)
IMetadataBuilder_setLength = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, Cardinal)
# procedure setCharSet(this: IMetadataBuilder; status: IStatus; index: Cardinal; charSet: Cardinal)
IMetadataBuilder_setCharSet = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, Cardinal)
# procedure setScale(this: IMetadataBuilder; status: IStatus; index: Cardinal; scale: Integer)
IMetadataBuilder_setScale = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c_int)
# procedure truncate(this: IMetadataBuilder; status: IStatus; count: Cardinal)
IMetadataBuilder_truncate = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal)
# procedure moveNameToIndex(this: IMetadataBuilder; status: IStatus; name: PAnsiChar; index: Cardinal)
IMetadataBuilder_moveNameToIndex = CFUNCTYPE(None, IMetadataBuilder, IStatus, c_char_p, Cardinal)
# procedure remove(this: IMetadataBuilder; status: IStatus; index: Cardinal)
IMetadataBuilder_remove = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal)
# function addField(this: IMetadataBuilder; status: IStatus): Cardinal
IMetadataBuilder_addField = CFUNCTYPE(Cardinal, IMetadataBuilder, IStatus)
# function getMetadata(this: IMetadataBuilder; status: IStatus): IMessageMetadata
IMetadataBuilder_getMetadata = CFUNCTYPE(IMessageMetadata, IMetadataBuilder, IStatus)
# >>> Firebird 4
# IMetadataBuilder(4) : IMetadataBuilder(3)
# procedure setField(this: IMetadataBuilder; status: IStatus; index: Cardinal; field: PAnsiChar)
IMetadataBuilder_setField = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c_char_p)
# procedure setRelation(this: IMetadataBuilder; status: IStatus; index: Cardinal; relation: PAnsiChar)
IMetadataBuilder_setRelation = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c_char_p)
# procedure setOwner(this: IMetadataBuilder; status: IStatus; index: Cardinal; owner: PAnsiChar)
IMetadataBuilder_setOwner = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c_char_p)
# procedure setAlias(this: IMetadataBuilder; status: IStatus; index: Cardinal; alias: PAnsiChar)
IMetadataBuilder_setAlias = CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c_char_p)
#
# IResultSet(3) : ReferenceCounted
# --------------------------------
# function fetchNext(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchNext = CFUNCTYPE(c_int, IResultSet, IStatus, c_void_p)
# function fetchPrior(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchPrior = CFUNCTYPE(c_int, IResultSet, IStatus, c_void_p)
# function fetchFirst(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchFirst = CFUNCTYPE(c_int, IResultSet, IStatus, c_void_p)
# function fetchLast(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchLast = CFUNCTYPE(c_int, IResultSet, IStatus, c_void_p)
# function fetchAbsolute(this: IResultSet; status: IStatus; position: Integer; message: Pointer): Integer
IResultSet_fetchAbsolute = CFUNCTYPE(c_int, IResultSet, IStatus, c_int, c_void_p)
# function fetchRelative(this: IResultSet; status: IStatus; offset: Integer; message: Pointer): Integer
IResultSet_fetchRelative = CFUNCTYPE(c_int, IResultSet, IStatus, c_int, c_void_p)
# function isEof(this: IResultSet; status: IStatus): Boolean
IResultSet_isEof = CFUNCTYPE(c_bool, IResultSet, IStatus)
# function isBof(this: IResultSet; status: IStatus): Boolean
IResultSet_isBof = CFUNCTYPE(c_bool, IResultSet, IStatus)
# function getMetadata(this: IResultSet; status: IStatus): IMessageMetadata
IResultSet_getMetadata = CFUNCTYPE(IMessageMetadata, IResultSet, IStatus)
# procedure close(this: IResultSet; status: IStatus)
IResultSet_close = CFUNCTYPE(None, IResultSet, IStatus)
# procedure setDelayedOutputFormat(this: IResultSet; status: IStatus; format: IMessageMetadata)
IResultSet_setDelayedOutputFormat = CFUNCTYPE(None, IResultSet, IStatus, IMessageMetadata)
#
# IStatement(3) : ReferenceCounted
# --------------------------------
# procedure getInfo(this: IStatement; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IStatement_getInfo = CFUNCTYPE(None, IStatement, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# function getType(this: IStatement; status: IStatus): Cardinal
IStatement_getType = CFUNCTYPE(Cardinal, IStatement, IStatus)
# function getPlan(this: IStatement; status: IStatus; detailed: Boolean): PAnsiChar
IStatement_getPlan = CFUNCTYPE(c_char_p, IStatement, IStatus, c_bool)
# function getAffectedRecords(this: IStatement; status: IStatus): QWord
IStatement_getAffectedRecords = CFUNCTYPE(QWord, IStatement, IStatus)
# function getInputMetadata(this: IStatement; status: IStatus): IMessageMetadata
IStatement_getInputMetadata = CFUNCTYPE(IMessageMetadata, IStatement, IStatus)
# function getOutputMetadata(this: IStatement; status: IStatus): IMessageMetadata
IStatement_getOutputMetadata = CFUNCTYPE(IMessageMetadata, IStatement, IStatus)
# function execute(this: IStatement; status: IStatus; transaction: ITransaction; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; outBuffer: Pointer): ITransaction
IStatement_execute = CFUNCTYPE(ITransaction, IStatement, IStatus, ITransaction, IMessageMetadata, c_void_p, IMessageMetadata, c_void_p)
# function openCursor(this: IStatement; status: IStatus; transaction: ITransaction; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; flags: Cardinal): IResultSet
IStatement_openCursor = CFUNCTYPE(IResultSet, IStatement, IStatus, ITransaction, IMessageMetadata, c_void_p, IMessageMetadata, Cardinal)
# procedure setCursorName(this: IStatement; status: IStatus; name: PAnsiChar)
IStatement_setCursorName = CFUNCTYPE(None, IStatement, IStatus, c_char_p)
# procedure free(this: IStatement; status: IStatus)
IStatement_free = CFUNCTYPE(None, IStatement, IStatus)
# function getFlags(this: IStatement; status: IStatus): Cardinal
IStatement_getFlags = CFUNCTYPE(Cardinal, IStatement, IStatus)
# >>> Firebird 4
# IStatement(4) : IStatement(3)
# function getTimeout(this: IStatement; status: IStatus): Cardinal
IStatement_getTimeout = CFUNCTYPE(Cardinal, IStatement, IStatus)
# procedure setTimeout(this: IStatement; status: IStatus; timeOut: Cardinal)
IStatement_setTimeout = CFUNCTYPE(None, IStatement, IStatus, Cardinal)
# function(this: IStatement; status: IStatus; inMetadata: IMessageMetadata; parLength: Cardinal; par: BytePtr): IBatch
IStatement_createBatch = CFUNCTYPE(IBatch, IStatement, IStatus, IMessageMetadata, Cardinal, BytePtr)
#
# IBatch(3) : ReferenceCounted
# ----------------------------
# procedure add(this: IBatch; status: IStatus; count: Cardinal; inBuffer: Pointer)
IBatch_add = CFUNCTYPE(None, IBatch, IStatus, Cardinal, c_void_p)
# procedure addBlob(this: IBatch; status: IStatus; length: Cardinal; inBuffer: Pointer; blobId: ISC_QUADPtr; parLength: Cardinal; par: BytePtr)
IBatch_addBlob = CFUNCTYPE(None, IBatch, IStatus, Cardinal, c_void_p, ISC_QUAD_PTR, Cardinal, BytePtr)
# procedure appendBlobData(this: IBatch; status: IStatus; length: Cardinal; inBuffer: Pointer)
IBatch_appendBlobData = CFUNCTYPE(None, IBatch, IStatus, Cardinal, c_void_p)
# procedure addBlobStream(this: IBatch; status: IStatus; length: Cardinal; inBuffer: Pointer)
IBatch_addBlobStream = CFUNCTYPE(None, IBatch, IStatus, Cardinal, c_void_p)
# procedure registerBlob(this: IBatch; status: IStatus; existingBlob: ISC_QUADPtr; blobId: ISC_QUADPtr)
IBatch_registerBlob = CFUNCTYPE(None, IBatch, IStatus, ISC_QUAD_PTR, ISC_QUAD_PTR)
# function execute(this: IBatch; status: IStatus; transaction: ITransaction): IBatchCompletionState
IBatch_execute = CFUNCTYPE(IBatchCompletionState, IBatch, IStatus, ITransaction)
# procedure cancel(this: IBatch; status: IStatus)
IBatch_cancel = CFUNCTYPE(None, IBatch, IStatus)
# function getBlobAlignment(this: IBatch; status: IStatus): Cardinal
IBatch_getBlobAlignment = CFUNCTYPE(Cardinal, IBatch, IStatus)
# function getMetadata(this: IBatch; status: IStatus): IMessageMetadata
IBatch_getMetadata = CFUNCTYPE(IMessageMetadata, IBatch, IStatus)
# procedure setDefaultBpb(this: IBatch; status: IStatus; parLength: Cardinal; par: BytePtr)
IBatch_setDefaultBpb = CFUNCTYPE(None, IBatch, IStatus, Cardinal, BytePtr)
#
# IBatchCompletionState(3) : Disposable
# -------------------------------------
# function getSize(this: IBatchCompletionState; status: IStatus): Cardinal
IBatchCompletionState_getSize = CFUNCTYPE(Cardinal, IBatchCompletionState, IStatus)
# function getState(this: IBatchCompletionState; status: IStatus; pos: Cardinal): Integer
IBatchCompletionState_getState = CFUNCTYPE(c_int, IBatchCompletionState, IStatus, Cardinal)
# function findError(this: IBatchCompletionState; status: IStatus; pos: Cardinal): Cardinal
IBatchCompletionState_findError = CFUNCTYPE(Cardinal, IBatchCompletionState, IStatus, Cardinal)
# procedure getStatus(this: IBatchCompletionState; status: IStatus; to_: IStatus; pos: Cardinal)
IBatchCompletionState_getStatus = CFUNCTYPE(None, IBatchCompletionState, IStatus, IStatus, Cardinal)
#
# IRequest(3) : ReferenceCounted
# ------------------------------
# procedure receive(this: IRequest; status: IStatus; level: Integer; msgType: Cardinal; length: Cardinal; message: Pointer)
IRequest_receive = CFUNCTYPE(None, IRequest, IStatus, c_int, Cardinal, Cardinal, c_void_p)
# procedure send(this: IRequest; status: IStatus; level: Integer; msgType: Cardinal; length: Cardinal; message: Pointer)
IRequest_send = CFUNCTYPE(None, IRequest, IStatus, c_int, Cardinal, Cardinal, c_void_p)
# procedure getInfo(this: IRequest; status: IStatus; level: Integer; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IRequest_getInfo = CFUNCTYPE(None, IRequest, IStatus, c_int, Cardinal, BytePtr, Cardinal, BytePtr)
# procedure start(this: IRequest; status: IStatus; tra: ITransaction; level: Integer)
IRequest_start = CFUNCTYPE(None, IRequest, IStatus, ITransaction, c_int)
# procedure startAndSend(this: IRequest; status: IStatus; tra: ITransaction; level: Integer; msgType: Cardinal; length: Cardinal; message: Pointer)
IRequest_startAndSend = CFUNCTYPE(None, IRequest, IStatus, ITransaction, c_int, Cardinal, Cardinal, c_void_p)
# procedure unwind(this: IRequest; status: IStatus; level: Integer)
IRequest_unwind = CFUNCTYPE(None, IRequest, IStatus, c_int)
# procedure free(this: IRequest; status: IStatus)
IRequest_free = CFUNCTYPE(None, IRequest, IStatus)
#
# IEvents(3) : ReferenceCounted
# -----------------------------
# procedure cancel(this: IEvents; status: IStatus)
IEvents_cancel = CFUNCTYPE(None, IEvents, IStatus)
#
# IAttachment(3) : ReferenceCounted
# ---------------------------------
# procedure getInfo(this: IAttachment; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IAttachment_getInfo = CFUNCTYPE(None, IAttachment, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# function startTransaction(this: IAttachment; status: IStatus; tpbLength: Cardinal; tpb: BytePtr): ITransaction
IAttachment_startTransaction = CFUNCTYPE(ITransaction, IAttachment, IStatus, Cardinal, BytePtr)
# function reconnectTransaction(this: IAttachment; status: IStatus; length: Cardinal; id: BytePtr): ITransaction
IAttachment_reconnectTransaction = CFUNCTYPE(ITransaction, IAttachment, IStatus, Cardinal, BytePtr)
# function compileRequest(this: IAttachment; status: IStatus; blrLength: Cardinal; blr: BytePtr): IRequest
IAttachment_compileRequest = CFUNCTYPE(IRequest, IAttachment, IStatus, Cardinal, BytePtr)
# procedure transactRequest(this: IAttachment; status: IStatus; transaction: ITransaction; blrLength: Cardinal; blr: BytePtr; inMsgLength: Cardinal; inMsg: BytePtr; outMsgLength: Cardinal; outMsg: BytePtr)
IAttachment_transactRequest = CFUNCTYPE(None, IAttachment, IStatus, ITransaction, Cardinal,
                                        BytePtr, Cardinal, BytePtr, Cardinal, BytePtr)
# function createBlob(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; bpbLength: Cardinal; bpb: BytePtr): IBlob
IAttachment_createBlob = CFUNCTYPE(IBlob, IAttachment, IStatus, ITransaction, ISC_QUAD_PTR, Cardinal, BytePtr)
# function openBlob(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; bpbLength: Cardinal; bpb: BytePtr): IBlob
IAttachment_openBlob = CFUNCTYPE(IBlob, IAttachment, IStatus, ITransaction, ISC_QUAD_PTR, Cardinal, BytePtr)
# function getSlice(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; sdlLength: Cardinal; sdl: BytePtr; paramLength: Cardinal; param: BytePtr; sliceLength: Integer; slice: BytePtr): Integer
IAttachment_getSlice = CFUNCTYPE(c_int, IAttachment, IStatus, ITransaction, ISC_QUAD_PTR,
                                 Cardinal, BytePtr, Cardinal, BytePtr, c_int, BytePtr)
# procedure putSlice(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; sdlLength: Cardinal; sdl: BytePtr; paramLength: Cardinal; param: BytePtr; sliceLength: Integer; slice: BytePtr)
IAttachment_putSlice = CFUNCTYPE(None, IAttachment, IStatus, ITransaction, ISC_QUAD_PTR,
                                 Cardinal, BytePtr, Cardinal, BytePtr, c_int, BytePtr)
# procedure executeDyn(this: IAttachment; status: IStatus; transaction: ITransaction; length: Cardinal; dyn: BytePtr)
IAttachment_executeDyn = CFUNCTYPE(None, IAttachment, IStatus, ITransaction, Cardinal, BytePtr)
# function prepare(this: IAttachment; status: IStatus; tra: ITransaction; stmtLength: Cardinal; sqlStmt: PAnsiChar; dialect: Cardinal; flags: Cardinal): IStatement
IAttachment_prepare = CFUNCTYPE(IStatement, IAttachment, IStatus, ITransaction,
                                Cardinal, c_char_p, Cardinal, Cardinal)
# function execute(this: IAttachment; status: IStatus; transaction: ITransaction; stmtLength: Cardinal; sqlStmt: PAnsiChar; dialect: Cardinal; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; outBuffer: Pointer): ITransaction
IAttachment_execute = CFUNCTYPE(ITransaction, IAttachment, IStatus, ITransaction,
                                Cardinal, c_char_p, Cardinal, IMessageMetadata,
                                c_void_p, IMessageMetadata, c_void_p)
# function openCursor(this: IAttachment; status: IStatus; transaction: ITransaction; stmtLength: Cardinal; sqlStmt: PAnsiChar; dialect: Cardinal; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; cursorName: PAnsiChar; cursorFlags: Cardinal): IResultSet
IAttachment_openCursor = CFUNCTYPE(IResultSet, IAttachment, IStatus, ITransaction,
                                   Cardinal, c_char_p, Cardinal, IMessageMetadata,
                                   c_void_p, IMessageMetadata, c_char_p, Cardinal)
# function queEvents(this: IAttachment; status: IStatus; callback: IEventCallback; length: Cardinal; events: BytePtr): IEvents
IAttachment_queEvents = CFUNCTYPE(IEvents, IAttachment, IStatus, IEventCallback, Cardinal, BytePtr)
# procedure cancelOperation(this: IAttachment; status: IStatus; option: Integer)
IAttachment_cancelOperation = CFUNCTYPE(None, IAttachment, IStatus, c_int)
# procedure ping(this: IAttachment; status: IStatus)
IAttachment_ping = CFUNCTYPE(None, IAttachment, IStatus)
# procedure detach(this: IAttachment; status: IStatus)
IAttachment_detach = CFUNCTYPE(None, IAttachment, IStatus)
# procedure dropDatabase(this: IAttachment; status: IStatus)
IAttachment_dropDatabase = CFUNCTYPE(None, IAttachment, IStatus)
# >>> Firebird 4
# IAttachment(4) : IAttachment(3)
# function getIdleTimeout(this: IAttachment; status: IStatus): Cardinal
IAttachment_getIdleTimeout = CFUNCTYPE(Cardinal, IAttachment, IStatus)
# procedure setIdleTimeout(this: IAttachment; status: IStatus; timeOut: Cardinal)
IAttachment_setIdleTimeout = CFUNCTYPE(None, IAttachment, IStatus, Cardinal)
# function getStatementTimeout(this: IAttachment; status: IStatus): Cardinal
IAttachment_getStatementTimeout = CFUNCTYPE(Cardinal, IAttachment, IStatus)
# procedure setStatementTimeout(this: IAttachment; status: IStatus; timeOut: Cardinal)
IAttachment_setStatementTimeout = CFUNCTYPE(None, IAttachment, IStatus, Cardinal)
# function createBatch(this: IAttachment; status: IStatus; transaction: ITransaction; stmtLength: Cardinal; sqlStmt: PAnsiChar; dialect: Cardinal; inMetadata: IMessageMetadata; parLength: Cardinal; par: BytePtr): IBatch
IAttachment_createBatch = CFUNCTYPE(IBatch, IAttachment, IStatus, ITransaction, Cardinal, c_char_p, Cardinal, IMessageMetadata, Cardinal, c_void_p)
# function createReplicator(this: IAttachment; status: IStatus): IReplicator
# NOT SURFACED IN DRIVER
#
# IService(3) : ReferenceCounted
# ------------------------------
# procedure detach(this: IService; status: IStatus)
IService_detach = CFUNCTYPE(None, IService, IStatus)
# procedure query(this: IService; status: IStatus; sendLength: Cardinal; sendItems: BytePtr; receiveLength: Cardinal; receiveItems: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IService_query = CFUNCTYPE(None, IService, IStatus, Cardinal, BytePtr, Cardinal,
                           BytePtr, Cardinal, BytePtr)
# procedure start(this: IService; status: IStatus; spbLength: Cardinal; spb: BytePtr)
IService_start = CFUNCTYPE(None, IService, IStatus, Cardinal, BytePtr)
#
# IProvider(4) : PluginBase
# -------------------------
# function attachDatabase(this: IProvider; status: IStatus; fileName: PAnsiChar; dpbLength: Cardinal; dpb: BytePtr): IAttachment
IProvider_attachDatabase = CFUNCTYPE(IAttachment, IProvider, IStatus, c_char_p, Cardinal, BytePtr)
# function createDatabase(this: IProvider; status: IStatus; fileName: PAnsiChar; dpbLength: Cardinal; dpb: BytePtr): IAttachment
IProvider_createDatabase = CFUNCTYPE(IAttachment, IProvider, IStatus, c_char_p, Cardinal, BytePtr)
# function attachServiceManager(this: IProvider; status: IStatus; service: PAnsiChar; spbLength: Cardinal; spb: BytePtr): IService
IProvider_attachServiceManager = CFUNCTYPE(IService, IProvider, IStatus, c_char_p, Cardinal, BytePtr)
# procedure shutdown(this: IProvider; status: IStatus; timeout: Cardinal; reason: Integer)
IProvider_shutdown = CFUNCTYPE(None, IProvider, IStatus, Cardinal, c_int)
# procedure setDbCryptCallback(this: IProvider; status: IStatus; cryptCallback: ICryptKeyCallback)
IProvider_setDbCryptCallback = CFUNCTYPE(None, IProvider, IStatus, ICryptKeyCallback)
#
# IDtcStart(3) : Disposable
# -------------------------
# procedure addAttachment(this: IDtcStart; status: IStatus; att: IAttachment)
IDtcStart_addAttachment = CFUNCTYPE(None, IDtcStart, IStatus, IAttachment)
# procedure addWithTpb(this: IDtcStart; status: IStatus; att: IAttachment; length: Cardinal; tpb: BytePtr)
IDtcStart_addWithTpb = CFUNCTYPE(None, IDtcStart, IStatus, IAttachment, Cardinal, BytePtr)
# function start(this: IDtcStart; status: IStatus): ITransaction
IDtcStart_start = CFUNCTYPE(ITransaction, IDtcStart, IStatus)
#
# IDtc(2) : Versioned
# -------------------
# function join(this: IDtc; status: IStatus; one: ITransaction; two: ITransaction): ITransaction
IDtc_join = CFUNCTYPE(ITransaction, IDtc, IStatus, ITransaction, ITransaction)
# function startBuilder(this: IDtc; status: IStatus): IDtcStart
IDtc_startBuilder = CFUNCTYPE(IDtcStart, IDtc, IStatus)
#
# ICryptKeyCallback(2) : Versioned
# --------------------------------
# function callback(this: ICryptKeyCallback; dataLength: Cardinal; data: Pointer; bufferLength: Cardinal; buffer: Pointer): Cardinal
ICryptKeyCallback_callback = CFUNCTYPE(Cardinal, ICryptKeyCallback, Cardinal, c_void_p, Cardinal, c_void_p)
#
# ITimer(3) : ReferenceCounted
# ----------------------------
# procedure handler(this: ITimer)
ITimer_handler = CFUNCTYPE(None, ITimer)
#
# ITimerControl(2) : Versioned
# ----------------------------
# procedure start(this: ITimerControl; status: IStatus; timer: ITimer; microSeconds: QWord)
ITimerControl_start = CFUNCTYPE(None, ITimerControl, IStatus, ITimer, QWord)
# procedure stop(this: ITimerControl; status: IStatus; timer: ITimer)
ITimerControl_stop = CFUNCTYPE(None, ITimerControl, IStatus, ITimer)
#
# IVersionCallback(2) : Versioned
# -------------------------------
# procedure callback(this: IVersionCallback; status: IStatus; text: PAnsiChar)
IVersionCallback_callback = CFUNCTYPE(None, IVersionCallback, IStatus, c_char_p)
#
# IUtil(2) : Versioned
# --------------------
# procedure getFbVersion(this: IUtil; status: IStatus; att: IAttachment; callback: IVersionCallback)
IUtil_getFbVersion = CFUNCTYPE(None, IUtil, IStatus, IAttachment, IVersionCallback)
# procedure loadBlob(this: IUtil; status: IStatus; blobId: ISC_QUADPtr; att: IAttachment; tra: ITransaction; file_: PAnsiChar; txt: Boolean)
IUtil_loadBlob = CFUNCTYPE(None, IUtil, IStatus, ISC_QUAD_PTR, IAttachment, ITransaction,
                           c_char_p, c_bool)
# procedure dumpBlob(this: IUtil; status: IStatus; blobId: ISC_QUADPtr; att: IAttachment; tra: ITransaction; file_: PAnsiChar; txt: Boolean)
IUtil_dumpBlob = CFUNCTYPE(None, IUtil, IStatus, ISC_QUAD_PTR, IAttachment, ITransaction,
                           c_char_p, c_bool)
# procedure getPerfCounters(this: IUtil; status: IStatus; att: IAttachment; countersSet: PAnsiChar; counters: Int64Ptr)
IUtil_getPerfCounters = CFUNCTYPE(None, IUtil, IStatus, IAttachment, c_char_p, Int64Ptr)
# function executeCreateDatabase(this: IUtil; status: IStatus; stmtLength: Cardinal; creatDBstatement: PAnsiChar; dialect: Cardinal; stmtIsCreateDb: BooleanPtr): IAttachment
IUtil_executeCreateDatabase = CFUNCTYPE(IAttachment, IUtil, IStatus, Cardinal, c_char_p, Cardinal, BooleanPtr)
# procedure decodeDate(this: IUtil; date: ISC_DATE; year: CardinalPtr; month: CardinalPtr; day: CardinalPtr)
IUtil_decodeDate = CFUNCTYPE(None, IUtil, ISC_DATE, CardinalPtr, CardinalPtr, CardinalPtr)
# procedure decodeTime(this: IUtil; time: ISC_TIME; hours: CardinalPtr; minutes: CardinalPtr; seconds: CardinalPtr; fractions: CardinalPtr)
IUtil_decodeTime = CFUNCTYPE(None, IUtil, ISC_TIME, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr)
# function encodeDate(this: IUtil; year: Cardinal; month: Cardinal; day: Cardinal): ISC_DATE
IUtil_encodeDate = CFUNCTYPE(ISC_DATE, IUtil, Cardinal, Cardinal, Cardinal)
# function encodeTime(this: IUtil; hours: Cardinal; minutes: Cardinal; seconds: Cardinal; fractions: Cardinal): ISC_TIME
IUtil_encodeTime = CFUNCTYPE(ISC_TIME, IUtil, Cardinal, Cardinal, Cardinal, Cardinal)
# function formatStatus(this: IUtil; buffer: PAnsiChar; bufferSize: Cardinal; status: IStatus): Cardinal
IUtil_formatStatus = CFUNCTYPE(Cardinal, IUtil, c_char_p, Cardinal, IStatus)
# function getClientVersion(this: IUtil): Cardinal
IUtil_getClientVersion = CFUNCTYPE(Cardinal, IUtil)
# function getXpbBuilder(this: IUtil; status: IStatus; kind: Cardinal; buf: BytePtr; len: Cardinal): IXpbBuilder
IUtil_getXpbBuilder = CFUNCTYPE(IXpbBuilder, IUtil, IStatus, Cardinal, BytePtr, Cardinal)
# function setOffsets(this: IUtil; status: IStatus; metadata: IMessageMetadata; callback: IOffsetsCallback): Cardinal
IUtil_setOffsets = CFUNCTYPE(Cardinal, IUtil, IStatus, IMessageMetadata, IOffsetsCallback)
# >>> Firebird 4
# IUtil(4) : IUtil(2)
# function getDecFloat16(this: IUtil; status: IStatus): IDecFloat16
IUtil_getDecFloat16 = CFUNCTYPE(IDecFloat16, IUtil, IStatus)
# function getDecFloat34(this: IUtil; status: IStatus): IDecFloat34
IUtil_getDecFloat34 = CFUNCTYPE(IDecFloat34, IUtil, IStatus)
# procedure decodeTimeTz(this: IUtil; status: IStatus; timeTz: ISC_TIME_TZPtr; hours: CardinalPtr; minutes: CardinalPtr; seconds: CardinalPtr; fractions: CardinalPtr; timeZoneBufferLength: Cardinal; timeZoneBuffer: PAnsiChar)
IUtil_decodeTimeTz = CFUNCTYPE(None, IUtil, IStatus, ISC_TIME_TZ_PTR, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, Cardinal, c_char_p)
# procedure decodeTimeStampTz(this: IUtil; status: IStatus; timeStampTz: ISC_TIMESTAMP_TZPtr; year: CardinalPtr; month: CardinalPtr; day: CardinalPtr; hours: CardinalPtr; minutes: CardinalPtr; seconds: CardinalPtr; fractions: CardinalPtr; timeZoneBufferLength: Cardinal; timeZoneBuffer: PAnsiChar)
IUtil_decodeTimeStampTz = CFUNCTYPE(None, IUtil, IStatus, ISC_TIMESTAMP_TZ_PTR, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, Cardinal, c_char_p)
# procedure encodeTimeTz(this: IUtil; status: IStatus; timeTz: ISC_TIME_TZPtr; hours: Cardinal; minutes: Cardinal; seconds: Cardinal; fractions: Cardinal; timeZone: PAnsiChar)
IUtil_encodeTimeTz = CFUNCTYPE(None, IUtil, IStatus, ISC_TIME_TZ_PTR, Cardinal, Cardinal, Cardinal, Cardinal, c_char_p)
# procedure encodeTimeStampTz(this: IUtil; status: IStatus; timeStampTz: ISC_TIMESTAMP_TZPtr; year: Cardinal; month: Cardinal; day: Cardinal; hours: Cardinal; minutes: Cardinal; seconds: Cardinal; fractions: Cardinal; timeZone: PAnsiChar)
IUtil_encodeTimeStampTz = CFUNCTYPE(None, IUtil, IStatus, ISC_TIMESTAMP_TZ_PTR, Cardinal, Cardinal, Cardinal, Cardinal, Cardinal, Cardinal, Cardinal, c_char_p)
# function getInt128(this: IUtil; status: IStatus): IInt128
IUtil_getInt128 = CFUNCTYPE(IInt128, IUtil, IStatus)
# procedure decodeTimeTzEx(this: IUtil; status: IStatus; timeTz: ISC_TIME_TZ_EXPtr; hours: CardinalPtr; minutes: CardinalPtr; seconds: CardinalPtr; fractions: CardinalPtr; timeZoneBufferLength: Cardinal; timeZoneBuffer: PAnsiChar)
IUtil_decodeTimeTzEx = CFUNCTYPE(None, IUtil, IStatus, ISC_TIME_TZ_EX_PTR, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, Cardinal, c_char_p)
# procedure decodeTimeStampTzEx(this: IUtil; status: IStatus; timeStampTz: ISC_TIMESTAMP_TZ_EXPtr; year: CardinalPtr; month: CardinalPtr; day: CardinalPtr; hours: CardinalPtr; minutes: CardinalPtr; seconds: CardinalPtr; fractions: CardinalPtr; timeZoneBufferLength: Cardinal; timeZoneBuffer: PAnsiChar)
IUtil_decodeTimeStampTzEx = CFUNCTYPE(None, IUtil, IStatus, ISC_TIMESTAMP_TZ_EX_PTR, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr, Cardinal, c_char_p)
#
# IOffsetsCallback(2) : Versioned
# -------------------------------
# procedure setOffset(this: IOffsetsCallback; status: IStatus; index: Cardinal; offset: Cardinal; nullOffset: Cardinal)
IOffsetsCallback_setOffset = CFUNCTYPE(None, IOffsetsCallback, IStatus, Cardinal, Cardinal, Cardinal)
#
# IXpbBuilder(3) : Disposable
# ---------------------------
# procedure clear(this: IXpbBuilder; status: IStatus)
IXpbBuilder_clear = CFUNCTYPE(None, IXpbBuilder, IStatus)
# procedure removeCurrent(this: IXpbBuilder; status: IStatus)
IXpbBuilder_removeCurrent = CFUNCTYPE(None, IXpbBuilder, IStatus)
# procedure insertInt(this: IXpbBuilder; status: IStatus; tag: Byte; value: Integer)
IXpbBuilder_insertInt = CFUNCTYPE(None, IXpbBuilder, IStatus, c_byte, c_int)
# procedure insertBigInt(this: IXpbBuilder; status: IStatus; tag: Byte; value: Int64)
IXpbBuilder_insertBigInt = CFUNCTYPE(None, IXpbBuilder, IStatus, c_byte, Int64)
# procedure insertBytes(this: IXpbBuilder; status: IStatus; tag: Byte; bytes: Pointer; length: Cardinal)
IXpbBuilder_insertBytes = CFUNCTYPE(None, IXpbBuilder, IStatus, c_byte, c_void_p, Cardinal)
# procedure insertString(this: IXpbBuilder; status: IStatus; tag: Byte; str: PAnsiChar)
IXpbBuilder_insertString = CFUNCTYPE(None, IXpbBuilder, IStatus, c_byte, c_char_p)
# procedure insertTag(this: IXpbBuilder; status: IStatus; tag: Byte)
IXpbBuilder_insertTag = CFUNCTYPE(None, IXpbBuilder, IStatus, c_byte)
# function isEof(this: IXpbBuilder; status: IStatus): Boolean
IXpbBuilder_isEof = CFUNCTYPE(c_bool, IXpbBuilder, IStatus)
# procedure moveNext(this: IXpbBuilder; status: IStatus)
IXpbBuilder_moveNext = CFUNCTYPE(None, IXpbBuilder, IStatus)
# procedure rewind(this: IXpbBuilder; status: IStatus)
IXpbBuilder_rewind = CFUNCTYPE(None, IXpbBuilder, IStatus)
# function findFirst(this: IXpbBuilder; status: IStatus; tag: Byte): Boolean
IXpbBuilder_findFirst = CFUNCTYPE(c_bool, IXpbBuilder, IStatus, c_byte)
# function findNext(this: IXpbBuilder; status: IStatus): Boolean
IXpbBuilder_findNext = CFUNCTYPE(c_bool, IXpbBuilder, IStatus)
# function getTag(this: IXpbBuilder; status: IStatus): Byte
IXpbBuilder_getTag = CFUNCTYPE(c_byte, IXpbBuilder, IStatus)
# function getLength(this: IXpbBuilder; status: IStatus): Cardinal
IXpbBuilder_getLength = CFUNCTYPE(Cardinal, IXpbBuilder, IStatus)
# function getInt(this: IXpbBuilder; status: IStatus): Integer
IXpbBuilder_getInt = CFUNCTYPE(c_int, IXpbBuilder, IStatus)
# function getBigInt(this: IXpbBuilder; status: IStatus): Int64
IXpbBuilder_getBigInt = CFUNCTYPE(Int64, IXpbBuilder, IStatus)
# function getString(this: IXpbBuilder; status: IStatus): PAnsiChar
IXpbBuilder_getString = CFUNCTYPE(c_char_p, IXpbBuilder, IStatus)
# function getBytes(this: IXpbBuilder; status: IStatus): BytePtr
IXpbBuilder_getBytes = CFUNCTYPE(BytePtr, IXpbBuilder, IStatus)
# function getBufferLength(this: IXpbBuilder; status: IStatus): Cardinal
IXpbBuilder_getBufferLength = CFUNCTYPE(Cardinal, IXpbBuilder, IStatus)
# function getBuffer(this: IXpbBuilder; status: IStatus): BytePtr
IXpbBuilder_getBuffer = CFUNCTYPE(BytePtr, IXpbBuilder, IStatus)
#
# IDecFloat16(2) : Versioned
# --------------------------
# procedure toBcd(this: IDecFloat16; from: FB_DEC16Ptr; sign: IntegerPtr; bcd: BytePtr; exp: IntegerPtr)
IDecFloat16_toBcd = CFUNCTYPE(None, IDecFloat16, FB_DEC16Ptr, IntPtr, BytePtr, IntPtr)
# procedure toString(this: IDecFloat16; status: IStatus; from: FB_DEC16Ptr; bufferLength: Cardinal; buffer: PAnsiChar)
IDecFloat16_toString = CFUNCTYPE(None, IDecFloat16, IStatus, FB_DEC16Ptr, Cardinal, c_char_p)
# procedure fromBcd(this: IDecFloat16; sign: Integer; bcd: BytePtr; exp: Integer; to_: FB_DEC16Ptr)
IDecFloat16_fromBcd = CFUNCTYPE(None, IDecFloat16, c_int, BytePtr, c_int, FB_DEC16Ptr)
# procedure fromString(this: IDecFloat16; status: IStatus; from: PAnsiChar; to_: FB_DEC16Ptr)
IDecFloat16_fromString = CFUNCTYPE(None, IDecFloat16, IStatus, c_char_p, FB_DEC16Ptr)
#
# IDecFloat34(2) : Versioned
# --------------------------
# procedure toBcd(this: IDecFloat34; from: FB_DEC34Ptr; sign: IntegerPtr; bcd: BytePtr; exp: IntegerPtr)
IDecFloat34_toBcd = CFUNCTYPE(None, IDecFloat34, FB_DEC34Ptr, IntPtr, BytePtr, IntPtr)
# procedure toString(this: IDecFloat34; status: IStatus; from: FB_DEC34Ptr; bufferLength: Cardinal; buffer: PAnsiChar)
IDecFloat34_toString = CFUNCTYPE(None, IDecFloat34, IStatus, FB_DEC34Ptr, Cardinal, c_char_p)
# procedure fromBcd(this: IDecFloat34; sign: Integer; bcd: BytePtr; exp: Integer; to_: FB_DEC34Ptr)
IDecFloat34_fromBcd = CFUNCTYPE(None, IDecFloat34, c_int, BytePtr, c_int, FB_DEC34Ptr)
# procedure fromString(this: IDecFloat34; status: IStatus; from: PAnsiChar; to_: FB_DEC34Ptr)
IDecFloat34_fromString = CFUNCTYPE(None, IDecFloat34, IStatus, c_char_p, FB_DEC34Ptr)
#
# IInt128(2) : Versioned
# ----------------------
# procedure toString(this: IInt128; status: IStatus; from: FB_I128Ptr; scale: Integer; bufferLength: Cardinal; buffer: PAnsiChar)
IInt128_toString = CFUNCTYPE(None, IInt128, IStatus, FB_I128Ptr, c_int, Cardinal, c_char_p)
# procedure fromString(this: IInt128; status: IStatus; scale: Integer; from: PAnsiChar; to_: FB_I128Ptr)
IInt128_fromString = CFUNCTYPE(None, IInt128, IStatus, c_int, c_char_p, FB_I128Ptr)
#
# ------------------------------------------------------------------------------
# Interfaces - Data structures
# ------------------------------------------------------------------------------
# IVersioned(1)
IVersioned_VTable._fields_ = [('dummy', c_void_p), ('version', c_ulong)]
# IReferenceCounted(2)
IReferenceCounted_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release)]
# IDisposable(2)
IDisposable_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('dispose', IDisposable_dispose)]
# IStatus(3) : Disposable
IStatus_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('dispose', IDisposable_dispose),
    ('init', IStatus_init),
    ('getState', IStatus_getState),
    ('setErrors2', IStatus_setErrors2),
    ('setWarnings2', IStatus_setWarnings2),
    ('setErrors', IStatus_setErrors),
    ('setWarnings', IStatus_setWarnings),
    ('getErrors', IStatus_getErrors),
    ('getWarnings', IStatus_getWarnings),
    ('clone', IStatus_clone)]
# IMaster(2) : Versioned
IMaster_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('getStatus', IMaster_getStatus),
    ('getDispatcher', IMaster_getDispatcher),
    ('getPluginManager', IMaster_getPluginManager),
    ('getTimerControl', IMaster_getTimerControl),
    ('getDtc', IMaster_getDtc),
    ('registerAttachment', IMaster_registerAttachment),
    ('registerTransaction', IMaster_registerTransaction),
    ('getMetadataBuilder', IMaster_getMetadataBuilder),
    ('serverMode', IMaster_serverMode),
    ('getUtilInterface', IMaster_getUtilInterface),
    ('getConfigManager', IMaster_getConfigManager),
    ('getProcessExiting', IMaster_getProcessExiting)]
# IPluginBase(3) : ReferenceCounted
IPluginBase_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('setOwner', IPluginBase_setOwner),
    ('getOwner', IPluginBase_getOwner)]
# IPluginSet(3) : ReferenceCounted
# IConfigEntry(3) : ReferenceCounted
IConfigEntry_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('getName', IConfigEntry_getName),
    ('getValue', IConfigEntry_getValue),
    ('getIntValue', IConfigEntry_getIntValue),
    ('getBoolValue', IConfigEntry_getBoolValue),
    ('getSubConfig', IConfigEntry_getSubConfig)]
# IConfig(3) : ReferenceCounted
IConfig_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('find', IConfig_find),
    ('findValue', IConfig_findValue),
    ('findPos', IConfig_findPos)]
# >>> Firebird 4
# IFirebirdConf(4) : ReferenceCounted
IFirebirdConf_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('getKey', IFirebirdConf_getKey),
    ('asInteger', IFirebirdConf_asInteger),
    ('asString', IFirebirdConf_asString),
    ('asBoolean', IFirebirdConf_asBoolean),
    ('getVersion', IFirebirdConf_getVersion)]
# IPluginConfig(3) : ReferenceCounted
# IPluginFactory(2) : Versioned
# IPluginModule(3) : Versioned
# IPluginManager(2) : Versioned
# ICryptKey(2) : Versioned
# >>> Firebird 4
# IConfigManager(3) : Versioned
IConfigManager_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('getDirectory', IConfigManager_getDirectory),
    ('getFirebirdConf', IConfigManager_getFirebirdConf),
    ('getDatabaseConf', IConfigManager_getDatabaseConf),
    ('getPluginConfig', IConfigManager_getPluginConfig),
    ('getInstallDirectory', IConfigManager_getInstallDirectory),
    ('getRootDirectory', IConfigManager_getRootDirectory),
    ('getDefaultSecurityDb', IConfigManager_getDefaultSecurityDb)]
# IEventCallback(3) : ReferenceCounted
IEventCallback_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('eventCallbackFunction', IEventCallback_eventCallbackFunction)]
# IBlob(3) : ReferenceCounted
IBlob_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('getInfo', IBlob_getInfo),
    ('getSegment', IBlob_getSegment),
    ('putSegment', IBlob_putSegment),
    ('cancel', IBlob_cancel),
    ('close', IBlob_close),
    ('seek', IBlob_seek)]
# ITransaction(3) : ReferenceCounted
ITransaction_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('getInfo', ITransaction_getInfo),
    ('prepare', ITransaction_prepare),
    ('commit', ITransaction_commit),
    ('commitRetaining', ITransaction_commitRetaining),
    ('rollback', ITransaction_rollback),
    ('rollbackRetaining', ITransaction_rollbackRetaining),
    ('disconnect', ITransaction_disconnect),
    ('join', ITransaction_join),
    ('validate', ITransaction_validate),
    ('enterDtc', ITransaction_enterDtc)]
# >>> Firebird 4
# IMessageMetadata(4) : ReferenceCounted
IMessageMetadata_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('getCount', IMessageMetadata_getCount),
    ('getField', IMessageMetadata_getField),
    ('getRelation', IMessageMetadata_getRelation),
    ('getOwner', IMessageMetadata_getOwner),
    ('getAlias', IMessageMetadata_getAlias),
    ('getType', IMessageMetadata_getType),
    ('isNullable', IMessageMetadata_isNullable),
    ('getSubType', IMessageMetadata_getSubType),
    ('getLength', IMessageMetadata_getLength),
    ('getScale', IMessageMetadata_getScale),
    ('getCharSet', IMessageMetadata_getCharSet),
    ('getOffset', IMessageMetadata_getOffset),
    ('getNullOffset', IMessageMetadata_getNullOffset),
    ('getBuilder', IMessageMetadata_getBuilder),
    ('getMessageLength', IMessageMetadata_getMessageLength),
    ('getAlignment', IMessageMetadata_getAlignment),
    ('getAlignedLength', IMessageMetadata_getAlignedLength)]
# >>> Firebird 4
# IMetadataBuilder(4) : ReferenceCounted
IMetadataBuilder_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('setType', IMetadataBuilder_setType),
    ('setSubType', IMetadataBuilder_setSubType),
    ('setLength', IMetadataBuilder_setLength),
    ('setCharSet', IMetadataBuilder_setCharSet),
    ('setScale', IMetadataBuilder_setScale),
    ('truncate', IMetadataBuilder_truncate),
    ('moveNameToIndex', IMetadataBuilder_moveNameToIndex),
    ('remove', IMetadataBuilder_remove),
    ('addField', IMetadataBuilder_addField),
    ('getMetadata', IMetadataBuilder_getMetadata),
    ('setField', IMetadataBuilder_setField),
    ('setRelation', IMetadataBuilder_setRelation),
    ('setOwner', IMetadataBuilder_setOwner),
    ('setAlias', IMetadataBuilder_setAlias)]
# IResultSet(3) : ReferenceCounted
IResultSet_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('fetchNext', IResultSet_fetchNext),
    ('fetchPrior', IResultSet_fetchPrior),
    ('fetchFirst', IResultSet_fetchFirst),
    ('fetchLast', IResultSet_fetchLast),
    ('fetchAbsolute', IResultSet_fetchAbsolute),
    ('fetchRelative', IResultSet_fetchRelative),
    ('isEof', IResultSet_isEof),
    ('isBof', IResultSet_isBof),
    ('getMetadata', IResultSet_getMetadata),
    ('close', IResultSet_close),
    ('setDelayedOutputFormat', IResultSet_setDelayedOutputFormat)]
# >>> Firebird 4
# IStatement(4) : ReferenceCounted
IStatement_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('getInfo', IStatement_getInfo),
    ('getType', IStatement_getType),
    ('getPlan', IStatement_getPlan),
    ('getAffectedRecords', IStatement_getAffectedRecords),
    ('getInputMetadata', IStatement_getInputMetadata),
    ('getOutputMetadata', IStatement_getOutputMetadata),
    ('execute', IStatement_execute),
    ('openCursor', IStatement_openCursor),
    ('setCursorName', IStatement_setCursorName),
    ('free', IStatement_free),
    ('getFlags', IStatement_getFlags),
    ('getTimeout', IStatement_getTimeout),
    ('setTimeout', IStatement_setTimeout),
    ('createBatch', IStatement_createBatch)]
# IBatch(3) : ReferenceCounted
IBatch_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('add', IBatch_add),
    ('addBlob', IBatch_addBlob),
    ('appendBlobData', IBatch_appendBlobData),
    ('addBlobStream', IBatch_addBlobStream),
    ('registerBlob', IBatch_registerBlob),
    ('execute', IBatch_execute),
    ('cancel', IBatch_cancel),
    ('getBlobAlignment', IBatch_getBlobAlignment),
    ('getMetadata', IBatch_getMetadata),
    ('setDefaultBpb', IBatch_setDefaultBpb)]
# IBatchCompletionState(3) : Disposable
IBatchCompletionState_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('dispose', IDisposable_dispose),
    ('getSize', IBatchCompletionState_getSize),
    ('getState', IBatchCompletionState_getState),
    ('findError', IBatchCompletionState_findError),
    ('getStatus', IBatchCompletionState_getStatus)]
# ? IReplicator(3) : ReferenceCounted
# IRequest(3) : ReferenceCounted
IRequest_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('receive', IRequest_receive),
    ('send', IRequest_send),
    ('getInfo', IRequest_getInfo),
    ('start', IRequest_start),
    ('startAndSend', IRequest_startAndSend),
    ('unwind', IRequest_unwind),
    ('free', IRequest_free)]
# IEvents(3) : ReferenceCounted
IEvents_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('cancel', IEvents_cancel)]
# >>> Firebird 4
# IAttachment(4) : ReferenceCounted
IAttachment_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('getInfo', IAttachment_getInfo),
    ('startTransaction', IAttachment_startTransaction),
    ('reconnectTransaction', IAttachment_reconnectTransaction),
    ('compileRequest', IAttachment_compileRequest),
    ('transactRequest', IAttachment_transactRequest),
    ('createBlob', IAttachment_createBlob),
    ('openBlob', IAttachment_openBlob),
    ('getSlice', IAttachment_getSlice),
    ('putSlice', IAttachment_putSlice),
    ('executeDyn', IAttachment_executeDyn),
    ('prepare', IAttachment_prepare),
    ('execute', IAttachment_execute),
    ('openCursor', IAttachment_openCursor),
    ('queEvents', IAttachment_queEvents),
    ('cancelOperation', IAttachment_cancelOperation),
    ('ping', IAttachment_ping),
    ('detach', IAttachment_detach),
    ('dropDatabase', IAttachment_dropDatabase),
    ('getIdleTimeout', IAttachment_getIdleTimeout),
    ('setIdleTimeout', IAttachment_setIdleTimeout),
    ('getStatementTimeout', IAttachment_getStatementTimeout),
    ('setStatementTimeout', IAttachment_setStatementTimeout),
    ('createBatch', IAttachment_createBatch),
    ('createReplicator', c_void_p)]
# IService(3) : ReferenceCounted
IService_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('detach', IService_detach),
    ('query', IService_query),
    ('start', IService_start)]
# IProvider(4) : PluginBase
IProvider_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('setOwner', IPluginBase_setOwner),
    ('getOwner', IPluginBase_getOwner),
    ('attachDatabase', IProvider_attachDatabase),
    ('createDatabase', IProvider_createDatabase),
    ('attachServiceManager', IProvider_attachServiceManager),
    ('shutdown', IProvider_shutdown),
    ('setDbCryptCallback', IProvider_setDbCryptCallback)]
# IDtcStart(3) : Disposable
IDtcStart_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('dispose', IDisposable_dispose),
    ('addAttachment', IDtcStart_addAttachment),
    ('addWithTpb', IDtcStart_addWithTpb),
    ('start', IDtcStart_start)]
# IDtc(2) : Versioned
IDtc_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('join', IDtc_join),
    ('startBuilder', IDtc_startBuilder)]
# ? IAuth(4) : PluginBase
# ? IWriter(2) : Versioned
# ? IServerBlock(2) : Versioned
# ? IClientBlock(4) : ReferenceCounted
# ? IServer(6) : Auth
# ? IClient(5) : Auth
# ? IUserField(2) : Versioned
# ? ICharUserField(3) : IUserField
# ? IIntUserField(3) : IUserField
# ? IUser(2) : Versioned
# ? IListUsers(2) : Versioned
# ? ILogonInfo(2) : Versioned
# ? IManagement(4) : PluginBase
# ? IAuthBlock(2) : Versioned
# ? IWireCryptPlugin(4) : PluginBase
# ICryptKeyCallback(2) : Versioned
ICryptKeyCallback_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('callback', ICryptKeyCallback_callback)]
# ? IKeyHolderPlugin(5) : PluginBase
# ? IDbCryptInfo(3) : ReferenceCounted
# ? IDbCryptPlugin(5) : PluginBase
# ? IExternalContext(2) : Versioned
# ? IExternalResultSet(3) : Disposable
# ? IExternalFunction(3) : Disposable
# ? IExternalProcedure(3) : Disposable
# ? IExternalTrigger(3) : Disposable
# ? IRoutineMetadata(2) : Versioned
# ? IExternalEngine(4) : PluginBase
# ITimer(3) : ReferenceCounted
ITimer_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('addRef', IReferenceCounted_addRef),
    ('release', IReferenceCounted_release),
    ('handler', ITimer_handler)]
# ITimerControl(2) : Versioned
ITimerControl_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('start', ITimerControl_start),
    ('stop', ITimerControl_stop)]
# IVersionCallback(2) : Versioned
IVersionCallback_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('callback', IVersionCallback_callback)]
# >>> Firebird 4
# IUtil(4) : Versioned
IUtil_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('getFbVersion', IUtil_getFbVersion),
    ('loadBlob', IUtil_loadBlob),
    ('dumpBlob', IUtil_dumpBlob),
    ('getPerfCounters', IUtil_getPerfCounters),
    ('executeCreateDatabase', IUtil_executeCreateDatabase),
    ('decodeDate', IUtil_decodeDate),
    ('decodeTime', IUtil_decodeTime),
    ('encodeDate', IUtil_encodeDate),
    ('encodeTime', IUtil_encodeTime),
    ('formatStatus', IUtil_formatStatus),
    ('getClientVersion', IUtil_getClientVersion),
    ('getXpbBuilder', IUtil_getXpbBuilder),
    ('setOffsets', IUtil_setOffsets),
    ('getDecFloat16', IUtil_getDecFloat16),
    ('getDecFloat34', IUtil_getDecFloat34),
    ('decodeTimeTz', IUtil_decodeTimeTz),
    ('decodeTimeStampTz', IUtil_decodeTimeStampTz),
    ('encodeTimeTz', IUtil_encodeTimeTz),
    ('encodeTimeStampTz', IUtil_encodeTimeStampTz),
    ('getInt128', IUtil_getInt128),
    ('decodeTimeTzEx', IUtil_decodeTimeTzEx),
    ('decodeTimeStampTzEx', IUtil_decodeTimeStampTzEx)]
# IOffsetsCallback(2) : Versioned
IOffsetsCallback_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('setOffset', IOffsetsCallback_setOffset)]
# IXpbBuilder(3) : Disposable
IXpbBuilder_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('dispose', IDisposable_dispose),
    ('clear', IXpbBuilder_clear),
    ('removeCurrent', IXpbBuilder_removeCurrent),
    ('insertInt', IXpbBuilder_insertInt),
    ('insertBigInt', IXpbBuilder_insertBigInt),
    ('insertBytes', IXpbBuilder_insertBytes),
    ('insertString', IXpbBuilder_insertString),
    ('insertTag', IXpbBuilder_insertTag),
    ('isEof', IXpbBuilder_isEof),
    ('moveNext', IXpbBuilder_moveNext),
    ('rewind', IXpbBuilder_rewind),
    ('findFirst', IXpbBuilder_findFirst),
    ('findNext', IXpbBuilder_findNext),
    ('getTag', IXpbBuilder_getTag),
    ('getLength', IXpbBuilder_getLength),
    ('getInt', IXpbBuilder_getInt),
    ('getBigInt', IXpbBuilder_getBigInt),
    ('getString', IXpbBuilder_getString),
    ('getBytes', IXpbBuilder_getBytes),
    ('getBufferLength', IXpbBuilder_getBufferLength),
    ('getBuffer', IXpbBuilder_getBuffer)]
# ? ITraceConnection(2) : Versioned
# ? ITraceDatabaseConnection(3) : TraceConnection
# ? ITraceTransaction(3) : Versioned
# ? ITraceParams(3) : Versioned
# ? ITraceStatement(2) : Versioned
# ? ITraceSQLStatement(3) : TraceStatement
# ? ITraceBLRStatement(3) : TraceStatement
# ? ITraceDYNRequest(2) : Versioned
# ? ITraceContextVariable(2) : Versioned
# ? ITraceProcedure(2) : Versioned
# ? ITraceFunction(2) : Versioned
# ? ITraceTrigger(2) : Versioned
# ? ITraceServiceConnection(3) : TraceConnection
# ? ITraceStatusVector(2) : Versioned
# ? ITraceSweepInfo(2) : Versioned
# ? ITraceLogWriter(4) : ReferenceCounted
# ? ITraceInitInfo(2) : Versioned
# ? ITracePlugin(3) : ReferenceCounted
# ? ITraceFactory(4) : PluginBase
# ? IUdrFunctionFactory(3) : Disposable
# ? IUdrProcedureFactory(3) : Disposable
# ? IUdrTriggerFactory(3) : Disposable
# ? IUdrPlugin(2) : Versioned
# >>> Firebird 4
# IDecFloat16(2) : Versioned
IDecFloat16_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('toBcd', IDecFloat16_toBcd),
    ('toString', IDecFloat16_toString),
    ('fromBcd', IDecFloat16_fromBcd),
    ('fromString', IDecFloat16_fromString)]
# IDecFloat34(2) : Versioned
IDecFloat34_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('toBcd', IDecFloat34_toBcd),
    ('toString', IDecFloat34_toString),
    ('fromBcd', IDecFloat34_fromBcd),
    ('fromString', IDecFloat34_fromString)]
# IInt128(2) : Versioned
IInt128_VTable._fields_ = [
    ('dummy', c_void_p),
    ('version', c_ulong),
    ('toString', IInt128_toString),
    ('fromString', IInt128_fromString)]


#: Encoding used to decode error messages from Firebird.
err_encoding = getpreferredencoding()

def db_api_error(status: ISC_STATUS_ARRAY) -> bool:
    "Returns True if status_vector contains error"
    return status[0] == 1 and status[1] > 0


def exception_from_status(error, status: ISC_STATUS_ARRAY, preamble: str = None) -> Exception:
    "Returns exception assembled from error information stored is `status`."
    msglist = []
    msg = create_string_buffer(1024)
    if preamble:
        msglist.append(preamble)
    sqlcode = api.isc_sqlcode(status)
    error_code = status[1]
    msglist.append('- SQLCODE: %i' % sqlcode)

    pvector = cast(addressof(status), ISC_STATUS_PTR)
    sqlstate = create_string_buffer(6)
    api.fb_sqlstate(sqlstate, pvector)

    while True:
        result = api.fb_interpret(msg, 1024, pvector)
        if result != 0:
            msglist.append('- ' + (msg.value).decode(err_encoding, errors='replace'))
        else:
            break
    return error('\n'.join(msglist), sqlcode=sqlcode, sqlstate=sqlstate, gds_codes=[error_code])

# Client library

class FirebirdAPI:
    """Firebird Client API interface object. Loads Firebird Client Library and
    exposes `fb_get_master_interface()`. Uses :ref:`ctypes <python:module-ctypes>`
    for bindings.

    Arguments:
        filename (`~pathlib.Path`): Firebird client library to be loaded. If it's not provided,
            the driver uses :func:`~ctypes.util.find_library()` to locate the library.

    Attributes:
        client_library (`~ctypes.ctypes.CDLL`): Loaded Firebird client library :mod:`ctypes` handler
        client_library_name (`~pathlib.Path`): Path to loaded Firebird client library
        master (iMaster): Firebird API IMaster interface
        util (iUtil): Firebird API IUtil interface

    Methods:
        fb_get_master_interface():
            This function is used to obtain primary Firebird interface, required
            to access all the rest of interfaces. Has no parameters and always succeeds.

            Returns:
                `.iMaster`

        fb_get_database_handle():
            Helper function that returns database handle for specified IAttachment interface.

            Arguments:
                status (`ISC_STATUS_PTR`): :ISC status
                db_handle (`FB_API_HANDLE_PTR`): database handle
                att (iAttachment): attachment

            Returns:
                `ISC_STATUS`

        fb_get_transaction_handle():
            Helper function that returns database handle for specified ITransaction interface.

            Arguments:
                status (`ISC_STATUS_PTR`): ISC status
                tra_handle (`FB_API_HANDLE_PTR`): Transaction handle
                att (iTransaction): Transaction

            Returns:
                `ISC_STATUS`

        fb_interpret():
            Helper function that fills buffer with text for errors noted in ISC status.

            Arguments:
                buffer (`STRING`): Buffer for message
                buf_size (int): Buffer size
                status_ptr: Pointer to `ISC_STATUS_PTR`

            Returns:
                `ISC_LONG`

        fb_sqlstate():
            Helper function that returns SQLSTATE for ISC_STATUS.

            Arguments:
                status (`ISC_STATUS_PTR`): ISC status

            Returns:
                `STRING` - 5 characters of SQLSTATE

        isc_sqlcode():
            Helper function that returns SQLCODE for ISC_STATUS.

            Arguments:
                status (`ISC_STATUS_PTR`): ISC status

            Returns:
                `ISC_LONG`

        isc_array_lookup_bounds():
            Old API function isc_array_lookup_bounds()

        isc_array_put_slice():
            Old API function isc_array_put_slice()

        isc_array_get_slice():
            Old API function isc_array_get_slice()

        isc_que_events():
            Old API function isc_que_events()

        isc_event_counts():
            Old API function isc_event_counts()

        isc_cancel_events():
            Old API function isc_cancel_events()
    """
    def __init__(self, filename: Path = None):
        decimal.getcontext().prec = 34
        if filename is None:
            if sys.platform == 'darwin':
                filename = find_library('Firebird')
            elif sys.platform == 'win32':
                filename = find_library('fbclient.dll')
            else:
                filename = find_library('fbclient')
                if not filename:
                    with suppress(Exception):
                        ctypes.CDLL('libfbclient.so')
                        filename = 'libfbclient.so'
            if not filename:
                raise Exception("The location of Firebird Client Library could not be determined.")
        elif not filename.exists():
            file_name = find_library(filename.name)
            if not file_name:
                raise Exception(f"Firebird Client Library '{filename}' not found")
            filename = file_name
        self.client_library: ctypes.CDLL = None
        if sys.platform in ('win32', 'cygwin', 'os2', 'os2emx'):
            self.client_library: ctypes.CDLL = ctypes.WinDLL(str(filename))
        else:
            self.client_library: ctypes.CDLL = ctypes.CDLL(str(filename))
        #
        self.client_library_name: Path = Path(filename)
        #
        self.fb_get_master_interface = (self.client_library.fb_get_master_interface)
        self.fb_get_master_interface.restype = IMaster
        self.fb_get_master_interface.argtypes = []
        #
        self.fb_get_database_handle = self.client_library.fb_get_database_handle
        self.fb_get_database_handle.restype = ISC_STATUS
        self.fb_get_database_handle.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR, IAttachment]
        #
        self.fb_get_transaction_handle = (self.client_library.fb_get_transaction_handle)
        self.fb_get_transaction_handle.restype = ISC_STATUS
        self.fb_get_transaction_handle.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR, ITransaction]
        #
        self.fb_sqlstate = self.client_library.fb_sqlstate
        self.fb_sqlstate.restype = None
        self.fb_sqlstate.argtypes = [STRING, ISC_STATUS_PTR]
        #
        self.fb_shutdown_callback = self.client_library.fb_shutdown_callback
        self.fb_shutdown_callback.restype = ISC_STATUS
        self.fb_shutdown_callback.argtypes = [ISC_STATUS_PTR,
                                              FB_SHUTDOWN_CALLBACK,
                                              c_int,
                                              c_void_p]
        #
        self.isc_sqlcode = self.client_library.isc_sqlcode
        self.isc_sqlcode.restype = ISC_LONG
        self.isc_sqlcode.argtypes = [ISC_STATUS_PTR]
        #
        self.fb_interpret = self.client_library.fb_interpret
        self.fb_interpret.restype = ISC_LONG
        self.fb_interpret.argtypes = [STRING, c_uint, POINTER(ISC_STATUS_PTR)]
        #
        self.isc_array_lookup_bounds = (self.client_library.isc_array_lookup_bounds)
        self.isc_array_lookup_bounds.restype = ISC_STATUS
        self.isc_array_lookup_bounds.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                                 FB_API_HANDLE_PTR, STRING, STRING,
                                                 ISC_ARRAY_DESC_PTR]
        #
        self.isc_array_put_slice = self.client_library.isc_array_put_slice
        self.isc_array_put_slice.restype = ISC_STATUS
        self.isc_array_put_slice.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                             FB_API_HANDLE_PTR, ISC_QUAD_PTR,
                                             ISC_ARRAY_DESC_PTR, c_void_p, ISC_LONG_PTR]
        #
        self.isc_array_get_slice = self.client_library.isc_array_get_slice
        self.isc_array_get_slice.restype = ISC_STATUS
        self.isc_array_get_slice.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                             FB_API_HANDLE_PTR, ISC_QUAD_PTR,
                                             ISC_ARRAY_DESC_PTR, c_void_p, ISC_LONG_PTR]
        #
        self.P_isc_event_block = CFUNCTYPE(ISC_LONG, POINTER(POINTER(ISC_UCHAR)),
                                           POINTER(POINTER(ISC_UCHAR)), ISC_USHORT)
        # C_isc_event_block(ISC_LONG, POINTER(POINTER(ISC_UCHAR)), POINTER(POINTER(ISC_UCHAR)), ISC_USHORT)
        self.C_isc_event_block = self.P_isc_event_block(('isc_event_block', self.client_library))
        self.P_isc_event_block_args = self.C_isc_event_block.argtypes
        #
        self.isc_que_events = self.client_library.isc_que_events
        self.isc_que_events.restype = ISC_STATUS
        self.isc_que_events.argtypes = [POINTER(ISC_STATUS), POINTER(FB_API_HANDLE),
                                        POINTER(ISC_LONG), c_short, POINTER(ISC_UCHAR),
                                        ISC_EVENT_CALLBACK, POINTER(ISC_UCHAR)]
        #
        self.isc_event_counts = self.client_library.isc_event_counts
        self.isc_event_counts.restype = None
        self.isc_event_counts.argtypes = [POINTER(RESULT_VECTOR), c_short,
                                          POINTER(ISC_UCHAR), POINTER(ISC_UCHAR)]
        #
        self.isc_cancel_events = self.client_library.isc_cancel_events
        self.isc_cancel_events.restype = ISC_STATUS
        self.isc_cancel_events.argtypes = [POINTER(ISC_STATUS), POINTER(FB_API_HANDLE),
                                           POINTER(ISC_LONG)]
        # Next netributes are set in types by API_LOADED hook
        self.master = None
        self.util = None

    def isc_event_block(self, event_buffer: bytes, result_buffer: bytes, *args) -> int:
        """Convenience wrapper for isc_event_block() API function. Injects variable
        number of parameters into `C_isc_event_block` call.
        """
        if len(args) > 15:
            raise ValueError("isc_event_block takes no more than 15 event names")
        newargs = list(self.P_isc_event_block_args)
        newargs.extend(STRING for x in args)
        self.C_isc_event_block.argtypes = newargs
        return self.C_isc_event_block(event_buffer, result_buffer, len(args), *args)

def has_api() -> bool:
    """Reaturns True if Firebird API is already loaded.
    """
    return api is not None

def load_api(filename: Union[None, str, Path] = None) -> None:
    """Initializes bindings to Firebird Client Library unless they are already initialized.
    Called automatically by `get_api()`.

    Args:
        filename: Path to Firebird Client Library.
        When it's not specified, driver does its best to locate appropriate client library.

    Returns:
        `FirebirdAPI` instance.

    Hooks:
        Event `HookType.HOOK_API_LOADED`: Executed after api is initialized.
        Hook routine must have signature: `hook_func(api)`. Any value returned by
        hook is ignored.
    """
    if not has_api():
        if filename is None:
            filename = driver_config.fb_client_library.value
        if filename and not isinstance(filename, Path):
            filename = Path(filename)
        _api = FirebirdAPI(filename)
        setattr(sys.modules[__name__], 'api', _api)
        for hook in get_callbacks(APIHook.LOADED, _api):
            hook(_api)

def get_api() -> FirebirdAPI:
    """Returns Firebird API. Loads the API if needed.
    """
    if not has_api():
        load_api()
    return api

api: FirebirdAPI = None

register_class(FirebirdAPI, set([APIHook.LOADED]))
