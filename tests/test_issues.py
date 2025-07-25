# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_issues.py
#   DESCRIPTION:    Tests for tracker issues
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

def test_issue_02(db_connection):
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C2,C3) values (?,?,?)', [1, None, 1])
        db_connection.commit()
        cur.execute('select C1,C2,C3 from T2 where C1 = 1')
        rows = cur.fetchall()
        assert rows == [(1, None, 1)]

def test_issue_53(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("select cast('0.00' as numeric(9,2)) from rdb$database")
        numeric_val = cur.fetchone()[0]
        numeric_val_exponent = numeric_val.as_tuple()[2]
        db_connection.commit()
        assert numeric_val_exponent == -2
