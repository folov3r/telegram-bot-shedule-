from aiogram import types



def create_keyboard(buttons: list[list[str]]) -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=btn) for btn in row] for row in buttons],
        resize_keyboard=True,
    )


main_keyboard = create_keyboard(
    [["Проверить расписание", "Расписание звонков"], ["Профиль"]]
)

schedule_keyboard = create_keyboard(
    [["Сегодня", "Завтра"], ["После завтра", "Другая дата"], ["Отмена"]]
)

cancel_keyboard = create_keyboard([["Отмена"]])

return_keyboard = create_keyboard([["Вернуться"]])

profile_keyboard = create_keyboard(
    [
        ["Изменить данные", "Удалить аккаунт"],
        ["Авто рассылка"],
        ["Обратная связь"],
        ["Вернуться"],
    ]
)

login_lvl_1_keyboard = create_keyboard([["/login"]])

yes_no_keyboard = create_keyboard([["Да", "Нет"]])

back_feedback_keyboard = create_keyboard([["Вернуться на главную"]])
