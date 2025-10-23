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

# --- КОНФИГУРАЦИЯ ФАЙЛОВ ---
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

# --- Инициализация ---
application = Application.builder().token(TOKEN).build()
app = Flask(__name__)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def setup_files():
    # Создаем папку и мастер-файл из жесткого списка
    os.makedirs(DATA_DIR, exist_ok=True)
    save_data(INITIAL_STUDENTS, MASTER_LIST_FILE)
    logger.info("Мастер-файл создан из жесткого списка.")

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

# --- ОБРАБОТЧИКИ КОМАНД ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    message = (
        f"👋 Привет, {user_name}!\n\n"
        "Я бот-рулетка для определения дежурных.\n\n"
        "*Команды:*\n"
        "`/list` - Показать, кто остался в рулетке.\n"
        "`/today` - Показать, кто дежурит сегодня.\n"
        "`/go` - Запустить рулетку. \n"