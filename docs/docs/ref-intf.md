
# firebird.driver.interfaces

This module contains interface wrappers for Firebird new API.

!!! important

    1. Firebird OO API interfaces use inheritance, i.e. they could be inherited from other
        interface. In fact, all interfaces returned by Firebird are inherited from `IVersioned`
        interface.

    2. Firebird OO API interfaces are versioned. Any addition to particular interface
        increases its version number. Application developers are responsible to check the
        version of returned interface to verify that it supports methods they want to use.

    If you want to use Firebird OO API interfaces directly in you application, read next
    section very carefuly.

In Python driver, interfaces are represented as instances of interface wrapper classes
that expose the methods provided by particular Firebird interface version. The wrapper
class hierarchy thus represent not only inheritance between Firebird interfaces, but also
between versions of particular Firebird interface.

Because all interfaces returned by Firebird are inherited from `IVersioned` interface,
all wrapper classes have `VERSION` class attribute that contain version number of wrapped
interface.

Each Firebird interface has it's "canonical" Python wrapper with coresponding name. For
example interface `IService` has wrapper class `iService`. However, if there are multiple
public versions of Firebird interface, there are multiple wrapper classes for each published
interface version (interim, non-public versions used during Firebird development are skipped).
These wrapper classes have names based on their canonical name with suffix that represent
the interface version they wrap. It means that canonical wrapper **always** represents
the highest interface version.

Whenever Firebird interface is returned from Firebird OO API call, it's wrapped to its
Python wrapper class according to interface type and version. The Python driver ensures
that correct wrapper class is used according to returned interface version.

However, this architecture has several important consequences:

1. The interface wrapper classes may change between driver releases as new interface versions
    are introduced. For example, driver versions up to 1.5.2 had only canonical `iService`
    (version 3), but in version 1.6.0 it was renamed to `iService_v3`, new wrappers
    `iService_v4` and (new canonical) `iService` (version 5) were added.
2. Instead using `isinstance` to check interface versions, you should always use
    `VERSION` attribute on wrapper class instance.


## Metaclasses

::: firebird.driver.interfaces.iVersionedMeta

## Firebird API Interface wrappers

### Base interfaces
::: firebird.driver.interfaces.iVersioned

::: firebird.driver.interfaces.iReferenceCounted

::: firebird.driver.interfaces.iDisposable

::: firebird.driver.interfaces.iStatus

::: firebird.driver.interfaces.iPluginBase

::: firebird.driver.interfaces.iMaster

### Configuration
::: firebird.driver.interfaces.iConfigEntry

::: firebird.driver.interfaces.iConfig

::: firebird.driver.interfaces.iFirebirdConf_v3

::: firebird.driver.interfaces.iFirebirdConf

::: firebird.driver.interfaces.iConfigManager_v2

::: firebird.driver.interfaces.iConfigManager

### Database and service attachments
::: firebird.driver.interfaces.iProvider

::: firebird.driver.interfaces.iAttachment_v3

::: firebird.driver.interfaces.iAttachment_v4

::: firebird.driver.interfaces.iAttachment

::: firebird.driver.interfaces.iService_v3

::: firebird.driver.interfaces.iService_v4

::: firebird.driver.interfaces.iService

::: firebird.driver.interfaces.iXpbBuilder

### Blobs
::: firebird.driver.interfaces.iBlob_v3

::: firebird.driver.interfaces.iBlob

### Transactions
::: firebird.driver.interfaces.iTransaction_v3

::: firebird.driver.interfaces.iTransaction

::: firebird.driver.interfaces.iDtcStart

::: firebird.driver.interfaces.iDtc

### Metadata
::: firebird.driver.interfaces.iMessageMetadata_v3

::: firebird.driver.interfaces.iMessageMetadata

::: firebird.driver.interfaces.iMetadataBuilder_v3

::: firebird.driver.interfaces.iMetadataBuilder

### SQL execution
::: firebird.driver.interfaces.iStatement_v3

::: firebird.driver.interfaces.iStatement_v4

::: firebird.driver.interfaces.iStatement

::: firebird.driver.interfaces.iResultSet_v3

::: firebird.driver.interfaces.iResultSet

::: firebird.driver.interfaces.iBatch_v3

::: firebird.driver.interfaces.iBatch

::: firebird.driver.interfaces.iBatchCompletionState

### Events
::: firebird.driver.interfaces.iEvents_v3

::: firebird.driver.interfaces.iEvents

### Utilities
::: firebird.driver.interfaces.iTimerControl

::: firebird.driver.interfaces.iUtil_v2

::: firebird.driver.interfaces.iUtil

::: firebird.driver.interfaces.iDecFloat16

::: firebird.driver.interfaces.iDecFloat34

::: firebird.driver.interfaces.iInt128

### Other
::: firebird.driver.interfaces.iPluginManager

::: firebird.driver.interfaces.iRequest_v3

::: firebird.driver.interfaces.iRequest

## Interface implementations

::: firebird.driver.interfaces.iVersionedImpl

::: firebird.driver.interfaces.iReferenceCountedImpl

::: firebird.driver.interfaces.iDisposableImpl

::: firebird.driver.interfaces.iVersionCallbackImpl

::: firebird.driver.interfaces.iCryptKeyCallbackImpl

::: firebird.driver.interfaces.iOffsetsCallbackImp

::: firebird.driver.interfaces.iEventCallbackImpl

::: firebird.driver.interfaces.iTimerImpl
