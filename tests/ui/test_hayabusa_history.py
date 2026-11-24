"""The panel's conversation list: what was said in this case is still there tomorrow."""

import time

import pytest

from fireblade.core.assistant_history import History
from fireblade.core.engine import Case
from fireblade.ui.app import Window

ALERTS = (
    "Timestamp,RuleTitle,Level,Computer,Channel,EventID,Details,RuleID,MitreTags\n"
    "2026-11-14T14:19:55Z,Defender real-time disabled,high,PC01,Defender,5001,"
    "DisableRealtimeMonitoring=1,r1,T1562.001\n"
)


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


@pytest.fixture
def window(qt_application, tmp_path):
    window = Window(require_case=False)
    errors = []
    window.error = errors.append
    yield window, errors, tmp_path
    settle(qt_application, window)
    assert window.close()
    assert not errors


def _case(tmp_path):
    source = tmp_path / "alerts.csv"
    source.write_text(ALERTS, encoding="utf-8")
    case = Case(tmp_path / "alerts.timeline")
    case.import_csv(source)
    return case


def test_a_conversation_saved_on_disk_can_be_reopened(qt_application, window):
    w, _errors, tmp_path = window
    case = _case(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel

    history = History(case.path)
    old = history.start("Question de la semaine derniere")
    history.append(
        old, "user", "Question de la semaine derniere", question="Question de la semaine derniere"
    )
    history.append(old, "assistant", "Un service suspect a ete installe sur PC01.")

    panel.refresh_conversations()

    labels = [panel.conversations.itemText(index) for index in range(panel.conversations.count())]
    assert labels[0] == "New conversation"
    assert any("Question de la semaine derniere" in label for label in labels)

    panel.open_conversation(1)
    text = panel.explanation.toPlainText()
    assert "You: Question de la semaine derniere" in text
    assert "Un service suspect a ete installe sur PC01." in text


def test_a_new_conversation_clears_the_transcript_and_the_memory(qt_application, window):
    w, _errors, tmp_path = window
    case = _case(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel

    history = History(case.path)
    old = history.start("Ancienne question")
    history.append(old, "user", "Ancienne question", question="Ancienne question")
    panel.refresh_conversations()
    panel.open_conversation(1)
    assert "Ancienne question" in panel.explanation.toPlainText()

    panel.start_conversation()

    assert panel.explanation.toPlainText().strip() == ""
    assert panel.chat is None or panel.chat.conversation is None


def test_the_list_starts_with_the_new_conversation_choice(qt_application, window):
    w, _errors, tmp_path = window
    case = _case(tmp_path)
    w.attach(case)
    settle(qt_application, w)
    panel = w.hayabusa_panel

    panel.refresh_conversations()

    assert panel.conversations.count() == 1
    assert panel.conversations.currentData() == ""
