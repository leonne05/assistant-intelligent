import uuid
from datetime import datetime


class SimulatedMessageSender:
    """Envoi simulé : le message n'est pas envoyé, il est seulement enregistré.

    Cette classe sera remplacée par celle du module messagerie (module 5)
    quand il sera disponible : elle devra garder la même méthode send.
    """

    def __init__(self):
        self.channel = "simulé"


    def send(self, recipient, subject, body):

        return {
            "message_id": uuid.uuid4().hex[:8],
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "channel": self.channel,
            "status": "simulated_sent",
            "sent_at": datetime.now().isoformat(timespec="seconds"),
        }