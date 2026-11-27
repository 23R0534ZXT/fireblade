"""The destruction certificate handed to the client, and its attachments.

The record produced by :mod:`fireblade.core.destruction` is the evidence; this module
turns it into the document that is signed. It is deliberately plain: no colour coding
that a black-and-white print would lose, every file listed individually, and the
limitations paragraph printed in full rather than as a footnote.

Photographs and screenshots are copied into the case first and fingerprinted, so the
certificate's annex cannot be swapped for another image afterwards without the
SHA-256 recorded here disagreeing.
"""

import base64
import hashlib
import html
import shutil
from datetime import UTC, datetime
from pathlib import Path

MAX_ATTACHMENTS = 20
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"RIFF", "image/webp"),
)


class _Parts(list):
    def __init__(self):
        super().__init__()
        self.characters = 0

    def append(self, value):
        self.characters += len(value)
        if self.characters > MAX_TOTAL_BYTES:
            raise ValueError(
                "The certificate is too large; reduce the number or size of attachments"
            )
        super().append(value)


def store_attachments(case_folder, paths, captions=None):
    """Copy photos into ``<case>/destruction/attachments`` and fingerprint them."""
    folder = Path(case_folder) / "destruction" / "attachments"
    folder.mkdir(parents=True, exist_ok=True)
    stored = []
    captions = list(captions or [])
    for index, value in enumerate(paths):
        if len(stored) >= MAX_ATTACHMENTS:
            raise ValueError(f"At most {MAX_ATTACHMENTS} attachments are allowed")
        source = Path(value)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"{source} is not a regular file")
        data = source.read_bytes()
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise ValueError(f"{source.name} exceeds 8 MiB; compress or crop it")
        mime = next((kind for magic, kind in IMAGE_MAGIC if data.startswith(magic)), None)
        if mime is None:
            raise ValueError(f"{source.name} is not a PNG, JPEG or WebP image")
        name = f"{index + 1:02d}-" + re_safe(source.name)
        target = folder / name
        target.write_bytes(data)
        stored.append(
            dict(
                name=name,
                path=str(target),
                relative="destruction/attachments/" + name,
                sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
                mime=mime,
                caption=(captions[index] if index < len(captions) else source.stem)[:300],
            )
        )
    return stored


def re_safe(name):
    cleaned = "".join(char for char in name if char.isalnum() or char in "._- ")
    return cleaned.strip() or "attachment.png"


def short_path(value):
    """The end of a path, so a table row stays on one line; the appendix keeps it whole."""
    text = str(value or "")
    if len(text) <= 30:
        return text
    return "…/" + text[-28:]


def short_digest(value):
    """Enough of a hash to compare two rows by eye; the full value lives in the appendix."""
    text = str(value or "")
    if len(text) <= 20:
        return text or "—"
    return text[:12] + "…" + text[-6:]


def _escape(value):
    return html.escape("" if value is None else str(value), quote=True)


def build(
    record, *, case_name="", case_id="", client=None, generated=None, case_folder=None, images=None
):
    """The certificate as one HTML document, attachments embedded as data URIs.

    ``images`` maps an attachment's SHA-256 to its bytes: a destruction reads the photos
    before the annex holding them goes with the residue, so the document still embeds them.
    """
    client = client or {}
    if case_folder:
        from fireblade.core.case_workspace import data_folder

        case_folder = data_folder(case_folder)
    escape = _escape
    parts = _Parts()
    for part in [
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">',
        "<title>Procès-verbal de destruction — " + escape(case_name or case_id) + "</title><style>",
        'body{font:11pt "Segoe UI",Arial,sans-serif;color:#182333;background:#ffffff;max-width:1000px;margin:35px auto;padding:24px}',
        "h1{color:#5b1c1c;border-bottom:3px solid #5b1c1c;padding-bottom:10px;margin-bottom:4px}",
        "h2{color:#174b73;border-bottom:1px solid #b8c6d4;padding-top:18px;font-size:13pt}",
        ".lead{font-size:12pt;margin:14px 0 4px}",
        ".muted{color:#4f6074;font-size:9.5pt}",
        "table{border-collapse:collapse;width:100%;margin:10px 0;table-layout:fixed}",
        "th,td{border:1px solid #ccd5df;padding:6px;text-align:left;vertical-align:top;",
        "overflow-wrap:anywhere;font-size:9.5pt}",
        "th{background:#eef3f8;width:22%}",
        "thead th{width:auto;background:#dde7f0}",
        ".ok{color:#1d6b2f;font-weight:bold}.ko{color:#8b320c;font-weight:bold}",
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:9pt monospace;margin:0}",
        ".sign{display:flex;gap:24px;margin-top:26px}.sign div{flex:1;border-top:1px solid #333;padding-top:6px}",
        "table.annex{width:100%}table.annex td{border:1px solid #ccd5df;padding:6px;vertical-align:top;width:50%}",
        "table.annex img{max-width:100%;height:auto}",
        ".annex .cap{font-size:8.5pt;color:#4f6074;margin-top:4px}",
        "tr{page-break-inside:avoid}",
        "thead{display:table-header-group}",
        ".digest{margin:6px 0;font-size:8.5pt}.digest code{font:8.5pt monospace;overflow-wrap:anywhere}",
        "@media print{body{margin:0;padding:0}h2{page-break-after:avoid}}",
        "</style></head><body>",
        "<h1>Procès-verbal de destruction de preuves</h1>",
        '<p class="lead">Case : '
        + escape(case_name or "—")
        + " · Référence : "
        + escape(case_id or "—")
        + "</p>",
    ]:
        parts.append(part)
    parts.append(
        "<table>"
        + "".join(
            "<tr><th>" + escape(label) + "</th><td>" + escape(value) + "</td></tr>"
            for label, value in (
                ("Client", client.get("name") or "—"),
                ("Référence client", client.get("reference") or "—"),
                ("Méthode", record.get("label", record.get("method", ""))),
                ("Passes", record.get("passes", "")),
                ("Opérateur", record.get("operator") or "—"),
                ("Témoin", record.get("witness") or "—"),
                ("Motif / base légale", record.get("reason") or "—"),
                ("Début (UTC)", record.get("started") or "—"),
                ("Fin (UTC)", record.get("finished") or "—"),
                (
                    "Statut",
                    "Complet"
                    if record.get("status") == "complete"
                    else "Partiel — voir la colonne État",
                ),
                ("Volume traité", f"{record.get('bytes', 0):,}".replace(",", " ") + " octets"),
            )
        )
        + "</table>"
    )
    quick = record.get("method") == "quick"
    parts.append("<h2>1. Deleted files</h2>" if quick else "<h2>1. Fichiers détruits</h2>")
    files = record.get("files", [])
    if not files:
        parts.append('<p class="ko">Aucun fichier n\'a été détruit.</p>')
    else:
        parts.append(
            "<table><thead><tr><th>Fichier</th><th>Taille</th><th>État</th></tr></thead><tbody>"
        )
        for item in files:
            state = item.get("state")
            if state == "deleted" and item.get("deleted"):
                label, css = "Deleted without overwrite", "ok"
            elif state == "destroyed" and item.get("verified"):
                label, css = "détruit et vérifié", "ok"
            else:
                label, css = "ÉCHEC : " + str(item.get("error") or state), "ko"
            parts.append(
                "<tr><td>" + escape(short_path(item.get("relative") or item.get("path"))) + "</td>"
                "<td>" + escape(f"{item.get('size', 0):,}".replace(",", " ")) + "</td>"
                '<td class="' + css + '">' + escape(label) + "</td></tr>"
            )
        parts.append("</tbody></table>")
    if files and not quick:
        # The table has to stay readable: the full hashes go to an appendix, one per line.
        parts.append(
            '<p class="muted">Empreintes abrégées dans le tableau ; les valeurs complètes '
            "figurent en annexe, pour les mêmes fichiers.</p>"
        )
        parts.append("<h2>2. Empreintes complètes</h2>")
        # Paragraphs, not table rows: a paragraph breaks between lines, a tall row does not.
        for item in files:
            started = str(item.get("started") or "")[11:19]
            finished = str(item.get("finished") or "")[11:19]
            parts.append(
                '<p class="digest"><b>'
                + escape(item.get("relative") or item.get("path"))
                + "</b><br>"
                + escape((started + " → " + finished) if started else "—")
                + " · "
                + escape(f"{item.get('size', 0):,}".replace(",", " "))
                + " octets<br>"
                "avant : <code>" + escape(item.get("sha256_before") or "—") + "</code><br>"
                "après : <code>" + escape(item.get("sha256_after") or "—") + "</code></p>"
            )
    removed = sum(1 for item in files if item.get("deleted"))
    if quick:
        parts.append(f"<p>{removed} of {len(files)} listed file(s) deleted.</p>")
    else:
        parts.append(
            f"<p>{removed} fichier(s) détruit(s) sur {len(files)} listé(s) · "
            f"{len({item.get('sha256_before') for item in files})} empreinte(s) distincte(s).</p>"
        )
    attachments = record.get("attachments") or []
    if attachments:
        parts.append("<h2>3. Annexes photographiques</h2>")
        cells = []
        for item in attachments:
            # The bytes were read before the annex disappeared, when it did; otherwise
            # read them here. A portable case moves the folder, so the recorded
            # relative path wins over the absolute one taken on the destroying machine.
            data = (images or {}).get(item.get("sha256"))
            if data is None:
                source = (
                    Path(case_folder) / item["relative"]
                    if case_folder and item.get("relative")
                    else Path(item.get("path", ""))
                )
                try:
                    data = source.read_bytes()
                except OSError:
                    cells.append(
                        '<p class="ko">Photo illisible : ' + escape(item.get("name")) + "</p>"
                    )
                    continue
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                cells.append(
                    '<p class="ko">Photo modifiée depuis son enregistrement : '
                    + escape(item.get("name"))
                    + " — non incluse.</p>"
                )
                continue
            cells.append(
                '<td><img alt="'
                + escape(item.get("caption"))
                + '" src="data:'
                + escape(item.get("mime", "image/png"))
                + ";base64,"
                + base64.b64encode(data).decode("ascii")
                + '">'
                '<div class="cap">'
                + escape(item.get("caption"))
                + "<br>SHA-256 : "
                + escape(item["sha256"])
                + "</div></td>"
            )
        if cells:
            parts.append('<table class="annex">')
            for start in range(0, len(cells), 2):
                parts.append("<tr>" + "".join(cells[start : start + 2]) + "</tr>")
            parts.append("</table>")
    parts.append(
        "<h2>4. Portée et limites</h2><p>" + escape(record.get("limitations", "")) + "</p>"
    )
    parts.append(
        "<h2>5. Signatures</h2>"
        '<p class="muted">Chaque signataire atteste avoir assisté à l\'opération décrite ci-dessus.</p>'
        '<div class="sign"><div>Opérateur<br>' + escape(record.get("operator") or "") + "</div>"
        "<div>Témoin<br>" + escape(record.get("witness") or "") + "</div>"
        "<div>Représentant du client<br>" + escape(client.get("contact") or "") + "</div></div>"
    )
    generated = generated or datetime.now(UTC).isoformat()
    parts.append(
        '<hr><p class="muted">Document généré par Fireblade le '
        + escape(generated)
        + " (UTC). Identifiant de l'opération : "
        + escape(record.get("id") or "—")
        + ".</p>"
        "</body></html>"
    )
    return dict(
        html="\n".join(parts),
        files=len(files),
        destroyed=0 if quick else removed,
        attachments=len(attachments),
    )


def write(target, document, *, pdf=False):
    """Write the certificate next to the case, atomically."""
    target = Path(target)
    temporary = target.with_name(target.name + ".partial")
    try:
        if pdf:
            from fireblade.core.pdf_export import html_to_pdf

            html_to_pdf(document["html"], temporary, title="Procès-verbal de destruction")
        else:
            temporary.write_text(document["html"], encoding="utf-8")
        try:
            temporary.replace(target)
        except PermissionError:
            target.unlink(missing_ok=True)
            temporary.replace(target)
        return str(target)
    finally:
        temporary.unlink(missing_ok=True)


def copy_into(target_folder, source):
    """Move a generated certificate into the case's destruction folder with its name."""
    target_folder = Path(target_folder)
    target_folder.mkdir(parents=True, exist_ok=True)
    destination = target_folder / Path(source).name
    shutil.copy2(source, destination)
    return destination
