"""Configuration : secrets/réglages depuis le .env, valeurs techniques en dur."""
import os

from dotenv import load_dotenv

load_dotenv()

PRIM_API_KEY = os.getenv("PRIM_API_KEY", "")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Neuilly-sur-Marne")
HOME_ADDRESS = os.getenv("HOME_ADDRESS", DEFAULT_CITY)
BUFFER_MINUTES = int(os.getenv("BUFFER_MINUTES", "10"))

RAIN_MARGIN = 5   # minutes ajoutées si pluie
SNOW_MARGIN = 10  # minutes ajoutées si neige
TIMEOUT = 10      # secondes avant d'abandonner un appel API
NAVITIA = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"
