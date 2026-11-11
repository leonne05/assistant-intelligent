"""Démo en ligne de commande du module Déplacements."""
import logging

from deplacements import handle_intent

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(handle_intent("GET_WEATHER", {"location": "Caen", "datetime": "2026-11-12T14:00"},
                        "Quel temps fera-t-il demain à Caen ?"))
    print(handle_intent("CHECK_TRANSPORT", {}, "Y a-t-il des perturbations sur le RER A ?"))
    print(handle_intent("PLAN_TRAVEL", {"location": "HETIC Paris 13", "datetime": "2026-11-27T09:00"},
                        "Quand dois-je partir pour être à HETIC à 9h ?"))
