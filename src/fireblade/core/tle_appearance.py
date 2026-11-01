"""Portable appearance data shared by TLE migration and Qt presentation."""
import math
import re

FONT_FLAGS=('bold','italic','underline','strikeout')
COLORS=('background','foreground','background2','border_color')
EXTRA=('word_wrap','trimming','hotkey','image','image_align','border_width','border_style')
ROLES={'row','odd_row','even_row','group_row','selected_row','focused_row','focused_cell','header','group_panel','footer_panel','view_caption','preview','empty','filter_panel','find_panel'}


def validate_styles(styles,columns):
    if not isinstance(styles,dict) or len(styles)>2*columns+len(ROLES):raise ValueError('Styles de disposition invalides')
    for target,style in styles.items():
        if not isinstance(target,str):raise ValueError('Cible de style invalide')
        if target not in ROLES:
            parts=target.split(':')
            if len(parts)!=2 or parts[0] not in ('cell','header') or not parts[1].isdecimal() or not 0<=int(parts[1])<columns:raise ValueError('Colonne du style absente')
        if not isinstance(style,dict) or set(style)-set(COLORS+FONT_FLAGS+('font_family','font_size','horizontal','vertical','gradient')+EXTRA):raise ValueError('Propriété de style inconnue')
        if 'image' in style:
            if not isinstance(style['image'],str):raise ValueError('Image de disposition invalide')
            from fireblade.core.layout_images import image_bytes
            image_bytes(style['image'])
        for key,value in style.items():
            if key=='word_wrap' and type(value) is not bool:raise ValueError('Renvoi à la ligne invalide')
            if key=='trimming' and value not in ('None','Character','Word','EllipsisCharacter','EllipsisWord','EllipsisPath'):raise ValueError('Troncature invalide')
            if key=='hotkey' and value not in ('None','Show','Hide'):raise ValueError('Préfixe clavier invalide')
            if key=='image_align' and value not in ('TopLeft','TopCenter','TopRight','MiddleLeft','MiddleCenter','MiddleRight','BottomLeft','BottomCenter','BottomRight'):raise ValueError('Alignement image invalide')
            if key=='border_width' and (type(value) is not int or not 1<=value<=8):raise ValueError('Largeur de bordure invalide')
            if key=='border_style' and value not in ('Solid','Dash','Dot'):raise ValueError('Style de bordure invalide')
            if key in COLORS and (not isinstance(value,str) or not re.fullmatch('#[a-fA-F0-9]{6}',value)):raise ValueError('Couleur de style invalide')
            if key in FONT_FLAGS and type(value) is not bool:raise ValueError('Police de style invalide')
            if key=='font_family' and (not isinstance(value,str) or len(value)>128):raise ValueError('Nom de police invalide')
            if key=='font_size' and (type(value) not in (int,float) or not math.isfinite(value) or not 4<=value<=96):raise ValueError('Taille de police invalide')
            if key=='horizontal' and value not in ('Near','Center','Far','Default'):raise ValueError('Alignement horizontal inconnu')
            if key=='vertical' and value not in ('Top','Center','Bottom','Default'):raise ValueError('Alignement vertical inconnu')
            if key=='gradient' and value not in ('Horizontal','Vertical','ForwardDiagonal','BackwardDiagonal'):raise ValueError('Dégradé de style inconnu')


def appearance(node,text,properties,color,warnings,defaults=None):
    result=dict(defaults or {})
    if node is None:return result
    options=properties(node).get('Options')
    def use(name,present):
        flag=(text(options,name) if options is not None else '') or text(node,'Options.'+name)
        if flag and flag.lower() not in ('true','false'):raise ValueError('Option de style invalide : '+name)
        return flag.lower()=='true' if flag else present
    for prop,key,flag in [('BackColor','background','UseBackColor'),('ForeColor','foreground','UseForeColor')]:
        raw=text(node,prop)
        if use(flag,bool(raw) or key in result):
            if raw and raw.lower() not in ('empty','transparent'):result[key]=color(raw,'#ffffff',warnings)
            elif raw:result.pop(key,None)
        else:result.pop(key,None)
    secondary=text(node,'BackColor2')
    if secondary and 'background' in result and secondary.lower() not in ('empty','transparent'):
        result['background2']=color(secondary,'#ffffff',warnings)
        result['gradient']=text(node,'GradientMode','Horizontal')
    font=text(node,'Font')
    font_keys=FONT_FLAGS+('font_family','font_size')
    if use('UseFont',bool(font) or any(key in result for key in font_keys)):
        if font:
            match=re.search(r',\s*(\d+(?:[.,]\d+)?)\s*(pt|px)\b',font,re.I)
            if not match:raise ValueError('Police de disposition non traduite : '+font)
            result.update(font_family=font[:match.start()].strip(),font_size=float(match.group(1).replace(',','.'))*(.75 if match.group(2).lower()=='px' else 1))
            for key in FONT_FLAGS:result[key]=key in font.lower()
    else:
        for key in font_keys:result.pop(key,None)
    border=text(node,'BorderColor')
    if use('UseBorderColor',bool(border) or 'border_color' in result):
        if border and border.lower() not in ('empty','transparent'):result['border_color']=color(border,'#808080',warnings)
    else:result.pop('border_color',None)
    image=text(node,'Image')
    image_options=properties(node).get('ImageOptions')
    if image_options is not None:image=text(image_options,'Image') or image
    if use('UseImage',bool(image) or 'image' in result):
        if image:
            from fireblade.core.layout_images import normalize_image
            result['image']=normalize_image(image)
        align=text(node,'ImageAlignment') or (text(image_options,'ImageAlignment') if image_options is not None else '')
        if align:result['image_align']=align
    else:result.pop('image',None)
    text_options=properties(node).get('TextOptions')
    if text_options is not None and use('UseTextOptions',True):
        for prop,key in [('HAlignment','horizontal'),('VAlignment','vertical')]:
            value=text(text_options,prop)
            if value:result[key]=value
        wrap=text(text_options,'WordWrap')
        if wrap and wrap not in ('Default','Wrap','NoWrap'):raise ValueError('Renvoi à la ligne inconnu : '+wrap)
        if wrap and wrap!='Default':result['word_wrap']=wrap=='Wrap'
        for prop,key in [('Trimming','trimming'),('HotkeyPrefix','hotkey')]:
            value=text(text_options,prop)
            if value:result[key]=value
    elif not use('UseTextOptions',True):
        for key in ('horizontal','vertical','word_wrap','trimming','hotkey'):result.pop(key,None)
    known={'Options','BackColor','BackColor2','ForeColor','GradientMode','Font','TextOptions','BorderColor','Image','ImageOptions','ImageAlignment'}
    supported_options={'UseBackColor','UseForeColor','UseFont','UseTextOptions','UseBorderColor','UseImage'}
    def active(child):
        return len(child)>0 or (child.text or '').strip() not in ('','False','false','Default','None','-1','0')
    for prop,child in properties(node).items():
        if prop not in known and prop not in {'Options.'+key for key in supported_options} and active(child):
            warnings.append('Option d’apparence non reprise : '+prop)
    if options is not None:
        for prop,child in properties(options).items():
            if prop not in supported_options and active(child):warnings.append('Option de priorité/bordure non reprise : '+prop)
    return result


def read_layout_styles(root,columns,text,properties,color,warnings):
    result={};container=properties(root).get('Appearance')
    mapping={'Row':'row','OddRow':'odd_row','EvenRow':'even_row','GroupRow':'group_row','SelectedRow':'selected_row','FocusedRow':'focused_row','FocusedCell':'focused_cell','HeaderPanel':'header','GroupPanel':'group_panel','FooterPanel':'footer_panel','GroupFooter':'footer_panel','ViewCaption':'view_caption','Preview':'preview','Empty':'empty','FilterPanel':'filter_panel','FindPanel':'find_panel'}
    options=properties(root).get('OptionsView')
    if container is not None:
        for name,node in properties(container).items():
            if name not in mapping:
                if len(node):warnings.append('Apparence TLE non reprise : '+name)
                continue
            role=mapping[name]
            if name in ('OddRow','EvenRow') and (options is None or text(options,'EnableAppearance'+name,'false').lower()!='true'):continue
            value=appearance(node,text,properties,color,warnings)
            if value:result[role]=value
    for column,node in columns:
        for prop,role in [('AppearanceCell','cell'),('AppearanceHeader','header')]:
            child=properties(node).get(prop)
            if child is not None:
                value=appearance(child,text,properties,color,warnings)
                if value:result[f'{role}:{column}']=value
    return result
