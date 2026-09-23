import asyncio
import os

os.environ["TELEGRAM_TOKEN"] = "123456789:FAKETOKEN"
os.environ["YANDEX_TOKEN"] = "fake"

import util.dispatch as dispatch
dispatch.yadisk_client.check_token = lambda: False
dispatch.yadisk_client.get_public_files = lambda *a, **k: []

import main
import db_def
from handlers import admin, login, misc, profile, schedule

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
        self.sent = []
    async def delete_message(self, chat_id, message_id):
        self.deleted.append(message_id)
    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))

async def run():
    storage = MemoryStorage()
    key = StorageKey(bot_id=main.bot.id, chat_id=111, user_id=111)
    state = FSMContext(storage=storage, key=key)

    # ---- ЗАПИСЬ ТЕСТОВОГО СТУДЕНТА ----
    msg = MockMessage("/login")
    await login.login(msg, state)
    msg = MockMessage("Студент")
    await login.ask_for_value(msg, state)
    msg = MockMessage("ОП-2")
    await login.save_inform(msg, state)
    check("студент зарегистрирован", (await state.get_state()) is None)

    # ---- ПРОФИЛЬ: открытие меню ----
    msg = MockMessage("Профиль")
    await profile.profile(msg, state)
    s = await state.get_state()
    check("профиль открыл меню", s == profile.ProfileForm.menu, s)

    # ---- УДАЛИТЬ АККАУНТ -> подтверждение -> Да ----
    msg = MockMessage("Удалить аккаунт")
    fake = FakeBot()
    profile.bot = fake
    await profile.edit_profile_user(msg, state)
    s = await state.get_state()
    check("кнопка Удалить -> delete_user", s == profile.ProfileForm.delete_user, s)
    msg = MockMessage("Да")
    await profile.delete_conf_def(msg, state)
    s = await state.get_state()
    removed = db_def.get_user_data(111)[0] is None
    check("подтверждение Да: юзер удалён, state сброшен", s is None and removed, (s, removed))

    # ---- ПРОФИЛЬ: Авто рассылка тоггл ----
    msg = MockMessage("/login")
    await login.login(msg, state)
    msg = MockMessage("Студент")
    await login.ask_for_value(msg, state)
    msg = MockMessage("ОП-2")
    await login.save_inform(msg, state)
    msg = MockMessage("Профиль")
    await profile.profile(msg, state)
    before = db_def.get_user_data(111)[2]
    msg = MockMessage("Авто рассылка")
    await profile.edit_profile_user(msg, state)
    after = db_def.get_user_data(111)[2]
    check("Авто рассылка переключила уведомления", before != after, (before, after))
    s = await state.get_state()
    check("Авто рассылка вернула меню профиля", s == profile.ProfileForm.menu, s)

    # ---- ПРОФИЛЬ: Обратная связь ----
    msg = MockMessage("Обратная связь")
    await profile.edit_profile_user(msg, state)
    s = await state.get_state()
    check("Обратная связь -> state feedback", s == profile.ProfileForm.feedback, s)
    msg = MockMessage("Вернуться на главную")
    await profile.process_feedback(msg, state)
    s = await state.get_state()
    check("feedback: выход в главное меню, state сброшен", s is None, s)

    # ---- ПРОФИЛЬ: отправка отзыва без MAIN_ADMIN_ID ----
    msg = MockMessage("Профиль")
    await profile.profile(msg, state)
    msg = MockMessage("Обратная связь")
    await profile.edit_profile_user(msg, state)
    msg = MockMessage("Классный бот")
    await profile.process_feedback(msg, state)
    not_set = any("не установлен" in a for a in msg.answers)
    s = await state.get_state()
    check("feedback без MAIN_ADMIN_ID: не крашится и сбрасывает state", not_set and s is None, (not_set, s))
    msg = MockMessage("Вернуться на главную")
    await profile.process_feedback(msg, state)

    # ---- ПРОФИЛЬ: Изменить данные -> логин заново ----
    msg = MockMessage("Профиль")
    await profile.profile(msg, state)
    msg = MockMessage("Изменить данные")
    await profile.edit_profile_user(msg, state)
    s = await state.get_state()
    check("Изменить данные -> перешли в выбор роли", s == login.LoginForm.choosing_role, s)

    # ---- РАСПИСАНИЕ: выбор периода -> другая дата -> отмена ----
    msg = MockMessage("Проверить расписание")
    await schedule.check_schedule(msg, state)
    s = await state.get_state()
    check("Проверить расписание -> choosing_period", s == schedule.ScheduleForm.choosing_period, s)
    text = MockMessage("Другая дата")
    await schedule.handle_schedule_choice(text, state)
    s = await state.get_state()
    check("Другая дата -> choosing_other_date", s == schedule.ScheduleForm.choosing_other_date, s)
    msg = MockMessage("Отмена")
    await schedule.other_data_send(msg, state)
    s = await state.get_state()
    check("Отмена в другой дате: state сброшен", s is None, s)

    # ---- РАСПИСАНИЕ: Отмена прямо из периода ----
    msg = MockMessage("Проверить расписание")
    await schedule.check_schedule(msg, state)
    msg = MockMessage("Отмена")
    await schedule.handle_schedule_choice(msg, state)
    s = await state.get_state()
    check("Отмена в периоде: state сброшен", s is None, s)

    # ---- АДМИН: смоук has_role и роутера ----
    check("admin_router прикреплён к dp", admin.admin_router.parent_router is main.dp)
    admin.add_admin(222, "adminuser", 3, "system")
    try:
        msg_adm = MockMessage("/list_admins", uid=222)
        await admin.list_admins(msg_adm)
        allowed = any("Список администраторов" in a for a in msg_adm.answers)
        check("админ (role 3) проходит has_role", allowed, msg_adm.answers)

        msg_stranger = MockMessage("/list_admins", uid=111)
        await admin.list_admins(msg_stranger)
        denied = any("недостаточно прав" in a for a in msg_stranger.answers)
        check("не-админ отклоняется has_role", denied, msg_stranger.answers)
    finally:
        admin.remove_admin_def(222)

    # ---- АРХИТЕКТУРА: порядок роутеров и единственный catch-all ----
    subs = main.dp.sub_routers
    all_routers = [
        login.login_router,
        profile.profile_router,
        schedule.schedule_router,
        admin.admin_router,
        misc.generic_router,
    ]
    check("все роутеры подключены к dp", all(r in subs for r in all_routers), len(subs))
    check("generic_router — последний роутер (catch-all в конце)", subs[-1] is misc.generic_router, subs)

    last_h = misc.generic_router.message.handlers[-1]
    check("any_mess — последний хендлер generic и без фильтров",
          last_h.callback.__name__ == "any_mess" and not last_h.filters,
          last_h.callback.__name__)

    others = [login.login_router, profile.profile_router, schedule.schedule_router, admin.admin_router]
    bare = [(r, h.callback.__name__) for r in others for h in r.message.handlers if not h.filters]
    check("catch-all есть только у misc", bare == [], bare)

    # ---- MISC: поведение без состояния ----
    msg = MockMessage("/start", uid=333)
    await misc.cmd_start(msg)
    prompted = any("Вас нет в базе" in a for a in msg.answers)
    check("cmd_start: незарегистрированный → приглашение к /login", prompted, msg.answers)

    msg = MockMessage("Me")
    await misc.egg_me(msg)
    check("пасхалка Me", any("everything for everyone" in a for a in msg.answers), msg.answers)

    msg = MockMessage("проверка")
    await misc.any_mess(msg)
    check("any_mess: ловит неизвестное", any("/help" in a for a in msg.answers), msg.answers)

    # ---- РАСПИСАНИЕ: звонки и мусор в периоде ----
    msg = MockMessage("Расписание звонков")
    await schedule.schedule_zvon(msg)
    check("schedule_zvon отдаёт текст", any("Расписание звонков" in a for a in msg.answers), msg.answers)

    msg = MockMessage("Проверить расписание")
    await schedule.check_schedule(msg, state)
    msg = MockMessage("чепуха")
    await schedule.handle_schedule_choice(msg, state)
    wrn = any("экранные кнопки" in a for a in msg.answers)
    s = await state.get_state()
    check("handle_schedule_choice: мусор → warning, state не сброшен", wrn and s == schedule.ScheduleForm.choosing_period, (wrn, s))
    await state.clear()

    # ---- LOGIN: неверные данные не ломают FSM ----
    msg = MockMessage("/login")
    await login.login(msg, state)
    msg = MockMessage("мусор")
    await login.ask_for_value(msg, state)
    wrn = any("экранные кнопки" in a for a in msg.answers)
    s = await state.get_state()
    check("ask_for_value: мусор → warning, роль не выбрана", wrn and s == login.LoginForm.choosing_role, (wrn, s))
    msg = MockMessage("Студент")
    await login.ask_for_value(msg, state)
    msg = MockMessage("оп2")
    await login.save_inform(msg, state)
    wrn = any("Некорректный номер группы" in a for a in msg.answers)
    s = await state.get_state()
    check("save_inform: оп2 → ошибка, state в выборе value", wrn and s == login.LoginForm.choosing_value, (wrn, s))
    msg = MockMessage("ОП-2")
    await login.save_inform(msg, state)
    s = await state.get_state()
    check("save_inform: корректная группа → регистрация", s is None, s)

    # ---- АДМИН: broadcast и list_users (через FakeBot) ----
    admin.add_admin(222, "adminuser", 3, "system")
    orig_admin_bot = admin.bot
    admin.bot = fake
    try:
        msg = MockMessage("/broadcast всем привет", uid=222)
        await admin.broadcast_message(msg)
        sent = any("Сообщение отправлено" in a for a in msg.answers) and len(fake.sent) > 0
        check("broadcast: доставил сообщения", sent, (msg.answers, fake.sent))

        msg = MockMessage("/list_users", uid=222)
        await admin.list_users(msg)
        listed = any("Зарегистрированных пользователей" in a for a in msg.answers)
        check("list_users: отдаёт список", listed, msg.answers)
    finally:
        admin.bot = orig_admin_bot
        admin.remove_admin_def(222)

    # ---- ПРОФИЛЬ: ветки delete_conf_def ----
    msg = MockMessage("Профиль")
    await profile.profile(msg, state)
    msg = MockMessage("Удалить аккаунт")
    await profile.edit_profile_user(msg, state)
    msg = MockMessage("Нет")
    await profile.delete_conf_def(msg, state)
    kept = any("Спасибо, что вы остались" in a for a in msg.answers)
    s = await state.get_state()
    check("delete_conf_def: Нет → остался, state сброшен", kept and s is None, (kept, s))

    msg = MockMessage("Профиль")
    await profile.profile(msg, state)
    msg = MockMessage("Удалить аккаунт")
    await profile.edit_profile_user(msg, state)
    msg = MockMessage("возможно")
    await profile.delete_conf_def(msg, state)
    wrn = any("'Да' или 'Нет'" in a for a in msg.answers)
    s = await state.get_state()
    check("delete_conf_def: мусор → warning, state не сброшен", wrn and s == profile.ProfileForm.delete_user, (wrn, s))
    msg = MockMessage("Да")
    await profile.delete_conf_def(msg, state)
    s = await state.get_state()
    check("delete_conf_def: Да после мусора → сброс", s is None, s)

    # ---- ПРОФИЛЬ: отзыв при заданном MAIN_ADMIN_ID ----
    profile.bot = fake
    os.environ["MAIN_ADMIN_ID"] = "999"
    try:
        msg = MockMessage("Обратная связь")
        await profile.edit_profile_user(msg, state)
        msg = MockMessage("Проверка связи")
        await profile.process_feedback(msg, state)
        thanks = any("Спасибо за обратную связь" in a for a in msg.answers)
        sent = any(cid == 999 for cid, _ in fake.sent)
        s = await state.get_state()
        check("feedback при MAIN_ADMIN_ID: отправка админу, спасибо, сброс",
              thanks and sent and s is None, (thanks, sent, s))
    finally:
        os.environ.pop("MAIN_ADMIN_ID", None)

    await storage.close()
    print(f"\nRESULT: {passed}/{total}")
    return passed == total

ok = asyncio.run(run())
if not ok:
    raise SystemExit(1)
