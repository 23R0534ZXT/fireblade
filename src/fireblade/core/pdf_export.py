"""HTML to PDF with Qt, when a document has to be handed over as a file.

The conversion needs a live QGuiApplication and is therefore called from a worker
thread only through ``QTextDocument``, which Qt documents as usable off the main
thread for this purpose. Both the investigation report and the destruction
certificate write their HTML first and convert the same string here, so the two
documents cannot drift apart in page geometry or font handling.
"""

from pathlib import Path


def html_to_pdf(html, target, *, title="Fireblade", creator="Fireblade"):
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument, QTextOption

    target = Path(target)
    writer, document = None, None
    try:
        writer = QPdfWriter(str(target))
        writer.setResolution(72)  # Document geometry and PDF points share one unit.
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setPageMargins(QMarginsF(12, 12, 12, 12))
        writer.setTitle(title)
        writer.setCreator(creator)
        document = QTextDocument()
        option = document.defaultTextOption()
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(option)
        # QTextDocument does not apply browser @media print rules.
        page_width = round(writer.width() * 96 / 72)  # HTML image dimensions use CSS pixels.
        pdf_html = html.replace("<body>", '<body style="margin:0;padding:0">')
        # QTextDocument has no page palette: without explicit colours the text of a
        # dark-themed session is printed dark on dark.
        compat = (
            "<style>body,p,td,th,li,pre,div,span{color:#182333;background-color:#ffffff;}"
            "h1,h2,h3{color:#174b73;}table{border-collapse:collapse;}</style>"
        )
        pdf_html = (
            pdf_html.replace("</head>", compat + "</head>", 1)
            if "</head>" in pdf_html
            else compat + pdf_html
        )
        pdf_html = pdf_html.replace('width="680"', f'width="{page_width}"')
        pdf_html = pdf_html.replace('width="960"', f'width="{page_width}"')
        document.setHtml(pdf_html)
        document.documentLayout().setPaintDevice(writer)
        document.setPageSize(QSizeF(writer.width(), writer.height()))
        document.setDocumentMargin(0)
        frame = document.rootFrame().frameFormat()
        frame.setMargin(0)
        frame.setPadding(0)
        document.rootFrame().setFrameFormat(frame)
        document.print_(writer)
    finally:
        # Release the Windows file handle before deleting/replacing it, including
        # when rendering fails partway through.
        del document, writer
    with open(target, "rb") as stream:
        header = stream.read(5)
        stream.seek(max(0, target.stat().st_size - 1024))
        trailer = stream.read()
    if header != b"%PDF-" or not trailer.rstrip().endswith(b"%%EOF"):
        raise ValueError("PDF creation failed or the document is incomplete")
