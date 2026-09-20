import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv


load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
storage = RedisStorage.from_url(REDIS_URL) if REDIS_URL else MemoryStorage()

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=storage)
