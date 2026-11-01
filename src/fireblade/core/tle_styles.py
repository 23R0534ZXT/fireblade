"""Portable adaptations of the twelve documented DevExpress text/fill presets."""
STYLES={
 'Bold Text':dict(bold=True),'Italic Text':dict(italic=True),'Strikeout Text':dict(strikeout=True),
 'Green Bold Text':dict(foreground='#006100',bold=True),'Green Text':dict(foreground='#006100'),
 'Green Fill':dict(background='#c6efce'),'Green Fill, Green Text':dict(background='#c6efce',foreground='#006100'),
 'Red Bold Text':dict(foreground='#9c0006',bold=True),'Red Text':dict(foreground='#9c0006'),
 'Red Fill':dict(background='#ffc7ce'),'Red Fill, Red Text':dict(background='#ffc7ce',foreground='#9c0006'),
 'Yellow Fill, Yellow Text':dict(background='#ffeb9c',foreground='#9c6500'),
}
def style(name,custom=None):
    if custom and name in custom:return dict(custom[name])
    if name not in STYLES:raise ValueError('Style prédéfini personnalisé non traduit : '+name)
    return dict(STYLES[name])


def custom_styles(layout_path):
    """Resolve named definitions from an explicit portable sidecar or user library."""
    import json
    from pathlib import Path
    from fireblade.runtime.windows_paths import user_directory
    from fireblade.core.tle_appearance import validate_styles
    result={}
    for path in (user_directory()/'Layouts'/'styles.json',Path(str(layout_path)+'.styles.json')):
        if not path.exists():continue
        if path.stat().st_size>1024*1024:raise ValueError('Bibliothèque de styles limitée à 1 Mo')
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data,dict) or len(data)>128:raise ValueError('Bibliothèque de styles invalide (128 styles maximum)')
        for name,value in data.items():
            if not isinstance(name,str) or not name or len(name)>128:raise ValueError('Nom de style invalide')
            validate_styles({'row':value},0)
            result[name]=value
    return result
