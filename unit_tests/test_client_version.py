"""Tests that do not require a Firebird server or client library."""

from types import SimpleNamespace

import pytest

from firebird.driver.interfaces import iUtil


@pytest.mark.parametrize(('encoded', 'expected'), [
    (0x0300, (3, 0)),
    (0x0401, (4, 1)),
    (0x0502, (5, 2)),
])
def test_get_client_version_decodes_major_and_minor(encoded, expected):
    util = SimpleNamespace(vtable=SimpleNamespace(getClientVersion=lambda _: encoded))

    assert iUtil.get_client_version(util) == expected
