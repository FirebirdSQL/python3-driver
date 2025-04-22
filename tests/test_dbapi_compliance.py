# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_dbapi_compliance.py
#   DESCRIPTION:    Tests for Python DB API 2.0 compliance
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
import firebird.driver as driver
import decimal
import datetime

def test_module_attributes():
    """Verify required DB API 2.0 module attributes."""
    assert hasattr(driver, 'apilevel'), "Module lacks 'apilevel' attribute"
    assert driver.apilevel == '2.0', "apilevel is not '2.0'"

    assert hasattr(driver, 'threadsafety'), "Module lacks 'threadsafety' attribute"
    assert isinstance(driver.threadsafety, int), "threadsafety is not an integer"
    assert driver.threadsafety in (0, 1, 2, 3), "threadsafety not in allowed range (0-3)"
    # firebird-driver is expected to be 1
    assert driver.threadsafety == 1, "Expected threadsafety level 1"

    assert hasattr(driver, 'paramstyle'), "Module lacks 'paramstyle' attribute"
    assert isinstance(driver.paramstyle, str), "paramstyle is not a string"
    allowed_paramstyles = ('qmark', 'numeric', 'named', 'format', 'pyformat')
    assert driver.paramstyle in allowed_paramstyles, f"paramstyle '{driver.paramstyle}' not in allowed styles"
    # firebird-driver uses qmark
    assert driver.paramstyle == 'qmark', "Expected paramstyle 'qmark'"

def test_module_connect():
    """Verify module has a connect() method."""
    assert hasattr(driver, 'connect'), "Module lacks 'connect' method"
    assert callable(driver.connect), "'connect' is not callable"

def test_module_exceptions():
    """Verify required DB API 2.0 exception hierarchy."""
    # Check existence
    assert hasattr(driver, 'Error'), "Module lacks 'Error' exception"
    assert hasattr(driver, 'InterfaceError'), "Module lacks 'InterfaceError' exception"
    assert hasattr(driver, 'DatabaseError'), "Module lacks 'DatabaseError' exception"
    assert hasattr(driver, 'DataError'), "Module lacks 'DataError' exception"
    assert hasattr(driver, 'OperationalError'), "Module lacks 'OperationalError' exception"
    assert hasattr(driver, 'IntegrityError'), "Module lacks 'IntegrityError' exception"
    assert hasattr(driver, 'InternalError'), "Module lacks 'InternalError' exception"
    assert hasattr(driver, 'ProgrammingError'), "Module lacks 'ProgrammingError' exception"
    assert hasattr(driver, 'NotSupportedError'), "Module lacks 'NotSupportedError' exception"

    # Check hierarchy
    assert issubclass(driver.Error, Exception), "Error does not inherit from Exception"
    assert issubclass(driver.InterfaceError, driver.Error), "InterfaceError does not inherit from Error"
    assert issubclass(driver.DatabaseError, driver.Error), "DatabaseError does not inherit from Error"
    assert issubclass(driver.DataError, driver.DatabaseError), "DataError does not inherit from DatabaseError"
    assert issubclass(driver.OperationalError, driver.DatabaseError), "OperationalError does not inherit from DatabaseError"
    assert issubclass(driver.IntegrityError, driver.DatabaseError), "IntegrityError does not inherit from DatabaseError"
    assert issubclass(driver.InternalError, driver.DatabaseError), "InternalError does not inherit from DatabaseError"
    assert issubclass(driver.ProgrammingError, driver.DatabaseError), "ProgrammingError does not inherit from DatabaseError"
    assert issubclass(driver.NotSupportedError, driver.DatabaseError), "NotSupportedError does not inherit from DatabaseError"

def test_connection_interface(db_connection):
    """Verify required DB API 2.0 Connection attributes and methods."""
    con = db_connection # Use the fixture

    # Required methods
    assert hasattr(con, 'close'), "Connection lacks 'close' method"
    assert callable(con.close), "'close' is not callable"

    assert hasattr(con, 'commit'), "Connection lacks 'commit' method"
    assert callable(con.commit), "'commit' is not callable"

    assert hasattr(con, 'rollback'), "Connection lacks 'rollback' method"
    assert callable(con.rollback), "'rollback' is not callable"

    assert hasattr(con, 'cursor'), "Connection lacks 'cursor' method"
    assert callable(con.cursor), "'cursor' is not callable"

    # Required exception attribute
    assert hasattr(con, 'Error'), "Connection lacks 'Error' attribute"
    assert con.Error is driver.Error, "Connection.Error is not the same as module.Error"

    # Context manager protocol (optional but good practice)
    assert hasattr(con, '__enter__'), "Connection lacks '__enter__' method"
    assert callable(con.__enter__), "'__enter__' is not callable"
    assert hasattr(con, '__exit__'), "Connection lacks '__exit__' method"
    assert callable(con.__exit__), "'__exit__' is not callable"

def test_cursor_attributes(db_connection):
    """Verify required DB API 2.0 Cursor attributes."""
    con = db_connection
    cur = None
    try:
        cur = con.cursor()

        # description attribute
        assert hasattr(cur, 'description'), "Cursor lacks 'description' attribute"
        assert cur.description is None, "Cursor.description should be None before execute"
        # Execute a simple query to populate description
        cur.execute("SELECT 1 AS N, 'a' AS S FROM RDB$DATABASE")
        assert isinstance(cur.description, tuple), "Cursor.description is not a tuple after execute"
        assert len(cur.description) == 2, "Cursor.description has wrong length"
        # Check basic structure of a description entry
        desc_entry = cur.description[0]
        assert isinstance(desc_entry, tuple), "Description entry is not a tuple"
        assert len(desc_entry) == 7, "Description entry does not have 7 elements"
        assert isinstance(desc_entry[driver.DESCRIPTION_NAME], str), "Description name is not a string"
        assert issubclass(desc_entry[driver.DESCRIPTION_TYPE_CODE], (int, float, decimal.Decimal, str, bytes, datetime.date, datetime.time, datetime.datetime, list, type(None))), "Description type_code is not a valid type"
        # Allow None or int for optional size fields
        assert desc_entry[driver.DESCRIPTION_DISPLAY_SIZE] is None or isinstance(desc_entry[driver.DESCRIPTION_DISPLAY_SIZE], int)
        assert desc_entry[driver.DESCRIPTION_INTERNAL_SIZE] is None or isinstance(desc_entry[driver.DESCRIPTION_INTERNAL_SIZE], int)
        # Allow None or int for precision/scale
        assert desc_entry[driver.DESCRIPTION_PRECISION] is None or isinstance(desc_entry[driver.DESCRIPTION_PRECISION], int)
        assert desc_entry[driver.DESCRIPTION_SCALE] is None or isinstance(desc_entry[driver.DESCRIPTION_SCALE], int)
        assert isinstance(desc_entry[driver.DESCRIPTION_NULL_OK], bool), "Description null_ok is not a boolean"


        # rowcount attribute
        assert hasattr(cur, 'rowcount'), "Cursor lacks 'rowcount' attribute"
        # Note: rowcount is -1 before fetch for SELECT, or affected rows for DML
        assert isinstance(cur.rowcount, int), "Cursor.rowcount is not an integer"

        # arraysize attribute
        assert hasattr(cur, 'arraysize'), "Cursor lacks 'arraysize' attribute"
        assert isinstance(cur.arraysize, int), "Cursor.arraysize is not an integer"
        assert cur.arraysize >= 1, "Cursor.arraysize must be >= 1"

    finally:
        if cur and not cur.is_closed():
            cur.close()

def test_cursor_methods(db_connection):
    """Verify required DB API 2.0 Cursor methods."""
    con = db_connection
    cur = None
    try:
        cur = con.cursor()

        assert hasattr(cur, 'close'), "Cursor lacks 'close' method"
        assert callable(cur.close), "'close' is not callable"

        assert hasattr(cur, 'execute'), "Cursor lacks 'execute' method"
        assert callable(cur.execute), "'execute' is not callable"

        assert hasattr(cur, 'fetchone'), "Cursor lacks 'fetchone' method"
        assert callable(cur.fetchone), "'fetchone' is not callable"

        # Optional but common methods
        assert hasattr(cur, 'executemany'), "Cursor lacks 'executemany' method"
        assert callable(cur.executemany), "'executemany' is not callable"

        assert hasattr(cur, 'fetchall'), "Cursor lacks 'fetchall' method"
        assert callable(cur.fetchall), "'fetchall' is not callable"

        assert hasattr(cur, 'fetchmany'), "Cursor lacks 'fetchmany' method"
        assert callable(cur.fetchmany), "'fetchmany' is not callable"

        assert hasattr(cur, 'setinputsizes'), "Cursor lacks 'setinputsizes' method"
        assert callable(cur.setinputsizes), "'setinputsizes' is not callable"

        assert hasattr(cur, 'setoutputsize'), "Cursor lacks 'setoutputsize' method"
        assert callable(cur.setoutputsize), "'setoutputsize' is not callable"

    finally:
        if cur and not cur.is_closed():
            cur.close()
