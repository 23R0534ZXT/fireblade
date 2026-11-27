"""Erasing a case, field by field: the method, who did it and why, where the certificate goes,
the photos that ride in it, and what the certificate says — in English, and nothing left behind.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import re

import pytest
from _audit import status

FRENCH = re.compile(
    r"\b(octets?|Fin|Complet|Partiel|Statut|Opérateur|Témoin|Motif|Méthode|Procès|détruit|fichiers?"
    r"|avant|après|Début|Empreintes?|Nom|supprimé)\b|[àâçéèêëîïôùûü]"
)


def _open_dialog(page):
    page.click('.menubar .m[data-menu="case"]')
    page.click('.menu.show [data-act="destroy-case"]')
    page.wait_for_selector("#destroy-modal.show")
    page.wait_for_function("document.getElementById('destroy-certificate').value !== ''")


def _png(path, width, height, colour):
    """A real PNG, written by hand: the suite needs no imaging library to make a photo."""
    import struct
    import zlib

    def chunk(kind, data):
        body = kind + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    rows = b"".join(b"\x00" + bytes(colour) * width for _ in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def _photos(tmp_path, count=2):
    made = []
    for index in range(count):
        path = tmp_path / f"scene-{index}.png"
        _png(path, 90, 60, (30 * index, 90, 200))
        made.append(str(path))
    return made


def _plain(html):
    body = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


def test_the_dialog_offers_both_methods_and_says_where_the_certificate_will_go(page):
    _open_dialog(page)
    options = page.eval_on_selector_all("#destroy-method option", "els => els.map(e => e.value)")
    assert options == ["dod3", "dod7", "quick"]
    assert page.input_value("#destroy-method") == "dod3"
    assert page.input_value("#destroy-certificate").endswith("certificates")
    assert "outside the case" in page.inner_text("#destroy-certificate-note")
    assert "type that name to confirm" in page.inner_text("#destroy-target")


def test_a_wrong_confirmation_erases_nothing(page, server):
    name = page.inner_text("#casecombo-label")
    _open_dialog(page)
    page.fill("#destroy-operator", "A. Analyst")
    page.fill("#destroy-confirm", name + " (typo)")
    page.click('#destroy-modal [data-act="destroy-run"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('does not match')")
    assert any(item.is_dir() for item in server[1].iterdir()), "the case is still there"
    page.keyboard.press("Escape")


def test_cancel_closes_the_dialog_and_keeps_the_case(page):
    _open_dialog(page)
    page.fill("#destroy-confirm", "not typed in full")
    page.click('#destroy-modal [data-act="settings-close"]')
    page.wait_for_selector("#destroy-modal", state="hidden")
    assert page.locator("#body tr[data-row]").count() > 0


def test_the_certificate_carries_the_operator_the_witness_the_reason_the_method_and_the_photos(
    page, server, tmp_path
):
    name = page.inner_text("#casecombo-label")
    folder = tmp_path / "certificates-here"
    _open_dialog(page)
    page.select_option("#destroy-method", "dod7")
    page.fill("#destroy-operator", "A. Analyst")
    page.fill("#destroy-witness", "B. Witness")
    page.fill("#destroy-reason", "Contract ended on 2026-11-30")
    page.fill("#destroy-certificate", str(folder))
    page.set_input_files("#destroy-photos", _photos(tmp_path))
    page.wait_for_function("document.getElementById('destroy-photo-count').innerText.includes('2')")
    page.fill("#destroy-confirm", name)
    page.click('#destroy-modal [data-act="destroy-run"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Case erased')", timeout=90000
    )
    assert str(folder) in status(page), "the certificate went where the analyst said"
    certificates = list(folder.glob("*.html"))
    assert len(certificates) == 1
    html = certificates[0].read_text(encoding="utf-8")
    text = _plain(html)
    for wanted in (
        "Evidence destruction certificate",
        "A. Analyst",
        "B. Witness",
        "Contract ended on 2026-11-30",
        "DoD 5220.22-M — 7 passes",
        name,
        "destroyed and verified",
    ):
        assert wanted in text, wanted
    assert html.count("<img") == 2, "both photos ride in the certificate"
    assert re.search(r"[0-9a-f]{64}", text), "the fingerprints of the files are in it"
    assert not FRENCH.search(text), FRENCH.findall(text)[:8]
    assert not any(item.name == name for item in server[1].iterdir() if item.is_dir())


@pytest.mark.parametrize(("method", "passes"), [("dod3", 3), ("dod7", 7), ("quick", 0)])
def test_each_method_names_its_number_of_passes(page, tmp_path, method, passes):
    name = page.inner_text("#casecombo-label")
    folder = tmp_path / "certs"
    _open_dialog(page)
    page.select_option("#destroy-method", method)
    page.fill("#destroy-operator", "A. Analyst")
    page.fill("#destroy-certificate", str(folder))
    page.fill("#destroy-confirm", name)
    page.click('#destroy-modal [data-act="destroy-run"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Case erased')", timeout=90000
    )
    text = _plain(next(folder.glob("*.html")).read_text(encoding="utf-8"))
    assert f"Passes {passes}" in text, text[:400]
    if method == "quick":
        assert "deleted without overwrite" in page.inner_text("#status")
        assert "Deleted without overwrite" in text
        assert "destroyed and verified" not in text
        assert next(folder.glob("*.docx")).is_file()
