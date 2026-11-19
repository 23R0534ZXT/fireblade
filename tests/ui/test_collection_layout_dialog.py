"""Three import layouts, named by what the analyst gets: per file, per family, or one grid.

The report that led here: "by artifact" was chosen and a hundred and twenty-eight EVTX
grids opened instead of one. The dialog is where the analyst picks; these tests pin what
each choice returns and that every choice says what it does.
"""
from fireblade.ui.collection import CollectionOrganizationDialog


def test_the_recommended_layout_is_one_grid_per_artifact_family(qt_application):
    dialog = CollectionOrganizationDialog()
    assert dialog.artifacts.isChecked()
    assert dialog.organization() == 'artifacts'
    assert not dialog.progressive.isChecked()


def test_every_layout_is_reachable_and_says_what_it_gives(qt_application):
    dialog = CollectionOrganizationDialog()
    for radio in (dialog.progressive, dialog.artifacts, dialog.combined):
        assert radio.isEnabled(), radio.text()
        assert radio.isCheckable()
    texts = [dialog.progressive.text(), dialog.artifacts.text(), dialog.combined.text(),
             dialog.progressive_hint.text(), dialog.artifacts_hint.text(), dialog.combined_hint.text()]
    joined = ' '.join(texts).casefold()
    assert 'evtx' in joined and 'mft' in joined and 'amcache' in joined
    assert 'grouping is fixed' in joined


def test_the_three_choices_are_exclusive(qt_application):
    dialog = CollectionOrganizationDialog()
    dialog.progressive.setChecked(True)
    assert dialog.organization() == 'files'
    assert not dialog.artifacts.isChecked() and not dialog.combined.isChecked()

    dialog.combined.setChecked(True)
    assert dialog.organization() == 'combined'
    assert not dialog.progressive.isChecked() and not dialog.artifacts.isChecked()

    dialog.artifacts.setChecked(True)
    assert dialog.organization() == 'artifacts'
    assert not dialog.progressive.isChecked() and not dialog.combined.isChecked()
