import os
import re
from datetime import datetime

from modules.module6_llm import LlmClient


class ReportManager:
    def __init__(self, meetings_service, exporter, sender):
        self.meetings_service = meetings_service
        self.exporter = exporter
        self.sender = sender
        self.correct_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_meeting_correct.txt")
        )

        self.max_text_length = 8000
        self.max_instruction_length = 1000
        self.action_statuses = ["open", "done"]
        self.formats = {
            "pdf": self.exporter.formats["pdf"],
            "docx": self.exporter.formats["docx"],
            "md": self.exporter.formats["md"],
        }


    def get_meeting_and_report(self, meeting_id):

        meeting = self.meetings_service.meetings.get(meeting_id)

        if meeting is None:
            return None, None

        if meeting["report"] is None:
            raise ValueError("Cette réunion n'a pas encore de compte rendu.")

        return meeting, meeting["report"]


    def mark_as_draft(self, report):
        report["status"] = "draft"
        report.pop("validated_at", None)
        report["edited_at"] = datetime.now().isoformat(timespec="seconds")


    def clean_due(self, due):

        due = (due or "").strip()

        if not due:
            return None

        try:
            return datetime.strptime(due, "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ValueError("La date doit être au format AAAA-MM-JJ, par exemple 2026-12-15.")


    def clean_who(self, meeting, who):

        who = " ".join((who or "").split())[:60]

        if not who:
            return "non précisé"

        for participant in meeting["participants"]:
            if participant["name"].lower() == who.lower():
                return participant["name"]

        return who


    def edit(self, meeting_id, text=None, decisions=None, open_points=None):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        if text is not None:
            text = text.strip()

            if not text:
                raise ValueError("Le compte rendu ne peut pas être vide.")

            if len(text) > self.max_text_length:
                raise ValueError("Le compte rendu est trop long.")

            report["text"] = text

        if decisions is not None:
            report["decisions"] = self.meetings_service.clean_text_list(raw_list=decisions)

        if open_points is not None:
            report["open_points"] = self.meetings_service.clean_text_list(raw_list=open_points)

        self.mark_as_draft(report=report)
        self.meetings_service.save_meeting(meeting_id=meeting_id)

        return report


    def correct(self, meeting_id, instruction):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        instruction = (instruction or "").strip()

        if not instruction:
            raise ValueError("Dis-moi ce que je dois corriger.")

        if len(instruction) > self.max_instruction_length:
            raise ValueError("La correction est trop longue : résume-la en quelques phrases.")

        new_text = self.meetings_service.llm_client.ask_paced(
            context=self.correct_context,
            text_interaction=(
                self.meetings_service.get_meeting_header(meeting=meeting)
                + "\n\n## Compte rendu actuel\n\n" + report["text"]
                + "\n\n## Correction demandée\n\n" + instruction
            ),
        ).strip()

        if not new_text:
            raise RuntimeError("La correction n'a pas pu être appliquée.")

        report["text"] = new_text
        report["details_outdated"] = False

        try:
            answer = self.meetings_service.llm_client.ask_paced(
                context=self.meetings_service.actions_context,
                text_interaction=(
                    self.meetings_service.get_calendar_text() + "\n\n"
                    + self.meetings_service.get_meeting_header(meeting=meeting)
                    + "\n\n## Notes prises pendant la réunion\n\n" + new_text
                ),
            )
            details = self.meetings_service.parse_report_data(answer=answer)
            report["decisions"] = details["decisions"]
            report["actions"] = details["actions"]
            report["open_points"] = details["open_points"]
        except Exception:
            report["details_outdated"] = True

        self.mark_as_draft(report=report)
        self.meetings_service.save_meeting(meeting_id=meeting_id)

        return report


    def add_action(self, meeting_id, who, what, due=None):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        what = " ".join((what or "").split())[:300]

        if not what:
            raise ValueError("Dis ce qu'il faut faire.")

        if len(report["actions"]) >= self.meetings_service.max_list_items:
            raise ValueError("Il y a déjà trop d'actions : supprime-en une avant d'en ajouter.")

        action = {
            "id": os.urandom(4).hex(),
            "who": self.clean_who(meeting=meeting, who=who),
            "what": what,
            "due": self.clean_due(due=due),
            "status": "open",
        }
        report["actions"].append(action)

        self.mark_as_draft(report=report)
        self.meetings_service.save_meeting(meeting_id=meeting_id)

        return action


    def update_action(self, meeting_id, action_id, who=None, what=None, due=None, status=None):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        action = next((item for item in report["actions"] if item["id"] == action_id), None)

        if action is None:
            return False

        content_changed = what is not None or who is not None or due is not None

        if what is not None:
            what = " ".join(what.split())[:300]

            if not what:
                raise ValueError("Dis ce qu'il faut faire.")

            action["what"] = what

        if who is not None:
            action["who"] = self.clean_who(meeting=meeting, who=who)

        if due is not None:
            action["due"] = self.clean_due(due=due)

        if status is not None:
            if status not in self.action_statuses:
                raise ValueError("Le statut doit être open ou done.")

            action["status"] = status

        if content_changed:
            self.mark_as_draft(report=report)

        self.meetings_service.save_meeting(meeting_id=meeting_id)

        return action


    def delete_action(self, meeting_id, action_id):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        remaining = [item for item in report["actions"] if item["id"] != action_id]

        if len(remaining) == len(report["actions"]):
            return False

        report["actions"] = remaining
        self.mark_as_draft(report=report)
        self.meetings_service.save_meeting(meeting_id=meeting_id)

        return True


    def validate(self, meeting_id):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        if report.get("details_outdated"):
            raise ValueError("Les décisions et actions ne correspondent plus au texte corrigé : vérifie-les avant de valider.")

        report["status"] = "validated"
        report["validated_at"] = datetime.now().isoformat(timespec="seconds")
        self.meetings_service.save_meeting(meeting_id=meeting_id)

        return report


    def approve_and_send(self, meeting_id, recipients=None):

        if self.validate(meeting_id=meeting_id) is None:
            return None

        return self.send(meeting_id=meeting_id, recipients=recipients)


    def build_message(self, meeting, report, name):

        subject = f"Compte rendu : {meeting['title']} ({meeting['created_at'][:10]})"
        own_actions = [action for action in report["actions"] if action["who"].lower() == name.lower()]

        if own_actions:
            lines = []

            for action in own_actions:
                due = f" (pour le {action['due']})" if action["due"] else ""
                lines.append(f"- {action['what']}{due}")

            actions_text = "\n".join(lines)
        else:
            actions_text = "Aucune action ne t'est attribuée."

        body = f"Bonjour {name},\n\n{report['text']}\n\n## Tes actions\n\n{actions_text}"

        return subject, body


    def send(self, meeting_id, recipients=None):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        if report["status"] == "draft":
            raise ValueError("Valide d'abord le compte rendu : je n'envoie pas un brouillon.")

        participant_names = [participant["name"] for participant in meeting["participants"]]

        if recipients:
            chosen_names = []

            for recipient in recipients:
                match = next((name for name in participant_names if name.lower() == recipient.strip().lower()), None)

                if match is None:
                    raise ValueError(f"{recipient} ne fait pas partie des participants de cette réunion.")

                if match not in chosen_names:
                    chosen_names.append(match)
        else:
            chosen_names = [participant["name"] for participant in meeting["participants"] if participant["consent"]]

        if not chosen_names:
            raise ValueError("Il n'y a aucun destinataire.")

        outbox = meeting.setdefault("outbox", [])
        sent_messages = []

        for name in chosen_names:
            subject, body = self.build_message(meeting=meeting, report=report, name=name)
            message = self.sender.send(recipient=name, subject=subject, body=body)
            outbox.append(message)
            sent_messages.append(message)

        report["status"] = "sent"
        report["sent_at"] = datetime.now().isoformat(timespec="seconds")
        self.meetings_service.save_meeting(meeting_id=meeting_id)

        return {"meeting_id": meeting_id, "channel": self.sender.channel, "messages": sent_messages}


    def get_outbox(self, meeting_id):

        meeting = self.meetings_service.meetings.get(meeting_id)

        if meeting is None:
            return None

        return meeting.get("outbox", [])


    def export(self, meeting_id, file_format):

        meeting, report = self.get_meeting_and_report(meeting_id=meeting_id)

        if meeting is None:
            return None

        if file_format not in self.formats:
            raise ValueError("Format inconnu : choisis pdf, docx ou md.")

        title = meeting["title"]

        if file_format == "md":
            data = report["text"].encode("utf-8")
        else:
            blocks = self.exporter.parse_markdown(markdown=report["text"])

            if file_format == "pdf":
                data = self.exporter.build_pdf(blocks=blocks, title=title)
            else:
                data = self.exporter.build_docx(blocks=blocks)

        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_") or "reunion"
        file_info = self.formats[file_format]

        return {
            "file_name": f"jarvis_{safe_name}_compte_rendu.{file_info['extension']}",
            "media_type": file_info["media_type"],
            "data": data,
        }