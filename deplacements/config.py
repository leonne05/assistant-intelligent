"""Configuration : secrets/réglages depuis le .env, valeurs techniques en dur."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PRIM_API_KEY = os.getenv("PRIM_API_KEY", "")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Neuilly-sur-Marne")
HOME_ADDRESS = os.getenv("HOME_ADDRESS", DEFAULT_CITY)
BUFFER_MINUTES = int(os.getenv("BUFFER_MINUTES", "10"))
# Position actuelle (voir location.py) : localisation Windows et serveur de position du téléphone
USE_PC_LOCATION = os.getenv("USE_PC_LOCATION", "true").lower() in ("1", "true", "oui", "yes")
POSITION_PORT = int(os.getenv("POSITION_PORT", "8765"))

RAIN_MARGIN = 5   # minutes ajoutées si pluie
SNOW_MARGIN = 10  # minutes ajoutées si neige
TIMEOUT = 10      # secondes avant d'abandonner un appel API
PHONE_POSITION_MAX_AGE = 10 * 60  # secondes : au-delà, la position du téléphone est trop vieille
PROJECT_DIR = Path(__file__).resolve().parent.parent
POSITION_FILE = PROJECT_DIR / ".position.json"  # dernière position du téléphone (local, ignoré par git)
CERT_DIR = PROJECT_DIR / ".certs"               # certificat HTTPS du serveur de position
NAVITIA = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"
