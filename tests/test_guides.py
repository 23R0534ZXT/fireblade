"""The built-in guides exist in English, and the interface opens them in English."""
import os

import pytest

from fireblade.core.i18n import set_language
from fireblade.runtime.resources import resource_path
from fireblade.ui.help_dialogs import guide_path

GUIDES = ("TUTORIEL-COMPLET", "UTILISATION", "CHRONOLOGIE-ET-SAUVEGARDES",
          "CHASSE-IOC", "COUVERTURE-COLLECTE")


@pytest.mark.parametrize("name", GUIDES)
def test_every_guide_reachable_from_help_has_an_english_version(name):
    french = resource_path(f"docs/guides/{name}.md")
    english = resource_path(f"docs/guides/{name}-en.md")
    assert french.is_file(), f"the French guide {name}.md is missing"
    assert english.is_file(), f"the guide {name} has no English version"
    assert english.stat().st_size > 200


@pytest.mark.parametrize("name", GUIDES)
def test_the_english_interface_opens_the_english_guide(name):
    try:
        set_language("en")
        assert guide_path(name).name == f"{name}-en.md"
        set_language("fr")
        assert guide_path(name).name == f"{name}.md"
    finally:
        set_language("fr")


def test_an_english_guide_keeps_the_french_structure():
    """Same heading count: a translation must not drop a section."""
    for name in GUIDES:
        french = resource_path(f"docs/guides/{name}.md").read_text(encoding="utf-8")
        english = resource_path(f"docs/guides/{name}-en.md").read_text(encoding="utf-8")
        count = lambda text: sum(1 for line in text.splitlines() if line.startswith("#"))
        assert count(english) == count(french), f"{name}: headings differ"
        assert not os.path.splitext(english)[0].endswith("-en-en")
