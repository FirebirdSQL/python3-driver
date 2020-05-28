.. module:: firebird.driver.fbapi
    :synopsis: Python ctypes interface to Firebird client library

=====================
firebird.driver.fbapi
=====================

This module contains low-level :ref:`ctypes <python:module-ctypes>` interface to
Firebird client library (`fbclient.so/dll`).

Constants
=========

C integer limit constants
-------------------------

.. hlist::
    :columns: 6

    - SHRT_MIN
    - SHRT_MAX
    - USHRT_MAX
    - INT_MIN
    - INT_MAX
    - UINT_MAX
    - LONG_MIN
    - LONG_MAX
    - SSIZE_T_MIN
    - SSIZE_T_MAX

Type codes
----------

.. hlist::
    :columns: 6

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

Internal type codes (for example used by ARRAY descriptor)
----------------------------------------------------------

.. hlist::
    :columns: 6

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


Info structural codes
---------------------

.. hlist::
    :columns: 6

    - isc_info_end
    - isc_info_truncated
    - isc_info_error
    - isc_info_data_not_ready
    - isc_info_length
    - isc_info_flag_end

Types
=====

Basic types
-----------

.. autoclass:: STRING
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: FB_API_HANDLE
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: FB_API_HANDLE_PTR
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_STATUS
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_STATUS_PTR
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_STATUS_ARRAY
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_STATUS_ARRAY_PTR
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_LONG
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_LONG_PTR
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_ULONG
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_SHORT
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_USHORT
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_UCHAR
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_INT64
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_UINT64
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_DATE
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_TIME
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_QUAD
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_QUAD_PTR
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_ARRAY_BOUND
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_ARRAY_DESC
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: ISC_ARRAY_DESC_PTR
    :no-show-inheritance:
    :no-inherited-members:

.. autoclass:: RESULT_VECTOR
    :no-show-inheritance:
    :no-inherited-members:

Functions
=========

has_api
-------
.. autofunction:: has_api

load_api
--------
.. autofunction:: load_api

get_api
-------
.. autofunction:: get_api


Classes
=======

FirebirdAPI
-----------

.. autoclass:: FirebirdAPI
    :members:
