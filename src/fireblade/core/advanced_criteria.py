"""Additional DevExpress scalar functions compiled to bounded native DuckDB SQL."""


def function(compiler,name,args):
    from fireblade.core.expressions import Value
    c=compiler
    def arity(low,high=None):
        if not low<=len(args)<=(low if high is None else high):raise ValueError('Nombre d’arguments invalide pour '+name)
    def result(sql,kind='text',values=None):return Value(sql,kind,[p for a in (args if values is None else values) for p in a.parameters])
    def once(body,kind='text',values=None):
        values=args if values is None else values
        fields=','.join('v'+str(i)+':='+a.sql for i,a in enumerate(values))
        return result('list_extract(list_transform([struct_pack('+fields+')],lambda __fb_arg: '+body+'),1)',kind,values)
    def field(i):return '__fb_arg.v'+str(i)
    if name in ('atn','atn2','sqr'):
        return c.function({'atn':'atan','atn2':'atan2','sqr':'sqrt'}[name],args)
    if name in ('cosh','sinh','tanh','trunc','truncate'):
        arity(1);value=c.cast(args[0],'number');return result(f'TRY({"trunc" if name=="truncate" else name}({value.sql}))','number',[value])
    if name in ('rnd','pi'):
        arity(0);return result('random()' if name=='rnd' else 'pi()','number')
    if name=='inrange':
        arity(3);left=c.binary('>=',args[0],args[1]);right=c.binary('<',args[0],args[2])
        return result('('+left.sql+') AND ('+right.sql+')','boolean',[left,right])
    if name=='isnullorwhitespace':
        arity(1);value=c.cast(args[0],'text');return result(f"coalesce(regexp_full_match({value.sql},'\\s*'),TRUE)",'boolean',[value])
    if name in ('charindex','indexof') and len(args)==3:
        text=c.cast(args[1],'text');needle=c.cast(args[0],'text');start=c.cast(args[2],'number')
        return once("CASE WHEN v2<0 OR v2>length(v1) THEN NULL WHEN strpos(substring(v1,cast(v2 AS BIGINT)+1),v0)=0 THEN -1 ELSE cast(v2 AS BIGINT)+strpos(substring(v1,cast(v2 AS BIGINT)+1),v0)-1 END".replace('v2',field(2)).replace('v1',field(1)).replace('v0',field(0)),'number',[needle,text,start])
    if name=='gettimeofday':
        arity(1);ns=c.nanoseconds(args[0]);return result(f'((({ns.sql})%86400000000000+86400000000000)%86400000000000)//100','number',[ns,ns])
    if name=='addtimespan':
        arity(2);ns=c.nanoseconds(args[0])
        if args[1].kind=='number':
            ticks=c.cast(args[1],'number')
            return c.date_value(result(f'TRY(({ns.sql})+try_cast(({ticks.sql})*100 AS HUGEINT))','number',[ns,ticks]))
        text=c.cast(args[1],'text');pattern=r'^([+-]?)(?:(\d+)\.)?(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,7}))?$'
        def part(index):return f"regexp_extract({field(1)},'{pattern}',{index})"
        day=f"coalesce(try_cast({part(2)} AS HUGEINT),0)";hour=f'try_cast({part(3)} AS HUGEINT)';minute=f'try_cast({part(4)} AS HUGEINT)';second=f'try_cast({part(5)} AS HUGEINT)'
        fraction=f"try_cast(rpad({part(6)},7,'0') AS HUGEINT)"
        elapsed=f"(({day}*86400+{hour}*3600+{minute}*60+{second})*1000000000+{fraction}*100)*(CASE WHEN {part(1)}='-' THEN -1 ELSE 1 END)"
        duration=f"coalesce(try_cast({field(1)} AS HUGEINT)*100,CASE WHEN regexp_full_match({field(1)},'{pattern}') AND {hour}<24 AND {minute}<60 AND {second}<60 THEN {elapsed} END)"
        return c.date_value(once(f'TRY({field(0)}+({duration}))','number',[ns,text]))
    if name in ('issameday','issamehour','issametime'):
        arity(2,32);unit={'issameday':'day','issamehour':'hour','issametime':'minute'}[name]
        dates=[c.cast(a,'date') for a in args];parts=[];values=[]
        for item in dates[1:]:
            parts.append(f"date_trunc('{unit}',{dates[0].sql})=date_trunc('{unit}',{item.sql})");values.extend([dates[0],item])
        return result(' AND '.join(parts),'boolean',values)
    months=('january','february','march','april','may','june','july','august','september','october','november','december')
    if name.startswith('is') and name[2:] in months:
        arity(1);value=c.cast(args[0],'date');return result(f'date_part(\'month\',{value.sql})={months.index(name[2:])+1}','boolean',[value])
    relative={'isthisweek':('week',0),'islastweek':('week',-1),'isnextweek':('week',1),'isthismonth':('month',0),'islastmonth':('month',-1),'isnextmonth':('month',1),'isthisyear':('year',0),'islastyear':('year',-1),'isnextyear':('year',1),'isthishour':('hour',0),'islasthour':('hour',-1),'isnexthour':('hour',1)}
    if name in relative:
        arity(1);unit,offset=relative[name];date=c.cast(args[0],'date')
        return result(f"date_trunc('{unit}',{date.sql})=date_trunc('{unit}',current_timestamp)+INTERVAL '{offset}' {unit.upper()}",'boolean',[date])
    if name=='isyeartodate':
        arity(1);date=c.cast(args[0],'date')
        return result(f"{date.sql}>=date_trunc('year',current_timestamp) AND {date.sql}<current_date+INTERVAL 1 DAY",'boolean',[date,date])
    if name.startswith('isoutlookinterval'):
        arity(1)
        from fireblade.core.date_ranges import RANGES,compile_range
        key=next((key for key in RANGES if key.casefold()==name[len('isoutlookinterval'):]),None)
        if key is None:raise ValueError('Période Outlook non prise en charge : '+name)
        date=c.cast(args[0],'date');sql,repeats=compile_range(date.sql,key);return result(sql,'boolean',[date]*repeats)
    calendar={'localdatetimethisweek':('week',0),'localdatetimelastweek':('week',-1),'localdatetimenextweek':('week',1),'localdatetimetwoweeksaway':('week',2),'localdatetimedayaftertomorrow':('day',2),'localdatetimetwomonthsaway':('month',2),'localdatetimetwoyearsaway':('year',2)}
    if name in calendar:
        arity(0);unit,amount=calendar[name];return result(f"date_trunc('{unit}',current_timestamp)+INTERVAL '{amount}' {unit.upper()}",'date')
    if name=='localdatetimeyearbeforetoday':
        arity(0);return result("current_date-INTERVAL 1 YEAR",'date')
    if name=='indaterange' and len(args)==3:
        date=c.cast(args[0],'date');low=c.cast(args[1],'date');high=c.cast(args[2],'date')
        return result(f"{date.sql}>=date_trunc('day',{low.sql}) AND {date.sql}<date_trunc('day',{high.sql})+INTERVAL 1 DAY",'boolean',[date,low,date,high])
    if name in ('datetimefromparts','dateonlyfromparts','timeonlyfromparts'):
        arity(2 if name=='timeonlyfromparts' else 3,4 if name=='timeonlyfromparts' else 3 if name=='dateonlyfromparts' else 7)
        values=[c.cast(a,'number') for a in args]
        if name=='timeonlyfromparts':
            hour,minute=field(0),field(1);second=field(2) if len(args)>2 else '0';ms=field(3) if len(args)>3 else '0'
            sql=f"CASE WHEN {hour} BETWEEN 0 AND 23 AND {minute} BETWEEN 0 AND 59 AND {second} BETWEEN 0 AND 59 AND {ms} BETWEEN 0 AND 999 THEN try_cast(printf('%02d:%02d:%02d.%03d',cast({hour} AS INT),cast({minute} AS INT),cast({second} AS INT),cast({ms} AS INT)) AS TIME_NS) END"
            value=once(sql,'time',values);value.native_tag='timeonly';return value
        year,month,day=[field(i) for i in range(3)]
        hour=field(3) if len(args)>3 else '0';minute=field(4) if len(args)>4 else '0';second=field(5) if len(args)>5 else '0';ms=field(6) if len(args)>6 else '0'
        sql=f"CASE WHEN {year} BETWEEN 1 AND 9999 AND {hour} BETWEEN 0 AND 23 AND {minute} BETWEEN 0 AND 59 AND {second} BETWEEN 0 AND 59 AND {ms} BETWEEN 0 AND 999 THEN TRY(make_timestamptz(cast({year} AS INT),cast({month} AS INT),cast({day} AS INT),cast({hour} AS INT),cast({minute} AS INT),cast({second}+{ms}/1000 AS DOUBLE))) END"
        value=once(sql,'date',values)
        if name=='dateonlyfromparts':value.native_tag='dateonly'
        return value
    if name in ('aftermidday','beforemidday','ismorning','isafternoon','isevening','isnight'):
        arity(1);value=args[0] if args[0].kind=='time' else c.cast(args[0],'date')
        hour=f"date_part('hour',{value.sql})";patterns={'aftermidday':hour+'>=12','beforemidday':hour+'<12','ismorning':hour+' BETWEEN 6 AND 11','isafternoon':hour+' BETWEEN 12 AND 17','isevening':hour+' BETWEEN 18 AND 20','isnight':hour+'>=21 OR '+hour+'<9'}
        return result('('+patterns[name]+')','boolean',[value]*(2 if name=='isnight' else 1))
    if name in ('addhours','addminutes','addseconds','addmilliseconds','addticks') and args and args[0].kind=='time':
        arity(2);base=c.nanoseconds(args[0]);amount=c.cast(args[1],'number');scale={'addhours':3600000000000,'addminutes':60000000000,'addseconds':1000000000,'addmilliseconds':1000000,'addticks':100}[name]
        ns=result(f'TRY(({base.sql})+try_cast(({amount.sql})*{scale} AS HUGEINT))','number',[base,amount])
        date=c.date_value(ns)
        value=Value('try_cast('+date.sql+' AS TIME_NS)','time',date.parameters,date_ns=ns,native_tag='timeonly');return value
    return None
