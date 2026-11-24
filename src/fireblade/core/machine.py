"""What this machine can give, and what an import is allowed to take.

A forensic tool is run on a laptop, on a small VM, and on a workstation, by people
who should not have to read a settings file to use it. The effort levels below are
the whole interface: each one is computed from the machine it runs on, so "Balanced"
means half of a 4-core VM and half of a 32-core server.
"""

import os
from dataclasses import dataclass

from fireblade.core.settings import auto_threads, physical_memory_mb

LEVELS = ("light", "balanced", "fast", "maximum")


def cores():
    return max(1, os.cpu_count() or 1)


def memory_mb():
    return physical_memory_mb()


@dataclass(frozen=True)
class Effort:
    level: str
    threads: int
    memory_mb: int
    share: float  # what fraction of the machine this takes, 0..1
    tone: str  # 'green', 'amber' or 'red'


def _fit(threads, memory, cpu, ram):
    """A level never promises more than the machine has."""
    return min(cpu, max(1, int(threads))), min(ram, max(64, int(memory)))


def tone_for(share):
    """Green while the machine stays responsive, red when the analyst will feel it."""
    if share < 0.45:
        return "green"
    if share < 0.8:
        return "amber"
    return "red"


def effort(level="balanced", cpu=None, ram=None):
    """Threads and memory for one level, on this machine."""
    cpu = cpu or cores()
    ram = ram or memory_mb()
    if level not in LEVELS:
        raise ValueError("Unknown effort level: %s" % level)
    threads, memory = {
        "light": (max(1, cpu // 4), min(512, max(256, ram // 8))),
        "balanced": (max(2, cpu // 2), min(2048, max(512, ram // 3))),
        "fast": (max(3, cpu * 3 // 4), min(4096, max(1024, ram // 2))),
        "maximum": (cpu, min(8192, max(2048, ram * 2 // 3))),
    }[level]
    threads, memory = _fit(threads, memory, cpu, ram)
    share = max(threads / cpu, memory / max(1, ram))
    return Effort(level, threads, memory, round(min(1.0, share), 3), tone_for(share))


def describe(item, ram=None):
    """One line an analyst can read without a manual."""
    ram = ram or memory_mb()
    return "%d threads · %.1f GB of %.1f GB" % (item.threads, item.memory_mb / 1024, ram / 1024)


def from_settings(threads, memory, cpu=None, ram=None):
    """Describe an explicit choice (a hand-edited thread count) with the same colour."""
    cpu = cpu or cores()
    ram = ram or memory_mb()
    threads = int(threads or auto_threads(cpu))
    memory = int(memory or min(2048, max(512, ram // 3)))
    threads, memory = _fit(threads, memory, cpu, ram)
    share = max(threads / cpu, memory / max(1, ram))
    return Effort("custom", threads, memory, round(min(1.0, share), 3), tone_for(share))
