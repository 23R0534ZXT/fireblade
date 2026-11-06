"""Open received DuckDB analyses without granting SQL access to host files.

Only an empty, object-free database can receive the explicit CSV import reader.
Existing analyses keep external access disabled, including portable import.
"""
import json
import duckdb

from fireblade.core.paths import same_file

CONFIG = {'autoload_known_extensions': False, 'autoinstall_known_extensions': False}


def connect_analysis(path, *, read_only=False, allow_empty_import=False):
    connection = duckdb.connect(str(path), read_only=read_only, config=CONFIG)
    try:
        # SET is executed before any query against database-supplied objects.
        # Keep connect() options identical for simultaneous connections to a DB.
        connection.execute('SET enable_external_access=false')
        name = next(row[1] for row in connection.execute('PRAGMA database_list').fetchall()
                    if row[2] and same_file(path, row[2]))
        tables = connection.execute('SELECT schema_name,table_name FROM system.main.duckdb_tables() '
                                    'WHERE database_name=? AND NOT internal AND NOT temporary', [name]).fetchall()
        views = connection.execute('SELECT schema_name,view_name FROM system.main.duckdb_views() '
                                   'WHERE database_name=? AND NOT internal AND NOT temporary', [name]).fetchall()
        macros = connection.execute("SELECT function_name FROM system.main.duckdb_functions() "
                                    "WHERE database_name=? AND function_type IN ('macro','table_macro') AND NOT internal",
                                    [name]).fetchall()
        if not tables and not views and not macros:
            if allow_empty_import and not read_only:
                connection.close()
                # There is no stored SQL to execute. Input paths are selected by
                # the importer; access is revoked as soon as import commits.
                return duckdb.connect(str(path), config=CONFIG)
            return connection
        if macros or any(schema != 'main' for schema, _ in tables+views):
            raise ValueError('Analyse contenant des objets SQL non autorisés')
        tables = {table for _, table in tables}; views = {view for _, view in views}
        if 'metadata' not in tables:
            raise ValueError('Métadonnées d’analyse absentes ou non stockées dans une table')
        columns = connection.execute('SELECT table_name,column_name,data_type FROM system.main.duckdb_columns() '
                                     'WHERE database_name=? AND schema_name=\'main\' ORDER BY column_index', [name]).fetchall()
        schema = {}
        for table, column, kind in columns:schema.setdefault(table, []).append((column, kind))
        if schema.get('metadata') != [('key','VARCHAR'),('value','VARCHAR')]:
            raise ValueError('Schéma des métadonnées d’analyse invalide')
        rows = connection.execute("SELECT key,value FROM main.metadata WHERE key IN ('source','derived')").fetchall()
        if any(not isinstance(value, str) or len(value)>16*1024**2 for _, value in rows):
            raise ValueError('Métadonnées d’analyse trop volumineuses')
        values = dict(rows)
        info = json.loads(values['source']); derived = json.loads(values.get('derived','[]'))
        headers = info['headers']
        if not isinstance(headers, list) or not headers or any(not isinstance(header, str) for header in headers):
            raise ValueError('Colonnes d’analyse invalides')
        if not isinstance(derived, list) or len(derived)>64:
            raise ValueError('Colonnes dérivées invalides')
        from fireblade.core.derived import validate_definition
        for definition in derived:validate_definition(definition)
        base = '__fireblade_source_events' if derived else 'events'
        if tables != {'metadata','bookmarks','views',base} or views != ({'events'} if derived else set()):
            raise ValueError('Analyse contenant des tables ou vues SQL non autorisées')
        expected = [('__row_id','BIGINT')]+[(f'c{i}','VARCHAR') for i in range(len(headers))]
        # Analyses written before 0.3.1 keep their row-level notes only; the
        # per-cell table is created when such a file is opened and migrated.
        notes_schemas = ([('row_id','BIGINT'),('note','VARCHAR')],
                         [('row_id','BIGINT'),('column_id','INTEGER'),('note','VARCHAR')])
        if (schema.get(base) != expected or schema.get('bookmarks') not in notes_schemas
                or schema.get('views') != [('name','VARCHAR'),('value','VARCHAR')]):
            raise ValueError('Schéma des tables d’analyse invalide')
        # Derived views may use approved .NET UDFs restored by Case after opening.
        # External access stays disabled when those views are subsequently bound.
        return connection
    except BaseException:
        connection.close()
        raise
