#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import random
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
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, IntegrityError

# --- НАСТРОЙКИ ---
TOKEN = "8347643283:AAFKD80QRaKeU_g0A1Eav7UVVKHieOpUIKA"
ADMIN_USERNAMES = ["phsquadd"]
WEBHOOK_URL = "https://nojack.onrender.com"
DATABASE_URL = os.environ.get('DATABASE_URL')

# --- НАСТРОЙКА БАЗЫ ДАННЫХ ---
db_available = False
db_session = None
try:
    if not DATABASE_URL:
        raise ValueError("Переменная окружения DATABASE_URL не найдена.")
    engine = create_engine(DATABASE_URL)
    metadata = MetaData()
    students = Table('students', metadata,
        Column('id', Integer, primary_key=True),
        Column('name', String(100), nullable=False),
        Column('username', String(100), unique=True, nullable=False),
        Column('duty_count', Integer, default=0),
        Column('duty_debt', Integer, default=0),
        Column('chat_id', String(100), nullable=True),
        Column('is_active', Boolean, default=True)
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
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    db_available = True
    print("✅ Успешное подключение к базе данных.")
except (ValueError, OperationalError) as e:
    print(f"!!! ОШИБКА ПОДКЛЮЧЕНИЯ К БД: {e}")

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
application = Application.builder().token(TOKEN).build()
app = Flask(__name__)

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С БД ---
def get_student_by_username(username):
    return db_session.query(students).filter(students.c.username == username).first()

def get_master_list_from_db(only_active=False):
    query = db_session.query(students)
    if only_active:
        query = query.filter(students.c.is_active == True)
    return [{"id": s.id, "name": s.name, "username": s.username, "duty_count": s.duty_count, "duty_debt": s.duty_debt, "is_active": s.is_active} 
            for s in query.order_by(students.c.name).all()]

def get_pool_from_db():
    return [s.username for s in db_session.query(current_pool).all()]

def get_winners_from_db():
    return [{"name": s.name, "username": s.username} for s in db_session.query(last_winners).all()]

# --- НОВАЯ ФУНКЦИЯ: Получение звания ---
def get_rank(duty_count):
    if duty_count >= 10:
        return "Магистр швабры 🧹"
    elif duty_count >= 5:
        return "Опытный страж порядка 🛡️"
    elif duty_count >= 1:
        return "Новобранец чистоты ✨"
    else:
        return "Гражданский 🧑‍"

# --- ОБРАБОТЧИКИ КОМАНД ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_name = user.first_name
    
    if update.message.chat.type == 'private':
        student_record = get_student_by_username(f"@{user.username}")
        if student_record and not student_record.chat_id:
            db_session.execute(
                students.update().where(students.c.username == f"@{user.username}").values(chat_id=user.id)
            )
            db_session.commit()
            await update.message.reply_text("Спасибо! Теперь я смогу присылать тебе личные уведомления о дежурстве.")

    await help_command(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "Я бот-рулетка с постоянной памятью. Вот что я умею:\n\n"
        "**Для всех:**\n"
        "`/list` - Показать, кто остался в рулетке.\n"
        "`/today` - Показать, кто дежурит сегодня.\n"
        "`/stats` - Показать статистику и звания.\n"
        "`/help` - Показать это сообщение.\n\n"
        "**Только для админов:**\n"
        "`/go` - Запустить рулетку.\n"
        "`/reset` - Начать новый цикл.\n"
        "`/manage` - Управление списком студентов.\n"
        "`/debt @username` - Добавить долг за пропуск.\n"
        "`/skip @username` - Временно убрать из рулетки.\n"
        "`/unskip @username` - Вернуть в рулетку."
    )
    await update.message.reply_text(message)

# ... (команда go остается без изменений, кроме упоминаний) ...
async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав.")
        return
    
    pool_usernames = get_pool_from_db()
    if not pool_usernames:
        await update.message.reply_text("🎲 Пул пуст! Начните новый цикл командой `/reset`.")
        return

    master_list = get_master_list_from_db()
    pool_students = [s for s in master_list if s['username'] in pool_usernames and s['is_active']]
    
    debtors = [s for s in pool_students if s['duty_debt'] > 0]
    winners = []
    if len(debtors) >= 2:
        winners = random.sample(debtors, 2)
    elif len(debtors) == 1:
        winners.append(debtors[0])
        non_debtors = [s for s in pool_students if s['duty_debt'] == 0 and s['username'] != debtors[0]['username']]
        if non_debtors:
            winners.append(random.choice(non_debtors))
        else:
            await update.message.reply_text(f"В пуле остался только один участник (должник) {debtors[0]['name']}. Невозможно выбрать пару.")
            return
    
    if not winners:
        if len(pool_students) < 2:
            if not pool_students:
                await update.message.reply_text("В пуле не осталось активных участников.")
                return
            winner = pool_students[0]
            db_session.query(current_pool).delete()
            db_session.query(last_winners).delete()
            db_session.execute(last_winners.insert().values(name=winner['name'], username=winner['username']))
            db_session.execute(students.update().where(students.c.username == winner['username']).values(duty_count=students.c.duty_count + 1))
            db_session.commit()
            message = (f"🏆 Остался последний герой: {winner['name']} {winner['username']}!\n\n"
                       "Цикл завершен. Для начала нового введите `/reset`.")
            await update.message.reply_text(message)
            return
        winners = random.sample(pool_students, 2)

    for winner in winners:
        db_session.execute(students.update().where(students.c.username == winner['username']).values(duty_count=students.c.duty_count + 1))
        student_record = get_student_by_username(winner['username'])
        if student_record and student_record.duty_debt > 0:
            db_session.execute(students.update().where(students.c.username == winner['username']).values(duty_debt=students.c.duty_debt - 1))
    
    for winner in winners:
        db_session.query(current_pool).filter(current_pool.c.username == winner['username']).delete()
    db_session.query(last_winners).delete()
    for winner in winners:
        db_session.execute(last_winners.insert().values(name=winner['name'], username=winner['username']))
    db_session.commit()

    new_pool_count = db_session.query(current_pool).count()
    message = (f"✨ Рулетка запущена! Сегодня дежурят:\n\n"
               f"👤 {winners[0]['name']} {winners[0]['username']}\n"
               f"👤 {winners[1]['name']} {winners[1]['username']}\n\n"
               f"В рулетке осталось {new_pool_count} участников.")
    await update.message.reply_text(message)

    for winner in winners:
        student_record = get_student_by_username(winner['username'])
        if student_record and student_record.chat_id:
            try:
                await context.bot.send_message(chat_id=student_record.chat_id, text="👋 Привет! Напоминаю, что сегодня твоя очередь дежурить.")
                logger.info(f"Отправлено личное уведомление для {winner['username']}")
            except Exception as e:
                logger.error(f"Не удалось отправить личное уведомление для {winner['username']}: {e}")

# ... (команды list, reset, today, debt, skip, unskip, manage остаются без изменений) ...
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
        await update.message.reply_text("⛔️ У вас нет прав.")
        return
    master_list = get_master_list_from_db(only_active=True)
    if not master_list:
        await update.message.reply_text("⚠️ Список активных студентов пуст! Добавьте их через `/manage` или верните командой `/unskip`.")
        return
    db_session.query(current_pool).delete()
    for student in master_list:
        try:
            db_session.execute(current_pool.insert().values(username=student['username']))
        except IntegrityError:
            db_session.rollback()
            continue
    db_session.query(last_winners).delete()
    db_session.commit()
    message = f"✅ Новый цикл запущен! В рулетку снова загружено {len(master_list)} активных участников."
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

async def debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав.")
        return
    try:
        username_to_penalize = context.args[0]
        if not username_to_penalize.startswith('@'):
            username_to_penalize = '@' + username_to_penalize
        student_record = get_student_by_username(username_to_penalize)
        if student_record:
            db_session.execute(students.update().where(students.c.username == username_to_penalize).values(duty_debt=students.c.duty_debt + 1))
            db_session.commit()
            await update.message.reply_text(f"✅ Долг для {student_record.name} ({username_to_penalize}) увеличен.")
        else:
            await update.message.reply_text(f"⚠️ Пользователь {username_to_penalize} не найден.")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Неверный формат. Используйте: `/debt @username`")

async def skip_user(update: Update, context: ContextTypes.DEFAULT_TYPE, make_active: bool):
    if update.message.from_user.username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔️ У вас нет прав.")
        return
    try:
        username_to_skip = context.args[0]
        if not username_to_skip.startswith('@'):
            username_to_skip = '@' + username_to_skip
        student_record = get_student_by_username(username_to_skip)
        if student_record:
            db_session.execute(students.update().where(students.c.username == username_to_skip).values(is_active=make_active))
            if not make_active:
                db_session.query(current_pool).filter(current_pool.c.username == username_to_skip).delete()
            db_session.commit()
            status = "возвращен в рулетку" if make_active else "временно убран из рулетки"
            await update.message.reply_text(f"✅ Пользователь {student_record.name} ({username_to_skip}) {status}.")
        else:
            await update.message.reply_text(f"⚠️ Пользователь {username_to_skip} не найден.")
    except (IndexError, ValueError):
        command = "/unskip" if make_active else "/skip"
        await update.message.reply_text(f"❌ Неверный формат. Используйте: `{command} @username`")

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await skip_user(update, context, make_active=False)

async def unskip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await skip_user(update, context, make_active=True)

# --- ИЗМЕНЕНО: Команда /stats теперь показывает звания ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_students = db_session.query(students).order_by(students.c.duty_count.desc()).all()
    if not all_students:
        await update.message.reply_text("Список студентов пуст.")
        return
    
    stats_lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, student in enumerate(all_students):
        medal = medals[i] if i < 3 else "🔹"
        rank = get_rank(student.duty_count)
        debt_info = f" (долг: {student.duty_debt})" if student.duty_debt > 0 else ""
        status_info = " (неактивен)" if not student.is_active else ""
        stats_lines.append(f"{medal} {student.name} - {rank} ({student.duty_count} раз){debt_info}{status_info}")
        
    message = "📊 **Рейтинг Хранителей Порядка:**\n\n" + "\n".join(stats_lines)
    await update.message.reply_text(message)

# --- НОВАЯ КОМАНДА: Пасхалка ---
async def gregory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ну конечно я буду и крутить, и накручивать, и никогда не буду дежурить.... Да. 😉")

# --- БЛОК УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ (без изменений) ---
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
        master_list = get_master_list_from_db()
        if not master_list:
            text = "Список пользователей пуст."
        else:
            user_lines = [f"👤 {user['name']} ({user['username']}){' (неактивен)' if not user['is_active'] else ''}" for user in master_list]
            text = "📋 **Полный список пользователей:**\n\n" + "\n".join(user_lines)
        await query.edit_message_text(text=text, reply_markup=query.message.reply_markup)

    elif command == 'manage_remove':
        master_list = get_master_list_from_db()
        if not master_list:
            await query.edit_message_text(text="Список пуст, некого удалять.", reply_markup=query.message.reply_markup)
            return
        keyboard = [[InlineKeyboardButton(f"❌ {user['name']}", callback_data=f"remove_{user['id']}")] for user in master_list]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_to_manage')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Выберите пользователя для удаления:", reply_markup=reply_markup)

    elif command.startswith('remove_'):
        user_id_to_remove = int(query.data.split('_', 1)[1])
        user_to_remove = db_session.query(students).filter(students.c.id == user_id_to_remove).first()
        if user_to_remove:
            db_session.query(students).filter(students.c.id == user_id_to_remove).delete()
            db_session.query(current_pool).filter(current_pool.c.username == user_to_remove.username).delete()
            db_session.commit()
            await query.edit_message_text(text=f"✅ Пользователь {user_to_remove.name} удален из всех списков.")
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
            db_session.execute(students.insert().values(name=name, username=username, duty_count=0, duty_debt=0, is_active=True))
            db_session.commit()
            await update.message.reply_text(f"✅ Пользователь {name} ({username}) успешно добавлен в базу данных!")
        except IntegrityError:
            db_session.rollback()
            await update.message.reply_text(f"⚠️ Ошибка: Пользователь с username {username} уже существует.")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка. Убедитесь, что формат: `Имя Фамилия @username`")
            logger.error(f"Ошибка добавления пользователя: {e}")

# --- БЛОК ЗАПУСКА ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("go", go))
application.add_handler(CommandHandler("list", list_participants))
application.add_handler(CommandHandler("reset", reset))
application.add_handler(CommandHandler("today", today))
application.add_handler(CommandHandler("manage", manage_users))
application.add_handler(CommandHandler("stats", stats))
application.add_handler(CommandHandler("debt", debt))
application.add_handler(CommandHandler("skip", skip))
application.add_handler(CommandHandler("unskip", unskip))
application.add_handler(CommandHandler("gregory", gregory)) # Пасхалка
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

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