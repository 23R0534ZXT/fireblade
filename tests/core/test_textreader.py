"""Text and saved pages must be read, not guessed at, and never silently dropped."""

import csv

from fireblade.core import textreader


def test_a_plain_text_file_keeps_its_lines_and_its_accents(tmp_path):
    path = tmp_path / "note.txt"
    path.write_bytes("Réunion du 14/11/2026 09:30\nligne deux\n".encode("cp1252"))
    produced = textreader.rows(path)
    assert produced[0][1] == 1 and "Réunion" in produced[0][3]
    # A date inside a sentence is text, not a timestamp: nothing is invented.
    assert produced[0][2] == ""
    assert len(produced) == 2


def test_a_leading_date_becomes_a_column_and_is_never_invented(tmp_path):
    path = tmp_path / "journal.log"
    path.write_text(
        "2026-11-14 08:12:00 demarrage\nsans date\n[2026-11-14 09:00] reprise\n", encoding="utf-8"
    )
    stamps = [row[2] for row in textreader.rows(path)]
    assert stamps == ["2026-11-14 08:12:00", "", "2026-11-14 09:00"]


def test_a_saved_page_yields_visible_text_and_its_links(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><title>Rapport</title><style>b{}</style></head>"
        "<body><h1>Rapport</h1><p>Le 14/11/2026 10:00 &amp; fin.</p>"
        '<script>var x=1</script><a href="https://exemple.fr/a">lien</a></body></html>',
        encoding="utf-8",
    )
    produced = textreader.rows(path)
    text = " ".join(row[3] for row in produced)
    links = [row[4] for row in produced if row[4]]
    assert "Rapport" in text and "& fin." in text
    assert "var x" not in text and "b{}" not in text
    assert links == ["https://exemple.fr/a"]


def test_html_is_recognised_by_content_when_the_suffix_lies(tmp_path):
    path = tmp_path / "save.dat"
    path.write_text("<!doctype html><html><body>bonjour</body></html>", encoding="utf-8")
    assert textreader.sniff(path) == "html"


def test_a_binary_file_is_refused_instead_of_read_as_text(tmp_path):
    path = tmp_path / "opaque.dat"
    path.write_bytes(bytes(range(256)))
    assert textreader.sniff(path) is None


def test_invalid_bytes_survive_the_read_instead_of_killing_it(tmp_path):
    path = tmp_path / "mixte.txt"
    path.write_bytes(b"bonjour\n\xff\xfe fin\n")
    produced = textreader.rows(path)
    assert len(produced) == 2 and "bonjour" in produced[0][3]


def test_the_csv_carries_one_row_per_line_and_a_header(tmp_path):
    source = tmp_path / "note.txt"
    source.write_text("un\ndeux\n", encoding="utf-8")
    target = tmp_path / "note.csv"
    result = textreader.write_csv(source, target)
    rows = list(csv.reader(target.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == list(textreader.HEADERS)
    assert result["rows"] == 2 and result["kind"] == "text"
    assert rows[1][0].endswith("note.txt")


def test_a_huge_file_is_capped_not_exploded(tmp_path):
    path = tmp_path / "gros.log"
    path.write_text("\n".join(f"ligne {index}" for index in range(500)), encoding="utf-8")
    assert len(textreader.rows(path, limit_lines=10)) == 10


def test_a_file_read_in_part_is_reported_as_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(textreader, "LIMIT_BYTES", 8)
    path = tmp_path / "gros.txt"
    path.write_text("une ligne bien plus longue que huit octets\n", encoding="utf-8")
    result = textreader.write_csv(path, tmp_path / "out.csv")
    assert result["truncated"] and result["rows"] == 1


def test_a_file_read_whole_is_not_marked_truncated(tmp_path):
    path = tmp_path / "court.txt"
    path.write_text("deux lignes\ncourtes\n", encoding="utf-8")
    result = textreader.write_csv(path, tmp_path / "out.csv")
    assert not result["truncated"] and result["size"] > 0


def test_a_powershell_utf16_log_is_read_as_text_not_as_bytes(tmp_path):
    """Windows writes UTF-16LE with a BOM as soon as output is redirected."""
    path = tmp_path / "ps.log"
    path.write_bytes(b"\xff\xfe" + "Sortie du script\nligne accentuée é\n".encode("utf-16-le"))
    produced = textreader.rows(path)
    assert [row[3] for row in produced] == ["Sortie du script", "ligne accentuée é"]
    assert textreader.sniff(path) == "text"


def test_a_utf8_bom_does_not_end_up_in_the_first_line(tmp_path):
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbf" + "2026-11-14 08:00 première ligne\n".encode())
    produced = textreader.rows(path)
    assert not produced[0][3].startswith("\ufeff")
    assert produced[0][3].startswith("2026-11-14 08:00")
    assert produced[0][2] == "2026-11-14 08:00", "le BOM ne doit pas empêcher la date d'être lue"


def test_a_page_saved_in_the_french_code_page_keeps_its_accents(tmp_path):
    path = tmp_path / "page.html"
    path.write_bytes("<html><body><p>Décision préfectorale</p></body></html>".encode("cp1252"))
    text = " ".join(row[3] for row in textreader.rows(path))
    assert "Décision préfectorale" in text


def test_a_page_that_declares_its_charset_is_read_with_it(tmp_path):
    path = tmp_path / "declare.html"
    path.write_bytes(
        b'<html><head><meta charset="windows-1252"></head>'
        b"<body><p>El\xe8ve convoqu\xe9</p></body></html>"
    )
    text = " ".join(row[3] for row in textreader.rows(path))
    assert "Elève convoqué" in text


def test_a_utf16_page_is_read_through_its_bom(tmp_path):
    path = tmp_path / "page16.html"
    path.write_bytes(
        b"\xff\xfe" + "<html><body><p>Pièce jointe</p></body></html>".encode("utf-16-le")
    )
    assert textreader.sniff(path) == "html"
    text = " ".join(row[3] for row in textreader.rows(path))
    assert "Pièce jointe" in text
