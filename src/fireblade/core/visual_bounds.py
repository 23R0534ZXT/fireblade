"""Whole-filter numeric bounds; exact percentiles use disk-backed ranks."""
from dataclasses import replace
from decimal import Decimal,localcontext
import uuid


def interpolate(a,b,t):
    with localcontext() as context:
        context.prec=80
        return a+(b-a)*t


def resolve_rules(case,view,rules):
    filtered_where,filtered_args=case.where(view)
    cache=getattr(case,'_visual_bounds_cache',None)
    if cache is None:cache=case._visual_bounds_cache={}
    output=[]
    for rule in rules:
        where,args=("",[]) if rule.all_source_rows else (filtered_where,filtered_args)
        modes=(rule.bound_mode,rule.maximum_mode or rule.bound_mode)
        dynamic_icons=rule.visual=='icon' and bool(rule.icon_thresholds) and rule.icon_threshold_mode in ('percent','percentile') or rule.visual=='icon' and rule.icon_floor and rule.icon_floor_mode in ('percent','percentile')
        if not rule.enabled or rule.visual=='none' or (modes==('fixed','fixed') and not dynamic_icons and not (rule.visual=='scale3' and rule.middle_mode in ('percent','percentile'))):output.append(rule);continue
        key=(where,tuple(args),case._bookmark_revision,getattr(case,"_visual_query_revision",0),rule.value_column if rule.value_column is not None else rule.target,modes,rule.minimum,rule.maximum,tuple(rule.icon_thresholds),rule.icon_threshold_mode,rule.middle_mode,rule.middle_value,rule.icon_floor,rule.icon_floor_mode,rule.zero_based)
        with case.operation():
            if key not in cache:
                col=case.numeric_expression(case.column(rule.value_column if rule.value_column is not None else rule.target));query=f'SELECT {col} AS v FROM events{where}'
                valid=f'SELECT v FROM ({query}) vals WHERE v IS NOT NULL'
                minimum,maximum=case.db.execute(f'SELECT min(v),max(v) FROM ({valid}) vals',args).fetchone()
                name='__fb_percentile_'+uuid.uuid4().hex;ordered=False;count=0
                def bound(mode,value,upper=False):
                    nonlocal ordered,count
                    if mode=='fixed' or mode=='number':return Decimal(value)
                    if minimum is None:return Decimal(0)
                    if mode=='auto':return max(maximum,Decimal(0)) if upper and rule.zero_based else min(minimum,Decimal(0)) if rule.zero_based else maximum if upper else minimum
                    p=Decimal(value)/100
                    if mode=='percent':return interpolate(minimum,maximum,p)
                    if not ordered:
                        with case.serial_query_threads():case.db.execute(f'CREATE TEMP TABLE "{name}" AS SELECT v,row_number() OVER (ORDER BY v) AS pos FROM ({valid}) vals',args)
                        ordered=True;count=case.db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
                    rank=p*(count-1);floor=int(rank)
                    points=dict(case.db.execute(f'SELECT pos,v FROM "{name}" WHERE pos IN (?,?)',[floor+1,min(count,floor+2)]).fetchall())
                    return interpolate(points[floor+1],points[min(count,floor+2)],rank-floor)
                try:
                    low,high=bound(modes[0],rule.minimum),bound(modes[1],rule.maximum,True)
                    thresholds=[bound(rule.icon_threshold_mode,v) for v in rule.icon_thresholds] if rule.visual=='icon' else []
                    icon_floor=bound(rule.icon_floor_mode,rule.icon_floor) if rule.icon_floor else None
                    middle=bound(rule.middle_mode,rule.middle_value) if rule.visual=="scale3" else Decimal(0)
                    if low>high:raise ValueError("Bornes calculées inversées")
                    case.check_cancelled()
                    if len(cache)>=128:cache.pop(next(iter(cache)))
                    cache[key]=(str(low),str(high),[str(t) for t in thresholds],str(middle),str(icon_floor) if icon_floor is not None else "")
                finally:
                    with case.finalizing_transaction():case.db.execute(f'DROP TABLE IF EXISTS "{name}"')
            low,high,thresholds,middle,icon_floor=cache[key]
        output.append(replace(rule,minimum=low,maximum=high,bound_mode='fixed',maximum_mode='fixed',icon_thresholds=thresholds,icon_threshold_mode='number',middle_mode='fixed',middle_value=middle,icon_floor=icon_floor,icon_floor_mode='number'))
    return output
