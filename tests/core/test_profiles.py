"""Profile detection: a catalogue entry must recognise its own exports."""

import pytest

from fireblade.core.profile_catalog import CATALOG
from fireblade.core.profiles import Profile, detect_profile, profile_view


def catalogue_headers(entry):
    """Headers a real export of this artefact would carry."""
    values = list(entry['signature']) + list(entry.get('columns', []))
    tokens = [part for value in values for part in str(value).split('\t') if part]
    return list(dict.fromkeys(tokens))


def test_every_catalogue_entry_recognises_its_own_headers():
    missed = []
    for entry in CATALOG:
        found = detect_profile(catalogue_headers(entry))
        if found is None or found.name != entry['name']:
            missed.append((entry['name'], found.name if found else None))
    assert missed == []


def test_the_most_specific_profile_wins():
    verbose = next(entry for entry in CATALOG if entry['name'] == 'HayabusaVerbose')
    standard = next(entry for entry in CATALOG if entry['name'] == 'HayabusaStandard')
    # Both match a verbose export; the detailed profile must be selected.
    found = detect_profile(catalogue_headers(verbose))
    assert found.name == 'HayabusaVerbose'
    assert len(found.signature) > len(standard['signature'])


def test_tab_joined_declarations_are_split_into_headers():
    from fireblade.core.profiles import all_profiles
    mft = next(profile for profile in all_profiles() if profile.name == 'MsftMft')
    assert len(mft.signature) > 1
    assert all('\t' not in name for name in mft.signature)
    assert detect_profile(list(mft.signature)).name == 'MsftMft'


def test_category_colours_only_fill_an_empty_rule_set():
    hayabusa = Profile('Hayabusa', ('Level',), ('Timestamp',), ('Level', 'Fireblade_Category'))
    view, _order = profile_view(hayabusa, ['Level', 'Fireblade_Category'])
    # Severity colours survive: the category palette must not overwrite them.
    assert [rule.background for rule in view.format_rules] == ['#ffc7ce', '#ffdfad', '#fff4c2']
    other = Profile('SomeArtifact', ('Level',), ('Timestamp',), ('Level', 'Fireblade_Category'))
    view, _order = profile_view(other, ['Level', 'Fireblade_Category'])
    assert view.format_rules and all(rule.background for rule in view.format_rules)
    assert len(view.format_rules) <= 32


def test_unknown_headers_select_no_profile():
    assert detect_profile(['Whatever', 'Something']) is None
    assert detect_profile([]) is None
