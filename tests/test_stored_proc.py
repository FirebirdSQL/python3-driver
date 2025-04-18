# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_stored_proc.py
#   DESCRIPTION:    Tests for stored procedures
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

import decimal
import pytest
from firebird.driver import InterfaceError

def test_callproc(db_connection):
    with db_connection.cursor() as cur:
        # Test with string parameter
        cur.callproc('sub_tot_budget', ['100'])
        result = cur.fetchone()
        assert result == (decimal.Decimal('3800000.00'), decimal.Decimal('760000.00'),
                          decimal.Decimal('500000.00'), decimal.Decimal('1500000.00'))

        # Test with integer parameter
        cur.callproc('sub_tot_budget', [100])
        result = cur.fetchone()
        assert result == (decimal.Decimal('3800000.00'), decimal.Decimal('760000.00'),
                          decimal.Decimal('500000.00'), decimal.Decimal('1500000.00'))

        # Test procedure with side effect (no output params expected)
        cur.callproc('proc_test', [10])
        result = cur.fetchone() # Fetchone after EXEC PROC should be None if no output params
        assert result is None
        db_connection.commit() # Commit the side effect

        # Verify side effect
        cur.execute('select c1 from t')
        result = cur.fetchone()
        assert result == (10,)
