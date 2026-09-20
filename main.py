import asyncio
import logging
import os

from aiogram.fsm.context import FSMContext
from aiogram import F, types
from aiogram.enums import ParseMode
from aiogram.filters.command import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from all_texts import help_message, start_message, text_log, zvon_schedule
from db_def import (
    disable_notify,
    enable_notify,
    get_all_users_id,
    remove_user_def,
)
from other_def import (
    back_feedback_keyboard,
    cancel_keyboard,
    create_keyboard,
    download_other_date,
    download_schedule,
    evening_schedule_task,
    get_user_data,
    login_lvl_1_keyboard,
    main_keyboard,
    morning_schedule_task,
    profile_keyboard,
    return_keyboard,
    save_user_data,
    schedule_keyboard,
    send_as_text2,
    send_schedule,
    validate_and_correct_group,
    yadisk_client,
    yes_no_keyboard,
)
from loader import bot, dp
from admin import admin_router


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


class LoginForm(StatesGroup):
    choosing_role = State()
    choosing_value = State()

class ProfileForm(StatesGroup):
    menu = State()
    delete_user = State()
    feedback = State()

class ScheduleForm(StatesGroup):
    choosing_period = State()
    choosing_other_date = State()

if yadisk_client.check_token():
    logging.info("Valid API Yandex? True")
else:
    logging.info("Valid API Yandex? False")

logging.getLogger("yadisk").setLevel(logging.WARNING)

dp.include_router(admin_router)

@dp.message(Command("login"))
async def login(message: types.Message, state: FSMContext, **kwargs):
    await state.set_state(LoginForm.choosing_role)
    role_keyboard = create_keyboard([["Студент", "Преподаватель"]])
    await message.answer(
        "Кто вы?\nСтудент или преподаватель?", reply_markup=role_keyboard
    )


# Получение role от пользователя
@dp.message(LoginForm.choosing_role)
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
@dp.message(LoginForm.choosing_value)
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


profile_messages = {}


# Обработка запроса на получение профиля для пользователя
@dp.message(F.text == "Профиль")
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
@dp.message(ProfileForm.menu)
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
@dp.message(ProfileForm.feedback)
async def process_feedback(message: types.Message, state: FSMContext):
    username = message.from_user.username
    feedback = message.text
    if feedback == "Вернуться на главную":
        await message.answer("Главная:", reply_markup=main_keyboard)
    else:
        admin_id = int(os.getenv("MAIN_ADMIN_ID"))
        if not admin_id:
            await message.answer("Главный администратор не установлен.", reply_markup=main_keyboard)
        else:
            await bot.send_message(
                chat_id=admin_id, text=f"Обратная связь от @{username}:\n\n{feedback}"
            )
        await message.answer("Спасибо за обратную связь!", reply_markup=main_keyboard)
    await state.clear()


# Обработка запроса на удаление данных из бд
@dp.message(ProfileForm.delete_user)
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


@dp.message(Command("start"))
async def cmd_start(message: types.Message, **kwargs):
    check_id = get_all_users_id()
    if message.from_user.id in check_id:
        await message.answer(
            start_message, reply_markup=main_keyboard, parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(start_message, parse_mode=ParseMode.HTML)
        await message.answer(
            "Вас нет в базе для получения расписания. Чтобы работать с ботом, вам нужно пройти процесс регистрации.\nПожалуйста, нажмите кнопку снизу или напишите /login ",
            reply_markup=login_lvl_1_keyboard,
        )


# Вызов списка команд для пользователей
@dp.message(Command("help"))
async def cmd_help(message: types.Message, **kwargs):
    await message.answer(help_message)


# "пасхалка"
@dp.message(F.text == "Lain")
async def egg_lain(message: types.Message, **kwargs):
    image_from_pc = FSInputFile("lain.jpg")
    await message.answer_photo(image_from_pc)
    await message.answer("No matter where you are. Everyone is always connected")


# "пасхалка"
@dp.message(F.text == "Me")
async def egg_me(message: types.Message):
    await message.answer("everything for everyone")


# /change - лог изменений в боте (для пользователей, текст заполняется в all_texts)
@dp.message(Command("change"))
async def send_change_logs(message: types.Message, **kwargs):
    await message.reply(text_log, parse_mode=ParseMode.HTML)


# Получение ботом запроса для получения расписания пользователем на интересующий день
@dp.message(F.text == "Проверить расписание")
async def check_schedule(message: types.Message, state: FSMContext, **kwargs):
    await state.set_state(ScheduleForm.choosing_period)
    await message.reply("Расписание на:", reply_markup=schedule_keyboard)


# Функция обработки запроса получения расписания
@dp.message(ScheduleForm.choosing_period)
async def handle_schedule_choice(message: types.Message, state: FSMContext, **kwargs):
    text = message.text
    if text == "Сегодня":
        await state.clear()
        await send_schedule(message, days_offset=0, caption="Расписание на сегодня")
        await send_schedule(
            message, days_offset=0, caption="Расписание на сегодня", send_as_text=True
        )
    elif text == "Завтра":
        await state.clear()
        await send_schedule(message, days_offset=1, caption="Расписание на завтра")
        await send_schedule(
            message, days_offset=1, caption="Расписание на завтра", send_as_text=True
        )
    elif text == "После завтра":
        await state.clear()
        await send_schedule(
            message, days_offset=2, caption="Расписание на после завтра"
        )
        await send_schedule(
            message,
            days_offset=2,
            caption="Расписание на после завтра",
            send_as_text=True,
        )
    elif text == "Другая дата":
        await state.set_state(ScheduleForm.choosing_other_date)
        await message.answer(
            "Пришлите дату в формате дд.мм.гггг", reply_markup=cancel_keyboard
        )
    elif text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено", reply_markup=main_keyboard)
    else:
        await message.answer("Пожалуйста, используйте на экранные кнопки")


# Отправка расписания звонков
@dp.message(F.text == "Расписание звонков")
async def schedule_zvon(message: types.Message, **kwargs):
    await message.answer(f"Расписание звонков:\n\n{zvon_schedule}")


# Функция отправки расписания на интересующую дату пользователя
@dp.message(ScheduleForm.choosing_other_date)
async def other_data_send(message: types.Message, state: FSMContext):
    text = message.text
    file_name = f"schedule/{text}.docx"

    if text == "Отмена":
        await message.answer("Действие отменено", reply_markup=main_keyboard)
        await state.clear()
        return

    await message.answer("🔎Производится поиск расписания, ожидайте...")

    # Проверяем, существует ли файл на сервере
    if not os.path.isfile(file_name):
        # Если файла нет, пытаемся скачать его с диска
        success = await download_other_date(text)
        if not success:
            await message.answer(
                "Вы ввели неправильные данные, либо расписания нет, извините",
                reply_markup=main_keyboard,
            )
            await state.clear()
            return
    # После скачивания проверяем, появился ли файл на сервере
    if os.path.isfile(file_name):
        try:
            file_from_pc = FSInputFile(file_name)
            await message.answer_document(
                file_from_pc,
                caption=f"Расписание на {text}",
                reply_markup=main_keyboard,
            )
            await send_as_text2(message, file_name)
        except Exception as e:
            logging.error(f"Ошибка при отправке файла: {e}")
            await message.answer(
                "Произошла ошибка при отправке расписания.", reply_markup=main_keyboard
            )
    else:
        await message.answer(
            "Расписание не найдено, извините.", reply_markup=main_keyboard
        )

    await state.clear()


# Обработка запросов, не предусмотренных обработчиком бота
@dp.message()
async def any_mess(message: types.Message, **kwargs):
    await message.answer(
        "Пожалуйста, используйте экранные кнопки или команды, которые можно найти с помощью /help",
        reply_markup=main_keyboard,
    )


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


async def start_scheduler():
    scheduler.start()
    logging.info("Планировщик запущен.")
    logging.info("Бот запущен")


async def main():
    asyncio.create_task(start_scheduler())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
