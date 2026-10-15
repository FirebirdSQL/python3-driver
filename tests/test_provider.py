"""Runtime provider tests that do not need a Firebird installation."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from firebird.driver import __VERSION__, fbapi
from firebird.driver.provider import _DriverProvider


def test_explicit_library_is_authoritative(tmp_path, monkeypatch):
    library = tmp_path / 'fbclient.so'
    library.touch()
    monkeypatch.setattr('firebird.driver.provider.find_library', lambda _: pytest.fail('unexpected lookup'))

    provider = _DriverProvider(library)

    assert provider.client_library == library
    assert provider.name == 'firebird'
    assert provider.package_version == __VERSION__
    with pytest.raises(RuntimeError, match='not initialized'):
        _ = provider.root
    with pytest.raises(FileNotFoundError):
        _DriverProvider(tmp_path / 'missing.so')


def test_system_library_lookup(monkeypatch):
    monkeypatch.setattr('firebird.driver.provider.find_library', lambda _: 'libfbclient.so.2')

    assert _DriverProvider().client_library == Path('libfbclient.so.2')


@pytest.mark.parametrize(('plugin', 'embedded'), [
    ('engine13.so', True),
    ('engine.so', False),
    ('engine13.so.bak', False),
])
def test_metadata_from_loaded_client(tmp_path, plugin, embedded):
    library = tmp_path / 'libfbclient.so'
    library.touch()
    runtime_root = tmp_path / 'runtime'
    plugins = runtime_root / 'plugins'
    runtime_root.mkdir()
    plugins.mkdir()
    (plugins / plugin).touch()
    provider = _DriverProvider(library)
    api = SimpleNamespace(
        _provider=provider,
        master=SimpleNamespace(get_config_manager=lambda: SimpleNamespace(
            get_root_directory=lambda: str(runtime_root))),
        util=SimpleNamespace(get_client_version=lambda: (5, 0)),
    )

    fbapi.FirebirdAPI._initialize_provider(api)

    assert provider.root == runtime_root
    assert provider.firebird_version == '5.0'
    assert provider.capabilities == (frozenset({'client', 'embedded'}) if embedded else frozenset({'client'}))
    assert fbapi.FirebirdAPI.provider.fget(api) is provider


def test_firebird_api_loads_supplied_provider(tmp_path, monkeypatch):
    library = tmp_path / 'libfbclient.so'
    provider = SimpleNamespace(name='firebird', package_version='5.0.4.0',
                               firebird_version='5.0.4', root=tmp_path,
                               client_library=library, capabilities=frozenset({'client', 'embedded'}))
    client = MagicMock()
    load = MagicMock(return_value=client)
    monkeypatch.setattr(fbapi.ctypes, 'CDLL', load)
    monkeypatch.setattr(fbapi, 'CFUNCTYPE', lambda *_args: lambda _: SimpleNamespace(argtypes=[]))

    api = fbapi.FirebirdAPI(provider=provider)

    load.assert_called_once_with(str(library), mode=fbapi.ctypes.RTLD_GLOBAL)
    assert api.provider is provider
    assert api.client_library_name == library
    with pytest.raises(AttributeError):
        api.provider = provider


def test_load_api_uses_external_provider(tmp_path, monkeypatch):
    provider = SimpleNamespace(client_library=tmp_path / 'fbclient.so')
    seen = []
    monkeypatch.setattr(fbapi, 'api', None)
    monkeypatch.setattr(fbapi, 'FirebirdAPI', lambda *, provider: seen.append(provider) or object())
    monkeypatch.setattr(fbapi, 'get_callbacks', lambda *_: [])

    fbapi.load_api(provider)

    assert seen == [provider]


def test_load_api_wraps_filename(tmp_path, monkeypatch):
    library = tmp_path / 'fbclient.so'
    library.touch()
    seen = []
    monkeypatch.setattr(fbapi, 'api', None)
    monkeypatch.setattr(fbapi, 'FirebirdAPI', lambda *, provider: seen.append(provider) or object())
    monkeypatch.setattr(fbapi, 'get_callbacks', lambda *_: [])

    fbapi.load_api(str(library))

    assert isinstance(seen[0], _DriverProvider)
    assert seen[0].client_library == library


def test_failed_initialization_does_not_cache_api(tmp_path, monkeypatch):
    provider = SimpleNamespace(client_library=tmp_path / 'fbclient.so')
    monkeypatch.setattr(fbapi, 'api', None)
    monkeypatch.setattr(fbapi, 'FirebirdAPI', lambda *, provider: SimpleNamespace(provider=provider))

    def fail(_):
        raise RuntimeError('initialization failed')
    monkeypatch.setattr(fbapi, 'get_callbacks', lambda *_: [fail])

    with pytest.raises(RuntimeError, match='initialization failed'):
        fbapi.load_api(provider)

    assert not fbapi.has_api()
