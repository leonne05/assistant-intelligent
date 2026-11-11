# JARVIS – Module Déplacements

Intentions : `GET_WEATHER`, `CHECK_TRANSPORT`, `PLAN_TRAVEL` (Python 3.10+).

## Installation (VS Code, Windows)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # puis renseigne PRIM_API_KEY
python main.py
pytest
```

## Utilisation
```python
from deplacements import handle_intent
handle_intent("GET_WEATHER", city="Paris", day="2026-11-27")
handle_intent("CHECK_TRANSPORT", line="RER A")
handle_intent("PLAN_TRAVEL", destination="HETIC Paris 13", arrive_by="2026-11-27T09:00")
handle_intent("PLAN_TRAVEL")   # prochain RDV du module Planning (agenda.py)
```
Chaque appel renvoie une phrase. `deplacements.HANDLERS` = {intention: fonction}, pour
enregistrer les trois intentions dans l'IntentRouter.

## Architecture
intents -> planner -> weather / transport / agenda -> common -> config
