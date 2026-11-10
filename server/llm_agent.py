from mistralai.client import Mistral
from dotenv import load_dotenv
import os


class ConversationAgent:
    MODEL = "ministral-8b-latest"

    def __init__(self):
        load_dotenv()
        self.mistral_client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self.conversation_history = [
            {
                "role": "system",
                "content": self.read_file(file_path="./context.txt"),
            }
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

    def ask_llm(self, text_interaction):
        self.update_conversation_history(role="user", text_interaction=text_interaction)

        try:
            response = self.mistral_client.chat.complete(
                model=self.MODEL,
                messages=self.conversation_history,
            ).choices[0].message.content
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