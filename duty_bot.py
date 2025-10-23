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
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

# --- НАСТРОЙКИ ---
TOKEN = "8347643283:AAFKD80QRaKeU_g0A1Eav7UVVKHieOpUIKA"
ADMIN_USERNAMES = ["phsquadd", "saduevvv18"]
WEBHOOK_URL = "https://nojack.onrender.com"

# --- ИСПРАВЛЕНИЕ №1: Правильно читаем адрес из переменных окружения ---
# Эта строка берет значение из настроек Render, которые мы сделали
DATABASE_URL = os.environ.get('DATABASE_URL')

# --- НАСТРОЙКА БАЗЫ ДАННЫХ ---
# --- ИСПРАВЛЕНИЕ №2: Передаем переменную, а не строку, и обрабатываем ошибку ---
db_available = False
db_session = None
engine = None

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
        metadata = MetaData()

        # Описываем таблицы
        students = Table('students', metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(100), nullable=False),
            Column('username', String(100), unique=True, nullable=False)
        )

        current_pool = Table('current_pool', metadata,
            Column('id', Integer, primary_key=True),
            Column('username', String(100), unique=True, nullable=False)
        )

        last_winners = Table('last_winners', metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(100), nullable=False),
            Column('username', String(100), nullable=False)
        )

        # Создаем таблицы, если их нет
        metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db_session = Session()
        db_available = True
        print("✅ Успешное подключение к базе данных.")
    except Exception as e:
        print(f"!!! ОШИБКА: Не удалось подключиться к базе данных. Ошибка: {e}")
else:
    print("!!! ОШИБКА: Переменная окружения DATABASE_URL не найдена.")

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Инициализация ---
application = Application.builder().token(TOKEN).build()
app = Flask(__name__)

# --- НОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С БД ---
def get_master_list_from_db():
    if not db_available: return []
    return [{"name": s.name, "username": s.username} for s in db_session.query(students).all()]

def get_pool_from_db():
    if not db_available: return []
    return [s.username for s in db_session.query(current_pool).all()]

def get_winners_from_db():
    if not db_available: return []
    return [{"name": s.name, "username": s.username} for s in db_session.query(last_winners).all()]

# --- ОБРАБОТЧИКИ КОМАНД (адаптированы под БД) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    message = (
        f"👋 Привет, {user_name}!\n\n"
        "Я бот-рулетка для определения дежурных.\n\n"
        "**Команды:**\n"
        "`/list` - Показать, кто остался в рулетке.\n"
        "`/today` - Показать, кто дежурит сегодня.\n"
        "`/go` - Запустить рулетку (только для админов).\n"
        "`/reset` - Начать новый цикл (только для админов).\n\n"
        "**ВАЖНО:** Список студентов теперь нужно добавлять через отдельный скрипт-менеджер."
    )
    await update.message.reply_text(message)

async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав для запуска рулетки.")
        return
    
    pool_usernames = get_pool_from_db()
    if not pool_usernames:
        await update.message.reply_text("🎲 Пул дежурных пуст! Начните новый цикл командой `/reset`.")
        return

    master_list = get_master_list_from_db()
    pool_students = [s for s in master_list if s['username'] in pool_usernames]

    if len(pool_students) < 2:
        winner = pool_students[0]
        db_session.query(current_pool).delete()
        db_session.query(last_winners).delete()
        db_session.execute(last_winners.insert().values(name=winner['name'], username=winner['username']))
        db_session.commit()
        message = (f"🏆 Остался последний герой: {winner['name']} ({winner['username']})!\n\n"
                   "Цикл завершен. Для начала нового введите `/reset`.")
        await update.message.reply_text(message)
        return

    winners = random.sample(pool_students, 2)
    
    for winner in winners:
        db_session.query(current_pool).filter(current_pool.c.username == winner['username']).delete()
    
    db_session.query(last_winners).delete()
    for winner in winners:
        db_session.execute(last_winners.insert().values(name=winner['name'], username=winner['username']))
    db_session.commit()

    new_pool_count = db_session.query(current_pool).count()
    message = (f"✨ Рулетка запущена! Сегодня дежурят:\n\n"
               f"👤 {winners[0]['name']} ({winners[0]['username']})\n"
               f"👤 {winners[1]['name']} ({winners[1]['username']})\n\n"
               f"В рулетке осталось {new_pool_count} участников.")
    await update.message.reply_text(message)

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool_usernames = get_pool_from_db()
    if not pool_usernames:
        await update.message.reply_text("🎲 Пул дежурных пуст.")
        return
    
    master_list = get_master_list_from_db()
    pool_students = [s for s in master_list if s['username'] in pool_usernames]
    
    participant_lines = [f"👤 {p['name']} ({p['username']})" for p in pool_students]
    message = "👥 В рулетке остались:\n\n" + "\n".join(participant_lines)
    await update.message.reply_text(message)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды.")
        return
        
    master_list = get_master_list_from_db()
    
    db_session.query(current_pool).delete()
    for student in master_list:
        db_session.execute(current_pool.insert().values(username=student['username']))
    
    db_session.query(last_winners).delete()
    db_session.commit()
    
    message = f"✅ Новый цикл запущен! В рулетку снова загружено {len(master_list)} участников."
    await update.message.reply_text(message)

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    winners = get_winners_from_db()
    if not winners:
        await update.message.reply_text("🤔 Дежурные на сегодня еще не выбраны.")
        return
    if len(winners) == 2:
        message = (f"👮‍♂️ Сегодня дежурят:\n\n"
                   f"👤 {winners[0]['name']} ({winners[0]['username']})\n"
                   f"👤 {winners[1]['name']} ({winners[1]['username']})")
    else:
        message = f"🦸‍♂️ Сегодня дежурит последний герой: {winners[0]['name']} ({winners[0]['username']})"
    await update.message.reply_text(message)

# --- БЛОК ЗАПУСКА ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("go", go))
application.add_handler(CommandHandler("list", list_participants))
application.add_handler(CommandHandler("reset", reset))
application.add_handler(CommandHandler("today", today))

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == "POST":
        asyncio.run(handle_update(request.get_json()))
        return '', 200
    else:
        return "Бот жив и здоров!", 200

async def handle_update(update_data):
    async with application:
        await application.process_update(Update.de_json(update_data, application.bot))

async def setup_bot():
    if not db_available:
        logger.error("База данных недоступна. Бот не может быть запущен.")
        return
    await application.initialize()
    await application.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Вебхук установлен на {WEBHOOK_URL}")
    await application.start()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(setup_bot())
    else:
        loop.run_until_complete(setup_bot())