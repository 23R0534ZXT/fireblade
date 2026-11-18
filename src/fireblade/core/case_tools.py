"""The case, seen through the few questions a chat needs to ask.

The assistant never gets SQL of its own: it names one of four lookups and this module
turns that into a bounded query on the open analysis. Everything is defensive — a case
imported as a plain spreadsheet has none of the columns a Hayabusa case has, and a
missing column must read as "that is not in this case", not as a stack trace.
"""
from __future__ import annotations

ROW_LIMIT = 25
LINE_CHARS = 240

DETAIL_COLUMNS = ('details', 'detailsshort', 'message', 'ruletitle', 'description', 'value')
HOST_COLUMNS = ('computer', 'host', 'hostname', 'machine')
TIME_COLUMNS = ('timestamp', 'timecreated', 'time', 'datetime', 'date')
ID_COLUMNS = ('eventid', 'event_id', 'id')
SOURCE_COLUMNS = ('evtxfile', 'sourcefile', 'source', 'file', 'path')
ARTIFACT_COLUMNS = ('artifact', 'artifactkind', 'evidence', 'kind')


def _clip(value, limit=LINE_CHARS):
    text = ' '.join(str(value if value is not None else '').split())
    return text[:limit]


class CaseTools:
    """`query(sql, params)` runs on the interface's connection, on its own thread."""

    def __init__(self, query, findings=None, brief=None, context=None):
        self.query = query
        self.findings = findings or (lambda: [])
        self.brief = brief or ''
        self.context = context or (lambda: '')
        self._columns = None

    # ------------------------------------------------------------------ reading
    def columns(self):
        """The columns of `events`, read where a view and a table are both described.

        `PRAGMA table_info` answers for a table and says nothing about a view, and an
        imported case exposes `events` as a view as soon as a derived column exists —
        which is why the assistant once reported that a case had no text to search.
        """
        if self._columns is None:
            rows = []
            for sql in ("SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='events' ORDER BY ordinal_position",
                        "PRAGMA table_info('events')"):
                try:
                    rows = self.query(sql, [])
                except Exception:  # noqa: BLE001 - a case without events is still a case
                    rows = []
                if rows:
                    break
            self._columns = {}
            for row in rows:
                name = str(row[0]) if row else ''
                if name and name.casefold() not in ('cid', 'notnull', 'dflt_value'):
                    self._columns[name.casefold()] = name
        return self._columns

    def column(self, candidates):
        columns = self.columns()
        for candidate in candidates:
            if candidate in columns:
                return columns[candidate]
        return ''

    def _count(self, sql, params=()):
        try:
            rows = self.query(sql, list(params))
            return int(rows[0][0]) if rows and rows[0] and rows[0][0] is not None else 0
        except Exception:  # noqa: BLE001 - an unreadable count is zero rows, not a crash
            return 0

    # ------------------------------------------------------------------ brief
    def describe(self):
        if self.brief:
            return self.brief
        selected = ''
        try:
            selected = self.context() or ''
        except Exception:  # noqa: BLE001 - a brief is context, never a failure
            selected = ''
        detections = self.findings()
        total = self._count('SELECT count(*) FROM events')
        if not total and not detections:
            return 'The case holds no imported rows yet.'
        if not total:
            detections_text = self._detections_brief(detections)
            return detections_text or 'The case holds no imported rows yet.'
        parts = ['%d row(s) in the case.' % total]
        host = self.column(HOST_COLUMNS)
        if host:
            rows = self.query('SELECT %s, count(*) FROM events GROUP BY 1 ORDER BY 2 DESC '
                              'LIMIT 8' % host, [])
            if rows:
                parts.append('Hosts: ' + ', '.join('%s (%d)' % (_clip(r[0], 40), r[1]) for r in rows))
        time = self.column(TIME_COLUMNS)
        if time:
            rows = self.query('SELECT min(%s), max(%s) FROM events' % (time, time), [])
            if rows and rows[0][0]:
                parts.append('Time span: %s to %s' % (_clip(rows[0][0], 30), _clip(rows[0][1], 30)))
        source = self.column(SOURCE_COLUMNS)
        if source:
            rows = self.query('SELECT %s, count(*) FROM events GROUP BY 1 ORDER BY 2 DESC LIMIT 12'
                              % source, [])
            if rows:
                parts.append('Sources: ' + ', '.join('%s (%d)' % (_clip(str(r[0]).rsplit('\\', 1)[-1], 60), r[1])
                                                     for r in rows if r[0]))
        if detections:
            counts = {}
            for item in detections:
                level = str(item.get('level') or 'unknown')
                counts[level] = counts.get(level, 0) + 1
            parts.append('%d detection(s) loaded, by severity: %s.'
                         % (len(detections), ', '.join('%d %s' % (count, level)
                                                       for level, count in counts.items())))
            parts.append('The most severe first:')
            for item in detections[:12]:
                parts.append('  - %s, %s, on %s, at %s' % (
                    item.get('title', '?'), item.get('level', '?'), item.get('host', '?'),
                    str(item.get('start', ''))[:19]))
        text = '\n'.join(parts)
        if selected:
            text += '\n' + selected
        return text

    def _detections_brief(self, detections):
        if not detections:
            return ''
        counts = {}
        for item in detections:
            level = str(item.get('level') or 'unknown')
            counts[level] = counts.get(level, 0) + 1
        lines = ['%d detection(s) loaded, by severity: %s.' % (
            len(detections), ', '.join('%d %s' % (count, level) for level, count in counts.items())),
            'The most severe first:']
        for item in detections[:12]:
            lines.append('  - %s, %s, on %s, at %s' % (
                item.get('title', '?'), item.get('level', '?'), item.get('host', '?'),
                str(item.get('start', ''))[:19]))
        return '\n'.join(lines)

    # ------------------------------------------------------------------ lookups
    def call(self, name, arguments):
        if name == 'overview':
            text = self.describe()
            return text, 1
        if name == 'search':
            return self.search(arguments.get('text', ''), arguments.get('host', ''),
                               arguments.get('event_id', ''), int(arguments.get('limit') or 0))
        if name == 'findings':
            return self.detections(arguments.get('host', ''), int(arguments.get('limit') or 0))
        if name == 'artifact':
            return self.artifact(arguments.get('artifact', ''), int(arguments.get('limit') or 0))
        return 'Unknown lookup: %s' % name, 0

    def search(self, text='', host='', event_id='', limit=0):
        text, host, event_id = (text or '').strip(), (host or '').strip(), (event_id or '').strip()
        if not (text or host or event_id):
            return 'The lookup had no filter; nothing was read.', 0
        where, params = [], []
        if text:
            detail = self.column(DETAIL_COLUMNS)
            if detail:
                where.append('%s ILIKE ?' % detail)
                params.append('%' + text + '%')
            else:
                return 'This case has no text column to search.', 0
        if host:
            column = self.column(HOST_COLUMNS)
            if column:
                where.append('%s ILIKE ?' % column)
                params.append(host)
        if event_id:
            column = self.column(ID_COLUMNS)
            if column:
                where.append('CAST(%s AS VARCHAR) = ?' % column)
                params.append(event_id)
        limit = min(limit or ROW_LIMIT, ROW_LIMIT)
        return self._render('SELECT * FROM events WHERE %s ORDER BY 1 DESC LIMIT %d'
                            % (' AND '.join(where), limit), params)

    def artifact(self, kind, limit=0):
        kind = (kind or '').strip()
        if not kind:
            return 'No artifact kind was named.', 0
        column = self.column(ARTIFACT_COLUMNS)
        params, where = ['%' + kind + '%'], None
        if column:
            where = '%s ILIKE ?' % column
        else:
            source = self.column(SOURCE_COLUMNS)
            if not source:
                return 'This case does not label its rows by artifact.', 0
            where = '%s ILIKE ?' % source
        limit = min(limit or ROW_LIMIT, ROW_LIMIT)
        return self._render('SELECT * FROM events WHERE %s ORDER BY 1 DESC LIMIT %d'
                            % (where, limit), params, title='%s rows' % kind)

    def detections(self, host='', limit=0):
        items = [item for item in self.findings()
                 if not host or str(item.get('host', '')).casefold() == host.strip().casefold()]
        if not items:
            return 'No detection matches.', 0
        # A planner that asks for one row starves its own answer: a page is the floor.
        limit = min(max(limit, 10), 25)
        lines = []
        for item in items[:limit]:
            lines.append('- %s, %s, on %s, at %s%s' % (
                item.get('title', '?'), item.get('level', '?'), item.get('host', '?'),
                str(item.get('start', ''))[:19],
                '' if item.get('count') in (1, '1', None) else ' (%s occurrences)' % item['count']))
        return '\n'.join(lines), len(items[:limit])

    # ------------------------------------------------------------------ rendering
    def _render(self, sql, params, title=''):
        try:
            rows = self.query(sql, params)
        except Exception as error:  # noqa: BLE001
            return 'The query was refused: %s' % error, 0
        if not rows:
            return 'Nothing matches in this case.', 0
        header = [str(value) for value in (params or [])]
        lines = [(title or 'rows') + ': %d' % len(rows)]
        for index, row in enumerate(rows, 1):
            cells = ' | '.join(_clip(value, 70) for value in row if value not in (None, ''))
            lines.append('[%d] %s' % (index, cells))
        del header
        return '\n'.join(lines), len(rows)
