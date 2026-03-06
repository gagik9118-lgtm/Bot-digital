import telebot
from telebot import types
import sqlite3
import time
import threading
from datetime import datetime, timedelta
import random
import string
import os
from functools import wraps

# Конфигурация - Токен берется из переменных окружения
TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_TOKEN_HERE')
OWNER_ID = 8396445302  # Твой ID (владелец)
ADMIN_IDS = [8396445302]  # Список админов (ты и другие)

bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    # Удаляем старую таблицу если есть
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS requests')
    c.execute('DROP TABLE IF EXISTS referrals')
    c.execute('DROP TABLE IF EXISTS transactions')
    c.execute('DROP TABLE IF EXISTS banned_users')
    
    # Таблица пользователей
    c.execute('''CREATE TABLE users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  is_admin INTEGER DEFAULT 0,
                  is_banned INTEGER DEFAULT 0,
                  joined_date TEXT,
                  referrer_id INTEGER DEFAULT NULL,
                  referral_code TEXT UNIQUE,
                  balance INTEGER DEFAULT 0)''')
    
    # Таблица забаненных
    c.execute('''CREATE TABLE banned_users
                 (user_id INTEGER PRIMARY KEY,
                  banned_by INTEGER,
                  ban_date TEXT,
                  reason TEXT DEFAULT NULL)''')
    
    # Таблица заявок
    c.execute('''CREATE TABLE requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  service TEXT,
                  sub_service TEXT,
                  description TEXT,
                  deadline TEXT,
                  budget TEXT,
                  business_type TEXT,
                  status TEXT DEFAULT 'new',
                  created_at TEXT)''')
    
    # Таблица рефералов
    c.execute('''CREATE TABLE referrals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referrer_id INTEGER,
                  referral_id INTEGER,
                  date TEXT,
                  bonus_amount INTEGER DEFAULT 0,
                  bonus_paid INTEGER DEFAULT 0)''')
    
    # Таблица транзакций
    c.execute('''CREATE TABLE transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount INTEGER,
                  type TEXT,
                  description TEXT,
                  date TEXT)''')
    
    conn.commit()
    conn.close()
    print("✅ База данных создана заново!")

# Декоратор для проверки бана
def check_banned(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result and result[0] == 1:
            bot.send_message(message.chat.id, 
                           "⛔ Вы были заблокированы администрацией.\n"
                           "По вопросам разблокировки: @Opps911")
            return
        return func(message, *args, **kwargs)
    return wrapper

# Декоратор для проверки бана в callback
def check_banned_callback(func):
    @wraps(func)
    def wrapper(call, *args, **kwargs):
        user_id = call.from_user.id
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result and result[0] == 1:
            bot.answer_callback_query(call.id, "⛔ Вы заблокированы")
            return
        return func(call, *args, **kwargs)
    return wrapper

# Генерация реферального кода
def generate_referral_code(user_id):
    return f"GOLD{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

# Начисление бонуса рефереру
def add_bonus_to_referrer(referrer_id, amount, description):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, referrer_id))
    c.execute("""INSERT INTO transactions (user_id, amount, type, description, date)
                 VALUES (?, ?, ?, ?, ?)""",
              (referrer_id, amount, 'bonus', description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

# Сохраняем пользователя
def save_user(message, referrer_code=None):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    user_id = message.from_user.id
    username = message.from_user.username or "Нет username"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return
    
    referral_code = generate_referral_code(user_id)
    referrer_id = None
    
    if referrer_code:
        c.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
        result = c.fetchone()
        if result:
            referrer_id = result[0]
            c.execute("INSERT INTO referrals (referrer_id, referral_id, date) VALUES (?, ?, ?)",
                     (referrer_id, user_id, joined_date))
    
    c.execute("""INSERT INTO users 
                 (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code, is_banned) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
              (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code))
    
    conn.commit()
    conn.close()

# Получаем всех пользователей
def get_all_users():
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, last_name, is_admin, is_banned, balance, referral_code FROM users")
    users = c.fetchall()
    conn.close()
    return users

# Главное меню
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    services = [
        "💻 Web-разработка",
        "📈 SEO-продвижение",
        "🎯 Таргет-реклама",
        "🤖 Telegram боты",
        "🔍 Аудит сайта",
        "🎨 Дизайн",
        "💼 Консультация (2.000₽/час)",
        "👥 Реферальная система",
        "⭐ Оставить отзыв"
    ]
    buttons = [types.KeyboardButton(service) for service in services]
    markup.add(*buttons)
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
@check_banned
def start(message):
    args = message.text.split()
    referrer_code = args[1] if len(args) > 1 else None
    
    save_user(message, referrer_code)
    
    welcome_text = """
🌟 Добро пожаловать в <b>Golden House</b>! 🌟

Золотой стандарт digital-услуг для вашего бизнеса. Мы превращаем идеи в прибыльные проекты.

<b>Наши контакты:</b>
📞 Телефон: +79509991605
💬 Telegram: @Goldenhouse911
📧 Email: digitalofficialgoldenhouse@gmail.com
👨‍💻 Владелец: @Opps911

Выберите интересующую вас услугу в меню ниже 👇
    """
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=main_menu())

# Обработка всех сообщений с проверкой бана
@bot.message_handler(func=lambda message: True)
@check_banned
def handle_all_messages(message):
    # Обработка отзыва
    if message.text == "⭐ Оставить отзыв":
        bot.send_message(message.chat.id, 
                        "📝 Оставьте свой отзыв в нашем специальном боте:\n\n"
                        "👉 @GoldenHouseOtzovBot\n\n"
                        "Ваше мнение очень важно для нас! 🌟",
                        reply_markup=main_menu())
    
    # Реферальная система
    elif message.text == "👥 Реферальная система":
        referral_system(message)
    
    # Дизайн
    elif message.text == "🎨 Дизайн":
        design_menu(message)
    
    # Консультация
    elif message.text == "💼 Консультация (2.000₽/час)":
        handle_consultation(message)
    
    # Остальные услуги
    elif message.text in [
        "💻 Web-разработка",
        "📈 SEO-продвижение",
        "🎯 Таргет-реклама",
        "🤖 Telegram боты",
        "🔍 Аудит сайта"
    ]:
        handle_service(message)

# Реферальная система
def referral_system(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    c.execute("SELECT referral_code, balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if not result:
        bot.send_message(message.chat.id, "❌ Ошибка: реферальный код не найден. Напишите /start заново.")
        conn.close()
        return
    
    referral_code, balance = result
    
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    referrals_count = c.fetchone()[0]
    
    c.execute("SELECT SUM(bonus_amount) FROM referrals WHERE referrer_id = ?", (user_id,))
    total_earned = c.fetchone()[0] or 0
    
    c.execute("SELECT amount, description, date FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT 5", (user_id,))
    transactions = c.fetchall()
    
    conn.close()
    
    referral_link = f"https://t.me/{bot.get_me().username}?start={referral_code}"
    
    text = f"""
👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА GOLDEN HOUSE</b>

💰 <b>Текущий баланс:</b> {balance} ₽
💵 <b>Всего заработано:</b> {total_earned} ₽
👤 <b>Приглашено друзей:</b> {referrals_count}

🔗 <b>Ваша реферальная ссылка:</b>
<code>{referral_link}</code>

📌 <b>Как это работает:</b>
• За каждого друга, который перейдёт по вашей ссылке и закажет услугу, вы получаете 10% от суммы заказа
• Выплаты раз в неделю (по запросу админу)
• Чем больше друзей, тем больше доход!
"""
    
    if transactions:
        text += "\n📋 <b>Последние начисления:</b>\n"
        for amount, desc, date in transactions:
            text += f"  • +{amount}₽ - {desc} ({date[:16]})\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_menu())

# Дизайн меню
def design_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("🏠 Дизайн интерьера (800₽/м²)", callback_data="design_interior"),
        types.InlineKeyboardButton("👕 Дизайн одежды", callback_data="design_clothing"),
        types.InlineKeyboardButton("📊 Инфографика", callback_data="design_infographic"),
        types.InlineKeyboardButton("💻 Веб-дизайн", callback_data="design_web"),
        types.InlineKeyboardButton("« Отмена", callback_data="cancel_design")
    ]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                    "🎨 <b>Выберите какой Вам нужен дизайн:</b>", 
                    parse_mode='HTML', reply_markup=markup)

# Обработка услуг
@bot.callback_query_handler(func=lambda call: True)
@check_banned_callback
def handle_callbacks(call):
    # Обработка админских коллбэков
    if call.from_user.id in ADMIN_IDS:
        handle_admin_callbacks(call)
        return
    
    # Обработка пользовательских коллбэков
    if call.data.startswith("design_") and call.data != "cancel_design":
        handle_design(call)
    elif call.data.startswith("cancel_"):
        cancel_order(call)
    elif call.data == "cancel_design":
        cancel_design(call)
    elif call.data == "back_to_main":
        back_to_main(call)
    elif call.data.startswith("delete_request_"):
        # Только админы могут удалять заявки
        if call.from_user.id in ADMIN_IDS:
            delete_request(call)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав")

# Удаление заявки
def delete_request(call):
    request_id = int(call.data.split("_")[2])
    
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("DELETE FROM requests WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    
    bot.edit_message_text(
        f"✅ Заявка #{request_id} удалена",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id, "Заявка удалена")

# Обработка выбора дизайна
def handle_design(call):
    user_id = call.from_user.id
    design_type = {
        "design_interior": "Дизайн интерьера (800₽/м²)",
        "design_clothing": "Дизайн одежды",
        "design_infographic": "Инфографика",
        "design_web": "Веб-дизайн"
    }.get(call.data, "Дизайн")
    
    user_data[user_id] = {'service': 'Дизайн', 'sub_service': design_type, 'step': 'business'}
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    bot.edit_message_text("📋 Расскажите о вашем бизнесе:\nЧем занимаетесь? Какая у вас ниша?",
                         call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    msg = bot.send_message(call.message.chat.id, "Введите описание:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_business)

# Обработка отмены
def cancel_order(call):
    user_id = int(call.data.split("_")[1])
    
    if user_id in user_data:
        del user_data[user_id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Заказ отменён. Возвращайтесь, когда будете готовы!", 
                    reply_markup=main_menu())

def cancel_design(call):
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Выбор дизайна отменён.", reply_markup=main_menu())

def back_to_main(call):
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=main_menu())

# Обработка услуг
def handle_service(message):
    user_id = message.from_user.id
    service = message.text
    
    user_data[user_id] = {'service': service, 'step': 'business'}
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "📋 Расскажите о вашем бизнесе:\n"
                          "Чем занимаетесь? Какая у вас ниша?",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_business)

# Обработка консультации
def handle_consultation(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
    user_data_db = c.fetchone()
    conn.close()
    
    username = user_data_db[0] if user_data_db else "Нет username"
    first_name = user_data_db[1] if user_data_db else ""
    last_name = user_data_db[2] if user_data_db else ""
    
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"""
🔔 <b>ЗАПРОС НА КОНСУЛЬТАЦИЮ (2.000₽/час)</b>

👤 <b>Клиент:</b> {first_name} {last_name}
🆔 <b>ID:</b> <code>{user_id}</code>
📱 <b>Username:</b> @{username}

💰 <b>Услуга:</b> Консультация (2.000₽/час)

⏰ <b>Время:</b> {datetime.now().strftime("%H:%M %d.%m.%Y")}
            """
            bot.send_message(admin_id, admin_text, parse_mode='HTML')
        except:
            pass
    
    bot.send_message(message.chat.id, 
                    "✅ Запрос на консультацию отправлен! Мы свяжемся с вами в ближайшее время.\n"
                    "Спасибо за обращение в Golden House! 🌟",
                    reply_markup=main_menu())

# Процессы создания заявки
def process_business(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['business'] = message.text
    user_data[user_id]['step'] = 'description'
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "💡 Что вы хотите получить?\n"
                          "Опишите задачу максимально подробно:",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_description)

def process_description(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['description'] = message.text
    user_data[user_id]['step'] = 'deadline'
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "⏰ Какой дедлайн?\n"
                          "Например: 3 дня, неделя, срочно за 4 часа",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_deadline)

def process_deadline(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['deadline'] = message.text
    user_data[user_id]['step'] = 'budget'
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "💰 Какой бюджет?\n"
                          "Укажите сумму в рублях:",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_budget)

def process_budget(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['budget'] = message.text
    
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    user_info = bot.get_chat(user_id)
    username = user_info.username or "Нет username"
    
    c.execute("""INSERT INTO requests 
                 (user_id, username, service, sub_service, business_type, description, deadline, budget, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (user_id, username, 
               user_data[user_id]['service'],
               user_data[user_id].get('sub_service', ''),
               user_data[user_id]['business'],
               user_data[user_id]['description'],
               user_data[user_id]['deadline'],
               user_data[user_id]['budget'],
               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    
    try:
        budget_amount = int(''.join(filter(str.isdigit, user_data[user_id]['budget'])))
        bonus = int(budget_amount * 0.1)
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer = c.fetchone()
        
        if referrer and referrer[0]:
            referrer_id = referrer[0]
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, referrer_id))
            c.execute("""UPDATE referrals SET bonus_amount = ? 
                        WHERE referrer_id = ? AND referral_id = ?""", 
                     (bonus, referrer_id, user_id))
            c.execute("""INSERT INTO transactions (user_id, amount, type, description, date)
                         VALUES (?, ?, ?, ?, ?)""",
                      (referrer_id, bonus, 'bonus', 
                       f"Бонус за заказ #{request_id} от @{username}", 
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
    except:
        pass
    
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"""
🔔 <b>НОВАЯ ЗАЯВКА #{request_id}</b>

👤 <b>Клиент:</b> @{username}
🆔 <b>ID:</b> <code>{user_id}</code>

📋 <b>Услуга:</b> {user_data[user_id]['service']}
"""
            if user_data[user_id].get('sub_service'):
                admin_text += f"📌 <b>Подкатегория:</b> {user_data[user_id]['sub_service']}\n"
            
            admin_text += f"""
💼 <b>О бизнесе:</b> {user_data[user_id]['business']}
📝 <b>Описание:</b> {user_data[user_id]['description']}
⏰ <b>Дедлайн:</b> {user_data[user_id]['deadline']}
💰 <b>Бюджет:</b> {user_data[user_id]['budget']}

⏱ <b>Время:</b> {datetime.now().strftime("%H:%M %d.%m.%Y")}
            """
            
            # Добавляем кнопку удаления
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🗑 Удалить заявку", callback_data=f"delete_request_{request_id}"))
            
            bot.send_message(admin_id, admin_text, parse_mode='HTML', reply_markup=markup)
        except:
            pass
    
    bot.send_message(message.chat.id, 
                    "✅ Ваш отклик отправлен администрации на проверку!\n"
                    "Мы свяжемся с вами в ближайшее время.\n\n"
                    "Спасибо, что выбрали Golden House! 🌟",
                    reply_markup=main_menu())
    
    del user_data[user_id]

# АДМИН-ПАНЕЛЬ
@bot.message_handler(commands=['admin'])
@check_banned
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ У вас нет доступа к админ-панели.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("👑 Назначить админа", callback_data="make_admin"),
        types.InlineKeyboardButton("❌ Разжаловать админа", callback_data="remove_admin"),
        types.InlineKeyboardButton("💰 Начислить баланс", callback_data="add_balance"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        types.InlineKeyboardButton("📨 Заявки", callback_data="requests"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="broadcast"),
        types.InlineKeyboardButton("👥 Все пользователи", callback_data="all_users"),
        types.InlineKeyboardButton("📈 Рефералы (топ)", callback_data="referral_stats"),
        types.InlineKeyboardButton("🔗 Детали рефералов", callback_data="referral_details"),
        types.InlineKeyboardButton("🔨 Заблокировать", callback_data="ban_user"),
        types.InlineKeyboardButton("🔓 Разблокировать", callback_data="unban_user"),
        types.InlineKeyboardButton("📋 Статистика юзера", callback_data="user_stats")
    ]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                    "⚙️ <b>Панель управления Golden House</b>\n\n"
                    "Выберите действие:",
                    parse_mode='HTML', reply_markup=markup)

# Обработка админских коллбэков
def handle_admin_callbacks(call):
    if call.data == "make_admin":
        msg = bot.send_message(call.message.chat.id, 
                              "🔑 Напишите ID пользователя, чтобы назначить его администратором:")
        bot.register_next_step_handler(msg, process_make_admin)
    
    elif call.data == "remove_admin":
        if call.from_user.id != OWNER_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец может разжаловать админов")
            return
        
        admins_list = []
        for admin_id in ADMIN_IDS:
            if admin_id != OWNER_ID:
                try:
                    user = bot.get_chat(admin_id)
                    admins_list.append(f"🆔 <code>{admin_id}</code> - @{user.username or 'Нет username'}")
                except:
                    admins_list.append(f"🆔 <code>{admin_id}</code>")
        
        if not admins_list:
            bot.send_message(call.message.chat.id, "❌ Нет других администраторов")
            return
        
        text = "📋 <b>Администраторы (кроме владельца):</b>\n\n" + "\n".join(admins_list) + \
               "\n\n🔑 Введите ID пользователя, которого нужно разжаловать:"
        
        msg = bot.send_message(call.message.chat.id, text, parse_mode='HTML')
        bot.register_next_step_handler(msg, process_remove_admin)
    
    elif call.data == "add_balance":
        msg = bot.send_message(call.message.chat.id, 
                              "💰 Введите ID пользователя и сумму через пробел\n"
                              "Например: 123456789 1000")
        bot.register_next_step_handler(msg, process_add_balance)
    
    elif call.data == "stats":
        show_stats(call.message)
    
    elif call.data == "requests":
        show_requests(call.message)
    
    elif call.data == "broadcast":
        msg = bot.send_message(call.message.chat.id, 
                              "📢 Введите сообщение для рассылки всем пользователям:")
        bot.register_next_step_handler(msg, process_broadcast)
    
    elif call.data == "all_users":
        show_all_users(call.message)
    
    elif call.data == "referral_stats":
        show_referral_stats(call.message)
    
    elif call.data == "referral_details":
        show_referral_details(call.message)
    
    elif call.data == "ban_user":
        msg = bot.send_message(call.message.chat.id, 
                              "🔨 Введите ID пользователя для блокировки:")
        bot.register_next_step_handler(msg, process_ban_user)
    
    elif call.data == "unban_user":
        msg = bot.send_message(call.message.chat.id, 
                              "🔓 Введите ID пользователя для разблокировки:")
        bot.register_next_step_handler(msg, process_unban_user)
    
    elif call.data == "user_stats":
        msg = bot.send_message(call.message.chat.id, 
                              "📋 Введите ID пользователя для просмотра статистики:")
        bot.register_next_step_handler(msg, process_user_stats)
    
    bot.answer_callback_query(call.id)

# Процесс блокировки пользователя
def process_ban_user(message):
    try:
        user_id = int(message.text)
        
        if user_id in ADMIN_IDS:
            bot.send_message(message.chat.id, "❌ Нельзя заблокировать администратора!")
            return
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            conn.close()
            return
        
        # Баним пользователя
        c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        
        # Добавляем в таблицу банов
        c.execute("""INSERT OR REPLACE INTO banned_users (user_id, banned_by, ban_date)
                     VALUES (?, ?, ?)""",
                  (user_id, message.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, 
                        f"✅ Пользователь @{user[0]} (ID: {user_id}) заблокирован")
        
        try:
            bot.send_message(user_id, 
                           "⛔ Вы были заблокированы администрацией Golden House.\n"
                           "По вопросам разблокировки: @Opps911")
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID")

# Процесс разблокировки
def process_unban_user(message):
    try:
        user_id = int(message.text)
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            conn.close()
            return
        
        # Разбаниваем
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, 
                        f"✅ Пользователь @{user[0]} (ID: {user_id}) разблокирован")
        
        try:
            bot.send_message(user_id, 
                           "🔓 Вы были разблокированы администрацией Golden House.\n"
                           "Можете снова пользоваться ботом!")
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID")

# Полная статистика пользователя
def process_user_stats(message):
    try:
        user_id = int(message.text)
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        # Основная информация
        c.execute("""SELECT user_id, username, first_name, last_name, is_admin, is_banned, 
                            joined_date, referral_code, balance
                     FROM users WHERE user_id = ?""", (user_id,))
        user = c.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            conn.close()
            return
        
        user_id, username, first_name, last_name, is_admin, is_banned, joined_date, ref_code, balance = user
        
        # Количество рефералов
        c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        referrals_count = c.fetchone()[0]
        
        # Список рефералов
        c.execute("""SELECT u.username, u.first_name, r.date, r.bonus_amount 
                     FROM referrals r
                     JOIN users u ON r.referral_id = u.user_id
                     WHERE r.referrer_id = ?""", (user_id,))
        referrals = c.fetchall()
        
        # Общий заработок
        c.execute("SELECT SUM(bonus_amount) FROM referrals WHERE referrer_id = ?", (user_id,))
        total_earned = c.fetchone()[0] or 0
        
        # Последние транзакции
        c.execute("""SELECT amount, type, description, date 
                     FROM transactions 
                     WHERE user_id = ? 
                     ORDER BY date DESC LIMIT 5""", (user_id,))
        transactions = c.fetchall()
        
        # Последние заявки
        c.execute("""SELECT id, service, budget, created_at, status 
                     FROM requests 
                     WHERE user_id = ? 
                     ORDER BY created_at DESC LIMIT 5""", (user_id,))
        requests = c.fetchall()
        
        conn.close()
        
        # Формируем отчет
        admin_status = "👑 Админ" if is_admin else "👤 Пользователь"
        ban_status = "🔴 Заблокирован" if is_banned else "🟢 Активен"
        
        text = f"""
📋 <b>ПОЛНАЯ СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ</b>

🔹 <b>Основная информация:</b>
🆔 ID: <code>{user_id}</code>
📱 Username: @{username or 'Нет'}
👤 Имя: {first_name} {last_name or ''}
📅 Дата регистрации: {joined_date}
{admin_status} | {ban_status}

🔹 <b>Реферальная система:</b>
🔗 Реф. код: <code>{ref_code}</code>
🔗 Реф. ссылка: https://t.me/{bot.get_me().username}?start={ref_code}
👥 Приглашено рефералов: {referrals_count}
💰 Текущий баланс: {balance}₽
💵 Всего заработано: {total_earned}₽
"""
        
        if referrals:
            text += "\n👥 <b>Список рефералов:</b>\n"
            for ref_user, ref_name, date, bonus in referrals:
                text += f"  • @{ref_user or 'Нет'} | {ref_name or ''} | Бонус: {bonus}₽ | {date[:10]}\n"
        
        if transactions:
            text += "\n💰 <b>Последние транзакции:</b>\n"
            for amount, t_type, desc, date in transactions:
                emoji = "➕" if amount > 0 else "➖"
                text += f"  {emoji} {amount}₽ | {desc} | {date[:16]}\n"
        
        if requests:
            text += "\n📨 <b>Последние заявки:</b>\n"
            for req_id, service, budget, date, status in requests:
                status_emoji = "🆕" if status == 'new' else "✅"
                text += f"  {status_emoji} #{req_id} | {service} | {budget} | {date[:10]}\n"
        
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML')
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def process_make_admin(message):
    try:
        new_admin_id = int(message.text)
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (new_admin_id,))
        conn.commit()
        conn.close()
        
        if new_admin_id not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin_id)
        
        bot.send_message(message.chat.id, 
                        f"✅ Пользователь с ID <code>{new_admin_id}</code> назначен администратором!",
                        parse_mode='HTML')
        
        try:
            bot.send_message(new_admin_id, 
                           "👑 Вас назначили администратором Golden House!\n"
                           "Используйте /admin для доступа к панели управления.")
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID (только цифры)")

def process_remove_admin(message):
    try:
        remove_id = int(message.text)
        
        if remove_id == OWNER_ID:
            bot.send_message(message.chat.id, "❌ Нельзя разжаловать владельца!")
            return
        
        if remove_id in ADMIN_IDS:
            ADMIN_IDS.remove(remove_id)
            
            conn = sqlite3.connect('golden_house.db')
            c = conn.cursor()
            c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (remove_id,))
            conn.commit()
            conn.close()
            
            bot.send_message(message.chat.id, 
                            f"✅ Пользователь с ID <code>{remove_id}</code> разжалован!",
                            parse_mode='HTML')
            
            try:
                bot.send_message(remove_id, "❌ Ваши права администратора были отозваны.")
            except:
                pass
        else:
            bot.send_message(message.chat.id, "❌ Этот пользователь не является администратором")
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID")

def process_add_balance(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Неправильный формат. Используйте: ID СУММА")
            return
        
        user_id = int(parts[0])
        amount = int(parts[1])
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь с таким ID не найден")
            conn.close()
            return
        
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        c.execute("""INSERT INTO transactions (user_id, amount, type, description, date)
                     VALUES (?, ?, ?, ?, ?)""",
                  (user_id, amount, 'admin', f"Начислено администратором", 
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, 
                        f"✅ Пользователю @{user[0]} начислено {amount}₽")
        
        try:
            bot.send_message(user_id, 
                           f"💰 Вам начислено {amount}₽ на баланс!\n"
                           "Проверьте в разделе 👥 Реферальная система")
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректные числа")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def show_stats(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    banned_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM requests")
    total_requests = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM requests WHERE status = 'new'")
    new_requests = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM referrals")
    total_refs = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT referrer_id) FROM referrals")
    active_refs = c.fetchone()[0]
    
    c.execute("SELECT SUM(bonus_amount) FROM referrals")
    total_bonus = c.fetchone()[0] or 0
    
    conn.close()
    
    stats_text = f"""
📊 <b>СТАТИСТИКА GOLDEN HOUSE</b>

👥 <b>Всего пользователей:</b> {total_users}
🔴 <b>Заблокировано:</b> {banned_users}
🟢 <b>Активных:</b> {total_users - banned_users}
📨 <b>Всего заявок:</b> {total_requests}
🆕 <b>Новых заявок:</b> {new_requests}

👥 <b>Реферальная система:</b>
   • Всего рефералов: {total_refs}
   • Активных рефереров: {active_refs}
   • Всего начислено бонусов: {total_bonus}₽
"""
    
    bot.send_message(message.chat.id, stats_text, parse_mode='HTML')

def show_referral_stats(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    c.execute("""SELECT u.user_id, u.username, u.first_name, 
                        COUNT(r.id) as ref_count, SUM(r.bonus_amount) as total_bonus, u.balance
                 FROM users u
                 LEFT JOIN referrals r ON u.user_id = r.referrer_id
                 GROUP BY u.user_id
                 HAVING ref_count > 0
                 ORDER BY total_bonus DESC
                 LIMIT 20""")
    
    top_referrers = c.fetchall()
    conn.close()
    
    if not top_referrers:
        bot.send_message(message.chat.id, "📊 Пока нет рефералов")
        return
    
    text = "🏆 <b>ТОП РЕФЕРЕРОВ ПО БОНУСАМ</b>\n\n"
    for i, (user_id, username, first_name, ref_count, total_bonus, balance) in enumerate(top_referrers, 1):
        name = first_name or username or f"ID{user_id}"
        text += f"{i}. {name}\n"
        text += f"   👥 Рефералов: {ref_count} | 💰 Бонусов: {total_bonus or 0}₽ | 💵 Баланс: {balance}₽\n"
        text += f"   🆔 <code>{user_id}</code>\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def show_referral_details(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    c.execute("""SELECT 
                    r.referrer_id, 
                    u1.username as referrer_username,
                    u1.first_name as referrer_name,
                    r.referral_id,
                    u2.username as referral_username,
                    u2.first_name as referral_name,
                    r.date,
                    r.bonus_amount
                 FROM referrals r
                 JOIN users u1 ON r.referrer_id = u1.user_id
                 JOIN users u2 ON r.referral_id = u2.user_id
                 ORDER BY r.date DESC""")
    
    referrals = c.fetchall()
    conn.close()
    
    if not referrals:
        bot.send_message(message.chat.id, "🔗 Пока нет реферальных связей")
        return
    
    text = "🔗 <b>ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О РЕФЕРАЛАХ</b>\n\n"
    
    current_referrer = None
    for ref in referrals:
        referrer_id, ref_user, ref_name, referral_id, ref_link, ref_link_name, date, bonus = ref
        
        if current_referrer != referrer_id:
            current_referrer = referrer_id
            text += f"\n👤 <b>Реферер:</b> @{ref_user or 'Нет username'} | {ref_name or ''} | ID: <code>{referrer_id}</code>\n"
            text += "└───────────\n"
        
        text += f"   👤 Реферал: @{ref_link or 'Нет username'} | {ref_link_name or ''} | ID: <code>{referral_id}</code>\n"
        text += f"   📅 Дата: {date[:16]}\n"
        text += f"   💰 Бонус: {bonus or 0}₽\n\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')

def show_requests(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("""SELECT id, username, service, sub_service, created_at, status, user_id
                 FROM requests ORDER BY created_at DESC LIMIT 20""")
    requests = c.fetchall()
    conn.close()
    
    if not requests:
        bot.send_message(message.chat.id, "📭 Пока нет заявок")
        return
    
    for req in requests:
        status_emoji = "🆕" if req[5] == 'new' else "✅"
        sub = f" ({req[3]})" if req[3] else ""
        
        text = f"""
{status_emoji} <b>Заявка #{req[0]}</b>
👤 @{req[1]}
📋 {req[2]}{sub}
⏰ {req[4]}
        """
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🗑 Удалить заявку", callback_data=f"delete_request_{req[0]}"))
        
        bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

def show_all_users(message):
    users = get_all_users()
    
    if not users:
        bot.send_message(message.chat.id, "👥 Пользователей пока нет")
        return
    
    text = "👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b>\n\n"
    for user in users:
        user_id, username, first_name, last_name, is_admin, is_banned, balance, ref_code = user
        admin_star = "👑 " if is_admin else ""
        ban_status = "🔴" if is_banned else "🟢"
        text += f"{ban_status} {admin_star}🆔 <code>{user_id}</code>\n"
        text += f"📱 @{username}\n"
        text += f"👤 {first_name} {last_name or ''}\n"
        text += f"🔗 Реф. код: <code>{ref_code}</code>\n"
        text += f"💰 Баланс: {balance}₽\n"
        text += "—" * 20 + "\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')

def process_broadcast(message):
    broadcast_text = message.text
    
    users = get_all_users()
    success = 0
    failed = 0
    
    status_msg = bot.send_message(message.chat.id, 
                                 "📢 Начинаю рассылку... Это может занять некоторое время.")
    
    for user in users:
        user_id = user[0]
        try:
            bot.send_message(user_id, 
                           f"📢 <b>РАССЫЛКА ОТ GOLDEN HOUSE</b>\n\n{broadcast_text}", 
                           parse_mode='HTML')
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    
    bot.edit_message_text(f"✅ Рассылка завершена!\n\n"
                         f"📨 Отправлено: {success}\n"
                         f"❌ Не доставлено: {failed}",
                         message.chat.id,
                         status_msg.message_id)

# Запуск бота
if __name__ == '__main__':
    print("🚀 Запуск бота Golden House...")
    print("⚠️ Токен загружается из переменных окружения")
    init_db()
    print("✅ Бот Golden House запущен!")
    print(f"👑 Владелец: {OWNER_ID}")
    print(f"👥 Админы: {ADMIN_IDS}")
    print("⏰ Ждём сообщения...")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(3)
