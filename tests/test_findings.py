"""Grouping and incident assembly: nothing dropped, and stable identifiers."""

from datetime import datetime, timezone

from fireblade.core.findings import group_alerts, instant, level_of, summarise


def alert(stamp, title="Rule A", host="PC01", level="high", event_id="4624", **extra):
    row = dict(
        Timestamp=stamp,
        RuleTitle=title,
        Level=level,
        Computer=host,
        EventID=event_id,
        Channel="Security",
        RuleID="rule-" + title,
        EvtxFile="C:\\x\\Security.evtx",
        Details="detail for " + title,
    )
    row.update(extra)
    return row


def test_timestamps_are_read_in_every_shape_hayabusa_writes():
    assert instant("2026-11-14T14:20:03.412Z").tzinfo is not None
    assert instant("2026-11-14 14:20:03.412 +01:00").astimezone(timezone.utc).hour == 13
    assert instant("2026-11-14 14:20:03 +0000").minute == 20
    assert instant("") is None
    assert instant("not a date") is None


def test_levels_are_normalised_and_never_dropped():
    assert level_of("med") == "medium"
    assert level_of("CRITICAL") == "critical"
    assert level_of("") == "informational"
    assert level_of("something new") == "informational"


def test_one_rule_bursting_twice_is_two_groups_not_one_line():
    rows = [
        alert("2026-11-14T10:00:00Z"),
        alert("2026-11-14T10:05:00Z"),
        alert("2026-11-14T14:00:00Z"),
        alert("2026-11-14T14:01:00Z"),
    ]
    groups, _incidents = group_alerts(rows)
    assert [group.count for group in groups] == [2, 2]
    assert groups[0].start.hour == 10 and groups[1].start.hour == 14


def test_a_row_without_a_timestamp_is_kept_in_an_undated_incident():
    rows = [alert("2026-11-14T10:00:00Z"), alert("bad date", title="Rule B")]
    groups, incidents = group_alerts(rows)
    assert len(groups) == 2
    assert any(group.start is None for group in groups)
    assert any(incident.key == "incident-undated" for incident in incidents)


def test_groups_carry_their_rows_and_their_severity():
    rows = [alert("2026-11-14T10:00:00Z", level="critical") for _ in range(3)]
    groups, _ = group_alerts(rows)
    assert len(groups) == 1
    assert groups[0].samples == [0, 1, 2]
    assert groups[0].severity == 100
    assert groups[0].event_ids == ("4624",)


def test_groups_in_the_same_window_share_an_incident():
    rows = [
        alert("2026-11-14T10:00:00Z", title="A"),
        alert("2026-11-14T10:20:00Z", title="B"),
        alert("2026-11-14T14:00:00Z", title="C"),
    ]
    groups, incidents = group_alerts(rows)
    first = next(incident for incident in incidents if incident.key == "incident-1")
    assert {group.title for group in first.groups} == {"A", "B"}
    assert {group.title for group in incidents[1].groups} == {"C"}


def test_summary_counts_groups_and_hits_separately():
    rows = [
        alert("2026-11-14T10:00:00Z"),
        alert("2026-11-14T10:01:00Z"),
        alert("2026-11-14T12:00:00Z", title="B", level="low"),
    ]
    summary = summarise(group_alerts(rows)[0])
    assert summary["groups"] == 2
    assert summary["hits"] == 3
    assert summary["levels"]["high"] == 1
    assert summary["levels"]["low"] == 1


def test_the_same_input_gives_the_same_keys():
    rows = [alert("2026-11-14T10:00:00Z"), alert("2026-11-14T11:00:00Z")]
    first = [group.key for group in group_alerts(rows)[0]]
    second = [group.key for group in group_alerts(rows)[0]]
    assert first == second


def test_an_empty_input_is_not_an_error():
    groups, incidents = group_alerts([])
    assert groups == [] and incidents == []
    assert summarise([])["groups"] == 0


def test_a_value_with_the_hayabusa_separator_keeps_every_event_id():
    rows = [alert("2026-11-14T10:00:00Z", event_id="4624 ¦ 4634")]
    groups, _ = group_alerts(rows)
    assert groups[0].event_ids == ("4624", "4634")


def test_ordering_is_by_time_then_severity():
    rows = [
        alert("2026-11-14T12:00:00Z", title="later", level="low"),
        alert("2026-11-14T09:00:00Z", title="early", level="high"),
    ]
    groups, _ = group_alerts(rows)
    assert [group.title for group in groups] == ["early", "later"]
    assert isinstance(groups[0].start, datetime)
