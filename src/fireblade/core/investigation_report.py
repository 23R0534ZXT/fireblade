"""Standalone, escaped reports from explicit forensic findings."""
from datetime import datetime, timezone
import html
import os
from pathlib import Path
import tempfile
import base64

from fireblade.core.models import View, FilterGroup, OPERATORS
from fireblade.core.paths import protected_destination
from fireblade.core.workspace_reader import WorkspaceReader


class ReportParts(list):
    def __init__(self):super().__init__();self.characters=0
    def append(self, value):
        self.characters += len(value)
        if self.characters > 16 * 1024 * 1024:
            raise ValueError('Rapport trop volumineux ; réduisez le nombre de constats ou de colonnes (16 millions de caractères maximum)')
        super().append(value)


def describe_view(view, headers):
    operators = {code: label for label, code in OPERATORS}
    def condition(item):
        if isinstance(item, FilterGroup):
            values = [condition(child) for child in item.children]
            if item.logic == 'not':return 'NON (' + ' ; '.join(values) + ')'
            return '(' + (' ET ' if item.logic == 'and' else ' OU ').join(values) + ')'
        name = headers[item.column] if 0 <= item.column < len(headers) else {-1:'Ligne source',-2:'Signet',-3:'Note'}.get(item.column,'Colonne '+str(item.column))
        return name + ' ' + operators.get(item.operator,item.operator) + ' ' + item.value
    parts = ['Recherche : ' + view.search] if view.search else []
    parts += [condition(item) for item in view.filters]
    if view.expression is not None:parts.append(condition(view.expression))
    if view.bookmarks_only:parts.append('Signets uniquement')
    return '\n'.join(parts) or 'Aucun filtre'


def build_report(reader: WorkspaceReader, title, description='', *, bookmarks_only=True,
                 respect_filters=True, row_ids=None, limit=2000, timeline=None):
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise ValueError('Titre de rapport requis (500 caractères maximum)')
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('Rapport limité à 1 à 10000 constats')
    escape = lambda value: html.escape('' if value is None else str(value), quote=True)
    result = ReportParts()
    for part in ['<!doctype html><html lang="fr"><head><meta charset="utf-8">',
              '<title>' + escape(title) + '</title><style>',
              'body{font:11pt sans-serif;color:#182333;max-width:1100px;margin:35px auto;padding:20px}',
              'h1{color:#174b73}h2{border-bottom:2px solid #457b9d;padding-top:20px}',
              'table{border-collapse:collapse;width:100%;margin:12px 0;table-layout:fixed}',
              'th,td{border:1px solid #ccd5df;padding:7px;text-align:left;vertical-align:top;overflow-wrap:anywhere}',
              'th{background:#eaf1f7;width:25%}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:10pt monospace}',
              '.note{background:#fff3c4;padding:10px}.warning{color:#8b320c}.muted{color:#4f6074}',
              '@media print{body{margin:0;padding:0}h2{page-break-before:auto}table{page-break-inside:avoid}}',
              '</style></head><body><h1>' + escape(title) + '</h1>',
              '<p>Généré le ' + escape(datetime.now(timezone.utc).isoformat()) + ' · UTC</p>',
              '<pre>' + escape(description) + '</pre>',
              '<p class="muted">Les constats ci-dessous sont des éléments à examiner. Les empreintes sources sont celles enregistrées à l’import ; leur présence ne prouve pas une nouvelle vérification de la source.</p>',
              '<p>Périmètre : ' + ('signets et notes' if bookmarks_only else 'enregistrements') +
              (' · filtres de chaque analyse appliqués' if respect_filters else ' · filtres ignorés') +
              (' · sélection explicite de lignes' if row_ids is not None else '') +
              f' · maximum {limit} constats.</p>']:result.append(part)
    if timeline is not None:
        image = base64.b64decode(timeline['png'], validate=True)
        if len(image) > 2 * 1024 * 1024 or not image.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Capture de chronologie invalide ou trop volumineuse')
        result.append('<h2>Chronologie graphique</h2><p>' + escape(timeline['caption']) + '</p>')
        result.append('<img alt="Vue graphique de la chronologie" width="680" style="max-width:100%;height:auto" src="data:image/png;base64,'+timeline['png']+'">')
    records, errors, remaining = 0, [], limit
    for document in reader.documents:
        reader.check()
        result.append('<h2>' + escape(Path(document.source_info['path']).name) + '</h2>')
        info = document.source_info
        result.append('<table>' + ''.join('<tr><th>' + escape(label) + '</th><td><pre>' + escape(value) + '</pre></td></tr>'
                      for label, value in [('Analyse', document.path), ('Source', info['path']),
                                           ('SHA-256 à l’import', info.get('sha256', 'Indisponible')),
                                           ('Taille source', info.get('size', 'Indisponible')),
                                           ('Lignes importées', info.get('rows', 'Indisponible')),
                                           ('Filtres appliqués', describe_view(document.view, info.get('headers',[])) if respect_filters else 'Aucun filtre')]) + '</table>')
        try:
            with reader.open(document) as case:
                view = document.view if respect_filters else View()
                where, args = case.where(view)
                clauses = []
                if bookmarks_only:clauses.append('events.__row_id IN (SELECT row_id FROM bookmarks)')
                if row_ids is not None:
                    ids = row_ids.get(document.path, [])
                    if len(ids) > 10000 or any(type(i) is not int or i < 1 for i in ids):
                        raise ValueError('Sélection du rapport invalide')
                    clauses.append('events.__row_id IN (SELECT unnest(?::BIGINT[]))');args.append(ids)
                if clauses:where += (' AND ' if where else ' WHERE ') + ' AND '.join(clauses)
                count = case.db.execute('SELECT count(*) FROM events' + where, args).fetchone()[0]
                result.append(f'<p>{count} correspondance(s) dans cette analyse.</p>')
                cursor = case.db.execute('SELECT events.*, (SELECT note FROM bookmarks b WHERE b.row_id=events.__row_id) '
                                         'FROM events' + where + ' ORDER BY __row_id LIMIT ?', args + [remaining])
                included = 0
                while row := cursor.fetchone():
                    reader.check()
                    included += 1
                    result.append('<h3>Enregistrement source nº ' + str(row[0]) + '</h3>')
                    if row[-1] is not None:result.append('<pre class="note">Note : ' + escape(row[-1]) + '</pre>')
                    result.append('<table>')
                    for name, value in zip(case.headers, row[1:-1]):
                        value = '∅' if value is None else str(value)
                        if len(value) > 20000:value = value[:20000] + '\n[Valeur abrégée dans le rapport ; valeur complète dans l’analyse.]'
                        result.append('<tr><th>' + escape(name) + '</th><td><pre>' + escape(value) + '</pre></td></tr>')
                    result.append('</table>')
                records += included;remaining -= included
                if count > included:result.append('<p class="warning">Résultats partiels : limite du rapport atteinte. Les autres constats restent dans les analyses.</p>')
        except Exception as exc:
            from fireblade.core.errors import OperationCancelled
            if isinstance(exc, OperationCancelled):raise
            errors.append(str(exc));result.append('<p class="warning">Analyse non incluse : ' + escape(exc) + '</p>')
    result.append(f'<hr><p>{records} constat(s) inclus · {len(errors)} analyse(s) en erreur.</p></body></html>')
    reader.check()
    return dict(html='\n'.join(result), records=records, errors=errors)


def write_report(target, report, documents, *, pdf=False):
    target = Path(target).resolve()
    protected = [doc.path for doc in documents] + [doc.source_info['path'] for doc in documents]
    if protected_destination(target, protected):raise ValueError('Le rapport ne peut pas écraser une analyse ou sa source')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.partial', delete=False) as stream:
            temporary = Path(stream.name)
            if not pdf:stream.write(report['html'].encode('utf-8'))
        if pdf:
            from PySide6.QtCore import QMarginsF, QSizeF
            from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument, QTextOption
            writer,document=None,None
            try:
                writer = QPdfWriter(str(temporary))
                writer.setResolution(72)  # Document geometry and PDF points share one unit.
                writer.setPageSize(QPageSize(QPageSize.A4));writer.setPageMargins(QMarginsF(12, 12, 12, 12))
                writer.setTitle('Fireblade — rapport d’investigation');writer.setCreator('Fireblade')
                document = QTextDocument()
                option=document.defaultTextOption();option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere);document.setDefaultTextOption(option)
                # QTextDocument does not apply browser @media print rules.
                page_width=round(writer.width()*96/72)  # HTML image dimensions use CSS pixels.
                pdf_html=report['html'].replace('<body>','<body style="margin:0;padding:0">').replace('width="680"',f'width="{page_width}"')
                document.setHtml(pdf_html)
                document.documentLayout().setPaintDevice(writer)
                document.setPageSize(QSizeF(writer.width(),writer.height()))
                document.setDocumentMargin(0)
                frame=document.rootFrame().frameFormat();frame.setMargin(0);frame.setPadding(0);document.rootFrame().setFrameFormat(frame)
                document.print_(writer)
            finally:
                # Release the Windows file handle before deleting/replacing it,
                # including when rendering fails partway through.
                del document, writer
            with temporary.open('rb') as stream:
                header=stream.read(5);stream.seek(max(0,temporary.stat().st_size-1024));trailer=stream.read()
            if header!=b'%PDF-' or not trailer.rstrip().endswith(b'%%EOF'):
                raise ValueError('Création du PDF impossible ou document incomplet')
        from fireblade.core.case_package import check_cancelled
        check_cancelled();os.replace(temporary, target)
        return str(target)
    finally:
        if temporary:temporary.unlink(missing_ok=True)
