"""Lien avec le module Planning (Mariam) : seul fichier à adapter pour le brancher."""
from .common import DeplacementsError


def get_next_appointment() -> dict:
    """Doit renvoyer {'place': str, 'time': datetime} du prochain rendez-vous."""
    raise DeplacementsError("Le module Planning n'est pas encore branché.")
