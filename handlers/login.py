import logging

from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db_def import save_user_data
from util.keyboards import (
    create_keyboard,
    main_keyboard,
    return_keyboard,

)
from util.parsing import validate_and_correct_group

class LoginForm(StatesGroup):
    choosing_role = State()
    choosing_value = State()

login_router = Router()

@login_router.message(Command("login"))
async def login(message: types.Message, state: FSMContext, **kwargs):
    await state.set_state(LoginForm.choosing_role)
    role_keyboard = create_keyboard([["Студент", "Преподаватель"]])
    await message.answer(
        "Кто вы?\nСтудент или преподаватель?", reply_markup=role_keyboard
    )

# Получение role от пользователя
@login_router.message(LoginForm.choosing_role)
async def ask_for_value(message: types.Message, state: FSMContext, **kwargs):
    role = message.text

    if role == "Студент":
        await message.answer(
            "Пожалуйста, введите группу, расписания которой хотите получать.\nЖелательно указывать группу правильно, соблюдая регистр и правильность написания.\nНапример:\n✅ ОП-2 ✅\n❌ оп 2; Оп2; оП-2 ❌",
            reply_markup=return_keyboard,
        )
        await state.update_data(role=role)
        await state.set_state(LoginForm.choosing_value)
    elif role == "Преподаватель":
        await message.answer(
            "Пожалуйста, введите ваше ФИО (например, Иванов И.И.).",
            reply_markup=return_keyboard,
        )
        await state.update_data(role=role)
        await state.set_state(LoginForm.choosing_value)
    else:
        await message.answer("Пожалуйста, используйте на экранные кнопки")
        return


# Сохранение value и role для пользователя при login
@login_router.message(LoginForm.choosing_value)
async def save_inform(message: types.Message, state: FSMContext, **kwargs):
    user_id = message.from_user.id
    value = message.text
    data = await state.get_data()
    role = data.get("role")
    username = message.from_user.username
    if value == "Вернуться":
        await state.clear()
        await login(message, state)
    else:
        if role == "Студент":
            validated_group, is_valid = validate_and_correct_group(value)
            if is_valid:
                save_user_data(
                    user_id, message.from_user.username, validated_group, is_teacher=0
                )
                await message.reply(
                    f"Вы успешно зарегистрировались. Вы будете получать расписание для группы {validated_group}.",
                    reply_markup=main_keyboard,
                )
                await state.clear()
                logging.info(
                    f"Пользователь {username} зарегистрировался как студент, поприветствуем!"
                )
            else:
                await message.answer(
                    "Некорректный номер группы. Пожалуйста, введите номер группы снова."
                )
                return
        elif role == "Преподаватель":
            save_user_data(user_id, message.from_user.username, value, is_teacher=1)
            await message.reply(
                f"Вы успешно зарегистрировались. Вы будете получать расписание для преподавателя {value}",
                reply_markup=main_keyboard,
            )
            await state.clear()
            logging.info(
                f"Пользователь {username} зарегистрировался как преподаватель, поприветствуем!"
            )
