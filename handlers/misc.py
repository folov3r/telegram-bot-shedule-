from aiogram import F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters.command import Command
from aiogram.types import FSInputFile

from all_texts import help_message, start_message, text_log
from db_def import get_all_users_id
from other_def import login_lvl_1_keyboard, main_keyboard

generic_router = Router()


@generic_router.message(Command("start"))
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
@generic_router.message(Command("help"))
async def cmd_help(message: types.Message, **kwargs):
    await message.answer(help_message)


# "пасхалка"
@generic_router.message(F.text == "Lain")
async def egg_lain(message: types.Message, **kwargs):
    image_from_pc = FSInputFile("lain.jpg")
    await message.answer_photo(image_from_pc)
    await message.answer("No matter where you are. Everyone is always connected")


# "пасхалка"
@generic_router.message(F.text == "Me")
async def egg_me(message: types.Message):
    await message.answer("everything for everyone")


# /change - лог изменений в боте (для пользователей, текст заполняется в all_texts)
@generic_router.message(Command("change"))
async def send_change_logs(message: types.Message, **kwargs):
    await message.reply(text_log, parse_mode=ParseMode.HTML)




# Обработка запросов, не предусмотренных обработчиком бота
@generic_router.message()
async def any_mess(message: types.Message, **kwargs):
    await message.answer(
        "Пожалуйста, используйте экранные кнопки или команды, которые можно найти с помощью /help",
        reply_markup=main_keyboard,
    )
