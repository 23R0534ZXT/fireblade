"""Rewrite layout column aliases without rewriting child collection properties."""
import re
from fireblade.core.collection_expressions import translate
from fireblade.core.expressions import TOKEN

HELPERS={'jsonfilter','jsonany','jsonall','jsonsumexpr','jsonavgexpr','jsonminexpr','jsonmaxexpr','jsonsingle'}
KEYWORDS={'true','false','null','and','or','not','in','between','like','is','xor','c'}


def migrate(value,headers,aliases,resolve,depth=0):
    if depth>16:raise ValueError('16 niveaux de collections maximum')
    from fireblade.core.criteria_literals import bind
    value=bind(value)
    roots=list(dict.fromkeys(list(headers)+list(aliases))) if depth==0 else list(dict.fromkeys(re.findall(r'\[([^\[\]]+)\]',value)))
    value=translate(value,roots)
    result=[];stack=[];last=None;offset=0
    def field(name):
        parent=re.match(r'^(\^(?:\.\^)*|\^+)\.(.+)$',name)
        if depth and (parent is None or parent.group(1).count('^')!=depth):return '['+name.replace(']',']]')+']'
        prefix='^.'*depth if depth else ''
        name=parent.group(2) if parent else name
        if name.casefold() in ('line','tag','note') and name.casefold() not in [h.casefold() for h in headers]:return '['+prefix+name+']'
        index=aliases[name] if name in aliases else resolve(name)
        return '['+prefix+headers[index].replace(']',']]')+']'
    while offset<len(value):
        token=TOKEN.match(value,offset)
        if not token:
            if value[offset:].strip():raise ValueError('Syntaxe de filtre TLE inconnue')
            break
        rendered=token.group(0);word=next(group for group in token.groups() if group is not None)
        leading=rendered[:len(rendered)-len(word)]
        if token.group(1):rendered=leading+field(word[1:-1].replace(']]',']'))
        elif token.group(2) and stack and stack[-1][0] in HELPERS and stack[-1][1]==1:
            quote=word[0];inner=word[1:-1].replace(quote*2,quote)
            migrated=migrate(inner,headers,aliases,resolve,depth+1)
            rendered=leading+"'"+migrated.replace("'","''")+"'"
        elif token.group(5) and depth==0 and word.casefold() not in KEYWORDS and not value[token.end():].lstrip().startswith('('):rendered=leading+field(word.lstrip('@'))
        if word=='(':stack.append([last.casefold() if last else '',0])
        elif word==',' and stack:stack[-1][1]+=1
        elif word==')' and stack:stack.pop()
        result.append(rendered);last=word;offset=token.end()
    return ''.join(result)
