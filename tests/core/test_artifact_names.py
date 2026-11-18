"""The tree label: what the evidence is, not the path it was saved under."""
from fireblade.core.artifact_names import friendly_label, kind_of, unique_labels

# Shaped like a real Magnet RESPONSE / KAPE export, which is where the trees are unreadable.
ROOT = r'C:\Users\OCD\Desktop\Malware\OCD_artefacts_collection-MagnetRESPONSE-2025.06.02_16.25.52\FORENSIC_LAB_OCD_2025.06.02_16.25.52\Saved_Files'


def test_a_known_artefact_is_named_by_what_it_is():
    assert friendly_label(ROOT + r'\Amcache\C\Windows\AppCompat\Programs\Amcache.hve') == 'Amcache'
    assert friendly_label(ROOT + r'\MFT\C\$MFT') == 'MFT'
    assert friendly_label(ROOT + r'\NTUSER.DAT\C\Users\OCD\NTUSER.DAT') == 'NTUSER.DAT'
    assert friendly_label(ROOT + r'\Browser_History\C\Users\OCD\AppData\Local\Microsoft\Edge\User Data\Default\Top Sites') == 'Browser history'


def test_an_event_log_carries_its_channel():
    path = ROOT + r'\Windows_Event_Logs\C\Windows\System32\winevt\Logs\Security.evtx'
    assert friendly_label(path) == 'Event logs'
    assert unique_labels([path])[path] == 'Event logs'


def test_two_event_logs_are_told_apart_by_their_file_names():
    paths = [ROOT + r'\Windows_Event_Logs\C\Windows\System32\winevt\Logs\%s.evtx' % name
             for name in ('Security', 'System', 'Application')]
    labels = unique_labels(paths)
    assert labels[paths[0]] == 'Event logs · Security'
    assert labels[paths[1]] == 'Event logs · System'
    assert labels[paths[2]] == 'Event logs · Application'


def test_the_folder_name_is_used_when_nothing_is_recognised():
    assert friendly_label(ROOT + r'\Unknown_Export\C\Users\OCD\notes.dat') == 'Unknown_Export'
    assert friendly_label(ROOT + r'\Unknown_Export\export.bin') == 'Unknown_Export'
    # A known database keeps its own name, not the format it happens to use.
    assert friendly_label(ROOT + r'\Browser_History\C\Users\OCD\AppData\Roaming\Mozilla\Firefox\Profiles\9nxwbqjt.default-release\cookies.sqlite') == 'Browser cookies'


def test_a_folder_source_is_named_after_the_folder_itself():
    assert friendly_label(ROOT + r'\Windows_Event_Logs') == 'Event logs'
    assert friendly_label(ROOT + r'\Some_Collector_Output') == 'Some_Collector_Output'


def test_the_saved_files_container_is_never_the_label():
    assert friendly_label(ROOT + r'\Saved_Files\Amcache') == 'Amcache'
    assert friendly_label(ROOT) == 'FORENSIC_LAB_OCD_2025.06.02_16.25.52'


def test_two_unknown_files_in_the_same_folder_keep_their_own_names():
    first = ROOT + r'\Exports\a.bin'
    second = ROOT + r'\Exports\b.bin'
    labels = unique_labels([first, second])
    # Two rows that would read "Exports" are told apart by the file, not by a number.
    assert (labels[first], labels[second]) == ('a.bin', 'b.bin')


def test_kind_of_answers_only_for_known_evidence():
    assert kind_of(ROOT + r'\Prefetch_Files\C\Windows\Prefetch\CMD.EXE-1234.pf') == 'Prefetch'
    assert kind_of(ROOT + r'\JumpLists-AutomaticDestinations\C\Users\OCD\1a2b.automaticdestinations-ms') == 'Jump lists'
    assert kind_of(ROOT + r'\Exports\a.bin') == ''
    assert kind_of('') == ''

def test_an_export_named_after_its_artefact_is_recognised():
    """`Prefetch.csv` in a temp folder is still a Prefetch export."""
    assert friendly_label(r'C:\temp\pytest-0\Prefetch.csv') == 'Prefetch'
    assert friendly_label(r'C:\temp\pytest-0\Browser_History.csv') == 'Browser history'

def test_generic_files_sharing_a_folder_are_named_by_their_file():
    """Six exports in one folder must not read "resume (1) ... resume (6)"."""
    paths = [r'C:\cases\x\Collectes\interrupted\resume\r%d.csv' % index for index in range(6)]
    labels = unique_labels(paths)
    assert sorted(labels.values()) == ['r0.csv', 'r1.csv', 'r2.csv', 'r3.csv', 'r4.csv', 'r5.csv']
