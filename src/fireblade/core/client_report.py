"""The report a client receives: everything the analyst recorded, in one document.

Different from :mod:`fireblade.core.investigation_report`, which lists evidence rows for
a technical reader. This one answers the questions a client asks: what was in scope,
what was found, how bad it is, what we did about it, who owes the next action, and
what happened to the evidence afterwards.

It is assembled from data the case already holds — the workspace (client, machines,
actions, indicators, destruction records), the findings of the Hayabusa analysis, the
source fingerprints of each imported analysis. Nothing is invented: a section with no
data says so rather than disappearing, because a report that silently omits the
indicators looks like a report that found none.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from pathlib import Path

from fireblade.core.model_texts import (
    ACTION_TYPE_LABELS,
    OWNER_LABELS,
    PRIORITY_LABELS,
    STATUS_LABELS,
)
from fireblade.core.paths import evidence_name
from fireblade.core.pdf_export import html_to_pdf

MAX_BYTES = 32 * 1024 * 1024

LEVEL_LABELS = {
    "critical": "Critique",
    "high": "Élevé",
    "medium": "Moyen",
    "low": "Faible",
    "informational": "Informationnel",
}


class _Parts(list):
    def __init__(self):
        super().__init__()
        self.characters = 0

    def append(self, value):
        self.characters += len(value)
        if self.characters > MAX_BYTES:
            raise ValueError(
                "The report is too large; reduce the number of findings or attachments"
            )
        super().append(value)


def _escape(value):
    return html.escape("" if value is None else str(value), quote=True)


def _date(value, fallback="—"):
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return _escape(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _window(group):
    start, end = getattr(group, "start", None), getattr(group, "end", None)
    if start is None:
        return "date inconnue"
    if end is None or end == start:
        return _date(start.isoformat())
    return _date(start.isoformat()) + " → " + _date(end.isoformat())


def _table(rows, headers, widths=None):
    parts = ["<table><thead><tr>"]
    for index, label in enumerate(headers):
        style = f' style="width:{widths[index]}"' if widths and index < len(widths) else ""
        parts.append(f"<th{style}>{_escape(label)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append(
            "<tr>"
            + "".join('<td style="color:#182333">' + _escape(value) + "</td>" for value in row)
            + "</tr>"
        )
    parts.append("</tbody></table>")
    return "".join(parts)


def build(
    *,
    title,
    case_name="",
    case_id="",
    workspace=None,
    documents=(),
    findings=(),
    incidents=(),
    graph_png=None,
    coverage=None,
    destruction=(),
    analyst="",
    generated=None,
):
    """Assemble the client report. Returns the HTML and the counts it was built from."""
    workspace = workspace or {}
    client = workspace.get("client") or {}
    engagement = workspace.get("engagement") or {}
    escape = _escape
    parts = _Parts()
    findings = list(findings)
    incidents = list(incidents)
    counts = {level: 0 for level in LEVEL_LABELS}
    for group in findings:
        counts[getattr(group, "level", "informational")] = (
            counts.get(getattr(group, "level", "informational"), 0) + 1
        )
    actions = workspace.get("actions") or []
    open_actions = [item for item in actions if item.get("status") not in ("done", "cancelled")]
    iocs = workspace.get("iocs") or []
    entities = workspace.get("entities") or []

    for part in [
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">',
        "<title>" + escape(title) + "</title><style>",
        'body{font:10.5pt "Segoe UI",Arial,sans-serif;color:#182333;background:#ffffff;max-width:1040px;margin:34px auto;padding:22px}',
        "h1{color:#174b73;font-size:22pt;margin:6px 0 0}",
        "h2{color:#174b73;border-bottom:2px solid #457b9d;padding-top:22px;page-break-after:avoid}",
        "h3{color:#2f5d7c;margin-bottom:4px}",
        "table{border-collapse:collapse;width:100%;margin:10px 0;table-layout:fixed}",
        "th,td{border:1px solid #ccd5df;padding:6px;text-align:left;vertical-align:top;",
        "overflow-wrap:anywhere;font-size:9pt}",
        "th{background:#eaf1f7}thead th{background:#dde7f0}",
        ".cover{border:2px solid #174b73;padding:26px;margin-bottom:10px}",
        ".conf{color:#8b320c;font-weight:bold;font-size:9pt}",
        ".muted{color:#4f6074}.note{background:#fff3c4;padding:10px}",
        "table.kpi{width:100%;margin:12px 0;border-collapse:collapse}",
        "table.kpi td{border:1px solid #ccd5df;padding:10px;text-align:center;width:16%;color:#182333}",
        "table.kpi b{font-size:18pt;color:#174b73}",
        ".crit{color:#8b1c1c;font-weight:bold}.high{color:#8b320c;font-weight:bold}",
        "img.graph{width:100%;height:auto;border:1px solid #ccd5df}",
        "@media print{body{margin:0;padding:0}h2{page-break-before:auto}}",
        "</style></head><body>",
        '<div class="cover"><p class="conf">CONFIDENTIEL — DIFFUSION RESTREINTE AU CLIENT</p>',
        "<h1>" + escape(title) + "</h1>",
        '<p class="lead">' + escape(client.get("name") or case_name or "—") + "</p>",
        '<p class="muted">Case '
        + escape(case_name or case_id)
        + " · Référence client "
        + escape(client.get("reference") or "—")
        + " · Généré le "
        + escape(_date(generated or datetime.now(UTC).isoformat()))
        + (" · Analyste " + escape(analyst) if analyst else "")
        + "</p></div>",
    ]:
        parts.append(part)

    parts.append("<h2>1. Synthèse</h2>")
    # A table, not a flex row: the PDF is rendered by QTextDocument, which has no flexbox.
    parts.append(
        '<table class="kpi"><tr>'
        + "".join(
            f"<td><b>{counts[level]}</b><br>{_escape(label)}</td>"
            for level, label in (
                ("critical", "Critique"),
                ("high", "Élevé"),
                ("medium", "Moyen"),
                ("low", "Faible"),
            )
        )
        + f"<td><b>{len(open_actions)}</b><br>Action(s) ouverte(s)</td>"
        + f"<td><b>{len(iocs)}</b><br>Indicateur(s)</td></tr></table>"
    )
    total_hits = sum(getattr(group, "count", 0) for group in findings)
    parts.append(
        f"<p>{total_hits} alerte(s) regroupée(s) en {len(findings)} constat(s) sur "
        f"{len(entities)} machine(s) et compte(s) déclaré(s), réparties sur {len(incidents)} "
        f"fenêtre(s) temporelle(s).</p>"
    )
    worst = sorted(
        findings, key=lambda item: (-getattr(item, "severity", 0), str(getattr(item, "start", "")))
    )[:5]
    if worst:
        parts.append("<h3>Constats les plus graves</h3>")
        parts.append(
            _table(
                [
                    (
                        LEVEL_LABELS.get(getattr(group, "level", ""), getattr(group, "level", "")),
                        getattr(group, "title", ""),
                        getattr(group, "host", ""),
                        _window(group),
                        getattr(group, "count", ""),
                    )
                    for group in worst
                ],
                ("Niveau", "Constat", "Hôte", "Fenêtre", "Alertes"),
                ("12%", "40%", "18%", "22%", "8%"),
            )
        )

    parts.append("<h2>2. Périmètre et preuves</h2>")
    if engagement.get("notes") or engagement.get("contract") or engagement.get("lead"):
        parts.append("<p>" + escape(engagement.get("notes") or "") + "</p>")
        parts.append(
            '<p class="muted">Contrat '
            + escape(engagement.get("contract") or "—")
            + " · Responsable "
            + escape(engagement.get("lead") or "—")
            + " · Du "
            + escape(_date(engagement.get("start")))
            + " au "
            + escape(_date(engagement.get("end")))
            + "</p>"
        )
    if entities:
        parts.append(
            _table(
                [
                    (
                        item.get("kind", ""),
                        item.get("label", ""),
                        item.get("hostname", ""),
                        item.get("ip", ""),
                        item.get("os", ""),
                        ", ".join(item.get("tags") or []),
                    )
                    for item in entities
                ],
                ("Type", "Nom", "Hôte", "Adresse", "Système", "Étiquettes"),
            )
        )
    else:
        parts.append(
            '<p class="muted">Aucune machine ni compte n\'a été enregistré pour ce case.</p>'
        )
    if documents:
        parts.append(
            _table(
                [
                    (
                        evidence_name(document.source_info.get("path", "")),
                        document.source_info.get("sha256", "indisponible"),
                        document.source_info.get("rows", ""),
                        document.path,
                    )
                    for document in documents
                ],
                ("Source", "SHA-256 à l'import", "Lignes", "Analyse"),
                ("26%", "40%", "10%", "24%"),
            )
        )
    else:
        parts.append('<p class="muted">Aucune analyse importée dans ce case.</p>')
    if coverage is not None:
        issues = [
            item
            for item in coverage.get("findings", [])
            if item.get("severity") in ("error", "warning")
        ]
        parts.append(
            "<h3>Couverture de la collecte</h3><p>" + escape(coverage.get("scope", "")) + "</p>"
        )
        if issues:
            parts.append(
                _table(
                    [
                        (item.get("stage", ""), item.get("path", ""), item.get("reason", ""))
                        for item in issues[:50]
                    ],
                    ("Étape", "Chemin", "Motif"),
                )
            )
            if len(issues) > 50:
                parts.append(
                    '<p class="muted">Détail limité aux 50 premiers points ; le bilan JSON complet '
                    "accompagne ce rapport.</p>"
                )
        else:
            parts.append(
                '<p class="muted">Aucun écart de couverture signalé au moment de la génération.</p>'
            )

    parts.append("<h2>3. Chronologie des constats</h2>")
    if incidents:
        rows = []
        for incident in incidents[:60]:
            levels = sorted(
                {LEVEL_LABELS.get(group.level, group.level) for group in incident.groups}
            )
            titles = " ; ".join(sorted({group.title for group in incident.groups})[:4])
            rows.append((_window(incident), incident.hits, ", ".join(levels), titles))
        parts.append(
            _table(
                rows, ("Fenêtre", "Alertes", "Niveaux", "Constats"), ("24%", "10%", "18%", "48%")
            )
        )
        if len(incidents) > 60:
            parts.append('<p class="muted">Chronologie limitée aux 60 premières fenêtres.</p>')
    else:
        parts.append(
            '<p class="muted">Aucune fenêtre temporelle n\'a pu être construite à partir des constats.</p>'
        )

    parts.append("<h2>4. Constats détaillés</h2>")
    if findings:
        rows = [
            (
                LEVEL_LABELS.get(group.level, group.level),
                group.title,
                group.host,
                ", ".join(group.event_ids),
                group.count,
                _window(group),
                ", ".join(filter(None, [group.tactics, group.techniques])),
            )
            for group in sorted(findings, key=lambda item: (-item.severity, str(item.start)))[:300]
        ]
        parts.append(
            _table(
                rows,
                ("Niveau", "Règle", "Hôte", "Événements", "Alertes", "Fenêtre", "MITRE"),
                ("9%", "29%", "14%", "11%", "7%", "17%", "13%"),
            )
        )
        if len(findings) > 300:
            parts.append(
                '<p class="muted">Tableau limité aux 300 constats les plus graves ; '
                "le reste est conservé dans l'analyse.</p>"
            )
        parts.append(
            '<p class="muted">Un constat est une règle déclenchée sur un hôte dans une fenêtre de temps ; '
            "il ne constitue pas à lui seul une conclusion de compromission.</p>"
        )
    else:
        parts.append('<p class="muted">Aucun constat Hayabusa n\'est présent dans ce case.</p>')

    if graph_png:
        parts.append("<h2>5. Graphe d'attaque</h2>")
        parts.append(
            '<p class="muted">Les hôtes, les techniques observées et les indicateurs suivis, '
            "ordonnés selon la chaîne d'attaque ; les étiquettes sont celles posées par l'analyste.</p>"
        )
        parts.append(
            '<img class="graph" alt="Graphe d\'attaque" width="960" src="data:image/png;base64,'
            + escape(graph_png)
            + '">'
        )
    else:
        parts.append(
            "<h2>5. Graphe d'attaque</h2><p class=\"muted\">Aucun graphe n'a été joint à ce rapport.</p>"
        )

    parts.append("<h2>6. Indicateurs suivis</h2>")
    if iocs:
        parts.append(
            _table(
                [
                    (
                        item.get("kind", ""),
                        item.get("value", ""),
                        item.get("status", ""),
                        item.get("machine", ""),
                        item.get("label", ""),
                        item.get("source", ""),
                    )
                    for item in iocs[:500]
                ],
                ("Type", "Valeur", "Statut", "Machine", "Libellé", "Source"),
                ("9%", "27%", "10%", "16%", "20%", "18%"),
            )
        )
        if len(iocs) > 500:
            parts.append(
                '<p class="muted">Liste limitée à 500 indicateurs ; le suivi complet est joint en CSV.</p>'
            )
    else:
        parts.append(
            '<p class="muted">Aucun indicateur n\'est suivi dans ce case à la date du rapport.</p>'
        )

    parts.append("<h2>7. Actions et suivi</h2>")
    if actions:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        def details(item):
            text = item.get("title", "")
            extra = (item.get("detail") or "").strip()
            machine = (item.get("machine") or "").strip()
            bits = (
                [text] + ([extra] if extra else []) + (["Machine : " + machine] if machine else [])
            )
            return " — ".join(bits)

        rows = [
            (
                _date(item.get("date"), "—"),
                PRIORITY_LABELS.get(item.get("priority"), item.get("priority", "")),
                STATUS_LABELS.get(item.get("status"), item.get("status", "")),
                ACTION_TYPE_LABELS.get(item.get("type"), item.get("type", "")),
                item.get("intervenant")
                or OWNER_LABELS.get(item.get("owner"), item.get("owner", "")),
                details(item),
            )
            for item in sorted(
                actions,
                key=lambda item: (
                    item.get("status") in ("done", "cancelled"),
                    order.get(item.get("priority"), 9),
                    str(item.get("date") or "9999"),
                ),
            )
        ]
        parts.append(
            _table(
                rows,
                ("Date", "Priorité", "État de l'action", "Type d'action", "Intervenant", "Détails"),
                ("11%", "9%", "13%", "11%", "14%", "42%"),
            )
        )
        parts.append(
            f"<p>{sum(1 for item in actions if item.get('status') in ('done', 'cancelled'))} action(s) "
            f"close(s) sur {len(actions)}.</p>"
        )
    else:
        parts.append('<p class="muted">Aucune action n\'est consignée dans ce case.</p>')

    parts.append("<h2>8. Devenir des preuves</h2>")
    if destruction:
        rows = [
            (
                item.get("label") or item.get("method", ""),
                _date(item.get("started")),
                item.get("operator", ""),
                item.get("witness", ""),
                f"{len(item.get('files', []))} fichier(s)",
                "complet" if item.get("status") == "complete" else "partiel",
            )
            for item in destruction
        ]
        parts.append(_table(rows, ("Méthode", "Date", "Opérateur", "Témoin", "Portée", "Statut")))
        parts.append(
            '<p class="muted">Les procès-verbaux de destruction signés accompagnent ce rapport.</p>'
        )
    else:
        parts.append(
            '<p class="muted">Aucune destruction de preuve n\'a été enregistrée à la date du rapport.</p>'
        )

    parts.append("<h2>9. Méthode et limites</h2>")
    parts.append(
        "<p>Les constats proviennent des règles Hayabusa appliquées aux journaux collectés ; "
        "les indicateurs ont été rapprochés hors ligne, sans requête réseau. Les empreintes "
        "SHA-256 des sources ont été relevées à l'import. Ce rapport décrit les éléments "
        "présents dans les analyses fournies : il ne prouve pas que la collecte était complète, "
        "ni qu'aucune activité n'a échappé aux journaux disponibles.</p>"
    )
    parts.append(
        '<hr><p class="muted">Rapport généré par Fireblade le '
        + escape(_date(generated or datetime.now(UTC).isoformat()))
        + ". Case "
        + escape(case_id or "—")
        + ".</p></body></html>"
    )
    return dict(
        html="\n".join(parts),
        findings=len(findings),
        actions=len(actions),
        open_actions=len(open_actions),
        iocs=len(iocs),
        entities=len(entities),
        counts=counts,
    )


def write(target, document, *, pdf=False):
    target = Path(target)
    temporary = target.with_name(target.name + ".partial")
    try:
        if pdf:
            html_to_pdf(document["html"], temporary, title="Rapport d'investigation — Fireblade")
        else:
            temporary.write_text(document["html"], encoding="utf-8")
        try:
            temporary.replace(target)
        except PermissionError:
            # A file still open in another program, or locked by a scanner, refuses the
            # replace. Removing the old copy and retrying is what a user gets by hand.
            target.unlink(missing_ok=True)
            temporary.replace(target)
        return str(target)
    finally:
        temporary.unlink(missing_ok=True)
