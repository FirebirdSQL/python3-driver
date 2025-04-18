# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/conftest.py
# DESCRIPTION:    Common fixtures
# CREATED:        28.1.2025
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
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

from __future__ import annotations

from pathlib import Path
import platform
from shutil import copyfile
from configparser import ConfigParser

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import parse
from firebird.base.config import EnvExtendedInterpolation
from firebird.driver import driver_config, get_api, connect_server, connect, DbInfoCode
from firebird.base.config import ConfigProto

_vars_: dict = {'client-lib': None,
                'firebird-config': None,
                'server': None,
                'host': None,
                'port': None,
                'user': 'SYSDBA',
                'password': 'masterkey',
                }

_platform: str = platform.system()

# Configuration

def pytest_addoption(parser, pluginmanager):
    """Adds specific pytest command-line options.

    .. seealso:: `pytest documentation <_pytest.hookspec.pytest_addoption>` for details.
    """
    grp = parser.getgroup('firebird', "Firebird driver QA", 'general')
    grp.addoption('--host', help="Server host", default=None, required=False)
    grp.addoption('--port', help="Server port", default=None, required=False)
    grp.addoption('--client-lib', help="Firebird client library", default=None, required=False)
    grp.addoption('--server', help="Server configuration name", default='', required=False)
    grp.addoption('--driver-config', help="Firebird driver configuration filename", default=None)

@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """General configuration.

    .. seealso:: `pytest documentation <_pytest.hookspec.pytest_configure>` for details.
    """
    if config.getoption('help'):
        return
    # Base paths
    root_path: Path = Path(config.rootpath)
    _vars_['root'] = root_path
    path = config.rootpath / 'tests' / 'databases'
    _vars_['databases'] = path if path.is_dir() else config.rootpath / 'tests'
    path = config.rootpath / 'tests' / 'backups'
    _vars_['backups'] = path if path.is_dir() else config.rootpath / 'tests'
    path = config.rootpath / 'tests' / 'files'
    _vars_['files'] = path if path.is_dir() else config.rootpath / 'tests'
    # Driver configuration
    db_config = driver_config.register_database('pytest')
    if server := config.getoption('server'):
        db_config.server.value = server
        _vars_['server'] = server

    config_path: Path = root_path / 'tests' / 'firebird-driver.conf'
    if cfg_path := config.getoption('driver_config'):
        config_path = Path(cfg_path)
    if config_path.is_file():
        driver_config.read(str(config_path))
        _vars_['firebird-config'] = config_path
        srv_conf = driver_config.get_server(_vars_['server'])
        _vars_['host'] = srv_conf.host.value
        _vars_['port'] = srv_conf.port.value
        _vars_['user'] = srv_conf.user.value
        _vars_['password'] = srv_conf.password.value
        # Handle server-specific "fb_client_library" configuration option
        #_vars_['client-lib'] = 'UNKNOWN'
        cfg = ConfigParser(interpolation=EnvExtendedInterpolation())
        cfg.read(str(config_path))
        if cfg.has_option(_vars_['server'], 'fb_client_library'):
            fbclient = Path(cfg.get(_vars_['server'], 'fb_client_library'))
            if not fbclient.is_file():
                pytest.exit(f"Client library '{fbclient}' not found!")
            driver_config.fb_client_library.value = str(fbclient)
        cfg.clear()
    else:
        # No configuration file, so we process 'host' and 'client-lib' options
        if client_lib := config.getoption('client_lib'):
            client_lib = Path(client_lib)
            if not client_lib.is_file():
                pytest.exit(f"Client library '{client_lib}' not found!")
            driver_config.fb_client_library.value = client_lib
        #
        if host := config.getoption('host'):
            _vars_['host'] = host
            _vars_['port'] = config.getoption('port')
            driver_config.server_defaults.host.value = config.getoption('host')
            driver_config.server_defaults.port.value = config.getoption('port')
        driver_config.server_defaults.user.value = 'SYSDBA'
        driver_config.server_defaults.password.value = 'masterkey'
    # THIS should load the driver API, do not connect db or server earlier!
    _vars_['client-lib'] = get_api().client_library_name
    # Information from server
    with connect_server('') as srv:
        version = parse(srv.info.version.replace('-dev', ''))
        _vars_['version'] = version
        _vars_['home-dir'] = Path(srv.info.home_directory)
        bindir = _vars_['home-dir'] / 'bin'
        if not bindir.exists():
            bindir = _vars_['home-dir']
        _vars_['bin-dir'] = bindir
        _vars_['lock-dir'] = Path(srv.info.lock_directory)
        _vars_['bin-dir'] = Path(bindir) if bindir else _vars_['home-dir']
        _vars_['security-db'] = Path(srv.info.security_database)
        _vars_['arch'] = srv.info.architecture
    # Create copy of test database
    if version in SpecifierSet('>=3.0, <4'):
        source_filename = 'fbtest30.fdb'
    elif version in SpecifierSet('>=4.0, <5'):
        source_filename = 'fbtest40.fdb'
    elif version in SpecifierSet('>=5.0, <6'):
        source_filename = 'fbtest50.fdb'
    else:
        pytest.exit(f"Unsupported Firebird version {version}")
    source_db_file: Path = _vars_['databases'] / source_filename
    if not source_db_file.is_file():
        pytest.exit(f"Source test database '{source_db_file}' not found!")
    _vars_['source_db'] = source_db_file

def pytest_report_header(config):
    """Returns plugin-specific test session header.

    .. seealso:: `pytest documentation <_pytest.hookspec.pytest_report_header>` for details.
    """
    return ["Firebird:",
            f"  configuration: {_vars_['firebird-config']}",
            f"  server: {_vars_['server']} [v{_vars_['version']}, {_vars_['arch']}]",
            f"  host: {_vars_['host']}",
            f"  home: {_vars_['home-dir']}",
            f"  bin: {_vars_['bin-dir']}",
            f"  client library: {_vars_['client-lib']}",
            f"  test database: {_vars_['source_db']}",
            ]

@pytest.fixture(scope='session')
def fb_vars():
    yield _vars_

@pytest.fixture(scope='session')
def tmp_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp('db')
    if _platform != 'Windows':
        wdir = path
        while wdir is not wdir.parent:
            try:
                wdir.chmod(16895)
            except:
                pass
            wdir = wdir.parent
    yield path

@pytest.fixture(scope='session', autouse=True)
def db_file(tmp_dir):
    test_db_filename: Path = tmp_dir / 'test-db.fdb'
    copyfile(_vars_['source_db'], test_db_filename)
    if _platform != 'Windows':
        test_db_filename.chmod(33206)
    driver_config.get_database('pytest').database.value = str(test_db_filename)
    return test_db_filename

@pytest.fixture(scope='session')
def dsn(db_file):
    host = _vars_['host']
    port = _vars_['port']
    if host is None:
        result = str(db_file)
    else:
        result = f'{host}/{port}:{db_file}' if port else f'{host}:{db_file}'
    yield result

@pytest.fixture()
def driver_cfg(tmp_path_factory):
    proto = ConfigProto()
    driver_config.save_proto(proto)
    yield driver_config
    driver_config.load_proto(proto)

@pytest.fixture
def db_connection(driver_cfg):
    conn = connect('pytest')
    yield conn
    if not conn.is_closed():
        conn.close()

@pytest.fixture(autouse=True)
def db_cleanup(db_connection):
    # Clean common test tables before each test using this fixture
    try:
        with db_connection.cursor() as cur:
            cur.execute("delete from t")
            cur.execute("delete from t2")
            cur.execute("delete from FB4")
            db_connection.commit()
    except Exception as e:
        # Ignore errors if tables don't exist, log others
        if "Table unknown" not in str(e):
            print(f"Warning: Error during pre-test cleanup: {e}")

@pytest.fixture
def server_connection(fb_vars):
    with connect_server(fb_vars['host'], user=fb_vars['user'], password=fb_vars['password']) as svc:
        yield svc
