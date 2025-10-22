#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import random
import json
import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
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

# --- ВОЗВРАЩАЕМ ЖЕСТКИЙ СПИСОК СТУДЕНТОВ ---
INITIAL_STUDENTS = [
    {"name": "Андреев Александр", "username": "@phsquadd"},
    {"name": "Абраменко Павел", "username": "@Pevlik12"},
    {"name": "Андросов Макар", "username": "@CalamitAss"},
    {"name": "Головань Елизавета", "username": "@Arp_ell"},
    {"name": "Дологодин Денис", "username": "@Gvstaxx"},
    {"name": "Дудник Александр", "username": "@llSirll"},
    {"name": "Кузнецов Артем", "username": "@h0moxide"},
    {"name": "Кривошеев Григорий", "username": "@SKOOKA2007"},
    {"name": "Княгинин Вадим", "username": "@Liro26"},
    {"name": "Маслевцов Иван", "username": "@maslov_vvv"},
    {"name": "Садуев Азамат", "username": "@saduevvv18"},
    {"name": "Прощалкин Дмитрий", "username": "@GopoChaechik"},
    {"name": "Саруханов Александр", "username": "@kk80968"},
    {"name": "Самодуров Елисей", "username": "@Prosto_EIKA"}
]

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Инициализация бота и веб-сервера ---
application = Application.builder().token(TOKEN).build()
app = Flask(__name__)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def setup_files():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    # Теперь мастер-файл всегда создается из жесткого списка
    save_data(INITIAL_STUDENTS, MASTER_LIST_FILE)
    logger.info(f"Создан мастер-файл из жесткого списка: {MASTER_LIST_FILE}")

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
        "Я бот-рулетка для определения дежурных.\n\n"
        "**Команды:**\n"
        "`/list` - Показать, кто остался в рулетке.\n"
        "`/today` - Показать, кто дежурит сегодня.\n"
        "`/go` - Запустить рулетку (только для админов).\n"
        "`/reset` - Начать новый цикл (только для админов)."
    )
    await update.message.reply_text(message)

async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав для запуска рулетки.")
        return
    pool = load_data(CURRENT_POOL_FILE)
    if not pool:
        await update.message.reply_text("🎲 Пул дежурных пуст! Начните новый цикл командой `/reset`.")
        return
    if len(pool) < 2:
        winner = pool[0]
        save_data([], CURRENT_POOL_FILE)
        save_data([winner], LAST_WINNERS_FILE)
        message = (f"🏆 Остался последний герой: {winner['name']} ({winner['username']})!\n\n"
                   "Цикл завершен. Для начала нового введите `/reset`.")
        await update.message.reply_text(message)
        return
    winners = random.sample(pool, 2)
    new_pool = [p for p in pool if p not in winners]
    save_data(new_pool, CURRENT_POOL_FILE)
    save_data(winners, LAST_WINNERS_FILE)
    message = (f"✨ Рулетка запущена! Сегодня дежурят:\n\n"
               f"👤 {winners[0]['name']} ({winners[0]['username']})\n"
               f"👤 {winners[1]['name']} ({winners[1]['username']})\n\n"
               f"В рулетке осталось {len(new_pool)} участников.")
    await update.message.reply_text(message)

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = load_data(CURRENT_POOL_FILE)
    if not pool:
        await update.message.reply_text("🎲 Пул дежурных пуст.")
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

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_winners = load_data(LAST_WINNERS_FILE)
    if not last_winners:
        await update.message.reply_text("🤔 Дежурные на сегодня еще не выбраны.")
        return
    if len(last_winners) == 2:
        message = (f"👮‍♂️ Сегодня дежурят:\n\n"
                   f"👤 {last_winners[0]['name']} ({last_winners[0]['username']})\n"
                   f"👤 {last_winners[1]['name']} ({last_winners[1]['username']})")
    else:
        message = f"🦸‍♂️ Сегодня дежурит последний герой: {last_winners[0]['name']} ({last_winners[0]['username']})"
    await update.message.reply_text(message)

# --- ФИНАЛЬНЫЙ, УПРОЩЕННЫЙ БЛОК ЗАПУСКА ---

# Регистрируем наши простые обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("go", go))
application.add_handler(CommandHandler("list", list_participants))
application.add_handler(CommandHandler("reset", reset))
application.add_handler(CommandHandler("today", today))

@app.route('/', methods=['GET', 'POST'])
def webhook():
    """Эта функция принимает обновления от Telegram."""
    if request.method == "POST":
        # Используем самый надежный способ обработки
        asyncio.run(handle_update(request.get_json()))
        return '', 200
    else:
        return "Бот жив и здоров!", 200

async def handle_update(update_data):
    """Асинхронная функция для обработки одного обновления."""
    async with application:
        await application.process_update(Update.de_json(update_data, application.bot))

async def setup_bot():
    """Настраивает бота и устанавливает вебхук."""
    setup_files()
    await application.initialize()
    await application.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Вебхук установлен на {WEBHOOK_URL}")
    # Запускаем обработку в фоновом режиме
    await application.start()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(setup_bot())
    else:
        loop.run_until_complete(setup_bot())