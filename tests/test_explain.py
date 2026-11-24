"""The evidence pack is small, bounded, and every citation it accepts exists in it."""

from fireblade.core.explain import (
    build_pack,
    citations,
    describe_without_model,
    severity_first,
    verify,
    window_around,
)
from fireblade.core.findings import group_alerts


def rows(count=3, title="Encoded PowerShell", level="high"):
    # A real clock: minute = index, so 50 rows stay 50 valid timestamps inside one hour.
    return [
        dict(
            Timestamp="2026-11-14T14:%02d:00Z" % index,
            RuleTitle=title,
            Level=level,
            Computer="PC01",
            EventID="4104",
            Channel="PowerShell",
            Details="powershell.exe -e JAB%d" % index,
            RuleID="r1",
            EvtxFile="C:\\x\\PowerShell.evtx",
        )
        for index in range(count)
    ]


def pack_for(items=None, extra=()):
    items = list(rows() if items is None else items) + list(extra)
    groups, incidents = group_alerts(items)
    group = groups[0]
    return build_pack(group, [items[index] for index in group.samples], groups, incidents), group


def test_the_pack_numbers_its_events_and_the_prompt_uses_the_same_numbers():
    pack, _group = pack_for()
    assert [row.number for row in pack.facts] == [1, 2, 3]
    assert "[evt 1]" in pack.prompt and "[evt 1]" in pack.prompt
    assert "EVIDENCE" in pack.prompt and "FINDING" in pack.prompt


def test_the_prompt_stays_a_page():
    pack, _ = pack_for(rows(count=400))
    assert len(pack.prompt) <= 6000
    assert len(pack.facts) <= 40


def test_a_citation_that_exists_is_accepted_and_one_that_does_not_is_refused():
    pack, _ = pack_for()
    assert verify("The rule fired three times [evt 1].", pack)
    assert not verify("The rule fired three times [evt 99].", pack)
    assert not verify("The rule fired three times.", pack)


def test_citations_are_extracted_from_prose():
    assert citations("a [evt 3] b [evt 11] c") == [3, 11]
    assert citations(None) == []


def test_what_the_pack_could_not_establish_is_written_down():
    pack, _ = pack_for(rows(count=50))
    assert any("not read" in item for item in pack.missing)


def test_neighbours_come_from_the_same_window_and_host_first():
    extra = [
        dict(
            Timestamp="2026-11-14T14:22:00Z",
            RuleTitle="Service installed",
            Level="critical",
            Computer="PC01",
            EventID="7045",
            Channel="System",
            Details="svc",
            RuleID="r2",
            EvtxFile="C:\\x\\System.evtx",
        ),
        dict(
            Timestamp="2026-11-14T14:23:00Z",
            RuleTitle="Other host",
            Level="high",
            Computer="PC02",
            EventID="4624",
            Channel="Security",
            Details="logon",
            RuleID="r3",
            EvtxFile="C:\\x\\Security.evtx",
        ),
    ]
    pack, group = pack_for(extra=extra)
    assert pack.neighbours
    assert pack.neighbours[0]["title"] == "Service installed"
    assert pack.neighbours[0]["same_host"] is True
    assert "OTHER FINDINGS IN THE SAME WINDOW" in pack.prompt


def test_the_description_without_a_model_still_reads_like_a_sentence():
    pack, _ = pack_for()
    text = describe_without_model(pack)
    assert "Encoded PowerShell" in text
    assert "3 time(s)" in text


def test_the_window_is_centred_on_the_burst():
    _pack, group = pack_for()
    start, end = window_around(group, 5)
    assert (group.start - start).total_seconds() == 300
    assert (end - group.end).total_seconds() == 300


def test_the_most_severe_and_most_frequent_come_first():
    items = rows(count=2, title="low one", level="low")
    items += [
        dict(
            Timestamp="2026-11-14T15:00:00Z",
            RuleTitle="critical one",
            Level="critical",
            Computer="PC01",
            EventID="7045",
            Channel="System",
            Details="svc",
            RuleID="r4",
            EvtxFile="C:\\x\\System.evtx",
        )
    ]
    groups, _ = group_alerts(items)
    assert severity_first(groups, 1)[0].title == "critical one"


def test_the_prompt_forbids_invention_in_so_many_words():
    pack, _ = pack_for()
    assert "Never invent" in pack.prompt
    assert "[evt" in pack.prompt or "evt" in pack.prompt
