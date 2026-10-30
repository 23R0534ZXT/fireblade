import pytest

from timeline_next.engine import Case
from timeline_next.models import View
from timeline_next.settings import Settings, load_settings


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
    assert load_settings(config).memory_mb == 256
    assert load_settings(config).threads == 1
