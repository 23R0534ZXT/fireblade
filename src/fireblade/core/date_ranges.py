"""Controlled UTC relative-date boundaries; weeks start on Monday."""
# Expressions here are trusted SQL constants, never text interpolated by a user.
D='current_date';W="date_trunc('week',current_date)";M="date_trunc('month',current_date)";Y="date_trunc('year',current_date)"
def shift(base,n,unit):return f"({base}+INTERVAL '{n}' {unit})"
RANGES={
 'Today':(D,shift(D,1,'DAY')),'Yesterday':(shift(D,-1,'DAY'),D),'Tomorrow':(shift(D,1,'DAY'),shift(D,2,'DAY')),
 'ThisWeek':(W,shift(W,1,'WEEK')),'LastWeek':(shift(W,-1,'WEEK'),W),'NextWeek':(shift(W,1,'WEEK'),shift(W,2,'WEEK')),
 'EarlierThisWeek':(W,shift(D,-1,'DAY')),'LaterThisWeek':(shift(D,2,'DAY'),shift(W,1,'WEEK')),
 'ThisMonth':(M,shift(M,1,'MONTH')),'EarlierThisMonth':(M,shift(W,-1,'WEEK')),'LaterThisMonth':(shift(W,2,'WEEK'),shift(M,1,'MONTH')),
 'EarlierThisYear':(Y,M),'LaterThisYear':(shift(M,1,'MONTH'),shift(Y,1,'YEAR')),
 'PriorThisYear':(None,Y),'BeyondThisYear':(shift(Y,1,'YEAR'),None),'Beyond':(shift(M,3,'MONTH'),None),'Earlier':(None,shift(M,-6,'MONTH')),
 **{f'MonthAfter{i}':(shift(M,i,'MONTH'),shift(M,i+1,'MONTH')) for i in (1,2)},
 **{f'MonthAgo{i}':(shift(M,-i,'MONTH'),shift(M,1-i,'MONTH')) for i in range(1,7)},
}


def compile_range(sql,name):
    if name in ('None','Empty'):return 'FALSE',0
    if name not in RANGES:raise ValueError('Intervalle de date non pris en charge : '+name)
    low,high=RANGES[name];parts=[]
    if low:parts.append(f'({sql})>={low}')
    if high:parts.append(f'({sql})<{high}')
    return '('+' AND '.join(parts)+')',len(parts)
