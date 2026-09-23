import logging
import os

from all_texts import use_button_msg

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile

from all_texts import zvon_schedule
from util.keyboards import (
    cancel_keyboard,
    main_keyboard,
    schedule_keyboard
)
from util.dispatch import download_other_date, send_text_schedule, send_schedule

schedule_router = Router()

class ScheduleForm(StatesGroup):
    choosing_period = State()
    choosing_other_date = State()

# Получение ботом запроса для получения расписания пользователем на интересующий день
@schedule_router.message(F.text == "Проверить расписание")
async def check_schedule(message: types.Message, state: FSMContext, **kwargs) -> None:
    await state.set_state(ScheduleForm.choosing_period)
    await message.reply("Расписание на:", reply_markup=schedule_keyboard)


# Функция обработки запроса получения расписания
@schedule_router.message(ScheduleForm.choosing_period)
async def handle_schedule_choice(message: types.Message, state: FSMContext, **kwargs) -> None:
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
        await message.answer(use_button_msg)


# Отправка расписания звонков
@schedule_router.message(F.text == "Расписание звонков")
async def schedule_zvon(message: types.Message, **kwargs) -> None:
    await message.answer(f"Расписание звонков:\n\n{zvon_schedule}")


# Функция отправки расписания на интересующую дату пользователя
@schedule_router.message(ScheduleForm.choosing_other_date)
async def other_data_send(message: types.Message, state: FSMContext) -> None:
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
            await send_text_schedule(message, file_name, f"на {text}")
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
