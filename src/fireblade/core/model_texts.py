"""Display labels for the operational vocabulary of a case.

Codes are what the file stores; these are what a person reads. They live in one place
so the operations board, the case dialog and the client report cannot disagree about
what ``waiting_client`` means.
"""

OWNER_LABELS = {
    "us": "Notre équipe",
    "client": "Client",
    "third_party": "Tiers / éditeur",
    "vendor": "Fournisseur",
    "unassigned": "Non attribué",
}

STATUS_LABELS = {
    "todo": "À faire",
    "in_progress": "En cours de traitement",
    "waiting_client": "En attente du client",
    "waiting_us": "En attente de notre côté",
    "blocked": "Bloquée",
    "done": "Terminée",
    "cancelled": "Annulée",
}

PRIORITY_LABELS = {"low": "Faible", "medium": "Moyenne", "high": "Haute", "critical": "Critique"}

ACTION_TYPE_LABELS = {
    "collect": "Collecte",
    "analysis": "Analyse",
    "remediation": "Remédiation",
    "coordination": "Coordination",
    "meeting": "Réunion",
    "report": "Rapport",
    "destruction": "Destruction",
    "legal": "Juridique",
    "other": "Autre",
}

ENTITY_LABELS = {
    "machine": "Machine",
    "account": "Compte",
    "domain": "Domaine",
    "mailbox": "Boîte mail",
    "share": "Partage",
}

IOC_STATUS_LABELS = {
    "new": "Nouveau",
    "confirmed": "Confirmé",
    "benign": "Bénin",
    "unknown": "À qualifier",
}

NODE_LABELS = {
    "host": "Hôte",
    "account": "Compte",
    "technique": "Technique",
    "stage": "Étape",
    "ioc": "Indicateur",
    "custom": "Libre",
}

OPEN_STATUSES = ("todo", "in_progress", "waiting_client", "waiting_us", "blocked")
