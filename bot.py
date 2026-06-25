import os
import json
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ═══ НАСТРОЙКИ ═══
BOT_TOKEN = "8149969315:AAHTSrPCbzhRhz0CFxvKnWIYemjvbgs2hZw"
GROQ_KEY = "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"
ADMIN_TG = "@SU_57_T_90M"

# Лимиты по тарифам
LIMITS = {"free": 3, "pro": 999999, "biz": 999999}
PRICES = {"pro": "990 ₽/мес", "biz": "2990 ₽/мес"}

# Хранилище пользователей (в памяти, для продакшена нужна БД)
users = {}

logging.basicConfig(level=logging.INFO)

# ═══ AI ФУНКЦИЯ ═══
def ask_ai(prompt):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
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
    raise Exception(data.get("error", {}).get("message", "Ошибка AI"))

# ═══ ПОЛУЧИТЬ ПОЛЬЗОВАТЕЛЯ ═══
def get_user(user_id):
    if user_id not in users:
        users[user_id] = {"plan": "free", "today_count": 0, "today_date": "", "history": []}
    return users[user_id]

def check_limit(user_id):
    from datetime import date
    u = get_user(user_id)
    today = str(date.today())
    if u["today_date"] != today:
        u["today_count"] = 0
        u["today_date"] = today
    limit = LIMITS.get(u["plan"], 3)
    return u["today_count"] < limit

def use_limit(user_id):
    u = get_user(user_id)
    u["today_count"] += 1

# ═══ КОМАНДА /start ═══
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name or "Продавец"
    get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔍 Аудит карточки", callback_data="audit")],
        [InlineKeyboardButton("⭐ Анализ отзывов", callback_data="reviews")],
        [InlineKeyboardButton("📝 Описание товара", callback_data="description")],
        [InlineKeyboardButton("🔑 SEO ключевые слова", callback_data="keywords")],
        [InlineKeyboardButton("🎯 Оффер и УТП", callback_data="offer")],
        [InlineKeyboardButton("💰 Расчёт прибыли", callback_data="finance")],
        [InlineKeyboardButton("⭐ Тарифы", callback_data="plans")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет, {name}!\n\n"
        f"🚀 *Продажник.AI* — умный помощник для продавцов на WB и Ozon.\n\n"
        f"Выбери что хочешь сделать:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# ═══ КОМАНДА /menu ═══
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Аудит карточки", callback_data="audit")],
        [InlineKeyboardButton("⭐ Анализ отзывов", callback_data="reviews")],
        [InlineKeyboardButton("📝 Описание товара", callback_data="description")],
        [InlineKeyboardButton("🔑 SEO ключевые слова", callback_data="keywords")],
        [InlineKeyboardButton("🎯 Оффер и УТП", callback_data="offer")],
        [InlineKeyboardButton("💰 Расчёт прибыли", callback_data="finance")],
        [InlineKeyboardButton("⭐ Тарифы", callback_data="plans")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери инструмент:", reply_markup=reply_markup)

# ═══ КНОПКИ ═══
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u = get_user(user_id)
    
    if query.data == "audit":
        context.user_data["mode"] = "audit"
        await query.message.reply_text(
            "🔍 *Аудит карточки товара*\n\n"
            "Отправь ссылку на товар с WB или Ozon.\n"
            "Например: `https://www.wildberries.ru/catalog/123456/detail.aspx`\n\n"
            f"Осталось анализов сегодня: *{max(0, LIMITS[u['plan']] - u['today_count'])}*",
            parse_mode="Markdown"
        )
    
    elif query.data == "reviews":
        context.user_data["mode"] = "reviews"
        await query.message.reply_text(
            "⭐ *Анализ отзывов*\n\n"
            "Скопируй отзывы покупателей и отправь их мне.\n"
            "Я найду главные жалобы, преимущества и дам советы как поднять рейтинг.",
            parse_mode="Markdown"
        )
    
    elif query.data == "description":
        context.user_data["mode"] = "description"
        await query.message.reply_text(
            "📝 *Описание товара*\n\n"
            "Напиши название товара и его характеристики.\n"
            "Например: *Беспроводные наушники TWS, Bluetooth 5.3, 30 часов работы, защита IPX5*",
            parse_mode="Markdown"
        )
    
    elif query.data == "keywords":
        context.user_data["mode"] = "keywords"
        await query.message.reply_text(
            "🔑 *SEO ключевые слова*\n\n"
            "Напиши название своего товара и я подберу ключевые слова для топа в поиске WB и Ozon.",
            parse_mode="Markdown"
        )
    
    elif query.data == "offer":
        context.user_data["mode"] = "offer"
        await query.message.reply_text(
            "🎯 *Оффер и УТП*\n\n"
            "Напиши:\n"
            "1. Что продаёшь\n"
            "2. Главное преимущество\n"
            "3. Целевая аудитория\n\n"
            "Например: *Продаю силиконовые формы для выпечки, они не ломаются и моются в посудомойке, для домохозяек*",
            parse_mode="Markdown"
        )
    
    elif query.data == "finance":
        context.user_data["mode"] = "finance"
        await query.message.reply_text(
            "💰 *Расчёт прибыли*\n\n"
            "Напиши данные через запятую:\n"
            "*Цена продажи, Себестоимость, Продаж в месяц, Комиссия %, Логистика руб*\n\n"
            "Например: *2490, 890, 150, 15, 80*",
            parse_mode="Markdown"
        )
    
    elif query.data == "plans":
        keyboard = [
            [InlineKeyboardButton("💬 Подключить Про — 990 ₽/мес", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
            [InlineKeyboardButton("💎 Подключить Бизнес — 2990 ₽/мес", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "⭐ *Тарифы Продажник.AI*\n\n"
            "🆓 *Старт* — бесплатно\n"
            "• 3 аудита в день\n"
            "• Описания, SEO, офферы\n\n"
            "⭐ *Про* — 990 ₽/мес\n"
            "• Безлимитные аудиты\n"
            "• Расчёт прибыли и налогов\n"
            "• Анализ конкурентов\n"
            "• Прогноз продаж\n\n"
            "💎 *Бизнес* — 2990 ₽/мес\n"
            "• Всё из Про\n"
            "• AI-наставник\n"
            "• Поиск прибыльных товаров\n"
            "• Ручной анализ от команды\n\n"
            "Для подключения напиши администратору:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# ═══ ОБРАБОТКА СООБЩЕНИЙ ═══
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    mode = context.user_data.get("mode", "")
    
    if not mode:
        await update.message.reply_text(
            "Выбери инструмент через /menu",
        )
        return
    
    # Проверка лимита
    if not check_limit(user_id):
        keyboard = [[InlineKeyboardButton("⭐ Подключить Про", callback_data="plans")]]
        await update.message.reply_text(
            "❌ *Лимит исчерпан*\n\n"
            "На бесплатном тарифе — 3 аудита в день.\n"
            "Подключи Про для безлимитных запросов!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Отправляем "печатает..."
    await update.message.chat.send_action("typing")
    
    loading_msg = await update.message.reply_text("⏳ Анализирую, подожди 10-15 секунд...")
    
    try:
        if mode == "audit":
            if not text.startswith("http"):
                await loading_msg.edit_text("❌ Отправь ссылку начинающуюся с https://")
                return
            platform = "Ozon" if "ozon" in text else "Wildberries"
            prompt = f"""Проведи детальный аудит карточки товара на {platform}.
Ссылка: {text}

Дай анализ по 6 параметрам с оценкой от 0 до 100:
1. 📋 ЗАГОЛОВОК — оценка и что улучшить
2. 📝 ОПИСАНИЕ — оценка и что улучшить  
3. 📸 ФОТО — оценка и рекомендации
4. 🔍 SEO — оценка и ключевые слова
5. 💰 ЦЕНА — оценка и позиционирование
6. ⭐ ОТЗЫВЫ — оценка и работа с репутацией

Итоговая оценка: X/100

🎯 ПЛАН ДЕЙСТВИЙ (топ-5 что сделать в первую очередь):"""
        
        elif mode == "reviews":
            prompt = f"""Проанализируй отзывы покупателей:

{text}

Дай:
1. 😤 ГЛАВНЫЕ ЖАЛОБЫ (топ-5)
2. 👍 ЧТО ХВАЛЯТ (топ-5)
3. 💡 СКРЫТЫЕ ИНСАЙТЫ
4. 📈 КАК ПОДНЯТЬ РЕЙТИНГ (5 конкретных шагов)
5. 💬 ШАБЛОН ОТВЕТА НА НЕГАТИВНЫЙ ОТЗЫВ"""
        
        elif mode == "description":
            prompt = f"""Напиши продающее SEO-описание для карточки на Wildberries/Ozon.
Товар: {text}

Структура:
1. ЗАГОЛОВОК с ключевым словом
2. ГЛАВНЫЕ ВЫГОДЫ (5 пунктов с эмодзи)
3. ОПИСАНИЕ (150-200 слов)
4. ХАРАКТЕРИСТИКИ
5. ПРИЗЫВ К ДЕЙСТВИЮ"""
        
        elif mode == "keywords":
            prompt = f"""Подбери ключевые слова для топа на Wildberries и Ozon.
Товар: {text}

Дай:
1. ОПТИМИЗИРОВАННЫЙ ЗАГОЛОВОК (до 100 символов)
2. ВЫСОКОЧАСТОТНЫЕ запросы (15 штук)
3. СРЕДНЕЧАСТОТНЫЕ запросы (15 штук)
4. НИЗКОЧАСТОТНЫЕ запросы (10 штук)
5. СОВЕТЫ по оптимизации карточки"""
        
        elif mode == "offer":
            prompt = f"""Создай продающий оффер и УТП.
Информация: {text}

Дай:
1. УТП — одна строка почему купят именно у тебя
2. ГЛАВНЫЙ ЗАГОЛОВОК + ПОДЗАГОЛОВОК
3. ВЫГОДЫ (5 пунктов)
4. ОФФЕР для карточки WB/Ozon
5. ОФФЕР для Telegram"""
        
        elif mode == "finance":
            parts = text.split(",")
            if len(parts) < 3:
                await loading_msg.edit_text("❌ Напиши данные через запятую:\nЦена, Себестоимость, Продаж, Комиссия%, Логистика\n\nПример: 2490, 890, 150, 15, 80")
                return
            price = float(parts[0].strip())
            cost = float(parts[1].strip())
            qty = float(parts[2].strip())
            comm = float(parts[3].strip()) if len(parts) > 3 else 15
            log = float(parts[4].strip()) if len(parts) > 4 else 80
            
            rev = price * qty
            comm_a = rev * comm / 100
            exp = comm_a + log * qty + cost * qty
            profit = rev - exp
            margin = (profit / rev * 100) if rev > 0 else 0
            
            prompt = f"""Проанализируй финансовые показатели продавца на маркетплейсе:
Цена: {price}₽, Себестоимость: {cost}₽, Продаж: {qty}шт/мес
Комиссия: {comm}%, Логистика: {log}₽/шт
Выручка: {rev:,.0f}₽, Расходы: {exp:,.0f}₽, Прибыль: {profit:,.0f}₽, Маржа: {margin:.1f}%

Дай:
1. ОЦЕНКУ показателей (хорошо/плохо для маркетплейсов)
2. ГЛАВНЫЕ ПРОБЛЕМЫ
3. ТОП-5 способов увеличить прибыль конкретно
4. ПРОГНОЗ при оптимизации"""
        
        result = ask_ai(prompt)
        use_limit(user_id)
        
        # Убираем лишние символы markdown которые Telegram не понимает
        result = result.replace("**", "*")
        
        await loading_msg.edit_text(
            f"✅ *Готово!*\n\n{result}\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"📋 /menu — другие инструменты",
            parse_mode="Markdown"
        )
        
        # Сбрасываем режим
        context.user_data["mode"] = ""
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ Ошибка: {str(e)}\n\nПопробуй снова /menu")

# ═══ ЗАПУСК ═══
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
