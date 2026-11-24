from datetime import datetime, timezone

from fireblade.core.findings import Group
from fireblade.ui.app import Window


def test_the_panel_offers_questions_and_a_click_only_fills_the_box(qt_application, tmp_path):
    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    try:
        window.create_investigation("Affaire S")
        window.hayabusa_panel.groups = [
            Group(
                key="k",
                title="Encoded PowerShell",
                level="critical",
                host="PC-COMPTA",
                channel="PowerShell",
                event_ids=("4104",),
                tactics="Execution",
                techniques="T1059.001",
                rule_id="r",
                rule_file="f",
                start=datetime(2026, 11, 17, 10, tzinfo=timezone.utc),
                end=datetime(2026, 11, 17, 10, 2, tzinfo=timezone.utc),
                count=3,
            )
        ]
        panel = window.hayabusa_panel
        panel.refresh_suggestions()
        qt_application.processEvents()
        assert panel.chip_buttons, "no suggestion offered"
        assert len(panel.chip_buttons) <= 3
        first = panel.chip_buttons[0]
        assert "Encoded PowerShell" in first.text()
        first.click()
        qt_application.processEvents()
        assert panel.ask.text() == first.text()
    finally:
        window.close()


def test_an_empty_case_still_proposes_a_starting_point(qt_application, tmp_path):
    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    try:
        window.hayabusa_panel.groups = []
        window.hayabusa_panel.refresh_suggestions()
        qt_application.processEvents()
        assert len(window.hayabusa_panel.chip_buttons) == 3
    finally:
        window.close()
