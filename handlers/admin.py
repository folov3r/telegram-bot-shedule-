import logging
import os

from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.types import FSInputFile

from all_texts import admin_comm
from db_def import (
    add_admin, get_admin_role, get_all_admins, get_all_users_data,
    get_all_users_id, get_username_admin, remove_admin_def,
)
from loader import bot

admin_router = Router()

ROLE_ADMIN = 1
ROLE_SECONDARY_ADMIN = 2
ROLE_MAIN_ADMIN = 3

# Декоратор для проверки роли администрации
def has_role(required_role: int):
    def decorator(func):
        async def wrapper(message: types.Message, *args, **kwargs):
            user_id = message.from_user.id
            user_role = get_admin_role(user_id)
            if user_role >= required_role:
                return await func(message, *args, **kwargs)
            await message.answer("У вас недостаточно прав для выполнения этой команды.")

        return wrapper

    return decorator

@admin_router.message(Command("add_admin"))
@has_role(ROLE_SECONDARY_ADMIN)
async def set_role(message: types.Message, **kwargs):
    try:
        _, user_id, username, role = message.text.split()
        user_id = int(user_id)
        role = int(role)
        username = str(username)

        role_admin = get_admin_role(message.from_user.id)
        if role_admin >= role:
            if role not in [ROLE_ADMIN, ROLE_SECONDARY_ADMIN, ROLE_MAIN_ADMIN]:
                await message.answer("Недопустимая роль уровня доступа.")
                return
            add_admin(user_id, username, role, message.from_user.username)
            logging.warning(
                f"Пользователь {message.from_user.username} назначил пользователя {username} администратором с уровнем доступа {role}"
            )
            await message.answer(
                f"✅ Уровень доступа {role} для пользователя {username} назначена успешно."
            )
        else:
            await message.answer(
                f"❌ Вы не можете назначить пользователя на роль администратора с уровнем доступа {role} из соображения безопасности"
            )
            logging.warning(
                f"Пользователь {message.from_user.username} попытался назначить пользователя {username} администратором с уровнем доступа {role}"
            )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@admin_router.message(Command("remove_admin"))
@has_role(ROLE_SECONDARY_ADMIN)
async def remove_admin(message: types.Message, **kwargs):
    try:
        _, user_id = message.text.split()
        user_id = int(user_id)
        admin_role = get_admin_role(message.from_user.id)
        remove_admin_role = get_admin_role(user_id)
        username_remove_admin = get_username_admin(user_id)
        if admin_role >= remove_admin_role:
            remove_admin_def(user_id)
            logging.warning(
                f"Пользователь {message.from_user.username} отозвал права доступа у пользователя {username_remove_admin}"
            )
            await message.answer(
                f"✅ Пользователь {username_remove_admin} больше не администратор."
            )
        else:
            logging.warning(
                f"Пользователь {message.from_user.username} попытался удалить администратора {username_remove_admin}"
            )
            await message.answer(
                "❌ Вы не можете удалить данного администратора, так как его уровень доступа выше вашего"
            )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


# Отправка списка администраторов
@admin_router.message(Command("list_admins"))
@has_role(ROLE_ADMIN)
async def list_admins(message: types.Message, **kwargs):
    admins = get_all_admins()
    if not admins:
        await message.answer("Администраторы не найдены.")
        return
    admins_list = "\n".join(
        [
            f"|🆔: {user_id}| |@ : {username}| |status: {role}| |who add: @{who_add}|"
            for user_id, username, role, who_add in admins
        ]
    )
    await message.answer(f"Список администраторов:\n{admins_list}")


# Функция авто рассылки сообщения для всех пользователей в дб users
@admin_router.message(Command("broadcast"))
@has_role(ROLE_SECONDARY_ADMIN)
async def broadcast_message(message: types.Message, **kwargs):
    try:
        text_to_send = message.text.split(maxsplit=1)[1]
    except IndexError:
        await message.answer(
            "Используйте команду в формате: /broadcast <текст сообщения>"
        )
        return

    users = get_all_users_id()
    if not users:
        await message.answer("В базе данных нет пользователей.")
        return

    success_count = 0
    failed_count = 0

    for user_id in users:
        try:
            await bot.send_message(user_id, text_to_send)
            success_count += 1
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            failed_count += 1

    await message.answer(
        f"Сообщение отправлено:\n"
        f"✅ Успешно: {success_count}\n"
        f"❌ Не удалось: {failed_count}"
    )


# Получение списка пользователей
@admin_router.message(Command("list_users"))
@has_role(ROLE_SECONDARY_ADMIN)
async def list_users(message: types.Message, **kwargs):
    users = get_all_users_data()

    if not users:
        await message.answer("В базе данных нет пользователей.")
        return

    count_users = len(users)
    students = [user for user in users if user[3] == 0]
    teachers = [user for user in users if user[3] == 1]

    students_list = "\n".join(
        f"|🆔: {user_id}| |👤: @{username}| |Группа: {value}| |🔔: {notifications_enabled}|"
        for user_id, username, value, _, notifications_enabled in students
    )

    teachers_list = "\n".join(
        f"|🆔: {user_id}| |👤: @{username}| |ФИО: {value}| |🔔: {notifications_enabled}|"
        for user_id, username, value, _, notifications_enabled in teachers
    )

    await message.answer(
        f"Зарегистрированных пользователей: {count_users}\n\n"
        f"Студенты (всего: {len(students)}):\n{students_list}\n\n"
        f"Преподаватели (всего: {len(teachers)}):\n{teachers_list}"
    )


# Получение логов в виде txt файла
@admin_router.message(Command("logs_txt"))
@has_role(ROLE_SECONDARY_ADMIN)
async def send_logs(message: types.Message, **kwargs):
    file_name = "log/log.txt"
    file_from_pc = FSInputFile(file_name)
    await message.answer_document(file_from_pc)


# Список команд для администрации
@admin_router.message(Command("admin"))
@has_role(ROLE_ADMIN)
async def send_admin_commands(message: types.Message, **kwargs):
    await message.answer(admin_comm)


def bootstrap_main_admin():
    admin_id = os.getenv("MAIN_ADMIN_ID")
    if not admin_id:
        logging.warning("MAIN_ADMIN_ID не задан в .env: главный администратор не назначен.")
        return
    try:
        admin_id = int(admin_id)
    except ValueError as e:
        logging.warning(f"TG ID имеет посторонние символы({e}), отличные от допустимых. проверьте .env файл")
        return
    add_admin(admin_id, os.getenv("MAIN_ADMIN_NAME", ""), ROLE_MAIN_ADMIN, "system")
    logging.info(f"Главный администратор {admin_id} назначен.")


bootstrap_main_admin()
