import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from handlers import (
    admin_router,
    generic_router,
    login_router,
    profile_router,
    schedule_router,
)
from loader import bot, dp
from util.dispatch import download_schedule, evening_schedule_task, morning_schedule_task, yadisk_client



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("log/log.txt", encoding="utf-8-sig"),
        logging.StreamHandler(),
    ],
)

logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("aiogram").setLevel(logging.WARNING)


if yadisk_client.check_token():
    logging.info("Valid API Yandex? True")
else:
    logging.info("Valid API Yandex? False")

logging.getLogger("yadisk").setLevel(logging.WARNING)

# Подключение роутеров
dp.include_router(login_router)
dp.include_router(profile_router)
dp.include_router(schedule_router)
dp.include_router(admin_router)
dp.include_router(generic_router)

scheduler = AsyncIOScheduler()

for days_offset in [0, 1, 2]:
    scheduler.add_job(
        download_schedule,
        "interval",
        minutes=5,
        args=[days_offset],
        misfire_grace_time=30 * (days_offset + 1),
    )

scheduler.add_job(
    morning_schedule_task, CronTrigger(hour=7, minute=0), misfire_grace_time=300
)

scheduler.add_job(
    evening_schedule_task, CronTrigger(hour=20, minute=00), misfire_grace_time=300
)


async def start_scheduler() -> None:
    scheduler.start()
    logging.info("Планировщик запущен.")
    logging.info("Бот запущен")


async def main() -> None:
    asyncio.create_task(start_scheduler())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
