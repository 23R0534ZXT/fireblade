"""The Linux reader runs in its own process, and degrades instead of failing."""
from pathlib import Path

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.parse_pool import ParsePool


def test_a_file_is_read_in_another_process(tmp_path):
    source = tmp_path / "auth.log"
    source.write_text("Jan  2 03:04:05 host sshd[42]: Accepted password for root from 10.0.0.5 port 22 ssh2\n",
                      encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    pool = ParsePool(2).start()
    try:
        result = pool.run(source, out)
    finally:
        pool.close()
    assert result["outputs"], "the child wrote an analysis"
    assert Path(result["outputs"][0]["csv"]).exists()


def test_a_pool_that_cannot_start_falls_back_on_this_process(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "auth.log").write_text("Jan  2 03:04:05 host sshd[42]: Accepted password for root from 10.0.0.5 port 22 ssh2\n",
                                   encoding="utf-8")
    collection = Collection(root, tmp_path / "work", ToolPack(tmp_path / "pack"))

    def refuse(self, source, output):
        raise RuntimeError("le processus de lecture n'a pas démarré")

    monkeypatch.setattr(ParsePool, "run", refuse)
    report = collection.parse()
    assert report["status"] == "complete"
    assert report["documents"], "the file is still read, in this process"
    assert collection.parser_pool() is None
