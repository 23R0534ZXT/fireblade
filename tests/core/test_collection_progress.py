"""The import percentage: what it counts, and what it refuses to claim.

A folder of a hundred and nineteen files must show where it stands while it reads them,
and the number must follow the work, not the number of files: one 4 GB image is not the
same amount of reading as one 2 KB text file.
"""

from fireblade.core.collection import CollectionProgress


def test_the_percentage_follows_the_size_of_what_is_read():
    progress = CollectionProgress()
    progress.inventory([100, 900])  # one small file, one big one
    progress.begin("small.log", 100)
    progress.finish_current()
    assert progress.snapshot()["percent"] == 10.0


def test_nothing_is_claimed_complete_before_the_end():
    progress = CollectionProgress()
    progress.inventory([1, 1])
    progress.begin("one.csv", 1)
    progress.finish_current()
    progress.begin("two.csv", 1)
    state = progress.snapshot()
    assert 50.0 <= state["percent"] < 99.0
    assert state["done"] == 1 and state["total"] == 2
    progress.finish_current()
    progress.done_all()
    assert progress.snapshot()["percent"] == 100.0


def test_the_rows_a_parser_wrote_are_read_from_its_message():
    progress = CollectionProgress()
    progress.inventory([1])
    progress.begin("Security.evtx", 1)
    progress.note("Import sur disque · 12 345 enregistrements écrits…")
    assert progress.snapshot()["rows"] == 12345
    progress.note("Collecte : autre fichier")
    assert progress.snapshot()["rows"] == 12345, "an unrelated message reset the count"


def test_the_current_file_is_named_while_it_is_read():
    progress = CollectionProgress()
    progress.inventory([1, 1])
    progress.begin("C:/evidence/Security.evtx", 1)
    state = progress.snapshot()
    assert state["current"].endswith("Security.evtx")
    assert state["done"] == 0
    assert state["remaining"] == 0, "a remaining time was promised before any file finished"
