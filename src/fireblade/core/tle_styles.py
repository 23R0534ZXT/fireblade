"""Portable adaptations of the twelve documented DevExpress text/fill presets."""
STYLES={
 'Bold Text':dict(bold=True),'Italic Text':dict(italic=True),'Strikeout Text':dict(strikeout=True),
 'Green Bold Text':dict(foreground='#006100',bold=True),'Green Text':dict(foreground='#006100'),
 'Green Fill':dict(background='#c6efce'),'Green Fill, Green Text':dict(background='#c6efce',foreground='#006100'),
 'Red Bold Text':dict(foreground='#9c0006',bold=True),'Red Text':dict(foreground='#9c0006'),
 'Red Fill':dict(background='#ffc7ce'),'Red Fill, Red Text':dict(background='#ffc7ce',foreground='#9c0006'),
 'Yellow Fill, Yellow Text':dict(background='#ffeb9c',foreground='#9c6500'),
}
def style(name):
    if name not in STYLES:raise ValueError('Style prédéfini personnalisé non traduit : '+name)
    return STYLES[name]
