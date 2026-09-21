import asyncio
import logging
import os
import sqlite3
from datetime import date, timedelta

import yadisk
from util.keyboards import main_keyboard
from util.parsing import process_schedule_file, format_teacher_schedule
from aiogram import types
from aiogram.types import FSInputFile
from dotenv import load_dotenv

from db_def import get_all_users_data, get_all_users_id, get_user_data
from loader import bot
load_dotenv()

YANDEX_TOKEN = os.getenv("YANDEX_TOKEN")

yadisk_client = yadisk.Client(token=YANDEX_TOKEN)

YANDEX_DISK_ROOT = os.getenv("YANDEX_DISK_ROOT", "app:/")
YANDEX_SCHEDULE_FILENAME = os.getenv("YANDEX_SCHEDULE_FILENAME", "schedule.docx")


def check_and_notify(file_name: str) -> None:
    with sqlite3.connect("db/notifications.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT notified FROM notifications WHERE file_name = ?", (file_name,)
        )
        result = cursor.fetchone()

        if not result or not result[0]:
            users = get_all_users_id()
            splited_name = file_name.split(".docx")[0]
            for user_id in users:
                asyncio.create_task(
                    send_notification(user_id, f"{splited_name} загружено на сервер.")
                )

            cursor.execute(
                """
                INSERT OR REPLACE INTO notifications (file_name, notified)
                VALUES (?, ?)
            """,
                (file_name, True),
            )
            conn.commit()


async def send_schedule(message: types.Message, days_offset: int, caption: str, send_as_text: bool = False) -> None:
    target_date = (date.today() + timedelta(days=days_offset)).strftime("%d.%m.%Y")
    file_name = f"schedule/{target_date}.docx"
    user_id = message.from_user.id
    value, is_teacher, _ = get_user_data(user_id)
    username = message.from_user.username
    if value is None or is_teacher is None:
        if send_as_text:
            await message.answer(
                "Чтобы получать расписание в текстовой форме, зарегистрируйтесь, прописав /login."
            )
            logging.info(
                f"Пользователь {username} сделал запрос, будучи не зарегистрированным"
            )
        else:
            if os.path.isfile(file_name):
                file_from_pc = FSInputFile(file_name)
                await message.answer_document(
                    file_from_pc, caption=caption, reply_markup=main_keyboard
                )
            else:
                await message.answer(
                    "Расписания пока еще нет, извините", reply_markup=main_keyboard
                )
        return

    try:
        if send_as_text:
            schedule_data, teacher_schedule_data = process_schedule_file(file_name)
            if schedule_data and teacher_schedule_data:
                if is_teacher:
                    response = format_teacher_schedule(teacher_schedule_data, value, f"на {target_date}")
                    if response:
                        await message.answer(response)
                    else:
                        await message.answer("У вас нет пар на этот день.")
                else:
                    if value in schedule_data:
                        await message.answer(
                            f"Расписание для группы {value} на {target_date}:\n\n|Пара| |Преподаватель| |Кабинет|\n\n{schedule_data[value]}"
                        )
                    else:
                        await message.answer("Расписание для вашей группы не найдено.")
            else:
                await message.answer("Извините, расписание не удалось обработать.")
        else:
            if os.path.isfile(file_name):
                file_from_pc = FSInputFile(file_name)
                await message.answer_document(
                    file_from_pc, caption=caption, reply_markup=main_keyboard
                )
            else:
                await message.answer(
                    "Расписания пока еще нет, извините", reply_markup=main_keyboard
                )

    except Exception as e:
        logging.error(f"Ошибка поиска файла: {e}")


async def send_as_text2(message: types.Message, file_name: str) -> None:
    target_date = message.text
    user_id = message.from_user.id
    username = message.from_user.username
    schedule_data, teacher_schedule_data = process_schedule_file(file_name)
    if schedule_data and teacher_schedule_data:
        value, is_teacher, _ = get_user_data(user_id)

        if value is None or is_teacher is None:
            await message.answer(
                "Чтобы получать расписание в текстовой форме, зарегистрируйтесь, написав /login."
            )
            logging.info(
                f"Пользователь {username} сделал запрос, будучи не зарегистрированным"
            )
            return

        if is_teacher:
            response = format_teacher_schedule(teacher_schedule_data, value, f"на {target_date}")
            if response:
                await message.answer(response)
            else:
                await message.answer(
                    "Судя по файлу, у вас нет пар на этот день. Возможно, произошла ошибка."
                )
        else:
            if value in schedule_data:
                await message.answer(
                    f"Расписание для группы {value} на {target_date}:\n\n|Пара| |Преподаватель| |Кабинет|\n\n{schedule_data[value]}"
                )
            else:
                await message.answer("Расписание для вашей группы не найдено.")
    else:
        await message.answer("Извините, расписание не удалось обработать.")


async def send_notification(chat_id: int, message: str) -> None:
    await bot.send_message(chat_id, message)

def find_file_sync(client: yadisk.Client, directory: str, filename: str) -> str | None:
    for item in client.listdir(directory):
        if item["type"] == "dir":
            found_file = find_file_sync(client, item["path"], filename)
            if found_file:
                return found_file
        elif item["name"] == filename:
            return item["path"]
    return None


async def download_other_date(date_str: str | None) -> bool:
    target_date = date_str
    filename = YANDEX_SCHEDULE_FILENAME
    root_directory = YANDEX_DISK_ROOT

    try:
        file_path = await asyncio.to_thread(
            find_file_sync, yadisk_client, root_directory, filename
        )
        if file_path:
            local_path = f"schedule/{target_date}.docx"
            await asyncio.to_thread(yadisk_client.download, file_path, local_path)
            logging.info(f"Файл на {target_date} скачен из {file_path}")
            return True  # Файл успешно скачан
        else:
            logging.warning(f"Файла на {target_date} нет")
            return False  # Файл не найден
    except Exception as e:
        logging.error(f"Ошибка при скачивании файла на {target_date}: {e}")
        return False  # Произошла ошибка


async def download_schedule(days_offset: int) -> None:
    target_date = (date.today() + timedelta(days=days_offset)).strftime("%d.%m.%Y")
    filename = YANDEX_SCHEDULE_FILENAME
    root_directory = YANDEX_DISK_ROOT

    try:
        file_path = await asyncio.to_thread(
            find_file_sync, yadisk_client, root_directory, filename
        )
        if file_path:
            local_path = f"schedule/{target_date}.docx"
            await asyncio.to_thread(yadisk_client.download, file_path, local_path)
            logging.info(f"Файл на {target_date} скачен из {file_path}")
            check_and_notify(f"{target_date}.docx")
        else:
            logging.warning(f"Файла на {target_date} нет")
    except Exception as e:
        logging.error(f"Ошибка при скачивании файла на {target_date}: {e}")


async def send_schedule_to_all_users(days_offset: int, caption: str) -> None:
    users = get_all_users_data()
    if not users:
        logging.warning("Нет пользователей для рассылки расписания.")
        return

    target_date = (date.today() + timedelta(days=days_offset)).strftime("%d.%m.%Y")
    file_name = f"schedule/{target_date}.docx"

    if not os.path.isfile(file_name):
        logging.warning(f"Файл расписания на {target_date} не найден.")
        return

    day_text = "на сегодня" if days_offset == 0 else "на завтра"

    for user_id, username, value, is_teacher, notifications_enabled in users:
        if notifications_enabled == 1:
            try:
                # Отправляем файл с расписанием
                file_from_pc = FSInputFile(file_name)
                await bot.send_document(user_id, file_from_pc, caption=caption)

                # Обрабатываем расписание для текстового вывода
                schedule_data, teacher_schedule_data = process_schedule_file(file_name)
                if schedule_data is None or teacher_schedule_data is None:
                    logging.warning(f"Не удалось обработать расписание на {target_date} для {user_id}")
                    continue
                if is_teacher:
                    if value in teacher_schedule_data:
                        # Форматируем расписание для преподавателя
                        response = format_teacher_schedule(teacher_schedule_data, value, day_text)
                        if response:
                            await bot.send_message(user_id, response)
                        else:
                            await bot.send_message(
                                user_id,
                                "Возможно у вас нет пар на этот день. Возможно, произошла ошибка",
                            )
                else:
                    if value in schedule_data:
                        await bot.send_message(
                            user_id,
                            f"Расписание для группы {value} {day_text}:\n\n{schedule_data[value]}",
                        )
                    else:
                        await bot.send_message(
                            user_id, "Расписание для вашей группы не найдено."
                        )
            except Exception as e:
                logging.error(
                    f"Не удалось отправить расписание пользователю {user_id}: {e}"
                )
        else:
            continue


async def morning_schedule_task() -> None:
    await send_schedule_to_all_users(days_offset=0, caption="Расписание на сегодня")


async def evening_schedule_task() -> None:
    await send_schedule_to_all_users(days_offset=1, caption="Расписание на завтра")
