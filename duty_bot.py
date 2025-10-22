#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import random
import json
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from flask import Flask, request

# --- НАСТРОЙКИ ---
TOKEN = "8347643283:AAFKD80QRaKeU_g0A1Eav7UVVKHieOpUIKA"
ADMIN_USERNAMES = ["phsquadd", "saduevvv18"]
WEBHOOK_URL = "https://nojack.onrender.com"

# --- КОНФИГУРАЦИЯ ФАЙЛОВ И ДАННЫХ ---
DATA_DIR = "data"
MASTER_LIST_FILE = os.path.join(DATA_DIR, "master_list.json")
CURRENT_POOL_FILE = os.path.join(DATA_DIR, "current_pool.json")
LAST_WINNERS_FILE = os.path.join(DATA_DIR, "last_winners.json")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Инициализация бота и веб-сервера ---
# Убираем .build() отсюда, так как будем использовать контекстный менеджер
application_builder = Application.builder().token(TOKEN)
app = Flask(__name__)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def setup_files():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(MASTER_LIST_FILE):
        save_data([], MASTER_LIST_FILE)
        logger.info(f"Создан пустой мастер-файл: {MASTER_LIST_FILE}")

def load_data(file_path):
    if not os.path.exists(file_path): return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_data(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ОБРАБОТЧИКИ КОМАНД ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    message = (
        f"👋 Привет, {user_name}!\n\n"
        "Я бот-рулетка для определения дежурных. Вот что я умею:\n\n"
        "**Для всех:**\n"
        "`/list` - Показать, кто еще остался в списке.\n"
        "`/today` - Показать, кто дежурит сегодня.\n\n"
        "**Только для администраторов:**\n"
        "`/go` - Запустить рулетку.\n"
        "`/reset` - Начать новый цикл дежурств.\n"
        "`/manage` - Управление списком пользователей.\n"
        "`/webhook_info` - Проверить статус вебхука."
    )
    await update.message.reply_text(message)

async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав для запуска рулетки.")
        return
    pool = load_data(CURRENT_POOL_FILE)
    if not pool:
        await update.message.reply_text("🎲 Пул дежурных пуст! Администратору нужно запустить новый цикл командой `/reset`.")
        return
    if len(pool) < 2:
        winner = pool[0] if pool else None
        if not winner:
            await update.message.reply_text("🎲 В пуле никого нет для выбора последнего героя.")
            return
        save_data([], CURRENT_POOL_FILE)
        save_data([winner], LAST_WINNERS_FILE)
        message = (f"🏆 Остался последний герой: {winner['name']} ({winner['username']})!\n\n"
                   "Все отдежурили. Цикл завершен. Для начала нового введите `/reset`.")
        await update.message.reply_text(message)
        return
    winners = random.sample(pool, 2)
    new_pool = [p for p in pool if p not in winners]
    save_data(new_pool, CURRENT_POOL_FILE)
    save_data(winners, LAST_WINNERS_FILE)
    message = (f"✨ Рулетка запущена! Сегодня Хранители Порядка:\n\n"
               f"👤 {winners[0]['name']} ({winners[0]['username']})\n"
               f"👤 {winners[1]['name']} ({winners[1]['username']})\n\n"
               f"В рулетке осталось {len(new_pool)} участников.")
    await update.message.reply_text(message)

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = load_data(CURRENT_POOL_FILE)
    if not pool:
        await update.message.reply_text("🎲 Пул дежурных пуст. Никого не осталось.")
        return
    participant_lines = [f"👤 {p['name']} ({p['username']})" for p in pool]
    message = "👥 В рулетке остались:\n\n" + "\n".join(participant_lines)
    await update.message.reply_text(message)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды.")
        return
    master_list = load_data(MASTER_LIST_FILE)
    save_data(master_list, CURRENT_POOL_FILE)
    save_data([], LAST_WINNERS_FILE)
    message = f"✅ Новый цикл запущен! В рулетку снова загружено {len(master_list)} участников."
    await update.message.reply_text(message)
    logger.info(f"Пул сброшен администратором @{update.message.from_user.username}")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_winners = load_data(LAST_WINNERS_FILE)
    if not last_winners:
        await update.message.reply_text("🤔 Дежурные на сегодня еще не выбраны. Администратор должен запустить рулетку командой `/go`.")
        return
    if len(last_winners) == 2:
        message = (f"👮‍♂️ Сегодня дежурят:\n\n"
                   f"👤 {last_winners[0]['name']} ({last_winners[0]['username']})\n"
                   f"👤 {last_winners[1]['name']} ({last_winners[1]['username']})")
    elif len(last_winners) == 1:
        message = f"🦸‍♂️ Сегодня дежурит последний герой: {last_winners[0]['name']} ({last_winners[0]['username']})"
    await update.message.reply_text(message)

async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ Эта команда доступна только администраторам.")
        return
    keyboard = [
        [InlineKeyboardButton("➕ Добавить пользователя", callback_data='manage_add')],
        [InlineKeyboardButton("➖ Удалить пользователя", callback_data='manage_remove')],
        [InlineKeyboardButton("📋 Показать всех", callback_data='manage_list')],
        [InlineKeyboardButton("❌ Закрыть", callback_data='manage_close')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Меню управления пользователями:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data
    if command == 'manage_add':
        context.user_data['next_step'] = 'add_user'
        await query.edit_message_text(text="Отправьте данные нового пользователя в формате:\n`Имя Фамилия @username`")
    elif command == 'manage_list':
        master_list = load_data(MASTER_LIST_FILE)
        if not master_list:
            text = "Список пользователей пуст."
        else:
            user_lines = [f"👤 {user['name']} ({user['username']})" for user in master_list]
            text = "📋 **Полный список пользователей:**\n\n" + "\n".join(user_lines)
        await query.edit_message_text(text=text, reply_markup=query.message.reply_markup)
    elif command == 'manage_remove':
        master_list = load_data(MASTER_LIST_FILE)
        if not master_list:
            await query.edit_message_text(text="Список пользователей пуст. Некого удалять.", reply_markup=query.message.reply_markup)
            return
        keyboard = [[InlineKeyboardButton(f"❌ {user['name']}", callback_data=f"remove_{user['username']}")] for user in master_list]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_to_manage')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Выберите пользователя для удаления:", reply_markup=reply_markup)
    elif command.startswith('remove_'):
        username_to_remove = query.data.split('_', 1)[1]
        master_list = load_data(MASTER_LIST_FILE)
        user_to_remove = next((user for user in master_list if user['username'] == username_to_remove), None)
        if user_to_remove:
            master_list.remove(user_to_remove)
            save_data(master_list, MASTER_LIST_FILE)
            current_pool = load_data(CURRENT_POOL_FILE)
            current_pool = [user for user in current_pool if user['username'] != username_to_remove]
            save_data(current_pool, CURRENT_POOL_FILE)
            await query.edit_message_text(text=f"✅ Пользователь {user_to_remove['name']} удален.")
        else:
            await query.edit_message_text(text="⚠️ Ошибка: пользователь не найден.")
    elif command == 'back_to_manage':
        keyboard = [
            [InlineKeyboardButton("➕ Добавить пользователя", callback_data='manage_add')],
            [InlineKeyboardButton("➖ Удалить пользователя", callback_data='manage_remove')],
            [InlineKeyboardButton("📋 Показать всех", callback_data='manage_list')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='manage_close')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('Меню управления пользователями:', reply_markup=reply_markup)
    elif command == 'manage_close':
        await query.edit_message_text(text="Меню закрыто.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('next_step') == 'add_user':
        del context.user_data['next_step']
        text = update.message.text
        try:
            parts = text.split('@')
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise ValueError("Неверный формат")
            name = parts[0].strip()
            username = "@" + parts[1].strip()
            new_user = {"name": name, "username": username}
            master_list = load_data(MASTER_LIST_FILE)
            if any(user['username'] == new_user['username'] for user in master_list):
                await update.message.reply_text(f"⚠️ Пользователь {username} уже есть в списке.")
                return
            master_list.append(new_user)
            save_data(master_list, MASTER_LIST_FILE)
            await update.message.reply_text(f"✅ Пользователь {name} ({username}) успешно добавлен!")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка. Пожалуйста, убедитесь, что вы отправили сообщение в формате: `Имя Фамилия @username`")
            logger.error(f"Ошибка добавления пользователя: {e}")

async def webhook_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ Эта команда доступна только администраторам.")
        return
    webhook = await context.bot.get_webhook_info()
    message = (
        f"ℹ️ **Информация о вебхуке:**\n\n"
        f"URL: `{webhook.url}`\n"
        f"Ожидающие обновления: `{webhook.pending_update_count}`\n"
        f"Последняя ошибка: `{webhook.last_error_message or 'Нет'}`"
    )
    await update.message.reply_text(message)

# --- ФИНАЛЬНЫЙ, ИСПРАВЛЕННЫЙ БЛОК ЗАПУСКА ---

# Регистрируем все наши обработчики
application_builder.add_handler(CommandHandler("start", start))
application_builder.add_handler(CommandHandler("go", go))
application_builder.add_handler(CommandHandler("list", list_participants))
application_builder.add_handler(CommandHandler("reset", reset))
application_builder.add_handler(CommandHandler("today", today))
application_builder.add_handler(CommandHandler("manage", manage_users))
application_builder.add_handler(CommandHandler("webhook_info", webhook_info))
application_builder.add_handler(CallbackQueryHandler(button_handler))
application_builder.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

@app.route('/', methods=['GET', 'POST'])
def webhook():
    """Эта функция принимает обновления от Telegram."""
    if request.method == "POST":
        asyncio.run(handle_update(request.get_json()))
        return '', 200
    else:
        return "Бот жив и здоров!", 200

async def handle_update(update_data):
    """Асинхронная функция для обработки одного обновления."""
    async with application_builder.build() as application:
        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)

async def setup_bot():
    """Настраивает бота и устанавливает вебхук."""
    setup_files()
    # Используем контекстный менеджер для установки вебхука
    async with application_builder.build() as application:
        await application.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
        logger.info(f"Вебхук установлен на {WEBHOOK_URL}")

if __name__ == "__main__":
    # Эта конструкция запускает настройку бота перед запуском веб-сервера
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(setup_bot())
    else:
        loop.run_until_complete(setup_bot())