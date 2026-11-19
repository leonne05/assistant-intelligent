from datetime import date

from modules.meetings.meeting_tool import MeetingTool


class ReminderBuilder(MeetingTool):
    """Écrit le rappel des actions en retard ou bientôt dues (le texte peut être lu par la voix de JARVIS)."""

    def __init__(self, meetings_service, action_tracker):
        super().__init__(meetings_service=meetings_service)
        self.action_tracker = action_tracker
        self.default_days_ahead = 3


    def describe_deadline(self, action):

        if action["days_left"] < 0:
            return f"en retard de {-action['days_left']} jour(s)"

        if action["days_left"] == 0:
            return "pour aujourd'hui"

        if action["days_left"] == 1:
            return "pour demain"

        return f"dans {action['days_left']} jours"


    def find_reminders(self, who=None, days_ahead=None, today=None):

        days_ahead = self.default_days_ahead if days_ahead is None else days_ahead
        actions = self.action_tracker.collect(who=who, status="open", today=today)

        return [action for action in actions if action["days_left"] is not None and action["days_left"] <= days_ahead]


    def build(self, who=None, days_ahead=None, today=None):

        reminders = self.find_reminders(who=who, days_ahead=days_ahead, today=today)

        if not reminders:
            return {"count": 0, "actions": [], "text": "Aucune action en retard ou à faire bientôt."}

        lines = [f"Tu as {len(reminders)} action(s) à surveiller :"]

        for action in reminders:
            lines.append(
                f"- {action['who']} : {action['what']} ({self.describe_deadline(action=action)}, réunion « {action['meeting_title']} »)"
            )

        return {"count": len(reminders), "actions": reminders, "text": "\n".join(lines)}