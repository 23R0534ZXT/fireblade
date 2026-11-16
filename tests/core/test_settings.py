import pytest

from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.settings import Settings, load_settings


def test_custom_resource_settings_reach_engine(tmp_path):
    config = tmp_path / 'custom.toml'
    config.write_text('[resources]\nmemory_mb=128\nthreads=1\npage_size=25\nmax_loaded_rows=50\nexport_batch_rows=1\n')
    settings = load_settings(config)
    source = tmp_path / 'sample.csv'
    source.write_text('ID,Artifact\n' + ''.join(f'{i},MFT\n' for i in range(80)))
    case = Case(tmp_path / 'sample.timeline', settings=settings)
    try:
        case.import_csv(source)
        assert len(case.page(View())) == 25
        assert case.page(View(), offset=25)[0][1] == '25'
        assert case.db.execute("SELECT current_setting('threads')").fetchone()[0] == 1
        output = tmp_path / 'out.csv'
        case.export(output, View())
        assert len(output.read_text(encoding='utf-8-sig').splitlines()) == 81
    finally:
        case.close()


@pytest.mark.parametrize('content', [
    '[resources]\nmemory_mb=0', '[resources]\nthreads=true',
    '[resources]\npage_size=25\nmax_loaded_rows=26',
    '[resources]\npage_size=1001', '[resources]\nunknown=10',
    '[other]\nthreads=1', 'resources=3',
    '[resources]\ncache_sorted_pages=1',
])
def test_invalid_resource_settings_fail_explicitly(tmp_path, content):
    config = tmp_path / 'invalid.toml'
    config.write_text(content)
    with pytest.raises(ValueError):
        load_settings(config)


def test_default_settings_and_partial_config(tmp_path):
    assert load_settings() == Settings()
    config = tmp_path / 'partial.toml'
    config.write_text('[resources]\nthreads=1')
    assert load_settings(config).memory_mb == 1024
    assert load_settings(config).threads == 1


def test_a_budget_that_cannot_spill_grows_but_never_eats_the_machine():
    from fireblade.core.settings import grown_memory
    assert grown_memory(128, ceiling_mb=2048) == 640
    assert grown_memory(1024, ceiling_mb=2048) == 2048
    assert grown_memory(2048, ceiling_mb=2048) is None, "plus de place : le dire au lieu de forcer"
    assert grown_memory(0, ceiling_mb=2048) == 512


def test_the_shipped_default_leaves_room_for_a_real_export():
    from fireblade.core.settings import Settings
    assert Settings().memory_mb >= 1024, "128 Mo ne suffit pas à un export de collecte"

def test_automatic_threads_are_resolved_before_the_engine_sees_them(tmp_path):
    from fireblade.core.settings import auto_threads

    assert auto_threads(cpu=20) == 8, 'le genou mesure : huit fichiers a la fois'
    assert auto_threads(cpu=2) == 2 and auto_threads(cpu=1) == 1
    assert Settings(threads=0).effective_threads == auto_threads()
    assert Settings(threads=4).effective_threads == 4
    # A setting of zero must never reach DuckDB: it refuses it and the import dies
    # without a visible error.
    source = tmp_path/'sample.csv'
    source.write_text('ID,Artifact\n' + ''.join(f'{index},MFT\n' for index in range(40)))
    case = Case(tmp_path/'automatic.timeline', settings=Settings(threads=0, memory_mb=256))
    try:
        case.import_csv(source)
        assert case.db.execute("SELECT current_setting('threads')").fetchone()[0] == auto_threads()
        assert case.info['rows'] == 40
    finally:
        case.close()


def test_parsing_threads_ship_on_automatic():
    from fireblade.core.preferences import Preferences
    preferences = Preferences()
    assert preferences.parsing_threads == 0
    preferences.validate()
