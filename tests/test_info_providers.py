# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_info_providers.py
#   DESCRIPTION:    Tests for information providers
#   CREATED:        10.4.2025
#
#  Software distributed under the License is distributed AS IS,
#  WITHOUT WARRANTY OF ANY KIND, either express or implied.
#  See the License for the specific language governing rights
#  and limitations under the License.
#
#  The Original Code was created by Pavel Cisar
#
#  Copyright (c) Pavel Cisar <pcisar@users.sourceforge.net>
#  and all contributors signed below.
#
#  All Rights Reserved.
#  Contributor(s): ______________________________________.
#
# See LICENSE.TXT for details.

import pytest
import datetime
import decimal
from enum import IntFlag, Enum
from packaging.specifiers import SpecifierSet
from firebird.driver import (connect, tpb, connect_server, NotSupportedError,
                             DbInfoCode, TraInfoCode, StmtInfoCode, SrvInfoCode,
                             Isolation, TraInfoAccess, StatementType,
                             ReplicaMode, Features, InterfaceError, DatabaseError,
                             ConnectionFlag, EncryptionFlag)
from firebird.driver.types import (DbProvider, DbClass, StateResult, StatementFlag,
                                   ReqInfoCode, ServerCapability, SrvDbInfoOption, ImpData,
                                   ImpDataOld)
from firebird.driver.core import Statement # To check instance type

# --- Fixtures ---

@pytest.fixture()
def prepared_statement(db_connection):
    """Provides a prepared statement for statement info tests."""
    # Need a transaction active for prepare
    with db_connection.transaction_manager() as tm:
        with tm.cursor() as cur:
            stmt = cur.prepare("SELECT * FROM RDB$DATABASE")
            yield stmt
            # Cleanup happens automatically when cursor/transaction/connection closes

# --- Version Requirement Sets ---

DBINFO_FB4_PLUS = {
    DbInfoCode.SES_IDLE_TIMEOUT_DB,
    DbInfoCode.SES_IDLE_TIMEOUT_ATT,
    DbInfoCode.SES_IDLE_TIMEOUT_RUN,
    DbInfoCode.STMT_TIMEOUT_DB,
    DbInfoCode.STMT_TIMEOUT_ATT,
    DbInfoCode.PROTOCOL_VERSION,
    DbInfoCode.CRYPT_PLUGIN,
    DbInfoCode.CREATION_TIMESTAMP_TZ,
    DbInfoCode.WIRE_CRYPT,
    DbInfoCode.FEATURES,
    DbInfoCode.NEXT_ATTACHMENT,
    DbInfoCode.NEXT_STATEMENT,
    DbInfoCode.DB_GUID,
    DbInfoCode.DB_FILE_ID,
    DbInfoCode.REPLICA_MODE,
    DbInfoCode.USER_NAME,
    DbInfoCode.SQL_ROLE,
}
DBINFO_FB5_PLUS = set() # Add FB5 codes here when known

TRAINFO_FB4_PLUS = {
    TraInfoCode.SNAPSHOT_NUMBER,
}
TRAINFO_FB5_PLUS = set()

STMTINFO_FB4_PLUS = {
    StmtInfoCode.TIMEOUT_USER,
    StmtInfoCode.TIMEOUT_RUN,
    StmtInfoCode.BLOB_ALIGN,
}
STMTINFO_FB5_PLUS = {
    StmtInfoCode.EXEC_PATH_BLR_BYTES,
    StmtInfoCode.EXEC_PATH_BLR_TEXT,
}

# --- Helper Functions ---

def _check_info(provider, info_code, fb_version, required_version_set):
    """Helper to check supports() and get_info() based on version."""
    min_version = 4 if info_code in required_version_set else 3 # Basic assumption

    if fb_version not in SpecifierSet(f'>={min_version}.0'):
        assert not provider.supports(info_code)
        with pytest.raises(NotSupportedError):
            provider.get_info(info_code)
    else:
        assert provider.supports(info_code)
        try:
            # Use try-except as a safety net for get_info
            result = provider.get_info(info_code)
            # Basic type check - specific tests will assert details
            assert result is not None or isinstance(result, (int, str, float, bool, list, tuple, dict, bytes, datetime.date, datetime.time, datetime.datetime, decimal.Decimal, Enum, IntFlag))
        except NotSupportedError:
            # This might happen if the supports() logic is less strict than get_info()
            pytest.fail(f"get_info({info_code}) raised NotSupportedError unexpectedly for FB version {fb_version}")
    return True # Indicates check passed (or expected exception was raised)

# --- Test Functions ---

def test_database_info_provider(db_connection, fb_vars, db_file):
    """Test DatabaseInfoProvider get_info and supports."""
    info = db_connection.info
    version = fb_vars['version']
    version_spec = SpecifierSet(f'<={version.major}.{version.minor}') # e.g., >=4.0

    checked_codes = set()

    for code in DbInfoCode:
        checked_codes.add(code)
        min_version = 0
        if code in DBINFO_FB5_PLUS:
            min_version = 5
        elif code in DBINFO_FB4_PLUS:
            min_version = 4
        else:
            # Assume FB3 base for others, unless known otherwise
            # Add specific checks for older/obsolete codes if needed
            min_version = 3

        if code == DbInfoCode.PAGE_CONTENTS:
            # Special handling: requires page_number
            if version_spec.contains(str(min_version)):
                assert info.supports(code)
                # Test getting a specific page (e.g., header page 0)
                page_data = info.get_info(code, page_number=0)
                assert isinstance(page_data, bytes)
                assert len(page_data) == info.page_size # Verify length matches page size
            else:
                assert not info.supports(code)
                with pytest.raises(NotSupportedError):
                    info.get_info(code, page_number=0)
            continue # Skip the generic check below

        # Generic check using helper
        if version_spec.contains(str(min_version)):
            assert info.supports(code)
            try:
                result = info.get_info(code)
                # Assert Type based on code
                if code in [DbInfoCode.PAGE_SIZE, DbInfoCode.NUM_BUFFERS, DbInfoCode.SWEEP_INTERVAL,
                            DbInfoCode.ATTACHMENT_ID, DbInfoCode.DB_SQL_DIALECT, DbInfoCode.ODS_VERSION,
                            DbInfoCode.ODS_MINOR_VERSION, DbInfoCode.BASE_LEVEL, DbInfoCode.ACTIVE_TRAN_COUNT,
                            DbInfoCode.OLDEST_TRANSACTION, DbInfoCode.OLDEST_ACTIVE, DbInfoCode.OLDEST_SNAPSHOT,
                            DbInfoCode.NEXT_TRANSACTION, DbInfoCode.ALLOCATION, DbInfoCode.DB_SIZE_IN_PAGES,
                            DbInfoCode.PAGES_USED, DbInfoCode.PAGES_FREE, DbInfoCode.CURRENT_MEMORY,
                            DbInfoCode.MAX_MEMORY, DbInfoCode.READS, DbInfoCode.WRITES, DbInfoCode.FETCHES,
                            DbInfoCode.MARKS, DbInfoCode.PAGE_ERRORS, DbInfoCode.RECORD_ERRORS,
                            DbInfoCode.BPAGE_ERRORS, DbInfoCode.DPAGE_ERRORS, DbInfoCode.IPAGE_ERRORS,
                            DbInfoCode.PPAGE_ERRORS, DbInfoCode.TPAGE_ERRORS, DbInfoCode.ATT_CHARSET,
                            DbInfoCode.SES_IDLE_TIMEOUT_DB, DbInfoCode.SES_IDLE_TIMEOUT_ATT,
                            DbInfoCode.SES_IDLE_TIMEOUT_RUN, DbInfoCode.STMT_TIMEOUT_DB,
                            DbInfoCode.STMT_TIMEOUT_ATT, DbInfoCode.PROTOCOL_VERSION, DbInfoCode.NEXT_ATTACHMENT,
                            DbInfoCode.NEXT_STATEMENT]:
                    assert isinstance(result, int)
                elif code in [DbInfoCode.VERSION, DbInfoCode.FIREBIRD_VERSION, DbInfoCode.CRYPT_KEY,
                              DbInfoCode.CRYPT_PLUGIN, DbInfoCode.WIRE_CRYPT, DbInfoCode.DB_GUID,
                              DbInfoCode.DB_FILE_ID, DbInfoCode.USER_NAME, DbInfoCode.SQL_ROLE]:
                    assert isinstance(result, str)
                elif code == DbInfoCode.DB_ID:
                    assert isinstance(result, list)
                    assert len(result) >= 1
                    assert isinstance(result[0], str)
                elif code == DbInfoCode.IMPLEMENTATION:
                    assert isinstance(result, tuple)
                    if result: assert isinstance(result[0], ImpData)
                elif code == DbInfoCode.IMPLEMENTATION_OLD:
                    assert isinstance(result, tuple)
                    if result: assert isinstance(result[0], ImpDataOld)
                elif code in [DbInfoCode.USER_NAMES]:
                    assert isinstance(result, dict)
                elif code in [DbInfoCode.ACTIVE_TRANSACTIONS, DbInfoCode.LIMBO]:
                    assert isinstance(result, list) # Can be empty if none active/limbo
                    if result: assert isinstance(result[0], int)
                elif code in [DbInfoCode.NO_RESERVE, DbInfoCode.FORCED_WRITES, DbInfoCode.DB_READ_ONLY,
                              DbInfoCode.SET_PAGE_BUFFERS]: # These return 0 or 1
                    assert isinstance(result, int)
                elif code in [DbInfoCode.READ_SEQ_COUNT, DbInfoCode.READ_IDX_COUNT, DbInfoCode.INSERT_COUNT,
                              DbInfoCode.UPDATE_COUNT, DbInfoCode.DELETE_COUNT, DbInfoCode.BACKOUT_COUNT,
                              DbInfoCode.PURGE_COUNT, DbInfoCode.EXPUNGE_COUNT]:
                    assert isinstance(result, dict) # Table stats dict {rel_id: count}
                elif code == DbInfoCode.CREATION_DATE:
                    assert isinstance(result, datetime.date)
                elif code == DbInfoCode.DB_CLASS:
                    assert isinstance(result, DbClass)
                elif code == DbInfoCode.DB_PROVIDER:
                    assert isinstance(result, DbProvider)
                elif code == DbInfoCode.CRYPT_STATE:
                    assert isinstance(result, EncryptionFlag)
                elif code == DbInfoCode.CONN_FLAGS:
                    assert isinstance(result, ConnectionFlag)
                # FB4+
                elif code == DbInfoCode.CREATION_TIMESTAMP_TZ:
                    assert isinstance(result, datetime.datetime)
                    assert result.tzinfo is not None
                elif code == DbInfoCode.FEATURES:
                    assert isinstance(result, list)
                    if result: assert isinstance(result[0], Features)
                elif code == DbInfoCode.REPLICA_MODE:
                    assert isinstance(result, ReplicaMode)
                # Add more specific type checks as needed
            except NotSupportedError:
                pytest.fail(f"get_info({code}) raised NotSupportedError unexpectedly for FB version {version_spec}")
        else:
            assert not info.supports(code)
            with pytest.raises(NotSupportedError):
                info.get_info(code)

    # Ensure all codes were covered by the loop
    assert checked_codes == set(DbInfoCode)

def test_transaction_info_provider(db_connection, fb_vars):
    """Test TransactionInfoProvider get_info and supports."""
    version = fb_vars['version']
    version_spec = SpecifierSet(f'<={version.major}.{version.minor}')

    # Need an active transaction to test
    with db_connection.transaction_manager(tpb(Isolation.READ_COMMITTED)) as tm:
        info = tm.info
        checked_codes = set()

        for code in TraInfoCode:
            checked_codes.add(code)
            min_version = 4 if code in TRAINFO_FB4_PLUS else 3

            if version_spec.contains(str(min_version)):
                assert info.supports(code)
                try:
                    result = info.get_info(code)
                    # Assert Type based on code
                    if code in [TraInfoCode.ID, TraInfoCode.OLDEST_INTERESTING,
                                TraInfoCode.OLDEST_SNAPSHOT, TraInfoCode.OLDEST_ACTIVE,
                                TraInfoCode.LOCK_TIMEOUT]:
                        assert isinstance(result, int)
                    elif code == TraInfoCode.ISOLATION:
                        assert isinstance(result, Isolation)
                    elif code == TraInfoCode.ACCESS:
                        assert isinstance(result, TraInfoAccess)
                    elif code == TraInfoCode.DBPATH:
                        assert isinstance(result, str)
                    # FB4+
                    elif code == TraInfoCode.SNAPSHOT_NUMBER:
                        assert isinstance(result, int)
                except NotSupportedError:
                    pytest.fail(f"get_info({code}) raised NotSupportedError unexpectedly for FB version {version_spec}")
            else:
                assert not info.supports(code)
                with pytest.raises(NotSupportedError):
                    info.get_info(code)

        # Ensure all codes were covered
        assert checked_codes == set(TraInfoCode)

def test_statement_info_provider(prepared_statement, fb_vars):
    """Test StatementInfoProvider get_info and supports."""
    stmt_info = prepared_statement.info
    version = fb_vars['version']
    version_spec = SpecifierSet(f'<={version.major}.{version.minor}')
    checked_codes = set()

    for code in StmtInfoCode:
        checked_codes.add(code)
        min_version = 0
        if code in STMTINFO_FB5_PLUS:
            min_version = 5
        elif code in STMTINFO_FB4_PLUS:
            min_version = 4
        else:
            min_version = 3

        if version_spec.contains(str(min_version)):
            assert stmt_info.supports(code)
            try:
                result = stmt_info.get_info(code)
                # Assert Type based on code
                if code == StmtInfoCode.STMT_TYPE:
                    assert isinstance(result, StatementType)
                elif code in [StmtInfoCode.GET_PLAN, StmtInfoCode.EXPLAIN_PLAN]:
                    assert isinstance(result, str) or result is None # Plan might be None
                elif code == StmtInfoCode.RECORDS:
                    assert isinstance(result, dict)
                    if result: assert isinstance(list(result.keys())[0], ReqInfoCode)
                elif code == StmtInfoCode.BATCH_FETCH: # Not typically used/exposed?
                    assert isinstance(result, int)
                elif code == StmtInfoCode.FLAGS:
                    assert isinstance(result, StatementFlag)
                # FB4+
                elif code in [StmtInfoCode.TIMEOUT_USER, StmtInfoCode.TIMEOUT_RUN, StmtInfoCode.BLOB_ALIGN]:
                    assert isinstance(result, int)
                # FB5+
                elif code == StmtInfoCode.EXEC_PATH_BLR_BYTES:
                    assert isinstance(result, bytes)
                elif code == StmtInfoCode.EXEC_PATH_BLR_TEXT:
                    assert isinstance(result, str)
            except NotSupportedError:
                pytest.fail(f"get_info({code}) raised NotSupportedError unexpectedly for FB version {version_spec}")
        else:
            assert not stmt_info.supports(code)
            with pytest.raises(NotSupportedError):
                stmt_info.get_info(code)

    # Ensure all codes were covered
    assert checked_codes == set(StmtInfoCode)

def test_server_info_provider(server_connection, fb_vars):
    """Test ServerInfoProvider get_info."""
    # Note: ServerInfoProvider doesn't have a .supports() method in core.py v1.10
    info = server_connection.info
    version = fb_vars['version']
    version_spec = SpecifierSet(f'>={version.major}.{version.minor}')
    checked_codes = set()

    for code in SrvInfoCode:
        checked_codes.add(code)
        # ServerInfoProvider get_info is simpler, mostly strings or ints
        # It doesn't have the fine-grained version checks like others
        # We rely on the underlying service query to fail if not supported
        try:
            result = info.get_info(code)

            # Assert Type based on code
            if code in [SrvInfoCode.VERSION, SrvInfoCode.CAPABILITIES, SrvInfoCode.RUNNING]: # GET_CONFIG might not be implemented/useful this way
                assert isinstance(result, int)
            elif code in [SrvInfoCode.SERVER_VERSION, SrvInfoCode.IMPLEMENTATION,
                          SrvInfoCode.GET_ENV, SrvInfoCode.GET_ENV_MSG, SrvInfoCode.GET_ENV_LOCK,
                          SrvInfoCode.USER_DBPATH]:
                assert isinstance(result, str)
            elif code == SrvInfoCode.SRV_DB_INFO:
                assert isinstance(result, tuple)
                assert len(result) == 2
                assert isinstance(result[0], int) # num_attachments
                assert isinstance(result[1], list) # databases
            #elif code == SrvInfoCode.LIMBO_TRANS: # Often requires specific setup
            #    assert isinstance(result, list)
            elif code == SrvInfoCode.GET_USERS: # Complex fetch needed, not via simple get_info
                with pytest.raises(InterfaceError): # Expect this to fail via simple get_info
                    info.get_info(code)
            elif code in [SrvInfoCode.LINE, SrvInfoCode.TO_EOF, SrvInfoCode.TIMEOUT,
                          SrvInfoCode.AUTH_BLOCK, SrvInfoCode.STDIN]:
                # These are typically used internally or for service interaction,
                # calling get_info directly might not be meaningful or may error
                with pytest.raises(InterfaceError): # Expect failure for direct call
                    info.get_info(code)
            else:
                # Default check if code isn't specifically handled above
                assert result is not None or isinstance(result, (int, str, list, tuple))

        except (InterfaceError, DatabaseError) as e:
            # Allow specific errors for codes not meant for direct get_info
            if code not in [SrvInfoCode.GET_USERS, SrvInfoCode.LINE, SrvInfoCode.TO_EOF,
                            SrvInfoCode.TIMEOUT, SrvInfoCode.AUTH_BLOCK, SrvInfoCode.STDIN]:
                pytest.fail(f"get_info({code}) raised an unexpected error: {e}")
        except NotSupportedError:
            # Should not happen with ServerInfoProvider as it lacks fine-grained checks
            pytest.fail(f"get_info({code}) raised NotSupportedError unexpectedly for FB version {version_spec}")


    # Ensure all codes were covered
    assert checked_codes == set(SrvInfoCode)
