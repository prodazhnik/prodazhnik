import logging
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
 
BOT_TOKEN = "8149969315:AAHTSrPCbzhRhz0CFxvKnWIYemjvbgs2hZw"
GROQ_KEY = "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"
ADMIN_TG = "SU_57_T_90M"
PORT = int(os.environ.get("PORT", 8080))
 
LIMITS = {"free": 3, "pro": 999999, "biz": 999999}
users = {}
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
# Простой HTTP сервер для Render
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Prodazhnik.AI Bot is running!")
    def log_message(self, format, *args):
        pass
 
def run_http():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
 
def ask_ai(prompt):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": "Ты эксперт по маркетплейсам Wildberries и Ozon. Отвечай на русском языке. Давай конкретные практичные советы."},
                {"role": "user", "content": prompt}
            ]
        },
        timeout=30
    )
    data = r.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    raise Exception(str(data))
 
def get_user(uid):
    if uid not in users:
        users[uid] = {"plan": "free", "today_count": 0, "today_date": ""}
    return users[uid]
 
def check_limit(uid):
    from datetime import date
    u = get_user(uid)
    today = str(date.today())
    if u["today_date"] != today:
        u["today_count"] = 0
        u["today_date"] = today
    return u["today_count"] < LIMITS.get(u["plan"], 3)
 
def use_limit(uid):
    get_user(uid)["today_count"] += 1
 
def start(update, context):
    name = update.effective_user.first_name or "Продавец"
    kb = [
        [InlineKeyboardButton("🔍 Аудит карточки", callback_data="audit")],
        [InlineKeyboardButton("⭐ Анализ отзывов", callback_data="reviews")],
        [InlineKeyboardButton("📝 Описание товара", callback_data="description")],
        [InlineKeyboardButton("🔑 SEO ключевые слова", callback_data="keywords")],
        [InlineKeyboardButton("🎯 Оффер и УТП", callback_data="offer")],
        [InlineKeyboardButton("💰 Расчёт прибыли", callback_data="finance")],
        [InlineKeyboardButton("⭐ Тарифы", callback_data="plans")],
    ]
    update.message.reply_text(
        f"👋 Привет, {name}!\n\n🚀 *Продажник.AI* — умный помощник для продавцов на WB и Ozon.\n\nВыбери что хочешь сделать:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
 
def menu(update, context):
    kb = [
        [InlineKeyboardButton("🔍 Аудит карточки", callback_data="audit")],
        [InlineKeyboardButton("⭐ Анализ отзывов", callback_data="reviews")],
        [InlineKeyboardButton("📝 Описание товара", callback_data="description")],
        [InlineKeyboardButton("🔑 SEO ключевые слова", callback_data="keywords")],
        [InlineKeyboardButton("🎯 Оффер и УТП", callback_data="offer")],
        [InlineKeyboardButton("💰 Расчёт прибыли", callback_data="finance")],
        [InlineKeyboardButton("⭐ Тарифы", callback_data="plans")],
    ]
    update.message.reply_text("Выбери инструмент:", reply_markup=InlineKeyboardMarkup(kb))
 
def button(update, context):
    query = update.callback_query
    query.answer()
    uid = query.from_user.id
    d = query.data
 
    if d == "audit":
        context.user_data["mode"] = "audit"
        query.message.reply_text("🔍 *Аудит карточки*\n\nОтправь ссылку на товар с WB или Ozon.", parse_mode="Markdown")
    elif d == "reviews":
        context.user_data["mode"] = "reviews"
        query.message.reply_text("⭐ *Анализ отзывов*\n\nСкопируй и отправь отзывы покупателей.", parse_mode="Markdown")
    elif d == "description":
        context.user_data["mode"] = "description"
        query.message.reply_text("📝 *Описание товара*\n\nНапиши название товара и характеристики.", parse_mode="Markdown")
    elif d == "keywords":
        context.user_data["mode"] = "keywords"
        query.message.reply_text("🔑 *SEO ключевые слова*\n\nНапиши название своего товара.", parse_mode="Markdown")
    elif d == "offer":
        context.user_data["mode"] = "offer"
        query.message.reply_text("🎯 *Оффер и УТП*\n\nНапиши что продаёшь, преимущество и целевую аудиторию.", parse_mode="Markdown")
    elif d == "finance":
        context.user_data["mode"] = "finance"
        query.message.reply_text("💰 *Расчёт прибыли*\n\nНапиши через запятую:\n*Цена, Себестоимость, Продаж/мес, Комиссия%, Логистика*\n\nПример: *2490, 890, 150, 15, 80*", parse_mode="Markdown")
    elif d == "plans":
        kb = [
            [InlineKeyboardButton("💬 Про — 990 ₽/мес", url=f"https://t.me/{ADMIN_TG}")],
            [InlineKeyboardButton("💎 Бизнес — 2990 ₽/мес", url=f"https://t.me/{ADMIN_TG}")],
        ]
        query.message.reply_text(
            "⭐ *Тарифы*\n\n🆓 *Старт* — бесплатно — 3 аудита/день\n⭐ *Про* — 990 ₽/мес — безлимит\n💎 *Бизнес* — 2990 ₽/мес — всё + AI-наставник",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
 
def handle_message(update, context):
    uid = update.effective_user.id
    text = update.message.text
    mode = context.user_data.get("mode", "")
 
    if not mode:
        update.message.reply_text("Выбери инструмент через /menu")
        return
 
    if not check_limit(uid):
        kb = [[InlineKeyboardButton("⭐ Подключить Про", callback_data="plans")]]
        update.message.reply_text("❌ *Лимит исчерпан*\n\n3 аудита в день на бесплатном тарифе.\nПодключи Про!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return
 
    msg = update.message.reply_text("⏳ Анализирую, подожди 15-20 секунд...")
 
    try:
        if mode == "audit":
            if not text.startswith("http"):
                msg.edit_text("❌ Отправь ссылку начинающуюся с https://")
                return
            platform = "Ozon" if "ozon" in text else "Wildberries"
            prompt = f"Аудит карточки на {platform}: {text}\n\nОцени по 6 параметрам (0-100):\n1. ЗАГОЛОВОК\n2. ОПИСАНИЕ\n3. ФОТО\n4. SEO\n5. ЦЕНА\n6. ОТЗЫВЫ\n\nИтог: X/100\n\nПЛАН ДЕЙСТВИЙ (топ-5):"
        elif mode == "reviews":
            prompt = f"Анализ отзывов:\n{text}\n\n1. ЖАЛОБЫ (топ-5)\n2. ХВАЛЯТ (топ-5)\n3. КАК ПОДНЯТЬ РЕЙТИНГ\n4. ШАБЛОН ОТВЕТА НА НЕГАТИВ"
        elif mode == "description":
            prompt = f"Продающее описание для WB/Ozon.\nТовар: {text}\n\n1. ЗАГОЛОВОК\n2. ВЫГОДЫ (5 пунктов)\n3. ОПИСАНИЕ (150 слов)\n4. ПРИЗЫВ К ДЕЙСТВИЮ"
        elif mode == "keywords":
            prompt = f"SEO для WB и Ozon.\nТовар: {text}\n\n1. ЗАГОЛОВОК (до 100 символов)\n2. ВЫСОКОЧАСТОТНЫЕ (15 запросов)\n3. СРЕДНЕЧАСТОТНЫЕ (15 запросов)\n4. СОВЕТЫ"
        elif mode == "offer":
            prompt = f"Оффер и УТП.\nИнфо: {text}\n\n1. УТП (одна строка)\n2. ЗАГОЛОВОК\n3. ВЫГОДЫ (5 пунктов)\n4. ОФФЕР для WB\n5. ОФФЕР для Telegram"
        elif mode == "finance":
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 3:
                msg.edit_text("❌ Формат: Цена, Себестоимость, Продаж, Комиссия%, Логистика\nПример: 2490, 890, 150, 15, 80")
                return
            price, cost, qty = float(parts[0]), float(parts[1]), float(parts[2])
            comm = float(parts[3]) if len(parts) > 3 else 15
            log = float(parts[4]) if len(parts) > 4 else 80
            rev = price * qty
            exp = (rev * comm / 100) + (log * qty) + (cost * qty)
            profit = rev - exp
            margin = (profit / rev * 100) if rev > 0 else 0
            prompt = f"Финансовый анализ:\nВыручка: {rev:,.0f}₽, Расходы: {exp:,.0f}₽, Прибыль: {profit:,.0f}₽, Маржа: {margin:.1f}%\n\n1. ОЦЕНКА\n2. ПРОБЛЕМЫ\n3. ТОП-5 способов увеличить прибыль"
        else:
            msg.edit_text("Выбери инструмент /menu")
            return
 
        result = ask_ai(prompt)
        use_limit(uid)
        context.user_data["mode"] = ""
        if len(result) > 3500:
            result = result[:3500] + "..."
        msg.edit_text(f"{result}\n\n─────────\n/menu — другие инструменты")
 
    except Exception as e:
        logger.error(f"Error: {e}")
        msg.edit_text("❌ Ошибка. Попробуй снова /menu")
 
def main():
    # Запускаем HTTP сервер в отдельном потоке
    t = threading.Thread(target=run_http, daemon=True)
    t.start()
    logger.info(f"HTTP server started on port {PORT}")
 
    # Запускаем бота
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("menu", menu))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    logger.info("Bot started!")
    updater.start_polling()
    updater.idle()
 
if __name__ == "__main__":
    main()
 
