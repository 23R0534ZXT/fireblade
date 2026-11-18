"""Choosing a grouped layout is reachable, and it is what makes the parse wait."""
from fireblade.ui.collection import CollectionOrganizationDialog


def test_both_layouts_are_reachable_while_the_parse_streams(qt_application):
    dialog = CollectionOrganizationDialog()
    assert dialog.progressive.isChecked()
    assert dialog.artifacts.isEnabled(), 'the per-artifact layout was greyed out'
    assert dialog.combined.isEnabled()
    dialog.deleteLater()


def test_choosing_a_grouped_layout_stops_publishing_file_by_file(qt_application):
    dialog = CollectionOrganizationDialog()
    assert dialog.organization() == 'files'

    dialog.combined.setChecked(True)

    assert not dialog.progressive.isChecked(), 'a merged layout still streamed'
    assert dialog.organization() == 'combined'
    dialog.deleteLater()


def test_the_artifact_layout_is_what_it_returns(qt_application):
    dialog = CollectionOrganizationDialog()
    dialog.artifacts.setChecked(True)

    dialog.progressive.setChecked(False)

    assert dialog.organization() == 'artifacts'
    dialog.deleteLater()
