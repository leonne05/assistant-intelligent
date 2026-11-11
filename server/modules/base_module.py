class BaseModule:
    """Modèle commun à tous les modules de JARVIS.

    Chaque module hérite de cette classe, donne son nom et son responsable,
    puis remplit self.actions : intention -> méthode qui renvoie la réponse (texte).
    """

    name = ""
    owner = ""
    demo = False

    def __init__(self):
        self.actions = {}

    def get_intents(self):
        return list(self.actions)

    def handle(self, intent, entities, text_interaction):
        return self.actions[intent](entities, text_interaction)

    def has_pending(self):
        """True si le module attend une réponse de l'utilisateur (ex : une confirmation)."""
        return False

    def handle_pending(self, text_interaction):
        return None