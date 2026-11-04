"""Source-order export without sorting the complete evidence payload."""


class SourceOrderCursor:
    def __init__(self, case, columns, where, args):
        self.case, self.columns, self.where, self.args = case, columns, where, args
        self.last = 0

    def fetchmany(self, size):
        case = self.case
        size = min(size, 512)
        case.check_cancelled()
        conjunction = ' AND ' if self.where else ' WHERE '
        ids = [row[0] for row in case.db.execute(
            'SELECT __row_id FROM events' + self.where + conjunction +
            '__row_id>? ORDER BY __row_id LIMIT ?', self.args + [self.last, size]).fetchall()]
        if not ids:
            return []
        # ID ranges preserve storage-zone pruning; sorting only this batch keeps
        # wide strings outside the full-result sort's memory/spill workspace.
        rows = case.db.execute(
            'SELECT ' + self.columns + ' FROM events' + self.where + conjunction +
            '__row_id>? AND __row_id<=? ORDER BY __row_id',
            self.args + [self.last, ids[-1]]).fetchall()
        self.last = ids[-1]
        return rows
