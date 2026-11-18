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


READ_ONLY_VERBS = ('select', 'pragma', 'describe', 'with')


def select_only(sql):
    """The assistant analyses; it never changes a case. Refuse anything but a read."""
    head = ' '.join(str(sql).strip().split())[:12].casefold()
    if not head.startswith(READ_ONLY_VERBS):
        raise ValueError('The assistant only reads the case; this statement was refused.')
    return sql


class CaseTools:
    """`query(sql, params)` runs on the interface's connection, on its own thread."""

    def __init__(self, query, findings=None, brief=None, context=None):
        self._run = query
        self.query = self._guarded(query)
        self.findings = findings or (lambda: [])
        self.brief = brief or ''
        self.context = context or (lambda: '')
        self._columns = None

    def _guarded(self, query):
        def run(sql, params):
            return query(select_only(sql), params)
        return run

    # ------------------------------------------------------------------ reading
    def headers(self):
        """The names the analyst gave the columns, kept in the metadata table.

        An imported analysis exposes `events` as `__row_id, c0, c1, ...`: the real
        headers live in `metadata`, as JSON. Reading only the view is why the assistant
        once decided that a case had no timestamp and no text to search.
        """
        if getattr(self, '_headers', None) is None:
            self._headers = []
            try:
                rows = self.query("SELECT value FROM metadata WHERE key='source'", [])
                if rows and rows[0] and rows[0][0]:
                    import json
                    self._headers = [str(name) for name in json.loads(rows[0][0]).get('headers') or []]
            except Exception:  # noqa: BLE001 - a case without metadata is still a case
                self._headers = []
        return self._headers

    def physical(self):
        """The concrete column names of the view, in order."""
        if getattr(self, '_physical', None) is None:
            self._physical = []
            for sql in ("SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='events' ORDER BY ordinal_position",
                        "PRAGMA table_info('events')"):
                try:
                    rows = self.query(sql, [])
                except Exception:  # noqa: BLE001
                    rows = []
                if rows:
                    self._physical = [str(row[0]) for row in rows if row and row[0]]
                    break
        return self._physical

    def labels(self):
        """What each column really is, in the order the rows come back."""
        headers = self.headers()
        names = []
        for name in self.physical():
            if name.startswith('__'):
                continue
            index = name[1:]
            if name[:1] == 'c' and index.isdigit() and int(index) < len(headers):
                names.append(headers[int(index)])
            else:
                names.append(name)
        return names

    def columns(self):
        """Logical name (casefold) to the column to put in the SQL."""
        if self._columns is None:
            self._columns = {}
            for physical, label in zip([name for name in self.physical()
                                        if not name.startswith('__')], self.labels()):
                self._columns.setdefault(label.casefold(), physical)
                self._columns.setdefault(physical.casefold(), physical)
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
        if name == 'around':
            return self.around(arguments.get('host', ''), arguments.get('time', ''),
                               arguments.get('minutes') or 5, int(arguments.get('limit') or 0))
        if name == 'timeline':
            return self.timeline(arguments.get('host', ''), int(arguments.get('limit') or 0))
        if name == 'sequence':
            return self.sequence(arguments.get('host', ''), arguments.get('time', ''),
                                 arguments.get('minutes') or 15,
                                 int(arguments.get('limit') or 0))
        if name == 'rare':
            return self.rare(arguments.get('column') or arguments.get('text', ''),
                             int(arguments.get('limit') or 0))
        if name == 'entity':
            return self.entity(arguments.get('text', ''), int(arguments.get('limit') or 0))
        if name == 'stats':
            return self.stats(arguments.get('column') or arguments.get('text', ''))
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

    def around(self, host='', timestamp='', minutes=5, limit=0):
        """What else happened on that host in the same few minutes: the first real pivot."""
        column = self.column(TIME_COLUMNS)
        if not column:
            return 'This case has no timestamp column.', 0
        stamp = str(timestamp or '').strip()
        if not stamp:
            return 'No time was given to look around.', 0
        try:
            minutes = max(1, min(int(minutes or 5), 240))
        except (TypeError, ValueError):
            minutes = 5
        where = ["CAST(%s AS TIMESTAMP) BETWEEN CAST(? AS TIMESTAMP) - INTERVAL %d MINUTE "
                 'AND CAST(? AS TIMESTAMP) + INTERVAL %d MINUTE' % (column, minutes, minutes)]
        params = [stamp, stamp]
        host_column = self.column(HOST_COLUMNS)
        if host and host_column:
            where.append('%s ILIKE ?' % host_column)
            params.append(host)
        limit = min(max(int(limit or 0), 10), ROW_LIMIT)
        return self._render('SELECT * FROM events WHERE %s ORDER BY %s LIMIT %d'
                            % (' AND '.join(where), column, limit), params,
                            title='around %s (%d min)' % (stamp, minutes))

    def timeline(self, host='', limit=0):
        """Where the activity is: one line per hour, the shape of the day before the detail."""
        column = self.column(TIME_COLUMNS)
        if not column:
            return 'This case has no timestamp column.', 0
        where, params = [], []
        host_column = self.column(HOST_COLUMNS)
        if host and host_column:
            where.append('%s ILIKE ?' % host_column)
            params.append(host)
        bucket = "strftime(CAST(%s AS TIMESTAMP), '%%Y-%%m-%%d %%H:00')" % column
        sql = 'SELECT %s AS bucket, count(*) FROM events %s GROUP BY 1 ORDER BY 2 DESC LIMIT %d' % (
            bucket, ('WHERE ' + ' AND '.join(where)) if where else '', min(max(int(limit or 0), 10), 40))
        try:
            rows = self.query(sql, params)
        except Exception as error:  # noqa: BLE001
            return 'The timeline could not be read: %s' % error, 0
        if not rows:
            return 'Nothing matches in this case.', 0
        lines = ['%d busiest hour(s):' % len(rows)]
        for stamp, count in rows:
            try:
                bar = '#' * min(40, max(1, int(count)))
            except (TypeError, ValueError):
                bar = '#'
            lines.append('  %s  %-40s %s' % (stamp, bar, count))
        return '\n'.join(lines), len(rows)

    def sequence(self, host='', timestamp='', minutes=15, limit=0):
        """The order of what happened on a host: a case is read as a sequence, not a set."""
        column = self.column(TIME_COLUMNS)
        if not column:
            return 'This case has no timestamp column.', 0
        where, params = [], []
        host_column = self.column(HOST_COLUMNS)
        if host and host_column:
            where.append('%s ILIKE ?' % host_column)
            params.append(host)
        stamp = str(timestamp or '').strip()
        if stamp:
            try:
                minutes = max(1, min(int(minutes or 15), 240))
            except (TypeError, ValueError):
                minutes = 15
            where.append("CAST(%s AS TIMESTAMP) BETWEEN CAST(? AS TIMESTAMP) - INTERVAL %d MINUTE "
                         'AND CAST(? AS TIMESTAMP) + INTERVAL %d MINUTE' % (column, minutes, minutes))
            params += [stamp, stamp]
        limit = min(max(int(limit or 0), 15), 25)
        sql = 'SELECT * FROM events %s ORDER BY %s LIMIT %d' % (
            ('WHERE ' + ' AND '.join(where)) if where else '', column, limit)
        return self._render(sql, params, title='in order')

    def rare(self, column='', limit=0):
        """The least frequent values: a process that ran once is where hunting starts."""
        columns = self.columns()
        wanted = str(column or '').strip().casefold()
        name = columns.get(wanted) or self.column(DETAIL_COLUMNS) or self.column(ID_COLUMNS)
        if not name:
            return 'This case has no column to count.', 0
        limit = min(max(int(limit or 0), 10), 25)
        sql = ('SELECT %s, count(*) FROM events WHERE %s IS NOT NULL GROUP BY 1 '
               'ORDER BY 2 ASC, 1 ASC LIMIT %d' % (name, name, limit))
        try:
            rows = self.query(sql, [])
        except Exception as error:  # noqa: BLE001
            return 'The count was refused: %s' % error, 0
        if not rows:
            return 'Nothing to count in this case.', 0
        lines = ['rarest values of %s:' % name]
        for value, count in rows:
            lines.append('  %s  (%s)' % (_clip(value, 90), count))
        return '\n'.join(lines), len(rows)

    def entity(self, name='', limit=0):
        """Everything one name touches: a host, an account, a path, a binary."""
        needle = str(name or '').strip()
        if not needle:
            return 'No name was given to look up.', 0
        columns = [self.column(HOST_COLUMNS), self.column(DETAIL_COLUMNS),
                   self.column(SOURCE_COLUMNS)]
        columns = [column for column in dict.fromkeys(columns) if column]
        if not columns:
            return 'This case has no text column to look a name up in.', 0
        where = ' OR '.join('%s ILIKE ?' % column for column in columns)
        params = ['%' + needle + '%'] * len(columns)
        limit = min(max(int(limit or 0), 10), ROW_LIMIT)
        time_column = self.column(TIME_COLUMNS)
        order = time_column or '1'
        return self._render('SELECT * FROM events WHERE %s ORDER BY %s LIMIT %d'
                            % (where, order, limit), params, title='everything about %s' % needle)

    def stats(self, column=''):
        """A column at a glance: how many distinct, how many empty, the range."""
        columns = self.columns()
        name = columns.get(str(column or '').strip().casefold())
        if not name:
            return 'That column is not in this case.', 0
        try:
            row = self.query('SELECT count(*), count(%s), count(DISTINCT %s), min(%s), max(%s) '
                             'FROM events' % (name, name, name, name), [])[0]
        except Exception as error:  # noqa: BLE001
            return 'The summary was refused: %s' % error, 0
        total, filled, distinct, low, high = row
        return ('%s: %s row(s), %s filled, %s distinct, from %s to %s'
                % (name, total, filled, distinct, _clip(low, 40), _clip(high, 40))), 1

    # ------------------------------------------------------------------ rendering
    def _render(self, sql, params, title=''):
        try:
            rows = self.query(sql, params)
        except Exception as error:  # noqa: BLE001
            return 'The query was refused: %s' % error, 0
        if not rows:
            return 'Nothing matches in this case.', 0
        labels = self.labels()
        skip = 1 if self.physical()[:1] == ['__row_id'] else 0
        lines = [(title or 'rows') + ': %d' % len(rows)]
        if labels:
            lines.append('  ' + ' | '.join(labels))
        for index, row in enumerate(rows, 1):
            cells = ' | '.join(_clip(value, 70) for value in row[skip:])
            lines.append('[%d] %s' % (index, cells))
        return '\n'.join(lines), len(rows)
