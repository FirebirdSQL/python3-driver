# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_server.py
#   DESCRIPTION:    Tests for Server (services)
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

from io import BytesIO
import pytest
from packaging.specifiers import SpecifierSet
import firebird.driver as driver
from firebird.driver import (connect, connect_server, create_database, Error, DatabaseError,
                             SrvInfoCode, ServerCapability, SrvStatFlag, SrvBackupFlag,
                             SrvRestoreFlag, SrvNBackupFlag, ShutdownMode, ShutdownMethod,
                             OnlineMode, DbSpaceReservation, DbWriteMode, DbAccessMode,
                             SrvRepairFlag)

@pytest.fixture
def service_test_env(tmp_dir, fb_vars):
    rfdb_path = tmp_dir / 'test_svc_db.fdb'
    fbk_path = tmp_dir / 'test_svc_db.fbk'
    fbk2_path = tmp_dir / 'test_svc_db.fbk2'
    host = fb_vars['host']
    port = fb_vars['port']
    if host is None:
        rfdb_dsn = str(rfdb_path)
    else:
        rfdb_dsn = f'{host}/{port}:{rfdb_path}' if port else f'{host}:{rfdb_path}'

    # Ensure the restore target DB exists and is clean
    try:
        with create_database(rfdb_dsn, overwrite=True) as c:
            pass # Just create/overwrite
    except Exception as e:
        pytest.fail(f"Failed to create restore target DB {rfdb_path}: {e}")

    yield {
        "rfdb": rfdb_path,
        "rfdb_dsn": rfdb_dsn,
        "fbk": fbk_path,
        "fbk2": fbk2_path
    }

    # Teardown: remove created files
    for f_path in [rfdb_path, fbk_path, fbk2_path]:
        if f_path.exists():
            try:
                f_path.unlink()
            except OSError:
                pass # Ignore if removal fails

def test_attach(server_connection):
    # The fixture itself tests attachment
    assert server_connection is not None
    assert server_connection._svc is not None # Check internal service object

def test_query(server_connection, fb_vars, dsn, db_file):
    svc = server_connection
    version = fb_vars['version']

    assert svc.info.manager_version == 2
    assert svc.info.version.startswith(str(version))
    assert float('.'.join(str(version).split('.')[:1])) <= svc.info.engine_version # engine_version can be more precise
    assert 'Firebird' in svc.info.architecture
    assert isinstance(svc.info.home_directory, str) and svc.info.home_directory

    sec_db = svc.info.security_database.upper()
    if version in SpecifierSet('>=5.0'):
        assert sec_db.endswith('SECURITY5.FDB')
    elif version in SpecifierSet('>=4.0'):
        assert sec_db.endswith('SECURITY4.FDB')
    else: # FB30
        assert sec_db.endswith('SECURITY53.FDB')

    assert isinstance(svc.info.lock_directory, str) # Path can vary
    caps = svc.info.capabilities
    assert ServerCapability.REMOTE_HOP in caps
    assert ServerCapability.NO_FORCED_WRITE not in caps # Usually False
    assert isinstance(svc.info.message_directory, str) # Path can vary

    # Test DB info requires a connection
    with connect(dsn) as con1, connect(dsn) as con2:
        db_info = svc.info.get_info(SrvInfoCode.SRV_DB_INFO)
        assert isinstance(db_info, tuple)
        count, dbs = db_info
        assert count >= 2
        assert isinstance(dbs, list)
        # Check if our test databases are listed (case-insensitive)
        db_upper_list = [s.upper() for s in dbs]
        assert str(db_file).upper() in db_upper_list

    # BAD request code
    with pytest.raises(Error, match="feature is not supported"): # More specific error?
        svc.info.get_info(255) # Use an invalid code

def test_running(server_connection):
    assert not server_connection.is_running()
    server_connection.info.get_log() # Start an async service
    assert server_connection.is_running()
    # fetch materialized
    server_connection.readlines() # Read all output
    assert not server_connection.is_running()

def test_wait(server_connection):
    assert not server_connection.is_running()
    server_connection.info.get_log()
    assert server_connection.is_running()
    server_connection.wait() # Wait for service to finish
    assert not server_connection.is_running()

def test_log(server_connection):
    def fetchline(line):
        output.append(line)

    server_connection.info.get_log()
    # fetch materialized
    log = server_connection.readlines()
    assert log
    assert isinstance(log, type(list()))
    # iterate over result
    server_connection.info.get_log()
    for line in server_connection:
        assert line is not None
        assert isinstance(line, str)
    # callback
    output = []
    server_connection.info.get_log(callback=fetchline)
    assert len(output) > 0
    assert output == log

def test_output_by_line(server_connection):
    server_connection.mode = SrvInfoCode.LINE
    test_log(server_connection)

def test_output_to_eof(server_connection):
    server_connection.mode = SrvInfoCode.TO_EOF
    test_log(server_connection)

def test_get_limbo_transaction_ids(server_connection, db_file):
    pytest.skip('Not implemented yet')
    ids = server_connection.database.get_limbo_transaction_ids(database=str(db_file))
    assert isinstance(ids, type(list()))

def test_trace(server_connection, db_file, fb_vars):
    trace_config = """database = %s
    {
      enabled = true
      log_statement_finish = true
      print_plan = true
      include_filter = %%SELECT%%
      exclude_filter = %%RDB$%%
      time_threshold = 0
      max_sql_length = 2048
    }
    """ % str(db_file)
    with connect_server(fb_vars['host'], user='SYSDBA', password=fb_vars['password']) as svc2, \
         connect_server(fb_vars['host'], user='SYSDBA', password=fb_vars['password']) as svcx:
        # Start trace sessions
        trace1_id = server_connection.trace.start(config=trace_config, name='test_trace_1')
        trace2_id = svc2.trace.start(config=trace_config)
        # check sessions
        sessions = svcx.trace.sessions
        assert trace1_id in sessions
        assert sessions[trace1_id].name == 'test_trace_1'
        assert sessions[trace2_id].name == ''
        # Windows returns SYSDBA
        #if sys.platform == 'win32':
            #self.assertEqual(sessions[trace1_id].user, 'SYSDBA')
            #self.assertEqual(sessions[trace2_id].user, 'SYSDBA')
        #else:
            #self.assertEqual(sessions[trace1_id].user, '')
            #self.assertEqual(sessions[trace2_id].user, '')
        assert sessions[trace1_id].user == 'SYSDBA'
        assert sessions[trace2_id].user == 'SYSDBA'
        assert trace2_id in sessions
        assert sessions[trace1_id].flags == ['active', ' trace']
        assert sessions[trace2_id].flags == ['active', ' trace']
        # Pause session
        svcx.trace.suspend(session_id=trace2_id)
        assert 'suspend' in svcx.trace.sessions[trace2_id].flags
        # Resume session
        svcx.trace.resume(session_id=trace2_id)
        assert 'active' in svcx.trace.sessions[trace2_id].flags
        # Stop session
        svcx.trace.stop(session_id=trace2_id)
        assert trace2_id not in svcx.trace.sessions
        # Finalize
        svcx.trace.stop(session_id=trace1_id)

def test_get_users(server_connection):
    users = server_connection.user.get_all()
    assert isinstance(users, type(list()))
    assert isinstance(users[0], driver.core.UserInfo)
    assert users[0].user_name == 'SYSDBA'

def test_manage_user(server_connection):
    USER_NAME = 'DRIVER_TEST'
    try:
        server_connection.user.delete(USER_NAME)
    except DatabaseError as e:
        if e.sqlstate == '28000':
            pass
        else:
            raise
    # Add user
    server_connection.user.add(user_name=USER_NAME, password='DRIVER_TEST',
                      first_name='Firebird', middle_name='Driver', last_name='Test')
    assert server_connection.user.exists(USER_NAME)
    users = [u for u in server_connection.user.get_all() if u.user_name == USER_NAME]
    assert users
    assert len(users) == 1
    assert users[0].first_name == 'Firebird'
    assert users[0].middle_name == 'Driver'
    assert users[0].last_name == 'Test'
    # Modify user
    server_connection.user.update(USER_NAME, first_name='XFirebird', middle_name='XDriver', last_name='XTest')
    user = server_connection.user.get(USER_NAME)
    assert user.user_name == USER_NAME
    assert user.first_name == 'XFirebird'
    assert user.middle_name == 'XDriver'
    assert user.last_name == 'XTest'
    # Delete user
    server_connection.user.delete(USER_NAME)
    assert not server_connection.user.exists(USER_NAME)

def test_get_statistics(server_connection, db_file):
    def fetchline(line):
        output.append(line)

    server_connection.database.get_statistics(database=db_file)
    assert server_connection.is_running()
    # fetch materialized
    stats = server_connection.readlines()
    assert not server_connection.is_running()
    assert isinstance(stats, type(list()))
    # iterate over result
    server_connection.database.get_statistics(database=db_file,
                                     flags=(SrvStatFlag.DEFAULT
                                            | SrvStatFlag.SYS_RELATIONS
                                            | SrvStatFlag.RECORD_VERSIONS))
    for line in server_connection:
        assert isinstance(line, str)
    # callback
    output = []
    server_connection.database.get_statistics(database=db_file, callback=fetchline)
    assert len(output) > 0
    # fetch only selected tables
    stats = server_connection.database.get_statistics(database=db_file,
                                             flags=SrvStatFlag.DATA_PAGES,
                                             tables=['COUNTRY'])
    stats = '\n'.join(server_connection.readlines())
    assert 'COUNTRY' in stats
    assert 'JOB' not in stats
    #
    stats = server_connection.database.get_statistics(database=db_file,
                                             flags=SrvStatFlag.DATA_PAGES,
                                             tables=('COUNTRY', 'PROJECT'))
    stats = '\n'.join(server_connection.readlines())
    assert 'COUNTRY' in stats
    assert 'PROJECT' in stats
    assert 'JOB' not in stats

def test_backup(server_connection, db_file, service_test_env):
    def fetchline(line):
        output.append(line)

    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    fbk = service_test_env['fbk']
    server_connection.database.backup(database=db_file, backup=fbk)
    assert server_connection.is_running()
    # fetch materialized
    report = server_connection.readlines()
    assert not server_connection.is_running()
    assert fbk.exists()
    assert isinstance(report, type(list()))
    assert report == []
    # iterate over result
    server_connection.database.backup(database=db_file, backup=fbk,
                                      flags=(SrvBackupFlag.CONVERT
                                             | SrvBackupFlag.IGNORE_LIMBO
                                             | SrvBackupFlag.METADATA_ONLY), verbose=True)
    for line in server_connection:
        assert line is not None
        assert isinstance(line, str)
    # callback
    output = []
    server_connection.database.backup(database=db_file, backup=fbk, callback=fetchline,
                                      verbose=True)
    assert len(output) > 0
    # Firebird 3.0 stats
    output = []
    server_connection.database.backup(database=db_file, backup=fbk, callback=fetchline,
                                      stats='TDRW', verbose=True)
    assert len(output) > 0
    assert 'gbak: time     delta  reads  writes \n' in output
    # Skip data option
    server_connection.database.backup(database=db_file, backup=fbk, skip_data='(sales|customer)')
    server_connection.wait()
    server_connection.database.restore(backup=fbk, database=rfdb, flags=SrvRestoreFlag.REPLACE)
    server_connection.wait()
    with connect(rfdb_dsn) as rcon:
        with rcon.cursor() as c:
            c.execute('select * from sales')
            assert c.fetchall() == []
            c.execute('select * from country')
            assert len(c.fetchall()) > 0

def test_restore(server_connection, db_file, service_test_env):
    def fetchline(line):
        output.append(line)

    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    fbk = service_test_env['fbk']
    output = []
    server_connection.database.backup(database=db_file, backup=fbk, callback=fetchline)
    assert fbk.exists()
    server_connection.database.restore(backup=fbk, database=rfdb, flags=SrvRestoreFlag.REPLACE)
    assert server_connection.is_running()
    # fetch materialized
    report = server_connection.readlines()
    assert not server_connection.is_running()
    assert isinstance(report, type(list()))
    # iterate over result
    server_connection.database.restore(backup=fbk, database=rfdb, flags=SrvRestoreFlag.REPLACE)
    for line in server_connection:
        assert line is not None
        assert isinstance(line, str)
    # callback
    output = []
    server_connection.database.restore(backup=fbk, database=rfdb, verbose=True,
                              flags=SrvRestoreFlag.REPLACE, callback=fetchline)
    assert len(output) > 0
    # Firebird 3.0 stats
    output = []
    server_connection.database.restore(backup=fbk, database=rfdb,
                              flags=SrvRestoreFlag.REPLACE, callback=fetchline,
                              stats='TDRW', verbose=True)
    assert len(output) > 0
    assert 'gbak: time     delta  reads  writes \n' in output
    # Skip data option
    server_connection.database.restore(backup=fbk, database=rfdb,
                              flags=SrvRestoreFlag.REPLACE, skip_data='(sales|customer)')
    server_connection.wait()
    with connect(rfdb_dsn) as rcon:
        with rcon.cursor() as c:
            c.execute('select * from sales')
            assert c.fetchall() == []
            c.execute('select * from country')
            assert len(c.fetchall()) > 0

def test_local_backup(server_connection, db_file, service_test_env):
    fbk = service_test_env['fbk']
    server_connection.database.backup(database=db_file, backup=fbk)
    server_connection.wait()
    with open(fbk, mode='rb') as f:
        f.seek(68)  # Wee must skip after backup creation time (68) that will differ
        bkp = f.read()
    backup_stream = BytesIO()
    server_connection.database.local_backup(database=db_file, backup_stream=backup_stream)
    backup_stream.seek(68)
    lbkp = backup_stream.read()
    stop = min(len(bkp), len(lbkp))
    i = 0
    while i < stop:
        assert bkp[i] == lbkp[i]
        i += 1
    del bkp

def test_local_restore(server_connection, db_file, service_test_env):
    rfdb = service_test_env['rfdb']
    backup_stream = BytesIO()
    server_connection.database.local_backup(database=db_file, backup_stream=backup_stream)
    backup_stream.seek(0)
    server_connection.database.local_restore(backup_stream=backup_stream, database=rfdb,
                                             flags=SrvRestoreFlag.REPLACE)
    assert rfdb.exists()

def test_nbackup(server_connection, service_test_env, db_file):
    fbk = service_test_env['fbk']
    fbk2 = service_test_env['fbk2']
    server_connection.database.nbackup(database=db_file, backup=fbk)
    assert fbk.exists()
    server_connection.database.nbackup(database=db_file, backup=fbk2, level=1,
                              direct=True, flags=SrvNBackupFlag.NO_TRIGGERS)
    assert fbk2.exists()

def test_nrestore(server_connection, service_test_env, db_file):
    rfdb = service_test_env['rfdb']
    fbk = service_test_env['fbk']
    fbk2 = service_test_env['fbk2']
    test_nbackup(server_connection, service_test_env, db_file)
    if rfdb.exists():
        rfdb.unlink()
    server_connection.database.nrestore(backups=[fbk], database=rfdb)
    assert rfdb.exists()
    if rfdb.exists():
        rfdb.unlink()
    server_connection.database.nrestore(backups=[fbk, fbk2], database=rfdb,
                      direct=True, flags=SrvNBackupFlag.NO_TRIGGERS)
    assert rfdb.exists()

def test_set_default_cache_size(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    with connect(rfdb_dsn) as con:
        assert con.info.page_cache_size != 100
    server_connection.database.set_default_cache_size(database=rfdb, size=100)
    with connect(rfdb_dsn) as con:
        assert con.info.page_cache_size == 100
    server_connection.database.set_default_cache_size(database=rfdb, size=5000)
    with connect(rfdb_dsn) as con:
        assert con.info.page_cache_size == 5000

def test_set_sweep_interval(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    with connect(rfdb_dsn) as con:
        assert con.info.sweep_interval != 10000
    server_connection.database.set_sweep_interval(database=rfdb, interval=10000)
    with connect(rfdb_dsn) as con:
        assert con.info.sweep_interval == 10000

def test_shutdown_bring_online(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    # Shutdown database to single-user maintenance mode
    server_connection.database.shutdown(database=rfdb,
                                                          mode=ShutdownMode.SINGLE,
                                                          method=ShutdownMethod.FORCED,
                                                          timeout=0)
    server_connection.database.get_statistics(database=rfdb,
                                                                flags=SrvStatFlag.HDR_PAGES)
    assert 'single-user maintenance' in ''.join(server_connection.readlines())
    # Enable multi-user maintenance
    server_connection.database.bring_online(database=rfdb,
                                                              mode=OnlineMode.MULTI)
    server_connection.database.get_statistics(database=rfdb,
                                                                flags=SrvStatFlag.HDR_PAGES)
    assert 'multi-user maintenance' in ''.join(server_connection.readlines())
    # Go to full shutdown mode, disabling new attachments during 5 seconds
    server_connection.database.shutdown(database=rfdb,
                                                          mode=ShutdownMode.FULL,
                                                          method=ShutdownMethod.DENY_ATTACHMENTS,
                                                          timeout=5)
    server_connection.database.get_statistics(database=rfdb,
                                                                flags=SrvStatFlag.HDR_PAGES)
    assert 'full shutdown' in ''.join(server_connection.readlines())
    # Enable single-user maintenance
    server_connection.database.bring_online(database=rfdb,
                                                              mode=OnlineMode.SINGLE)
    server_connection.database.get_statistics(database=rfdb,
                                                                flags=SrvStatFlag.HDR_PAGES)
    assert 'single-user maintenance' in ''.join(server_connection.readlines())
    # Return to normal state
    server_connection.database.bring_online(database=rfdb)

def test_set_space_reservation(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    with connect(rfdb_dsn) as con:
        assert con.info.space_reservation == DbSpaceReservation.RESERVE
    server_connection.database.set_space_reservation(database=rfdb,
                                                     mode=DbSpaceReservation.USE_FULL)
    with connect(rfdb_dsn) as con:
        assert con.info.space_reservation == DbSpaceReservation.USE_FULL

def test_set_write_mode(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    with connect(rfdb_dsn) as con:
        assert con.info.write_mode == DbWriteMode.SYNC
    server_connection.database.set_write_mode(database=rfdb, mode=DbWriteMode.ASYNC)
    with connect(rfdb_dsn) as con:
        assert con.info.write_mode == DbWriteMode.ASYNC

def test_set_access_mode(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    with connect(rfdb_dsn) as con:
        assert con.info.access_mode == DbAccessMode.READ_WRITE
    server_connection.database.set_access_mode(database=rfdb, mode=DbAccessMode.READ_ONLY)
    with connect(rfdb_dsn) as con:
        assert con.info.access_mode == DbAccessMode.READ_ONLY

def test_set_sql_dialect(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    rfdb_dsn = service_test_env['rfdb_dsn']
    with connect(rfdb_dsn) as con:
        assert con.info.sql_dialect == 3
    server_connection.database.set_sql_dialect(database=rfdb, dialect=1)
    with connect(rfdb_dsn) as con:
        assert con.info.sql_dialect == 1

def test_activate_shadow(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    server_connection.database.activate_shadow(database=rfdb)

def test_no_linger(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    server_connection.database.no_linger(database=rfdb)

def test_sweep(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    server_connection.database.sweep(database=rfdb)

def test_repair(server_connection, service_test_env):
    rfdb = service_test_env['rfdb']
    server_connection.database.repair(database=rfdb, flags=SrvRepairFlag.CORRUPTION_CHECK)
    server_connection.database.repair(database=rfdb, flags=SrvRepairFlag.REPAIR)

def test_validate(server_connection, db_file, fb_vars):
    def fetchline(line):
        output.append(line)

    output = []
    server_connection.database.validate(database=db_file)
    # fetch materialized
    report = server_connection.readlines()
    assert not server_connection.is_running()
    assert isinstance(report, type(list()))
    assert 'Validation started' in '/n'.join(report)
    assert 'Validation finished' in '/n'.join(report)
    # iterate over result
    server_connection.database.validate(database=db_file)
    for line in server_connection:
        assert line is not None
        assert isinstance(line, str)
    # callback
    output = []
    server_connection.database.validate(database=db_file, callback=fetchline)
    assert len(output) > 0
    # Parameters
    server_connection.database.validate(database=db_file, include_table='COUNTRY|SALES',
                      include_index='SALESTATX', lock_timeout=-1)
    report = '/n'.join(server_connection.readlines())
    assert '(JOB)' not in report
    assert '(COUNTRY)' in report
    assert '(SALES)' in report
    if fb_vars['version'] in SpecifierSet('>=4.0'):
        assert '(SALESTATX)' in report
