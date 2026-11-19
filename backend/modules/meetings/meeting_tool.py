class MeetingTool:
    """Classe mère des outils qui travaillent sur une réunion : elle ne s'utilise pas directement.

    Elle garde le service des réunions et sait retrouver et sauvegarder une réunion.
    Chaque classe fille fait une seule tâche (planifier, éditer l'ordre du jour, préparer...).
    """

    def __init__(self, meetings_service):
        self.meetings_service = meetings_service


    def get_meeting(self, meeting_id):
        return self.meetings_service.get_meeting(meeting_id=meeting_id)


    def save_meeting(self, meeting_id):
        self.meetings_service.save_meeting(meeting_id=meeting_id)