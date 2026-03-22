import os

from dotenv import load_dotenv

load_dotenv(override=True)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID")
DAILY_API_KEY = os.getenv("DAILY_API_KEY")
DAILY_API_URL = "https://api.daily.co/v1"

SESSION_TIMEOUT_MINUTES = 15
