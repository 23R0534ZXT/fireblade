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

from fireblade.core.models import Filter, FilterGroup, SortKey, View
from fireblade.core.summaries import group_expression, summary_expressions, group_order
from fireblade.core.conditions import compile_condition, validate_format_rules
from fireblade.core.errors import OperationCancelled, job_cancelled
from fireblade.core.settings import Settings
from fireblade.core import csv_chunks


class Case:
    PAGE_SIZE = Settings().page_size

    def __init__(self, path: str | Path, memory_mb=None, threads=None, settings=None, read_only=False):
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
        self._outline_key = None
        self._source_index_tried = False
        self._read_only = read_only
        self._plugin_object_session=None
        self._plugin_object_lock=threading.RLock()
        self._operation_depth=0
        self._plugin_sessions=[]
        self._plugin_functions={}
        self._saved_function_types={}
        self.plugin_restore_errors=[]
        from fireblade.core.analysis_storage import connect_analysis
        self.db = connect_analysis(self.path, read_only=read_only, allow_empty_import=True)
        self.db.execute(f"SET memory_limit='{self.settings.memory_mb}MB'")
        self.db.execute(f"SET threads={self.settings.threads}")
        self.db.execute("SET enable_progress_bar=false")
        self.db.execute("SET TimeZone='UTC'")
        self.db.execute("SET preserve_insertion_order=true")
        # DuckDB defaults to <database>.tmp, which remains available after
        # revoking external access on an existing analysis.
        self._plugin_udf=False
        self.headers: list[str] = []
        if self.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='metadata'").fetchone()[0]:
            self.info = json.loads(self.db.execute("SELECT value FROM metadata WHERE key='source'").fetchone()[0])
            self.headers = list(self.info["headers"])
            row = self.db.execute("SELECT value FROM metadata WHERE key='derived'").fetchone()
            self.derived = json.loads(row[0]) if row else []
            self.headers += [d['name'] for d in self.derived]
            from fireblade.core.plugin_registry import restore_functions
            try:restore_functions(self)
            except BaseException:
                self.close()
                raise
        else:
            self.info = {}
            self.derived = []

    @property
    def expression_functions(self):
        return self._saved_function_types | {name:session.types.get(name,"text") for name,session in self._plugin_functions.items() if session.process.poll() is None}

    def close(self):
        with self.lock:
            if self._plugin_object_session:self._plugin_object_session.close();self._plugin_object_session=None
            for session in self._plugin_sessions:session.close()
            self._plugin_sessions.clear();self._plugin_functions.clear()
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
    def serial_query_threads(self):
        """Wide external sorts need one spill workspace within a small budget."""
        self.db.execute('SET threads=1')
        try:
            yield
        finally:
            with self.finalizing_transaction():
                self.db.execute(f'SET threads={self.settings.threads}')

    @contextmanager
    def operation(self, final_check=True):
        """Serialize reads/writes and normalize DuckDB's expected interruption.

        New operations can run after cancellation. Read results are checked before
        returning; mutations check before their explicit commit/replace instead.
        """
        with self.lock:
            self._operation_depth+=1
            self.cancelled.clear()
            try:
                self.check_cancelled()
                yield
                if final_check:
                    self.check_cancelled()
            except duckdb.InterruptException as exc:
                raise OperationCancelled() from exc
            except duckdb.Error as exc:
                # Python UDF exceptions are wrapped by DuckDB as InvalidInputException.
                if self.cancelled.is_set() or job_cancelled():raise OperationCancelled() from exc
                raise
            finally:
                self._operation_depth-=1
                if self._operation_depth==0 and self._plugin_object_session:
                    try:
                        self.check_cancelled()
                        self._plugin_object_session.clear_handles()
                    except BaseException:
                        self._plugin_object_session.close();self._plugin_object_session=None

    @contextmanager
    def utf8_input(self, source, encoding):
        utf8 = encoding.lower() in ("utf-8", "utf8", "utf-8-sig")
        # PowerShell Export-Csv can prepend a #TYPE metadata line. Detect it
        # only at the beginning; ordinary data records starting #TYPE survive.
        with source.open(encoding="utf-8-sig" if utf8 else encoding, newline="", errors="strict") as probe:
            from fireblade.core.csv_preamble import preamble_lines
            skip_lines = preamble_lines(probe)
        if utf8 and not skip_lines:
            yield source
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", suffix=".csv", dir=self.path.parent, delete=False) as out:
                temporary = Path(out.name)
                with source.open(encoding="utf-8-sig" if utf8 else encoding, newline="", errors="strict") as incoming:
                    for _ in range(skip_lines):
                        incoming.readline()
                    while chunk := incoming.read(1024 * 1024):
                        self.check_cancelled()
                        out.write(chunk)
            yield temporary
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def column(self, index):
        if type(index) is not int or not 0 <= index < len(self.headers):
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

    def _import_table(self, source, delimiter, encoding, progress, sheet=None, provenance=None):
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
            if encoding=='auto':
                from fireblade.core.encodings import bom_encoding
                encoding=bom_encoding(source)
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
                    from fireblade.core.spreadsheets import csv_from_sheet
                    if source.suffix.lower() == ".xls":
                        from fireblade.core.legacy_excel import csv_from_sheet
                    incoming = csv_from_sheet(source, sheet, self.path.parent, self.check_cancelled)
                else:
                    incoming = self.utf8_input(source, encoding)
                with incoming as input_path:
                    self.check_cancelled()
                    headers = None
                    relation = batch = None
                    try:
                        relation = self.db.read_csv(str(input_path), **options)
                        headers = relation.columns
                        if not headers:
                            raise ValueError("Aucune colonne dans le CSV")
                        if delimiter is None and len(headers) == 1:
                            self.validate_single_column_header(input_path)
                        projections = [f'"{h.replace(chr(34), chr(34)*2)}" AS "c{i}"' for i, h in enumerate(headers)]
                        progress("Écriture des enregistrements sur disque…")
                        self.check_cancelled()
                        chunk_bytes = min(csv_chunks.CHUNK_BYTES, self.settings.memory_mb * 1024 * 1024 // 16)
                        if input_path.stat().st_size <= chunk_bytes:
                            relation.project('row_number() OVER () AS "__row_id", ' + ", ".join(projections)).create("events")
                        else:
                            # Release the original reader's sample buffers before the
                            # bounded queries. Explicit IDs preserve source order.
                            del relation
                            separator = delimiter or self.db.execute(
                                'SELECT Delimiter FROM sniff_csv(?, header=true, skip=0, comment=\'\', '
                                'quote=\'"\', escape=\'"\', sample_size=20480)', [str(input_path)]).fetchone()[0]
                            written = 0
                            self.db.execute('CREATE TABLE events (__row_id BIGINT, ' +
                                            ', '.join(f'"c{i}" VARCHAR' for i in range(len(headers))) + ')')
                            chunks = csv_chunks.csv_chunks(input_path, headers, separator, self.path.parent,
                                                           chunk_bytes, self.check_cancelled)
                            try:
                                for chunk, records in chunks:
                                    self.check_cancelled()
                                    batch_options = dict(options, delimiter=',')
                                    batch = self.db.read_csv(str(chunk), **batch_options)
                                    batch = batch.project(f'row_number() OVER () + {written} AS "__row_id", ' + ", ".join(projections))
                                    batch.insert_into('events')
                                    del batch
                                    written += records
                                    progress(f'Import sur disque · {written:,} enregistrements écrits…')
                            finally:
                                chunks.close()
                    except duckdb.OutOfMemoryException:
                        # Wide parser exports can exhaust native CSV vectors even
                        # for small files. Retry using bounded, parameter-bound rows.
                        if not headers:
                            with input_path.open(encoding='utf-8-sig',newline='') as probe:
                                if not delimiter:
                                    sample=probe.read(65536);probe.seek(0)
                                    try:delimiter=csv.Sniffer().sniff(sample,delimiters=',;\t|').delimiter
                                    except csv.Error:delimiter=','
                                headers=next((row for row in csv.reader(probe,delimiter=delimiter,strict=True) if row),None)
                            # Avoid guessing native renaming for ambiguous headers.
                            if not headers or any(not h for h in headers) or len({h.casefold() for h in headers})!=len(headers):raise
                        relation = batch = None
                        self.db.execute('ROLLBACK')
                        self.check_cancelled()
                        self.db.execute('BEGIN')
                        progress('Import à mémoire réduite…')
                        self._import_csv_rows(input_path, headers, delimiter, progress)
                count = self.db.execute("SELECT count(*) FROM events").fetchone()[0]
                progress("Vérification de l’intégrité de la source…")
                after_sha = digest()
                after = source.stat()
                if sha != after_sha or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("Le fichier source a changé pendant l’import")
                info = dict(path=str(source), size=before.st_size, sha256=sha,
                            headers=headers, rows=count, encoding=encoding,
                            delimiter=delimiter or "auto", schema_version=1)
                if provenance is not None:info.update(provenance)
                if sheet is not None:
                    info.update(format=source.suffix.lower().lstrip("."), sheet=sheet)
                self.db.execute("CREATE TABLE metadata (key VARCHAR PRIMARY KEY, value VARCHAR)")
                self.db.execute("INSERT INTO metadata VALUES ('source', ?)", [json.dumps(info)])
                self.db.execute("CREATE TABLE bookmarks (row_id BIGINT PRIMARY KEY, note VARCHAR)")
                self.db.execute("CREATE TABLE views (name VARCHAR PRIMARY KEY, value VARCHAR)")
                progress("Validation de l’analyse…")
                with self.finalizing_transaction():
                    self.check_cancelled()
                    self.db.execute("COMMIT")
                    self.db.execute('SET enable_external_access=false')
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

    def _import_csv_rows(self, source, headers, delimiter, progress):
        """Atomic low-memory fallback; preserve original cells and explicit row IDs."""
        csv.field_size_limit(max(csv.field_size_limit(), 16*1024*1024))
        self.db.execute('CREATE TABLE events (__row_id BIGINT, '+
                        ', '.join(f'"c{i}" VARCHAR' for i in range(len(headers)))+')')
        statement = 'INSERT INTO events VALUES ('+','.join('?' for _ in range(len(headers)+1))+')'
        with source.open(encoding='utf-8-sig', newline='') as incoming:
            if not delimiter:
                sample = incoming.read(65536); incoming.seek(0)
                delimiter = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
            reader = csv.reader(incoming, delimiter=delimiter, strict=True)
            next((row for row in reader if row), None)
            pending, size, written = [], 0, 0
            for row in reader:
                self.check_cancelled()
                if not row:continue
                if len(row) != len(headers):
                    raise ValueError(f'CSV incohérent à la ligne {reader.line_num}')
                written += 1
                # DuckDB's default null string is the empty CSV field, quoted or not.
                pending.append([written]+[value if value else None for value in row])
                size += sum(len(value) for value in row)
                if len(pending)>=64 or size>=1024*1024:
                    self.db.executemany(statement, pending)
                    pending, size = [], 0
                    progress(f'Import sur disque · {written:,} enregistrements écrits…')
            if pending:self.db.executemany(statement, pending)

    def add_derived_columns(self, definitions):
        """Add declarative columns atomically; source metadata/bytes stay intact."""
        from fireblade.core.derived import compile_definition
        if not self.headers:
            raise ValueError('Importez une source avant de calculer des colonnes')
        definitions = list(definitions)
        if not definitions or len(self.derived) + len(definitions) > 64:
            raise ValueError('De 1 à 64 colonnes dérivées par analyse')
        planned = self.derived + definitions
        headers = list(self.info['headers'])
        sql = 'SELECT * FROM "__fireblade_source_events"'
        for definition in planned:
            name = definition.get('name') if isinstance(definition, dict) else None
            if not isinstance(name, str) or name.casefold() in {h.casefold() for h in headers}:
                raise ValueError('Nom de colonne dérivée absent ou déjà utilisé')
            def column(index):
                if index in (-1,-2,-3):return self.expression_column(index)
                if type(index) is not int or not 0 <= index < len(headers):
                    raise ValueError('Une colonne dérivée ne peut référencer que les colonnes précédentes')
                return f'"c{index}"'
            column.case=self
            expression = compile_definition(definition, headers, column, self.numeric_expression)
            sql = f'SELECT events.*, cast(({expression}) AS VARCHAR) AS "c{len(headers)}" FROM ({sql}) AS events'
            headers.append(name)
        with self.operation(final_check=False):
            try:
                self.db.execute('BEGIN')
                if not self.derived:
                    # DuckDB blocks renaming a table with dependent indexes.
                    # Rebuild our optional navigation index on its new storage
                    # name, only when a point page is subsequently requested.
                    self.db.execute('DROP INDEX IF EXISTS "__fireblade_source_id"')
                    self.db.execute('ALTER TABLE events RENAME TO "__fireblade_source_events"')
                else:
                    self.db.execute('DROP VIEW events')
                self.db.execute('CREATE VIEW events AS ' + sql)
                # Bind the entire plan before committing, without scanning the file.
                self.db.execute('SELECT * FROM events LIMIT 0')
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES ('derived', ?)", [json.dumps(planned)])
                with self.finalizing_transaction():
                    self.check_cancelled()
                    self.db.execute('COMMIT')
            except BaseException:
                with self.finalizing_transaction():
                    self.db.execute('ROLLBACK')
                raise
            self.headers, self.derived = headers, planned
            self._page_cache_key = self._outline_key = None
            self._source_index_tried = False
        return headers

    def derived_quality(self, columns=None):
        """Report missing/invalid derived values; never discard their rows."""
        columns = list(range(len(self.info['headers']),len(self.headers))) if columns is None else columns
        with self.operation():
            return {self.headers[i]: self.db.execute(f'SELECT count(*) FILTER (WHERE {self.column(i)} IS NULL),count(*) FROM events').fetchone() for i in columns}

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
        if len(path) > len(view.groups):
            raise ValueError("Chemin de groupe plus profond que les regroupements de la vue")
        for i, val in enumerate(path):
            clauses.append(f"{group_expression(self, view, view.groups[i])} IS NOT DISTINCT FROM ?")
            args.append(val)
        if view.bookmarks_only:
            clauses.append("__row_id IN (SELECT row_id FROM bookmarks)")
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), args

    def expression_column(self,index):
        if index == -1:
            return 'cast(events.__row_id AS VARCHAR)'
        if index == -2:
            return 'cast(EXISTS(SELECT 1 FROM bookmarks b WHERE b.row_id=events.__row_id) AS VARCHAR)'
        if index == -3:
            return '(SELECT b.note FROM bookmarks b WHERE b.row_id=events.__row_id)'
        return self.column(index)

    def condition(self, expression):
        return compile_condition(expression, self.expression_column, self.numeric_expression)

    def total_summary(self,view):
        """One filtered aggregate over source rows, independent of grouping/pages."""
        expressions=summary_expressions(self,view,view.total_summaries)
        where,args=self.where(view)
        with self.operation():
            return self.db.execute('SELECT count(*)'+''.join(', '+value for value in expressions)+' FROM events'+where,args).fetchone()

    def validate_view(self, view):
        self.where(view)
        self.order(view)
        if not isinstance(view.tle_fields,dict) or len(view.tle_fields)>len(self.headers):
            raise ValueError('Correspondances TLE invalides')
        for key,value in view.tle_fields.items():
            if not isinstance(key,str) or not key.isdecimal() or not 0<=int(key)<len(self.headers) or not isinstance(value,dict) or set(value)!={'name','field'} or any(not isinstance(v,str) or not 1<=len(v)<=1000 for v in value.values()):
                raise ValueError('Correspondance de colonne TLE invalide')
        import re
        if not isinstance(view.tle_expressions,dict) or len(view.tle_expressions)>64 or any(not isinstance(key,str) or not re.fullmatch(r'[0-9a-f]{64}',key) or not isinstance(value,str) or len(value)>65536 for key,value in view.tle_expressions.items()):
            raise ValueError('Expressions TLE d’origine invalides')
        if type(view.auto_row_height) is not bool or any(type(value) is not int or not 0<=value<=10000 for value in (view.row_height,view.group_row_height,view.header_height)):
            raise ValueError('Hauteur de ligne ou d’en-tête invalide')
        if view.group_footer_mode not in ("hidden","expanded","always") or type(view.show_total_footer) is not bool:
            raise ValueError("Affichage des pieds de page invalide")
        summary_expressions(self,view,view.total_summaries)
        if type(view.expand_all) is not bool:
            raise ValueError("expand_all doit être un booléen")
        if len(view.groups) != len(set(view.groups)):
            raise ValueError("Une colonne ne peut apparaître deux fois dans les groupes")
        for column in view.groups:
            self.column(column)
        from fireblade.core.summaries import group_sort_terms
        group_sort_terms(view)
        for key in view.group_sorts:
            self.column(key.column)
        from fireblade.core.tle_appearance import validate_styles
        validate_styles(view.layout_styles,len(self.headers))
        if type(view.global_rules_enabled) is not bool:
            raise ValueError("L’activation des règles globales doit être un booléen")
        validate_format_rules(view.format_rules, self.expression_column, self.numeric_expression)
        summary_expressions(self, view)
        group_order(self, view, self.column(0))
        for mapping in (view.pinned_columns, view.right_pinned_columns, view.boolean_columns, view.timestamp_columns):
            if not isinstance(mapping, list) or len(mapping) != len(set(mapping)):
                raise ValueError("Liste de colonnes invalide")
            for column in mapping:
                self.column(column)
        if set(view.pinned_columns) & set(view.right_pinned_columns):
            raise ValueError("Une colonne ne peut être épinglée des deux côtés")
        if not isinstance(view.pinned_widths, dict) or any(not isinstance(key, str) or not key.isdecimal()
                or not 0 <= int(key) <= len(self.headers) or type(width) is not int or not 1 <= width <= 1048575
                for key, width in view.pinned_widths.items()):
            raise ValueError("Largeurs de colonnes épinglées invalides")
        for column in view.group_intervals:
            if not isinstance(column, str) or not column.isdecimal():
                raise ValueError("Intervalle de groupement invalide")
            group_expression(self, view, int(column))

    def page_styles(self, view, rows, global_rules=()):
        """Evaluate conditions on already loaded values, without rescanning events."""
        if not view.global_rules_enabled:
            global_rules = ()
        if len(view.format_rules) > 32 or len(global_rules) > 32:
            raise ValueError("32 règles locales et 32 règles globales au maximum")
        rules = list(view.format_rules) + list(global_rules)
        if not rows or not rules:
            return {}
        projections, args, required = [], [], set()
        def collect_columns(condition):
            if isinstance(condition, Filter):
                if condition.operator == 'expression':
                    from fireblade.core.expressions import referenced_columns
                    required.update(referenced_columns(condition.value,self.headers,self.expression_functions))
                else:
                    required.add(condition.column)
            else:
                for child in condition.children:
                    collect_columns(child)
        for rule in rules:
            if rule.target is not None:
                self.column(rule.target)
            sql, values = self.condition(rule.condition) if rule.enabled else ("FALSE", [])
            if rule.enabled:
                collect_columns(rule.condition)
            projections.append("(" + sql + ")")
            args.extend(values)
        from fireblade.core.statistical_rules import source_column,matches as statistical_matches
        stat_columns=sorted({source_column(r) for r in rules if r.enabled and r.statistic and r.statistic not in ('unique','duplicate')})
        required.update(stat_columns)
        for column in stat_columns:projections.append(self.numeric_expression(self.column(column)))
        columns = sorted(i for i in required if i>=0)
        aliases = ["__row_id"] + [self.column(i) for i in columns]
        record = "(cast(? AS BIGINT)" + ", cast(? AS VARCHAR)" * len(columns) + ")"
        values = [value for row in rows for value in [row[0]] + [row[i + 1] for i in columns]]
        with self.operation():
            result = self.db.execute(
                "WITH visible(" + ",".join(aliases) + ") AS (VALUES " + ",".join(record for _ in rows) + ") "
                "SELECT __row_id, " + ", ".join(projections) + " FROM visible AS events", values + args).fetchall()
        numbers={(row[0],column):row[1+len(rules)+i] for row in result for i,column in enumerate(stat_columns)}
        stats=statistical_matches(self,view,rules,rows,numbers)
        return {row[0]:tuple(i for i,matched in enumerate(row[1:1+len(rules)]) if matched and (i not in stats or row[0] in stats[i])) for row in result}

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
                from fireblade.core.timestamps import timestamp_key
                col = timestamp_key(col)
            parts.append(f"{col} {'DESC' if key.descending else 'ASC'} NULLS LAST")
        return " ORDER BY " + ", ".join(parts + ["__row_id"])

    def page(self, view: View, path=(), offset=0, limit=None):
        limit = self.settings.page_size if limit is None else limit
        with self.operation():
            where, args = self.where(view, path)
            limit, offset = max(1, min(limit, self.settings.page_size)), max(0, offset)
            if len(path) < len(view.groups):
                col = group_expression(self, view, view.groups[len(path)])
                summaries = summary_expressions(self, view)
                extra = ", " + ", ".join(summaries) if summaries else ""
                sql = f"SELECT {col}, count(*){extra} FROM events{where} GROUP BY {col} ORDER BY {group_order(self, view, col, group_column=view.groups[len(path)])} LIMIT ? OFFSET ?"
            else:
                order = self.order(view)
                key = (where, tuple(args), order, self._bookmark_revision)
                if (self.settings.cache_sorted_pages and not getattr(self, '_wide_pages', False)
                        and (offset >= self.settings.max_loaded_rows or self._page_cache_key == key)):
                    return self.sorted_page(where, args, order, key, offset, limit)
                sql = f"SELECT * FROM events{where}{order} LIMIT ? OFFSET ?"
            if len(path) >= len(view.groups) and getattr(self, '_wide_pages', False):
                return self._page_columns(view, where, args, offset, limit)
            try:
                return self.db.execute(sql, args + [limit, offset]).fetchall()
            except duckdb.OutOfMemoryException:
                if len(path) < len(view.groups):raise
                self._wide_pages = True
                return self._page_columns(view, where, args, offset, limit)

    def _page_columns(self, view, where, args, offset, limit):
        """Read a wide page in column batches without raising the DB memory budget."""
        ids = [row[0] for row in self.db.execute('SELECT __row_id FROM events'+where+
               self.order(view)+' LIMIT ? OFFSET ?', args+[limit,offset]).fetchall()]
        if not ids:return []
        rows = {row_id:[row_id]+[None]*len(self.headers) for row_id in ids}
        placeholders = ','.join('?' for _ in ids)
        for start in range(0,len(self.headers),32):
            self.check_cancelled()
            end = min(start+32,len(self.headers))
            columns = ','.join(self.column(i) for i in range(start,end))
            for record in self.db.execute(f'SELECT __row_id,{columns} FROM events WHERE __row_id IN ({placeholders})',ids).fetchall():
                rows[record[0]][start+1:end+1] = record[1:]
        return [tuple(rows[row_id]) for row_id in ids]

    def outline_page(self, view, offset=0, limit=None, progress=lambda _: None):
        from fireblade.core.outline import outline_page
        return outline_page(self,view,offset,limit,progress)

    def rows_by_ids(self, ids):
        """Bounded point acquisition. Caller holds operation()/the query lock."""
        ids=list(ids)
        if not ids:return {}
        if len(ids)>self.settings.page_size or any(type(i) is not int for i in ids):
            raise ValueError('Page d’identifiants invalide')
        # The native on-disk ID index avoids rescanning wide evidence payloads
        # for every deep page. It is optional and skipped for tiny budgets or a
        # read-only analysis; failed allocation falls back to a regular scan.
        if not self._source_index_tried and self.settings.cache_sorted_pages and self.settings.memory_mb>=128 and not self._read_only:
            self._source_index_tried=True
            table='__fireblade_source_events' if self.derived else 'events'
            try:
                with self.serial_query_threads():
                    self.db.execute(f'CREATE INDEX IF NOT EXISTS "__fireblade_source_id" ON "{table}"(__row_id)')
            except duckdb.OutOfMemoryException:
                pass
        query='SELECT * FROM events WHERE __row_id IN ('+','.join('?' for _ in ids)+')'
        return {row[0]:row for row in self.db.execute(query,ids).fetchall()}

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
        ids=[row[0] for row in self.db.execute(
            'SELECT __row_id FROM "__timeline_order" WHERE position>? AND position<=? ORDER BY position',
            [offset,offset+limit]).fetchall()]
        records=self.rows_by_ids(ids)
        return [records[i] for i in ids]


    def count(self, view):
        with self.operation():
            where, args = self.where(view)
            return self.db.execute("SELECT count(*) FROM events" + where, args).fetchone()[0]

    def bookmark(self, row_id, note):
        return self.bookmark_many([row_id], note, "remove" if note is None else "replace")

    def bookmark_many(self, row_ids, note="", mode="mark"):
        """One transaction for an explicit selection, never all rows in a group."""
        if mode not in ("mark", "append", "replace", "remove"):
            raise ValueError("Action de signet inconnue")
        ids, seen = [], set()
        for row_id in row_ids:
            if type(row_id) is not int or not 1 <= row_id <= self.info.get("rows", 0):
                raise ValueError("Identifiant d’enregistrement invalide")
            if row_id not in seen:
                ids.append(row_id)
                seen.add(row_id)
                if len(ids) > 100_000:
                    raise ValueError("Sélection limitée à 100000 enregistrements par opération")
        if mode != "remove" and not isinstance(note, str):
            raise ValueError("La note doit être du texte")
        if not ids:
            return 0
        with self.operation(final_check=False):
            try:
                self.db.execute("BEGIN")
                if mode == "remove":
                    self.db.execute("DELETE FROM bookmarks WHERE row_id IN (SELECT unnest(?::BIGINT[]))", [ids])
                else:
                    conflict = {"mark": "DO NOTHING", "replace": "DO UPDATE SET note=excluded.note",
                                "append": "DO UPDATE SET note=CASE WHEN bookmarks.note='' THEN excluded.note WHEN excluded.note='' THEN bookmarks.note ELSE bookmarks.note || chr(10) || excluded.note END"}[mode]
                    self.db.execute("INSERT INTO bookmarks SELECT row_id, ? FROM unnest(?::BIGINT[]) AS chosen(row_id) "
                                    "ON CONFLICT (row_id) " + conflict, ["" if mode == "mark" else note, ids])
                with self.finalizing_transaction():
                    self.check_cancelled()
                    self.db.execute("COMMIT")
                self._bookmark_revision += 1
                return len(ids)
            except BaseException:
                with self.finalizing_transaction():
                    try:
                        self.db.execute("ROLLBACK")
                    except duckdb.TransactionException:
                        pass
                raise

    def bookmarks(self, row_ids=None):
        if row_ids is not None and not row_ids:
            return {}
        with self.operation():
            sql = "SELECT * FROM bookmarks"
            args = []
            if row_ids is not None:
                sql += " WHERE row_id IN (SELECT unnest(?::BIGINT[]))"
                args = [list(row_ids)]
            return dict(self.db.execute(sql, args).fetchall())

    def save_view(self, name, view):
        with self.operation(final_check=False):
            self.db.execute("INSERT OR REPLACE INTO views VALUES (?, ?)", [name, view.to_json()])

    def views(self):
        with self.operation():
            return {name: View.from_json(value) for name, value in self.db.execute("SELECT * FROM views ORDER BY name").fetchall()}

    def export(self, target, view, grouped=False, include_annotations=False, columns=None):
        target = Path(target).resolve()
        from fireblade.core.paths import protected_destination
        if protected_destination(target,(self.path, self.info["path"])):
            raise ValueError("L’export ne peut pas écraser la source ou le dossier d’analyse")
        # Atomic replacement: failed exports never leave an apparently complete CSV.
        temporary = target.with_name(target.name + ".partial")
        if temporary.exists():
            raise ValueError(f"Le fichier temporaire existe déjà : {temporary}")
        with self.operation(final_check=False), self.serial_query_threads():
            where, args = self.where(view)
            selected = list(range(len(self.headers))) if columns is None else list(columns)
            if not selected or len(selected) != len(set(selected)):
                raise ValueError("Choisissez au moins une colonne distincte à exporter")
            cols = ", ".join(self.column(i) for i in selected)
            headers = [self.headers[i] for i in selected]
            if grouped and include_annotations:
                raise ValueError("Les notes s’exportent par enregistrement, pas par comptage de groupes")
            if grouped and view.groups:
                expressions = [group_expression(self, view, i) for i in view.groups]
                cols = ", ".join(expressions)
                ties = ', '.join(col + ' ASC NULLS LAST' for col in expressions)
                summaries = summary_expressions(self, view)
                extra = ", " + ", ".join(summaries) if summaries else ""
                primary = group_order(self, view, expressions[0], include_tie=False)
                sql = f"SELECT {cols}, count(*){extra} FROM events{where} GROUP BY {cols} ORDER BY {primary}, {ties}"
                if view.group_sorts:
                    from fireblade.core.summaries import grouped_export_query
                    sql,args=grouped_export_query(self,view,where,args)
                headers = [self.headers[i] for i in view.groups] + ["Count"] + [f"{s.operation}({self.headers[s.column]})" for s in view.summaries]
            else:
                if include_annotations:
                    cols += ", __row_id, EXISTS(SELECT 1 FROM bookmarks b WHERE b.row_id=events.__row_id), (SELECT b.note FROM bookmarks b WHERE b.row_id=events.__row_id)"
                    headers = headers.copy()
                    existing = {h.casefold() for h in headers}
                    for name in ("Fireblade_SourceRecord", "Fireblade_Bookmarked", "Fireblade_Note"):
                        candidate, number = name, 2
                        while candidate.casefold() in existing:
                            candidate = f"{name}_{number}"
                            number += 1
                        headers.append(candidate)
                        existing.add(candidate.casefold())
                sql = f"SELECT {cols} FROM events{where}{self.order(view)}"
            owns_temporary = False
            try:
                expected=self.db.execute('SELECT count(*) FROM ('+sql+') AS export_coverage',args).fetchone()[0]
                from fireblade.core.coverage import ExportCursor,verify_export
                try:
                    native_cursor = self.db.execute(sql, args)
                except duckdb.OutOfMemoryException:
                    if grouped or view.sorts or view.sort_column is not None:
                        raise
                    from fireblade.core.export_rows import SourceOrderCursor
                    native_cursor = SourceOrderCursor(self, cols, where, args)
                cursor = ExportCursor(native_cursor)
                if target.suffix.lower() == ".xlsx":
                    from fireblade.core.spreadsheets import write_xlsx
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
                if cursor.written!=expected:raise ValueError(f'Export incomplet : {cursor.written} lignes écrites sur {expected} attendues')
                verified=verify_export(temporary,expected,headers,cursor.rows.hexdigest(),xlsx=target.suffix.lower()=='.xlsx',checker=self.check_cancelled)
                sha=verified['sha256']
                self.check_cancelled();os.replace(temporary, target)
                return dict(path=str(target),expected=expected,written=cursor.written,sha256=sha,content_sha256=verified['content_sha256'],verified_rows=verified['verified_rows'],analysis=str(self.path),source=self.info['path'],
                            source_rows=self.info['rows'],available_columns=len(self.headers),view=json.loads(view.to_json()),columns=headers,grouped=bool(grouped and view.groups))
            except BaseException:
                if owns_temporary:
                    temporary.unlink(missing_ok=True)
                raise
