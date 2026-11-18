from datetime import datetime, timezone

from fireblade.core.client_report import build, write
from fireblade.core.findings import Group


def group(title='Encoded PowerShell', host='SRV01', level='critical', start=None):
    return Group(key=title, title=title, level=level, host=host, channel='PowerShell',
                 event_ids=('4104',), tactics='Execution', techniques='T1059.001 PowerShell',
                 rule_id='r', rule_file='f', start=start or datetime(2026, 11, 10, 8, tzinfo=timezone.utc),
                 end=start or datetime(2026, 11, 10, 8, 3, tzinfo=timezone.utc), count=12,
                 details='powershell -enc ...')


def workspace():
    return dict(client=dict(name='ACME', reference='REF-2026-7', sector='Industrie', contact='M. Client'),
                engagement=dict(contract='CT-9', lead='M. Martin', start='2026-11-01',
                                end='2026-11-20', notes='Périmètre : siège et deux serveurs.'),
                entities=[dict(kind='machine', label='SRV01', hostname='SRV01', ip='10.0.0.5',
                               os='Windows Server 2022', tags=['critique'])],
                actions=[dict(title='Réinitialiser les comptes', machine='SRV01', owner='client',
                              status='waiting_client', priority='high', due='2026-11-25', reference='JIRA-1'),
                         dict(title='Clore l\'accès distant', machine='SRV01', owner='us',
                              status='done', priority='medium', due=None, reference='')],
                iocs=[dict(kind='domain', value='exemple.fr', status='confirmed', machine='SRV01',
                           label='C2 suspecté', source='analyse DNS')],
                graph=dict(nodes=[], edges=[]), destruction=[])


def test_the_report_covers_every_section_a_client_expects():
    document = build(title='Rapport d\'investigation', case_name='Affaire ACME', case_id='a'*32,
                     workspace=workspace(), documents=[], findings=[group()],
                     incidents=[], destruction=[], analyst='Maxime',
                     graph_png='iVBORw0KGgo=')
    html = document['html']
    for heading in ('1. Synthèse', '2. Périmètre et preuves', '3. Chronologie', '4. Constats détaillés',
                    '5. Graphe d\'attaque', '6. Indicateurs suivis', '7. Actions et suivi',
                    '8. Devenir des preuves', '9. Méthode et limites'):
        assert heading in html
    assert 'ACME' in html and 'REF-2026-7' in html and 'SRV01' in html
    assert 'Réinitialiser les comptes' in html and 'En attente du client' in html
    assert 'exemple.fr' in html and 'C2 suspecté' in html
    assert document['counts']['critical'] == 1 and document['open_actions'] == 1


def test_the_report_escapes_client_text_and_still_writes_a_file(tmp_path):
    data = workspace()
    data['client']['name'] = 'ACME <script>alert(1)</script>'
    data['actions'][0]['title'] = '" onmouseover="alert(2)'
    document = build(title='Rapport', workspace=data, findings=[], incidents=[])
    assert '<script>alert(1)</script>' not in document['html']
    assert '&lt;script&gt;' in document['html']
    target = tmp_path/'rapport.html'
    write(target, document)
    assert 'ACME' in target.read_text(encoding='utf-8')


def test_an_empty_case_still_produces_a_report_that_says_what_is_missing():
    document = build(title='Rapport', workspace={}, findings=[], incidents=[])
    html = document['html']
    assert 'Aucune analyse importée' in html
    assert 'Aucune action n\'est consignée' in html
    assert 'Aucun indicateur' in html
    assert 'Aucune destruction' in html


def test_the_report_pdf_is_a_real_pdf(tmp_path):
    document = build(title='Rapport', workspace=workspace(), findings=[group()])
    target = tmp_path/'rapport.pdf'
    write(target, document, pdf=True)
    assert target.read_bytes().startswith(b'%PDF-')
