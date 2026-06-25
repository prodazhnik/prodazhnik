import logging
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup, 
                       LabeledPrice, ShippingAddress)
from telegram.ext import (Application, CommandHandler, MessageHandler, 
                           CallbackQueryHandler, filters, ContextTypes,
                           PreCheckoutQueryHandler)

BOT_TOKEN = "8149969315:AAHTSrPCbzhRhz0CFxvKnWIYemjvbgs2hZw"
GROQ_KEY = "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"
ADMIN_TG = "SU_57_T_90M"
ADMIN_ID = None  # Заполнится автоматически
PORT = int(os.environ.get("PORT", 8080))

# Тарифы
PLANS = {
    "free": {"name": "🆓 Старт", "price": 0, "audits": 3, "desc": "3 аудита в день"},
    "pro": {"name": "⭐ Про", "price": 990, "audits": 999999, "desc": "Безлимит + все инструменты"},
    "biz": {"name": "💎 Бизнес", "price": 2990, "audits": 999999, "desc": "Всё + AI-наставник + приоритет"},
}

# База пользователей (в памяти)
users = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── HTTP сервер для Render ───
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Prodazhnik.AI Bot is running!")
    def log_message(self, *args): pass

def run_http():
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

# ─── AI ───
def ask_ai(prompt, image_base64=None):
    messages = [
        {"role": "system", "content": "Ты эксперт-консультант по маркетплейсам Wildberries и Ozon с 10 годами опыта. Давай развёрнутые, конкретные, практичные советы. Никогда не пиши общими фразами — только конкретика для данного товара/ситуации."},
        {"role": "user", "content": prompt}
    ]
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "max_tokens": 2000, "messages": messages},
        timeout=45
    )
    data = r.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    raise Exception(str(data))

# ─── Пользователи ───
def get_user(uid):
    if uid not in users:
        users[uid] = {
            "plan": "free", "today_count": 0, "today_date": "",
            "name": "", "username": "", "balance": 0,
            "total_audits": 0, "reviews_given": False
        }
    return users[uid]

def check_limit(uid):
    from datetime import date
    u = get_user(uid)
    today = str(date.today())
    if u["today_date"] != today:
        u["today_count"] = 0
        u["today_date"] = today
    return u["today_count"] < PLANS[u["plan"]]["audits"]

def use_limit(uid):
    u = get_user(uid)
    u["today_count"] += 1
    u["total_audits"] += 1

def get_remaining(uid):
    from datetime import date
    u = get_user(uid)
    today = str(date.today())
    if u["today_date"] != today:
        return PLANS[u["plan"]]["audits"]
    limit = PLANS[u["plan"]]["audits"]
    if limit == 999999:
        return "∞"
    return max(0, limit - u["today_count"])

# ─── Клавиатуры ───
def kb_main(uid):
    u = get_user(uid)
    plan = u["plan"]
    remaining = get_remaining(uid)
    
    keyboard = [
        [
            InlineKeyboardButton("🔍 Аудит карточки", callback_data="audit"),
            InlineKeyboardButton("⭐ Отзывы", callback_data="reviews")
        ],
        [
            InlineKeyboardButton("📝 Описание товара", callback_data="description"),
            InlineKeyboardButton("🔑 SEO слова", callback_data="keywords")
        ],
        [
            InlineKeyboardButton("🎯 Оффер и УТП", callback_data="offer"),
            InlineKeyboardButton("💰 Расчёт прибыли", callback_data="finance")
        ],
        [
            InlineKeyboardButton("🧾 Налоги и бухучёт", callback_data="taxes"),
            InlineKeyboardButton("📊 Анализ конкурентов", callback_data="competitors")
        ],
        [
            InlineKeyboardButton("🤖 AI-наставник", callback_data="mentor"),
            InlineKeyboardButton("📅 Контент-план", callback_data="content")
        ],
        [
            InlineKeyboardButton("👤 Личный кабинет", callback_data="profile"),
            InlineKeyboardButton("⭐ Тарифы и оплата", callback_data="plans")
        ],
        [InlineKeyboardButton("✍️ Оставить отзыв о боте", callback_data="leave_review")],
    ]
    return InlineKeyboardMarkup(keyboard)

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])

def kb_plans():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Про — 990 ₽/мес", callback_data="buy_pro")],
        [InlineKeyboardButton("💎 Бизнес — 2990 ₽/мес", callback_data="buy_biz")],
        [InlineKeyboardButton("💬 Написать администратору", url=f"https://t.me/{ADMIN_TG}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ])

# ─── /start ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    u["name"] = update.effective_user.first_name or "Продавец"
    u["username"] = update.effective_user.username or ""
    name = u["name"]
    plan = PLANS[u["plan"]]
    remaining = get_remaining(uid)
    
    text = (
        f"👋 Привет, *{name}*!\n\n"
        f"🚀 *Продажник.AI* — твой личный эксперт по WB и Ozon\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Твой тариф: *{plan['name']}*\n"
        f"🔢 Осталось анализов сегодня: *{remaining}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Что умею:*\n"
        f"🔍 Аудит карточки товара по ссылке\n"
        f"⭐ Анализ отзывов покупателей\n"
        f"📝 Создание продающих описаний\n"
        f"🔑 Подбор SEO ключевых слов\n"
        f"🎯 Разработка офферов и УТП\n"
        f"💰 Расчёт прибыли и юнит-экономики\n"
        f"🧾 Налоги и бухгалтерия для WB/Ozon\n"
        f"📊 Анализ конкурентов\n"
        f"🤖 AI-наставник по маркетплейсам\n"
        f"📅 Контент-план для соцсетей\n\n"
        f"Выбери нужный инструмент 👇"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_main(uid))

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text("Выбери инструмент 👇", reply_markup=kb_main(uid))

# ─── Кнопки ───
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    u = get_user(uid)
    d = query.data

    if d == "main_menu":
        await query.message.reply_text("Главное меню 👇", reply_markup=kb_main(uid))
        return

    if d == "profile":
        plan = PLANS[u["plan"]]
        remaining = get_remaining(uid)
        text = (
            f"👤 *Личный кабинет*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Имя: *{u['name']}*\n"
            f"📱 Username: @{u['username'] or 'не указан'}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 Тариф: *{plan['name']}*\n"
            f"📋 Описание: {plan['desc']}\n"
            f"🔢 Осталось сегодня: *{remaining}*\n"
            f"📊 Всего анализов: *{u['total_audits']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Баланс: *{u['balance']} ₽*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Для пополнения баланса или смены тарифа нажми кнопку ниже 👇"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Сменить тариф", callback_data="plans")],
            [InlineKeyboardButton("💬 Поддержка", url=f"https://t.me/{ADMIN_TG}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
        ])
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if d == "plans":
        text = (
            f"💎 *Тарифы Продажник.AI*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆓 *Старт* — Бесплатно\n"
            f"• 3 аудита карточек в день\n"
            f"• Описания товаров\n"
            f"• SEO ключевые слова\n"
            f"• Базовый анализ\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ *Про* — 990 ₽/мес\n"
            f"• Безлимитные аудиты\n"
            f"• Все инструменты без ограничений\n"
            f"• Анализ конкурентов\n"
            f"• Расчёт прибыли и налогов\n"
            f"• Приоритетная поддержка\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *Бизнес* — 2990 ₽/мес\n"
            f"• Всё из Про\n"
            f"• AI-наставник с памятью\n"
            f"• Персональный разбор бизнеса\n"
            f"• Ручной анализ от команды\n"
            f"• Консультация бухгалтера\n"
            f"• Реальные данные о конкурентах\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 *Бухгалтер/Юрист* — от 500 ₽\n"
            f"• Расчёт всех налогов WB/Ozon\n"
            f"• Подача отчётов в налоговую\n"
            f"• Представление в суде\n"
            f"• Юридическая поддержка\n\n"
            f"Для подключения напиши администратору 👇"
        )
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_plans())
        return

    if d == "buy_pro":
        text = (
            f"⭐ *Подключение Про тарифа*\n\n"
            f"Стоимость: *990 ₽/мес*\n\n"
            f"Что входит:\n"
            f"✅ Безлимитные аудиты карточек\n"
            f"✅ Все инструменты без ограничений\n"
            f"✅ Анализ конкурентов\n"
            f"✅ Расчёт прибыли и налогов\n"
            f"✅ Приоритетная поддержка\n\n"
            f"Напиши администратору для оплаты через ЮКассу:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить Про — 990 ₽", url=f"https://t.me/{ADMIN_TG}?text=Хочу подключить Про тариф 990 руб")],
            [InlineKeyboardButton("◀️ Назад", callback_data="plans")],
        ])
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if d == "buy_biz":
        text = (
            f"💎 *Подключение Бизнес тарифа*\n\n"
            f"Стоимость: *2990 ₽/мес*\n\n"
            f"Что входит:\n"
            f"✅ Всё из Про тарифа\n"
            f"✅ AI-наставник с памятью\n"
            f"✅ Персональный разбор бизнеса\n"
            f"✅ Ручной анализ от команды\n"
            f"✅ Консультация бухгалтера\n"
            f"✅ Реальные данные о конкурентах\n\n"
            f"Напиши администратору для оплаты:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить Бизнес — 2990 ₽", url=f"https://t.me/{ADMIN_TG}?text=Хочу подключить Бизнес тариф 2990 руб")],
            [InlineKeyboardButton("◀️ Назад", callback_data="plans")],
        ])
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if d == "leave_review":
        context.user_data["mode"] = "leave_review"
        await query.message.reply_text(
            f"✍️ *Оставить отзыв о Продажник.AI*\n\n"
            f"Напиши своё мнение о боте — что понравилось, что улучшить.\n"
            f"Твой отзыв поможет нам стать лучше! 🙏\n\n"
            f"Просто напиши сообщение 👇",
            parse_mode="Markdown",
            reply_markup=kb_back()
        )
        return

    if d == "taxes":
        text = (
            f"🧾 *Налоги и бухгалтерия для маркетплейсов*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Что могу рассчитать бесплатно:*\n"
            f"• УСН 6% (доходы)\n"
            f"• УСН 15% (доходы минус расходы)\n"
            f"• Налог для самозанятых\n"
            f"• Страховые взносы ИП\n"
            f"• Сравнение режимов налогообложения\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 *Услуги профессионального бухгалтера* (от 500 ₽):\n"
            f"• Полный расчёт налогов WB/Ozon\n"
            f"• Подача деклараций в налоговую\n"
            f"• Квартальные/годовые отчёты\n"
            f"• Представление интересов в суде\n"
            f"• Налоговая оптимизация\n"
            f"• Регистрация ИП/ООО\n\n"
            f"Для работы с профессиональным бухгалтером — напиши нам 👇"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 Рассчитать налоги AI", callback_data="calc_taxes")],
            [InlineKeyboardButton("💼 Бухгалтер (от 500 ₽)", url=f"https://t.me/{ADMIN_TG}?text=Нужна консультация бухгалтера по маркетплейсам")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
        ])
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if d == "calc_taxes":
        context.user_data["mode"] = "taxes"
        await query.message.reply_text(
            f"🧾 *Расчёт налогов*\n\n"
            f"Напиши свои данные в формате:\n"
            f"*Статус, Доход/мес, Расходы/мес*\n\n"
            f"Пример:\n"
            f"`ИП УСН 6%, 300000, 150000`\n\n"
            f"Статусы: ИП УСН 6%, ИП УСН 15%, Самозанятый",
            parse_mode="Markdown",
            reply_markup=kb_back()
        )
        return

    tool_msgs = {
        "audit": (
            f"🔍 *Аудит карточки товара*\n\n"
            f"*Что анализирую:*\n"
            f"📋 Заголовок — соответствие SEO, привлекательность, ключевые слова\n"
            f"📝 Описание — структура, продающие элементы, характеристики\n"
            f"📸 Фото — количество, качество, инфографика, видео\n"
            f"🔍 SEO — ключевые слова, индексация, позиции\n"
            f"💰 Цена — конкурентоспособность, скидки, стратегия\n"
            f"⭐ Отзывы — рейтинг, работа с негативом, количество\n\n"
            f"*Как получить аудит:*\n"
            f"Отправь ссылку на товар с WB или Ozon\n"
            f"Или отправь скриншот карточки товара 📸\n\n"
            f"Пример: `https://www.wildberries.ru/catalog/123456/detail.aspx`"
        ),
        "reviews": (
            f"⭐ *Анализ отзывов покупателей*\n\n"
            f"*Что анализирую:*\n"
            f"😤 Главные жалобы и проблемы\n"
            f"👍 Что хвалят и ценят покупатели\n"
            f"💡 Скрытые инсайты и паттерны\n"
            f"📈 Как поднять рейтинг\n"
            f"💬 Готовые шаблоны ответов на негатив\n\n"
            f"*Как получить анализ:*\n"
            f"Отправь текст отзывов или скриншот страницы с отзывами 📸\n\n"
            f"Чем больше отзывов — тем точнее анализ!"
        ),
        "description": (
            f"📝 *Создание описания товара*\n\n"
            f"*Что создам:*\n"
            f"📋 SEO-оптимизированный заголовок\n"
            f"✅ Продающие выгоды (не характеристики!)\n"
            f"📖 Подробное описание 150-300 слов\n"
            f"🔑 Встроенные ключевые слова\n"
            f"📊 Структурированные характеристики\n"
            f"🎯 Призыв к действию\n\n"
            f"*Как получить описание:*\n"
            f"Напиши название товара и его характеристики\n"
            f"Или отправь фото товара 📸"
        ),
        "keywords": (
            f"🔑 *SEO ключевые слова*\n\n"
            f"*Что получишь:*\n"
            f"🎯 Оптимизированный заголовок до 100 символов\n"
            f"🔥 15 высокочастотных запросов\n"
            f"📊 15 среднечастотных запросов\n"
            f"💎 10 низкочастотных (низкая конкуренция)\n"
            f"📝 Советы по оптимизации карточки\n"
            f"📈 Стратегия продвижения в поиске\n\n"
            f"*Как получить:*\n"
            f"Напиши название товара и категорию"
        ),
        "offer": (
            f"🎯 *Оффер и УТП*\n\n"
            f"*Что создам:*\n"
            f"💎 Уникальное торговое предложение (1 строка)\n"
            f"📣 Главный заголовок + подзаголовок\n"
            f"✅ 5 выгод для покупателя\n"
            f"🛒 Оффер для карточки WB/Ozon\n"
            f"📱 Оффер для Telegram-канала\n"
            f"📊 Оффер для рекламы\n\n"
            f"*Как получить:*\n"
            f"Напиши: что продаёшь, главное преимущество, целевую аудиторию"
        ),
        "finance": (
            f"💰 *Расчёт прибыли и юнит-экономика*\n\n"
            f"*Что рассчитаю:*\n"
            f"💵 Выручка, расходы, чистая прибыль\n"
            f"📊 Маржинальность в %\n"
            f"📦 Прибыль с 1 единицы товара\n"
            f"📈 Точка безубыточности\n"
            f"💡 5 способов увеличить прибыль\n"
            f"🎯 Оптимальная цена\n\n"
            f"*Как получить расчёт:*\n"
            f"Напиши через запятую:\n"
            f"`Цена продажи, Себестоимость, Продаж/мес, Комиссия%, Логистика`\n"
            f"Пример: `2490, 890, 150, 15, 80`"
        ),
        "competitors": (
            f"📊 *Анализ конкурентов*\n\n"
            f"*Что анализирую:*\n"
            f"🔍 Конкурентная среда в нише\n"
            f"💪 Слабые места конкурентов\n"
            f"🎯 Стратегия дифференциации\n"
            f"💰 Рекомендации по цене\n"
            f"📈 SEO против конкурентов\n"
            f"📢 Стратегия рекламы\n\n"
            f"*Как получить анализ:*\n"
            f"Напиши свой товар, нишу и что знаешь о конкурентах\n"
            f"Или отправь скриншот страницы поиска 📸"
        ),
        "mentor": (
            f"🤖 *AI-наставник по маркетплейсам*\n\n"
            f"*Что умею:*\n"
            f"❓ Отвечу на любой вопрос о WB и Ozon\n"
            f"📋 Дам пошаговый план действий\n"
            f"⚠️ Расскажу о типичных ошибках\n"
            f"📈 Помогу разработать стратегию роста\n"
            f"💡 Поделюсь инсайтами и лайфхаками\n"
            f"🔍 Разберу твою конкретную ситуацию\n\n"
            f"*Как получить совет:*\n"
            f"Задай любой вопрос о продажах на маркетплейсах!\n\n"
            f"Например: _Как выйти на WB с нуля с бюджетом 50к?_"
        ),
        "content": (
            f"📅 *Контент-план для соцсетей*\n\n"
            f"*Что создам:*\n"
            f"📆 План публикаций на месяц\n"
            f"💡 Темы и форматы постов\n"
            f"📱 Адаптация под Telegram/Instagram/ВК\n"
            f"🔥 Идеи вирусного контента\n"
            f"⏰ Лучшее время публикаций\n"
            f"#️⃣ Хэштеги и теги\n\n"
            f"*Как получить план:*\n"
            f"Напиши свою нишу, платформу и частоту публикаций"
        ),
    }

    if d in tool_msgs:
        context.user_data["mode"] = d
        await query.message.reply_text(
            tool_msgs[d], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])
        )
        return

# ─── Обработка сообщений ───
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    mode = context.user_data.get("mode", "")

    # Получаем текст
    text = ""
    has_photo = False
    has_voice = False

    if update.message.text:
        text = update.message.text
    elif update.message.photo:
        has_photo = True
        text = update.message.caption or ""
    elif update.message.voice:
        has_voice = True

    if has_voice:
        await update.message.reply_text(
            "🎤 Голосовые сообщения пока не поддерживаются.\n"
            "Напиши текстом или отправь скриншот 📸",
            reply_markup=kb_back()
        )
        return

    if not mode and not has_photo:
        await update.message.reply_text(
            "Выбери инструмент из меню 👇",
            reply_markup=kb_main(uid)
        )
        return

    # Если фото без режима — аудит
    if has_photo and not mode:
        mode = "audit"
        context.user_data["mode"] = "audit"

    # Отзыв о боте
    if mode == "leave_review":
        review_text = text or "📸 [скриншот]"
        # Отправляем отзыв администратору
        try:
            bot = context.bot
            await bot.send_message(
                chat_id=f"@{ADMIN_TG}",
                text=f"⭐ ОТЗЫВ О БОТЕ\n\nОт: {u['name']} (@{u.get('username','')})\nUID: {uid}\n\nОтзыв:\n{review_text}"
            )
        except:
            pass
        u["reviews_given"] = True
        context.user_data["mode"] = ""
        await update.message.reply_text(
            "✅ *Спасибо за отзыв!*\n\nМы обязательно учтём твоё мнение 🙏",
            parse_mode="Markdown",
            reply_markup=kb_main(uid)
        )
        return

    # Проверка лимита
    if not check_limit(uid):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Подключить Про — 990 ₽", callback_data="buy_pro")],
            [InlineKeyboardButton("◀️ Меню", callback_data="main_menu")],
        ])
        await update.message.reply_text(
            f"❌ *Лимит исчерпан*\n\n"
            f"На бесплатном тарифе — 3 аудита в день.\n"
            f"Подключи Про для безлимитных анализов!",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    msg = await update.message.reply_text("⏳ *Анализирую...*\n\nПодожди 20-30 секунд, готовлю детальный отчёт", parse_mode="Markdown")

    try:
        photo_note = "\n[Пользователь прислал скриншот карточки товара - анализируй как будто видишь реальную карточку]" if has_photo else ""

        if mode == "audit":
            if not has_photo and not text.startswith("http"):
                await msg.edit_text("❌ Отправь ссылку с https:// или скриншот карточки товара 📸")
                return
            p = "Ozon" if text and "ozon" in text else "Wildberries"
            ref = f"ссылка: {text}" if text.startswith("http") else "скриншот карточки"
            prompt = (
                f"Ты эксперт по маркетплейсам с 10 годами опыта. Проведи ДЕТАЛЬНЫЙ аудит карточки на {p} ({ref}).{photo_note}\n\n"
                f"ВАЖНО: давай конкретные, развёрнутые советы. Никаких общих фраз!\n\n"
                f"Формат ответа:\n\n"
                f"1️⃣ ЗАГОЛОВОК (X/100)\n"
                f"Текущий: [процитируй или опиши]\n"
                f"Проблемы: [конкретно что не так]\n"
                f"✏️ Готовый новый заголовок: [напиши прямо сейчас]\n\n"
                f"2️⃣ ОПИСАНИЕ (X/100)\n"
                f"Анализ: [что есть, чего нет]\n"
                f"Проблемы: [конкретно]\n"
                f"✏️ Что добавить: [конкретные блоки текста]\n\n"
                f"3️⃣ ФОТО И МЕДИА (X/100)\n"
                f"Текущее состояние: [опиши]\n"
                f"✏️ Что добавить: [конкретный список: инфографика с ценой, фото в использовании, видео, etc]\n\n"
                f"4️⃣ SEO (X/100)\n"
                f"Текущие ключевые слова: [перечисли]\n"
                f"Отсутствуют: [5+ конкретных запросов для этого товара]\n"
                f"✏️ Готовые ключевые слова для добавления: [список]\n\n"
                f"5️⃣ ЦЕНА (X/100)\n"
                f"Текущая цена: [укажи]\n"
                f"Анализ: [завышена/нормальная/занижена и почему]\n"
                f"✏️ Рекомендация: [конкретная цена или стратегия]\n\n"
                f"6️⃣ ОТЗЫВЫ (X/100)\n"
                f"Рейтинг/количество: [укажи]\n"
                f"Проблемы: [конкретно]\n"
                f"✏️ Как улучшить: [конкретные шаги]\n\n"
                f"━━━━━━━━━━\n"
                f"🏆 ИТОГОВАЯ ОЦЕНКА: X/100\n\n"
                f"🎯 ПЛАН ДЕЙСТВИЙ (по приоритету):\n"
                f"1. [Самое важное — сделай сегодня]\n"
                f"2. [На этой неделе]\n"
                f"3. [В течение месяца]\n"
                f"4. [Дополнительно]\n"
                f"5. [Долгосрочно]\n\n"
                f"💡 СЕКРЕТНЫЙ ЛАЙФХАК для этого товара: [конкретный совет]"
            )

        elif mode == "reviews":
            prompt = (
                f"Ты эксперт по управлению репутацией на маркетплейсах.{photo_note}\n"
                f"Проанализируй отзывы ДЕТАЛЬНО:\n{text}\n\n"
                f"1️⃣ ГЛАВНЫЕ ЖАЛОБЫ (топ-5 с частотой упоминаний)\n"
                f"Для каждой жалобы: в чём причина и как устранить\n\n"
                f"2️⃣ ЧТО ХВАЛЯТ (топ-5 преимуществ)\n"
                f"Как использовать это в маркетинге\n\n"
                f"3️⃣ СКРЫТЫЕ ИНСАЙТЫ\n"
                f"Что не написано прямо, но видно между строк\n\n"
                f"4️⃣ КАК ПОДНЯТЬ РЕЙТИНГ\n"
                f"Конкретные шаги с временными рамками\n\n"
                f"5️⃣ ГОТОВЫЕ ШАБЛОНЫ ОТВЕТОВ\n"
                f"- Ответ на типичный негативный отзыв\n"
                f"- Ответ на позитивный отзыв\n\n"
                f"6️⃣ УЛУЧШЕНИЯ ТОВАРА\n"
                f"Что изменить в самом товаре по данным отзывов"
            )

        elif mode == "description":
            prompt = (
                f"Ты топовый копирайтер для маркетплейсов.{photo_note}\n"
                f"Товар: {text}\n\n"
                f"Создай ПРОДАЮЩЕЕ описание для WB/Ozon:\n\n"
                f"📋 ЗАГОЛОВОК (до 100 символов, с главным ключевым словом):\n[напиши]\n\n"
                f"⚡ ГЛАВНЫЕ ВЫГОДЫ (5 штук, эмодзи + выгода для покупателя, не характеристики!):\n[напиши]\n\n"
                f"📖 ОСНОВНОЕ ОПИСАНИЕ (200-250 слов):\n[напиши]\n\n"
                f"📊 ХАРАКТЕРИСТИКИ (таблицей):\n[напиши]\n\n"
                f"🎯 ПРИЗЫВ К ДЕЙСТВИЮ:\n[напиши]\n\n"
                f"🔑 КЛЮЧЕВЫЕ СЛОВА (встроены в текст):\n[перечисли использованные]"
            )

        elif mode == "keywords":
            prompt = (
                f"Ты SEO-специалист по маркетплейсам с глубоким знанием WB и Ozon.\n"
                f"Товар: {text}\n\n"
                f"Подбери ключевые слова КОНКРЕТНО для этого товара:\n\n"
                f"📋 ОПТИМИЗИРОВАННЫЙ ЗАГОЛОВОК (до 100 символов):\n[напиши готовый заголовок]\n\n"
                f"🔥 ВЫСОКОЧАСТОТНЫЕ ЗАПРОСЫ (15 штук):\n[список с примерным объёмом поиска]\n\n"
                f"📊 СРЕДНЕЧАСТОТНЫЕ ЗАПРОСЫ (15 штук):\n[список]\n\n"
                f"💎 НИЗКОЧАСТОТНЫЕ (меньше конкуренции, 10 штук):\n[список]\n\n"
                f"📍 ГЕОЗАВИСИМЫЕ ЗАПРОСЫ (если актуально):\n[список]\n\n"
                f"💡 СОВЕТЫ ПО ОПТИМИЗАЦИИ:\n"
                f"- Куда вставить ключевые слова в карточке\n"
                f"- Как правильно заполнить характеристики\n"
                f"- Ошибки которых избегать"
            )

        elif mode == "offer":
            prompt = (
                f"Ты маркетолог-эксперт по продажам на маркетплейсах.\n"
                f"Информация: {text}\n\n"
                f"Создай УБОЙНЫЙ оффер:\n\n"
                f"💎 УТП (одна строка — почему купят именно у тебя):\n[напиши]\n\n"
                f"📣 ГЛАВНЫЙ ЗАГОЛОВОК:\n[напиши]\n\n"
                f"📣 ПОДЗАГОЛОВОК:\n[напиши]\n\n"
                f"✅ ВЫГОДЫ ДЛЯ ПОКУПАТЕЛЯ (5 штук — выгоды, не характеристики!):\n[напиши]\n\n"
                f"🛒 ОФФЕР ДЛЯ КАРТОЧКИ WB/OZON:\n[готовый текст]\n\n"
                f"📱 ОФФЕР ДЛЯ TELEGRAM:\n[готовый текст с эмодзи]\n\n"
                f"📢 ОФФЕР ДЛЯ РЕКЛАМЫ (Яндекс/ВК):\n[готовый текст]"
            )

        elif mode == "finance":
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 3:
                await msg.edit_text("❌ Формат: Цена, Себестоимость, Продаж/мес, Комиссия%, Логистика\nПример: 2490, 890, 150, 15, 80")
                return
            price = float(parts[0])
            cost = float(parts[1])
            qty = float(parts[2])
            comm = float(parts[3]) if len(parts) > 3 else 15
            log = float(parts[4]) if len(parts) > 4 else 80
            rev = price * qty
            exp = (rev * comm / 100) + (log * qty) + (cost * qty)
            profit = rev - exp
            margin = (profit / rev * 100) if rev > 0 else 0
            profit_per_unit = (price - cost - price * comm / 100 - log)
            prompt = (
                f"Ты финансовый аналитик для маркетплейсов.\n\n"
                f"ДАННЫЕ:\n"
                f"Цена: {price}₽ | Себестоимость: {cost}₽ | Продаж: {qty}шт/мес\n"
                f"Комиссия: {comm}% | Логистика: {log}₽/шт\n"
                f"Выручка: {rev:,.0f}₽ | Расходы: {exp:,.0f}₽\n"
                f"Прибыль: {profit:,.0f}₽ | Маржа: {margin:.1f}%\n"
                f"Прибыль с 1 шт: {profit_per_unit:,.0f}₽\n\n"
                f"Дай ДЕТАЛЬНЫЙ анализ:\n\n"
                f"📊 ОЦЕНКА ПОКАЗАТЕЛЕЙ:\n"
                f"Сравни с нормой для маркетплейсов (хорошо/нормально/плохо и почему)\n\n"
                f"⚠️ ГЛАВНЫЕ ПРОБЛЕМЫ:\n"
                f"Что убивает прибыль и почему\n\n"
                f"💡 ТОП-7 СПОСОБОВ УВЕЛИЧИТЬ ПРИБЫЛЬ:\n"
                f"Конкретные действия с ожидаемым эффектом в рублях\n\n"
                f"📈 ПРОГНОЗ:\n"
                f"Прибыль при оптимизации (через 1 мес и через 3 мес)\n\n"
                f"🎯 ОПТИМАЛЬНАЯ ЦЕНА:\n"
                f"Рекомендуемая цена для максимальной прибыли"
            )

        elif mode == "competitors":
            prompt = (
                f"Ты стратег по маркетплейсам.{photo_note}\n"
                f"Информация: {text}\n\n"
                f"Проведи ДЕТАЛЬНЫЙ анализ конкурентов:\n\n"
                f"🔍 АНАЛИЗ НИШИ:\n"
                f"Уровень конкуренции, топ игроки, тренды\n\n"
                f"💪 СЛАБЫЕ МЕСТА КОНКУРЕНТОВ:\n"
                f"Конкретные уязвимости которые можно использовать\n\n"
                f"🎯 СТРАТЕГИЯ ДИФФЕРЕНЦИАЦИИ:\n"
                f"5 конкретных способов выделиться\n\n"
                f"💰 СТРАТЕГИЯ ЦЕНООБРАЗОВАНИЯ:\n"
                f"Оптимальная цена и ценовое позиционирование\n\n"
                f"📈 SEO-СТРАТЕГИЯ ПРОТИВ КОНКУРЕНТОВ:\n"
                f"Ключевые слова которые они упускают\n\n"
                f"📢 РЕКЛАМНАЯ СТРАТЕГИЯ:\n"
                f"Где и как рекламироваться чтобы обойти конкурентов\n\n"
                f"🏆 ПЛАН ЗАХВАТА РЫНКА НА 90 ДНЕЙ"
            )

        elif mode == "mentor":
            prompt = (
                f"Ты опытный наставник по WB и Ozon с 10 годами практики.\n"
                f"Вопрос: {text}\n\n"
                f"Дай РАЗВЁРНУТЫЙ профессиональный ответ:\n\n"
                f"✅ ПРЯМОЙ ОТВЕТ НА ВОПРОС\n\n"
                f"📋 ПОШАГОВЫЙ ПЛАН ДЕЙСТВИЙ (с конкретными шагами)\n\n"
                f"⚠️ ТИПИЧНЫЕ ОШИБКИ которых нужно избежать\n\n"
                f"💡 КОНКРЕТНЫЕ ПРИМЕРЫ из практики\n\n"
                f"📈 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ\n\n"
                f"🔑 ГЛАВНЫЙ СОВЕТ (самое важное в 1-2 предложениях)"
            )

        elif mode == "content":
            prompt = (
                f"Ты контент-стратег для продавцов маркетплейсов.\n"
                f"Информация: {text}\n\n"
                f"Создай ДЕТАЛЬНЫЙ контент-план на месяц:\n\n"
                f"📅 ПЛАН ПО НЕДЕЛЯМ:\n"
                f"Неделя 1: [темы и форматы]\n"
                f"Неделя 2: [темы и форматы]\n"
                f"Неделя 3: [темы и форматы]\n"
                f"Неделя 4: [темы и форматы]\n\n"
                f"🔥 ТОП-5 ИДЕЙ ДЛЯ ВИРУСНЫХ ПОСТОВ\n\n"
                f"📌 РУБРИКИ которые нужно вести постоянно\n\n"
                f"⏰ ЛУЧШЕЕ ВРЕМЯ для публикаций\n\n"
                f"#️⃣ ХЭШТЕГИ (20 штук для этой ниши)\n\n"
                f"📊 KPI: какие метрики отслеживать"
            )

        elif mode == "taxes":
            prompt = (
                f"Ты налоговый консультант для ИП на маркетплейсах.\n"
                f"Данные: {text}\n\n"
                f"Сделай ПОЛНЫЙ расчёт налогов:\n\n"
                f"💰 РАСЧЁТ ПО ТЕКУЩЕМУ РЕЖИМУ:\n"
                f"- Налог за месяц: X ₽\n"
                f"- Налог за квартал: X ₽\n"
                f"- Налог за год: X ₽\n"
                f"- Когда платить (даты)\n\n"
                f"⚖️ СРАВНЕНИЕ РЕЖИМОВ:\n"
                f"- УСН 6%: X ₽/год\n"
                f"- УСН 15%: X ₽/год\n"
                f"- Самозанятый: X ₽/год\n"
                f"- Какой выгоднее и почему\n\n"
                f"💡 ЗАКОННЫЕ СПОСОБЫ СНИЗИТЬ НАЛОГ:\n"
                f"Конкретные методы с суммами экономии\n\n"
                f"📋 СТРАХОВЫЕ ВЗНОСЫ ИП:\n"
                f"Фиксированные и дополнительные\n\n"
                f"⚠️ ВАЖНЫЕ ДАТЫ И ДЕДЛАЙНЫ"
            )

        else:
            await msg.edit_text("Выбери инструмент /menu")
            return

        result = ask_ai(prompt)
        use_limit(uid)
        context.user_data["mode"] = ""

        if len(result) > 4000:
            # Разбиваем на части
            parts = [result[i:i+3900] for i in range(0, len(result), 3900)]
            await msg.edit_text(f"📊 *Часть 1/{len(parts)}*\n\n{parts[0]}", parse_mode="Markdown")
            for i, part in enumerate(parts[1:], 2):
                await update.message.reply_text(
                    f"📊 *Часть {i}/{len(parts)}*\n\n{part}",
                    parse_mode="Markdown"
                )
            await update.message.reply_text(
                f"✅ Анализ завершён!\n\n/menu — другие инструменты",
                reply_markup=kb_main(uid)
            )
        else:
            await msg.edit_text(
                f"{result}\n\n─────────────\n/menu — другие инструменты",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(
            "❌ Произошла ошибка. Попробуй снова или напиши /menu",
            reply_markup=kb_main(uid)
        )

# ─── Обработка фото ───
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mode = context.user_data.get("mode", "audit")
    if not mode:
        context.user_data["mode"] = "audit"
    update.message.text = update.message.caption or ""
    await handle_message(update, context)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎤 Голосовые сообщения пока не поддерживаются.\n"
        "Напиши текстом или отправь скриншот 📸"
    )

def main():
    threading.Thread(target=run_http, daemon=True).start()
    logger.info(f"HTTP server on port {PORT}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
