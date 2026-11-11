# 🧭 Module Déplacements — JARVIS

Responsable : **Moïra** · Branche : `feature/deplacements`

Ce module répond aux questions de déplacement de l'assistant : **météo**, **perturbations de transport** et **planification de trajet** (heure de départ, alternative, marge météo). Chaque appel renvoie **une phrase prête à être lue à voix haute**. Le module ne lève jamais d'exception.

## Contrat avec le routeur

Le routeur appelle chaque action ainsi : `fonction(entities, text_interaction)` et attend **une phrase** en retour. Seules les entités déjà présentes sont envoyées, donc le module utilise `entities.get(...)`.

| Intention | Entités utilisées | Exemple de réponse |
|---|---|---|
| `GET_WEATHER` | `location` (ville), `datetime` (jour) | « À Caen le 12/11 : pluie, 5 à 9°C… » |
| `CHECK_TRANSPORT` | ligne repérée dans `text_interaction` (ex. « RER A »), sinon `location` | « Aucune perturbation signalée sur RER A. » |
| `PLAN_TRAVEL` | `location` (destination), `datetime` (heure d'arrivée) | « Pars à 08:05 : RER A, 40 min. » |

- `datetime` est un texte ISO (`"2026-11-12T14:00"`). Pour la météo, seule la date est utilisée.
- Le départ est `HOME_ADDRESS` (`.env`).
- `PLAN_TRAVEL` sans `location` ni `datetime` prend le **prochain rendez-vous** du module Planning (via `agenda.py`).
- Les autres entités (`duration_minutes`, `contact`, `device`...) sont ignorées.
- Une action ne lève jamais d'exception : en cas de problème, elle renvoie une phrase.

## Utilisation

```python
from deplacements import ACTIONS, handle_intent

# Enregistrement dans le module : self.actions = ACTIONS
ACTIONS["GET_WEATHER"]({"location": "Caen", "datetime": "2026-11-12T14:00"}, "Quel temps fera-t-il demain à Caen ?")

# Équivalent, par nom d'intention
handle_intent("CHECK_TRANSPORT", {}, "Y a-t-il des perturbations sur le RER A ?")
```

`ACTIONS` est un dictionnaire `{"GET_WEATHER": fonction, "CHECK_TRANSPORT": fonction, "PLAN_TRAVEL": fonction}`.

## Installation

```powershell
pip install requests python-dotenv pytest
copy deplacements\.env.example .env     # à la racine du dépôt
```

Renseigne ensuite `PRIM_API_KEY` dans `.env` (clé gratuite : https://prim.iledefrance-mobilites.fr). Le fichier `.env` n'est **jamais** versionné.

| Variable | Rôle | Défaut |
|---|---|---|
| `PRIM_API_KEY` | Clé de l'API transports (obligatoire pour les transports) | — |
| `DEFAULT_CITY` | Ville de la météo | Neuilly-sur-Marne |
| `HOME_ADDRESS` | Départ par défaut des trajets | = `DEFAULT_CITY` |
| `BUFFER_MINUTES` | Marge de sécurité avant l'arrivée | 10 |

La météo fonctionne sans clé (Open-Meteo).

## Architecture

```
deplacements/
├── intents.py     actions du routeur : ACTIONS, handle_intent
├── planner.py     logique : meilleur trajet, alternative, heure de départ
├── weather.py     météo (Open-Meteo) + règle d'impact sur le trajet
├── transport.py   itinéraires et perturbations (PRIM / Navitia)
├── agenda.py      lien avec le module Planning (à brancher)
├── common.py      appel HTTP unique + exception DeplacementsError
└── config.py      réglages (.env) et constantes
```

Chaque couche n'appelle que celles du dessous : `intents → planner → weather / transport / agenda → common → config`.

## Comment `PLAN_TRAVEL` décide

1. Cherche des itinéraires arrivant avant l'heure demandée et garde le plus court (puis le moins de correspondances).
2. Vérifie les perturbations sur les lignes du trajet. S'il y en a, **relance l'itinéraire en excluant ces lignes**.
3. Ajoute de la marge selon la météo : **+5 min** s'il pleut, **+10 min** s'il neige.
4. Heure de départ = arrivée − durée du trajet − marge.

Si la météo ou les perturbations sont indisponibles, l'itinéraire est quand même renvoyé.

## Tests

```powershell
pytest
```

23 tests : contrat du routeur, lecture des entités, calcul d'heure de départ, choix du trajet, alternative en cas de perturbation, API en panne, lieu inconnu, marge pluie.

## Limites connues / à faire

- Le module Planning n'est pas encore branché : `agenda.get_next_appointment()` à implémenter.
- Les endpoints PRIM (`line_reports`, `forbidden_uris[]`) sont à valider avec une vraie clé.
- Prévisions météo limitées à environ 16 jours.
- Les heures sont sans fuseau horaire (heure locale).
