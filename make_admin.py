# make_admin.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import UserDB
from config import settings

# Подключаемся к БД
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(engine)
db = SessionLocal()

# Укажите имя пользователя, которого хотите сделать админом
username = "Admin1"  # Замените на ваше имя пользователя

user = db.query(UserDB).filter(UserDB.username == username).first()

if user:
    user.role = "admin"
    db.commit()
    print(f"✅ Пользователь {username} теперь администратор!")
    print(f"ID: {user.id}, Роль: {user.role}")
else:
    print(f"❌ Пользователь {username} не найден")
    print("\nСписок всех пользователей:")
    users = db.query(UserDB).all()
    for u in users:
        print(f"ID: {u.id}, Имя: {u.username}, Роль: {u.role}")

db.close()