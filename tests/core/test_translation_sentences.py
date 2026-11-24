"""Composed sentences an analyst reads after a collection, an audit or a hunt."""

from fireblade.core.i18n import set_language, translate


def test_the_collection_and_coverage_sentences_are_english():
    set_language("en")
    try:
        assert (
            translate(
                "Collecte {} · {} fichiers inventoriés · {} sans réussite complète attestée."
            ).format("complete", 44, 13)
            == "Collection complete · 44 files inventoried · 13 without an attested complete success."
        )
        assert (
            translate(
                "Index construit : {} lignes datées, {} sans date ({} absentes, {} invalides), "
                "{} sans fuseau et {} analyses en erreur."
            )
            .format(663185, 1835842, 0, 0, 1835842, 0)
            .startswith("Index built: 663185 dated rows")
        )
        assert (
            translate("Export vérifié : {} / {} lignes écrites ; SHA-256 calculé.").format(7, 7)
            == "Verified export: 7 / 7 rows written; SHA-256 computed."
        )
        assert (
            translate("Chasse {} : {} lignes lues ; {} IOC rejetés ; détails limités : {}.").format(
                "complete", 2499027, 1, 0
            )
            == "Hunt complete: 2499027 rows read; 1 IOCs rejected; details limited: 0."
        )
    finally:
        set_language("fr")


def test_the_engine_reasons_are_english():
    set_language("en")
    try:
        assert (
            translate(
                "Moteur intégré absent : SQLECmd. La construction du pack forensic est nécessaire."
            )
            == "Built-in engine missing: SQLECmd. The forensic pack must be built."
        )
        assert (
            translate("{} ligne(s) non structurée(s), conservée(s) en texte brut").format(2)
            == "2 unstructured line(s), kept as raw text"
        )
        assert (
            translate("Binaire inconnu ; aucun décodage arbitraire")
            == "Unknown binary; no arbitrary decoding"
        )
    finally:
        set_language("fr")


def test_the_timeline_lane_counter_is_english():
    set_language("en")
    try:
        assert translate("{} datés").format("1 752 069") == "1 752 069 dated"
    finally:
        set_language("fr")


def test_the_alert_banner_and_the_row_details_are_english():
    set_language("en")
    try:
        assert (
            translate("Alerte : {} · Gravité : {}").format("Important Log File Cleared", "high")
            == "Alert: Important Log File Cleared · Severity: high"
        )
        assert (
            translate("Date source ({}) : {}").format("Horodatage UTC", "2026-08-12")
            == "Source date (Horodatage UTC): 2026-08-12"
        )
    finally:
        set_language("fr")
