class BaseModule:
    """Modèle commun à tous les modules de JARVIS.

    Chaque module hérite de cette classe, donne son nom et son responsable,
    puis remplit self.actions : intention -> méthode qui renvoie la réponse (texte).
    """

    name = ""
    owner = ""

    def __init__(self):
        self.actions = {}

    def get_intents(self):
        return list(self.actions)

    def handle(self, intent, entities, text_interaction):
        return self.actions[intent](entities, text_interaction)