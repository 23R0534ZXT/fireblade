"""Translate declarative DevExpress graphical rules without .NET deserialization."""
from decimal import Decimal
from fireblade.core.models import FormatRule,FilterGroup
from fireblade.core.icon_assets import png_bytes


def read_graphic(item,node,kind,text,properties,color,resolve,aliases,warnings):
    name=kind.lstrip('#').split(',')[0].split('.')[-1]
    modes={'FormatConditionRuleDataBar':'bar','FormatConditionRule2ColorScale':'scale','FormatConditionRule3ColorScale':'scale3','FormatConditionRuleIconSet':'icon'}
    if name not in modes:return None
    def field(value):return aliases[value] if value in aliases else resolve(value)
    column_name=text(item,'ColumnName') or text(item,'Column')
    if not column_name:raise ValueError('Règle graphique sans colonne de valeurs')
    value_column=field(column_name)
    target_name=text(item,'ColumnApplyToName') or column_name
    target=None if text(item,'ApplyToRow','false').lower()=='true' else field(target_name)
    def mode(value):
        names={'Automatic':'auto','Auto':'auto','Default':'auto','Minimum':'auto','Maximum':'auto','Number':'fixed','Numeric':'fixed','Value':'fixed','Percent':'percent','Percentage':'percent','Percentile':'percentile'}
        if value not in names:raise ValueError('Type de borne graphique non traduit : '+value)
        return names[value]
    def first(*names,default=''):
        return next((text(node,n) for n in names if text(node,n)),default)
    lower=mode(first('MinimumType','MinType',default='Automatic'))
    upper=mode(first('MaximumType','MaxType',default='Automatic'))
    low=first('Minimum','MinimumValue','MinValue',default='0');high=first('Maximum','MaximumValue','MaxValue',default='100')
    background=color(first('MinimumColor','MinColor','StartColor',default='White'),'#ffffff',warnings)
    foreground=color(first('MaximumColor','MaxColor','EndColor',default='Blue'),'#0000ff',warnings)
    rule=FormatRule(condition=FilterGroup(),target=target,value_column=value_column,visual=modes[name],background=background,foreground=foreground,
        minimum=low,maximum=high,bound_mode=lower,maximum_mode=upper,use_font=False,show_values=text(node,'ShowValues','true').lower()!='false',stop_if_true=text(item,'StopIfTrue','false').lower()=='true',enabled=text(item,'Enabled','true').lower()!='false')
    rule.zero_based=text(node,'AutomaticType','Default')=='ZeroBased'
    if rule.visual=='scale3':
        rule.middle_color=color(first('MiddleColor','MidColor',default='Yellow'),'#ffff00',warnings)
        middle_type=first('MiddleType','MidType',default='Automatic')
        rule.middle_mode='percent' if middle_type in ('Automatic','Auto','Default') else mode(middle_type)
        rule.middle_value=first('Middle','MiddleValue','MidValue',default='50')
    if rule.visual=='bar':
        # Common serializers store the bar color under Appearance / AppearancePositive.
        appearance=properties(node).get('AppearancePositive')
        if appearance is None:appearance=properties(node).get('Appearance')
        negative=properties(node).get('AppearanceNegative')
        if negative is not None:rule.negative_color=color(text(negative,'BackColor'),'#d64c4c',warnings)
        rule.axis_color=color(text(node,'AxisColor'),'#777777',warnings);rule.draw_axis=text(node,'DrawAxis','true').lower()!='false'
        if appearance is not None:
            fill=text(appearance,'BackColor') or text(appearance,'FillColor')
            if fill:rule.background=rule.foreground=color(fill,'#6c9bd2',warnings)
    if rule.visual=='icon':
        icon_set=properties(node).get('IconSet')
        if icon_set is None:raise ValueError('Jeu d’icônes absent du layout')
        container=properties(icon_set).get('Icons')
        entries=list(container) if container is not None else [c for c in icon_set if c.get('name','').startswith('Item')]
        if not 3<=len(entries)<=5:raise ValueError('Le jeu doit contenir 3 à 5 icônes')
        entries=sorted(entries,key=lambda e:Decimal(text(e,'Value','0')))
        label=(text(icon_set,'Name')+' '+text(entries[0],'PredefinedName')).lower()
        rule.icon_set='arrows' if any(x in label for x in ('arrow','direction','triangle')) else 'signs' if 'sign' in label else 'circles'
        palette={3:['#c62828','#c58b00','#218739'],4:['#c62828','#e39900','#88aa33','#218739'],5:['#c62828','#f57c00','#c58b00','#88aa33','#218739']}
        default_type=mode(text(icon_set,'ValueType','Percent'))
        threshold_modes=[];thresholds=[];images=[];colors=[]
        for i,entry in enumerate(entries):
            comparison=text(entry,'ValueComparison','GreaterOrEqual')
            if comparison not in ('GreaterOrEqual','Greater'):raise ValueError('Comparaison d’icône non traduite : '+comparison)
            if i==0:
                rule.icon_floor=text(entry,'Value','0');rule.icon_floor_comparison='>' if comparison=='Greater' else '>='
            else:rule.icon_comparisons.append('>' if comparison=='Greater' else '>=')
            if i:
                thresholds.append(text(entry,'Value',str(i*100/len(entries))))
                threshold_modes.append(mode(text(entry,'ValueType',text(icon_set,'ValueType','Percent'))))
            encoded=text(entry,'Image') or text(entry,'ImageData')
            image=properties(entry).get('Icon')
            if image is not None:encoded=text(image,'Image') or text(image,'ImageData') or encoded
            if encoded:png_bytes(encoded)
            images.append(encoded)
            colors.append(color(text(entry,'Color'),palette[len(entries)][i],warnings))
        if len(set(threshold_modes))>1:raise ValueError('Types mixtes de seuils d’icônes non pris en charge')
        mode_name=threshold_modes[0] if threshold_modes else default_type
        rule.icon_threshold_mode={'fixed':'number','auto':'number'}.get(mode_name,mode_name)
        rule.icon_floor_mode={'fixed':'number','auto':'number'}.get(default_type,default_type)
        rule.icon_thresholds=thresholds;rule.icon_images=images;rule.icon_colors=colors
        warnings.append('Pictogrammes prédéfinis adaptés aux formes Fireblade ; images PNG intégrées conservées')
    return rule
