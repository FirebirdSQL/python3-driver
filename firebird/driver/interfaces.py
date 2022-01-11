# coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/interfaces.py
# DESCRIPTION:    Interface wrappers for Firebird new API
# CREATED:        11.6.2020
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

"""firebird-driver - Interface wrappers for Firebird new API
"""

from __future__ import annotations
from typing import Union, Any, Optional, ByteString
import sys
import threading
import datetime
from warnings import warn
from ctypes import memmove, memset, create_string_buffer, cast, byref, string_at, sizeof, \
     c_char_p, c_void_p, c_byte, c_ulong
from .types import Error, DatabaseError, InterfaceError, FirebirdWarning, BCD, \
     StateResult, DirectoryCode, BlobInfoCode, SQLDataType, XpbKind, \
     StatementType, StateFlag, CursorFlag, StatementFlag, PreparePrefetchFlag, get_timezone
from . import fbapi as a
from .hooks import APIHook, add_hook

# Internal
_master = None
_util = None
_thns = threading.local()

# Info structural codes
isc_info_end = 1

# ------------------------------------------------------------------------------
# Interface wrappers
# ------------------------------------------------------------------------------
class iVersionedMeta(type):
    """Metaclass for iVersioned interfaces.

This metaclass uses MRO to instantiate wrapper interface with version that matches version
of wrapped interface.
"""
    def __call__(cls: iVersioned, intf):
        v = intf.contents.vtable.contents.version
        for c in cls.__mro__:
            if getattr(c, 'VERSION', 0) <= v:
                return super(iVersionedMeta, iVersionedMeta).__call__(c, intf)

# IVersioned(1)
class iVersioned(metaclass=iVersionedMeta):
    "IVersioned interface wrapper"
    VERSION = 1
    def __init__(self, intf):
        self._as_parameter_ = intf
        if intf and self.vtable.version < self.VERSION:  # pragma: no cover
            raise InterfaceError(f"Wrong interface version {self.vtable.version}, expected {self.VERSION}")
    def __report(self, cls: Union[Error, FirebirdWarning], vector_ptr: a.ISC_STATUS_ARRAY_PTR) -> None:
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
        # We need to clean up the iStatus before returning
        self.status.init()
        return cls(msg, sqlstate=sqlstate.value.decode(),
                   gds_codes=tuple(gds_codes), sqlcode=sqlcode,)
    def _check(self) -> None:
        state = self.status.get_state()
        if StateFlag.ERRORS in state:
            raise self.__report(DatabaseError, self.status.get_errors())
        if StateFlag.WARNINGS in state:  # pragma: no cover
            #raise self.__report(FirebirdWarning, self.status.get_warning())
            warn(self.__report(FirebirdWarning, self.status.get_warning()),
                 stacklevel=2)
    @property
    def status(self) -> iStatus:
        "iStatus for interface"
        if (result := getattr(_thns, 'status', None)) is None:
            result = _master.get_status()
            _thns.status = result
        return result
    @property
    def vtable(self):
        "Interface method table"
        return self._as_parameter_.contents.vtable.contents
    @property
    def version(self) -> int:
        "Interface version"
        return self._as_parameter_.contents.vtable.contents.version.value

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
class iFirebirdConf_v3(iReferenceCounted):
    "Class that wraps IFirebirdConf v3 interface for use from Python"
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

# IFirebirdConf(4) : IFirebirdConf(3)
class iFirebirdConf(iFirebirdConf_v3):
    "Class that wraps IFirebirdConf v4 interface for use from Python"
    VERSION = 4
    def get_version(self) -> int:
        "Returns configuration version"
        result = self.vtable.asBoolean(self, self.status)
        self._check()
        return result

# >>> Firebird 4
# IPluginManager(2) : Versioned
class iPluginManager(iVersioned):
    "IPluginManager interface wrapper. This is only STUB."
    VERSION = 2

# IConfigManager(2) : Versioned
class iConfigManager_v2(iVersioned):
    "Class that wraps IConfigManager v2 interface for use from Python"
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

# >>> Firebird 4
# IConfigManager(3) : IConfigManager(2)
class iConfigManager(iConfigManager_v2):
    "Class that wraps IConfigManager v3 interface for use from Python"
    VERSION = 3
    def get_default_security_db(self) -> str:
        "Returns default security database."
        return self.vtable.getDefaultSecurityDb(self).decode()

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
class iMessageMetadata_v3(iReferenceCounted):
    "Class that wraps IMessageMetadata v3 interface for use from Python"
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

# >>> Firebird 4
# IMessageMetadata(4) : IMessageMetadata(3)
class iMessageMetadata(iMessageMetadata_v3):
    "Class that wraps IMessageMetadata v4 interface for use from Python"
    VERSION = 4
    def get_alignment(self) -> int:
        "TODO"
        result = self.vtable.getAlignment(self, self.status)
        self._check()
        return result
    def get_aligned_length(self) -> int:
        "TODO"
        result = self.vtable.getAlignedLength(self, self.status)
        self._check()
        return result

# IMetadataBuilder(3) : ReferenceCounted
class iMetadataBuilder_v3(iReferenceCounted):
    "Class that wraps IMetadataBuilder v3 interface for use from Python"
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

# >>> Firebird 4
# IMetadataBuilder(4) : IMetadataBuilder(3)
class iMetadataBuilder(iMetadataBuilder_v3):
    "Class that wraps IMetadataBuilder v4 interface for use from Python"
    VERSION = 4
    def set_field(self, index: int, field: str) -> None:
        "Set field name"
        self.vtable.setField(self, self.status, index, field.encode())
        self._check()
    def set_relation(self, index: int, relation: str) -> None:
        "Set relation name"
        self.vtable.setRelation(self, self.status, index, relation.encode())
        self._check()
    def set_owner(self, index: int, owner: str) -> None:
        "Set owner name"
        self.vtable.setOwner(self, self.status, index, owner.encode())
        self._check()
    def set_alias(self, index: int, alias: str) -> None:
        "Set the alias"
        self.vtable.setAlias(self, self.status, index, alias.encode())
        self._check()

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
class iStatement_v3(iReferenceCounted):
    "Class that wraps IStatement v3 interface for use from Python"
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

# >>> Firebird 4
# IStatement(4) : IStatement(3)
class iStatement(iStatement_v3):
    "Class that wraps IStatement v4 interface for use from Python"
    VERSION = 4
    def get_timeout(self) -> int:
        "Return statement timeout"
        result = self.vtable.getTimeout(self, self.status)
        self._check()
        return result
    def set_timeout(self, timeout: int) -> None:
        "Set the statement timeout"
        self.vtable.setTimeout(self, self.status, timeout)
        self._check()
    def create_batch(self, in_meta: iMessageMetadata, params: bytes) -> iBatch:
        "Create new batch"
        result = self.vtable.createBatch(self, self.status, in_meta, len(params), params)
        self._check()
        return iBatch(result)

# IBatch(3) : ReferenceCounted
class iBatch(iReferenceCounted):
    "Class that wraps IBatch interface for use from Python"
    VERSION = 3
    def add(self, count: int, in_buffer: bytes) -> None:
        "TODO"
        self.vtable.add(self, self.status, count, in_buffer)
        self._check()
    def add_blob(self, length: int, in_buffer: bytes, id_: a.ISC_QUAD, params: bytes) -> None:
        "TODO"
        self.vtable.addBlob(self, self.status, length, in_buffer, byref(id_), len(params), params)
        self._check()
    def append_blob_data(self, length: int, in_buffer: bytes) -> None:
        "TODO"
        self.vtable.appendBlobData(self, self.status, length, in_buffer)
        self._check()
    def add_blob_stream(self, length: int, in_buffer: bytes) -> None:
        "TODO"
        self.vtable.addBlobStream(self, self.status, length, in_buffer)
        self._check()
    def register_blob(self, existing: a.ISC_QUAD, id_: a.ISC_QUAD):
        "TODO"
        self.vtable.registerBlob(self, self.status, byref(existing), byref(id_))
        self._check()
    def execute(self, transaction: iTransaction) -> iBatchCompletionState:
        "TODO"
        result = self.vtable.execute(self, self.status, transaction)
        self._check()
        return iBatchCompletionState(result)
    def cancel(self) -> None:
        "TODO"
        self.vtable.cancel(self, self.status)
        self._check()
    def get_blob_alignment(self) -> int:
        "TODO"
        result = self.vtable.getBlobAlignment(self, self.status)
        self._check()
        return result
    def get_metadata(self) -> iMessageMetadata:
        "TODO"
        result = self.vtable.getMetadata(self, self.status)
        self._check()
        return iMessageMetadata(result)
    def set_default_bpb(self, bpb: bytes) -> None:
        "TODO"
        self.vtable.setDefaultBpb(self, self.status, len(bpb), bpb)
        self._check()

# IBatchCompletionState(3) : Disposable
class iBatchCompletionState(iDisposable):
    "Class that wraps IBatchCompletionState interface for use from Python"
    VERSION = 3
    def get_size(self) -> int:
        "TODO"
        result = self.vtable.getSize(self, self.status)
        self._check()
        return result
    def get_state(self, pos: int) -> int:
        "TODO"
        result = self.vtable.getState(self, self.status, pos)
        self._check()
        return result
    def find_error(self, pos: int) -> int:
        "TODO"
        result = self.vtable.findError(self, self.status, pos)
        self._check()
        return result
    def get_status(self, result: iStatus, pos: int) -> None:
        "TODO"
        self.vtable.getStatus(self, self.status, result, pos)
        self._check()

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
class iAttachment_v3(iReferenceCounted):
    "Class that wraps IAttachment v3 interface for use from Python"
    VERSION = 3
    def __init__(self, intf):
        super().__init__(intf)
        #: Encoding used for string values
        self.encoding: str = 'ascii'
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
        b_stmt: bytes = stmt.encode(self.encoding)
        result = self.vtable.prepare(self, self.status, transaction, len(b_stmt), b_stmt,
                                     dialect, flags)
        self._check()
        return iStatement(result)
    def execute(self, transaction: iTransaction, stmt: str, dialect: int,
                in_metadata: iMessageMetadata = None, in_buffer: bytes = None,
                out_metadata: iMessageMetadata = None, out_buffer: bytes = None) -> None:
        """Executes any SQL statement except returning multiple rows of data.
Partial analogue of `isc_dsql_execute2()` - in and out XSLQDAs replaced with
input and output messages with appropriate buffers."""
        b_stmt: bytes = stmt.encode(self.encoding)
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
        b_stmt: bytes = stmt.encode(self.encoding)
        result = self.vtable.openCursor(self, self.status, transaction, len(b_stmt), b_stmt,
                                        dialect, in_metadata, in_buffer, out_metadata,
                                        cursor_name.encode(self.encoding), cursor_flags)
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
        self._refcnt -= 1
    def drop_database(self) -> None:
        "Replaces `isc_drop_database()`. On success releases interface."
        self.vtable.dropDatabase(self, self.status)
        self._check()
        self._refcnt -= 1

# >>> Firebird 4
# IAttachment(4) : IAttachment(3)
class iAttachment(iAttachment_v3):
    "Class that wraps IAttachment v4 interface for use from Python"
    VERSION = 4
    def get_idle_timeout(self) -> int:
        "TODO"
        result = self.vtable.getIdleTimeout(self, self.status)
        self._check()
        return result
    def set_idle_timeout(self, timeout: int) -> None:
        "TODO"
        self.vtable.setIdleTimeout(self, self.status, timeout)
        self._check()
    def get_statement_timeout(self) -> int:
        "TODO"
        result = self.vtable.getStatementTimeout(self, self.status)
        self._check()
        return result
    def set_statement_timeout(self, timeout: int) -> None:
        "TODO"
        self.vtable.setStatementTimeout(self, self.status, timeout)
        self._check()
    def create_batch(self, transaction: iTransaction, stmt: str, dialect: int,
                     in_metadata: iMessageMetadata, params: bytes) -> iBatch:
        "TODO"
        b_stmt: bytes = stmt.encode(self.encoding)
        result = self.vtable.createBatch(self, self.status, transaction, len(b_stmt), b_stmt,
                                         dialect, in_metadata, len(params), params)
        self._check()
        return iBatch(result)

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
    def insert_string(self, tag: int, value: str, *, encoding: str='ascii', errors: str='strict') -> None:
        "Inserts a clumplet with value containing passed string."
        self.vtable.insertString(self, self.status, tag, value.encode(encoding, errors))
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
    def get_string(self, *, encoding: str='ascii', errors: str='strict') -> str:
        "Returns value of current clumplet as string."
        result = self.vtable.getString(self, self.status)
        self._check()
        return string_at(result).decode(encoding, errors)
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
class iUtil_v2(iVersioned):
    "Class that wraps IUtil v2 interface for use from Python"
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
        return datetime.time(hours.value, minutes.value, seconds.value, fractions.value * 100)
    def encode_date(self, date: datetime.date) -> a.ISC_DATE:
        "Replaces `isc_encode_sql_date()`"
        return self.vtable.encodeDate(self, date.year, date.month, date.day)
    def encode_time(self, atime: datetime.time) -> a.ISC_TIME:
        "Replaces isc_encode_sql_time()"
        return self.vtable.encodeTime(self, atime.hour, atime.minute, atime.second, int(atime.microsecond / 100))
    def format_status(self, status: iStatus, encoding: str=a.err_encoding) -> str:
        "Replaces `fb_interpret()`."
        buffer = create_string_buffer(1024)
        self.vtable.formatStatus(self, buffer, 1024, status)
        return buffer.value.decode(encoding, errors='replace')
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

# >>> Firebird 4
# IUtil(4) : IUtil(2)
class iUtil(iUtil_v2):
    "Class that wraps IUtil v4 interface for use from Python"
    VERSION = 4
    STR_SIZE = 200
    def __init__(self, intf):
        super().__init__(intf)
        self.year = a.Cardinal(0)
        self.month = a.Cardinal(0)
        self.day = a.Cardinal(0)
        self.hours = a.Cardinal(0)
        self.minutes = a.Cardinal(0)
        self.seconds = a.Cardinal(0)
        self.fractions = a.Cardinal(0)
        self.str_buf = create_string_buffer(self.STR_SIZE)
        self.time_tz = create_string_buffer(sizeof(a.ISC_TIME_TZ()))
        self.timestamp_tz = create_string_buffer(sizeof(a.ISC_TIMESTAMP_TZ()))
    def get_decfloat16(self) -> iDecFloat16:
        "Returns iDecFloat16 interface."
        result = self.vtable.getDecFloat16(self, self.status)
        self._check()
        return iDecFloat16(result)
    def get_decfloat34(self) -> iDecFloat34:
        "Returns iDecFloat34 interface."
        result = self.vtable.getDecFloat34(self, self.status)
        self._check()
        return iDecFloat34(result)
    def decode_time_tz(self, timetz: Union[a.ISC_TIME_TZ, bytes]) -> datetime.time:
        "Decodes TIME WITH TIMEZONE from internal format to datetime.time with tzinfo."
        if isinstance(timetz, bytes):
            timetz = a.ISC_TIME_TZ.from_buffer_copy(timetz)
        self.hours.value = 0
        self.minutes.value = 0
        self.seconds.value = 0
        self.fractions.value = 0
        memset(self.str_buf, 0, self.STR_SIZE)
        # procedure decodeTimeTz(this: IUtil; status: IStatus; timeTz: ISC_TIME_TZPtr;
        #                        hours: CardinalPtr; minutes: CardinalPtr;
        #                        seconds: CardinalPtr; fractions: CardinalPtr;
        #                        timeZoneBufferLength: Cardinal; timeZoneBuffer: PAnsiChar)
        self.vtable.decodeTimeTz(self, self.status, byref(timetz), byref(self.hours),
                                 byref(self.minutes), byref(self.seconds), byref(self.fractions),
                                 self.STR_SIZE, self.str_buf)
        self._check()
        tz = get_timezone(self.str_buf.value.decode())
        return datetime.time(self.hours.value, self.minutes.value, self.seconds.value,
                             self.fractions.value * 100, tz)
    def decode_timestamp_tz(self, timestamptz: Union[a.ISC_TIMESTAMP_TZ, bytes]) -> datetime.datetime:
        "Decodes TIMESTAMP WITH TIMEZONE from internal format to datetime.datetime with tzinfo."
        if isinstance(timestamptz, bytes):
            timestamptz = a.ISC_TIMESTAMP_TZ.from_buffer_copy(timestamptz)
        self.year.value = 0
        self.month.value = 0
        self.day.value = 0
        self.hours.value = 0
        self.minutes.value = 0
        self.seconds.value = 0
        self.fractions.value = 0
        memset(self.str_buf, 0, self.STR_SIZE)
        # procedure decodeTimeStampTz(this: IUtil; status: IStatus; timeStampTz: ISC_TIMESTAMP_TZPtr;
        #                             year: CardinalPtr; month: CardinalPtr; day: CardinalPtr;
        #                             hours: CardinalPtr; minutes: CardinalPtr;
        #                             seconds: CardinalPtr; fractions: CardinalPtr;
        #                             timeZoneBufferLength: Cardinal; timeZoneBuffer: PAnsiChar)
        self.vtable.decodeTimeStampTz(self, self.status, byref(timestamptz), byref(self.year),
                                      byref(self.month), byref(self.day), byref(self.hours),
                                      byref(self.minutes), byref(self.seconds), byref(self.fractions),
                                      self.STR_SIZE, self.str_buf)
        self._check()
        tz = get_timezone(self.str_buf.value.decode())
        return datetime.datetime(self.year.value, self.month.value, self.day.value,
                                 self.hours.value, self.minutes.value, self.seconds.value,
                                 self.fractions.value * 100, tz)
    def encode_time_tz(self, time: datetime.time) -> bytes:
        "Encodes datetime.time with tzinfo into internal format for TIME WITH TIMEZONE."
        tzname = getattr(time.tzinfo, '_timezone_', None)
        if not tzname:
            raise InterfaceError("Time timezone not set or does not have a name")
        self.str_buf.value = tzname.encode()
        memset(self.time_tz, 0, 8)
        # procedure encodeTimeTz(this: IUtil; status: IStatus; timeTz: ISC_TIME_TZPtr;
        #                        hours: Cardinal; minutes: Cardinal; seconds: Cardinal;
        #                        fractions: Cardinal; timeZone: PAnsiChar)
        self.vtable.encodeTimeTz(self, self.status, cast(self.time_tz, a.ISC_TIME_TZ_PTR),
                                 time.hour, time.minute, time.second, time.microsecond // 100, self.str_buf)
        self._check()
        return self.time_tz.raw
    def encode_timestamp_tz(self, timestamp: datetime.datetime) -> bytes:
        "Encodes datetime.datetime with tzinfo into internal format for TIMESTAMP WITH TIMEZONE."
        tzname = getattr(timestamp.tzinfo, '_timezone_', None)
        if not tzname:
            raise InterfaceError("Datetime timezone not set or does not have a name")
        self.str_buf.value = tzname.encode()
        memset(self.timestamp_tz, 0, 12)
        # procedure encodeTimeStampTz(this: IUtil; status: IStatus; timeStampTz: ISC_TIMESTAMP_TZPtr;
        #                             year: Cardinal; month: Cardinal; day: Cardinal;
        #                             hours: Cardinal; minutes: Cardinal; seconds: Cardinal;
        #                             fractions: Cardinal; timeZone: PAnsiChar)
        self.vtable.encodeTimeStampTz(self, self.status, cast(self.timestamp_tz, a.ISC_TIMESTAMP_TZ_PTR),
                                      timestamp.year, timestamp.month, timestamp.day,
                                      timestamp.hour, timestamp.minute, timestamp.second,
                                      timestamp.microsecond // 100, self.str_buf)
        self._check()
        return self.timestamp_tz.raw
    def get_int128(self) -> iInt128:
        "Returns iInt128 interface."
        result = self.vtable.getInt128(self, self.status)
        self._check()
        return iInt128(result)
    def decode_time_tz_ex(self, timetz: a.ISC_TIME_TZ_EX, hours: a.Cardinal, minutes: a.Cardinal,
                          seconds: a.Cardinal, fractions: a.Cardinal, zone_bufer: bytes):
        "TODO"
        # procedure decodeTimeTzEx(this: IUtil; status: IStatus; timeTz: ISC_TIME_TZ_EXPtr;
        #                          hours: CardinalPtr; minutes: CardinalPtr; seconds: CardinalPtr;
        #                          fractions: CardinalPtr; timeZoneBufferLength: Cardinal;
        #                          timeZoneBuffer: PAnsiChar)
        self.vtable.decodeTimeTzEx(self, self.status, byref(timetz), byref(hours),
                                 byref(minutes), byref(seconds), byref(fractions),
                                 len(zone_bufer), zone_bufer)
        self._check()
    def decode_timestamp_tz_ex(self, timestamptz: a.ISC_TIMESTAMP_TZ_EX, year: a.Cardinal,
                               month: a.Cardinal, day: a.Cardinal, hours: a.Cardinal,
                               minutes: a.Cardinal, seconds: a.Cardinal, fractions: a.Cardinal,
                               zone_bufer: bytes):
        "TODO"
        # procedure decodeTimeStampTzEx(this: IUtil; status: IStatus; timeStampTz: ISC_TIMESTAMP_TZ_EXPtr;
        #                               year: CardinalPtr; month: CardinalPtr; day: CardinalPtr;
        #                               hours: CardinalPtr; minutes: CardinalPtr;
        #                               seconds: CardinalPtr; fractions: CardinalPtr;
        #                               timeZoneBufferLength: Cardinal; timeZoneBuffer: PAnsiChar)
        self.vtable.decodeTimeStampTzEx(self, self.status, byref(timestamptz), byref(year),
                                        byref(month), byref(day), byref(hours),
                                        byref(minutes), byref(seconds), byref(fractions),
                                        len(zone_bufer), zone_bufer)
        self._check()

# IDecFloat16(2) : Versioned
class iDecFloat16(iVersioned):
    "Class that wraps IDecFloat16 interface for use from Python"
    VERSION = 2
    BCD_SIZE = 16
    STR_SIZE = 24
    def __init__(self, intf):
        super().__init__(intf)
        self.sign = a.Int(0)
        self.exp = a.Int(0)
        self.bcd = create_string_buffer(self.STR_SIZE)
        self.str_buf = create_string_buffer(self.STR_SIZE)
    def to_bcd(self, value: a.FB_DEC16) -> BCD:
        "Convert decimal float value to BCD"
        # procedure toBcd(this: IDecFloat16; from: FB_DEC16Ptr; sign: IntegerPtr; bcd: BytePtr; exp: IntegerPtr)
        self.sign.value = 0
        self.exp.value = 0
        memset(self.bcd, 0, self.BCD_SIZE)
        self.vtable.toBcd(self, byref(value), byref(self.sign), self.bcd, byref(self.exp))
        return BCD(self.sign.value, self.bcd.value, self.exp.value)
    def to_str(self, value: a.FB_DEC16) -> str:
        "Convert decimal float value to string"
        # procedure toString(this: IDecFloat16; status: IStatus; from: FB_DEC16Ptr; bufferLength: Cardinal; buffer: PAnsiChar)
        memset(self.str_buf, 0, self.STR_SIZE)
        self.vtable.toString(self, self.status, byref(value), self.STR_SIZE, self.str_buf)
        self._check()
        return self.str_buf.value.decode()
    def from_bcd(self, value: BCD, into: a.FB_DEC16=None) -> a.FB_DEC16:
        "Make decimal float value from BCD"
        # procedure fromBcd(this: IDecFloat16; sign: Integer; bcd: BytePtr; exp: Integer; to_: FB_DEC16Ptr)
        result = a.FB_DEC16(0) if into is None else into
        self.vtable.fromBcd(self, value.sign, value.number, value.exp, byref(result))
        return result
    def from_str(self, value: str, into: a.FB_DEC16=None) -> a.FB_DEC16:
        "Make decimal float value from string"
        # procedure fromString(this: IDecFloat16; status: IStatus; from: PAnsiChar; to_: FB_DEC16Ptr)
        result = a.FB_DEC16(0) if into is None else into
        self.vtable.fromString(self, self.status, value.encode(), byref(result))
        self._check()
        return result

# IDecFloat34(2) : Versioned
class iDecFloat34(iVersioned):
    "Class that wraps IDecFloat34 interface for use from Python"
    VERSION = 2
    BCD_SIZE = 34
    STR_SIZE = 43
    def __init__(self, intf):
        super().__init__(intf)
        self.sign = a.Int(0)
        self.exp = a.Int(0)
        self.bcd = create_string_buffer(self.STR_SIZE)
        self.str_buf = create_string_buffer(self.STR_SIZE)
    def to_bcd(self, value: a.FB_DEC34) -> BCD:
        "Convert decimal float value to BCD"
        # procedure toBcd(this: IDecFloat34; from: FB_DEC34Ptr; sign: IntegerPtr; bcd: BytePtr; exp: IntegerPtr)
        self.sign.value = 0
        self.exp.value = 0
        memset(self.bcd, 0, self.BCD_SIZE)
        self.vtable.toBcd(self, byref(value), byref(self.sign), self.bcd, byref(self.exp))
        return BCD(self.sign.value, self.bcd.value, self.exp.value)
    def to_str(self, value: a.FB_DEC34) -> str:
        "Convert decimal float value to string"
        # procedure toString(this: IDecFloat34; status: IStatus; from: FB_DEC34Ptr; bufferLength: Cardinal; buffer: PAnsiChar)
        memset(self.str_buf, 0, self.STR_SIZE)
        self.vtable.toString(self, self.status, byref(value), self.STR_SIZE, self.str_buf)
        self._check()
        return self.str_buf.value.decode()
    def from_bcd(self, value: BCD, into: a.FB_DEC34=None) -> a.FB_DEC34:
        "Make decimal float value from BCD"
        # procedure fromBcd(this: IDecFloat34; sign: Integer; bcd: BytePtr; exp: Integer; to_: FB_DEC34Ptr)
        result = a.FB_DEC34(0) if into is None else into
        self.vtable.fromBcd(self, value.sign, value.number, value.exp, byref(result))
        return result
    def from_str(self, value: str, into: a.FB_DEC34=None) -> a.FB_DEC34:
        "Make decimal float value from string"
        # procedure fromString(this: IDecFloat34; status: IStatus; from: PAnsiChar; to_: FB_DEC34Ptr)
        result = a.FB_DEC34(0) if into is None else into
        self.vtable.fromString(self, self.status, value.encode(), byref(result))
        self._check()
        return result

# IInt128(2) : Versioned
class iInt128(iVersioned):
    "Class that wraps IInt128 interface for use from Python"
    VERSION = 2
    STR_SIZE = 46
    def __init__(self, intf):
        super().__init__(intf)
        self.str_buf = create_string_buffer(self.STR_SIZE)
    def to_str(self, value: a.FB_I128, scale: int) -> str:
        # procedure toString(this: IInt128; status: IStatus; from: FB_I128Ptr; scale: Integer; bufferLength: Cardinal; buffer: PAnsiChar)
        memset(self.str_buf, 0, self.STR_SIZE)
        self.vtable.toString(self, self.status, byref(value), scale, self.STR_SIZE, self.str_buf)
        self._check()
        return self.str_buf.value.decode()
    def from_str(self, value: str, scale: int, into: a.FB_I128=None) -> a.FB_I128:
        # procedure fromString(this: IInt128; status: IStatus; scale: Integer; from: PAnsiChar; to_: FB_I128Ptr)
        result = a.FB_I128(0) if into is None else into
        self.vtable.fromString(self, self.status, scale, value.encode(), byref(result))
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

add_hook(APIHook.LOADED, a.FirebirdAPI, __augment_api)
