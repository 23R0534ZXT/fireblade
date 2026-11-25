"""The Host's PDF keeps the report's structure: headings, table columns, page numbers."""

import pytest

pypdf = pytest.importorskip("pypdf")

from fireblade.web.pdf import _width, text_pdf, wrap_width  # noqa: E402

REPORT = (
    "<html><head><style>p{}</style></head><body><h1>Client report</h1>"
    '<table class="kpi"><tr><td><b>3</b><br>Critical</td><td><b>1</b><br>High</td></tr></table>'
    "<h2>Findings</h2><table><thead><tr><th style='width:30%'>Level</th>"
    "<th style='width:70%'>Finding</th></tr></thead><tbody>"
    "<tr><td>High</td><td>Suspicious Service Path 10:02 → 10:15</td></tr></tbody></table>"
    "<p>Done.</p></body></html>"
)


def read(path):
    return [page.extract_text() for page in pypdf.PdfReader(str(path)).pages]


def test_a_summary_tile_reads_number_then_label(tmp_path):
    target = text_pdf(REPORT, tmp_path / "r.pdf", "Client report")
    text = read(target)[0]
    assert "3 Critical" in text and "1 High" in text


def test_a_table_keeps_its_columns_and_an_arrow_is_not_lost(tmp_path):
    text = read(text_pdf(REPORT, tmp_path / "r.pdf"))[0]
    assert "Level" in text and "Finding" in text
    assert "10:02 -> 10:15" in text and "?" not in text


def test_every_page_says_where_it_is_and_a_long_table_repeats_its_header(tmp_path):
    rows = "".join(f"<tr><td>Medium</td><td>Rule number {n}</td></tr>" for n in range(200))
    markup = (
        "<h1>T</h1><table><thead><tr><th>Level</th><th>Finding</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )
    pages = read(text_pdf(markup, tmp_path / "r.pdf", "Long"))
    assert len(pages) > 2
    assert all(f"page {n} / {len(pages)}" in page for n, page in enumerate(pages, start=1))
    assert all("Level" in page and "Finding" in page for page in pages)


def test_wrapping_is_by_width_so_capitals_do_not_overrun():
    token = "BACKGROUNDTASKHOST.EXE-04A46BB6.pf"
    for line in wrap_width(token, 100, 8.5):
        assert _width(line, 8.5) <= 100
    assert "".join(wrap_width(token, 100, 8.5)) == token
