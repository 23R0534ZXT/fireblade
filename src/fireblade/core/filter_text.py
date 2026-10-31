"""Safe parser for common Timeline Explorer filter expressions; never eval/SQL.

A deliberately explicit grammar rejects unsupported functions instead of silently
changing their meaning. The normal tree editor remains the canonical format.
"""
import re
from fireblade.core.models import Filter, FilterGroup

TOKEN = re.compile(r"\s*(?:(\[(?:[^\]]|\]\])*\])|('(?:[^']|'')*')|(#(?:[^#]+)#)|([+-]?(?:\d+(?:\.\d*)?|\.\d+))|([A-Za-z_]\w*)|(>=|<=|<>|!=|==|[=<>(),]))")


class Parser:
    def __init__(self, text, headers):
        if len(text) > 65536:
            raise ValueError('Expression limitée à 64 Ko')
        self.tokens, self.position = [], 0
        self.headers = {h.casefold(): i for i, h in enumerate(headers)}
        offset = 0
        text = text.strip()
        while offset < len(text):
            match = TOKEN.match(text, offset)
            if not match:
                raise ValueError(f'Syntaxe non prise en charge près du caractère {offset + 1}')
            kind = next(i for i, value in enumerate(match.groups()) if value is not None)
            self.tokens.append((kind, match.group(kind + 1)))
            offset = match.end()
            if len(self.tokens) > 4096:
                raise ValueError('Expression trop complexe')

    def peek(self, value=None):
        if self.position >= len(self.tokens):
            return False
        return self.tokens[self.position][1].casefold() == value.casefold() if value else self.tokens[self.position]

    def take(self, expected=None):
        if not self.peek():
            raise ValueError('Expression incomplète')
        token = self.tokens[self.position]
        if expected is not None and token[1].casefold() != expected.casefold():
            raise ValueError(f'{expected} attendu')
        self.position += 1
        return token

    def parse(self, depth=0):
        if depth > 24:
            raise ValueError('24 niveaux au maximum')
        values = [self.conjunction(depth + 1)]
        while self.peek('or'):
            self.take()
            values.append(self.conjunction(depth + 1))
        return values[0] if len(values) == 1 else FilterGroup('or', values)

    def conjunction(self, depth):
        values = [self.atom(depth)]
        while self.peek('and'):
            self.take()
            values.append(self.atom(depth))
        return values[0] if len(values) == 1 else FilterGroup('and', values)

    def column(self):
        kind, token = self.take()
        if kind != 0:
            raise ValueError('Une colonne [Nom] est attendue')
        name = token[1:-1].replace(']]', ']')
        if name.casefold() not in self.headers:
            raise ValueError(f'Colonne inconnue : {name}')
        return self.headers[name.casefold()]

    def literal(self):
        kind, token = self.take()
        if kind == 1:
            return token[1:-1].replace("''", "'"), 'text'
        if kind == 2:
            return token[1:-1], 'date'
        if kind == 3:
            return token, 'number'
        if token.casefold() in ('true','false'):
            # Boolean literals need the typed compiler, including CSV booleans
            # whose textual casing differs from the literal.
            raise ValueError('Comparaison booléenne typée')
        if token.casefold()=='null':return 'NULL','null'
        if token.casefold() in ('datetime', 'todate'):
            self.take('(')
            value, _kind = self.literal()
            self.take(')')
            return value, 'date'
        raise ValueError('Valeur littérale attendue')

    def atom(self, depth):
        if depth > 24:
            raise ValueError('24 niveaux au maximum')
        if self.peek('not'):
            self.take()
            return FilterGroup('not', [self.atom(depth + 1)])
        if self.peek('('):
            self.take()
            value = self.parse(depth + 1)
            self.take(')')
            return value
        token = self.peek()
        if token and token[0] == 4:
            function = self.take()[1].casefold()
            self.take('(')
            column = self.column()
            if function in ('isnull', 'isnullorempty'):
                self.take(')')
                return Filter(column, 'empty')
            if function not in ('contains', 'startswith', 'endswith'):
                raise ValueError(f'Fonction non prise en charge : {function}')
            self.take(',')
            value, _kind = self.literal()
            self.take(')')
            return Filter(column, {'contains': 'contains', 'startswith': 'starts', 'endswith': 'ends'}[function], value)
        column = self.column()
        negate = False
        if self.peek('not'):
            self.take()
            negate = True
        if self.peek('in'):
            self.take()
            self.take('(')
            values = []
            while True:
                value, kind = self.literal()
                values.append(Filter(column, 'empty' if kind == 'null' else 'eq', '' if kind == 'null' else value))
                if not self.peek(','):
                    break
                self.take()
            self.take(')')
            result = FilterGroup('or', values)
        elif self.peek('between'):
            self.take()
            start, kind = self.literal()
            self.take('and')
            end, end_kind = self.literal()
            if kind != end_kind or kind not in ('number', 'date'):
                raise ValueError('Between nécessite deux nombres ou deux dates')
            result = FilterGroup('and', [Filter(column, 'after' if kind == 'date' else 'ge', start), Filter(column, 'before' if kind == 'date' else 'le', end)])
        else:
            if negate:
                raise ValueError('Not doit précéder In ou Between')
            op = self.take()[1]
            value, kind = self.literal()
            mapping = {'=': 'eq', '==': 'eq', '<>': 'ne', '!=': 'ne', '>': 'gt', '>=': 'ge', '<': 'lt', '<=': 'le'}
            if op not in mapping:
                raise ValueError('Comparaison non prise en charge')
            code = mapping[op]
            if kind == 'null':
                if code not in ('eq', 'ne'):
                    raise ValueError('NULL doit être comparé par égalité')
                code, value = ('empty' if code == 'eq' else 'not_empty'), ''
            elif kind == 'date':
                code = {'gt': 'date_after', 'ge': 'after', 'lt': 'date_before', 'le': 'before', 'eq': 'date_eq', 'ne': 'date_ne'}[code]
            elif kind == 'text' and code not in ('eq', 'ne'):
                code = 'text_' + code
            result = Filter(column, code, value)
        return FilterGroup('not', [result]) if negate else result


def _parse_simple_filter(text, headers):
    parser = Parser(text, headers)
    if not parser.tokens:
        return FilterGroup()
    result = parser.parse()
    if parser.position != len(parser.tokens):
        raise ValueError('Texte supplémentaire après la condition')
    return result if isinstance(result, FilterGroup) else FilterGroup('and', [result])


def parse_filter(text, headers):
    try:
        return _parse_simple_filter(text, headers)
    except ValueError:
        from fireblade.core.expressions import compile_expression
        compile_expression(text, headers, lambda i: f'"c{i}"', lambda c: f'try_cast({c} AS DECIMAL(38,10))')
        return FilterGroup('and', [Filter(0,'expression',text)])
