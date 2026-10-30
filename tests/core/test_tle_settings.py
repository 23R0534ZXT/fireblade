import pytest
from fireblade.core.tle_settings import read_tle_settings
from fireblade.core.timestamps import format_timestamp
from fireblade.core.preferences import Preferences,save_preferences,load_preferences


def test_documented_tle_settings_import_preserves_their_preferences(tmp_path):
    source=tmp_path/'TLE_settings.xml'
    source.write_text('''<Settings xmlns="http://schemas.datacontract.org/2004/07/TimelineExplorer.Classes">
    <CopyColumnHeaders>false</CopyColumnHeaders><CopyRightClick>true</CopyRightClick>
    <DateTimeFormat>yyyy-MM-dd HH:mm:ss.fffffffK</DateTimeFormat><DetailsOnTop>true</DetailsOnTop>
    <FirstPinnedColumns xmlns:a="http://schemas.microsoft.com/2003/10/Serialization/Arrays"><a:string>TimeCreated</a:string><a:string>EventId</a:string></FirstPinnedColumns>
    <FontName>Consolas</FontName><FontSize>12.5</FontSize><MultilineTabs>true</MultilineTabs><Theme>Office 2019 Black</Theme>
    <FutureSetting>unchanged</FutureSetting></Settings>''')
    before=source.read_bytes();result=read_tle_settings(source)
    p=result.preferences
    assert not p.copy_headers and p.right_click_copy and p.multiline_tabs
    assert p.font_family=='Consolas' and p.font_size==12.5 and p.theme=='dark'
    assert p.details_position=='top' and p.first_pinned_columns==['TimeCreated','EventId']
    assert len(result.warnings)==2 and source.read_bytes()==before
    save_preferences(p,tmp_path/'p.json');assert load_preferences(tmp_path/'p.json')==p
    assert format_timestamp('2026-01-02T01:02:03.123456789+02:00',p.custom_date_format)=='2026-01-02 01:02:03.123456789+02:00'


@pytest.mark.parametrize('value',["<Settings><CopyRightClick>yes</CopyRightClick></Settings>","<!DOCTYPE x><Settings/>","<Settings><FontSize>NaN</FontSize></Settings>","<Settings><DateTimeFormat>yyyy q</DateTimeFormat></Settings>","<Settings><FontSize>10</FontSize><FontSize>11</FontSize></Settings>"])
def test_invalid_tle_settings_do_not_mutate_existing_preferences(tmp_path,value):
    source=tmp_path/'TLE_settings.xml';source.write_text(value)
    current=Preferences()
    with pytest.raises(ValueError):read_tle_settings(source,current)
    assert current==Preferences()


def test_custom_date_pattern_keeps_literal_and_source_offset():
    value='2026-01-02T13:04:05.1234567Z'
    assert format_timestamp(value,"dd/MM/yyyy 'at' hh:mm:ss.fffffff tt zzz")=='02/01/2026 at 01:04:05.1234567 PM +00:00'
    assert format_timestamp('invalid','yyyy-MM-dd')=='invalid'
