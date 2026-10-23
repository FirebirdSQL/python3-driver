"""Runtime provider contract and the driver's system-client implementation."""

from __future__ import annotations

import ctypes
import re
import sys
from contextlib import suppress
from ctypes.util import find_library
from importlib import import_module
from pathlib import Path
from typing import Protocol


class FirebirdProvider(Protocol):
    """Description of a Firebird-compatible runtime supplied to the driver."""

    @property
    def name(self) -> str:
        """Runtime implementation identifier."""
        ...

    @property
    def package_version(self) -> str:
        """Version of the distribution supplying this runtime."""
        ...

    @property
    def firebird_version(self) -> str:
        """Version of the supplied client library."""
        ...

    @property
    def root(self) -> Path:
        """Runtime root directory."""
        ...

    @property
    def client_library(self) -> Path:
        """Client library to load."""
        ...

    @property
    def firebird_log(self) -> Path | None:
        """Path to a directly accessible Firebird log, if available."""
        ...

    @property
    def capabilities(self) -> frozenset[str]:
        """Features supplied by this runtime."""
        ...


class _DriverProvider:
    """Provider for an explicitly selected or system Firebird client library."""

    def __init__(self, client_library: str | Path | None = None):
        if client_library is None:
            if sys.platform == 'darwin':
                name = 'Firebird'
            elif sys.platform == 'win32':
                name = 'fbclient.dll'
            else:
                name = 'fbclient'
            located = find_library(name)
            if not located and sys.platform not in ('darwin', 'win32'):
                with suppress(OSError):
                    ctypes.CDLL('libfbclient.so')
                    located = 'libfbclient.so'
            if not located:
                raise FileNotFoundError('The location of Firebird Client Library could not be determined.')
            self._client_library = Path(located)
        else:
            self._client_library = Path(client_library)
            if not self._client_library.is_file():
                raise FileNotFoundError(f"Firebird Client Library '{self._client_library}' not found")
        self._root: Path | None = None
        self._firebird_version: str | None = None
        self._capabilities: frozenset[str] | None = None

    @property
    def name(self) -> str:
        """Runtime implementation identifier."""
        return 'firebird'

    @property
    def package_version(self) -> str:
        """Version of the firebird-driver distribution."""
        return import_module('firebird.driver').__VERSION__

    @property
    def firebird_version(self) -> str:
        """Version of the loaded Firebird client library."""
        if self._firebird_version is None:
            raise RuntimeError('Provider metadata is not initialized')
        return self._firebird_version

    @property
    def root(self) -> Path:
        """Root directory reported by the client API."""
        if self._root is None:
            raise RuntimeError('Provider metadata is not initialized')
        return self._root

    @property
    def client_library(self) -> Path:
        """Client library to load."""
        return self._client_library

    @property
    def firebird_log(self) -> Path | None:
        """The system client's Firebird log location is not known."""
        return None

    @property
    def capabilities(self) -> frozenset[str]:
        """Capabilities of the loaded runtime."""
        if self._capabilities is None:
            raise RuntimeError('Provider metadata is not initialized')
        return self._capabilities

    def _initialize(self, root: str, version: tuple[int, int]) -> None:
        """Complete metadata once the client interfaces are available."""
        runtime_root = Path(root)
        if not root:
            raise RuntimeError('The Firebird client did not report a root directory')
        extension = 'dll' if sys.platform == 'win32' else 'so'
        pattern = re.compile(rf'(?:lib)?engine[0-9]+\.{extension}', re.IGNORECASE)
        capabilities = {'client'}
        plugins = runtime_root / 'plugins'
        if plugins.is_dir() and any(pattern.fullmatch(path.name) for path in plugins.iterdir()):
            capabilities.add('embedded')
        self._root = runtime_root
        self._firebird_version = f'{version[0]}.{version[1]}'
        self._capabilities = frozenset(capabilities)
