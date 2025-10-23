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
from github import Github

# --- НАСТРОЙКИ ---
TOKEN = "8347643283:AAFKD80QRaKeU_g0A1Eav7UVVKHieOpUIKA"
ADMIN_USERNAMES = ["phsquadd", "saduevvv18"]
WEBHOOK_URL = "https://nojack.onrender.com"

# --- НАСТРОЙКИ GITHUB (читаются из Render Environment) ---
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_NAME = os.environ.get('REPO_NAME')
FILE_PATH = "data/master_list.json"

# --- КОНФИГУРАЦИЯ ЛОКАЛЬНЫХ ФАЙЛОВ ---
DATA_DIR = "data"
MASTER_LIST_FILE = os.path.join(DATA_DIR, "master_list.json")
CURRENT_POOL_FILE = os.path.join(DATA_DIR, "current_pool.json")
LAST_WINNERS_FILE = os.path.join(DATA_DIR, "last_winners.json")

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Инициализация ---
application = Application.builder().token(TOKEN).build()
app = Flask(__name__)
github_api = Github(GITHUB_TOKEN) if GITHUB_TOKEN else None
repo = github_api.get_repo(REPO_NAME) if github_api and REPO_NAME else None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def setup_files():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    try:
        if repo:
            file_content = repo.get_contents(FILE_PATH).decoded_content.decode('utf-8')
            with open(MASTER_LIST_FILE, 'w', encoding='utf-8') as f:
                f.write(file_content)
            logger.info("Мастер-файл успешно загружен с GitHub.")
    except Exception as e:
        logger.error(f"Не удалось загрузить мастер-файл с GitHub: {e}. Будет создан пустой список.")
        save_data([], MASTER_LIST_FILE)

def load_data(file_path):
    if not os.path.exists(file_path): return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_data(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ФУНКЦИЯ ДЛЯ СОХРАНЕНИЯ НА GITHUB ---
async def save_master_list_to_github(new_data, commit_message, context: ContextTypes.DEFAULT_TYPE):
    if not repo:
        await context.bot.send_message(chat_id=context._chat_id, text="❌ Ошибка: Бот не подключен к GitHub. Проверьте переменные окружения.")
        return False
    try:
        file = repo.get_contents(FILE_PATH)
        new_content = json.dumps(new_data, ensure_ascii=False, indent=4)
        repo.update_file(file.path, commit_message, new_content, file.sha)
        logger.info(f"Изменения сохранены на GitHub: {commit_message}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения на GitHub: {e}")
        await context.bot.send_message(chat_id=context._chat_id, text=f"❌ Ошибка сохранения на GitHub: {e}")
        return False

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
        "`/reset` - Начать новый цикл (только для админов).\n"
        "`/manage` - Управление списком студентов (только для админов)."
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
    if not master_list:
        await update.message.reply_text("⚠️ Мастер-список пуст! Добавьте студентов через `/manage`.")
        return
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
    reply_markup = InlineKeyboardMa