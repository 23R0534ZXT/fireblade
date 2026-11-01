from pathlib import Path
import pytest

from fireblade.core import plugin_registry
from fireblade.core.reader_detection import detect_reader


@pytest.fixture
def installed(tmp_path, monkeypatch):
    from fireblade.core.reader_detection import reader_directories
    folder = reader_directories()[0]
    folder.mkdir(parents=True)
    dll = folder / 'Example.dll'
    dll.write_bytes(b'fake assembly for metadata tests')
    calls = []
    def inspect(path, check):
        check()
        calls.append(Path(path))
        return [dict(type='Typed.Reader', headers=['Text,Identifier']),
                dict(type='Generic.Reader', headers=[])]
    monkeypatch.setattr('fireblade.core.tle_plugins.inspect_plugin', inspect)
    return dll, calls


@pytest.mark.parametrize('encoding,header', [
    ('utf-8', 'Text,Identifier\n'),
    ('utf-8-sig', '"TEXT","identifier"\r\n'),
    ('utf-16', 'Text,Identifier\n'),
    ('utf-32', '#TYPE Test\r\nText,Identifier\r\n'),
    ('cp1252', ' Text , Identifier \n'),
])
def test_first_csv_matches_without_manual_binding(tmp_path, installed, encoding, header):
    dll, calls = installed
    source = tmp_path / 'first.csv'
    source.write_text(header+'évidence,0001\n', encoding=encoding)
    original = source.read_bytes()
    assert detect_reader(source) == (dll, 'Typed.Reader')
    assert calls == [dll] and source.read_bytes() == original
    assert plugin_registry.reader_for_source(source) is None
    # A second filename reuses the persisted catalog, without reloading .NET.
    other = tmp_path / 'other.csv'
    other.write_bytes(original)
    assert detect_reader(other) == (dll, 'Typed.Reader')
    assert calls == [dll]


@pytest.mark.parametrize('header', ['Identifier,Text\n', 'Text,Identifier,Extra\n', 'Other,Data\n', ''])
def test_no_subset_match_or_generic_override(tmp_path, installed, header):
    source = tmp_path/'unknown.csv'
    source.write_text(header)
    assert detect_reader(source) is None


def test_changed_installed_dll_refreshes_catalog(tmp_path, installed):
    dll, calls = installed
    source = tmp_path/'first.csv'; source.write_text('Text,Identifier\n')
    detect_reader(source)
    dll.write_bytes(b'updated installed assembly')
    assert detect_reader(source) == (dll, 'Typed.Reader')
    assert calls == [dll, dll]


def test_approved_reader_and_explicit_binding_take_precedence(tmp_path, monkeypatch):
    dll = tmp_path/'chosen.dll'; dll.write_bytes(b'approved')
    source = tmp_path/'chosen.custom'; source.write_text('not a CSV')
    plugin_registry.approve(dll, source=source, reader='Explicit.Reader')
    monkeypatch.setattr('fireblade.core.tle_plugins.inspect_plugin', lambda *_: pytest.fail('binding should skip inspection'))
    assert detect_reader(source) == (dll, 'Explicit.Reader')
    dll.write_bytes(b'changed')
    with pytest.raises(ValueError, match='modifié'):
        detect_reader(source)


def test_dll_beside_csv_is_never_loaded(tmp_path, monkeypatch):
    (tmp_path/'untrusted.dll').write_bytes(b'not installed')
    source = tmp_path/'source.csv'; source.write_text('Text,Identifier\n')
    monkeypatch.setattr('fireblade.core.tle_plugins.inspect_plugin', lambda *_: pytest.fail('uninstalled DLL'))
    assert detect_reader(source) is None


def test_conflicting_readers_require_explicit_choice(tmp_path, installed, monkeypatch):
    dll, _ = installed
    (dll.parent/'Second.dll').write_bytes(b'another installed reader')
    source = tmp_path/'ambiguous.csv'; source.write_text('Text,Identifier\n')
    with pytest.raises(ValueError, match='ambigu'):
        detect_reader(source)


def test_probe_reads_only_header_prefix(tmp_path, installed, monkeypatch):
    source = Path('/workspace/scratch/existing-3gib/Fireblade-test-3GiB.csv')
    if not source.is_file():
        pytest.skip('Existing 3 GiB dataset not present')
    original = Path.open
    def checked_open(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        if path != source:
            return stream
        class Bounded:
            def __enter__(self): return self
            def __exit__(self, *args): stream.close()
            def read(self, size=-1):
                assert 0 < size <= 65536
                return stream.read(size)
        return Bounded()
    monkeypatch.setattr(Path, 'open', checked_open)
    assert detect_reader(source) is None


def test_header_with_tab_separator_and_alternative_signature(tmp_path, installed, monkeypatch):
    dll, _ = installed
    monkeypatch.setattr('fireblade.core.tle_plugins.inspect_plugin',
                        lambda *_: [dict(type='TSV.Reader',headers=['Other\tVersion', 'Text\tIdentifier'])])
    source=tmp_path/'input.tsv';source.write_text('"Text"\t"Identifier"\nvalue\t1\n')
    assert detect_reader(source)==(dll,'TSV.Reader')


def test_oversized_header_cannot_match_a_truncated_prefix(tmp_path, installed):
    source=tmp_path/'wide.csv';source.write_text('Text,Identifier'+(' '*65536)+'\n')
    assert detect_reader(source) is None


def test_native_dependency_does_not_block_reader_detection(tmp_path, installed, monkeypatch):
    dll, _ = installed
    (dll.parent/'Native.dll').write_bytes(b'native dependency')
    def inspect(path, check):
        if path.name=='Native.dll':
            raise ValueError('BadImageFormatException: native dependency')
        return [dict(type='Typed.Reader',headers=['Text,Identifier'])]
    monkeypatch.setattr('fireblade.core.tle_plugins.inspect_plugin',inspect)
    source=tmp_path/'first.csv';source.write_text('Text,Identifier\n')
    assert detect_reader(source)==(dll,'Typed.Reader')


def test_cancellation_stops_detection(tmp_path, installed):
    import threading
    from fireblade.core.errors import cancellation_scope,OperationCancelled
    source=tmp_path/'first.csv';source.write_text('Text,Identifier\n')
    event=threading.Event();event.set()
    with cancellation_scope(event),pytest.raises(OperationCancelled):
        detect_reader(source)


def test_quoted_single_field_is_not_a_two_column_signature(tmp_path, installed):
    source=tmp_path/'single.csv';source.write_text('"Text,Identifier"\nvalue\n')
    assert detect_reader(source) is None
