# JARVIS — Majordome intelligent

Assistant à qui l'on parle en temps réel et à qui l'on délègue des tâches.

```
Téléphone (Expo)  ──Wi-Fi──▶  Serveur Python (FastAPI)  ──▶  Mistral (LLM, Voxtral)
  mobile/                       server/
```

- `mobile/` : l'appli (React Native + Expo + React Native Paper)
- `server/` : le cerveau en Python POO
  - `llm_agent.py` : `ConversationAgent` (mémoire, orchestration, voix)
  - `intent_router.py` : `IntentRouter` (reconnaît l'intention d'une phrase)
  - `api.py` : `JarvisApi` (routes `/health`, `/chat`, `/transcribe`)
  - `modules/` : un module par fonctionnalité (Planning, Déplacements…)

## Prérequis

- Python 3.10 ou plus, Node.js LTS
- Une clé Mistral : console.mistral.ai → API Keys
- L'appli **Expo Go** sur le téléphone
- Le téléphone et le PC sur le **même Wi-Fi** (ou le PC sur le partage de connexion du téléphone)

## 1. Lancer le serveur

```powershell
cd server
python -m pip install -r requirements.txt
copy .env.example .env          # puis coller sa clé Mistral dans .env
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Tester : http://localhost:8000/docs

## 2. Lancer l'appli

```powershell
cd mobile
npm install
copy .env.example .env          # puis mettre l'adresse IPv4 de son PC (ipconfig)
npx expo start
```

Scanner le QR code avec Expo Go. Pour vérifier le réseau depuis le téléphone, ouvrir `http://ADRESSE_IP:8000/health`.

## 3. Ajouter son module

1. Créer `server/modules/mon_module.py` :

```python
from modules.base_module import BaseModule


class DeplacementsModule(BaseModule):
    name = "Déplacements"
    owner = "Moïra"
    demo = True      # passer à False quand les vraies données sont branchées

    def __init__(self):
        super().__init__()
        self.actions = {
            "GET_WEATHER": self.get_weather,
        }

    def get_weather(self, entities, text_interaction):
        city = entities.get("location", "Paris")
        return f"Demain à {city}, il fera 14 degrés."
```

2. L'ajouter dans `server/llm_agent.py`, dans `self.modules`.
3. Les intentions possibles et les informations extraites (`entities` : `datetime`, `location`, `contact`…) sont listées dans `server/intent_context.txt`.
4. Règles :
   - renvoyer une phrase courte et naturelle (elle est lue à voix haute) ;
   - ne jamais inventer : si une donnée manque, le dire ;
   - toute action irréversible (envoyer un message, déverrouiller…) devra passer par une confirmation.

## Problèmes fréquents

| Symptôme | Solution |
| --- | --- |
| `ImportError: cannot import name 'Mistral'` | Mauvaise version : `python -m pip install -U "mistralai>=3"` (toujours `python -m pip`, jamais `pip` seul) |
| « erreur Mistral 401 » | Clé expirée ou fausse : nouvelle clé dans `server/.env`, puis redémarrer le serveur |
| « Trop de demandes… » (429) | Limite du compte gratuit : attendre quelques secondes |
| « Je n'arrive pas à joindre mon cerveau » | Vérifier l'IP dans `mobile/.env` (relancer `npx expo start` après modification), le pare-feu Windows (réseau en profil **Privé**) et le même Wi-Fi |
| L'IP a changé | Refaire `ipconfig`, mettre à jour `mobile/.env`, relancer Expo |