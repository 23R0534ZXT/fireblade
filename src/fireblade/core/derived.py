"""Declarative computed columns persisted as a SQL view over immutable raw rows.

No Python callback per record and no second copy of the source table. SQL comes
only from this registry and the scalar expression compiler, never from plugins.
"""

import re
from fireblade.core.expressions import compile_scalar

FORMATS = {
    "iso": "ISO / date et heure",
    "mdy": "Mois/jour/année",
    "dmy": "Jour/mois/année",
    "invariant": "Dates forensic (ISO, mactime, mois/jour/année)",
    "unix_s": "Unix secondes",
    "unix_ms": "Unix millisecondes",
    "unix_us": "Unix microsecondes",
    "unix_ns": "Unix nanosecondes",
    "filetime": "Windows FILETIME (100 ns depuis 1601)",
    "webkit": "WebKit microsecondes depuis 1601",
    "dotnet": ".NET ticks (100 ns depuis 0001)",
    "ole": "OLE Automation jours",
}


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return "'" + str(value).replace("'", "''") + "'"


def inline_parameters(sql, parameters):
    # Compiler-generated SQL may contain '?' in quoted SQL literals. Replace
    # only placeholders outside quoted strings/identifiers.
    out, at, quoted = [], 0, None
    i = 0
    while i < len(sql):
        char = sql[i]
        if quoted:
            out.append(char)
            if char == quoted:
                if i + 1 < len(sql) and sql[i + 1] == quoted:
                    out.append(char)
                    i += 1
                else:
                    quoted = None
        elif char in ("'", '"'):
            quoted = char
            out.append(char)
        elif char == "?":
            out.append(literal(parameters[at]))
            at += 1
        else:
            out.append(char)
        i += 1
    if at != len(parameters):
        raise ValueError("Expression parameter count differs")
    return "".join(out)


def validate_definition(data):
    allowed = {
        "name",
        "operation",
        "columns",
        "format",
        "timezone",
        "timezone_column",
        "expression",
        "family",
    }
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Définition de colonne dérivée invalide")
    if not isinstance(data.get("name"), str) or not 1 <= len(data["name"]) <= 300:
        raise ValueError("Nom de colonne dérivée invalide")
    op = data.get("operation")
    if op not in ("timestamp", "expression", "category", "macb"):
        raise ValueError("Transformation inconnue")
    if op == "expression":
        if (
            not isinstance(data.get("expression"), str)
            or len(data["expression"]) > 65536
        ):
            raise ValueError("Expression invalide")
    else:
        columns = data.get("columns")
        if (
            not isinstance(columns, list)
            or not 1 <= len(columns) <= 8
            or any(not isinstance(c, str) or not c for c in columns)
        ):
            raise ValueError("Colonnes sources invalides")
    if op == "timestamp":
        if data.get("format", "iso") not in FORMATS:
            raise ValueError("Format temporel inconnu")
        zone = data.get("timezone", "UTC")
        if not isinstance(zone, str) or not re.fullmatch(
            r"[A-Za-z0-9_ /+:.\-]{1,100}", zone
        ):
            raise ValueError("Fuseau horaire invalide")
        if "timezone_column" in data and not isinstance(data["timezone_column"], str):
            raise ValueError("Colonne de fuseau invalide")
    return dict(data)


def timestamp_sql(value, fmt="iso", zone="'UTC'", suppress_input_errors=True):
    if fmt not in FORMATS:
        raise ValueError("Format temporel inconnu")
    # All arithmetic up to the final timestamp uses 128-bit integers. Avoid a
    # DOUBLE intermediary: FILETIME and nanosecond epochs exceed 2**53.
    integer = f"try_cast({value} AS HUGEINT)"
    decimal = f"try_cast({value} AS DECIMAL(38,12))"
    ns = {
        "unix_s": f"try_cast(({decimal})*1000000000 AS HUGEINT)",
        "unix_ms": f"try_cast(({decimal})*1000000 AS HUGEINT)",
        "unix_us": f"({integer})*1000",
        "unix_ns": integer,
        "filetime": f"(({integer})-116444736000000000)*100",
        "webkit": f"(({integer})-11644473600000000)*1000",
        "dotnet": f"(({integer})-621355968000000000)*100",
        "ole": f"try_cast((trunc({decimal})+abs(({decimal})-trunc({decimal}))-25569)*86400000000000 AS HUGEINT)",
    }.get(fmt)
    if ns is None:
        if fmt == "invariant":
            # Some forensic CSV exporters protect timestamps as Excel text.
            # Interpret the wrapper in the derived field, retain raw evidence.
            value = f"trim(trim({value}, '='), '\"')"
        # Preserve the submicrosecond tail that TIMESTAMPTZ itself cannot hold.
        fraction = f"rpad(substr(regexp_extract({value}, '\\.([0-9]+)', 1),1,9),9,'0')"
        formats = {
            "iso": ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"],
            "mdy": ["%m/%d/%Y %H:%M:%S.%f", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"],
            "dmy": ["%d/%m/%Y %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"],
            "invariant": [
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S.%f",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y %I:%M:%S %p",
                "%a %b %d %Y %H:%M:%S",
                "%a %b %d %H:%M:%S %Y",
                "%b %d %Y %H:%M:%S",
            ],
        }[fmt]
        # Strip only digits beyond microseconds before parsing; retain all nine
        # digits separately. Zoned ISO input overrides the selected source zone.
        short = f"regexp_replace(replace(trim({value}),'T',' '), '(\\.[0-9]{{6}})[0-9]+', '\\1')"
        parsed = f"try_strptime({short}, [{','.join(literal(x) for x in formats)}])"
        zoned = f"regexp_matches(trim({value}), '(Z|[+-][0-9]{{2}}:?[0-9]{{2}})$')"
        # Numeric UTC offsets are handled explicitly; ICU accepts IANA names.
        fixed = f"regexp_full_match({zone}, '(UTC|GMT)?[+-][0-9]{{2}}:?[0-9]{{2}}')"
        hours = f"try_cast(regexp_extract({zone}, '([+-])([0-9]{{2}}):?([0-9]{{2}})$',2) AS INTEGER)"
        minutes = f"try_cast(regexp_extract({zone}, '([+-])([0-9]{{2}}):?([0-9]{{2}})$',3) AS INTEGER)"
        sign = f"CASE WHEN contains({zone},'-') THEN -1 ELSE 1 END"
        local = f"CASE WHEN {fixed} THEN CASE WHEN {hours}<=23 AND {minutes}<60 THEN timezone('UTC',{parsed})-({sign})*({hours}*60+{minutes})*INTERVAL 1 MINUTE END ELSE timezone({zone},{parsed}) END"
        stamp = (
            f"CASE WHEN {zoned} THEN try_cast({short} AS TIMESTAMPTZ) ELSE {local} END"
        )

        ns = f"CASE WHEN length(regexp_extract({value}, '\\.([0-9]+)',1))<=9 THEN cast(epoch_us(date_trunc('second',{stamp})) AS HUGEINT)*1000+try_cast({fraction} AS HUGEINT) END"
    # Row-local SQL lambdas factor the nanosecond value without a correlated
    # subquery/hash join. Memory remains bounded for millions of distinct times.
    rendered = """TRY(CASE WHEN __fb_n BETWEEN -62135596800000000000 AND 253402300799999999999
        THEN strftime(make_timestamp(cast(((__fb_n-__fb_r)//1000000000)*1000000 AS BIGINT)), '%Y-%m-%dT%H:%M:%S')
        ||'.'||lpad(cast(__fb_r AS VARCHAR),9,'0')||'Z' END)"""
    source=f'TRY({ns})' if suppress_input_errors else ns
    return f"list_extract(list_transform([{source}], lambda __fb_n: list_extract(list_transform([((__fb_n%1000000000)+1000000000)%1000000000], lambda __fb_r: {rendered}),1)),1)"


def compile_definition(data, headers, column, numeric):
    data = validate_definition(data)

    def index(name):
        matches = [i for i, h in enumerate(headers) if h.casefold() == name.casefold()]
        if len(matches) != 1:
            raise ValueError(f"Colonne source absente ou ambiguë : {name}")
        return matches[0]

    op = data["operation"]
    if op == "expression":
        scalar = compile_scalar(data["expression"], headers, column, numeric)
        return f"cast(({inline_parameters(scalar.sql, scalar.parameters)}) AS VARCHAR)"
    cols = [column(index(c)) for c in data["columns"]]
    if op == "timestamp":
        value = cols[0] if len(cols) == 1 else "concat_ws(' '," + ",".join(cols) + ")"
        from fireblade.core.windows_zones import WINDOWS_ZONES

        if data.get("timezone_column"):
            zone = column(index(data["timezone_column"]))
            mappings = (
                "MAP {"
                + ",".join(
                    literal(k) + ":" + literal(v) for k, v in WINDOWS_ZONES.items()
                )
                + "}"
            )
            zone = f"coalesce(map_extract_value({mappings},{zone}),nullif({zone},''),'UTC')"
        else:
            selected = data.get("timezone", "UTC")
            zone = literal(WINDOWS_ZONES.get(selected, selected))

        return timestamp_sql(value, data.get("format", "iso"), zone)
    if op == "macb":
        col = cols[0]
        return (
            "("
            + " + ".join(
                f"CASE WHEN contains(lower({col}),'{c}') THEN {n} ELSE 0 END"
                for c, n in zip("macb", (1, 2, 4, 8))
            )
            + ")::VARCHAR"
        )
    from fireblade.core.timeline_categories import category_sql

    return category_sql(data.get("family", "plaso"), cols)
