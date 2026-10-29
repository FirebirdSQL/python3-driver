# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT

from contextlib import ExitStack, contextmanager
from ctypes import c_long
from io import StringIO
from unittest.mock import Mock, PropertyMock, patch

import pytest

from firebird.driver import DatabaseError, DistributedTransactionManager, connect, interfaces
from firebird.driver.types import StateFlag


@contextmanager
def error_status(code):
    status = Mock()
    status.get_state.return_value = StateFlag.ERRORS
    status.get_errors.return_value = (c_long * 3)(1, code, 0)
    with ExitStack() as stack:
        stack.enter_context(patch.object(interfaces.iVersioned, 'status',
                                         new_callable=PropertyMock, return_value=status))
        stack.enter_context(patch.object(interfaces._util, 'format_status',
                                         return_value='database error'))
        stack.enter_context(patch.object(interfaces.a.api, 'fb_sqlstate',
                                         side_effect=lambda buf, _vector: setattr(buf, 'value', b'08006')))
        stack.enter_context(patch.object(interfaces.a.api, 'isc_sqlcode', return_value=-902))
        yield


@pytest.mark.parametrize('code', [335544648, 335544726, 335544727,
                                  335544741, 335544856])
def test_connection_loss_status_marks_lifecycle(dsn, code):
    with connect(dsn) as con:
        with error_status(code):
            with pytest.raises(DatabaseError) as exc:
                con._att._check()
        assert code in exc.value.gds_codes
        assert con._lifecycle.is_dead
        assert con._att._lifecycle is con._lifecycle
        con._lifecycle.is_dead = False


def test_other_status_does_not_mark_lifecycle(dsn):
    with connect(dsn) as con:
        with error_status(335544569):
            with pytest.raises(DatabaseError):
                con._att._check()
        assert not con._lifecycle.is_dead


def test_result_and_blob_interfaces_share_connection_lifecycle(dsn):
    with connect(dsn) as con:
        with connect(dsn) as other:
            assert other._lifecycle is not con._lifecycle
            assert other._att._lifecycle is other._lifecycle
        with con.cursor() as cur:
            cur.execute('insert into T2 (C1,C9) values (?,?)',
                        [42, StringIO('lifecycle test')])
            con.commit()
            cur.stream_blobs.append('C9')
            cur.execute('select C9 from T2 where C1 = 42')
            reader = cur.fetchone()[0]
            assert con._lifecycle is cur._lifecycle
            assert con._lifecycle is cur._result._lifecycle
            assert con._lifecycle is reader._lifecycle
            assert con._lifecycle is reader._blob._lifecycle
            for interface in (cur._result, reader._blob):
                with error_status(335544741):
                    with pytest.raises(DatabaseError):
                        interface._check()
                assert con._lifecycle.is_dead
                con._lifecycle.is_dead = False
            with patch.object(reader, 'close') as close, patch.object(reader._blob, 'release') as release:
                con._lifecycle.is_dead = True
                try:
                    reader.__del__()
                    reader._blob.__del__()
                    close.assert_not_called()
                    release.assert_not_called()
                finally:
                    con._lifecycle.is_dead = False


def test_dead_connection_finalizers_skip_native_cleanup(dsn):
    with connect(dsn) as con:
        with con.cursor() as cur:
            cur.execute('select * from country')
            tra = con.main_transaction
            stmt = cur._stmt
            assert tra._tra._lifecycle is con._lifecycle
            assert stmt._istmt._lifecycle is con._lifecycle
            assert cur._result._lifecycle is con._lifecycle
            with ExitStack() as stack:
                targets = [(con, '_close'), (tra, '_finish'), (stmt, 'free'),
                           (cur, 'close'), (con._att, 'release'),
                           (tra._tra, 'release'), (stmt._istmt, 'release'),
                           (cur._result, 'release')]
                mocks = [stack.enter_context(patch.object(obj, method))
                         for obj, method in targets]
                con._lifecycle.is_dead = True
                try:
                    for obj in (con, tra, stmt, cur, con._att, tra._tra,
                                stmt._istmt, cur._result):
                        obj.__del__()
                    for method in mocks:
                        method.assert_not_called()
                finally:
                    con._lifecycle.is_dead = False


def test_distributed_transaction_finalizer_checks_each_connection(dsn):
    with connect(dsn) as first, connect(dsn) as second:
        dt = DistributedTransactionManager((first, second))
        assert dt._lifecycles == (first._lifecycle, second._lifecycle)
        dt._tra = object()
        with patch.object(dt, '_finish') as finish:
            second._lifecycle.is_dead = True
            try:
                dt.__del__()
                finish.assert_not_called()
            finally:
                second._lifecycle.is_dead = False
                dt._tra = None
