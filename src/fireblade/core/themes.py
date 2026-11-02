"""Original Qt palettes, inspired by familiar desktop theme families.

These are not DevExpress skin assets or reproductions of proprietary metrics.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePreset:
    name: str
    mode: str
    colors: tuple[str, ...]

    def palette(self):
        return dict(zip(('window','text','base','alternate','highlight','selection_text'),self.colors))


THEMES = {
    'office-white': ThemePreset('Office clair', 'light', ('#f3f3f3','#202020','#ffffff','#f5f7fa','#cde6ff','#102030')),
    'office-dark': ThemePreset('Office gris foncé', 'dark', ('#3b3b3b','#f3f3f3','#292929','#333333','#385d80','#ffffff')),
    'office-black': ThemePreset('Office noir', 'dark', ('#202020','#f5f5f5','#141414','#252525','#284d71','#ffffff')),
    'classic-blue': ThemePreset('Bleu classique', 'light', ('#e7eff8','#172c43','#ffffff','#f0f5fb','#b4d5f5','#102438')),
    'silver': ThemePreset('Argent', 'light', ('#e8e9ec','#25272d','#ffffff','#f2f3f5','#d4dcf0','#202838')),
    'graphite': ThemePreset('Graphite', 'dark', ('#292d34','#eef1f5','#1d2127','#262b33','#3f526b','#ffffff')),
    'studio-light': ThemePreset('Studio clair', 'light', ('#eeeeF2','#222222','#ffffff','#f4f4f7','#c9def5','#152b43')),
    'studio-dark': ThemePreset('Studio sombre', 'dark', ('#2d2d30','#f1f1f1','#1e1e1e','#29292c','#264f78','#ffffff')),
    'night': ThemePreset('Nuit profonde', 'dark', ('#11151b','#e8edf5','#090c11','#141a22','#274d73','#ffffff')),
    'night-lit': ThemePreset('Nuit éclairée', 'dark', ('#303949','#f2f5fa','#252e3e','#2e394b','#37618f','#ffffff')),
    'code-dark': ThemePreset('Code sombre', 'dark', ('#181818','#e6e6e6','#1f1f1f','#27272b','#264f78','#ffffff')),
    'midnight-blue': ThemePreset('Bleu minuit', 'dark', ('#161e31','#dde7ff','#0d1424','#18213b','#314a80','#ffffff')),
    'violet-night': ThemePreset('Nuit violette', 'dark', ('#282a36','#f8f8f2','#20212b','#2d3040','#55466f','#ffffff')),
    'ocean-night': ThemePreset('Océan nocturne', 'dark', ('#15303a','#e3f4f5','#0c222b','#17343d','#216678','#ffffff')),
    'nord': ThemePreset('Nordique', 'dark', ('#2e3440','#eceff4','#242933','#353d4c','#425b77','#ffffff')),
    'arctic-light': ThemePreset('Aurore claire', 'light', ('#e7f0f4','#173441','#f8fcff','#edf5fa','#bddbea','#132d3b')),
    'warm-light': ThemePreset('Atelier clair', 'light', ('#f0eae4','#342c27','#fffaf4','#f6efe7','#dfc6aa','#32251b')),
    'amber-night': ThemePreset('Ambre nocturne', 'dark', ('#30271f','#f4eadb','#211b16','#332b23','#70502b','#ffffff')),
    'rose-night': ThemePreset('Rose nocturne', 'dark', ('#32252e','#f8eaf2','#221a21','#362631','#71405b','#ffffff')),
    'emerald-night': ThemePreset('Émeraude nocturne', 'dark', ('#17332e','#e1f5ed','#10251f','#1a382f','#23634f','#ffffff')),
    'sand': ThemePreset('Sable', 'light', ('#f1eadb','#352c20','#fffdf7','#f7f1e4','#e6d2a7','#352613')),
    'forest': ThemePreset('Forêt', 'dark', ('#25352f','#edf5ef','#182820','#22362b','#345e4b','#ffffff')),
    'contrast-light': ThemePreset('Contraste élevé clair', 'light', ('#ffffff','#000000','#ffffff','#eeeeee','#000000','#ffffff')),
    'contrast-dark': ThemePreset('Contraste élevé sombre', 'dark', ('#000000','#ffffff','#000000','#181818','#ffff00','#000000')),
}


def effective_palette(preferences):
    preset=THEMES.get(preferences.theme_preset)
    colors=preset.palette() if preset and preset.mode==preferences.theme else {}
    return colors | preferences.theme_palette


def tle_theme(name):
    """Map recognised families explicitly; preserve the fact this is adaptation."""
    value=' '.join(name.casefold().split())
    if 'high contrast' in value or 'contraste' in value:
        return 'contrast-dark' if any(x in value for x in ('dark','black','sombre','noir')) else 'contrast-light'
    if 'visual studio' in value:
        return 'studio-dark' if 'dark' in value else 'studio-light'
    if 'office' in value:
        return 'office-black' if 'black' in value else 'office-dark' if any(x in value for x in ('dark','gray','grey')) else 'office-white'
    if 'blue' in value or 'bleu' in value:return 'classic-blue'
    if 'silver' in value or 'argent' in value:return 'silver'
    return ''
