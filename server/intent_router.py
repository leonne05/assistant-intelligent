from mistralai.client import Mistral
from dotenv import load_dotenv
from datetime import datetime
import json
import os


class IntentRouter:
    MODEL = "ministral-8b-latest"
    MIN_CONFIDENCE = 0.5
    INTENTS = [
        "CHAT_LIBRE",
        "GENERATE_BRIEFING",
        "GET_SCHEDULE",
        "GET_WEATHER",
        "CHECK_TRANSPORT",
        "PLAN_TRAVEL",
        "SNOOZE_TASKS",
        "START_FOCUS",
        "SEND_MESSAGE",
        "SUMMARIZE_GROUP",
        "READ_MESSAGES",
        "PREPARE_MEETING",
        "GENERATE_REPORT",
        "SUMMARIZE_COURSE",
        "GENERATE_QUIZ",
        "CONTROL_DEVICE",
        "GET_DEVICE_STATUS",
    ]

    def __init__(self, mistral_client):
        self.mistral_client = mistral_client
        self.intent_context = self.read_file(file_path="./intent_context.txt")

    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def analyse_intent(self, text_interaction):
        now = datetime.now().isoformat(timespec="minutes")
        messages = [
            {
                "role": "system",
                "content": f"{self.intent_context}\n\nDate et heure actuelles : {now}",
            },
            {
                "role": "user",
                "content": text_interaction,
            },
        ]

        response = self.mistral_client.chat.complete(
            model=self.MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        ).choices[0].message.content

        return self.validate(response)

    def validate(self, response):
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return {"intent": "CHAT_LIBRE", "confidence": 0.0, "entities": {}}

        intent = data.get("intent")
        confidence = float(data.get("confidence", 0))

        if intent not in self.INTENTS or confidence < self.MIN_CONFIDENCE:
            intent = "CHAT_LIBRE"

        return {
            "intent": intent,
            "confidence": confidence,
            "entities": data.get("entities") or {},
        }


if __name__ == "__main__":
    load_dotenv()
    intent_router_object = IntentRouter(Mistral(api_key=os.environ["MISTRAL_API_KEY"]))
    print("Écris une demande pour voir l'intention détectée (vide pour quitter).")
    while True:
        question = input("\nToi : ")
        if question == "":
            break
        print(intent_router_object.analyse_intent(question))