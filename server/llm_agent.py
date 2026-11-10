from mistralai.client import Mistral
from mistralai.client.utils import BackoffStrategy, RetryConfig
from dotenv import load_dotenv
from intent_router import IntentRouter
from modules.planning_module import PlanningModule
import os


class ConversationAgent:
    MODEL = "ministral-8b-latest"

    def __init__(self):
        load_dotenv()
        self.mistral_client = Mistral(
            api_key=os.environ["MISTRAL_API_KEY"],
            # En cas d'erreur 429 (trop de demandes), réessaie automatiquement pendant 20 secondes maximum.
            retry_config=RetryConfig("backoff", BackoffStrategy(1000, 8000, 2.0, 20000), True),
        )
        self.conversation_history = [
            {
                "role": "system",
                "content": self.read_file(file_path="./context.txt"),
            }
        ]
        self.intent_router_object = IntentRouter(self.mistral_client)
        self.modules = [
            PlanningModule(),
        ]

    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def get_conversation_history(self):
        return self.conversation_history[1:]

    def update_conversation_history(self, role, text_interaction):
        self.conversation_history.append(
            {
                "role": role,
                "content": text_interaction,
            }
        )

    def find_module(self, intent):
        for module in self.modules:
            if intent in module.get_intents():
                return module
        return None

    def generate_response(self):
        return self.mistral_client.chat.complete(
            model=self.MODEL,
            messages=self.conversation_history,
        ).choices[0].message.content

    def route(self, intent, text_interaction):
        if intent["intent"] == "CHAT_LIBRE":
            return self.generate_response()

        module = self.find_module(intent["intent"])
        if module is None:
            return "J'ai bien compris ta demande, mais je ne sais pas encore le faire. Cette fonctionnalité arrive bientôt."

        return module.handle(intent["intent"], intent["entities"], text_interaction)

    def ask_llm(self, text_interaction):
        intent = self.intent_router_object.analyse_intent(text_interaction)
        print(f"[JARVIS] Intention : {intent['intent']} ({intent['confidence']}) {intent['entities']}")

        self.update_conversation_history(role="user", text_interaction=text_interaction)

        try:
            response = self.route(intent, text_interaction)
        except Exception:
            # La question est restée sans réponse : on la retire de l'historique.
            self.conversation_history.pop()
            raise

        self.update_conversation_history(role="assistant", text_interaction=response)
        return response


if __name__ == "__main__":
    conversation_agent_object = ConversationAgent()
    print("Parle à JARVIS (laisse vide et appuie sur Entrée pour quitter).")
    while True:
        question = input("\nToi : ")
        if question == "":
            break
        print(f"JARVIS : {conversation_agent_object.ask_llm(question)}")