"""Group Hayabusa findings without losing one of them.

A collection of a real workstation produces tens of thousands of alerts at the
highest verbosity, and reading them one by one is not an investigation. This module
answers one question, with no model involved: *which alerts are the same thing
happening again*, and *which of those bundles sit inside the same incident window*.

Two levels, and the second is the one the interface shows:

- a **group** is one rule, on one host, over one channel, whose events are never more
  than ``GAP_SECONDS`` apart — a burst keeps its own start and end;
- an **incident** is a set of groups whose own span overlaps a rolling window, so a
  chain of alerts an analyst would read as one story stays together.

Everything here is a pure function of the alert rows: no clock, no randomness, no
network. The identifiers it hands out are stable for a given input, which is what
lets a finding point at the rows it was built from.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# A burst ends when the same rule stays silent for this long on the same host.
GAP_SECONDS = 900
# Two groups belong to the same incident when their spans are this close together.
INCIDENT_WINDOW_SECONDS = 3600
# How many rows a group hands to the interface for its detail view.
MAX_SAMPLES = 200

LEVELS = ('critical', 'high', 'medium', 'low', 'informational')
# The canonical names are aliases of themselves on purpose: level_of() is applied to
# values that are already normalised, and a table missing 'critical' silently demoted
# every critical finding to informational.
_LEVEL_ALIASES = {'critical': 'critical', 'crit': 'critical',
                  'high': 'high', 'medium': 'medium', 'med': 'medium',
                  'low': 'low', 'informational': 'informational', 'info': 'informational',
                  'information': 'informational'}
_LEVEL_RANK = {name: rank for rank, name in enumerate(reversed(LEVELS))}

SEVERITY_SCORE = {'critical': 100, 'high': 40, 'medium': 10, 'low': 3, 'informational': 1}


def level_of(value):
    """Hayabusa writes ``high`` or ``med``; an unknown word is informational, never dropped."""
    return _LEVEL_ALIASES.get(str(value or '').strip().casefold(), 'informational')


def rank(level):
    return _LEVEL_RANK.get(level, 0)


def instant(value):
    """The timestamp of an alert, as an aware UTC datetime, or None when unusable."""
    text = str(value or '').strip()
    if not text:
        return None
    text = text.replace('Z', '+00:00')
    # Hayabusa writes '+00:00' but also ' +00:00' with a leading space in some profiles.
    text = text.replace(' +', '+')
    for parser in (datetime.fromisoformat, _from_common_formats):
        try:
            stamp = parser(text)
        except (ValueError, TypeError, OverflowError):
            continue
        if stamp.tzinfo is None:
            return stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    return None


def _from_common_formats(text):
    for pattern in ('%Y-%m-%d %H:%M:%S%.f %z', '%Y-%m-%d %H:%M:%S %z', '%Y/%m/%d %H:%M:%S%.f %z'):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ValueError(text)


def _first(row, *names):
    for name in names:
        value = row.get(name)
        if value not in (None, '', '-'):
            return str(value).strip()
    return ''


@dataclass
class Group:
    """One rule on one host, one burst."""
    key: str
    title: str
    level: str
    host: str
    channel: str
    event_ids: tuple
    tactics: str
    techniques: str
    rule_id: str
    rule_file: str
    start: datetime | None
    end: datetime | None
    count: int
    samples: list = field(default_factory=list)      # row ids, at most MAX_SAMPLES
    details: str = ''
    incident: str = ''

    @property
    def severity(self):
        return SEVERITY_SCORE.get(self.level, 1)

    @property
    def seconds(self):
        if self.start is None or self.end is None:
            return 0
        return max(0, int((self.end - self.start).total_seconds()))

    def span(self):
        """(start, end) with a usable fallback for an alert whose timestamp could not be read."""
        floor = datetime.max.replace(tzinfo=timezone.utc)
        return (self.start or floor, self.end or floor)

    def as_dict(self):
        return dict(key=self.key, title=self.title, level=self.level, host=self.host,
                    channel=self.channel, event_ids=list(self.event_ids), tactics=self.tactics,
                    techniques=self.techniques, rule_id=self.rule_id, rule_file=self.rule_file,
                    start=self.start.isoformat() if self.start else None,
                    end=self.end.isoformat() if self.end else None,
                    count=self.count, seconds=self.seconds, details=self.details,
                    incident=self.incident, samples=list(self.samples))


@dataclass
class Incident:
    """Groups an analyst would read as one story, ordered by the hour they started."""
    key: str
    start: datetime | None
    end: datetime | None
    groups: list = field(default_factory=list)

    @property
    def level(self):
        best = 'informational'
        for group in self.groups:
            if rank(group.level) > rank(best):
                best = group.level
        return best

    @property
    def hits(self):
        return sum(group.count for group in self.groups)

    def as_dict(self):
        return dict(key=self.key, level=self.level, hits=self.hits, groups=len(self.groups),
                    start=self.start.isoformat() if self.start else None,
                    end=self.end.isoformat() if self.end else None)


def group_alerts(rows, gap_seconds=GAP_SECONDS, incident_window=INCIDENT_WINDOW_SECONDS):
    """Turn alert rows into (groups, incidents).

    ``rows`` is any iterable of mappings with Hayabusa's own column names; the row's
    position in that iterable is its identifier, which is what a sample refers to.
    Nothing is dropped: a row without a timestamp still joins a group.
    """
    buckets = {}
    for index, row in enumerate(rows):
        stamp = instant(_first(row, 'Timestamp', 'TimeCreated', 'DateTime'))
        title = _first(row, 'RuleTitle', 'Title', 'Rule')
        host = _first(row, 'Computer', 'Host', 'Hostname')
        channel = _first(row, 'Channel')
        level = level_of(_first(row, 'Level'))
        key = (title.casefold(), host.casefold(), channel.casefold(), level)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = buckets[key] = dict(title=title, host=host, channel=channel, level=level,
                                         rows=[], stamps=[])
        bucket['rows'].append(index)
        if stamp is not None:
            bucket['stamps'].append(stamp)

    groups = []
    for (title, host, channel, level), bucket in buckets.items():
        stamps = sorted(bucket['stamps'])
        for start, end, members in _bursts(stamps, gap_seconds):
            event_ids = []
            tactics, techniques, rule_id, rule_file, details = '', '', '', '', ''
            for index in bucket['rows']:
                row = rows[index]
                for value in str(_first(row, 'EventID')).split('¦'):
                    value = value.strip()
                    if value and value not in event_ids:
                        event_ids.append(value)
                tactics = tactics or _first(row, 'MitreTactics', 'MitreTacticsShort')
                techniques = techniques or _first(row, 'MitreTags', 'MitreTechniques')
                rule_id = rule_id or _first(row, 'RuleID', 'RuleId')
                rule_file = rule_file or _first(row, 'RuleFile')
                details = details or _first(row, 'Details', 'DetailsShort')
            key = '|'.join((bucket['title'] or '(untitled)', bucket['host'], level,
                            start.isoformat() if start else 'no-date'))
            groups.append(Group(
                key=key, title=bucket['title'] or '(untitled rule)', level=level,
                host=bucket['host'], channel=bucket['channel'], event_ids=tuple(event_ids),
                tactics=tactics, techniques=techniques, rule_id=rule_id, rule_file=rule_file,
                start=start, end=end, count=len(members) if members else len(bucket['rows']),
                samples=list(bucket['rows'][:MAX_SAMPLES]), details=details))
    groups.sort(key=lambda item: (item.span(), -item.severity, item.title.casefold()))
    incidents = _incidents(groups, incident_window)
    return groups, incidents


def _bursts(stamps, gap_seconds):
    """Sorted timestamps into [start, end, members] runs separated by more than the gap."""
    if not stamps:
        return [(None, None, [])]
    runs, current = [], [stamps[0]]
    for stamp in stamps[1:]:
        if (stamp - current[-1]).total_seconds() > gap_seconds:
            runs.append((current[0], current[-1], current))
            current = [stamp]
        else:
            current.append(stamp)
    runs.append((current[0], current[-1], current))
    return runs


def _incidents(groups, window):
    """Groups whose spans fall inside one rolling window become an incident."""
    dated = [group for group in groups if group.start is not None]
    undated = [group for group in groups if group.start is None]
    dated.sort(key=lambda item: item.span())
    incidents = []
    span = timedelta(seconds=window)
    for group in dated:
        if incidents and group.start <= incidents[-1].end + span:
            incident = incidents[-1]
        else:
            incident = Incident(key='incident-%d' % (len(incidents) + 1), start=group.start, end=group.end)
            incidents.append(incident)
        incident.groups.append(group)
        if group.end is not None and (incident.end is None or group.end > incident.end):
            incident.end = group.end
    if undated:
        incidents.append(Incident(key='incident-undated', start=None, end=None, groups=undated))
    for incident in incidents:
        for group in incident.groups:
            group.incident = incident.key
    return incidents


def summarise(groups):
    """Counts per level, for the header line an analyst reads first."""
    counts = {level: 0 for level in LEVELS}
    hits = 0
    for group in groups:
        counts[group.level] = counts.get(group.level, 0) + 1
        hits += group.count
    return dict(groups=len(groups), hits=hits, levels=counts)


def _columns(case):
    """The Hayabusa columns this analysis actually has, quoted for SQL."""
    wanted = ('Timestamp', 'RuleTitle', 'Level', 'Computer', 'Channel', 'EventID', 'MitreTactics',
              'MitreTags', 'RuleID', 'RuleFile', 'Details', 'DetailsShort')
    found = {}
    for name in wanted:
        try:
            index = case.headers.index(name)
        except ValueError:
            continue
        found[name] = case.column(index)
    return found


def group_alerts_sql(case, gap_seconds=GAP_SECONDS, incident_window=INCIDENT_WINDOW_SECONDS):
    """The same grouping as ``group_alerts``, done by DuckDB.

    Millions of alerts cannot be grouped in a Python loop without holding them all in
    memory; a window function over the events table can. The dated alerts are cut into
    bursts per rule and host by the gap between two consecutive timestamps, the undated
    ones are counted as one burst of their own, and the incident windows are then built
    on the few hundred groups this returns.

    The caller holds the case's operation lock; this function does not open one.
    """
    columns = _columns(case)
    if 'RuleTitle' not in columns:
        raise ValueError('Cette analyse ne contient pas de colonne RuleTitle')
    title = columns['RuleTitle']
    host = columns.get('Computer', "'unknown'")
    channel = columns.get('Channel', "''")
    level = columns.get('Level', "'informational'")
    event_id = columns.get('EventID', "''")
    tactics = columns.get('MitreTactics', "''")
    techniques = columns.get('MitreTags', "''")
    rule_id = columns.get('RuleID', "''")
    rule_file = columns.get('RuleFile', "''")
    details = columns.get('Details', columns.get('DetailsShort', "''"))
    stamp = columns.get('Timestamp')
    gap = int(gap_seconds)

    if stamp is None:
        return group_alerts((), gap_seconds, incident_window)

    dated = f"""
        WITH parsed AS (
            SELECT __row_id AS rid, {title} AS title, {host} AS host, {channel} AS channel,
                   {level} AS lvl, {event_id} AS eid, {tactics} AS tac, {techniques} AS tech,
                   {rule_id} AS rule, {rule_file} AS rfile, {details} AS det,
                   TRY_CAST({stamp} AS TIMESTAMPTZ) AS ts
            FROM events
        ), marked AS (
            SELECT *,
                   CASE WHEN lag(ts) OVER w IS NULL THEN 1
                        WHEN date_diff('second', lag(ts) OVER w, ts) > {gap} THEN 1
                        ELSE 0 END AS starts
            FROM parsed WHERE ts IS NOT NULL
            WINDOW w AS (PARTITION BY title, host, channel, lvl ORDER BY ts)
        ), numbered AS (
            SELECT *, sum(starts) OVER (PARTITION BY title, host, channel, lvl ORDER BY ts
                                        ROWS UNBOUNDED PRECEDING) AS burst
            FROM marked
        )
        SELECT title, host, channel, lvl, min(ts) AS start, max(ts) AS end, count(*) AS n,
               min(eid) AS eid, min(tac) AS tac, min(tech) AS tech, min(rule) AS rule,
               min(rfile) AS rfile, min(det) AS det,
               list(rid ORDER BY ts) AS rows
        FROM numbered GROUP BY title, host, channel, lvl, burst
    """
    undated = f"""
        SELECT {title} AS title, {host} AS host, {channel} AS channel, {level} AS lvl,
               CAST(NULL AS TIMESTAMPTZ) AS start, CAST(NULL AS TIMESTAMPTZ) AS end, count(*) AS n,
               min({event_id}) AS eid, min({tactics}) AS tac, min({techniques}) AS tech,
               min({rule_id}) AS rule, min({rule_file}) AS rfile, min({details}) AS det,
               list(__row_id) AS rows
        FROM events WHERE TRY_CAST({stamp} AS TIMESTAMPTZ) IS NULL
        GROUP BY 1, 2, 3, 4
    """
    fields = ('title', 'host', 'channel', 'lvl', 'start', 'end', 'n', 'eid', 'tac', 'tech',
              'rule', 'rfile', 'det', 'rows')
    cursor = case.db.execute(dated + ' UNION ALL ' + undated)
    groups = []
    for record in cursor.fetchall():
        row = dict(zip(fields, record))
        level_name = level_of(row['lvl'])
        start = row['start'].astimezone(timezone.utc) if row['start'] is not None else None
        end = row['end'].astimezone(timezone.utc) if row['end'] is not None else None
        event_ids = tuple(value.strip() for value in str(row['eid'] or '').split('¦')
                          if value.strip() and value.strip() != '-')
        keys = list(row['rows'] or [])
        groups.append(Group(
            key='|'.join((row['title'] or '(untitled)', row['host'] or '', level_name,
                          start.isoformat() if start else 'no-date')),
            title=row['title'] or '(untitled rule)', level=level_name, host=row['host'] or '',
            channel=row['channel'] or '', event_ids=event_ids,
            tactics=row['tac'] or '', techniques=row['tech'] or '', rule_id=row['rule'] or '',
            rule_file=row['rfile'] or '', start=start, end=end, count=int(row['n']),
            samples=[int(value) for value in keys[:MAX_SAMPLES]], details=row['det'] or ''))
    groups.sort(key=lambda item: (item.span(), -item.severity, item.title.casefold()))
    incidents = _incidents(groups, incident_window)
    return groups, incidents
