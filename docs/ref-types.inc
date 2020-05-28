.. module:: firebird.driver.types
    :synopsis: Firebird driver types

=====================
firebird.driver.types
=====================

Exceptions
==========

Next exceptions are required by Python DB API 2.0

Error
-----
Imported from `firebird.base.types`.

.. autoexception:: Error

InterfaceError
--------------
.. autoexception:: InterfaceError

DatabaseError
-------------
.. autoexception:: DatabaseError

DataError
---------
.. autoexception:: DataError

OperationalError
----------------
.. autoexception:: OperationalError

IntegrityError
--------------
.. autoexception:: IntegrityError

InternalError
-------------
.. autoexception:: InternalError

ProgrammingError
----------------
.. autoexception:: ProgrammingError

NotSupportedError
-----------------
.. autoexception:: NotSupportedError

This is the exception inheritance layout::

    StandardError
    |__Warning
    |__Error
        |__InterfaceError
        |__DatabaseError
            |__DataError
            |__OperationalError
            |__IntegrityError
            |__InternalError
            |__ProgrammingError
            |__NotSupportedError

Other constants and types required by Python DB API 2.0 specification
=====================================================================

Globals
-------

.. autodata:: apilevel

.. autodata:: threadsafety

.. autodata:: paramstyle

Helper constants for work with :attr:`Cursor.description` content
-----------------------------------------------------------------

- DESCRIPTION_NAME
- DESCRIPTION_TYPE_CODE
- DESCRIPTION_DISPLAY_SIZE
- DESCRIPTION_INTERNAL_SIZE
- DESCRIPTION_PRECISION
- DESCRIPTION_SCALE
- DESCRIPTION_NULL_OK

Types
-----

.. autodata:: STRING

.. autodata:: BINARY

.. autodata:: NUMBER

.. autodata:: DATETIME

.. autodata:: ROWID

Constructors for data types
---------------------------

.. autodata:: Date

.. autodata:: Time

.. autodata:: Timestamp

.. autofunction:: DateFromTicks

.. autofunction:: TimeFromTicks

.. autofunction:: TimestampFromTicks

.. autodata:: Binary

Types for type hints
====================

.. autodata:: DESCRIPTION

.. autodata:: CB_OUTPUT_LINE

.. autoclass:: Transactional

Enums
=====

NetProtocol
-----------
.. autoclass:: NetProtocol

DirectoryCode
-------------
.. autoclass:: DirectoryCode

XpbKind
-------
.. autoclass:: XpbKind

StateResult
-----------
.. autoclass:: StateResult

DBKeyScope
----------
.. autoclass:: DBKeyScope

InfoItemType
------------
.. autoclass:: InfoItemType

SvcInfoCode
-----------
.. autoclass:: SvcInfoCode

BlobInfoCode
------------
.. autoclass:: BlobInfoCode

DbInfoCode
----------
.. autoclass:: DbInfoCode

TraInfoCode
-----------
.. autoclass:: TraInfoCode

TraInfoIsolation
----------------
.. autoclass:: TraInfoIsolation

TraInfoReadCommitted
--------------------
.. autoclass:: TraInfoReadCommitted

TraInfoAccess
-------------
.. autoclass:: TraInfoAccess

TraIsolation
------------
.. autoclass:: TraIsolation

TraReadCommitted
----------------
.. autoclass:: TraReadCommitted

Isolation
---------
.. autoclass:: Isolation

TraLockResolution
-----------------
.. autoclass:: TraLockResolution

TraAccessMode
-------------
.. autoclass:: TraAccessMode

TableShareMode
--------------
.. autoclass:: TableShareMode

TableAccessMode
---------------
.. autoclass:: TableAccessMode

DefaultAction
-------------
.. autoclass:: DefaultAction

StatementType
-------------
.. autoclass:: StatementType

SQLDataType
-----------
.. autoclass:: SQLDataType

DPBItem
-------
.. autoclass:: DPBItem

TPBItem
-------
.. autoclass:: TPBItem

SPBItem
-------
.. autoclass:: SPBItem

BPBItem
-------
.. autoclass:: BPBItem

BlobType
--------
.. autoclass:: BlobType

BlobStorage
-----------
.. autoclass:: BlobStorage

ServiceAction
-------------
.. autoclass:: ServiceAction

SvcDbInfoOption
---------------
.. autoclass:: SvcDbInfoOption

SvcRepairOption
---------------
.. autoclass:: SvcRepairOption

SvcBackupOption
---------------
.. autoclass:: SvcBackupOption

SvcRestoreOption
----------------
.. autoclass:: SvcRestoreOption

SvcNBackupOption
----------------
.. autoclass:: SvcNBackupOption

SvcTraceOption
--------------
.. autoclass:: SvcTraceOption

SvcPropertiesOption
-------------------
.. autoclass:: SvcPropertiesOption

SvcValidateOption
-----------------
.. autoclass:: SvcValidateOption

SvcUserOption
-------------
.. autoclass:: SvcUserOption

DbAccessMode
------------
.. autoclass:: DbAccessMode

DbSpaceReservation
-------------------
.. autoclass:: DbSpaceReservation

DbWriteMode
------------
.. autoclass:: DbWriteMode

ShutdownMode
------------
.. autoclass:: ShutdownMode

OnlineMode
----------
.. autoclass:: OnlineMode

ShutdownMethod
--------------
.. autoclass:: ShutdownMethod

TransactionState
----------------
.. autoclass:: TransactionState

Flags
=====

StateFlag
---------
.. autoclass:: StateFlag

PreparePrefetchFlag
-------------------
.. autoclass:: PreparePrefetchFlag

StatementFlag
-------------
.. autoclass:: StatementFlag

CursorFlag
----------
.. autoclass:: CursorFlag

ConnectionFlag
--------------
.. autoclass:: ConnectionFlag

ServerCapability
----------------
.. autoclass:: ServerCapability

SvcRepairFlag
-------------
.. autoclass:: SvcRepairFlag

SvcStatFlag
-----------
.. autoclass:: SvcStatFlag

SvcBackupFlag
-------------
.. autoclass:: SvcBackupFlag

SvcRestoreFlag
--------------
.. autoclass:: SvcRestoreFlag

SvcNBackupFlag
--------------
.. autoclass:: SvcNBackupFlag

SvcPropertiesFlag
-----------------
.. autoclass:: SvcPropertiesFlag

Dataclasses
===========

ItemMetadata
------------
.. autoclass:: ItemMetadata
   :no-members:

TableAccessStats
----------------
.. autoclass:: TableAccessStats
   :no-members:

UserInfo
--------
.. autoclass:: UserInfo
   :no-members:

Managers for parameter buffers
==============================

TPB
---
.. autoclass:: TPB

DPB
---
.. autoclass:: DPB

SPB_ATTACH
----------
.. autoclass:: SPB_ATTACH

Buffer
------
.. autoclass:: Buffer

Firebird API Interface wrappers
===============================

iVersioned
----------
.. autoclass:: iVersioned

iReferenceCounted
-----------------
.. autoclass:: iReferenceCounted

iDisposable
-----------
.. autoclass:: iDisposable

iPluginBase
-----------
.. autoclass:: iPluginBase

iConfigEntry
------------
.. autoclass:: iConfigEntry

iConfig
-------
.. autoclass:: iConfig

iFirebirdConf
-------------
.. autoclass:: iFirebirdConf

iPluginManager
--------------
.. autoclass:: iPluginManager

iConfigManager
--------------
.. autoclass:: iConfigManager

iBlob
-----
.. autoclass:: iBlob

iTransaction
------------
.. autoclass:: iTransaction

iMessageMetadata
----------------
.. autoclass:: iMessageMetadata

iMetadataBuilder
----------------
.. autoclass:: iMetadataBuilder

iResultSet
----------
.. autoclass:: iResultSet

iStatement
----------
.. autoclass:: iStatement

iRequest
--------
.. autoclass:: iRequest

iEvents
-------
.. autoclass:: iEvents

iAttachment
-----------
.. autoclass:: iAttachment

iService
--------
.. autoclass:: iService

iProvider
---------
.. autoclass:: iProvider

iDtcStart
---------
.. autoclass:: iDtcStart

iDtc
----
.. autoclass:: iDtc

iTimerControl
-------------
.. autoclass:: iTimerControl

iXpbBuilder
-----------
.. autoclass:: iXpbBuilder

iUtil
-----
.. autoclass:: iUtil

iMaster
-------
.. autoclass:: iMaster

Interface implementations
=========================

iVersionedImpl
--------------
.. autoclass:: iVersionedImpl

iReferenceCountedImpl
---------------------
.. autoclass:: iReferenceCountedImpl

iDisposableImpl
---------------
.. autoclass:: iDisposableImpl

iVersionCallbackImpl
--------------------
.. autoclass:: iVersionCallbackImpl

iCryptKeyCallbackImpl
---------------------
.. autoclass:: iCryptKeyCallbackImpl

iOffsetsCallbackImp
-------------------
.. autoclass:: iOffsetsCallbackImp

iEventCallbackImpl
------------------
.. autoclass:: iEventCallbackImpl

iTimerImpl
----------
.. autoclass:: iTimerImpl

