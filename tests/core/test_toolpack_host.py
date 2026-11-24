"""The tool pack must find a .NET host on Windows and on Linux.

The pack ships dotnet.exe for the desktop edition; the container runs the same
dll files through the distribution runtime. One branch, no change to the command
line: the tool, its arguments and its CSV stay identical.
"""

import pytest

from fireblade.core import collection
from fireblade.core.collection import ToolPack


def _pack(tmp_path, host_name, tool="WxTCmd"):
    root = tmp_path
    (root / "dotnet").mkdir(parents=True)
    (root / "dotnet" / host_name).write_bytes(b"")
    (root / tool).mkdir()
    (root / tool / f"{tool}.dll").write_bytes(b"")
    return ToolPack(root)


def test_windows_uses_the_bundled_dotnet_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "WINDOWS", True)
    pack = _pack(tmp_path, "dotnet.exe")
    command = pack.command("WxTCmd")
    assert command == [
        str(tmp_path / "dotnet" / "dotnet.exe"),
        str(tmp_path / "WxTCmd" / "WxTCmd.dll"),
    ]


def test_linux_uses_the_plain_dotnet_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "WINDOWS", False)
    pack = _pack(tmp_path, "dotnet")
    command = pack.command("WxTCmd")
    assert command[0] == str(tmp_path / "dotnet" / "dotnet")


def test_arguments_are_the_same_on_both_platforms(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "WINDOWS", False)
    pack = _pack(tmp_path, "dotnet")
    args = pack.arguments("WxTCmd", "/data/x.db", "/data/out")
    assert args[2:] == ["-f", "/data/x.db", "--csv", "/data/out"]


def test_a_missing_dll_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "WINDOWS", False)
    pack = _pack(tmp_path, "dotnet")
    (tmp_path / "WxTCmd" / "WxTCmd.dll").unlink()
    with pytest.raises(FileNotFoundError):
        pack.command("WxTCmd")
    assert pack.available("WxTCmd") is False


def test_hayabusa_binary_is_found_with_or_without_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, "WINDOWS", False)
    (tmp_path / "Hayabusa").mkdir(parents=True)
    binary = tmp_path / "Hayabusa" / "hayabusa"
    binary.write_bytes(b"")
    pack = ToolPack(tmp_path)
    assert pack.command("Hayabusa") == [str(binary)]
