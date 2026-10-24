# Assistant Intelligent

Assistant personnel inspiré de Jarvis, avec une API Python/FastAPI prévue pour
le chat, la voix et l’exécution d’actions validées.

## Architecture

```text
assistant-intelligent/
├── README.md
├── .gitignore
└── backend/                  # Python · FastAPI
    ├── .env.example
    ├── requirements.txt
    ├── main.py               # Application et routes (/chat, /voice, /actions)
    ├── llm.py                # Appels aux modèles, bascule et transcription
    ├── router.py             # Routeur d’intentions
    ├── memory.py             # Historique, préférences et journal
    ├── actions.py            # Actions en attente et validation avant exécution
    └── context.txt           # Personnalité de Jarvis
```

Le répertoire `backend/` décrit l’organisation cible de l’API. Les actions
sensibles doivent rester en attente jusqu’à validation explicite de
l’utilisateur.

## Démarrer l’API

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell : .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

L’API est ensuite disponible sur `http://127.0.0.1:8000`. La documentation
interactive se trouve sur `/docs`. Copiez `.env.example` vers `.env` pour
ajouter les clés des fournisseurs LLM lorsque leur intégration sera activée.