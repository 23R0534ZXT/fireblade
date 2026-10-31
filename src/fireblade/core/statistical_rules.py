"""Global statistical formatting with bounded Python state and exact duplicates.

A compact hash-frequency table identifies certainly unique values. Every candidate
collision/duplicate is checked against the original values, so hash collisions can
never produce a false duplicate. Table buffers use DuckDB's normal spill budget.
"""
from collections import OrderedDict
from decimal import Decimal,localcontext,ROUND_CEILING
import sys
import uuid


def source_column(rule):return rule.value_column if rule.value_column is not None else rule.target


def matches(case,view,rules,rows,numbers):
    active=[(i,r) for i,r in enumerate(rules) if r.enabled and r.statistic]
    if not active or not rows:return {}
    where,args=case.where(view)
    context=(where,tuple(args),case._bookmark_revision,getattr(case,'_visual_query_revision',0))
    result={}
    with case.operation():
        if getattr(case,'_stat_context',None)!=context:
            for name in getattr(case,'_stat_frequencies',{}).values():case.db.execute(f'DROP TABLE IF EXISTS "{name}"')
            case._stat_context=context;case._stat_frequencies={};case._stat_data={};case._stat_counts=OrderedDict();case._stat_bytes=0
        for index,rule in active:
            column=source_column(rule);raw=case.column(column);key=(column,rule.statistic,rule.stat_rank,rule.stat_percent)
            selected=set()
            if rule.statistic in ('unique','duplicate'):
                transformed=f'lower({raw})' if rule.stat_ignore_case else raw
                frequency_key=(column,rule.stat_ignore_case)
                if frequency_key not in case._stat_frequencies:
                    name='__fb_frequency_'+uuid.uuid4().hex
                    with case.serial_query_threads():case.db.execute(f'CREATE TEMP TABLE "{name}" AS SELECT hash({transformed}) AS h,count(*) AS n FROM events{where} GROUP BY 1',args)
                    case._stat_frequencies[frequency_key]=name
                name=case._stat_frequencies[frequency_key]
                values=list(dict.fromkeys(row[column+1] for row in rows if rule.stat_include_null or row[column+1] is not None))
                found={};missing=[]
                for value in values:
                    count_key=(column,rule.stat_ignore_case,value)
                    if count_key in case._stat_counts:found[value]=case._stat_counts[count_key][0];case._stat_counts.move_to_end(count_key)
                    else:missing.append(value)
                if missing:
                    requested='(VALUES '+','.join('(cast(? AS VARCHAR))' for _ in missing)+')'
                    normalized='lower(r.v)' if rule.stat_ignore_case else 'r.v'
                    candidates=case.db.execute(f'SELECT r.v,{normalized},coalesce(f.n,0) FROM {requested} r(v) LEFT JOIN "{name}" f ON f.h=hash({normalized})',missing).fetchall()
                    checks=list(dict.fromkeys(normal for original,normal,count in candidates if count>1))
                    exact={}
                    if checks:
                        nonnull=[v for v in checks if v is not None]
                        clauses=[]
                        if nonnull:clauses.append(transformed+' IN ('+','.join('?' for _ in nonnull)+')')
                        if None in checks:clauses.append(transformed+' IS NULL')
                        filtered=where+(' AND ' if where else ' WHERE ')+'('+' OR '.join(clauses)+')'
                        exact=dict(case.db.execute(f'SELECT {transformed},count(*) FROM events{filtered} GROUP BY 1',args+nonnull).fetchall())
                    for original,normal,count in candidates:
                        count=exact.get(normal,0) if count>1 else count;found[original]=count
                        cost=sys.getsizeof(original)+128
                        if cost<=131072:
                            count_key=(column,rule.stat_ignore_case,original)
                            while case._stat_counts and case._stat_bytes+cost>8*1024**2:
                                _,(_,removed)=case._stat_counts.popitem(last=False);case._stat_bytes-=removed
                            case._stat_counts[count_key]=(count,cost);case._stat_bytes+=cost
                for row in rows:
                    value=row[column+1]
                    if value is None and not rule.stat_include_null:continue
                    n=found.get(value,0)
                    if n==1 and rule.statistic=='unique' or n>1 and rule.statistic=='duplicate':selected.add(row[0])
            else:
                if key not in case._stat_data:
                    expression=case.numeric_expression(raw);valid=f'SELECT v FROM (SELECT {expression} AS v FROM events{where}) s WHERE v IS NOT NULL'
                    if rule.statistic in ('above_avg','below_avg'):
                        total=Decimal(0);count=0
                        with localcontext() as precision:
                            precision.prec=80;cursor=case.db.execute(valid,args)
                            while batch:=cursor.fetchmany(4096):
                                case.check_cancelled()
                                for value, in batch:total+=value;count+=1
                        case._stat_data[key]=(total,count)
                    else:
                        count=case.db.execute(f'SELECT count(*) FROM ({valid}) s',args).fetchone()[0]
                        n=int((Decimal(count)*Decimal(rule.stat_rank)/100).to_integral_value(rounding=ROUND_CEILING)) if rule.stat_percent else int(Decimal(rule.stat_rank))
                        n=min(n,count)
                        if not n:threshold=None
                        else:
                            name='__fb_rank_'+uuid.uuid4().hex
                            try:
                                with case.serial_query_threads():case.db.execute(f'CREATE TEMP TABLE "{name}" AS SELECT v,row_number() OVER (ORDER BY v) AS p FROM ({valid}) s',args)
                                position=n if rule.statistic=='bottom' else count-n+1
                                threshold=case.db.execute(f'SELECT v FROM "{name}" WHERE p=?',[position]).fetchone()[0]
                            finally:
                                with case.finalizing_transaction():case.db.execute(f'DROP TABLE IF EXISTS "{name}"')
                        case._stat_data[key]=threshold
                data=case._stat_data[key]
                for row in rows:
                    value=numbers.get((row[0],column))
                    if value is None:continue
                    if rule.statistic in ('above_avg','below_avg'):
                        total,count=data
                        with localcontext() as precision:
                            precision.prec=80;comparison=value*count
                            valid=count and (comparison>total if rule.statistic=='above_avg' else comparison<total)
                    else:valid=data is not None and (value>=data if rule.statistic=='top' else value<=data)
                    if valid:selected.add(row[0])
            case.check_cancelled();result[index]=selected
    return result
