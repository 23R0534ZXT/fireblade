"""All identifiers are generated; user values are always bound parameters.

One serialized DuckDB connection per case. Call expensive operations from workers;
interrupt() is intentionally callable from another thread without the query lock.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import threading
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import duckdb

from .models import Filter, FilterGroup, SortKey, View
from .conditions import compile_condition
from .errors import OperationCancelled, job_cancelled
from .settings import Settings


class Case:
    PAGE_SIZE = Settings().page_size

    def __init__(self, path: str | Path, memory_mb=None, threads=None, settings=None):
        self.settings = settings or Settings()
        overrides = {}
        if memory_mb is not None:
            overrides["memory_mb"] = memory_mb
        if threads is not None:
            overrides["threads"] = threads
        self.settings = replace(self.settings, **overrides)
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._interrupt_lock = threading.Lock()
        self._finalizing_transaction = False
        self.cancelled = threading.Event()
        self._page_cache_key = None
        self._bookmark_revision = 0
        self.db = duckdb.connect(str(self.path))
        self.db.execute(f"SET memory_limit='{self.settings.memory_mb}MB'")
        self.db.execute(f"SET threads={self.settings.threads}")
        self.db.execute("SET enable_progress_bar=false")
        self.db.execute("SET preserve_insertion_order=true")
        self.db.execute("SET temp_directory=?", [str(self.path) + ".tmp"])
        self.headers: list[str] = []
        if self.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='metadata'").fetchone()[0]:
            self.info = json.loads(self.db.execute("SELECT value FROM metadata WHERE key='source'").fetchone()[0])
            self.headers = self.info["headers"]
        else:
            self.info = {}

    def close(self):
        with self.lock:
            self.db.close()

    def interrupt(self):
        with self._interrupt_lock:
            self.cancelled.set()
            if not self._finalizing_transaction:
                self.db.interrupt()

    @contextmanager
    def finalizing_transaction(self):
        """Allow rollback to finish; a commit already in progress finishes too."""
        with self._interrupt_lock:
            self._finalizing_transaction = True
        try:
            yield
        finally:
            with self._interrupt_lock:
                self._finalizing_transaction = False

    def check_cancelled(self):
        if self.cancelled.is_set() or job_cancelled():
            raise OperationCancelled()

    @contextmanager
    def operation(self, final_check=True):
        """Serialize reads/writes and normalize DuckDB's expected interruption.

        New operations can run after cancellation. Read results are checked before
        returning; mutations check before their explicit commit/replace instead.
        """
        with self.lock:
            self.cancelled.clear()
            try:
                self.check_cancelled()
                yield
                if final_check:
                    self.check_cancelled()
            except duckdb.InterruptException as exc:
                raise OperationCancelled() from exc

    @contextmanager
    def utf8_input(self, source, encoding):
        if encoding.lower() in ("utf-8", "utf8", "utf-8-sig"):
            yield source
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", suffix=".csv", dir=self.path.parent, delete=False) as out:
                temporary = Path(out.name)
                with source.open(encoding=encoding, newline="", errors="strict") as incoming:
                    while chunk := incoming.read(1024 * 1024):
                        self.check_cancelled()
                        out.write(chunk)
            yield temporary
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def column(self, index):
        if not isinstance(index, int) or not 0 <= index < len(self.headers):
            raise ValueError("Colonne invalide")
        return f'"c{index}"'

    @staticmethod
    def validate_single_column_header(path):
        """Do not silently flatten a malformed multi-column CSV during sniffing."""
        with path.open(encoding="utf-8-sig", newline="") as incoming:
            for separator in (",", ";", "\t", "|"):
                incoming.seek(0)
                try:
                    header = next(csv.reader(incoming, delimiter=separator, strict=True), [])
                except csv.Error as exc:
                    raise ValueError("Détection CSV ambiguë. Choisissez le séparateur dans Options du CSV.") from exc
                if len(header) > 1:
                    raise ValueError("La détection automatique n’a pas trouvé de séparateur cohérent. Choisissez le séparateur dans Options du CSV.")

    def import_csv(self, source, delimiter=None, encoding="utf-8", progress=lambda _: None):
        return self._import_table(source, delimiter, encoding, progress)

    def import_excel(self, source, sheet, progress=lambda _: None):
        return self._import_table(source, ",", "utf-8", progress, sheet=sheet)

    def _import_table(self, source, delimiter, encoding, progress, sheet=None):
        source = Path(source).resolve()
        if self.headers:
            raise ValueError("Ce dossier contient déjà un import")
        with self.operation(final_check=False):
            # Hash before and after parsing detects source changes during acquisition.
            progress("Calcul SHA-256 de la source…")
            def digest():
                h = hashlib.sha256()
                with source.open("rb") as f:
                    while chunk := f.read(4 * 1024 * 1024):
                        self.check_cancelled()
                        h.update(chunk)
                return h.hexdigest()
            before = source.stat()
            sha = digest()
            progress("Import sur disque · détection du schéma…")
            options = dict(header=True, all_varchar=True, sample_size=20480,
                           encoding="utf-8", strict_mode=True, ignore_errors=False,
                           parallel=False, skiprows=0, null_padding=False,
                           comment="", quotechar='"', escapechar='"')
            if delimiter:
                options["delimiter"] = delimiter
            try:
                self.check_cancelled()
                self.db.execute("BEGIN")
                if sheet is not None:
                    from .spreadsheets import csv_from_sheet
                    incoming = csv_from_sheet(source, sheet, self.path.parent, self.check_cancelled)
                else:
                    incoming = self.utf8_input(source, encoding)
                with incoming as input_path:
                    self.check_cancelled()
                    relation = self.db.read_csv(str(input_path), **options)
                    headers = relation.columns
                    if not headers:
                        raise ValueError("Aucune colonne dans le CSV")
                    if delimiter is None and len(headers) == 1:
                        self.validate_single_column_header(input_path)
                    projections = [f'"{h.replace(chr(34), chr(34)*2)}" AS "c{i}"' for i, h in enumerate(headers)]
                    progress("Écriture des enregistrements sur disque…")
                    self.check_cancelled()
                    relation.project('row_number() OVER () AS "__row_id", ' + ", ".join(projections)).create("events")
                count = self.db.execute("SELECT count(*) FROM events").fetchone()[0]
                progress("Vérification de l’intégrité de la source…")
                after_sha = digest()
                after = source.stat()
                if sha != after_sha or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("Le fichier source a changé pendant l’import")
                info = dict(path=str(source), size=before.st_size, sha256=sha,
                            headers=headers, rows=count, encoding=encoding,
                            delimiter=delimiter or "auto", schema_version=1)
                if sheet is not None:
                    info.update(format="xlsx", sheet=sheet)
                self.db.execute("CREATE TABLE metadata (key VARCHAR PRIMARY KEY, value VARCHAR)")
                self.db.execute("INSERT INTO metadata VALUES ('source', ?)", [json.dumps(info)])
                self.db.execute("CREATE TABLE bookmarks (row_id BIGINT PRIMARY KEY, note VARCHAR)")
                self.db.execute("CREATE TABLE views (name VARCHAR PRIMARY KEY, value VARCHAR)")
                progress("Validation de l’analyse…")
                with self.finalizing_transaction():
                    self.check_cancelled()
                    self.db.execute("COMMIT")
                self.info, self.headers = info, headers
                return info
            except BaseException:
                with self.finalizing_transaction():
                    try:
                        self.db.execute("ROLLBACK")
                    except duckdb.TransactionException:
                        # BEGIN may itself have failed; preserve the original error.
                        pass
                raise

    def where(self, view: View, path=()):
        clauses, args = [], []
        if view.search:
            clauses.append("(" + " OR ".join(f"contains(lower(coalesce({self.column(i)}, '')), lower(?))" for i in range(len(self.headers))) + ")")
            args += [view.search] * len(self.headers)
        if view.filters:
            sql, values = self.condition(FilterGroup("and", view.filters))
            clauses.append("(" + sql + ")")
            args.extend(values)
        if view.expression is not None:
            sql, values = self.condition(view.expression)
            clauses.append("(" + sql + ")")
            args.extend(values)
        for i, val in enumerate(path):
            clauses.append(f"{self.column(view.groups[i])} IS NOT DISTINCT FROM ?")
            args.append(val)
        if view.bookmarks_only:
            clauses.append("__row_id IN (SELECT row_id FROM bookmarks)")
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), args

    def condition(self, expression):
        return compile_condition(expression, self.column, self.numeric_expression)

    def validate_view(self, view):
        self.where(view)
        self.order(view)
        if len(view.groups) != len(set(view.groups)):
            raise ValueError("Une colonne ne peut apparaître deux fois dans les groupes")
        for column in view.groups:
            self.column(column)
        if len(view.format_rules) > 32:
            raise ValueError("32 règles de coloration au maximum")
        import re
        for rule in view.format_rules:
            self.condition(rule.condition)
            if rule.target is not None:
                self.column(rule.target)
            if not all(isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in (rule.background, rule.foreground)):
                raise ValueError("Couleur invalide ; utilisez #RRGGBB")

    def page_styles(self, view, rows):
        """Evaluate the same conditions as filters, only for visible row IDs."""
        rules = view.format_rules
        if len(rules) > 32:
            raise ValueError("32 règles de coloration au maximum")
        if not rows or not rules:
            return {}
        projections, args = [], []
        for rule in rules:
            if rule.target is not None:
                self.column(rule.target)
            sql, values = self.condition(rule.condition) if rule.enabled else ("FALSE", [])
            projections.append("(" + sql + ")")
            args.extend(values)
        ids = [row[0] for row in rows]
        with self.operation():
            result = self.db.execute(
                "SELECT __row_id, " + ", ".join(projections) +
                " FROM events WHERE __row_id IN (" + ",".join("?" for _ in ids) + ")",
                args + ids).fetchall()
        return {row[0]: tuple(i for i, matched in enumerate(row[1:]) if matched) for row in result}

    @staticmethod
    def numeric_expression(column):
        # The general DECIMAL parser is expensive for 128-bit decimals. Integer
        # strings can take the much faster HUGEINT parser without using floats.
        # Decimal / scientific / invalid strings keep DuckDB's original semantics.
        return (f"CASE WHEN regexp_full_match({column}, '[[:space:]]*[+-]?[0-9]+[[:space:]]*') "
                f"THEN try_cast(try_cast({column} AS HUGEINT) AS DECIMAL(38,10)) "
                f"ELSE try_cast({column} AS DECIMAL(38,10)) END")

    def order(self, view):
        keys = view.sorts or ([SortKey(view.sort_column, view.sort_type, view.descending)] if view.sort_column is not None else [])
        if len(keys) > 16 or len({key.column for key in keys}) != len(keys):
            raise ValueError("16 colonnes de tri distinctes au maximum")
        parts = []
        for key in keys:
            col = self.column(key.column)
            if key.kind not in ("text", "number", "timestamp"):
                raise ValueError("Type de tri invalide")
            if key.kind == "number":
                col = self.numeric_expression(col)
            elif key.kind == "timestamp":
                col = f"try_cast({col} AS TIMESTAMP)"
            parts.append(f"{col} {'DESC' if key.descending else 'ASC'} NULLS LAST")
        return " ORDER BY " + ", ".join(parts + ["__row_id"])

    def page(self, view: View, path=(), offset=0, limit=None):
        limit = self.settings.page_size if limit is None else limit
        with self.operation():
            where, args = self.where(view, path)
            limit, offset = max(1, min(limit, self.settings.page_size)), max(0, offset)
            if len(path) < len(view.groups):
                col = self.column(view.groups[len(path)])
                sql = f"SELECT {col}, count(*) FROM events{where} GROUP BY {col} ORDER BY count(*) DESC, {col} ASC NULLS LAST LIMIT ? OFFSET ?"
            else:
                order = self.order(view)
                key = (where, tuple(args), order, self._bookmark_revision if view.bookmarks_only else None)
                if (self.settings.cache_sorted_pages and (view.sort_column is not None or view.sorts)
                        and (offset >= self.settings.max_loaded_rows or self._page_cache_key == key)):
                    return self.sorted_page(where, args, order, key, offset, limit)
                sql = f"SELECT * FROM events{where}{order} LIMIT ? OFFSET ?"
            return self.db.execute(sql, args + [limit, offset]).fetchall()

    def sorted_page(self, where, args, order, key, offset, limit):
        """One temporary order at a time, containing IDs rather than full rows.

        The first window uses Top-N. Navigating beyond it builds a reusable order
        inside DuckDB's buffer/spill budget, removed when the connection closes.
        """
        if key != self._page_cache_key:
            self._page_cache_key = None
            self.db.execute(
                'CREATE OR REPLACE TEMP TABLE "__timeline_order" AS '
                f'SELECT row_number() OVER ({order}) AS position, __row_id FROM events{where}', args)
            self.check_cancelled()
            self._page_cache_key = key
        return self.db.execute(
            'SELECT e.* FROM events e JOIN "__timeline_order" p USING (__row_id) '
            'WHERE p.position > ? AND p.position <= ? ORDER BY p.position',
            [offset, offset + limit]).fetchall()

    def count(self, view):
        with self.operation():
            where, args = self.where(view)
            return self.db.execute("SELECT count(*) FROM events" + where, args).fetchone()[0]

    def bookmark(self, row_id, note):
        with self.operation(final_check=False):
            if note is None:
                self.db.execute("DELETE FROM bookmarks WHERE row_id=?", [row_id])
            else:
                self.db.execute("INSERT OR REPLACE INTO bookmarks VALUES (?, ?)", [row_id, note])
            self._bookmark_revision += 1

    def bookmarks(self):
        with self.operation():
            return dict(self.db.execute("SELECT * FROM bookmarks").fetchall())

    def save_view(self, name, view):
        with self.operation(final_check=False):
            self.db.execute("INSERT OR REPLACE INTO views VALUES (?, ?)", [name, view.to_json()])

    def views(self):
        with self.operation():
            return {name: View.from_json(value) for name, value in self.db.execute("SELECT * FROM views ORDER BY name").fetchall()}

    def export(self, target, view, grouped=False):
        target = Path(target).resolve()
        if target in (self.path, Path(self.info["path"]).resolve()):
            raise ValueError("L’export ne peut pas écraser la source ou le dossier d’analyse")
        # Atomic replacement: failed exports never leave an apparently complete CSV.
        temporary = target.with_name(target.name + ".partial")
        if temporary.exists():
            raise ValueError(f"Le fichier temporaire existe déjà : {temporary}")
        with self.operation(final_check=False):
            where, args = self.where(view)
            cols = ", ".join(self.column(i) for i in range(len(self.headers)))
            headers = self.headers
            if grouped and view.groups:
                cols = ", ".join(self.column(i) for i in view.groups)
                sql = f"SELECT {cols}, count(*) FROM events{where} GROUP BY {cols} ORDER BY count(*) DESC"
                headers = [self.headers[i] for i in view.groups] + ["Count"]
            else:
                sql = f"SELECT {cols} FROM events{where}{self.order(view)}"
            owns_temporary = False
            try:
                cursor = self.db.execute(sql, args)
                if target.suffix.lower() == ".xlsx":
                    from .spreadsheets import write_xlsx
                    with temporary.open("xb"):
                        owns_temporary = True
                    write_xlsx(temporary, headers, cursor, self.settings.export_batch_rows, self.check_cancelled)
                else:
                    with temporary.open("x", encoding="utf-8-sig", newline="") as out:
                        owns_temporary = True
                        writer = csv.writer(out)
                        writer.writerow(headers)
                        while batch := cursor.fetchmany(self.settings.export_batch_rows):
                            self.check_cancelled()
                            writer.writerows(batch)
                self.check_cancelled()
                os.replace(temporary, target)
            except Exception:
                if owns_temporary:
                    temporary.unlink(missing_ok=True)
                raise
