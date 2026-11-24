from datetime import UTC, datetime

from fireblade.core.findings import Group
from fireblade.core.i18n import lookup
from fireblade.core.suggestions import suggest


def group(title, host, level="high", tactics="Execution"):
    return Group(
        key=title + host,
        title=title,
        level=level,
        host=host,
        channel="Security",
        event_ids=("1",),
        tactics=tactics,
        techniques="T1059.001",
        rule_id="r",
        rule_file="f",
        start=datetime(2026, 11, 17, 10, tzinfo=UTC),
        end=datetime(2026, 11, 17, 10, 5, tzinfo=UTC),
        count=2,
    )


def test_an_empty_case_offers_the_three_questions_that_make_sense():
    questions = suggest([])
    assert questions == [
        "Que contient ce case et par quoi commencer ?",
        "Quels artefacts ont été importés et combien de lignes ?",
        "Où l'activité est-elle la plus dense ?",
    ]
    assert suggest([], limit=2) == questions[:2]


def test_the_worst_finding_comes_first_and_names_its_host():
    questions = suggest(
        [
            group("Encoded PowerShell", "PC-COMPTA", "critical"),
            group("RDP Logon", "SRV-DC01", "informational"),
        ]
    )
    assert "Encoded PowerShell" in questions[0] and "PC-COMPTA" in questions[0]
    assert "explication bénigne" in questions[1]


def test_the_busiest_host_and_lateral_movement_are_proposed():
    questions = suggest([group("A", "SRV-DC01"), group("B", "SRV-DC01"), group("C", "PC-COMPTA")])
    assert any("heure par heure" in question and "SRV-DC01" in question for question in questions)
    assert any("mouvement latéral" in question for question in questions)


def test_tracked_indicators_and_open_actions_are_used():
    workspace = dict(
        iocs=[dict(value="evil.example")], actions=[dict(status="in_progress", machine="SRV-DC01")]
    )
    questions = suggest([group("A", "SRV-DC01")], workspace, limit=6)
    assert any("evil.example" in question for question in questions)
    assert any("SRV-DC01" in question and "clore" in question for question in questions)


def test_the_limit_is_respected_and_questions_are_distinct():
    many = [group("Rule %d" % index, "HOST%d" % (index % 4)) for index in range(20)]
    questions = suggest(many, limit=3)
    assert len(questions) == 3 and len(set(questions)) == 3


def test_the_english_interface_translates_a_question_with_its_two_values():
    english = lookup("Qu'est-ce qui s'est passé autour de « Encoded PowerShell » sur PC-COMPTA ?")
    assert english.startswith("What happened around") and "PC-COMPTA" in english
