from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
import os
import requests
from dotenv import load_dotenv
from models import UserDB, VerificationCodeDB
from passlib.context import CryptContext

load_dotenv()



# === Настройка хеширования паролей ===
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# === Telegram бот ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("⚠️ TELEGRAM_BOT_TOKEN не найден в .env")

def send_telegram_code(telegram_id: str, code: str) -> bool:
    """Отправка кода подтверждения в Telegram"""
    if not BOT_TOKEN or not telegram_id:
        return False
    
    message = f"""
🔐 *Код подтверждения*

Ваш код для входа в IT Project Cost:

`{code}`

⏳ Код действителен 5 минут

_Если вы не запрашивали код, проигнорируйте это сообщение._
    """
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": telegram_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def generate_code() -> str:
    """Генерация 6-значного кода"""
    return ''.join(random.choices('0123456789', k=6))

# === Временное хранилище ===
temp_codes = {}

def create_verification_code(db: Session, phone: str) -> str:
    """Создание кода подтверждения"""
    code = generate_code()
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    # Удаляем старые коды для этого номера
    db.query(VerificationCodeDB).filter(
        VerificationCodeDB.phone == phone,
        VerificationCodeDB.is_used == False
    ).delete()
    
    # Создаем новый
    ver_code = VerificationCodeDB(
        phone=phone,
        code=code,
        expires_at=expires_at
    )
    db.add(ver_code)
    db.commit()
    db.refresh(ver_code)
    
    # Сохраняем в памяти для быстрого доступа
    temp_codes[phone] = {
        "code": code,
        "expires_at": expires_at,
        "used": False
    }
    
    return code

def verify_code(db: Session, phone: str, code: str) -> bool:
    """Проверка кода"""
    # Ищем в БД
    ver_code = db.query(VerificationCodeDB).filter(
        VerificationCodeDB.phone == phone,
        VerificationCodeDB.code == code,
        VerificationCodeDB.is_used == False,
        VerificationCodeDB.expires_at > datetime.utcnow()
    ).first()
    
    if ver_code:
        ver_code.is_used = True
        db.commit()
        return True
    
    # Проверяем в памяти
    if phone in temp_codes:
        data = temp_codes[phone]
        if data["code"] == code and not data["used"] and data["expires_at"] > datetime.utcnow():
            data["used"] = True
            # Отмечаем в БД
            ver_code = db.query(VerificationCodeDB).filter(
                VerificationCodeDB.phone == phone,
                VerificationCodeDB.code == code
            ).first()
            if ver_code:
                ver_code.is_used = True
                db.commit()
            return True
    
    return False

def get_user_by_phone(db: Session, phone: str):
    """Получить пользователя по номеру телефона"""
    return db.query(UserDB).filter(UserDB.phone == phone).first()

def get_user_by_username(db: Session, username: str):
    """Получить пользователя по имени пользователя"""
    return db.query(UserDB).filter(UserDB.username == username).first()

def create_user(db: Session, **kwargs):
    """Создание нового пользователя"""
    user = UserDB(**kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate_user(db: Session, username: str, password: str):
    """Аутентификация по логину/паролю"""
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# === OAuth2 (для будущих расширений) ===
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)