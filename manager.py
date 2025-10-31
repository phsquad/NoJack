import os
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# --- НАСТРОЙКИ (ЗАПОЛНИТЕ САМИ) ---
# Вставьте сюда "External Connection String" из настроек базы данных на Render
DATABASE_URL = "postgresql://duty_bot_memory_lu9y_user:Nii1uyhvLh2YbgK7o8jOvwLGmQ5qquKZ@dpg-d42eidh5pdvs73e7e83g-a.oregon-postgres.render.com/duty_bot_memory_lu9y"
# --- КОНЕЦ НАСТРОЕК ---

# Настройка такая же, как в основном боте
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
metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db_session = Session()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    while True:
        clear_screen()
        print("--- Менеджер списка студентов (База данных) ---")
        all_students = db_session.query(students).order_by(students.c.name).all()
        print("\nТекущий список:")
        if not all_students:
            print("  (пусто)")
        else:
            for i, user in enumerate(all_students, 1):
                print(f"  {i}. {user.name} ({user.username}) - Дежурств: {user.duty_count}")
        
        print("\nВыберите действие:")
        print("  1. ➕ Добавить пользователя")
        print("  2. ➖ Удалить пользователя")
        print("  3. ✏️ Изменить счетчик дежурств") # НОВАЯ ОПЦИЯ
        print("  4. 🚪 Выйти")
        
        choice = input("\nВаш выбор: ")

        if choice == '1':
            name = input("Введите Имя Фамилию: ").strip()
            username = input("Введите username (начиная с @): ").strip()
            if name and username.startswith('@'):
                try:
                    db_session.execute(students.insert().values(name=name, username=username, duty_count=0, duty_debt=0, is_active=True))
                    db_session.commit()
                    print(f"\n✅ Пользователь {name} добавлен.")
                except IntegrityError:
                    db_session.rollback()
                    print(f"\n⚠️ Ошибка: Пользователь с username {username} уже существует.")
            else:
                print("\n❌ Неверный формат.")
            input("\nНажмите Enter для продолжения...")

        elif choice == '2':
            if not all_students:
                print("\nСписок пуст, некого удалять.")
                input("\nНажмите Enter для продолжения...")
                continue
            try:
                num_to_remove = int(input("Введите номер пользователя для удаления: "))
                if 1 <= num_to_remove <= len(all_students):
                    user_to_remove = all_students[num_to_remove - 1]
                    db_session.query(students).filter(students.c.id == user_to_remove.id).delete()
                    db_session.commit()
                    print(f"\n✅ Пользователь {user_to_remove.name} удален.")
                else:
                    print("\n❌ Неверный номер.")
            except ValueError:
                print("\n❌ Пожалуйста, введите число.")
            input("\nНажмите Enter для продолжения...")

        # --- НОВЫЙ БЛОК ДЛЯ РЕДАКТИРОВАНИЯ ---
        elif choice == '3':
            if not all_students:
                print("\nСписок пуст, нечего редактировать.")
                input("\nНажмите Enter для продолжения...")
                continue
            try:
                num_to_edit = int(input("Введите номер пользователя для редактирования: "))
                if 1 <= num_to_edit <= len(all_students):
                    user_to_edit = all_students[num_to_edit - 1]
                    new_count_str = input(f"Введите новое количество дежурств для {user_to_edit.name}: ")
                    new_count = int(new_count_str)
                    
                    db_session.execute(
                        students.update().where(students.c.id == user_to_edit.id).values(duty_count=new_count)
                    )
                    db_session.commit()
                    print(f"\n✅ Счетчик для {user_to_edit.name} обновлен на {new_count}.")
                else:
                    print("\n❌ Неверный номер.")
            except ValueError:
                print("\n❌ Пожалуйста, введите число.")
            input("\nНажмите Enter для продолжения...")

        elif choice == '4':
            print("\nДо свидания!")
            break
        else:
            print("\nНеверный выбор.")
            input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    main()