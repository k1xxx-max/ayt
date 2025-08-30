import logging
import random
import asyncio
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ===== НАСТРОЙКИ =====
TOKEN =  "88268250061:AAEAVFkU47ISRsKYpJ4IjKlpcrGEXyJxd3Y"  # Убедитесь, что токен правильный!
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ХРАНИЛИЩЕ ДАННЫХ =====
user_data = {}
used_promocodes = set()
promocode_activations = {}
last_message_ids = {}
last_user_message_ids = {}

# ===== ПРОМОКОДЫ =====
promocodes = {
    "BONUS100": {"value": 100, "max_activations": 30},
    "FREE250": {"value": 250, "max_activations": 30},
    "WELCOME100": {"value": 100, "max_activations": 30},
    "GOLD250": {"value": 250, "max_activations": 30},
    "HACKER100": {"value": 100, "max_activations": 30},
    "SHADOW250": {"value": 250, "max_activations": 30},
    "STANDOFF100": {"value": 100, "max_activations": 30},
    "PRO250": {"value": 250, "max_activations": 30},
    "MASTER100": {"value": 100, "max_activations": 30},
    "ELITE250": {"value": 250, "max_activations": 30}
}

# Инициализация счетчиков активаций
for code in promocodes:
    promocode_activations[code] = 0

# ===== КЛАВИАТУРЫ =====
main_keyboard = ReplyKeyboardMarkup([
    ['🚀 Начать взлом', '💰 Баланс'],
    ['👤 Профиль', '❓ Помощь']
], resize_keyboard=True, input_field_placeholder='Выберите действие...')

profile_keyboard = ReplyKeyboardMarkup([
    ['💸 Вывод средств', '🎁 Промокод'],
    ['🔙 На главную']
], resize_keyboard=True)

back_keyboard = ReplyKeyboardMarkup([
    ['🔙 Назад']
], resize_keyboard=True)

# ===== СООБЩЕНИЯ =====
WELCOME_MESSAGE = """
🖥️ <b>ShadowTerminal v5.0</b>

🌐 <i>Подключение к серверам Standoff 2...</i> <code>УСТАНОВЛЕНО</code>
🔒 <i>Статус безопасности:</i> <code>АКТИВЕН</code>
📊 <i>Текущий баланс:</i> <b>{} G</b>

Выберите действие:
"""

FAILURE_MESSAGES = [
    "❌ Аккаунт {} не содержит активов",
    "❌ На балансе аккаунта {} не было голды",
    "⚠️ Обнаружена система защиты! Отмена операции...",
    "🔒 Активирована блокировка! Прерываю связь...",
    "🌐 Потеряно соединение с сервером...",
    "🛡️ Система безопасности обнаружила подозрительную активность...",
    "🔍 Аккаунт защищен усиленной аутентификацией...",
    "⏰ Превышено время ожидания ответа от сервера..."
]

HACKING_STEPS = [
    "📡 Устанавливаю связь с серверами...",
    "🔍 Сканирую базу данных...",
    "🎯 Обнаружен аккаунт: {}",
    "⚡ Анализ уязвимостей...",
    "🔓 Подбор учетных данных...",
    "🌐 Обход системы обнаружения...",
    "📊 Перехват сессии...",
    "🔓 Получение доступа...",
    "💾 Анализ содержимого...",
    "📁 Извлечение ресурсов...",
    "🗂️ Упаковка данных..."
]

# ===== САМОПИНГ ДЛЯ RENDER =====
async def self_ping():
    """Функция для самопинга, чтобы приложение не засыпало на Render"""
    while True:
        try:
            # Получаем URL приложения из переменных окружения Render
            render_url = "https://your-bot-name.onrender.com"  # Замените на ваш URL
            
            # Используем синхронный requests в отдельном потоке
            response = requests.get(render_url, timeout=10)
            if response.status_code == 200:
                logger.info("Самопинг успешен")
            else:
                logger.warning(f"Самопинг неуспешен: {response.status_code}")
        except Exception as e:
            logger.error(f"Ошибка самопинга: {e}")
        
        # Пингуем каждые 10 минут (600 секунд)
        await asyncio.sleep(600)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def get_user_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {'gold': 0}
    return user_data[user_id]

def generate_account_name():
    return f"user_{random.randint(10000, 99999)}"

def format_gold(amount):
    return f"{amount:,} G".replace(",", " ")

async def delete_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет предыдущее сообщение бота и пользователя"""
    user_id = update.effective_user.id
    
    # Удаляем предыдущее сообщение бота
    if user_id in last_message_ids:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=last_message_ids[user_id])
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение бота: {e}")
        finally:
            del last_message_ids[user_id]
    
    # Удаляем предыдущее сообщение пользователя (команду)
    if user_id in last_user_message_ids:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=last_user_message_ids[user_id])
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")
        finally:
            del last_user_message_ids[user_id]
    
    # Сохраняем ID текущего сообщения пользователя для будущего удаления
    last_user_message_ids[user_id] = update.message.message_id

async def send_and_remember_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text, 
                                   parse_mode=None, reply_markup=None):
    """Отправляет сообщение и запоминает его ID для последующего удаления"""
    # Сначала удаляем предыдущие сообщения
    await delete_previous_messages(update, context)
    
    # Отправляем новое сообщение
    message = await update.message.reply_text(
        text, 
        parse_mode=parse_mode, 
        reply_markup=reply_markup
    )
    
    # Запоминаем ID нового сообщения
    last_message_ids[update.effective_user.id] = message.message_id
    return message

# ===== ОСНОВНЫЕ ФУНКЦИИ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    await send_and_remember_message(
        update, context,
        WELCOME_MESSAGE.format(user['gold']),
        parse_mode='HTML',
        reply_markup=main_keyboard
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    status = "✅ Доступен вывод средств" if user['gold'] >= 500 else f"❌ Для вывода необходимо: {500 - user['gold']} G"
    
    await send_and_remember_message(
        update, context,
        f"💳 <b>Текущий баланс:</b>\n{format_gold(user['gold'])}\n\n{status}",
        parse_mode='HTML',
        reply_markup=main_keyboard
    )

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    activated_count = len([p for p in used_promocodes if str(user_id) in p])
    
    await send_and_remember_message(
        update, context,
        f"👤 <b>Ваш профиль</b>\n\n"
        f"💳 Баланс: {format_gold(user['gold'])}\n"
        f"🎁 Активировано промокодов: {activated_count}\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=profile_keyboard
    )

async def hack_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Для взлома не удаляем предыдущие сообщения
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    account_name = generate_account_name()
    
    # Отправляем начальное сообщение
    msg = await update.message.reply_text(
        "🔄 <b>Подготовка к взлому...</b>\n"
        "▰▱▱▱▱▱▱▱ 10%",
        parse_mode='HTML'
    )
    
    # Анимация взлома
    steps = HACKING_STEPS.copy()
    steps[2] = steps[2].format(account_name)  # Вставляем имя аккаунта
    
    # С шансом 10% добавляем этап двухфакторной аутентификации
    if random.random() <= 0.1:
        steps.insert(6, "💾 Обход двухфакторной аутентификации...")
    
    progress = 10
    for i, step in enumerate(steps):
        await asyncio.sleep(random.uniform(1.0, 2.0))
        progress = min(90, progress + 8)
        await msg.edit_text(
            f"<code>{step}</code>\n\n"
            f"▰{'▰' * (i+1)}{'▱' * (len(steps)-i-1)} {progress}%",
            parse_mode='HTML'
        )
    
    # Финальная задержка
    await asyncio.sleep(2)
    
    # Результат взлома
    if random.random() <= 0.3:  # 30% успеха
        gold_found = random.randint(10, 100)
        
        # Проверяем, нужно ли дать бонус (баланс >= 400)
        if user['gold'] >= 400:
            gold_found = random.randint(5000, 15000)
        
        # Применяем комиссию 10%
        commission = int(gold_found * 0.1)
        net_gold = gold_found - commission
        user['gold'] += net_gold
        
        await msg.edit_text(
            f"✅ <b>Взлом успешен!</b>\n\n"
            f"📦 Извлечено: {format_gold(gold_found)}\n"
            f"📉 Комиссия системы (10%): {format_gold(commission)}\n"
            f"💰 Чистый доход: {format_gold(net_gold)}\n\n"
            f"💳 Текущий баланс: {format_gold(user['gold'])}\n\n"
            f"🌐 <i>Стирание логов... ЗАВЕРШЕНО</i>\n"
            f"🔒 <i>Восстановление защиты... ВЫПОЛНЕНО</i>",
            parse_mode='HTML'
        )
    else:
        failure_msg = random.choice(FAILURE_MESSAGES)
        if "{}" in failure_msg:
            failure_msg = failure_msg.format(account_name)
            
        await msg.edit_text(
            f"❌ <b>Взлом не удался</b>\n\n"
            f"{failure_msg}\n\n"
            f"💳 Текущий баланс: {format_gold(user['gold'])}",
            parse_mode='HTML'
        )

async def withdraw_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    if user['gold'] < 500:
        await send_and_remember_message(
            update, context,
            f"❌ <b>Недостаточно средств</b>\n\n"
            f"Минимальная сумма для вывода: 500 G\n"
            f"Ваш текущий баланс: {format_gold(user['gold'])}\n\n"
            f"Продолжайте взламывать аккаунты для накопления средств",
            parse_mode='HTML',
            reply_markup=profile_keyboard
        )
        return
    
    # Генерация случайного ID транзакции
    transaction_id = f"TX{random.randint(100000, 999999)}"
    
    await send_and_remember_message(
        update, context,
        f"📤 <b>Инициирован вывод средств</b>\n\n"
        f"💳 Сумма: {format_gold(user['gold'])}\n"
        f"📋 ID транзакции: <code>{transaction_id}</code>\n\n"
        f"💸 <b>Для вывода необходимо оплатить комиссию 125 G</b>\n"
        f"   - Аренда защищенных прокси-серверов\n"
        f"   - Обновление инструментов взлома\n"
        f"   - Обеспечение анонимности операций\n\n"
        f"💬 <b>Для оплаты напишите:</b> @ImZagen\n\n"
        f"⏱️ Обработка после оплаты: до 24 часов",
        parse_mode='HTML',
        reply_markup=profile_keyboard
    )

async def activate_promocode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_and_remember_message(
        update, context,
        "🎁 <b>Активация промокода</b>\n\n"
        "Введите промокод для активации:",
        parse_mode='HTML',
        reply_markup=back_keyboard
    )

async def process_promocode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    promocode = update.message.text.upper()
    user_key = f"{user_id}_{promocode}"
    
    # Проверяем, использовал ли пользователь уже этот промокод
    if user_key in used_promocodes:
        await send_and_remember_message(
            update, context,
            f"❌ Вы уже использовали промокод {promocode}!",
            reply_markup=profile_keyboard
        )
        return
    
    # Проверяем, существует ли промокод
    if promocode in promocodes:
        # Проверяем, не превышено ли максимальное количество активаций
        if promocode_activations[promocode] >= promocodes[promocode]["max_activations"]:
            await send_and_remember_message(
                update, context,
                f"❌ Промокод {promocode} больше не активен!",
                reply_markup=profile_keyboard
            )
            return
            
        # Начисляем бонус
        bonus = promocodes[promocode]["value"]
        user['gold'] += bonus
        
        # Отмечаем промокод как использованный для этого пользователя
        used_promocodes.add(user_key)
        
        # Увеличиваем счетчик активаций промокода
        promocode_activations[promocode] += 1
        
        await send_and_remember_message(
            update, context,
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"🎁 Получено: {format_gold(bonus)}\n"
            f"💳 Текущий баланс: {format_gold(user['gold'])}",
            parse_mode='HTML',
            reply_markup=profile_keyboard
        )
    else:
        await send_and_remember_message(
            update, context,
            "❌ Неверный промокод!",
            reply_markup=profile_keyboard
        )

async def how_it_works(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🔒 <b>Как работает система</b>\n\n"
        "ShadowTerminal использует уязвимости в протоколе аутентификации Standoff 2 "
        "для получения доступа к заброшенным аккаунтам.\n\n"
        "<b>Процесс взлома:</b>\n"
        "1. Сканирование базы данных на наличие неактивных аккаунтов\n"
        "2. Обход базовой защиты через уязвимость Zero-Day\n"
        "3. Подбор учетных данных с использованием модифицированного алгоритма Bruteforce\n"
        "4. Извлечение цифровых активов с последующим восстановлением защиты аккаунта\n\n"
        "<b>Комиссия системы:</b>\n"
        "• С каждой успешной операции взимается 10% комиссия\n"
        "• Комиссия идет на поддержание инфраструктуры и обновление инструментов\n\n"
        "<b>Вывод средств:</b>\n"
        "• Минимальная сумма вывода: 500 G\n"
        "• Комиссия за вывод: 125 G (оплачивается отдельно @ImZagen)\n"
        "• Обработка транзакций: до 24 часов\n\n"
        "<b>Промокоды:</b>\n"
        "• Доступны промокоды на 100 G и 250 G\n"
        "• Каждый промокод можно использовать только один раз\n"
        "• Каждый промокод имеет ограниченное количество активаций\n\n"
        "<b>Примечание:</b> Система автоматически маскирует IP-адрес и стирает логи после каждой операции."
    )
    await send_and_remember_message(
        update, context,
        help_text, 
        parse_mode='HTML', 
        reply_markup=main_keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    text = update.message.text
    
    if text == '🚀 Начать взлом':
        await hack_account(update, context)
    elif text == '💰 Баланс':
        await show_balance(update, context)
    elif text == '👤 Профиль':
        await show_profile(update, context)
    elif text == '❓ Помощь':
        await how_it_works(update, context)
    elif text == '💸 Вывод средств':
        await withdraw_funds(update, context)
    elif text == '🎁 Промокод':
        await activate_promocode(update, context)
    elif text == '🔙 На главную' or text == '🔙 Назад':
        await start(update, context)
    elif text.upper() in promocodes:
        await process_promocode(update, context)
    else:
        await send_and_remember_message(
            update, context,
            "Используйте кнопки меню для навигации",
            reply_markup=main_keyboard
        )

def main():
    # Создаем новый цикл событий
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем самопинг в фоновом режиме
    loop.create_task(self_ping())
    
    logger.info("Бот запущен...")
    
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    finally:
        loop.close()

if __name__ == "__main__":
    main()
