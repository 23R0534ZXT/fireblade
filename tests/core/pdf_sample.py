"""A PDF built by hand, so the PDF tests depend on no writer library."""


def build_pdf(text="Paiement du 14/11/2026 confirmé", pages=1, page_size=(240, 200)):
    """A valid PDF with one text object per page, or pages with no text layer.

    `text` may be a single string (repeated), a list of per-page strings, or None
    for pages with no text layer at all. The object offsets are computed as the file
    is written, so the cross-reference table is correct and a reader has no reason
    to repair anything.
    """
    width, height = page_size
    bodies = list(text) if isinstance(text, (list, tuple)) else [text] * pages
    count = len(bodies)
    font_number = 3 + 2 * count
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            "<< /Type /Pages /Kids ["
            + " ".join("%d 0 R" % (3 + index) for index in range(count))
            + "] /Count %d >>" % count
        ).encode("ascii"),
    ]
    for number in range(count):
        _page, stream = 3 + number, 3 + count + number
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources "
                "<< /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (width, height, font_number, stream)
            ).encode("ascii")
        )
    for body in bodies:
        if body is None:
            objects.append(b"<< /Length 0 >>\nstream\n\nendstream")
        else:
            stream = b"BT /F1 12 Tf 20 150 Td (" + body.encode("cp1252") + b") Tj ET"
            objects.append(
                b"<< /Length "
                + str(len(stream)).encode("ascii")
                + b" >>\nstream\n"
                + stream
                + b"\nendstream"
            )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(number).encode("ascii") + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += ("%010d 00000 n \n" % offset).encode("ascii")
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref).encode("ascii")
        + b"\n%%EOF\n"
    )
    return bytes(out)
