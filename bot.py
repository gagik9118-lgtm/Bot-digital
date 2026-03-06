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
TOKEN = os.environ.get('BOT_TOKEN', '8575046727:AAEMIIrHcHrfe5FN6yzaV7gJOYSIi_FMTHY')
OWNER_ID = 8396445302  # Твой ID (владелец)
ADMIN_IDS = [8396445302]  # Список админов (ты и другие)

bot = telebot.TeleBot(TOKEN)
user_data = {}  # Хранилище временных данных пользователей

# ==================== ДЕКОРАТОРЫ ЗАЩИТЫ ====================

# Декоратор для проверки бана (УМНЫЙ - пропускает админов и новые регистрации)
def check_banned(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        
        # Команда /start доступна всем (даже если юзера нет в базе)
        if message.text and message.text.startswith('/start'):
            return func(message, *args, **kwargs)
        
        try:
            conn = sqlite3.connect('golden_house.db')
            c = conn.cursor()
            
            # Проверяем есть ли юзер вообще
            c.execute("SELECT is_banned, is_admin FROM users WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            conn.close()
            
            # Если юзера нет в базе - пропускаем (он сейчас создастся через /start)
            if not result:
                return func(message, *args, **kwargs)
            
            is_banned, is_admin = result
            
            # Админов не баним
            if is_admin == 1:
                return func(message, *args, **kwargs)
            
            # Если забанен - шлем сообщение и НЕ пропускаем
            if is_banned == 1:
                bot.send_message(message.chat.id, 
                               "⛔ Вы были заблокированы администрацией.\n"
                               "По вопросам разблокировки: @Opps911")
                return None
                
            return func(message, *args, **kwargs)
        except Exception as e:
            print(f"Ошибка в check_banned: {e}")
            return func(message, *args, **kwargs)  # В случае ошибки пропускаем
    return wrapper

# Декоратор для проверки бана в callback (УМНЫЙ)
def check_banned_callback(func):
    @wraps(func)
    def wrapper(call, *args, **kwargs):
        user_id = call.from_user.id
        
        try:
            conn = sqlite3.connect('golden_house.db')
            c = conn.cursor()
            
            c.execute("SELECT is_banned, is_admin FROM users WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            conn.close()
            
            if not result:
                return func(call, *args, **kwargs)
            
            is_banned, is_admin = result
            
            if is_admin == 1:
                return func(call, *args, **kwargs)
            
            if is_banned == 1:
                bot.answer_callback_query(call.id, "⛔ Вы заблокированы")
                return None
                
            return func(call, *args, **kwargs)
        except Exception as e:
            print(f"Ошибка в check_banned_callback: {e}")
            return func(call, *args, **kwargs)
    return wrapper

# ==================== БАЗА ДАННЫХ ====================

def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        # Таблица пользователей
        c.execute('''CREATE TABLE IF NOT EXISTS users
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
        c.execute('''CREATE TABLE IF NOT EXISTS banned_users
                     (user_id INTEGER PRIMARY KEY,
                      banned_by INTEGER,
                      ban_date TEXT,
                      reason TEXT DEFAULT NULL)''')
        
        # Таблица заявок
        c.execute('''CREATE TABLE IF NOT EXISTS requests
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
        c.execute('''CREATE TABLE IF NOT EXISTS referrals
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      referrer_id INTEGER,
                      referral_id INTEGER,
                      date TEXT,
                      bonus_amount INTEGER DEFAULT 0,
                      bonus_paid INTEGER DEFAULT 0)''')
        
        # Таблица транзакций
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      amount INTEGER,
                      type TEXT,
                      description TEXT,
                      date TEXT)''')
        
        conn.commit()
        conn.close()
        print("✅ База данных проверена/создана")
        
        # Проверяем, есть ли владелец в базе
        check_and_add_owner()
        
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")

def check_and_add_owner():
    """Проверяет и добавляет владельца в базу если его нет"""
    try:
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        # Проверяем, есть ли владелец
        c.execute("SELECT * FROM users WHERE user_id = ?", (OWNER_ID,))
        owner = c.fetchone()
        
        if not owner:
            # Добавляем владельца
            referral_code = generate_referral_code(OWNER_ID)
            joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            c.execute("""INSERT INTO users 
                         (user_id, username, first_name, last_name, joined_date, referral_code, is_admin, is_banned, balance) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (OWNER_ID, "Opps911", "Owner", "", joined_date, referral_code, 1, 0, 0))
            print("✅ Владелец добавлен в базу данных")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка при проверке владельца: {e}")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def generate_referral_code(user_id):
    """Генерация уникального реферального кода"""
    return f"GOLD{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

def save_user(message, referrer_code=None):
    """Сохраняет нового пользователя в базу данных"""
    try:
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        user_id = message.from_user.id
        username = message.from_user.username or "Нет username"
        first_name = message.from_user.first_name or ""
        last_name = message.from_user.last_name or ""
        joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Проверяем, есть ли уже пользователь
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            conn.close()
            return
        
        referral_code = generate_referral_code(user_id)
        referrer_id = None
        
        # Если есть реферальный код
        if referrer_code:
            c.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
            result = c.fetchone()
            if result:
                referrer_id = result[0]
                # Записываем реферала
                c.execute("INSERT INTO referrals (referrer_id, referral_id, date) VALUES (?, ?, ?)",
                         (referrer_id, user_id, joined_date))
        
        # Определяем, админ ли этот пользователь
        is_admin = 1 if user_id == OWNER_ID or user_id in ADMIN_IDS else 0
        
        c.execute("""INSERT INTO users 
                     (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code, is_admin, is_banned, balance) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code, is_admin, 0, 0))
        
        # Если это владелец и его нет в ADMIN_IDS - добавляем
        if user_id == OWNER_ID and user_id not in ADMIN_IDS:
            ADMIN_IDS.append(user_id)
        
        conn.commit()
        conn.close()
        print(f"✅ Новый пользователь сохранен: {user_id} (@{username})")
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении пользователя: {e}")

def get_all_users():
    """Получает всех пользователей из базы"""
    try:
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name, last_name, is_admin, is_banned, balance, referral_code FROM users ORDER BY user_id")
        users = c.fetchall()
        conn.close()
        return users
    except Exception as e:
        print(f"❌ Ошибка при получении пользователей: {e}")
        return []

def is_user_banned(user_id):
    """Проверяет, забанен ли пользователь"""
    try:
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 1
    except:
        return False

# ==================== МЕНЮ ====================

def main_menu():
    """Главное меню с кнопками"""
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

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    try:
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
    except Exception as e:
        print(f"❌ Ошибка в /start: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте еще раз.", reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Админ-панель"""
    try:
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
    except Exception as e:
        print(f"❌ Ошибка в /admin: {e}")
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")

# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================

@bot.message_handler(func=lambda message: True)
@check_banned
def handle_all_messages(message):
    """Обработчик всех текстовых сообщений"""
    try:
        text = message.text
        
        # Обработка отзыва
        if text == "⭐ Оставить отзыв":
            bot.send_message(message.chat.id, 
                            "📝 Оставьте свой отзыв в нашем специальном боте:\n\n"
                            "👉 @GoldenHouseOtzovBot\n\n"
                            "Ваше мнение очень важно для нас! 🌟",
                            reply_markup=main_menu())
        
        # Реферальная система
        elif text == "👥 Реферальная система":
            referral_system(message)
        
        # Дизайн
        elif text == "🎨 Дизайн":
            design_menu(message)
        
        # Консультация
        elif text == "💼 Консультация (2.000₽/час)":
            handle_consultation(message)
        
        # Остальные услуги
        elif text in [
            "💻 Web-разработка",
            "📈 SEO-продвижение",
            "🎯 Таргет-реклама",
            "🤖 Telegram боты",
            "🔍 Аудит сайта"
        ]:
            handle_service(message)
        else:
            # Если сообщение не подходит ни под одну категорию
            bot.send_message(message.chat.id, "Используйте кнопки меню 👇", reply_markup=main_menu())
            
    except Exception as e:
        print(f"❌ Ошибка в handle_all_messages: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте еще раз.", reply_markup=main_menu())

# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

def referral_system(message):
    """Показывает информацию о реферальной системе"""
    try:
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
        
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"
        
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
    except Exception as e:
        print(f"❌ Ошибка в referral_system: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте позже.")

# ==================== ДИЗАЙН ====================

def design_menu(message):
    """Меню выбора дизайна"""
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

# ==================== КОНСУЛЬТАЦИЯ ====================

def handle_consultation(message):
    """Обработка запроса на консультацию"""
    try:
        user_id = message.from_user.id
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
        user_data_db = c.fetchone()
        conn.close()
        
        username = user_data_db[0] if user_data_db else "Нет username"
        first_name = user_data_db[1] if user_data_db else ""
        last_name = user_data_db[2] if user_data_db else ""
        
        # Отправляем админам
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
    except Exception as e:
        print(f"❌ Ошибка в handle_consultation: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте позже.")

# ==================== ОБРАБОТКА УСЛУГ ====================

def handle_service(message):
    """Начало обработки заявки на услугу"""
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

def process_business(message):
    """Обработка описания бизнеса"""
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
    """Обработка описания задачи"""
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
    """Обработка дедлайна"""
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
    """Финальная обработка заявки и сохранение в БД"""
    try:
        user_id = message.from_user.id
        if user_id not in user_data:
            bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
            return
        
        user_data[user_id]['budget'] = message.text
        
        # Сохраняем заявку
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
        
        # Начисляем бонус рефереру (10% от бюджета)
        try:
            budget_amount = int(''.join(filter(str.isdigit, user_data[user_id]['budget'])))
            if budget_amount > 0:
                bonus = int(budget_amount * 0.1)
                
                c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
                referrer = c.fetchone()
                
                if referrer and referrer[0]:
                    referrer_id = referrer[0]
                    # Обновляем баланс реферера
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, referrer_id))
                    
                    # Обновляем запись в рефералах
                    c.execute("""UPDATE referrals SET bonus_amount = ? 
                                WHERE referrer_id = ? AND referral_id = ?""", 
                             (bonus, referrer_id, user_id))
                    
                    # Записываем транзакцию
                    c.execute("""INSERT INTO transactions (user_id, amount, type, description, date)
                                 VALUES (?, ?, ?, ?, ?)""",
                              (referrer_id, bonus, 'bonus', 
                               f"Бонус за заказ #{request_id} от @{username}", 
                               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
        except Exception as e:
            print(f"Ошибка при начислении бонуса: {e}")
        
        conn.close()
        
        # Отправляем админам
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
            except Exception as e:
                print(f"Ошибка при отправке админу {admin_id}: {e}")
        
        bot.send_message(message.chat.id, 
                        "✅ Ваш отклик отправлен администрации на проверку!\n"
                        "Мы свяжемся с вами в ближайшее время.\n\n"
                        "Спасибо, что выбрали Golden House! 🌟",
                        reply_markup=main_menu())
        
        # Очищаем временные данные
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        print(f"❌ Ошибка в process_budget: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при отправке заявки. Попробуйте позже.", reply_markup=main_menu())

# ==================== ОБРАБОТЧИК КОЛЛБЭКОВ ====================

@bot.callback_query_handler(func=lambda call: True)
@check_banned_callback
def handle_callbacks(call):
    """Обработчик всех инлайн кнопок"""
    try:
        user_id = call.from_user.id
        
        # Админские коллбэки
        if user_id in ADMIN_IDS:
            if call.data == "make_admin":
                msg = bot.send_message(call.message.chat.id, 
                                      "🔑 Напишите ID пользователя, чтобы назначить его администратором:")
                bot.register_next_step_handler(msg, process_make_admin)
                bot.answer_callback_query(call.id)
                
            elif call.data == "remove_admin":
                if user_id != OWNER_ID:
                    bot.answer_callback_query(call.id, "❌ Только владелец может разжаловать админов")
                    return
                
                # Показываем список админов
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
                    bot.answer_callback_query(call.id)
                    return
                
                text = "📋 <b>Администраторы (кроме владельца):</b>\n\n" + "\n".join(admins_list) + \
                       "\n\n🔑 Введите ID пользователя, которого нужно разжаловать:"
                
                msg = bot.send_message(call.message.chat.id, text, parse_mode='HTML')
                bot.register_next_step_handler(msg, process_remove_admin)
                bot.answer_callback_query(call.id)
                
            elif call.data == "add_balance":
                msg = bot.send_message(call.message.chat.id, 
                                      "💰 Введите ID пользователя и сумму через пробел\n"
                                      "Например: 123456789 1000")
                bot.register_next_step_handler(msg, process_add_balance)
                bot.answer_callback_query(call.id)
                
            elif call.data == "stats":
                show_stats(call.message)
                bot.answer_callback_query(call.id)
                
            elif call.data == "requests":
                show_requests(call.message)
                bot.answer_callback_query(call.id)
                
            elif call.data == "broadcast":
                msg = bot.send_message(call.message.chat.id, 
                                      "📢 Введите сообщение для рассылки всем пользователям:")
                bot.register_next_step_handler(msg, process_broadcast)
                bot.answer_callback_query(call.id)
                
            elif call.data == "all_users":
                show_all_users(call.message)
                bot.answer_callback_query(call.id)
                
            elif call.data == "referral_stats":
                show_referral_stats(call.message)
                bot.answer_callback_query(call.id)
                
            elif call.data == "referral_details":
                show_referral_details(call.message)
                bot.answer_callback_query(call.id)
                
            elif call.data == "ban_user":
                msg = bot.send_message(call.message.chat.id, 
                                      "🔨 Введите ID пользователя для блокировки:")
                bot.register_next_step_handler(msg, process_ban_user)
                bot.answer_callback_query(call.id)
                
            elif call.data == "unban_user":
                msg = bot.send_message(call.message.chat.id, 
                                      "🔓 Введите ID пользователя для разблокировки:")
                bot.register_next_step_handler(msg, process_unban_user)
                bot.answer_callback_query(call.id)
                
            elif call.data == "user_stats":
                msg = bot.send_message(call.message.chat.id, 
                                      "📋 Введите ID пользователя для просмотра статистики:")
                bot.register_next_step_handler(msg, process_user_stats)
                bot.answer_callback_query(call.id)
                
            elif call.data.startswith("delete_request_"):
                delete_request(call)
                
            else:
                bot.answer_callback_query(call.id, "Неизвестная команда")
        
        # Пользовательские коллбэки
        else:
            if call.data.startswith("design_") and call.data != "cancel_design":
                handle_design_callback(call)
            elif call.data.startswith("cancel_"):
                cancel_order(call)
            elif call.data == "cancel_design":
                cancel_design(call)
            elif call.data == "back_to_main":
                back_to_main(call)
            else:
                bot.answer_callback_query(call.id, "Неизвестная команда")
                
    except Exception as e:
        print(f"❌ Ошибка в handle_callbacks: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

# ==================== ОБРАБОТКА ДИЗАЙНА (КОЛЛБЭКИ) ====================

def handle_design_callback(call):
    """Обработка выбора дизайна"""
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
    
    bot.answer_callback_query(call.id)
    bot.register_next_step_handler(call.message, process_business)

def cancel_order(call):
    """Отмена заказа"""
    user_id = int(call.data.split("_")[1])
    
    if user_id in user_data:
        del user_data[user_id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Заказ отменён. Возвращайтесь, когда будете готовы!", 
                    reply_markup=main_menu())
    bot.answer_callback_query(call.id)

def cancel_design(call):
    """Отмена выбора дизайна"""
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Выбор дизайна отменён.", reply_markup=main_menu())
    bot.answer_callback_query(call.id)

def back_to_main(call):
    """Возврат в главное меню"""
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=main_menu())
    bot.answer_callback_query(call.id)

def delete_request(call):
    """Удаление заявки админом"""
    try:
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
    except Exception as e:
        print(f"Ошибка при удалении заявки: {e}")
        bot.answer_callback_query(call.id, "Ошибка при удалении")

# ==================== АДМИН-ФУНКЦИИ ====================

def process_make_admin(message):
    """Назначение администратора"""
    try:
        new_admin_id = int(message.text.strip())
        
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
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def process_remove_admin(message):
    """Снятие администратора"""
    try:
        remove_id = int(message.text.strip())
        
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
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def process_add_balance(message):
    """Начисление баланса пользователю"""
    try:
        parts = message.text.strip().split()
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

def process_ban_user(message):
    """Блокировка пользователя"""
    try:
        user_id = int(message.text.strip())
        
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
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def process_unban_user(message):
    """Разблокировка пользователя"""
    try:
        user_id = int(message.text.strip())
        
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
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def process_user_stats(message):
    """Полная статистика пользователя"""
    try:
        user_id = int(message.text.strip())
        
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
        
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start={ref_code}"
        
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
🔗 Реф. ссылка: {referral_link}
👥 Приглашено рефералов: {referrals_count}
💰 Текущий баланс: {balance}₽
💵 Всего заработано: {total_earned}₽
"""
        
        if referrals:
            text += "\n👥 <b>Список рефералов:</b>\n"
            for ref_user, ref_name, date, bonus in referrals[:5]:  # Показываем только первых 5
                text += f"  • @{ref_user or 'Нет'} | {ref_name or ''} | Бонус: {bonus}₽ | {date[:10]}\n"
            if len(referrals) > 5:
                text += f"  • ... и еще {len(referrals) - 5}\n"
        
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
        
        # Разбиваем на части если слишком длинное
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML')
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# ==================== СТАТИСТИКА ====================

def show_stats(message):
    """Показывает общую статистику бота"""
    try:
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        banned_users = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM requests")
        total_requests = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM requests WHERE status = 'new'")
        new_requests = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM referrals")
        total_refs = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(DISTINCT referrer_id) FROM referrals")
        active_refs = c.fetchone()[0] or 0
        
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
    except Exception as e:
        print(f"Ошибка в show_stats: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при получении статистики")

def show_referral_stats(message):
    """Топ рефереров"""
    try:
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        c.execute("""SELECT u.user_id, u.username, u.first_name, 
                            COUNT(r.id) as ref_count, 
                            COALESCE(SUM(r.bonus_amount), 0) as total_bonus, 
                            u.balance
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
            text += f"   👥 Рефералов: {ref_count} | 💰 Бонусов: {total_bonus}₽ | 💵 Баланс: {balance}₽\n"
            text += f"   🆔 <code>{user_id}</code>\n\n"
        
        bot.send_message(message.chat.id, text, parse_mode='HTML')
    except Exception as e:
        print(f"Ошибка в show_referral_stats: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при получении статистики")

def show_referral_details(message):
    """Детальная информация о рефералах"""
    try:
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
                     ORDER BY r.date DESC
                     LIMIT 50""")  # Ограничиваем для производительности
        
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
    except Exception as e:
        print(f"Ошибка в show_referral_details: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при получении данных")

def show_requests(message):
    """Показывает последние заявки"""
    try:
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
    except Exception as e:
        print(f"Ошибка в show_requests: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при получении заявок")

def show_all_users(message):
    """Показывает всех пользователей"""
    try:
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
    except Exception as e:
        print(f"Ошибка в show_all_users: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при получении списка пользователей")

def process_broadcast(message):
    """Рассылка сообщений всем пользователям"""
    try:
        broadcast_text = message.text
        
        users = get_all_users()
        success = 0
        failed = 0
        
        status_msg = bot.send_message(message.chat.id, 
                                     "📢 Начинаю рассылку... Это может занять некоторое время.")
        
        for user in users:
            user_id = user[0]
            # Не отправляем забаненным
            if user[5] == 1:  # is_banned
                continue
                
            try:
                bot.send_message(user_id, 
                               f"📢 <b>РАССЫЛКА ОТ GOLDEN HOUSE</b>\n\n{broadcast_text}", 
                               parse_mode='HTML')
                success += 1
                time.sleep(0.05)  # Небольшая задержка чтобы не флудить
            except Exception as e:
                failed += 1
                print(f"Ошибка отправки пользователю {user_id}: {e}")
        
        bot.edit_message_text(f"✅ Рассылка завершена!\n\n"
                             f"📨 Отправлено: {success}\n"
                             f"❌ Не доставлено: {failed}",
                             message.chat.id,
                             status_msg.message_id)
    except Exception as e:
        print(f"Ошибка в process_broadcast: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при рассылке: {e}")

# ==================== ЗАПУСК БОТА ====================

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 ЗАПУСК БОТА GOLDEN HOUSE")
    print("=" * 50)
    
    # Проверка токена
    if TOKEN == 'YOUR_TOKEN_HERE' or not TOKEN:
        print("⚠️ ВНИМАНИЕ: Токен не установлен!")
        print("Установите токен через переменную окружения BOT_TOKEN")
        print("Или вставьте токен напрямую в переменную TOKEN")
    else:
        print("✅ Токен загружен")
    
    # Инициализация БД
    init_db()
    
    # Информация о запуске
    print(f"👑 Владелец: {OWNER_ID}")
    print(f"👥 Админы: {ADMIN_IDS}")
    print(f"🤖 Бот: @{bot.get_me().username}")
    print("⏰ Ожидание сообщений...")
    print("=" * 50)
    
    # Бесконечный цикл с перезапуском при ошибках
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"❌ Ошибка в основном цикле: {e}")
            print("🔄 Перезапуск через 3 секунды...")
            time.sleep(3)
