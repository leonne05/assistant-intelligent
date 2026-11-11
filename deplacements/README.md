# 🧭 Module Déplacements — JARVIS

Responsable : **Moïra** · Branche : `feature/deplacements`

Ce module répond aux questions de déplacement de l'assistant : **météo**, **perturbations de transport** et **planification de trajet** (heure de départ, alternative, marge météo). Chaque appel renvoie **une phrase prête à être lue à voix haute**. Le module ne lève jamais d'exception.

## Intentions

| Intention | Paramètres | Exemple de réponse |
|---|---|---|
| `GET_WEATHER` | `city` (option), `day` (option, `AAAA-MM-JJ`) | « À Paris le 27/11 : pluie, 4 à 9°C… » |
| `CHECK_TRANSPORT` | `line` (ex. `"RER A"`) | « Aucune perturbation signalée sur RER A. » |
| `PLAN_TRAVEL` | `destination`, `arrive_by` (`AAAA-MM-JJTHH:MM`), `origin` (option), `city` (option) | « Pars à 08:05 : RER A, 40 min. » |

- `origin` vaut `HOME_ADDRESS` par défaut.
- `PLAN_TRAVEL` sans `destination` ni `arrive_by` prend le **prochain rendez-vous** du module Planning (via `agenda.py`).

## Utilisation

```python
from deplacements import handle_intent

handle_intent("GET_WEATHER", city="Paris", day="2026-11-27")
handle_intent("CHECK_TRANSPORT", line="RER A")
handle_intent("PLAN_TRAVEL", destination="HETIC Paris 13", arrive_by="2026-11-27T09:00")
```

Pour l'`IntentRouter` : `deplacements.HANDLERS` est un dictionnaire `{"GET_WEATHER": fonction, ...}` qui permet d'enregistrer les trois intentions.

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
├── intents.py     point d'entrée : handle_intent, HANDLERS
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

18 tests : calcul d'heure de départ, choix du trajet, alternative en cas de perturbation, API en panne, lieu inconnu, marge pluie.

## Limites connues / à faire

- Le module Planning n'est pas encore branché : `agenda.get_next_appointment()` à implémenter.
- Les endpoints PRIM (`line_reports`, `forbidden_uris[]`) sont à valider avec une vraie clé.
- Prévisions météo limitées à environ 16 jours.
- Les heures sont sans fuseau horaire (heure locale).
