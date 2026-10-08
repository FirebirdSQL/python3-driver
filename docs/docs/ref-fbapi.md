
# firebird.driver.fbapi

This module contains low-level [ctypes](https://docs.python.org/3/library/ctypes.html) interface to
Firebird client library (`fbclient.so/dll`).

## Constants

### Type codes

    - SQL_TEXT
    - SQL_VARYING
    - SQL_SHORT
    - SQL_LONG
    - SQL_FLOAT
    - SQL_DOUBLE
    - SQL_D_FLOAT
    - SQL_TIMESTAMP
    - SQL_BLOB
    - SQL_ARRAY
    - SQL_QUAD
    - SQL_TYPE_TIME
    - SQL_TYPE_DATE
    - SQL_INT64
    - SQL_BOOLEAN
    - SQL_NULL
    - SUBTYPE_NUMERIC
    - SUBTYPE_DECIMAL

### Internal type codes (for example used by ARRAY descriptor)

    - blr_text
    - blr_text2
    - blr_short
    - blr_long
    - blr_quad
    - blr_float
    - blr_double
    - blr_d_float
    - blr_timestamp
    - blr_varying
    - blr_varying2
    - blr_blob
    - blr_cstring
    - blr_cstring2
    - blr_blob_id
    - blr_sql_date
    - blr_sql_time
    - blr_int64
    - blr_blob2
    - blr_domain_name
    - blr_domain_name2
    - blr_not_nullable
    - blr_column_name
    - blr_column_name2
    - blr_bool
    - blr_dec64
    - blr_dec128
    - blr_dec_fixed
    - blr_sql_time_tz
    - blr_timestamp_tz
    - blr_ex_time_tz
    - blr_ex_timestamp_tz

## Types

::: firebird.driver.fbapi.Int
    options:
        show_bases: false

::: firebird.driver.fbapi.IntPtr
    options:
        show_bases: false

::: firebird.driver.fbapi.Int64
    options:
        show_bases: false

::: firebird.driver.fbapi.Int64Ptr
    options:
        show_bases: false

::: firebird.driver.fbapi.QWord
    options:
        show_bases: false

::: firebird.driver.fbapi.STRING
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_LONG
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_LONG_PTR
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_ULONG
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_SHORT
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_USHORT
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_UCHAR
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_INT64
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_UINT64
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_DATE
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_TIME
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_DEC16
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_DEC16Ptr
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_DEC34
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_DEC34Ptr
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_I128
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_I128Ptr
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_QUAD
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_QUAD_PTR
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_API_HANDLE
    options:
        show_bases: false

::: firebird.driver.fbapi.FB_API_HANDLE_PTR
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_STATUS
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_STATUS_PTR
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_STATUS_ARRAY
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_STATUS_ARRAY_PTR
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_ARRAY_BOUND
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_ARRAY_DESC
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_ARRAY_DESC_PTR
    options:
        show_bases: false

::: firebird.driver.fbapi.RESULT_VECTOR
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_TIME_TZ
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_TIME_TZ_EX
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_TIMESTAMP
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_TIMESTAMP_TZ
    options:
        show_bases: false

::: firebird.driver.fbapi.ISC_TIMESTAMP_TZ_EX
    options:
        show_bases: false

::: firebird.driver.fbapi.TraceCounts
    options:
        show_bases: false

::: firebird.driver.fbapi.PerformanceInfo
    options:
        show_bases: false

## Variables

::: firebird.driver.fbapi.err_encoding

## Functions

::: firebird.driver.fbapi.has_api

::: firebird.driver.fbapi.load_api

::: firebird.driver.fbapi.get_api

## Classes

::: firebird.driver.fbapi.FirebirdAPI

## Firebird API Interface definitions

::: firebird.driver.fbapi.IVersioned_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IVersioned_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IReferenceCounted_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IReferenceCounted_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IDisposable_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IDisposable_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IStatus_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IStatus_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IMaster_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IMaster_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IPluginBase_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IPluginBase_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IPluginSet_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IPluginSet_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IConfigEntry_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IConfigEntry_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IConfig_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IConfig_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IFirebirdConf_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IFirebirdConf_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IPluginManager_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IPluginManager_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IConfigManager_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IConfigManager_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IEventCallback_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IEventCallback_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IBlob_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IBlob_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.ITransaction_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.ITransaction_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IMessageMetadata_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IMessageMetadata_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IMetadataBuilder_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IMetadataBuilder_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IResultSet_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IResultSet_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IStatement_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IStatement_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IBatch_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IBatch_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IBatchCompletionState_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IBatchCompletionState_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IRequest_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IRequest_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IEvents_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IEvents_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IAttachment_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IAttachment_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IService_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IService_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IProvider_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IProvider_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IDtcStart_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IDtcStart_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IDtc_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IDtc_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.ICryptKeyCallback_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.ICryptKeyCallback_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.ITimer_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.ITimer_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.ITimerControl_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.ITimerControl_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IVersionCallback_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IVersionCallback_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IUtil_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IUtil_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IOffsetsCallback_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IOffsetsCallback_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IXpbBuilder_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IXpbBuilder_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IDecFloat16_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IDecFloat16_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IDecFloat34_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IDecFloat34_struct
    options:
        show_bases: false

::: firebird.driver.fbapi.IInt128_VTable
    options:
        show_bases: false

::: firebird.driver.fbapi.IInt128_struct
    options:
        show_bases: false
