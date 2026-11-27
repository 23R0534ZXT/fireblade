"""Editable incident intake and destruction records derived from case facts."""

from io import BytesIO
from os import environ

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FIELDS = {
    "discovered": "Discovery time (ISO date/time)",
    "severity": "Severity",
    "incident_type": "Type",
    "description": "What happened?",
    "objectives": "Investigation objectives",
    "impact": "Affected assets and business impact",
    "containment": "Containment already performed",
    "requested": "Evidence to acquire",
    "infrastructure": "Infrastructure and exposure",
}


def document(title, setting):
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    path = environ.get(setting)
    try:
        doc = Document(path) if path else Document()
    except PackageNotFoundError as exc:
        raise ValueError(
            f"The template configured by {setting} is unavailable or invalid."
        ) from exc
    if path:
        doc.element.body.clear_content()
    doc.core_properties.title = title
    doc.add_paragraph(title, style="Title" if "Title" in doc.styles else None)
    return doc


def heading(doc, label):
    doc.add_paragraph(label, style="Heading 1" if "Heading 1" in doc.styles else None)


def table(doc, rows):
    from re import compile

    illegal = compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")

    grid = doc.add_table(rows=0, cols=len(rows[0]))
    if "Table Grid" in doc.styles:
        grid.style = "Table Grid"
    for row in rows:
        for cell, value in zip(grid.add_row().cells, row, strict=True):
            cell.text = illegal.sub("", str(value if value is not None else ""))


def serialize(doc):
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


def intake(name, data):
    from fireblade.web.tracking import event_summary, selected_events

    doc = document("Formulaire de réponse à incident", "FIREBLADE_IR_TEMPLATE")
    doc.add_paragraph(name)
    client = data["client"]
    context = data.get("incident_context", {})
    for title, rows in (
        (
            "Récapitulatif et contacts",
            [
                ("Organisation", client.get("name")),
                ("Référence", client.get("reference")),
                ("Contact", client.get("contact")),
                ("Date de découverte", context.get("discovered")),
                ("Type d’incident", context.get("incident_type")),
                ("Sévérité", context.get("severity")),
            ],
        ),
        (
            "Description, objectifs et périmètre",
            [
                ("Description", context.get("description")),
                ("Objectifs", context.get("objectives")),
                ("Impact", context.get("impact")),
                ("Endiguement", context.get("containment")),
                ("Infrastructure", context.get("infrastructure")),
                ("Éléments à récupérer", context.get("requested")),
            ],
        ),
        (
            "Liste des actifs suspects",
            [("Actif", "Type", "Observations")]
            + [(e["label"], e["kind"], e.get("notes")) for e in data["entities"]],
        ),
        (
            "Chronologie",
            [("Date et heure", "Machine", "Description")]
            + [(e["time"], e["machine"], event_summary(e)) for e in selected_events(data)],
        ),
    ):
        heading(doc, title)
        table(doc, rows)
    return serialize(doc)


def destruction(record, client, images, *, doc=None):
    from docx.shared import Inches

    if doc is None:
        doc = document("Procès-verbal de destruction des données", "FIREBLADE_DESTRUCTION_TEMPLATE")
    heading(doc, "Référence du document")
    table(
        doc,
        [
            ("Identifiant", record["id"]),
            ("Dossier", record.get("case_name")),
            ("Organisation", client.get("name")),
            ("Référence client", client.get("reference")),
            ("Méthode", record.get("label") or record.get("method")),
            ("Passes", str(record.get("passes", ""))),
            ("Motif", record.get("reason")),
            ("Début et fin (UTC)", f"{record.get('started', '')} / {record.get('finished', '')}"),
            ("Statut", record.get("status")),
        ],
    )
    heading(doc, "Détail des opérations")
    doc.add_paragraph(record.get("limitations") or "")
    table(
        doc,
        [("Élément", "Octets", "Résultat", "SHA-256 avant / après")]
        + [
            (
                item.get("relative") or item.get("path"),
                item.get("size"),
                "Vérifié et supprimé"
                if item.get("verified") and item.get("deleted")
                else "Supprimé sans réécriture"
                if item.get("deleted")
                else item.get("error") or item.get("state"),
                f"{item.get('sha256_before') or '—'} / {item.get('sha256_after') or '—'}",
            )
            for item in record["files"]
        ],
    )
    if images:
        from docx.image.exceptions import UnrecognizedImageError

        heading(doc, "Annexes photographiques")
        for item in record.get("attachments", []):
            digest = item.get("sha256")
            if digest in images:
                doc.add_paragraph(f"{item.get('caption') or item.get('name')} · SHA-256 {digest}")
                try:
                    doc.add_picture(BytesIO(images[digest]), width=Inches(4.5))
                except UnrecognizedImageError:
                    doc.add_paragraph("Photographie disponible dans le procès-verbal HTML.")
    heading(doc, "Signatures")
    table(
        doc,
        [
            ("Rôle", "Nom", "Signature"),
            ("Opérateur", record.get("operator"), ""),
            ("Témoin", record.get("witness"), ""),
            ("Représentant du client", client.get("contact"), ""),
        ],
    )
    return serialize(doc)


def destruction_writer(certificate, reported, folder):
    """Prepare Word export before erasure, preserving the verified HTML on export error."""
    from fireblade.core.case_workspace import load

    client = load(folder)["client"]
    template = document(
        "Procès-verbal de destruction des données", "FIREBLADE_DESTRUCTION_TEMPLATE"
    )
    word = certificate.with_suffix(".docx")

    def write(record, images):
        from uuid import uuid4

        temporary = word.with_name(f".{word.name}.{uuid4().hex}.partial")
        try:
            temporary.write_bytes(destruction(record, client, images, doc=template))
            temporary.replace(word)
            record["certificate_word"] = str(reported.with_suffix(".docx"))
        except Exception as exc:  # The verified HTML record has already been written.
            record["certificate_word_error"] = str(exc)
        finally:
            temporary.unlink(missing_ok=True)

    return write
