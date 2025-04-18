# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_createdrop.py
#   DESCRIPTION:    Tests for database create and drop operations
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
from firebird.driver import (create_database, DatabaseError, connect_server, ShutdownMethod,
                             ShutdownMode, PageSize)

@pytest.fixture
def droptest_file(fb_vars, tmp_dir):
    drop_file = tmp_dir / 'droptest.fdb'
    # Setup: Ensure file doesn't exist
    if drop_file.exists():
        drop_file.unlink()
    #
    yield drop_file # Provide the dsn to the test
    # Teardown: Ensure file is removed
    if drop_file.exists():
        try:
            # May need to shut down lingering connections on Classic Server
            with connect_server(fb_vars['host']) as svc:
                svc.database.shutdown(database=str(drop_file), mode=ShutdownMode.FULL,
                                      method=ShutdownMethod.FORCED, timeout=0)
                svc.database.bring_online(database=str(drop_file))
        except Exception:
            pass # Ignore errors if shutdown fails (e.g., file already gone)
        finally:
            if drop_file.exists():
                drop_file.unlink()

@pytest.fixture
def droptest_dsn(fb_vars, droptest_file):
    host = fb_vars['host']
    port = fb_vars['port']
    if host is None:
        result = str(droptest_file)
    else:
        result = f'{host}/{port}:{droptest_file}' if port else f'{host}:{droptest_file}'
    yield result


def test_create_drop_dsn(droptest_dsn):
    with create_database(droptest_dsn) as con:
        assert con.dsn == droptest_dsn
        assert con.sql_dialect == 3
        assert con.charset is None
        con.drop_database()
    # Overwrite
    with create_database(droptest_dsn) as con:
        assert con.dsn == droptest_dsn
        assert con.sql_dialect == 3
        assert con.charset is None
    # Check overwrite=False raises error
    with pytest.raises(DatabaseError, match='exist'):
        create_database(droptest_dsn)
    # Check overwrite=True works
    with create_database(droptest_dsn, overwrite=True) as con:
        assert con.dsn == droptest_dsn
        con.drop_database()

def test_create_drop_config(fb_vars, droptest_file, driver_cfg):
    host = fb_vars['host']
    port = fb_vars['port']
    if host is None:
        srv_config = f"""
            [server.local]
            user = {fb_vars['user']}
            password = {fb_vars['password']}
            """
        db_config = f"""
            [test_db2]
            server = server.local
            database = {droptest_file}
            utf8filename = true
            charset = UTF8
            sql_dialect = 1
            page_size = {PageSize.PAGE_16K}
            db_sql_dialect = 1
            sweep_interval = 0
            """
        dsn = str(droptest_file)
    else:
        srv_config = f"""
            [server.local]
            host = {host}
            user = {fb_vars['user']}
            password = {fb_vars['password']}
            port = {port if port else ''}
            """
        db_config = f"""
            [test_db2]
            server = server.local
            database = {droptest_file}
            utf8filename = true
            charset = UTF8
            sql_dialect = 1
            page_size = {PageSize.PAGE_16K}
            db_sql_dialect = 1
            sweep_interval = 0
            """
        dsn = f'{host}/{port}:{droptest_file}' if port else f'{host}:{droptest_file}'
    # Ensure config section doesn't exist from previous runs if tests run in parallel/reordered
    if driver_cfg.get_server('server.local'):
        driver_cfg.servers.value = [s for s in driver_cfg.servers.value if s.name != 'server.local']
    if driver_cfg.get_database('test_db2'):
        driver_cfg.databases.value = [db for db in driver_cfg.databases.value if db.name != 'test_db2']

    driver_cfg.register_server('server.local', srv_config)
    driver_cfg.register_database('test_db2', db_config)

    try:
        with create_database('test_db2') as con:
            assert con.sql_dialect == 1
            assert con.charset == 'UTF8'
            assert con.info.page_size == 16384
            assert con.info.sql_dialect == 1
            assert con.info.charset == 'UTF8'
            assert con.info.sweep_interval == 0
            con.drop_database()
    finally:
        # Clean up registered config
        driver_cfg.databases.value = [db for db in driver_cfg.databases.value if db.name != 'test_db2']
