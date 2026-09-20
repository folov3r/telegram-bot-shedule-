import logging
import os

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db_def import disable_notify, enable_notify, remove_user_def, get_user_data
from loader import bot
from .login import login

from util.keyboards import (
    back_feedback_keyboard,
    login_lvl_1_keyboard,
    main_keyboard,
    profile_keyboard,
    yes_no_keyboard,
)

profile_router = Router()

profile_messages = {}

class ProfileForm(StatesGroup):
    menu = State()
    delete_user = State()
    feedback = State()

# Обработка запроса на получение профиля для пользователя
@profile_router.message(F.text == "Профиль")
async def profile(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id
    value, is_teacher, notification_enabled = get_user_data(user_id)
    username = message.from_user.username
    if value is None or is_teacher is None:
        await message.answer(
            "Вас нет в базе данных. Пожалуйста, зарегистрируйтесь, прописав /login."
        )
        logging.info(
            f"Пользователь {username} сделал запрос, будучи не зарегистрированным"
        )
        return  # Завершаем выполнение функции

    if notification_enabled == 1:
        notification_enabled = "Включена"
    else:
        notification_enabled = "Выключена"

    if is_teacher == 0:
        is_teacher = "Студент"
    else:
        is_teacher = "Преподаватель"
    sent_message = await message.answer(
        f"""Ваш профиль:
👤Ваш юз: @{message.from_user.username}
👥Роль: {is_teacher}
❓Расписание кого отслеживаете: {value}
📩Авто рассылка: {notification_enabled}""",
        reply_markup=profile_keyboard,
    )
    profile_messages[user_id] = sent_message.message_id
    await state.set_state(ProfileForm.menu)

# Обработка функций системы профиля
@profile_router.message(ProfileForm.menu)
async def edit_profile_user(message: types.Message,state: FSMContext, **kwargs):
    text_message = message.text
    user_id = message.from_user.id
    value, is_teacher, notifications_enabled = get_user_data(user_id)
    if text_message == "Изменить данные":
        remove_user_def(user_id)
        await state.clear()
        await login(message, state)
    elif text_message == "Удалить аккаунт":
        await message.answer(
            "Вы уверены, что хотите перестать получать расписание?",
            reply_markup=yes_no_keyboard,
        )
        await state.set_state(ProfileForm.delete_user)
    elif text_message == "Авто рассылка":
        if notifications_enabled == 1:
            user_id = message.from_user.id
            disable_notify(user_id)
            await message.answer("🔕Уведомления отключены🔕")
        else:
            user_id = message.from_user.id
            enable_notify(user_id)
            await message.answer("🔔Уведомления включены🔔")
        if user_id in profile_messages:
            try:
                await bot.delete_message(
                    chat_id=user_id, message_id=profile_messages[user_id]
                )
                del profile_messages[user_id]
            except Exception as e:
                logging.error(f"Ошибка удаления сообщения профиля: {e}")
        await profile(message, state)
    elif text_message == "Обратная связь":
        await message.answer(
            "Напишите отзыв или жалобу по поводу работы бота, мы его отправим главному администратору:",
            reply_markup=back_feedback_keyboard,
        )
        await state.set_state(ProfileForm.feedback)
    elif text_message == "Вернуться":
        await message.answer("Главное меню:", reply_markup=main_keyboard)
        await state.clear()
    else:
        await message.answer(
            "Пожалуйста, используйте кнопки, которые вы видите на экране",
            reply_markup=profile_keyboard,
        )
    try:
        await bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except Exception as e:
        logging.error(f"Ошибка удаления сообщения пользователя: {e}")


# Обработка отправки отзыва глав админу
@profile_router.message(ProfileForm.feedback)
async def process_feedback(message: types.Message, state: FSMContext):
    username = message.from_user.username
    feedback = message.text
    if feedback == "Вернуться на главную":
        await message.answer("Главная:", reply_markup=main_keyboard)
    else:
        admin_id = os.getenv("MAIN_ADMIN_ID")
        if not admin_id:
            await message.answer("Главный администратор не установлен.", reply_markup=main_keyboard)
        else:
            await bot.send_message(
                chat_id=int(admin_id), text=f"Обратная связь от @{username}:\n\n{feedback}"
            )
            await message.answer("Спасибо за обратную связь!", reply_markup=main_keyboard)
    await state.clear()


# Обработка запроса на удаление данных из бд
@profile_router.message(ProfileForm.delete_user)
async def delete_conf_def(message: types.Message, state: FSMContext, **kwargs):
    text = message.text
    user_id = message.from_user.id
    if text == "Да":
        remove_user_def(user_id)
        await message.answer(
            "✅ Вы успешно удалили себя из системы.\nЕсли захотите вернуться, то вы можете повторно зарегистрироваться, нажав кнопку ниже или прописав /login, а также перезапустив бота.\nУдачи, до скорого 👋",
            reply_markup=login_lvl_1_keyboard,
        )
    elif text == "Нет":
        await message.answer("Спасибо, что вы остались!", reply_markup=main_keyboard)
    else:
        await message.answer("Пожалуйста, ответьте 'Да' или 'Нет' используя кнопки или клавиатуру.", reply_markup=yes_no_keyboard)
        return
    await state.clear()
