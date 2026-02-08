import asyncio
import json
import os
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================== НАСТРОЙКИ ==================

BOT_TOKEN = "8210500922:AAFFqBlU-6pMnWBdGWYH940i1ay6BpJs2Pg"
ADMIN_ID = 7564214415

CARD_NUMBER = "2204 3203 9312 7750"
CARD_HOLDER = "LEONID L."

STAR_PACKS = {
    100: 160,
    150: 240,
    200: 310,
    250: 380,
    300: 460
}

USERS_FILE = "users.json"
PAYMENTS_FILE = "payments.json"
PURCHASES_FILE = "purchases.json"
TICKETS_FILE = "tickets.json"

# ================== BOT ==================

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== STORAGE ==================

def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

USERS = load(USERS_FILE, {})
PAYMENTS = load(PAYMENTS_FILE, {})
PURCHASES = load(PURCHASES_FILE, {})
TICKETS = load(TICKETS_FILE, {})

def get_user(uid: int):
    uid = str(uid)
    if uid not in USERS:
        USERS[uid] = {"balance": 0}
        save(USERS_FILE, USERS)
    return USERS[uid]

# ================== FSM ==================

class BuyFSM(StatesGroup):
    username = State()

class PayFSM(StatesGroup):
    amount = State()
    proof = State()

class TicketFSM(StatesGroup):
    text = State()

class AdminTicketFSM(StatesGroup):
    answer = State()

class AdminPromoFSM(StatesGroup):
    code = State()
    amount = State()
    limit = State()

class PromoFSM(StatesGroup):
    code = State()
    amount = State()
    limit = State()

# ================== KEYBOARDS ==================

def main_kb(uid: int):
    kb = [
        [InlineKeyboardButton(text="⭐ Купить", callback_data="menu:buy")],
        [InlineKeyboardButton(text="💳 Пополнить", callback_data="menu:pay")],
        [InlineKeyboardButton(text="🎫 Поддержка", callback_data="menu:ticket")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="menu:profile")],
        [InlineKeyboardButton(text="🎁 Промокод", callback_data="menu:promo")],
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="👑 Админ", callback_data="menu:admin")])
        [InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin:promos")],
    return InlineKeyboardMarkup(inline_keyboard=kb)

def buy_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{s} ⭐ — {p} ₽", callback_data=f"buy:{s}")]
            for s, p in STAR_PACKS.items()
        ]
    )

def admin_confirm_kb(prefix, pid):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅", callback_data=f"{prefix}:ok:{pid}"),
        InlineKeyboardButton(text="❌", callback_data=f"{prefix}:no:{pid}")
    ]])

def admin_ticket_kb(tid: str, status: str):
    buttons = []

    if status != "closed":
        buttons.append(
            InlineKeyboardButton(
                text="✉️ Ответить",
                callback_data=f"ticket:reply:{tid}"
            )
        )

        buttons.append(
            InlineKeyboardButton(
                text="🔒 Закрыть",
                callback_data=f"ticket:close:{tid}"
            )
        )

    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])

def admin_promos_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin:promo:add")],
        [InlineKeyboardButton(text="📋 Список", callback_data="admin:promos")],
    ])

def promo_manage_kb(code, enabled):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔴 Выкл" if enabled else "🟢 Вкл",
                callback_data=f"promo:toggle:{code}"
            ),
            InlineKeyboardButton(
                text="❌ Удалить",
                callback_data=f"promo:delete:{code}"
            )
        ]
    ])


# ================== START ==================

@dp.message(Command("start"))
async def start(m: Message):
    get_user(m.from_user.id)
    await m.answer("👋 Добро пожаловать", reply_markup=main_kb(m.from_user.id))

# ================== PROFILE ==================

@dp.callback_query(F.data == "menu:profile")
async def profile(c: CallbackQuery):
    u = get_user(c.from_user.id)
    purchases = [p for p in PURCHASES.values() if p["user"] == c.from_user.id]

    await c.message.answer(
        f"👤 Профиль\n\n"
        f"🆔 ID: {c.from_user.id}\n"
        f"💰 Баланс: {u['balance']} ₽\n"
        f"🛒 Покупок: {len(purchases)}"
    )
    await c.answer()

# ================== BUY ==================

@dp.callback_query(F.data == "menu:buy")
async def buy_menu(c: CallbackQuery):
    await c.message.answer("Выберите пакет:", reply_markup=buy_kb())
    await c.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def buy_pack(c: CallbackQuery, state: FSMContext):
    stars = int(c.data.split(":")[1])
    price = STAR_PACKS[stars]
    u = get_user(c.from_user.id)

    if u["balance"] < price:
        await c.message.answer("❌ Недостаточно средств")
        await c.answer()
        return

    u["balance"] -= price
    save(USERS_FILE, USERS)

    await state.set_state(BuyFSM.username)
    await state.update_data(stars=stars, price=price)
    await c.message.answer("✍️ Напишите @username")
    await c.answer()

@dp.message(BuyFSM.username)
async def buy_username(m: Message, state: FSMContext):
    data = await state.get_data()
    pid = str(int(time.time()))

    PURCHASES[pid] = {
        "user": m.from_user.id,
        "username": m.text,
        "stars": data["stars"],
        "price": data["price"]
    }
    save(PURCHASES_FILE, PURCHASES)

    await bot.send_message(
        ADMIN_ID,
        f"⭐ ПОКУПКА #{pid}\n"
        f"👤 {m.from_user.id}\n"
        f"🔗 {m.text}\n"
        f"⭐ {data['stars']}\n"
        f"💰 {data['price']} ₽",
        reply_markup=admin_confirm_kb("buy", pid)
    )

    await m.answer("⏳ Заявка отправлена")
    await state.clear()

# ================== PAY ==================

@dp.callback_query(F.data == "menu:pay")
async def pay_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(PayFSM.amount)
    await c.message.answer("Введите сумму:")
    await c.answer()

@dp.message(PayFSM.amount)
async def pay_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("Введите число")
        return

    amount = int(m.text)
    await state.update_data(amount=amount)
    await state.set_state(PayFSM.proof)

    await m.answer(
        f"💳 Переведите {amount} ₽\n\n{CARD_NUMBER}\n{CARD_HOLDER}\n\nОтправьте чек"
    )

@dp.message(PayFSM.proof)
async def pay_proof(m: Message, state: FSMContext):
    data = await state.get_data()
    pid = str(int(time.time()))

    PAYMENTS[pid] = {"user": m.from_user.id, "amount": data["amount"]}
    save(PAYMENTS_FILE, PAYMENTS)

    await bot.send_message(
        ADMIN_ID,
        f"💳 ПОПОЛНЕНИЕ #{pid}\n👤 {m.from_user.id}\n💰 {data['amount']} ₽",
        reply_markup=admin_confirm_kb("pay", pid)
    )

    await m.answer("⏳ На проверке")
    await state.clear()

# ================== TICKETS ==================

@dp.callback_query(F.data == "menu:ticket")
async def ticket_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(TicketFSM.text)
    await c.message.answer("✍️ Опишите проблему")
    await c.answer()

@dp.message(TicketFSM.text)
async def ticket_text(m: Message, state: FSMContext):
    tid = str(int(time.time()))
    TICKETS[tid] = {"user": m.from_user.id, "text": m.text}
    save(TICKETS_FILE, TICKETS)

    await bot.send_message(
        ADMIN_ID,
        f"🎫 ТИКЕТ #{tid}\n👤 {m.from_user.id}\n\n{m.text}"
    )

    await m.answer("✅ Тикет отправлен")
    await state.clear()

# ================== PROMO (USER) ==================

@dp.callback_query(F.data == "menu:promo")
async def promo_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(PromoFSM.code)
    await c.message.answer("🎁 Введите промокод:")
    await c.answer()

@dp.message(PromoFSM.code)
async def promo_use(m: Message, state: FSMContext):
    global PROMOS
    PROMOS_FILE = "promos.json"
    PROMOS = load(PROMOS_FILE, {})

    code = m.text.strip().upper()
    promo = PROMOS.get(code)

    if not promo:
        await m.answer("❌ Промокод не найден")
        await state.clear()
        return


    uid = str(m.from_user.id)

    if uid in promo["used"]:
        await m.answer("⚠️ Вы уже использовали этот промокод")
        await state.clear()
        return

    if len(promo["used"]) >= promo["limit"]:
        await m.answer("❌ Лимит активаций исчерпан")
        await state.clear()
        return

    user = get_user(m.from_user.id)
    user["balance"] += promo["amount"]

    promo["used"].append(uid)

    save(USERS_FILE, USERS)
    save(PROMOS_FILE, PROMOS)

    await m.answer(f"✅ Промокод активирован! +{promo['amount']} ₽")
    await state.clear()

# ================== ADMIN ==================

def admin_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="👤 Пользователи", callback_data="admin:users")],
            [InlineKeyboardButton(text="🎫 Тикеты", callback_data="admin:tickets")],
            [InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin:promo:menu")]
        ]
    )

@dp.callback_query(F.data == "menu:admin")
async def admin_menu(c: CallbackQuery):
    await c.message.answer(
        "👑 Админ панель",
        reply_markup=admin_menu_kb()
    )
    await c.answer()

@dp.callback_query(F.data == "admin:promo:menu")
async def admin_promo_menu(c: CallbackQuery):
    await c.message.answer("🎁 Управление промокодами", reply_markup=admin_promos_kb())
    await c.answer()

@dp.callback_query(F.data == "admin:promo:add")
async def promo_add_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(PromoFSM.code)
    await c.message.answer("✍️ Введите код промокода:")
    await c.answer()

@dp.message(PromoFSM.code)
async def promo_add_code(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    PROMOS_FILE = "promos.json"
    PROMOS = load(PROMOS_FILE, {})


    if code in PROMOS:
        await m.answer("❌ Такой промокод уже существует")
        return

    await state.update_data(code=code)
    await state.set_state(PromoFSM.amount)
    await m.answer("💰 Введите сумму бонуса:")

@dp.message(PromoFSM.amount)
async def promo_add_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("Введите число")
        return

    await state.update_data(amount=int(m.text))
    await state.set_state(PromoFSM.limit)
    await m.answer("📊 Введите лимит активаций (0 = ∞):")


@dp.message(PromoFSM.limit)

async def promo_add_finish(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("Введите число")
        return

    data = await state.get_data()
    PROMOS_FILE = "promos.json"
    PROMOS = load(PROMOS_FILE, {})


    PROMOS[data["code"]] = {
        "amount": data["amount"],
        "limit": int(m.text),
        "used": [],
        "enabled": True
    }

    save(PROMOS_FILE, PROMOS)

    await m.answer(f"✅ Промокод <b>{data['code']}</b> создан", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("promo:toggle:"))
async def promo_toggle(c: CallbackQuery):
    code = c.data.split(":")[2]
    PROMOS_FILE = "promos.json"
    PROMOS = load(PROMOS_FILE, {})


    PROMOS[code]["enabled"] = not PROMOS[code]["enabled"]
    save(PROMOS_FILE, PROMOS)

    await c.message.edit_text("🔁 Статус изменён")
    await c.answer()

@dp.callback_query(F.data.startswith("promo:delete:"))
async def promo_delete(c: CallbackQuery):
    code = c.data.split(":")[2]
    PROMOS_FILE = "promos.json"
    PROMOS = load(PROMOS_FILE, {})


    PROMOS.pop(code, None)
    save(PROMOS_FILE, PROMOS)

    await c.message.edit_text("❌ Промокод удалён")
    await c.answer()


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(c: CallbackQuery):
    await c.message.answer(
        f"📊 Статистика\n\n"
        f"👥 Пользователей: {len(USERS)}\n"
        f"💳 Платежей: {len(PAYMENTS)}\n"
        f"⭐ Покупок: {len(PURCHASES)}\n"
        f"🎫 Тикетов: {len(TICKETS)}"
    )
    await c.answer()

@dp.callback_query(F.data == "admin:users")
async def admin_users(c: CallbackQuery):
    text = "👥 Пользователи:\n\n"
    for uid, u in list(USERS.items())[-10:]:
        text += f"🆔 {uid} — {u['balance']} ₽\n"
    await c.message.answer(text)
    await c.answer()

@dp.callback_query(F.data == "admin:tickets")
async def admin_tickets(c: CallbackQuery):
    if not TICKETS:
        await c.message.answer("🎫 Тикетов нет")
        await c.answer()
        return

    for tid, t in TICKETS.items():
        user = t.get("user", "unknown")
        msg = t.get("text", "❗ Старый тикет")
        ans = t.get("answer")
        status = t.get("status", "open")

        status_text = {
            "open": "⏳ Открыт",
            "answered": "✅ Отвечен",
            "closed": "🔒 Закрыт"
        }.get(status, status)

        text = (
            f"🎫 Тикет #{tid}\n"
            f"👤 {user}\n"
            f"💬 {msg}\n"
            f"📌 Статус: {status_text}"
        )

        await c.message.answer(
            text,
            reply_markup=admin_ticket_kb(tid, status)
        )

    await c.answer()

@dp.callback_query(F.data == "admin:promos")
async def admin_promos(c: CallbackQuery):
    if not PROMOS:
        await c.message.answer("🎁 Промокодов нет")
        await c.answer()
        return
    PROMOS_FILE = "promos.json"
    PROMOS = load(PROMOS_FILE, {})

    for code, p in PROMOS.items():
        await c.message.answer(
            f"{'🟢' if p['enabled'] else '🔴'} <b>{code}</b>\n"
            f"💰 {p['amount']} ₽\n"
            f"📊 {len(p['used'])}/{p['limit'] if p['limit'] else '∞'}",
            reply_markup=promo_manage_kb(code, p["enabled"]),
            parse_mode="HTML"
        )

    await c.answer()


@dp.callback_query(F.data.startswith("ticket:reply:"))
async def admin_ticket_reply(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return

    tid = c.data.split(":")[2]

    ticket = TICKETS.get(tid)
    if not ticket:
        await c.answer("Тикет не найден", show_alert=True)
        return

    if ticket.get("status") == "closed":
        await c.answer("🔒 Тикет закрыт", show_alert=True)
        return

    await state.set_state(AdminTicketFSM.answer)
    await state.update_data(tid=tid)

    await c.message.answer("✍️ Введите ответ пользователю:")
    await c.answer()

@dp.message(AdminTicketFSM.answer)
async def admin_ticket_answer(m: Message, state: FSMContext):
    data = await state.get_data()
    tid = data["tid"]
    ticket["status"] = "answered"


    ticket = TICKETS.get(tid)
    if not ticket:
        await m.answer("Тикет не найден")
        await state.clear()
        return

    ticket["answer"] = m.text
    save(TICKETS_FILE, TICKETS)

    await bot.send_message(
        ticket["user"],
        f"📩 Ответ от поддержки:\n\n{m.text}"
    )

    await m.answer("✅ Ответ отправлен пользователю")
    await state.clear()

@dp.callback_query(F.data.startswith("ticket:close:"))
async def admin_ticket_close(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return

    tid = c.data.split(":")[2]
    ticket = TICKETS.get(tid)

    if not ticket:
        await c.answer("Тикет не найден", show_alert=True)
        return

    if ticket.get("status") == "closed":
        await c.answer("Тикет уже закрыт", show_alert=True)
        return

    ticket["status"] = "closed"
    save(TICKETS_FILE, TICKETS)

    await bot.send_message(
        ticket["user"],
        "🔒 Ваш тикет был закрыт администратором.\n"
        "Если вопрос остался — создайте новый тикет."
    )

    await c.message.edit_text(
        c.message.text + "\n\n🔒 Тикет закрыт"
    )

    await c.answer("Закрыто")


# ================== RUN ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
