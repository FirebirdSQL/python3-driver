# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_transaction.py
#   DESCRIPTION:    Tests for Transaction
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
from firebird.driver import (connect, create_database, connect_server, Isolation,
                             transaction, InterfaceError, TPB, TableShareMode,
                             ShutdownMode, ShutdownMethod, DistributedTransactionManager,
                             TableAccessMode, TraInfoCode, TraInfoAccess, TraAccessMode)

@pytest.fixture(scope="function") # Function scope for isolation
def distributed_transaction_dbs(driver_cfg, tmp_dir, fb_vars):
    # Setup two databases for DTS tests
    db1_path = tmp_dir / 'fbtest-dts-1.fdb'
    db2_path = tmp_dir / 'fbtest-dts-2.fdb'
    con1, con2 = None, None
    cfg1_name, cfg2_name = 'dts-1-test', 'dts-2-test'

    # Register configs
    cfg1 = driver_cfg.register_database(cfg1_name)
    cfg1.server.value = fb_vars['server']
    cfg1.database.value = str(db1_path)
    cfg1.no_linger.value = True

    cfg2 = driver_cfg.register_database(cfg2_name)
    cfg2.server.value = fb_vars['server']
    cfg2.database.value = str(db2_path)
    cfg2.no_linger.value = True

    # Create databases
    try:
        con1 = create_database(cfg1_name, overwrite=True)
        con1.execute_immediate("recreate table T (PK integer, C1 integer)")
        con1.commit()

        con2 = create_database(cfg2_name, overwrite=True)
        con2.execute_immediate("recreate table T (PK integer, C1 integer)")
        con2.commit()
    except Exception as e:
        # Cleanup if setup fails
        if con1 and not con1.is_closed(): con1.close()
        if con2 and not con2.is_closed(): con2.close()
        if db1_path.exists(): db1_path.unlink()
        if db2_path.exists(): db2_path.unlink()
        driver_cfg.databases.value = [db for db in driver_cfg.databases.value if db.name not in [cfg1_name, cfg2_name]]
        pytest.fail(f"Failed to set up distributed transaction databases: {e}")

    yield con1, con2, str(db1_path), str(db2_path), cfg1_name, cfg2_name # Provide connections and paths

    # Teardown
    if con1 and not con1.is_closed(): con1.close()
    if con2 and not con2.is_closed(): con2.close()

    # Ensure databases can be dropped (shutdown might be needed)
    for db_fpath in [db1_path, db2_path]:
        if db_fpath.exists():
            try:
                with connect_server(fb_vars['server']) as svc:
                    svc.database.shutdown(database=str(db_fpath), mode=ShutdownMode.FULL,
                                          method=ShutdownMethod.FORCED, timeout=0)
                    svc.database.bring_online(database=str(db_fpath))
                # Use config name for connect-to-drop to ensure server is specified
                db_conf_name = cfg1_name if str(db_fpath) == str(db1_path) else cfg2_name
                with connect(db_conf_name) as con_drop:
                    con_drop.drop_database()
            except Exception as e:
                print(f"Warning: Could not drop DTS database {db_fpath}: {e}")
            finally:
                # Attempt unlink again just in case drop failed but left file
                if db_fpath.exists():
                    try:
                        db_fpath.unlink()
                    except OSError:
                        print(f"Warning: Could not unlink DTS database file {db_fpath}")

def test_context_manager(distributed_transaction_dbs):
    con1, con2, _, _, _, _ = distributed_transaction_dbs
    with DistributedTransactionManager((con1, con2)) as dt:
        q = 'select * from T order by pk'
        with dt.cursor(con1) as c1, con1.cursor() as cc1, \
             dt.cursor(con2) as c2, con2.cursor() as cc2:

            # Distributed transaction: COMMIT
            with transaction(dt):
                c1.execute('insert into t (pk) values (1)')
                c2.execute('insert into t (pk) values (1)')

            with transaction(con1):
                cc1.execute(q)
                result = cc1.fetchall()
            assert result == [(1, None)]
            with transaction(con2):
                cc2.execute(q)
                result = cc2.fetchall()
            assert result == [(1, None)]

            # Distributed transaction: ROLLBACK
            with pytest.raises(Exception, match="Simulated DTS error"):
                with transaction(dt):
                    c1.execute('insert into t (pk) values (2)')
                    c2.execute('insert into t (pk) values (2)')
                    raise Exception("Simulated DTS error")

            c1.execute(q) # Should reuse dt transaction context implicitly if needed
            result = c1.fetchall()
            assert result == [(1, None)]
            c2.execute(q)
            result = c2.fetchall()
            assert result == [(1, None)]

def test_simple_dt(distributed_transaction_dbs):
    con1, con2, _, _, _, _ = distributed_transaction_dbs
    with DistributedTransactionManager((con1, con2)) as dt:
        q = 'select * from T order by pk'
        with dt.cursor(con1) as c1, con1.cursor() as cc1, \
             dt.cursor(con2) as c2, con2.cursor() as cc2:
            # Distributed transaction: COMMIT
            c1.execute('insert into t (pk) values (1)')
            c2.execute('insert into t (pk) values (1)')
            dt.commit()

            with transaction(con1): cc1.execute(q); result = cc1.fetchall()
            assert result == [(1, None)]
            with transaction(con2): cc2.execute(q); result = cc2.fetchall()
            assert result == [(1, None)]

            # Distributed transaction: PREPARE+COMMIT
            c1.execute('insert into t (pk) values (2)')
            c2.execute('insert into t (pk) values (2)')
            dt.prepare()
            dt.commit()

            with transaction(con1): cc1.execute(q); result = cc1.fetchall()
            assert result == [(1, None), (2, None)]
            with transaction(con2): cc2.execute(q); result = cc2.fetchall()
            assert result == [(1, None), (2, None)]

            # Distributed transaction: SAVEPOINT+ROLLBACK to it
            c1.execute('insert into t (pk) values (3)')
            dt.savepoint('CG_SAVEPOINT')
            c2.execute('insert into t (pk) values (3)')
            dt.rollback(savepoint='CG_SAVEPOINT')

            c1.execute(q); result = c1.fetchall()
            assert result == [(1, None), (2, None), (3, None)]
            c2.execute(q); result = c2.fetchall()
            assert result == [(1, None), (2, None)]

            # Distributed transaction: ROLLBACK
            dt.rollback()

            with transaction(con1): cc1.execute(q); result = cc1.fetchall()
            assert result == [(1, None), (2, None)]
            with transaction(con2): cc2.execute(q); result = cc2.fetchall()
            assert result == [(1, None), (2, None)]

            # Distributed transaction: EXECUTE_IMMEDIATE
            dt.execute_immediate('insert into t (pk) values (3)')
            dt.commit()

            with transaction(con1): cc1.execute(q); result = cc1.fetchall()
            assert result == [(1, None), (2, None), (3, None)]
            with transaction(con2): cc2.execute(q); result = cc2.fetchall()
            assert result == [(1, None), (2, None), (3, None)]

def test_limbo_transactions(distributed_transaction_dbs):
    pytest.skip('Limbo transaction test needs review and reliable setup.')
    # Original test was skipped and likely requires manual server intervention
    # or specific timing to force limbo state, which is hard to automate reliably.
