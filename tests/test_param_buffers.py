# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-driver
# FILE:           tests/test_param_buffers.py
# DESCRIPTION:    Tests for TPB, DPB, SPB_ATTACH classes
# CREATED:        18.4.2025
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
# Copyright (c) 2025 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Cline - generated code
#                 ______________________________________.

from __future__ import annotations

import pytest

from firebird.driver.core import TPB, DPB, SPB_ATTACH
from firebird.driver.types import (TraAccessMode, Isolation, TableShareMode, TableAccessMode,
                                   DBKeyScope, ReplicaMode, DecfloatRound, DecfloatTraps)

def test_tpb_parsing():
    """Tests TPB buffer creation and parsing."""
    # Test case 1: Default values
    tpb1 = TPB()
    buffer1 = tpb1.get_buffer()
    tpb2 = TPB()
    tpb2.parse_buffer(buffer1)
    assert tpb1.access_mode == tpb2.access_mode
    assert tpb1.isolation == tpb2.isolation
    assert tpb1.lock_timeout == tpb2.lock_timeout
    assert tpb1.no_auto_undo == tpb2.no_auto_undo
    assert tpb1.auto_commit == tpb2.auto_commit
    assert tpb1.ignore_limbo == tpb2.ignore_limbo
    assert tpb1._table_reservation == tpb2._table_reservation
    assert tpb1.at_snapshot_number == tpb2.at_snapshot_number

    # Test case 2: Various options set
    tpb1 = TPB(access_mode=TraAccessMode.READ,
               isolation=Isolation.READ_COMMITTED_NO_RECORD_VERSION,
               lock_timeout=0, # NO_WAIT
               no_auto_undo=True,
               auto_commit=True,
               ignore_limbo=True,
               at_snapshot_number=12345,
               encoding='iso8859_1')
    tpb1.reserve_table('TABLE1', TableShareMode.PROTECTED, TableAccessMode.LOCK_READ)
    tpb1.reserve_table('TABLE2', TableShareMode.SHARED, TableAccessMode.LOCK_WRITE)

    buffer1 = tpb1.get_buffer()
    tpb2 = TPB(encoding='iso8859_1') # Ensure parser uses same encoding
    tpb2.parse_buffer(buffer1)

    assert tpb1.access_mode == tpb2.access_mode
    assert tpb1.isolation == tpb2.isolation
    assert tpb1.lock_timeout == tpb2.lock_timeout
    assert tpb1.no_auto_undo == tpb2.no_auto_undo
    assert tpb1.auto_commit == tpb2.auto_commit
    assert tpb1.ignore_limbo == tpb2.ignore_limbo
    assert tpb1._table_reservation == tpb2._table_reservation
    assert tpb1.at_snapshot_number == tpb2.at_snapshot_number

    # Test case 3: Different isolation levels and lock timeout > 0
    tpb1 = TPB(isolation=Isolation.SERIALIZABLE, lock_timeout=5)
    buffer1 = tpb1.get_buffer()
    tpb2 = TPB()
    tpb2.parse_buffer(buffer1)
    assert tpb1.isolation == tpb2.isolation
    assert tpb1.lock_timeout == tpb2.lock_timeout

    tpb1 = TPB(isolation=Isolation.READ_COMMITTED_READ_CONSISTENCY)
    buffer1 = tpb1.get_buffer()
    tpb2 = TPB()
    tpb2.parse_buffer(buffer1)
    assert tpb1.isolation == tpb2.isolation

def test_dpb_parsing():
    """Tests DPB buffer creation and parsing."""
    # Test case 1: Default values
    dpb1 = DPB()
    buffer1 = dpb1.get_buffer()
    dpb2 = DPB()
    dpb2.parse_buffer(buffer1)
    # Assert all default attributes match
    assert dpb1.config == dpb2.config
    assert dpb1.auth_plugin_list == dpb2.auth_plugin_list
    assert dpb1.trusted_auth == dpb2.trusted_auth
    assert dpb1.user == dpb2.user
    assert dpb1.password == dpb2.password
    assert dpb1.role == dpb2.role
    assert dpb1.sql_dialect == dpb2.sql_dialect
    assert dpb1.charset == dpb2.charset
    assert dpb1.timeout == dpb2.timeout
    assert dpb1.dummy_packet_interval == dpb2.dummy_packet_interval
    assert dpb1.cache_size == dpb2.cache_size
    assert dpb1.no_gc == dpb2.no_gc
    assert dpb1.no_db_triggers == dpb2.no_db_triggers
    assert dpb1.no_linger == dpb2.no_linger
    assert dpb1.utf8filename == dpb2.utf8filename
    assert dpb1.dbkey_scope == dpb2.dbkey_scope
    assert dpb1.session_time_zone == dpb2.session_time_zone
    assert dpb1.set_db_replica == dpb2.set_db_replica
    assert dpb1.set_bind == dpb2.set_bind
    assert dpb1.decfloat_round == dpb2.decfloat_round
    assert dpb1.decfloat_traps == dpb2.decfloat_traps
    assert dpb1.parallel_workers == dpb2.parallel_workers
    # Create options
    assert dpb1.page_size == dpb2.page_size
    assert dpb1.overwrite == dpb2.overwrite
    assert dpb1.db_cache_size == dpb2.db_cache_size
    assert dpb1.forced_writes == dpb2.forced_writes
    assert dpb1.reserve_space == dpb2.reserve_space
    assert dpb1.read_only == dpb2.read_only
    assert dpb1.sweep_interval == dpb2.sweep_interval
    assert dpb1.db_sql_dialect == dpb2.db_sql_dialect
    assert dpb1.db_charset == dpb2.db_charset

    # Test case 2: Various connect options set
    dpb1 = DPB(user='testuser', password='pwd', role='tester',
               sql_dialect=1, timeout=60,
               charset='WIN1250', cache_size=2048, no_gc=True,
               no_db_triggers=True, no_linger=True,
               utf8filename=True, dbkey_scope=DBKeyScope.TRANSACTION,
               dummy_packet_interval=120,
               config='myconfig', auth_plugin_list='Srp256,Srp',
               session_time_zone='Europe/Prague',
               set_db_replica=ReplicaMode.READ_ONLY,
               set_bind='192.168.1.100',
               decfloat_round=DecfloatRound.HALF_UP,
               decfloat_traps=[DecfloatTraps.DIVISION_BY_ZERO, DecfloatTraps.INVALID_OPERATION],
               parallel_workers=4)

    buffer1 = dpb1.get_buffer(for_create=False)
    dpb2 = DPB(charset='WIN1250') # Ensure parser uses same encoding
    dpb2.parse_buffer(buffer1)

    # Assert all connect attributes match
    assert dpb1.config == dpb2.config
    assert dpb1.auth_plugin_list == dpb2.auth_plugin_list
    assert dpb1.trusted_auth == dpb2.trusted_auth
    assert dpb1.user == dpb2.user
    assert dpb1.password == dpb2.password # Note: Password isn't parsed back for security
    assert dpb1.role == dpb2.role
    assert dpb1.sql_dialect == dpb2.sql_dialect
    assert dpb1.charset == dpb2.charset
    assert dpb1.timeout == dpb2.timeout
    assert dpb1.dummy_packet_interval == dpb2.dummy_packet_interval
    assert dpb1.cache_size == dpb2.cache_size
    assert dpb1.no_gc == dpb2.no_gc
    assert dpb1.no_db_triggers == dpb2.no_db_triggers
    assert dpb1.no_linger == dpb2.no_linger
    assert dpb1.utf8filename == dpb2.utf8filename
    assert dpb1.dbkey_scope == dpb2.dbkey_scope
    assert dpb1.session_time_zone == dpb2.session_time_zone
    assert dpb1.set_db_replica == dpb2.set_db_replica
    assert dpb1.set_bind == dpb2.set_bind
    assert dpb1.decfloat_round == dpb2.decfloat_round
    assert dpb1.decfloat_traps == dpb2.decfloat_traps
    assert dpb1.parallel_workers == dpb2.parallel_workers

    # Test case 3: Various create options set
    dpb1 = DPB(user='creator', password='createkey', charset='NONE',
               page_size=8192, overwrite=True, db_cache_size=4096,
               forced_writes=False, reserve_space=False, read_only=True,
               sweep_interval=10000, db_sql_dialect=3, db_charset='UTF8')

    buffer1 = dpb1.get_buffer(for_create=True)
    dpb2 = DPB(charset='NONE') # Ensure parser uses same encoding
    dpb2.parse_buffer(buffer1)

    # Assert all create attributes match
    assert dpb1.page_size == dpb2.page_size
    assert dpb1.overwrite == dpb2.overwrite
    assert dpb1.db_cache_size == dpb2.db_cache_size
    assert dpb1.forced_writes == dpb2.forced_writes
    assert dpb1.reserve_space == dpb2.reserve_space
    assert dpb1.read_only == dpb2.read_only
    assert dpb1.sweep_interval == dpb2.sweep_interval
    assert dpb1.db_sql_dialect == dpb2.db_sql_dialect
    assert dpb1.db_charset == dpb2.db_charset
    # Also check connect attributes set during create
    assert dpb1.user == dpb2.user
    assert dpb1.password == dpb2.password # Note: Password isn't parsed back
    assert dpb1.charset == dpb2.charset # Should be set by db_charset during create

def test_spb_attach_parsing():
    """Tests SPB_ATTACH buffer creation and parsing."""
    # Test case 1: Default values
    spb1 = SPB_ATTACH()
    buffer1 = spb1.get_buffer()
    spb2 = SPB_ATTACH()
    spb2.parse_buffer(buffer1)
    assert spb1.user == spb2.user
    assert spb1.password == spb2.password
    assert spb1.trusted_auth == spb2.trusted_auth
    assert spb1.config == spb2.config
    assert spb1.auth_plugin_list == spb2.auth_plugin_list
    assert spb1.expected_db == spb2.expected_db
    assert spb1.role == spb2.role

    # Test case 2: Various options set
    spb1 = SPB_ATTACH(user='service_user', password='svc',
                      config='service_conf', auth_plugin_list='Srp',
                      expected_db='/path/to/expected.fdb', role='SVC_ROLE',
                      encoding='utf_8', errors='replace')

    buffer1 = spb1.get_buffer()
    spb2 = SPB_ATTACH(encoding='utf_8', errors='replace') # Ensure parser uses same encoding/errors
    spb2.parse_buffer(buffer1)

    assert spb1.user == spb2.user
    assert spb1.password == spb2.password # Note: Password isn't parsed back
    assert spb1.trusted_auth == spb2.trusted_auth
    assert spb1.config == spb2.config
    assert spb1.auth_plugin_list == spb2.auth_plugin_list
    assert spb1.expected_db == spb2.expected_db
    assert spb1.role == spb2.role
