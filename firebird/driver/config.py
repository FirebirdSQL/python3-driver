#coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/config.py
# DESCRIPTION:    Driver configuration
# CREATED:        1.6.2020
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""firebird-driver - Driver configuration


"""

from __future__ import annotations
from typing import Dict, Union, Iterable
import os
from configparser import ConfigParser, ExtendedInterpolation
from firebird.base.config import Config, StrOption, IntOption, BoolOption, EnumOption, \
     ConfigListOption, ListOption
from .types import NetProtocol, DecfloatRound, DecfloatTraps

class ServerConfig(Config): # pylint: disable=R0902
    """Server configuration.
    """
    def __init__(self, name: str, *, optional: bool=False, description: str=None):
        super().__init__(name, optional=optional, description=description)
        #: Server host machine specification
        self.host: StrOption = \
            StrOption('host', "Server host machine specification")
        #: Port used by Firebird server
        self.port: StrOption = \
            StrOption('port', "Port used by Firebird server")
        #: Defaul user name, default is envar ISC_USER or None if not specified
        self.user: StrOption = \
            StrOption('user', "Defaul user name", default=os.environ.get('ISC_USER', None))
        #: Default user password, default is envar ISC_PASSWORD or None if not specified
        self.password: StrOption = \
            StrOption('password', "Default user password",
                      default=os.environ.get('ISC_PASSWORD', None))
        #: Configuration override
        self.config: StrOption = \
            StrOption('config', "Configuration override")
        #: List of authentication plugins override
        self.auth_plugin_list: StrOption = \
            StrOption('auth_plugin_list', "List of authentication plugins override")
        #: Use trusted authentication, default: False
        self.trusted_auth: BoolOption = \
            BoolOption('trusted_auth', "Use trusted authentication", default=False)
        #: Encoding used for text data exchange with server
        self.encoding: StrOption = \
            StrOption('encoding', "Encoding used for text data exchange with server",
                      default='ascii')
        #: Handler used for encoding errors. See `codecs error handlers <codecs>` for details.
        self.encoding_errors: StrOption = \
            StrOption('encoding_errors', "Handler used for encoding errors", default='strict')

class DatabaseConfig(Config): # pylint: disable=R0902
    """Database configuration.
    """
    def __init__(self, name: str, *, optional: bool=False, description: str=None):
        super().__init__(name, optional=optional, description=description)
        #: Name of server where database is located
        self.server: StrOption = \
            StrOption('server', "Name of server where database is located")
        #: Database connection string
        self.dsn: StrOption = \
            StrOption('dsn', "Database connection string")
        #: Database file specification or alias
        self.database: StrOption = \
            StrOption('database', "Database file specification or alias")
        #: Database filename should be passed in UTF8
        self.utf8filename: BoolOption = \
            BoolOption('utf8filename', "Database filename should be passed in UTF8")
        #: Protocol to be used for databasem value is `.NetProtocol`
        self.protocol: EnumOption = \
            EnumOption('protocol', NetProtocol, "Protocol to be used for database")
        #: Defaul user name, default is envar ISC_USER or None if not specified
        self.user: StrOption = \
            StrOption('user', "Defaul user name", default=os.environ.get('ISC_USER', None))
        #: Default user password, default is envar ISC_PASSWORD or None if not specified
        self.password: StrOption = \
            StrOption('password', "Default user password",
                      default=os.environ.get('ISC_PASSWORD', None))
        #: Use trusted authentication, default: False
        self.trusted_auth: BoolOption = \
            BoolOption('trusted_auth', "Use trusted authentication", default=False)
        #: User role
        self.role: StrOption = \
            StrOption('role', "User role")
        #: Character set for database connection
        self.charset: StrOption = \
            StrOption('charset', "Character set for database connection")
        #: SQL Dialect for database connection, default: 3
        self.sql_dialect: IntOption = \
            IntOption('sql_dialect', "SQL Dialect for database connection", default=3)
        #: Connection timeout
        self.timeout: IntOption = \
            IntOption('timeout', "Connection timeout")
        #: Do not use linger for database connection
        self.no_linger: BoolOption = \
            BoolOption('no_linger', "Do not use linger for database connection")
        #: Page cache size override for database connection
        self.cache_size: IntOption = \
            IntOption('cache_size', "Page cache size override for database connection")
        #: Dummy packet interval for this database connection
        self.dummy_packet_interval: IntOption = \
            IntOption('dummy_packet_interval',
                      "Dummy packet interval")
        #: Configuration override
        self.config: StrOption = \
            StrOption('config', "Configuration override")
        #: List of authentication plugins override
        self.auth_plugin_list: StrOption = \
            StrOption('auth_plugin_list', "List of authentication plugins override")
        #: Session time zone [Firebird 4]
        self.session_time_zone: StrOption = \
            StrOption('session_time_zone', "Session time zone")
        #: Set BIND [Firebird 4]
        self.set_bind: StrOption = \
            StrOption('set_bind', "Set BIND - sets up columns coercion rules in session")
        #: Set DECFLOAT ROUND [Firebird 4], value is `.DecfloatRound`
        self.decfloat_round: EnumOption = \
            EnumOption('decfloat_round', DecfloatRound, "DECFLOAT round mode")
        #: Set DECFLOAT TRAPS [Firebird 4], values are `.DecfloatTraps`
        self.decfloat_traps: ListOption = \
            ListOption('decfloat_traps', DecfloatTraps,
                       "Which DECFLOAT exceptional conditions cause a trap")
        # Create options
        #: Database create option. Page size to be used.
        self.page_size: IntOption = \
            IntOption('page_size', "Page size to be used for created database.")
        #: Database create option. Write mode (True = sync/False = async).
        self.forced_writes: BoolOption = \
            BoolOption('forced_writes', "Write mode for created database (True = sync, False = async)")
        #: Database create option. Character set for the database.
        self.db_charset: StrOption = \
            StrOption('db_charset', "Character set for created database")
        #: Database create option. SQL dialect for the database.
        self.db_sql_dialect: IntOption = \
            IntOption('db_sql_dialect', "SQL dialect for created database")
        #: Database create option. Page cache size override for database.
        self.db_cache_size: IntOption = \
            IntOption('db_cache_size', "Page cache size override for created database")
        #: Database create option. Sweep interval for the database.
        self.sweep_interval: IntOption = \
            IntOption('sweep_interval', "Sweep interval for created database")
        #: Database create option. Data page space usage (True = reserve space, False = Use all space).
        self.reserve_space: BoolOption = \
            BoolOption('reserve_space',
                       "Data page space usage for created database (True = reserve space, False = Use all space)")

class DriverConfig(Config):
    """Firebird driver configuration.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Path to Firebird client library
        self.fb_client_library: StrOption = \
            StrOption('fb_client_library', "Path to Firebird client library")
        #: BLOB size threshold. Bigger BLOB will be returned as stream BLOBs.
        self.stream_blob_threshold: IntOption = \
            IntOption('stream_blob_threshold',
                      "BLOB size threshold. Bigger BLOB will be returned as stream BLOBs.",
                      default=65536)
        #: Default database configuration ('firebird.db.defaults')
        self.db_defaults: DatabaseConfig = DatabaseConfig('firebird.db.defaults',
                                                          optional=True,
                                                          description="Default database configuration.")
        #: Default server configuration ('firebird.server.defaults')
        self.server_defaults: ServerConfig = ServerConfig('firebird.server.defaults',
                                                          optional=True,
                                                          description="Default server configuration.")
        #: Registered servers
        self.servers: ConfigListOption = \
            ConfigListOption('servers', "Registered servers", ServerConfig)
        #: Registered databases
        self.databases: ConfigListOption = \
            ConfigListOption('databases', "Registered databases", DatabaseConfig)
    def read(self, filenames: Union[str, Iterable], encoding: str=None):
        """Read configuration from a filename or an iterable of filenames.

        Files that cannot be opened are silently ignored; this is
        designed so that you can specify an iterable of potential
        configuration file locations (e.g. current directory, user's
        home directory, systemwide directory), and all existing
        configuration files in the iterable will be read.  A single
        filename may also be given.

        Return list of successfully read files.
        """
        parser = ConfigParser(interpolation=ExtendedInterpolation())
        read_ok = parser.read(filenames, encoding)
        if read_ok:
            self.load_config(parser)
        return read_ok
    def read_file(self, f):
        """Read configuration from a file-like object.

        The `f` argument must be iterable, returning one line at a time.
        """
        parser = ConfigParser(interpolation=ExtendedInterpolation())
        parser.read_file(f)
        self.load_config(parser)
    def read_string(self, string: str) -> None:
        """Read configuration from a given string.
        """
        parser = ConfigParser(interpolation=ExtendedInterpolation())
        parser.read_string(string)
        self.load_config(parser)
    def read_dict(self, dictionary: Dict) -> None:
        """Read configuration from a dictionary.

        Keys are section names, values are dictionaries with keys and values
        that should be present in the section. If the used dictionary type
        preserves order, sections and their keys will be added in order.

        All types held in the dictionary are converted to strings during
        reading, including section names, option names and keys.
        """
        parser = ConfigParser(interpolation=ExtendedInterpolation())
        parser.read_dict(dictionary)
        self.load_config(parser)
    def get_server(self, name: str) -> ServerConfig:
        """Returns server configuration.
        """
        for srv in self.servers.value:
            if srv.name == name:
                return srv
        return None
    def get_database(self, name: str) -> DatabaseConfig:
        """Returns database configuration.
        """
        for db in self.databases.value:
            if db.name == name:
                return db
        return None
    def register_server(self, name: str, config: str=None) -> ServerConfig:
        """Register server.

        Arguments:
            name: Server name.
            config: Optional server configuration string in ConfigParser format in [name] section.

        Returns:
           ServerConfig: For newly registered server

        Raises:
            ValueError: If server is already registered.
        """
        if self.get_server(name) is not None:
            raise ValueError(f"Server '{name}' already registered.")
        srv_config = ServerConfig(name)
        self.servers.value.append(srv_config)
        if config:
            parser = ConfigParser(interpolation=ExtendedInterpolation())
            parser.read_string(config)
            srv_config.load_config(parser, name)
        return srv_config
    def register_database(self, name: str, config: str=None) -> DatabaseConfig:
        """Register database.

        Arguments:
            name: Database name.
            config: Optional database configuration string in ConfigParser format in [name] section.

        Returns:
           DatabaseConfig: For newly registered database

        Raises:
            ValueError: If database is already registered.
        """
        if self.get_database(name) is not None:
            raise ValueError(f"Database '{name}' already registered.")
        db_config = DatabaseConfig(name)
        self.databases.value.append(db_config)
        if config:
            parser = ConfigParser(interpolation=ExtendedInterpolation())
            parser.read_string(config)
            db_config.load_config(parser, name)
        return db_config

# Configuration

driver_config: DriverConfig = DriverConfig('firebird.driver')
