from modules.base_module import BaseModule
import json
import re


class CommunicationModule(BaseModule):
    """Module Communications (Elyna) — VERSION DÉMO avec des messages fictifs.

    Lire les messages autorisés, distinguer les homonymes, rédiger un message
    et ne jamais l'envoyer sans la confirmation de l'utilisateur.
    """

    name = "Communications"
    owner = "Elyna"
    demo = True      # passer à False quand WhatsApp / SMS seront branchés

    MODEL = "ministral-8b-latest"
    YES_WORDS = {"oui", "ouais", "envoie", "envoie-le", "valide", "confirme", "ok", "vas-y", "d'accord"}
    NO_WORDS = {"non", "annule", "stop", "laisse", "n'envoie"}

    def __init__(self, mistral_client):
        super().__init__()
        self.mistral_client = mistral_client
        self.contacts = self.read_json(file_path="./data/contacts.json")
        self.conversations = self.read_json(file_path="./data/messages.json")
        self.pending_action = None
        self.actions = {
            "SEND_MESSAGE": self.send_message,
            "SUMMARIZE_GROUP": self.summarize_group,
            "READ_MESSAGES": self.read_messages,
        }

    @staticmethod
    def read_json(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def words(text_interaction):
        return set(re.findall(r"[\w'-]+", text_interaction.lower()))

    def ask_llm(self, system_prompt, user_prompt):
        return self.mistral_client.chat.complete(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        ).choices[0].message.content.strip()

    # ---------- Consulter les messages autorisés ----------

    def get_conversation(self, name):
        for conversation in self.conversations:
            if conversation["name"].lower() == name.lower() and conversation["authorized"]:
                return conversation
        return None

    def get_messages(self, name):
        conversation = self.get_conversation(name)
        if conversation is None:
            return []
        return conversation["messages"]

    def read_messages(self, entities, text_interaction):
        contacts = self.find_contacts(entities.get("contact") or text_interaction)
        if len(contacts) != 1:
            return "De qui veux-tu lire les messages ? Donne-moi le prénom et le nom."

        messages = self.get_messages(contacts[0]["name"])
        if not messages:
            return f"Je n'ai pas l'autorisation de lire les messages de {contacts[0]['name']}."

        last_message = messages[-1]
        return f"Dernier message de la conversation avec {contacts[0]['name']}, de {last_message['sender']} : {last_message['content']}"

    # ---------- Distinguer les homonymes ----------

    def find_contacts(self, text_interaction, contacts=None):
        """Renvoie les contacts qui correspondent le mieux (nom, prénom ou relation)."""
        contacts = contacts or self.contacts
        text_words = self.words(text_interaction)

        scores = []
        for contact in contacts:
            contact_words = self.words(contact["name"]) | {contact["relation"].lower()}
            scores.append(len(contact_words & text_words))

        best_score = max(scores, default=0)
        if best_score == 0:
            return []
        return [contact for contact, score in zip(contacts, scores) if score == best_score]

    @staticmethod
    def describe(contacts):
        return " ou ".join(f"{contact['name']} ({contact['relation']})" for contact in contacts)

    # ---------- Rédiger une réponse ----------

    def draft(self, contact, content):
        return self.ask_llm(
            system_prompt=(
                "Tu rédiges un message court à envoyer de la part de l'utilisateur, à la première personne. "
                "Adapte le ton à la relation avec le destinataire. "
                "Réponds uniquement avec le texte du message, sans guillemets."
            ),
            user_prompt=f"Destinataire : {contact['name']} ({contact['relation']})\nCe que l'utilisateur veut dire : {content}",
        )

    def propose(self, contact, content):
        draft = self.draft(contact, content)
        self.pending_action = {"step": "confirm", "contact": contact, "draft": draft}
        return f"Voici le message pour {contact['name']} : {draft}. Je l'envoie ?"

    def send_message(self, entities, text_interaction):
        content = entities.get("message_content") or text_interaction
        name = entities.get("contact")
        if not name:
            self.pending_action = {"step": "contact", "candidates": self.contacts, "content": content}
            return "À qui veux-tu envoyer ce message ?"

        contacts = self.find_contacts(name)
        if not contacts:
            return f"Je ne trouve pas {name} dans tes contacts."

        if len(contacts) > 1:
            self.pending_action = {"step": "contact", "candidates": contacts, "content": content}
            return f"Lequel ? {self.describe(contacts)} ?"

        return self.propose(contacts[0], content)

    # ---------- Demander confirmation avant envoi ----------

    def has_pending(self):
        return self.pending_action is not None

    def handle_pending(self, text_interaction):
        text_words = self.words(text_interaction)
        if text_words & self.NO_WORDS:
            self.pending_action = None
            return "D'accord, je n'envoie rien."

        action = self.pending_action

        if action["step"] == "contact":
            contacts = self.find_contacts(text_interaction, action["candidates"])
            if len(contacts) != 1:
                return f"Je n'ai pas compris. {self.describe(action['candidates'][:3])} ?"
            return self.propose(contacts[0], action["content"])

        # action["step"] == "confirm"
        if text_words & self.YES_WORDS:
            self.send(action["contact"]["name"], action["draft"])
            self.pending_action = None
            return f"C'est envoyé à {action['contact']['name']}."

        # Ni oui ni non : la phrase sert à modifier le message.
        return self.propose(action["contact"], f"{action['draft']}\nModification demandée : {text_interaction}")

    def send(self, name, content):
        # Envoi simulé : on ajoute le message à la conversation.
        conversation = self.get_conversation(name)
        if conversation is None:
            conversation = {"name": name, "type": "contact", "app": "SMS", "authorized": True, "messages": []}
            self.conversations.append(conversation)
        conversation["messages"].append({"sender": "Moi", "content": content})

    # ---------- Résumé de groupe ----------

    def find_group(self, entities, text_interaction):
        searched = f"{entities.get('topic', '')} {entities.get('contact', '')} {text_interaction}".lower()
        for conversation in self.conversations:
            if conversation["type"] == "group" and conversation["authorized"] and conversation["name"].lower() in searched:
                return conversation
        return None

    def summarize_group(self, entities, text_interaction):
        group = self.find_group(entities, text_interaction)
        if group is None:
            names = ", ".join(c["name"] for c in self.conversations if c["type"] == "group" and c["authorized"])
            return f"Quel groupe veux-tu que je résume ? J'ai accès à : {names}."

        number = re.search(r"\d+", text_interaction)
        limit = int(number.group()) if number else 50
        messages = group["messages"][-limit:]

        text = "\n".join(f"{message['sender']} : {message['content']}" for message in messages)
        return self.ask_llm(
            system_prompt=(
                "Tu résumes une conversation de groupe en français, pour une lecture à voix haute. "
                "Deux à quatre phrases, sans liste ni markdown. "
                "Termine par les actions à faire : qui doit faire quoi."
            ),
            user_prompt=text,
        )