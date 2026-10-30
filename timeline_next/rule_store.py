"""User-wide format rules, bound to column names rather than file positions."""
import copy
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .conditions import validate_format_rules
from .models import Filter, View

MAX_BYTES = 2 * 1024 * 1024


def atoms(condition):
    if isinstance(condition, Filter):
        yield condition
    else:
        for child in condition.children:
            yield from atoms(child)


@dataclass
class RuleBook:
    headers: list[str] = field(default_factory=list)
    rules: list = field(default_factory=list)

    def column(self, index):
        if type(index) is not int or not 0 <= index < len(self.headers):
            raise ValueError("Colonne invalide dans les règles globales")
        return f'"c{index}"'

    def validate(self):
        if (len(self.headers) > 2048 or any(not isinstance(h, str) or not h or len(h) > 4096 for h in self.headers)
                or len(set(self.headers)) != len(self.headers)):
            raise ValueError("Noms de colonnes globaux invalides ou dupliqués")
        validate_format_rules(self.rules, self.column, lambda col: f"try_cast({col} AS DECIMAL(38,10))")
        operands = set()
        count = 0
        for rule in self.rules:
            for condition in atoms(rule.condition):
                count += 1
                if count > 1024:
                    raise ValueError("1024 conditions au maximum dans les règles globales")
                kind = ("regex" if condition.operator == "regex" else
                        "number" if condition.operator in ("gt", "ge", "lt", "le") else
                        "date" if condition.operator in ("after", "before") else None)
                if kind:
                    operands.add((kind, condition.value))
        if operands:
            import duckdb
            with duckdb.connect(":memory:", config={"memory_limit": "16MB", "threads": "1"}) as db:
                for kind, value in operands:
                    sql = {"regex": "SELECT regexp_matches('', ?)", "number": "SELECT cast(? AS DECIMAL(38,10))", "date": "SELECT cast(? AS TIMESTAMP)"}[kind]
                    try:
                        db.execute(sql, [value]).fetchone()
                    except duckdb.Error as exc:
                        raise ValueError(f"Valeur de règle {kind} invalide : {value}") from exc

    def to_bytes(self):
        self.validate()
        value = dict(format="fireblade-global-rules", version=1, headers=self.headers,
                     rules=json.loads(View(format_rules=self.rules).to_json())["format_rules"])
        data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        if len(data) > MAX_BYTES:
            raise ValueError("Les règles globales sont limitées à 2 Mo")
        return data

    @classmethod
    def from_bytes(cls, data):
        if len(data) > MAX_BYTES:
            raise ValueError("Les règles globales sont limitées à 2 Mo")
        try:
            value = json.loads(data.decode("utf-8-sig"))
            if value.get("format") != "fireblade-global-rules" or value.get("version") != 1:
                raise ValueError("Format de règles globales inconnu")
            if not isinstance(value.get("headers"), list) or not isinstance(value.get("rules"), list):
                raise ValueError("Liste de colonnes ou de règles invalide")
            rules = View.from_json(json.dumps(dict(format_rules=value["rules"]))).format_rules
            book = cls(value["headers"], rules)
            book.validate()
            return book
        except (KeyError, TypeError, AttributeError, UnicodeError, RecursionError) as exc:
            raise ValueError("Fichier de règles globales invalide") from exc

    def adapt(self, headers):
        """Skip a whole rule when a referenced field or its target is absent."""
        exact = {name: i for i, name in enumerate(headers)}
        folded = {}
        for i, name in enumerate(headers):
            folded.setdefault(name.casefold(), []).append(i)
        mapping = {}
        for i, name in enumerate(self.headers):
            matches = folded.get(name.casefold(), [])
            if name in exact:
                mapping[i] = exact[name]
            elif len(matches) == 1:
                mapping[i] = matches[0]
        adapted, skipped = [], []
        for number, source in enumerate(self.rules, 1):
            required = {condition.column for condition in atoms(source.condition)}
            if source.target is not None:
                required.add(source.target)
            absent = sorted(required - mapping.keys())
            if absent:
                skipped.append(f"Règle {number} : " + ", ".join(self.headers[i] for i in absent))
                continue
            rule = copy.deepcopy(source)
            for condition in atoms(rule.condition):
                condition.column = mapping[condition.column]
            if rule.target is not None:
                rule.target = mapping[rule.target]
            adapted.append(rule)
        return adapted, skipped

    def with_columns(self, headers):
        columns = self.headers.copy()
        known = {name.casefold() for name in columns}
        for name in headers:
            if name.casefold() not in known:
                columns.append(name)
                known.add(name.casefold())
        return RuleBook(columns, copy.deepcopy(self.rules))


def read_book(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Les règles globales sont limitées à 2 Mo")
    return RuleBook.from_bytes(path.read_bytes())


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, suffix=".partial", delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


class RuleStore:
    def __init__(self, path):
        self.path = Path(path)
        self.revision = None

    def load(self):
        if not self.path.exists():
            self.revision = None
            return RuleBook()
        if self.path.stat().st_size > MAX_BYTES:
            raise ValueError("Les règles globales sont limitées à 2 Mo")
        data = self.path.read_bytes()
        book = RuleBook.from_bytes(data)
        self.revision = hashlib.sha256(data).hexdigest()
        return book

    def save(self, book):
        data = book.to_bytes()
        if self.path.exists() and self.path.stat().st_size > MAX_BYTES:
            raise ValueError("Le fichier de règles globales a changé et dépasse 2 Mo")
        current = hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.exists() else None
        if current != self.revision:
            raise ValueError("Les règles globales ont changé sur disque. Rechargez-les avant de les modifier.")
        atomic_write(self.path, data)
        self.revision = hashlib.sha256(data).hexdigest()

    def replace(self, book):
        """Explicit import: validate first, then replace even an invalid old file."""
        data = book.to_bytes()
        atomic_write(self.path, data)
        self.revision = hashlib.sha256(data).hexdigest()
