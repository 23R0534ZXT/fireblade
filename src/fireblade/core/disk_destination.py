"""Prevent case writes to a physical disk selected as evidence."""

import os
import re
import stat
import struct
from pathlib import Path


def windows_volume_disks(drive):
    r"""Query VOLUME_DISK_EXTENTS without asking for read access to the volume.

    Opening \\.\C: for reading needs administrator rights, so every non-elevated
    analyst had the physical-device path refused with "use an acquired image".
    Opening the volume with no access at all is enough for the IOCTL and works for
    a normal user; the handle is closed as soon as the extents are read.
    """
    import ctypes
    from ctypes import wintypes

    if not re.fullmatch(r"[A-Za-z]:", drive):
        raise ValueError(
            "Le case doit être sur un volume local identifiable pour une lecture physique."
        )
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    invalid = wintypes.HANDLE(-1).value
    handle = create("\\\\.\\" + drive, 0, 3, None, 3, 0, None)
    if handle == invalid:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        ioctl = kernel32.DeviceIoControl
        ioctl.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        ioctl.restype = wintypes.BOOL
        buffer = ctypes.create_string_buffer(65536)
        returned = wintypes.DWORD()
        if not ioctl(handle, 0x560000, None, 0, buffer, len(buffer), ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)
    return parse_windows_extents(buffer.raw[: returned.value])


def parse_windows_extents(payload):
    if len(payload) < 8:
        raise ValueError("Réponse de localisation du volume tronquée")
    count = struct.unpack_from("<I", payload)[0]
    if not count or count > (len(payload) - 8) // 24:
        raise ValueError("Étendues de volume invalides")
    return {struct.unpack_from("<I", payload, 8 + index * 24)[0] for index in range(count)}


def linux_backing_disks(device, seen=None):
    seen = set() if seen is None else seen
    path = Path("/sys/dev/block") / f"{os.major(device)}:{os.minor(device)}"
    path = path.resolve(strict=True)
    if path in seen:
        raise ValueError("Cycle dans la localisation du volume")
    seen = seen | {path}
    if (path / "partition").is_file():
        path = path.parent
    slaves = list((path / "slaves").iterdir()) if (path / "slaves").is_dir() else []
    if slaves:
        result = set()
        for slave in slaves:
            major, minor = (slave / "dev").read_text().strip().split(":")
            result.update(linux_backing_disks(os.makedev(int(major), int(minor)), seen))
        return result
    return {str(path)}


def check_physical_destination(source, workspace):
    """Fail closed if evidence and destination disks overlap or cannot be mapped."""
    workspace = Path(workspace)
    while not workspace.exists():
        workspace = workspace.parent
    try:
        if os.name == "nt":
            physical = re.fullmatch(r"\\\\\.\\PhysicalDrive(\d+)", str(source), re.IGNORECASE)
            if physical:
                source_disks = {int(physical.group(1))}
            else:
                volume = re.fullmatch(r"\\\\\.\\([A-Za-z]:)", str(source))
                if not volume:
                    raise ValueError("Chemin physique attendu : \\\\.\\PhysicalDriveN ou \\\\.\\X:")
                source_disks = windows_volume_disks(volume.group(1))
            destination_disks = windows_volume_disks(workspace.drive)
        else:
            source_stat = Path(source).stat()
            if not stat.S_ISBLK(source_stat.st_mode):
                # A normal RAW file can also exercise this stream backend.
                return
            source_disks = linux_backing_disks(source_stat.st_rdev)
            destination_disks = linux_backing_disks(workspace.stat().st_dev)
    except (OSError, ValueError) as exc:
        raise ValueError(
            "Impossible de vérifier le disque de destination ; utilisez une image acquise ou un volume identifiable. "
            + str(exc)
        ) from exc
    if source_disks & destination_disks:
        raise ValueError("Le case doit être stocké sur un autre disque physique que la source.")
