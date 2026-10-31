"""Bound, typed scalar expressions for grid filters and conditional formatting.

User text is parsed into immutable nodes. Only this module's operator/function
registry emits SQL; literals are parameters and identifiers come from the schema.
"""

from dataclasses import dataclass
from functools import lru_cache
import re

TOKEN = re.compile(
    r"""\s*(?:(\[(?:[^\]]|\]\])*\])|('(?:[^']|'')*'|"(?:[^"]|"")*")|(#(?:[^#]+)#)|(\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-z_]\w*)|(>=|<=|<>|!=|==|&&|\|\||[=<>(),+*/%&|^!~-]))"""
)


@dataclass(frozen=True)
class Node:
    kind: str
    value: object = None
    children: tuple = ()


class Parser:
    def __init__(self, text, headers):
        if not isinstance(text, str) or len(text) > 65536:
            raise ValueError("Expression limitée à 64 Ko")
        self.headers = headers
        self.tokens = []
        self.at = 0
        offset = 0
        text = text.strip()
        while offset < len(text):
            match = TOKEN.match(text, offset)
            if not match:
                raise ValueError(f"Syntaxe inconnue au caractère {offset + 1}")
            kind = next(i for i, x in enumerate(match.groups()) if x is not None)
            self.tokens.append((kind, match.group(kind + 1)))
            offset = match.end()
            if len(self.tokens) > 4096:
                raise ValueError("Expression trop complexe")

    def peek(self, value=None):
        if self.at >= len(self.tokens):
            return False
        return (
            self.tokens[self.at][1].casefold() == value.casefold()
            if value
            else self.tokens[self.at]
        )

    def take(self, expected=None):
        if not self.peek():
            raise ValueError("Expression incomplète")
        token = self.tokens[self.at]
        if expected is not None and token[1].casefold() != expected.casefold():
            raise ValueError(f"{expected} attendu")
        self.at += 1
        return token

    def expression(self, minimum=0, depth=0):
        if depth > 24:
            raise ValueError("24 niveaux au maximum")
        kind, text = self.take()
        word = text.casefold()
        if word in ("not", "!", "+", "-", "~"):
            left = Node(
                "unary",
                word,
                (self.expression(25 if word in ("not", "!") else 70, depth + 1),),
            )
        elif text == "(":
            left = self.expression(0, depth + 1)
            self.take(")")
        elif kind == 0:
            name = text[1:-1].replace("]]", "]")
            exact = [i for i, h in enumerate(self.headers) if h == name]
            folded = [
                i for i, h in enumerate(self.headers) if h.casefold() == name.casefold()
            ]
            matches = exact or folded
            virtual = {
                "line": -1,
                "tag": -2,
                "note": -3,
                "fireblade_sourcerecord": -1,
                "fireblade_bookmarked": -2,
                "fireblade_note": -3,
            }
            if not matches and name.casefold() in virtual:
                left = Node("column", virtual[name.casefold()])
            elif len(matches) == 1:
                left = Node("column", matches[0])
            else:
                raise ValueError(f"Colonne absente ou ambiguë : {name}")
        elif kind in (1, 2, 3):
            value = (
                text[1:-1].replace(text[0] * 2, text[0])
                if kind == 1
                else text[1:-1]
                if kind == 2
                else text
            )
            left = Node({1: "text", 2: "date", 3: "number"}[kind], value)
        elif word in ("true", "false", "null"):
            left = Node("null") if word == "null" else Node("boolean", word == "true")
        elif kind == 4:
            self.take("(")
            args = []
            if not self.peek(")"):
                while True:
                    args.append(self.expression(0, depth + 1))
                    if not self.peek(","):
                        break
                    self.take()
            self.take(")")
            left = Node("function", word, tuple(args))
        else:
            raise ValueError(f"Expression inattendue : {text}")
        precedence = {
            "or": 10,
            "||": 10,
            "xor": 15,
            "and": 20,
            "&&": 20,
            "=": 30,
            "==": 30,
            "!=": 30,
            "<>": 30,
            ">": 30,
            ">=": 30,
            "<": 30,
            "<=": 30,
            "like": 30,
            "in": 30,
            "between": 30,
            "is": 30,
            "not": 30,
            "|": 35,
            "^": 36,
            "&": 37,
            "+": 40,
            "-": 40,
            "*": 50,
            "/": 50,
            "%": 50,
        }
        while self.peek():
            operator = self.peek()[1].casefold()
            power = precedence.get(operator, -1)
            if power < minimum:
                break
            self.take()
            negate = False
            if operator == "not":
                operator = self.take()[1].casefold()
                negate = True
                if operator not in ("in", "between", "like"):
                    raise ValueError("Not doit précéder In, Between ou Like")
            if operator == "in":
                self.take("(")
                args = [left]
                while True:
                    args.append(self.expression(0, depth + 1))
                    if not self.peek(","):
                        break
                    self.take()
                self.take(")")
                left = Node("in", None, tuple(args))
            elif operator == "between":
                low = self.expression(31, depth + 1)
                self.take("and")
                high = self.expression(31, depth + 1)
                left = Node("between", None, (left, low, high))
            elif operator == "is":
                negative = bool(self.peek("not"))
                if negative:
                    self.take()
                self.take("null")
                left = Node("function", "isnull", (left,))
                if negative:
                    left = Node("unary", "not", (left,))
            else:
                right = self.expression(power + 1, depth + 1)
                canonical = {"&&": "and", "||": "or"}.get(operator, operator)
                if canonical in ("and", "or"):
                    children = (
                        left.children + (right,)
                        if left.kind == "logic" and left.value == canonical
                        else (left, right)
                    )
                    left = Node("logic", canonical, children)
                else:
                    left = Node("binary", operator, (left, right))
            if negate:
                left = Node("unary", "not", (left,))
        return left


@lru_cache(maxsize=256)
def parse(text, headers):
    parser = Parser(text, headers)
    if not parser.tokens:
        return Node("boolean", True)
    result = parser.expression()
    if parser.peek():
        raise ValueError("Texte supplémentaire après la condition")
    return result


def referenced_columns(text, headers):
    result = set()
    pending = [parse(text, tuple(headers))]
    while pending:
        node = pending.pop()
        if node.kind == "column":
            result.add(node.value)
        pending.extend(node.children)
    return result


@dataclass
class Value:
    sql: str
    kind: str
    parameters: list
    date_ns: "Value | None" = None

    def __post_init__(self):
        if len(self.sql) > 1024 * 1024 or len(self.parameters) > 4096:
            raise ValueError("Expression compilée trop volumineuse")


class Compiler:
    def __init__(self, column, numeric):
        self.column, self.numeric = column, numeric
        self.nodes = 0

    def nanoseconds(self, value):
        if value.date_ns is not None:
            return value.date_ns
        if value.kind == "null":
            return Value("NULL::HUGEINT", "number", [])
        from fireblade.core.timestamps import timestamp_key

        return Value(
            timestamp_key(f"cast({value.sql} AS VARCHAR)"),
            "number",
            value.parameters * 2,
        )

    def date_value(self, ns):
        from fireblade.core.derived import timestamp_sql

        return Value(
            timestamp_sql(f"cast(({ns.sql}) AS VARCHAR)", "unix_ns"),
            "date",
            ns.parameters,
            ns,
        )

    def cast(self, value, kind):
        if kind == "date":
            return Value(
                f"try_cast({value.sql} AS TIMESTAMPTZ)",
                "date",
                value.parameters,
                self.nanoseconds(value),
            )
        if kind == "text" and value.kind == "date":
            ns = self.nanoseconds(value)
            date = self.date_value(ns)
            return Value(date.sql, "text", date.parameters, ns)
        if kind == "boolean":
            return Value(
                f"coalesce(try_cast(({value.sql}) AS BOOLEAN),FALSE)",
                "boolean",
                value.parameters,
            )
        if value.kind == kind:
            return value
        if kind == "number":
            sql = f"try_cast({value.sql} AS DECIMAL(38,10))"
        elif kind == "date":
            sql = f"try_cast({value.sql} AS TIMESTAMPTZ)"
        elif kind == "boolean":
            sql = f"coalesce(try_cast({value.sql} AS BOOLEAN),FALSE)"
        else:
            sql = f"cast({value.sql} AS VARCHAR)"
        return Value(sql, kind, value.parameters)

    def emit(self, node, depth=0):
        self.nodes += 1
        if self.nodes > 1024 or depth > 24:
            raise ValueError("Expression limitée à 1024 nœuds et 24 niveaux")
        if node.kind == "column":
            return Value(self.column(node.value), "column", [])
        if node.kind == "null":
            return Value("NULL", "null", [])
        if node.kind in ("text", "number", "date", "boolean"):
            sql = {
                "text": "?",
                "number": "cast(? AS DECIMAL(38,10))",
                "date": "cast(? AS TIMESTAMPTZ)",
                "boolean": "cast(? AS BOOLEAN)",
            }[node.kind]
            value = Value(sql, node.kind, [node.value])
            if node.kind == "date":
                value.date_ns = self.nanoseconds(Value("?", "text", [node.value]))
            return value
        args = [self.emit(child, depth + 1) for child in node.children]
        if node.kind == "unary":
            value = args[0]
            if node.value in ("not", "!"):
                value = self.cast(value, "boolean")
                return Value(f"NOT ({value.sql})", "boolean", value.parameters)
            value = self.cast(value, "number")
            sql = (
                f"~cast({value.sql} AS HUGEINT)"
                if node.value == "~"
                else f"{node.value}({value.sql})"
            )
            return Value(sql, "number", value.parameters)
        if node.kind == "logic":
            args = [self.cast(a, "boolean") for a in args]
            return Value(
                "("
                + (" AND " if node.value == "and" else " OR ").join(a.sql for a in args)
                + ")",
                "boolean",
                [p for a in args for p in a.parameters],
            )
        if node.kind == "binary":
            return self.binary(node.value, *args)
        if node.kind == "in":
            left = args[0]
            if (
                len(left.sql) * len(args) > 1024 * 1024
                or len(left.parameters) * len(args) > 4096
            ):
                raise ValueError("Liste In trop volumineuse")
            branches = [self.binary("=", left, right) for right in args[1:]]
            return Value(
                "(" + " OR ".join(f"({b.sql})" for b in branches) + ")",
                "boolean",
                [p for b in branches for p in b.parameters],
            )
        if node.kind == "between":
            a = self.binary(">=", args[0], args[1])
            b = self.binary("<=", args[0], args[2])
            return Value(
                f"({a.sql}) AND ({b.sql})", "boolean", a.parameters + b.parameters
            )
        if node.kind == "function":
            return self.function(node.value, args)
        raise ValueError("Nœud d’expression invalide")

    def binary(self, op, left, right):
        if op in ("and", "&&", "or", "||", "xor"):
            left, right = self.cast(left, "boolean"), self.cast(right, "boolean")
            operator = {"and": "AND", "&&": "AND", "or": "OR", "||": "OR", "xor": "<>"}[
                op
            ]
        elif op == "like":
            left, right = self.cast(left, "text"), self.cast(right, "text")
            operator = "ILIKE"
        elif op in ("=", "==", "!=", "<>", ">", ">=", "<", "<="):
            if left.kind == "null" or right.kind == "null":
                if op not in ("=", "==", "!=", "<>"):
                    raise ValueError("NULL doit être comparé par égalité")
                value = right if left.kind == "null" else left
                return Value(
                    f"{value.sql} IS {'NOT ' if op in ('!=', '<>') else ''}NULL",
                    "boolean",
                    value.parameters,
                )
            kind = (
                "date"
                if "date" in (left.kind, right.kind)
                else "number"
                if "number" in (left.kind, right.kind)
                else "boolean"
                if "boolean" in (left.kind, right.kind)
                else "text"
            )
            left, right = (
                (self.nanoseconds(left), self.nanoseconds(right))
                if kind == "date"
                else (self.cast(left, kind), self.cast(right, kind))
            )
            operator = "=" if op == "==" else "<>" if op == "!=" else op
        elif op == "+" and "text" in (left.kind, right.kind):
            left, right = self.cast(left, "text"), self.cast(right, "text")
            return Value(
                f"({left.sql}) || ({right.sql})",
                "text",
                left.parameters + right.parameters,
            )
        else:
            left, right = self.cast(left, "number"), self.cast(right, "number")
            if op not in ("+", "-", "*", "/", "%", "&", "|", "^"):
                raise ValueError("Opérateur inconnu")
            if op in ("&", "|", "^"):
                a, b = (
                    f"try_cast({left.sql} AS HUGEINT)",
                    f"try_cast({right.sql} AS HUGEINT)",
                )
                sql = f"xor({a},{b})" if op == "^" else f"({a}) {op} ({b})"
            else:
                sql = f"({left.sql}) {op} " + (
                    f"nullif(({right.sql}),0)" if op in ("/", "%") else f"({right.sql})"
                )
            return Value(f"TRY({sql})", "number", left.parameters + right.parameters)
        return Value(
            f"({left.sql}) {operator} ({right.sql})",
            "boolean",
            left.parameters + right.parameters,
        )

    def function(self, name, args):
        def arity(low, high=None):
            if not low <= len(args) <= (low if high is None else high):
                raise ValueError(f"Nombre d’arguments invalide pour {name}")

        def result(sql, kind="text", values=None):
            return Value(
                sql,
                kind,
                [p for a in (args if values is None else values) for p in a.parameters],
            )

        def typed(kind):
            return [self.cast(a, kind) for a in args]

        names = {
            "toupper": "upper",
            "tolower": "lower",
            "length": "len",
            "tostring": "tostr",
            "tointeger": "toint",
            "todouble": "tofloat",
            "tolong": "toint",
            "todecimal": "tofloat",
            "isnullorempty": "isempty",
            "regexismatch": "matches",
            "regexmatch": "matches",
            "ismatch": "matches",
            "ceiling": "ceil",
            "power": "pow",
            "tobyte": "toint",
            "toint16": "toint",
            "toint32": "toint",
            "toint64": "toint",
            "toint128": "toint",
            "tosingle": "tofloat",
            "getdayofmonth": "getday",
            "addticks": "addtick",
        }
        name = names.get(name, name)
        if name in ("contains", "startswith", "endswith", "matches", "like"):
            arity(2)
            args = typed("text")
            a, b = [x.sql for x in args]
            sql = (
                f"regexp_matches({a},{b})"
                if name == "matches"
                else f"({a} ILIKE {b})"
                if name == "like"
                else f"{ {'contains': 'contains', 'startswith': 'starts_with', 'endswith': 'ends_with'}[name] }(lower({a}),lower({b}))"
            )
            return result(sql, "boolean")
        if name in ("upper", "lower", "trim", "ltrim", "rtrim", "reverse"):
            arity(1)
            args = typed("text")
            return result(f"{name}({args[0].sql})")
        if name == "len":
            arity(1)
            args = typed("text")
            return result(f"length({args[0].sql})", "number")
        if name == "isempty":
            arity(1)
            args = typed("text")
            a = args[0]
            return result(f"coalesce({a.sql},'')=''", "boolean")
        if name in ("isnull", "coalesce"):
            arity(1, 32)
            if len(args) == 1:
                return (
                    result(f"{args[0].sql} IS NULL", "boolean")
                    if name == "isnull"
                    else args[0]
                )
            kind = next(
                (a.kind for a in args if a.kind not in ("column", "null")), "text"
            )
            if kind == "date":
                args = [self.nanoseconds(a) for a in args]
                return self.date_value(
                    result("coalesce(" + ",".join(a.sql for a in args) + ")", "number")
                )
            args = [self.cast(a, kind) for a in args]
            return result("coalesce(" + ",".join(a.sql for a in args) + ")", kind)
        if name in ("iif", "if"):
            arity(3, 31)
            if len(args) % 2 != 1:
                raise ValueError(
                    "Iif nécessite des paires condition/valeur et une valeur finale"
                )
            branches = args[1::2] + [args[-1]]
            kind = next(
                (a.kind for a in branches if a.kind not in ("column", "null")), "text"
            )
            clauses = []
            ordered = []
            for i in range(0, len(args) - 1, 2):
                condition = self.cast(args[i], "boolean")
                value = (
                    self.nanoseconds(args[i + 1])
                    if kind == "date"
                    else self.cast(args[i + 1], kind)
                )
                clauses.append(f"WHEN {condition.sql} THEN {value.sql}")
                ordered.extend([condition, value])
            default = (
                self.nanoseconds(args[-1])
                if kind == "date"
                else self.cast(args[-1], kind)
            )
            ordered.append(default)
            value = result(
                "CASE " + " ".join(clauses) + f" ELSE {default.sql} END",
                "number" if kind == "date" else kind,
                ordered,
            )
            return self.date_value(value) if kind == "date" else value
        if name in ("tostr", "toint", "tofloat", "todatetime", "todate", "datetime"):
            arity(1)
            if name in ("todatetime", "todate", "datetime"):
                return self.cast(args[0], "date")
            value = self.cast(args[0], "text" if name == "tostr" else "number")
            return Value(
                f"try_cast({value.sql} AS HUGEINT)" if name == "toint" else value.sql,
                "number" if name != "tostr" else "text",
                value.parameters,
            )
        if name in ("concat", "concatws"):
            arity(1, 32)
            args = typed("text")
            return result(
                "concat"
                + ("_ws" if name == "concatws" else "")
                + "("
                + ",".join(a.sql for a in args)
                + ")"
            )
        if name == "substring":
            arity(2, 3)
            args = [self.cast(args[0], "text")] + [
                self.cast(a, "number") for a in args[1:]
            ]
            return result(
                f"substring({args[0].sql},cast({args[1].sql} AS BIGINT)+1"
                + (
                    f",greatest(0,cast({args[2].sql} AS BIGINT))"
                    if len(args) == 3
                    else ""
                )
                + ")"
            )
        if name in ("ascii", "char"):
            arity(1)
            args = typed("text" if name == "ascii" else "number")
            argument = (
                args[0].sql
                if name == "ascii"
                else f"try_cast({args[0].sql} AS INTEGER)"
            )
            return result(
                f"TRY({'ascii' if name == 'ascii' else 'chr'}({argument}))",
                "number" if name == "ascii" else "text",
            )
        if name in ("insert", "remove"):
            arity(3 if name == "insert" else 2, 3)
            text = self.cast(args[0], "text")
            position = self.cast(args[1], "number")
            end = (
                self.cast(args[2], "number")
                if len(args) == 3 and name == "remove"
                else None
            )
            addition = self.cast(args[2], "text") if name == "insert" else None
            # Repeated SQL operands also repeat their bound parameters.
            start = (
                f"substring({text.sql},1,greatest(0,cast({position.sql} AS BIGINT)))"
            )
            if name == "insert":
                return result(
                    f"{start} || {addition.sql} || substring({text.sql},greatest(0,cast({position.sql} AS BIGINT))+1)",
                    values=[text, position, addition, text, position],
                )
            if end:
                return result(
                    f"{start} || substring({text.sql},greatest(0,cast({position.sql} AS BIGINT))+greatest(0,cast({end.sql} AS BIGINT))+1)",
                    values=[text, position, text, position, end],
                )
            return result(start, values=[text, position])
        if name in ("replace", "padleft", "padright"):
            arity(2 if name.startswith("pad") else 3, 3)
            args = [
                self.cast(args[0], "text"),
                self.cast(args[1], "number" if name.startswith("pad") else "text"),
            ] + [self.cast(a, "text") for a in args[2:]]
            if name == "replace":
                return result("replace(" + ",".join(a.sql for a in args) + ")")
            fill = args[2].sql if len(args) == 3 else "' '"
            return result(
                f"{'lpad' if name == 'padleft' else 'rpad'}({args[0].sql},cast(greatest(length({args[0].sql}),least(1000000,greatest(0,cast({args[1].sql} AS INTEGER)))) AS INTEGER),{fill})",
                values=[args[0], args[0], args[1]] + args[2:],
            )
        if name in ("charindex", "indexof"):
            arity(2)
            args = typed("text")
            a, b = args
            return result(f"strpos({b.sql},{a.sql})-1", "number", [b, a])
        if name in (
            "abs",
            "floor",
            "ceil",
            "sqrt",
            "exp",
            "ln",
            "log10",
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "sign",
        ):
            arity(1)
            args = typed("number")
            return result(f"TRY({name}({args[0].sql}))", "number")
        if name in ("round", "pow", "atan2"):
            arity(1 if name == "round" else 2, 2)
            args = typed("number")
            parts = [a.sql for a in args]
            if name == "round" and len(parts) == 2:
                parts[1] = f"cast({parts[1]} AS INTEGER)"
            return result("TRY(" + name + "(" + ",".join(parts) + "))", "number")
        if name in ("log", "bigmul"):
            arity(1 if name == "log" else 2, 2)
            args = typed("number")
            if name == "bigmul":
                return result(f"TRY({args[0].sql}*{args[1].sql})", "number")
            return result(
                f"TRY(ln({args[0].sql})"
                + (f"/nullif(ln({args[1].sql}),0)" if len(args) == 2 else "")
                + ")",
                "number",
            )
        if name in ("min", "max"):
            arity(2, 32)
            args = typed("number")
            return result(
                ("least" if name == "min" else "greatest")
                + "("
                + ",".join(a.sql for a in args)
                + ")",
                "number",
            )
        if name in (
            "now",
            "utcnow",
            "today",
            "localdatetimenow",
            "localdatetimetoday",
            "localdatetimethisday",
            "localdatetimethismonth",
            "localdatetimethisyear",
            "localdatetimeyesterday",
            "localdatetimetomorrow",
            "localdatetimelastmonth",
            "localdatetimenextmonth",
            "localdatetimelastyear",
            "localdatetimenextyear",
        ):
            arity(0)
            sql = (
                "current_timestamp"
                if name in ("now", "utcnow", "localdatetimenow")
                else "date_trunc('day',current_timestamp)"
            )
            if "month" in name:
                sql = "date_trunc('month',current_timestamp)"
            if "year" in name:
                sql = "date_trunc('year',current_timestamp)"
            if "yesterday" in name:
                sql += "-INTERVAL 1 DAY"
            if "tomorrow" in name:
                sql += "+INTERVAL 1 DAY"
            if "lastmonth" in name:
                sql += "-INTERVAL 1 MONTH"
            if "nextmonth" in name:
                sql += "+INTERVAL 1 MONTH"
            if "lastyear" in name:
                sql += "-INTERVAL 1 YEAR"
            if "nextyear" in name:
                sql += "+INTERVAL 1 YEAR"
            return result(sql, "date")
        parts = {
            "getyear": "year",
            "getmonth": "month",
            "getday": "day",
            "getdayofweek": "dow",
            "getdayofyear": "doy",
            "gethour": "hour",
            "getminute": "minute",
            "getsecond": "second",
            "getmillisecond": "millisecond",
        }
        if name in parts:
            arity(1)
            args = typed("date")
            sql = f"date_part('{parts[name]}',{args[0].sql})"
            if name == "getmillisecond":
                sql = "(" + sql + " % 1000)"
            return result(sql, "number")
        if name == "getdate":
            arity(1)
            args = typed("date")
            return result(f"date_trunc('day',{args[0].sql})", "date")
        for prefix in ("add", "datediff"):
            if name.startswith(prefix) and name[len(prefix) :].rstrip("s") in (
                "second",
                "minute",
                "hour",
                "day",
                "month",
                "year",
                "millisecond",
                "microsecond",
                "nanosecond",
                "tick",
            ):
                arity(2)
                unit = name[len(prefix) :].rstrip("s")
                if prefix == "add":
                    base = self.nanoseconds(args[0])
                    amount = self.cast(args[1], "number")
                    scales = {
                        "tick": 100,
                        "microsecond": 1000,
                        "nanosecond": 1,
                        "millisecond": 1000000,
                        "second": 1000000000,
                        "minute": 60000000000,
                        "hour": 3600000000000,
                        "day": 86400000000000,
                    }
                    if unit in scales:
                        ns = Value(
                            f"TRY(({base.sql})+try_cast(({amount.sql})*{scales[unit]} AS HUGEINT))",
                            "number",
                            base.parameters + amount.parameters,
                        )
                    else:
                        # Bind the source ns once, retaining the submicrosecond
                        # tail while ICU performs month/year calendar arithmetic.
                        tail = "((__fb_cal%1000)+1000)%1000"
                        stamp = f"make_timestamptz(cast((__fb_cal-({tail}))//1000 AS BIGINT))"
                        body = f"TRY(cast(epoch_us({stamp}+({amount.sql})*INTERVAL 1 {unit.upper()}) AS HUGEINT)*1000+({tail}))"
                        ns = Value(
                            f"list_extract(list_transform([({base.sql})],lambda __fb_cal:{body}),1)",
                            "number",
                            base.parameters + amount.parameters,
                        )
                    return self.date_value(ns)
                if unit in ("tick", "microsecond", "nanosecond"):
                    left, right = self.nanoseconds(args[0]), self.nanoseconds(args[1])
                    scale = {"tick": 100, "microsecond": 1000, "nanosecond": 1}[unit]
                    return Value(
                        f"TRY((({right.sql})-({left.sql}))//{scale})",
                        "number",
                        right.parameters + left.parameters,
                    )
                args = typed("date")
                return result(
                    f"date_diff('{unit}',{args[0].sql},{args[1].sql})", "number"
                )
        predicates = {
            "istoday": ("day", 0),
            "isyesterday": ("day", -1),
            "istomorrow": ("day", 1),
            "isthismonth": ("month", 0),
            "isthisyear": ("year", 0),
            "islastmonth": ("month", -1),
            "isnextmonth": ("month", 1),
            "islastyear": ("year", -1),
            "isnextyear": ("year", 1),
        }
        if name in predicates:
            arity(1)
            unit, offset = predicates[name]
            args = typed("date")
            return result(
                f"date_trunc('{unit}',{args[0].sql})=date_trunc('{unit}',current_timestamp)+INTERVAL '{offset}' {unit.upper()}",
                "boolean",
            )
        raise ValueError(f"Fonction non prise en charge : {name}")


def compile_scalar(text, headers, column, numeric):
    compiler = Compiler(column, numeric)
    value = compiler.emit(parse(text, tuple(headers)))
    return (
        compiler.date_value(compiler.nanoseconds(value))
        if value.kind == "date"
        else value
    )


def compile_expression(text, headers, column, numeric):
    compiler = Compiler(column, numeric)
    value = compiler.cast(compiler.emit(parse(text, tuple(headers))), "boolean")
    return value.sql, value.parameters
