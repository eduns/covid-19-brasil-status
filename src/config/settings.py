import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
COVID19_DATA_URL = os.getenv('COVID19_DATA_URL')