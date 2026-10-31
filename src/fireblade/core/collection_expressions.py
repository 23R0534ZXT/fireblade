"""Translate flat JSON collection criteria into controlled scalar functions."""
import re


def translate(text,headers):
    if not re.search(r"\]\s*(?:\[|\.)|\[[^\]]*\.",text):return text
    tokens=sorted(('['+h.replace(']',']]')+']' for h in headers),key=len,reverse=True)
    def end_group(start,left,right):
        depth=0;quote=None;i=start
        while i<len(text):
            ch=text[i]
            if quote:
                if ch==quote:
                    if i+1<len(text) and text[i+1]==quote:i+=2;continue
                    quote=None
            elif ch in ("'",'"'):quote=ch
            elif ch==left:depth+=1
            elif ch==right:
                depth-=1
                if depth==0:return i
            i+=1
        raise ValueError('Collection : délimiteur non fermé')
    def quote(value):return "'"+value.replace("'","''")+"'"
    field_pattern=re.compile('|'.join(re.escape(t) for t in tokens),re.I) if tokens else None
    result=[];i=0;string=None
    while i<len(text):
        ch=text[i]
        if string:
            result.append(ch)
            if ch==string:
                if i+1<len(text) and text[i+1]==string:result.append(text[i+1]);i+=2;continue
                string=None
            i+=1;continue
        if ch in ("'",'"'):string=ch;result.append(ch);i+=1;continue
        match_field=field_pattern.match(text,i) if ch=='[' and field_pattern else None
        token=match_field.group(0) if match_field else None
        parts=[]
        stop=i+len(token) if token else i
        if not token and ch=='[':
            field=re.match(r'\[((?:[^\]]|\]\])+)\]',text[i:])
            if field:
                full=field.group(1).replace(']]',']')
                parent=next((h for h in sorted(headers,key=len,reverse=True) if full.casefold().startswith(h.casefold()+'.')),None)
                if parent:
                    token='['+parent.replace(']',']]')+']';parts=full[len(parent)+1:].split('.');stop=i+field.end()
        if token:
            while chain:=re.match(r'\s*\.\s*\[((?:[^\]]|\]\])+)\]',text[stop:]):
                parts.append(chain.group(1).replace(']]',']'));stop+=chain.end()
            collection=token
            if parts:
                import json
                path='$.'+'.'.join(json.dumps(part,ensure_ascii=False) for part in parts)
                collection=f'JsonValue({token},{quote(path)})' 
            while stop<len(text) and text[stop].isspace():stop+=1
            predicate=None
            if stop<len(text) and text[stop]=='[':
                close=end_group(stop,'[',']');predicate=text[stop+1:close];stop=close+1
            match=re.match(r'\s*\.\s*(Count|Exists|Sum|Avg|Average|Min|Max|Single)\s*\(',text[stop:],re.I)
            if match:
                start=stop+match.end()-1;close=end_group(start,'(',')');argument=text[start+1:close].strip();name=match.group(1).lower()
                if predicate is not None:collection=f'JsonFilter({collection},{quote(predicate)})'
                if name=='count':replacement=f'JsonCount({collection})' if not argument else f'JsonCount(JsonFilter({collection},{quote(argument)}))'
                elif name=='exists':replacement=f'JsonAny({collection},{quote(argument or "True")})'
                elif name=='single':replacement=f'JsonSingle({collection}'+(','+quote(argument) if argument else '')+')'
                else:
                    if not argument:raise ValueError('Agrégat de collection sans expression')
                    name='avg' if name=='average' else name
                    replacement=f'Json{name.title()}Expr({collection},{quote(argument)})'
                result.append(replacement);i=close+1;continue
            if parts:
                result.append(collection);i=stop;continue
        result.append(ch);i+=1
    return ''.join(result)
