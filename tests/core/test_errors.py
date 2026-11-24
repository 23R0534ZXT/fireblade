"""A failure has to arrive as a sentence someone can act on."""

from fireblade.core.errors import explain_failure


DUCKDB = """Out of Memory Error: failed to pin block of size 256.0 KiB (60.8 MiB/61.0 MiB used)

Possible solutions:
* Reducing the number of threads (SET threads=X)
* Disabling insertion-order preservation (SET preserve_insertion_order=false)
* Increasing the memory limit (SET memory_limit='...GB')

See also https://duckdb.org/docs/stable/guides/performance/how_to_tune_workloads"""


def test_an_out_of_memory_becomes_a_sentence_and_two_remedies():
    explained = explain_failure(DUCKDB, 64)
    assert explained["kind"] == "memory"
    assert "Not enough memory" in explained["summary"] and "64" in explained["summary"]
    assert any("Preferences → Resources" in line for line in explained["advice"])
    assert any("smaller batches" in line for line in explained["advice"])
    assert "failed to pin" in explained["detail"], "le texte technique reste disponible"


def test_a_source_changed_during_import_names_its_own_cause():
    explained = explain_failure("ValueError: Le fichier source a change pendant l'import")
    assert explained["kind"] == "source_changed"
    assert "changed during" in explained["summary"] and explained["advice"]


def test_anything_else_keeps_its_first_line_and_the_detail():
    explained = explain_failure('Binder Error: Referenced column "x" not found\nLINE 1: SELECT x')
    assert explained["kind"] == "other"
    assert explained["summary"] == 'Binder Error: Referenced column "x" not found'
    assert "LINE 1" in explained["detail"]
    assert explained["advice"] == []
