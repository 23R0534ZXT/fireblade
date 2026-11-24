"""The Hayabusa + AI tab: reads a real analysis, groups it, and draws it."""

import time

import pytest

from fireblade.core.engine import Case
from fireblade.ui.app import Window
from fireblade.ui.hayabusa import HayabusaPanel
from fireblade.ui.maps import ChainMap, CircularMap, HeatMap


def settle(app, window):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        app.processEvents()
        if (
            not window.jobs
            and not window.pool.activeThreadCount()
            and (window.model is None or not window.model.jobs)
        ):
            return
        time.sleep(0.005)
    pytest.fail("The desktop did not finish its background operations")


ALERTS = (
    "Timestamp,RuleTitle,Level,Computer,Channel,EventID,Details,RuleID,MitreTags\n"
    "2026-11-14T14:19:55Z,Defender real-time disabled,high,PC01,Defender,5001,DisableRealtimeMonitoring=1,r1,T1562.001\n"
    "2026-11-14T14:20:03Z,Encoded PowerShell,high,PC01,PowerShell,4104,powershell.exe -e JAB,r2,T1059.001\n"
    "2026-11-14T14:20:19Z,Encoded PowerShell,high,PC01,PowerShell,4104,IEX (New-Object),r2,T1059.001\n"
    "2026-11-14T14:21:02Z,Encoded PowerShell,high,PC01,PowerShell,4104,FromBase64String,r2,T1059.001\n"
    "2026-11-14T14:27:02Z,Service installed,critical,PC01,System,7045,svc_8f3ak,r3,T1543.003\n"
    "2026-11-14T15:40:00Z,Logon failure,medium,PC01,Security,4625,unknown user,r4,T1110\n"
)


@pytest.fixture
def window(qt_application, tmp_path):
    window = Window(require_case=False)
    errors = []
    window.error = errors.append
    yield window, errors, tmp_path
    settle(qt_application, window)
    assert window.close()
    assert not errors


def analysis(tmp_path, text=ALERTS, name="alerts"):
    source = tmp_path / (name + ".csv")
    source.write_text(text, encoding="utf-8")
    case = Case(tmp_path / (name + ".timeline"))
    case.import_csv(source)
    return case


def test_the_tab_exists_beside_the_other_panels(qt_application, window):
    _w, _errors, _tmp = window
    labels = [qt_application and _w.workbench.tabText(i) for i in range(_w.workbench.count())]
    assert "Hayabusa + AI" in labels


def test_without_a_hayabusa_analysis_the_tab_explains_what_to_do(qt_application, window):
    w, _errors, tmp_path = window
    plain = Case(tmp_path / "plain.timeline")
    (tmp_path / "plain.csv").write_text("A,B\n1,2\n", encoding="utf-8")
    plain.import_csv(tmp_path / "plain.csv")
    w.attach(plain)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()
    assert panel.groups == []
    assert "No Hayabusa analysis is loaded" in panel.state.text()
    assert "Run Hayabusa" in panel.state.text()


def test_a_real_analysis_is_grouped_and_drawn(qt_application, window):
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()
    assert panel.groups, "the panel read no group from a real analysis"
    assert panel.table.rowCount() == len(panel.groups)
    titles = [panel.table.item(row, 2).text() for row in range(panel.table.rowCount())]
    assert "Encoded PowerShell" in titles
    # three identical alerts three minutes apart are one finding, not three rows
    assert titles.count("Encoded PowerShell") == 1
    assert panel.summary["hits"] == 6
    map_widget = panel.maps[panel._active]
    assert map_widget.groups
    assert map_widget.width() >= 0


def test_selecting_a_finding_fills_the_card_and_the_explanation(qt_application, window):
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()
    index = next(i for i, group in enumerate(panel.groups) if group.title == "Encoded PowerShell")
    panel.select_group(index)
    assert "Encoded PowerShell" in panel.card.text()
    assert "3 time(s)" in panel.explanation.toPlainText()
    assert panel.table.selectionModel().selectedRows(), "the grid did not follow the selection"


def test_every_view_renders_without_raising(qt_application, window):
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()
    for index, (_label, factory) in enumerate(((0, CircularMap), (1, HeatMap), (2, ChainMap))):
        panel.view_box.setCurrentIndex(index)
        qt_application.processEvents()
        assert isinstance(panel.maps[factory], factory)
        assert panel.maps[factory].isVisible() or not panel.isVisible()
    panel.view_box.setCurrentIndex(0)


def test_the_level_filter_and_the_text_filter_narrow_the_list(qt_application, window):
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()
    everything = panel.table.rowCount()
    panel.level_box.setCurrentIndex(1)  # critical only
    qt_application.processEvents()
    assert panel.table.rowCount() == 1
    panel.level_box.setCurrentIndex(0)
    qt_application.processEvents()
    assert panel.table.rowCount() == everything
    panel.filter_box.setText("logon")
    qt_application.processEvents()
    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 2).text() == "Logon failure"
    panel.filter_box.clear()


def test_asking_a_question_without_a_model_says_why(qt_application, window):
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()
    panel.select_group(0)
    panel.ask.setText("what does this mean?")
    panel.ask_question()
    text = panel.explanation.toPlainText()
    assert "what does this mean?" in text
    assert "cannot answer" in text


def test_a_draft_with_an_invented_citation_is_refused(qt_application, window, monkeypatch):
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()
    panel.select_group(
        next(i for i, group in enumerate(panel.groups) if group.title == "Encoded PowerShell")
    )

    class Ready:
        detail = ""
        can_answer = True
        enabled = True

    panel.assistant = type(
        "Stub", (), {"status": staticmethod(lambda: Ready()), "root": tmp_path}
    )()

    import json as _json

    import fireblade.ui.hayabusa as module

    def answer_with(payload):
        return lambda *args, **kwargs: dict(
            ok=True, text=_json.dumps(payload), seconds=1.0, completion_tokens=10
        )

    # a claim pointing at an event that does not exist must never be shown
    monkeypatch.setattr(
        module,
        "answer",
        answer_with(
            dict(
                summary="something happened",
                facts=[dict(text="invented", events=[999])],
                links=[dict(**{"from": 1, "to": 999}, why="invented")],
                missing=[],
            )
        ),
    )
    # The button keeps the verified path: a claim about an event that does not exist
    # is discarded before it reaches the analyst.
    panel.explain_group()
    settle(qt_application, w)
    text = panel.explanation.toPlainText()
    assert "discarded" in text or "Dropped" in text
    assert "evt 999" not in text

    # a claim inside the pack is shown with its reference
    monkeypatch.setattr(
        module,
        "answer",
        answer_with(
            dict(
                summary="three alerts in order",
                facts=[dict(text="encoded powershell ran", events=[1, 2])],
                links=[dict(**{"from": 1, "to": 2}, why="the same process")],
                missing=[],
            )
        ),
    )
    panel.explain_group()
    settle(qt_application, w)
    text = panel.explanation.toPlainText()
    assert "three alerts in order" in text
    assert "[evt 1]" in text
    assert panel._pack.links and panel._pack.links[0]["target"] == 2


def test_the_panel_is_a_qt_widget_that_can_be_closed_cleanly(qt_application, window):
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    assert isinstance(panel, HayabusaPanel)
    panel.close()


def test_the_question_box_talks_to_the_chat(qt_application, window):
    """The box is a conversation now: no selection, and the answer is prose."""
    w, _errors, tmp_path = window
    case = analysis(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel
    panel.reload()

    class Ready:
        detail = ""
        can_answer = True
        enabled = True

    panel.assistant = type(
        "Stub", (), {"status": staticmethod(lambda: Ready()), "root": tmp_path}
    )()
    asked = []

    class Turn:
        text = "Deux hotes : PC01 et PC02."
        steps = []
        seconds = 1.2

    class FakeChat:
        root = str(tmp_path)

        def ask(self, question):
            asked.append(question)
            return Turn()

    panel.chat = FakeChat()
    panel.ask.setText("Combien d hotes ?")
    panel.ask_question()
    settle(qt_application, w)
    text = panel.explanation.toPlainText()
    assert asked == ["Combien d hotes ?"]
    assert "You: Combien d hotes ?" in text
    assert "Deux hotes : PC01 et PC02." in text
