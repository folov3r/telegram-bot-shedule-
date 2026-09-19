import asyncio
import os

os.environ["TELEGRAM_TOKEN"] = "123456789:FAKETOKEN"
os.environ["YANDEX_TOKEN"] = "fake"

import other_def
other_def.yadisk_client.check_token = lambda: False
other_def.yadisk_client.get_public_files = lambda *a, **k: []

import main

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

passed = 0
total = 0

def check(name, cond, detail=""):
    global passed, total
    total += 1
    if cond:
        passed += 1
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}: {detail}")

class MockUser:
    def __init__(self, uid=111):
        self.id = uid
        self.username = "testuser"

class MockChat:
    id = 111
    type = "private"

class MockMessage:
    _seq = 0

    def __init__(self, text, uid=111):
        self.text = text
        self.from_user = MockUser(uid)
        self.chat = MockChat()
        self.message_id = 1
        self.answers = []
    async def answer(self, text, **kw):
        self.answers.append(text)
        return self._sent()
    async def reply(self, text, **kw):
        self.answers.append(text)
        return self._sent()
    async def answer_document(self, *a, **k):
        self.answers.append("document")
        return self._sent()
    async def answer_photo(self, *a, **k):
        self.answers.append("photo")
        return self._sent()
    def _sent(self):
        MockMessage._seq += 1
        return _SentMessage(MockMessage._seq)

class _SentMessage:
    def __init__(self, message_id):
        self.message_id = message_id

class FakeBot:
    def __init__(self):
        self.deleted = []
    async def delete_message(self, chat_id, message_id):
        self.deleted.append(message_id)
    async def send_message(self, chat_id, text):
        pass

async def run():
    storage = MemoryStorage()
    key = StorageKey(bot_id=main.bot.id, chat_id=111, user_id=111)
    state = FSMContext(storage=storage, key=key)

    # ---- ЗАПИСЬ ТЕСТОВОГО СТУДЕНТА ----
    msg = MockMessage("/login")
    await main.login(msg, state)
    msg = MockMessage("Студент")
    await main.ask_for_value(msg, state)
    msg = MockMessage("ОП-2")
    await main.save_inform(msg, state)
    check("студент зарегистрирован", (await state.get_state()) is None)

    # ---- ПРОФИЛЬ: открытие меню ----
    msg = MockMessage("Профиль")
    await main.profile(msg, state)
    s = await state.get_state()
    check("профиль открыл меню", s == main.ProfileForm.menu, s)

    # ---- УДАЛИТЬ АККАУНТ -> подтверждение -> Да ----
    msg = MockMessage("Удалить аккаунт")
    fake = FakeBot()
    main.bot = fake
    await main.edit_profile_user(msg, state)
    s = await state.get_state()
    check("кнопка Удалить -> delete_user", s == main.ProfileForm.delete_user, s)
    msg = MockMessage("Да")
    await main.delete_conf_def(msg, state)
    s = await state.get_state()
    removed = main.get_user_data(111)[0] is None
    check("подтверждение Да: юзер удалён, state сброшен", s is None and removed, (s, removed))

    # ---- ПРОФИЛЬ: Авто рассылка тоггл ----
    msg = MockMessage("/login")
    await main.login(msg, state)
    msg = MockMessage("Студент")
    await main.ask_for_value(msg, state)
    msg = MockMessage("ОП-2")
    await main.save_inform(msg, state)
    msg = MockMessage("Профиль")
    await main.profile(msg, state)
    before = main.get_user_data(111)[2]
    msg = MockMessage("Авто рассылка")
    await main.edit_profile_user(msg, state)
    after = main.get_user_data(111)[2]
    check("Авто рассылка переключила уведомления", before != after, (before, after))
    s = await state.get_state()
    check("Авто рассылка вернула меню профиля", s == main.ProfileForm.menu, s)

    # ---- ПРОФИЛЬ: Обратная связь ----
    msg = MockMessage("Обратная связь")
    await main.edit_profile_user(msg, state)
    s = await state.get_state()
    check("Обратная связь -> state feedback", s == main.ProfileForm.feedback, s)
    msg = MockMessage("Вернуться на главную")
    await main.process_feedback(msg, state)
    s = await state.get_state()
    check("feedback: выход в главное меню, state сброшен", s is None, s)

    # ---- ПРОФИЛЬ: Изменить данные -> логин заново ----
    msg = MockMessage("Профиль")
    await main.profile(msg, state)
    msg = MockMessage("Изменить данные")
    await main.edit_profile_user(msg, state)
    s = await state.get_state()
    check("Изменить данные -> перешли в выбор роли", s == main.LoginForm.choosing_role, s)

    # ---- РАСПИСАНИЕ: выбор периода -> другая дата -> отмена ----
    msg = MockMessage("Проверить расписание")
    await main.check_schedule(msg, state)
    s = await state.get_state()
    check("Проверить расписание -> choosing_period", s == main.ScheduleForm.choosing_period, s)
    text = MockMessage("Другая дата")
    await main.handle_schedule_choice(text, state)
    s = await state.get_state()
    check("Другая дата -> choosing_other_date", s == main.ScheduleForm.choosing_other_date, s)
    msg = MockMessage("Отмена")
    await main.other_data_send(msg, state)
    s = await state.get_state()
    check("Отмена в другой дате: state сброшен", s is None, s)

    # ---- РАСПИСАНИЕ: Отмена прямо из периода ----
    msg = MockMessage("Проверить расписание")
    await main.check_schedule(msg, state)
    msg = MockMessage("Отмена")
    await main.handle_schedule_choice(msg, state)
    s = await state.get_state()
    check("Отмена в периоде: state сброшен", s is None, s)

    await storage.close()
    print(f"\nRESULT: {passed}/{total}")
    return passed == total

ok = asyncio.run(run())
if not ok:
    raise SystemExit(1)