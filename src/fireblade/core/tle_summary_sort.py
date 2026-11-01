"""Decode TLE's length-prefixed group-summary sort records as data only.

Each UTF-16-sized record is ColumnName,SortOrder,SummaryTag. Tags may reference
an original GroupSummary index (#0) or the item's explicit Tag property.
"""
from fireblade.core.models import GroupSort


def read_summary_sorts(state,resolve,indices,tags):
    if not state:return []
    if len(state)>65536:raise ValueError('Tri de résumés TLE trop volumineux')
    data=state.encode('utf-16-le');offset=0;result=[]
    while offset<len(data):
        end=data.find(b':\x00',offset)
        if end<offset or (end-offset)%2:raise ValueError('Longueur du tri de résumés TLE invalide')
        digits=data[offset:end].decode('utf-16-le')
        if not digits.isascii() or not digits.isdecimal() or len(digits)>5:raise ValueError('Longueur du tri de résumés TLE invalide')
        size=int(digits)*2;offset=end+2
        if size<2 or offset+size>len(data):raise ValueError('Tri de résumés TLE tronqué')
        try:parts=data[offset:offset+size].decode('utf-16-le').split(',',2)
        except UnicodeError as exc:raise ValueError('Tri de résumés TLE invalide') from exc
        offset+=size
        if len(parts)!=3 or parts[1] not in ('Ascending','Descending','None','0','1','2'):raise ValueError('Direction du tri de résumés TLE inconnue')
        name,direction,tag=parts
        if direction in ('None','0'):continue
        if tag.startswith('#'):
            index=tag[1:]
            if not index.isascii() or not index.isdecimal() or int(index)>=len(indices):raise ValueError('Référence de résumé TLE absente')
            mapped=indices[int(index)]
        else:
            if tag not in tags:raise ValueError('Tag du résumé TLE absent ou ambigu : '+tag)
            mapped=tags[tag]
        if mapped=='unsupported':raise ValueError('Tri lié à un résumé TLE non traduit')
        result.append(GroupSort(resolve(name),'count' if mapped is None else 'summary',mapped or 0,direction in ('Descending','2')))
        if len(result)>128:raise ValueError('128 tris de groupes au maximum')
    return result
