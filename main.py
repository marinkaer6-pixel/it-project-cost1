from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from contextlib import contextmanager
from datetime import datetime, timedelta
from passlib.hash import pbkdf2_sha256
from pydantic import BaseModel
import os
import random
import requests

# === Импорты ===
from config import settings
from models import Base, ProjectDB, ProjectResourceDB, EmployeeDB, ContractorDB, EquipmentDB, ClientDB, UserDB, VerificationCodeDB, TeamDB, ChatMessageDB

# === Pydantic модели ===
class RegisterRequest(BaseModel):
    username: str
    password: str
    phone: str
    telegram_id: str

class LoginRequest(BaseModel):
    username: str
    password: str

class CodeRequest(BaseModel):
    username: str

class SetRoleRequest(BaseModel):
    username: str
    new_role: str

class CreateTeamRequest(BaseModel):
    name: str
    description: str = ""

class AddUserToTeamRequest(BaseModel):
    username: str
    team_id: int

class SendMessageRequest(BaseModel):
    team_id: int
    message: str

# === Создание приложения ===
app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === БД ===
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(engine, autocommit=False, autoflush=False)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    print(f"✅ База данных: {settings.DATABASE_URL}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# === Хеширование ===
def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pbkdf2_sha256.verify(plain, hashed)

# === Сессии ===
sessions = {}
temp_codes = {}

def generate_code():
    return ''.join(random.choices('0123456789', k=6))

def send_telegram_code(telegram_id: str, code: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or not telegram_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    message = f"🔐 *Код подтверждения*\n\nВаш код: `{code}`\n\n⏳ Действует 5 минут"
    try:
        response = requests.post(url, json={"chat_id": telegram_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        return response.status_code == 200
    except:
        return False

# ============================================================
# HTML_PAGE (полный интерфейс)
# ============================================================

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>IT Project Cost</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: system-ui, sans-serif;
            background: #0c0e1a;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .logo h1 { color: #a78bfa; }
        .btn {
            padding: 8px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-primary { background: #a78bfa; color: #0c0e1a; }
        .btn-primary:hover { background: #8b6ff0; transform: translateY(-2px); }
        .btn-danger { background: rgba(248,113,113,0.2); color: #f87171; }
        .btn-danger:hover { background: rgba(248,113,113,0.3); }
        .btn-success { background: #6ee7b7; color: #0c0e1a; }
        .btn-success:hover { background: #5ad4a5; transform: translateY(-2px); }
        .btn-sm { padding: 4px 12px; font-size: 0.8em; }
        .btn-warning { background: rgba(251,191,36,0.2); color: #fbbf24; }
        .btn-warning:hover { background: rgba(251,191,36,0.3); }
        .auth-form {
            max-width: 400px;
            margin: 40px auto;
            background: rgba(255,255,255,0.05);
            padding: 30px;
            border-radius: 16px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .auth-form input {
            width: 100%;
            padding: 10px 14px;
            margin-bottom: 12px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #fff;
            font-size: 1em;
            outline: none;
            transition: border-color 0.2s;
        }
        .auth-form input:focus { border-color: #a78bfa; }
        .auth-form .btn { width: 100%; margin-top: 5px; }
        .toggle-link {
            text-align: center;
            margin-top: 15px;
            color: rgba(255,255,255,0.5);
            cursor: pointer;
        }
        .toggle-link span { color: #a78bfa; text-decoration: underline; }
        .hidden { display: none; }
        .status-msg { text-align: center; margin-top: 10px; min-height: 24px; }
        .status-msg.success { color: #6ee7b7; }
        .status-msg.error { color: #f87171; }
        .status-msg.info { color: #a78bfa; }
        .menu {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        .menu .btn {
            background: rgba(255,255,255,0.05);
            color: #fff;
        }
        .menu .btn.active {
            background: rgba(167,139,250,0.2);
            color: #a78bfa;
        }
        .page { display: none; }
        .page.active { display: block; }
        .table-wrap {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            overflow-x: auto;
            border: 1px solid rgba(255,255,255,0.05);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        th {
            color: rgba(255,255,255,0.5);
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        tr:hover { background: rgba(255,255,255,0.02); }
        .empty {
            text-align: center;
            padding: 40px 20px;
            color: rgba(255,255,255,0.3);
        }
        .error {
            color: #f87171;
            text-align: center;
            padding: 20px;
        }
        .role-badge {
            display: inline-block;
            padding: 2px 12px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
        }
        .role-badge.admin { background: rgba(167,139,250,0.2); color: #a78bfa; }
        .role-badge.user { background: rgba(110,231,183,0.15); color: #6ee7b7; }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.6);
            justify-content: center;
            align-items: center;
            z-index: 1000;
            backdrop-filter: blur(4px);
        }
        .modal.active { display: flex; }
        .modal-content {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 30px;
            max-width: 500px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .modal-content input, .modal-content select, .modal-content textarea {
            width: 100%;
            padding: 10px;
            margin-bottom: 12px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #fff;
            outline: none;
            transition: border-color 0.2s;
        }
        .modal-content input:focus, .modal-content select:focus, .modal-content textarea:focus { 
            border-color: #a78bfa; 
        }
        .modal-content select option { background: #1a1a2e; color: #fff; }
        .modal-content textarea { min-height: 60px; resize: vertical; }
        .modal-close {
            float: right;
            background: none;
            border: none;
            color: rgba(255,255,255,0.4);
            font-size: 1.3em;
            cursor: pointer;
            transition: color 0.2s;
        }
        .modal-close:hover { color: #fff; }
        .modal-title { margin-bottom: 20px; }
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .chat-box {
            height: 400px;
            overflow-y: auto;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .chat-message {
            margin-bottom: 10px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
        }
        .chat-message .username { color: #a78bfa; font-weight: 600; }
        .chat-message .time { color: rgba(255,255,255,0.3); font-size: 0.75em; margin-left: 10px; }
        .chat-message .text { margin-top: 4px; }
        .chat-input {
            display: flex;
            gap: 10px;
        }
        .chat-input input {
            flex: 1;
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #fff;
            outline: none;
        }
        .chat-input input:focus { border-color: #a78bfa; }
        .chat-input button { width: auto; }
        .owner-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.7em;
            background: rgba(255,215,0,0.15);
            color: #ffd700;
            margin-left: 8px;
        }
        .stat-card {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .stat-card .number { font-size: 1.8em; font-weight: 700; color: #a78bfa; }
        .stat-card .label { color: rgba(255,255,255,0.5); font-size: 0.8em; }
        .action-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .btn-delete {
            background: rgba(248,113,113,0.2);
            color: #f87171;
            padding: 4px 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8em;
            transition: all 0.2s;
        }
        .btn-delete:hover { background: rgba(248,113,113,0.3); }
        .profit-positive { color: #6ee7b7; }
        .profit-negative { color: #f87171; }
        .status-badge {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.8em;
        }
        .status-badge.created { background: rgba(167,139,250,0.2); color: #a78bfa; }
        .status-badge.in-progress { background: rgba(251,191,36,0.2); color: #fbbf24; }
        .status-badge.completed { background: rgba(110,231,183,0.2); color: #6ee7b7; }
        .status-badge.cancelled { background: rgba(248,113,113,0.2); color: #f87171; }
        .text-muted { color: rgba(255,255,255,0.4); font-size: 0.8em; }
        .highlight { background: rgba(167,139,250,0.1); padding: 2px 8px; border-radius: 4px; }
        @media (max-width: 768px) {
            .form-row { grid-template-columns: 1fr; }
            .header { flex-direction: column; align-items: flex-start; }
            .menu .btn { font-size: 0.9em; padding: 6px 14px; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="logo"><h1>🚀 IT Project Cost</h1></div>
        <div>
            <span id="user-name">👤 Не авторизован</span>
            <span id="user-role" class="role-badge hidden"></span>
            <button class="btn btn-danger hidden" id="logout-btn">Выйти</button>
        </div>
    </div>

    <!-- Форма авторизации -->
    <div id="auth-form" class="auth-form">
        <h2 id="form-title" style="text-align:center;margin-bottom:20px;">Вход</h2>
        <input type="text" id="auth-username" placeholder="Имя пользователя">
        <input type="password" id="auth-password" placeholder="Пароль">
        <div id="register-fields" class="hidden">
            <input type="tel" id="auth-phone" placeholder="Телефон (+7...)">
            <input type="text" id="auth-telegram" placeholder="Telegram ID (только цифры)">
        </div>
        <div id="code-field" class="hidden">
            <input type="text" id="auth-code" placeholder="Код из Telegram" maxlength="6">
        </div>
        <button class="btn btn-primary" id="auth-submit">Войти</button>
        <div class="status-msg" id="auth-status"></div>
        <div class="toggle-link">
            <span id="toggle-text">Нет аккаунта? <span id="toggle-link">Зарегистрироваться</span></span>
        </div>
    </div>

    <!-- Основной контент -->
    <div id="main-content" class="hidden">
        <div class="menu">
            <button class="btn active" data-page="projects">📁 Проекты</button>
            <button class="btn" data-page="employees">👨‍💻 Сотрудники</button>
            <button class="btn" data-page="equipment">💻 Оборудование</button>
            <button class="btn" data-page="clients">🏢 Клиенты</button>
            <button class="btn" data-page="stats">📊 Статистика</button>
            <button class="btn" data-page="users" id="users-menu-btn">👥 Пользователи</button>
            <button class="btn" data-page="teams" id="teams-menu-btn">🏷️ Команды</button>
            <button class="btn" data-page="chat" id="chat-menu-btn">💬 Чат</button>
        </div>

        <!-- Проекты -->
        <div id="page-projects" class="page active">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
                <h2>📋 Проекты</h2>
                <button class="btn btn-success" onclick="openProjectModal()">+ Новый проект</button>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Название</th><th>Статус</th><th>Стоимость для клиента</th><th>Себестоимость</th><th>Прибыль</th><th>Дата</th><th>Действия</th></tr></thead>
                    <tbody id="projects-table"></tbody>
                </table>
            </div>
        </div>

        <!-- Сотрудники -->
        <div id="page-employees" class="page">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
                <h2>👨‍💻 Сотрудники</h2>
                <button class="btn btn-success" onclick="openEmployeeModal()">+ Добавить сотрудника</button>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>ФИО</th><th>Должность</th><th>Зарплата</th><th>Налог</th><th>Действия</th></tr></thead>
                    <tbody id="employees-table"></tbody>
                </table>
            </div>
        </div>

        <!-- Оборудование -->
        <div id="page-equipment" class="page">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
                <h2>💻 Оборудование</h2>
                <button class="btn btn-success" onclick="openEquipmentModal()">+ Добавить оборудование</button>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Название</th><th>Тип</th><th>Цена</th><th>Действия</th></tr></thead>
                    <tbody id="equipment-table"></tbody>
                </table>
            </div>
        </div>

        <!-- Клиенты -->
        <div id="page-clients" class="page">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
                <h2>🏢 Клиенты</h2>
                <button class="btn btn-success" onclick="openClientModal()">+ Добавить клиента</button>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>ИНН</th><th>Название</th><th>Тип</th><th>Действия</th></tr></thead>
                    <tbody id="clients-table"></tbody>
                </table>
            </div>
        </div>

        <!-- Статистика -->
        <div id="page-stats" class="page">
            <h2>📊 Статистика</h2>
            <div id="stats-content"><p class="empty">Загрузка...</p></div>
        </div>

        <!-- Пользователи -->
        <div id="page-users" class="page">
            <h2>👥 Пользователи</h2>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>ID</th><th>Имя</th><th>Телефон</th><th>Telegram ID</th><th>Роль</th><th>Команда</th></tr></thead>
                    <tbody id="users-table"></tbody>
                </table>
            </div>
        </div>

        <!-- Команды -->
        <div id="page-teams" class="page">
            <h2>🏷️ Команды</h2>
            <div id="create-team-form" style="margin-bottom: 20px;">
                <h3>➕ Создать команду</h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <input type="text" id="team-name-input" placeholder="Название команды" style="flex: 1; min-width: 200px; padding: 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); color: #fff;">
                    <input type="text" id="team-desc-input" placeholder="Описание (необязательно)" style="flex: 1; min-width: 200px; padding: 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); color: #fff;">
                    <button class="btn btn-success" onclick="createTeam()">Создать</button>
                </div>
            </div>
            <div id="teams-content"><p class="empty">⏳ Загрузка...</p></div>
        </div>

        <!-- Чат -->
        <div id="page-chat" class="page">
            <h2>💬 Чат команды</h2>
            <div id="chat-content">
                <p class="empty">Выберите команду для чата</p>
            </div>
        </div>
    </div>
</div>

<!-- Модальное окно для добавления проекта -->
<div class="modal" id="project-modal">
    <div class="modal-content">
        <button class="modal-close" onclick="closeProjectModal()">✕</button>
        <h2 class="modal-title">➕ Новый проект</h2>
        <input type="text" id="project-name" placeholder="Название проекта *">
        <input type="date" id="project-start" placeholder="Дата начала *">
        <input type="date" id="project-end" placeholder="Дата окончания *">
        <input type="text" id="project-desc" placeholder="Описание (необязательно)">
        <div class="form-row">
            <input type="number" id="project-client-cost" placeholder="💰 Стоимость для заказчика *" step="0.01" required>
            <input type="number" id="project-tax" placeholder="Налоговая ставка %" value="0">
        </div>
        <div class="form-row">
            <input type="number" id="project-margin" placeholder="Маржинальность %" value="0">
            <input type="number" id="project-client-id" placeholder="ID клиента (необязательно)">
        </div>
        <div style="background: rgba(167,139,250,0.1); padding: 10px; border-radius: 8px; margin: 10px 0;">
            <p style="font-size: 0.9em; color: rgba(255,255,255,0.7);">
                💡 <strong>Подсказка:</strong> 
                <span class="text-muted">Стоимость для заказчика - это сумма, которую заплатит клиент.</span>
            </p>
        </div>
        <button class="btn btn-success" id="project-submit" style="width:100%;margin-top:10px;">Создать проект</button>
    </div>
</div>

<!-- Модальное окно для добавления сотрудника -->
<div class="modal" id="employee-modal">
    <div class="modal-content">
        <button class="modal-close" onclick="closeEmployeeModal()">✕</button>
        <h2 class="modal-title">➕ Новый сотрудник</h2>
        <input type="text" id="emp-surname" placeholder="Фамилия">
        <input type="text" id="emp-name" placeholder="Имя">
        <input type="text" id="emp-patronymic" placeholder="Отчество (необязательно)">
        <input type="text" id="emp-position" placeholder="Должность">
        <input type="number" id="emp-salary" placeholder="Зарплата в месяц">
        <input type="number" id="emp-tax" placeholder="Налоговая ставка %">
        <button class="btn btn-success" id="employee-submit" style="width:100%;margin-top:10px;">Добавить сотрудника</button>
    </div>
</div>

<!-- Модальное окно для добавления оборудования -->
<div class="modal" id="equipment-modal">
    <div class="modal-content">
        <button class="modal-close" onclick="closeEquipmentModal()">✕</button>
        <h2 class="modal-title">➕ Новое оборудование</h2>
        <input type="text" id="eq-name" placeholder="Название">
        <input type="text" id="eq-type" placeholder="Тип (час/день/шт)">
        <input type="number" id="eq-price" placeholder="Цена за единицу">
        <textarea id="eq-desc" placeholder="Описание (необязательно)"></textarea>
        <button class="btn btn-success" id="equipment-submit" style="width:100%;margin-top:10px;">Добавить оборудование</button>
    </div>
</div>

<!-- Модальное окно для добавления клиента -->
<div class="modal" id="client-modal">
    <div class="modal-content">
        <button class="modal-close" onclick="closeClientModal()">✕</button>
        <h2 class="modal-title">➕ Новый клиент</h2>
        <input type="text" id="client-inn" placeholder="ИНН">
        <input type="text" id="client-type" placeholder="Тип (Физлицо/ИП/Юрлицо)">
        <input type="text" id="client-name" placeholder="Название (необязательно)">
        <input type="email" id="client-email" placeholder="Email (необязательно)">
        <input type="tel" id="client-phone" placeholder="Телефон (необязательно)">
        <button class="btn btn-success" id="client-submit" style="width:100%;margin-top:10px;">Добавить клиента</button>
    </div>
</div>

<!-- Модальное окно для добавления ресурса -->
<div class="modal" id="resource-modal">
    <div class="modal-content">
        <button class="modal-close" onclick="closeResourceModal()">✕</button>
        <h2 class="modal-title">➕ Добавить ресурс</h2>
        <input type="text" id="res-name" placeholder="Название ресурса">
        <select id="res-type">
            <option value="сотрудник">Сотрудник</option>
            <option value="исполнитель">Исполнитель</option>
            <option value="оборудование">Оборудование</option>
        </select>
        <select id="res-executor">
            <option value="">Выберите исполнителя</option>
        </select>
        <input type="text" id="res-service" placeholder="Название услуги">
        <div class="form-row">
            <input type="number" id="res-hours" placeholder="Количество часов/дней">
            <input type="number" id="res-margin" placeholder="Маржинальность %">
        </div>
        <button class="btn btn-success" id="resource-submit" style="width:100%;margin-top:10px;">Добавить ресурс</button>
    </div>
</div>

<script>
// ============================================================
// 1. СОСТОЯНИЕ
// ============================================================
var isLoginMode = true;
var isCodeStep = false;
var currentUsername = '';
var currentRole = '';
var currentUserId = null;
var currentTeamId = null;
var currentProjectId = null;

// ============================================================
// 2. DOM-ЭЛЕМЕНТЫ
// ============================================================
var authForm = document.getElementById('auth-form');
var mainContent = document.getElementById('main-content');
var formTitle = document.getElementById('form-title');
var authSubmit = document.getElementById('auth-submit');
var authStatus = document.getElementById('auth-status');
var logoutBtn = document.getElementById('logout-btn');
var userName = document.getElementById('user-name');
var userRole = document.getElementById('user-role');
var usersMenuBtn = document.getElementById('users-menu-btn');
var teamsMenuBtn = document.getElementById('teams-menu-btn');
var chatMenuBtn = document.getElementById('chat-menu-btn');

var usernameInput = document.getElementById('auth-username');
var passwordInput = document.getElementById('auth-password');
var phoneInput = document.getElementById('auth-phone');
var telegramInput = document.getElementById('auth-telegram');
var codeInput = document.getElementById('auth-code');
var registerFields = document.getElementById('register-fields');
var codeField = document.getElementById('code-field');

// ============================================================
// 3. ПРОВЕРКА ТОКЕНА
// ============================================================
var token = localStorage.getItem('session_token');

if (token && token !== 'null') {
    fetch('/api/auth/me?session_token=' + token)
        .then(function(r) {
            if (!r.ok) throw new Error('Сессия истекла');
            return r.json();
        })
        .then(function(user) {
            currentUsername = user.username || user.id;
            currentRole = user.role || 'user';
            currentUserId = user.id;
            currentTeamId = user.team_id || null;
            showMainContent();
        })
        .catch(function() {
            localStorage.removeItem('session_token');
            showAuthForm();
        });
} else {
    showAuthForm();
}

// ============================================================
// 4. ПЕРЕКЛЮЧЕНИЕ
// ============================================================
function showMainContent() {
    authForm.classList.add('hidden');
    mainContent.classList.remove('hidden');
    logoutBtn.classList.remove('hidden');
    userName.textContent = '👤 ' + currentUsername;
    userRole.textContent = currentRole.toUpperCase();
    userRole.className = 'role-badge ' + currentRole;
    userRole.classList.remove('hidden');

    var isAdmin = currentRole === 'admin';
    var hasTeam = currentTeamId !== null;

    usersMenuBtn.style.display = (isAdmin || hasTeam) ? 'inline-block' : 'none';
    teamsMenuBtn.style.display = 'inline-block';
    chatMenuBtn.style.display = 'inline-block';
    document.querySelector('.menu .btn[data-page="employees"]').style.display = isAdmin ? 'inline-block' : 'none';
    document.querySelector('.menu .btn[data-page="equipment"]').style.display = isAdmin ? 'inline-block' : 'none';
    document.querySelector('.menu .btn[data-page="clients"]').style.display = isAdmin ? 'inline-block' : 'none';

    var createTeamForm = document.getElementById('create-team-form');
    if (createTeamForm) {
        createTeamForm.style.display = 'block';
    }

    loadProjects();
}

function showAuthForm() {
    authForm.classList.remove('hidden');
    mainContent.classList.add('hidden');
    logoutBtn.classList.add('hidden');
    userRole.classList.add('hidden');
    userName.textContent = '👤 Не авторизован';
    isCodeStep = false;
    codeField.classList.add('hidden');
    authSubmit.textContent = isLoginMode ? 'Войти' : 'Зарегистрироваться';
}

// ============================================================
// 5. ПЕРЕКЛЮЧЕНИЕ РЕЖИМОВ
// ============================================================
document.addEventListener('click', function(e) {
    if (e.target.id === 'toggle-link') {
        isLoginMode = !isLoginMode;
        if (isLoginMode) {
            formTitle.textContent = 'Вход';
            authSubmit.textContent = 'Войти';
            document.getElementById('toggle-text').innerHTML = 'Нет аккаунта? <span id="toggle-link">Зарегистрироваться</span>';
            registerFields.classList.add('hidden');
            codeField.classList.add('hidden');
            isCodeStep = false;
        } else {
            formTitle.textContent = 'Регистрация';
            authSubmit.textContent = 'Зарегистрироваться';
            document.getElementById('toggle-text').innerHTML = 'Уже есть аккаунт? <span id="toggle-link">Войти</span>';
            registerFields.classList.remove('hidden');
            codeField.classList.add('hidden');
            isCodeStep = false;
        }
        authStatus.textContent = '';
        authStatus.className = 'status-msg';
    }
});

// ============================================================
// 6. ОТПРАВКА ФОРМЫ
// ============================================================
authSubmit.addEventListener('click', function() {
    var username = usernameInput.value.trim();
    var password = passwordInput.value.trim();

    if (isCodeStep) {
        verifyCode(username);
        return;
    }

    if (!username || !password) {
        showStatus('Заполните все поля', 'error');
        return;
    }

    if (isLoginMode) {
        login(username, password);
    } else {
        register(username, password);
    }
});

// ============================================================
// 7. ВХОД
// ============================================================
function login(username, password) {
    showStatus('⏳ Вход...', 'info');
    authSubmit.disabled = true;

    fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.session_token) {
            localStorage.setItem('session_token', data.session_token);
            currentUsername = username;
            requestCode(username);
        } else {
            showStatus(data.detail || 'Ошибка входа', 'error');
            authSubmit.disabled = false;
        }
    })
    .catch(function() {
        showStatus('Ошибка сервера', 'error');
        authSubmit.disabled = false;
    });
}

// ============================================================
// 8. РЕГИСТРАЦИЯ
// ============================================================
function register(username, password) {
    var phone = phoneInput.value.trim();
    var telegram = telegramInput.value.trim();

    if (!phone || !telegram) {
        showStatus('Заполните все поля', 'error');
        return;
    }

    if (!/^\\d+$/.test(telegram)) {
        showStatus('Telegram ID — только цифры', 'error');
        return;
    }

    showStatus('⏳ Регистрация...', 'info');
    authSubmit.disabled = true;

    fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: username,
            password: password,
            phone: phone,
            telegram_id: telegram
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.id) {
            showStatus('✅ Регистрация успешна! Теперь войдите.', 'success');
            isLoginMode = true;
            formTitle.textContent = 'Вход';
            authSubmit.textContent = 'Войти';
            document.getElementById('toggle-text').innerHTML = 'Нет аккаунта? <span id="toggle-link">Зарегистрироваться</span>';
            registerFields.classList.add('hidden');
            codeField.classList.add('hidden');
            isCodeStep = false;
        } else {
            showStatus(data.detail || 'Ошибка регистрации', 'error');
        }
        authSubmit.disabled = false;
    })
    .catch(function() {
        showStatus('Ошибка сервера', 'error');
        authSubmit.disabled = false;
    });
}

// ============================================================
// 9. ЗАПРОС КОДА
// ============================================================
function requestCode(username) {
    fetch('/api/auth/request-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.sent !== undefined) {
            showStatus('✅ Код отправлен в Telegram', 'success');
            isCodeStep = true;
            codeField.classList.remove('hidden');
            authSubmit.textContent = 'Подтвердить код';
            authSubmit.disabled = false;
            window._verifyUsername = username;
            codeInput.focus();
        } else {
            showStatus(data.detail || 'Ошибка отправки кода', 'error');
            authSubmit.disabled = false;
        }
    })
    .catch(function() {
        showStatus('Ошибка сервера', 'error');
        authSubmit.disabled = false;
    });
}

// ============================================================
// 10. ПРОВЕРКА КОДА
// ============================================================
function verifyCode(username) {
    var code = codeInput.value.trim();

    if (!code || code.length !== 6) {
        showStatus('Введите 6-значный код', 'error');
        return;
    }

    showStatus('⏳ Проверка...', 'info');
    authSubmit.disabled = true;

    fetch('/api/auth/verify-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, code: code })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.session_token) {
            localStorage.setItem('session_token', data.session_token);
            currentUsername = username;
            var me = fetch('/api/auth/me?session_token=' + data.session_token)
                .then(function(r) { return r.json(); })
                .then(function(user) {
                    currentRole = user.role || 'user';
                    currentUserId = user.id;
                    currentTeamId = user.team_id || null;
                    showMainContent();
                    showStatus('✅ Успешный вход!', 'success');
                });
        } else {
            showStatus(data.detail || 'Неверный код', 'error');
        }
        authSubmit.disabled = false;
    })
    .catch(function() {
        showStatus('Ошибка сервера', 'error');
        authSubmit.disabled = false;
    });
}

// ============================================================
// 11. ВЫХОД
// ============================================================
logoutBtn.addEventListener('click', function() {
    var token = localStorage.getItem('session_token');
    if (token) {
        fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_token: token })
        }).catch(function() {});
    }
    localStorage.removeItem('session_token');
    showAuthForm();
});

// ============================================================
// 12. ВСПОМОГАТЕЛЬНЫЕ
// ============================================================
function showStatus(msg, type) {
    authStatus.textContent = msg;
    authStatus.className = 'status-msg ' + (type || '');
}

// ============================================================
// 13. ПРОЕКТЫ
// ============================================================
function loadProjects() {
    var token = localStorage.getItem('session_token');
    if (!token) return;

    var tbody = document.getElementById('projects-table');
    tbody.innerHTML = '<tr><td colspan="7" class="empty">⏳ Загрузка...</td></tr>';

    fetch('/api/projects?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="empty">📭 Нет проектов</td></tr>';
                return;
            }
            var html = '';
            data.forEach(function(p) {
                var clientCost = parseFloat(p.client_cost) || 0;
                var costPrice = parseFloat(p.cost_price) || 0;
                var profit = clientCost - costPrice;
                var profitClass = profit >= 0 ? 'profit-positive' : 'profit-negative';
                var statusClass = p.status || 'created';
                html += '<tr>' +
                    '<td><strong>' + p.name + '</strong></td>' +
                    '<td><span class="status-badge ' + statusClass + '">' + (p.status || 'создан') + '</span></td>' +
                    '<td>💰 ' + clientCost.toFixed(2) + '</td>' +
                    '<td>💰 ' + costPrice.toFixed(2) + '</td>' +
                    '<td class="' + profitClass + '">💰 ' + profit.toFixed(2) + '</td>' +
                    '<td>' + (p.start_date || '—') + '</td>' +
                    '<td><button class="btn btn-sm btn-primary" onclick="loadProjectDetails(' + p.id + ')">📋 Просмотр</button></td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
        })
        .catch(function() {
            tbody.innerHTML = '<tr><td colspan="7" class="error">❌ Ошибка загрузки</td></tr>';
        });
}

function loadProjectDetails(projectId) {
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }
    
    var mainContent = document.getElementById('main-content');
    mainContent.innerHTML = '<p class="empty">⏳ Загрузка проекта...</p>';
    
    fetch('/api/projects/' + projectId + '?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var project = data.project;
            var resources = data.resources || [];
            
            var html = '<div style="margin-bottom:20px;">';
            html += '<button class="btn btn-primary" onclick="backToProjects()">← Назад к проектам</button>';
            html += '</div>';
            
            var clientCost = parseFloat(project.client_cost) || 0;
            var costPrice = parseFloat(project.cost_price) || 0;
            var profit = clientCost - costPrice;
            var profitClass = profit >= 0 ? 'profit-positive' : 'profit-negative';
            
            html += '<h2>📋 ' + project.name + '</h2>';
            html += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin:20px 0;background:rgba(255,255,255,0.03);padding:20px;border-radius:12px;">';
            html += '<div><strong>Статус:</strong> <span class="status-badge ' + (project.status || 'created') + '">' + (project.status || 'создан') + '</span></div>';
            html += '<div><strong>Дата начала:</strong> ' + (project.start_date || '—') + '</div>';
            html += '<div><strong>Дата окончания:</strong> ' + (project.end_date || '—') + '</div>';
            html += '<div><strong>Налоговая ставка:</strong> ' + (project.tax_rate || 0) + '%</div>';
            html += '<div><strong>Маржинальность:</strong> ' + (project.margin_percent || 0) + '%</div>';
            html += '<div><strong>Стоимость для заказчика:</strong> 💰 ' + clientCost.toFixed(2) + '</div>';
            html += '<div><strong>Себестоимость:</strong> 💰 ' + costPrice.toFixed(2) + '</div>';
            html += '<div><strong>Чистая прибыль:</strong> <span class="' + profitClass + '">💰 ' + profit.toFixed(2) + '</span></div>';
            html += '<div><strong>Рентабельность:</strong> ' + (costPrice > 0 ? ((profit / costPrice) * 100).toFixed(1) : 0) + '%</div>';
            html += '</div>';
            
            html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">';
            html += '<h3>🔧 Ресурсы проекта</h3>';
            html += '<button class="btn btn-success" onclick="openResourceModal(' + projectId + ')">+ Добавить ресурс</button>';
            html += '</div>';
            
            html += '<div class="table-wrap" style="margin-top:15px;"><table><thead><tr>';
            html += '<th>Название</th><th>Тип</th><th>Услуга</th><th>Дни/часы</th><th>Себестоимость</th><th>Маржинальность</th><th>Итоговая стоимость</th>';
            html += '</tr></thead><tbody>';
            
            if (!resources || resources.length === 0) {
                html += '<tr><td colspan="7" class="empty">📭 Нет ресурсов</td></tr>';
            } else {
                resources.forEach(function(r) {
                    html += '<tr>';
                    html += '<td>' + r.name + '</td>';
                    html += '<td>' + r.type + '</td>';
                    html += '<td>' + (r.service || '—') + '</td>';
                    html += '<td>' + r.days + '</td>';
                    html += '<td>💰 ' + r.cost_price + '</td>';
                    html += '<td>' + r.margin_percent + '%</td>';
                    html += '<td>💰 ' + r.total_cost + '</td>';
                    html += '</tr>';
                });
            }
            
            html += '</tbody></table></div>';
            
            mainContent.innerHTML = html;
        })
        .catch(function(err) {
            console.error('Ошибка загрузки проекта:', err);
            mainContent.innerHTML = '<p class="error">❌ Ошибка загрузки проекта</p>';
        });
}

function backToProjects() {
    var mainContent = document.getElementById('main-content');
    if (!mainContent) {
        console.error('❌ mainContent не найден');
        return;
    }
    
    mainContent.innerHTML = `
        <div class="menu">
            <button class="btn active" data-page="projects">📁 Проекты</button>
            <button class="btn" data-page="employees">👨‍💻 Сотрудники</button>
            <button class="btn" data-page="equipment">💻 Оборудование</button>
            <button class="btn" data-page="clients">🏢 Клиенты</button>
            <button class="btn" data-page="stats">📊 Статистика</button>
            <button class="btn" data-page="users" id="users-menu-btn">👥 Пользователи</button>
            <button class="btn" data-page="teams" id="teams-menu-btn">🏷️ Команды</button>
            <button class="btn" data-page="chat" id="chat-menu-btn">💬 Чат</button>
        </div>
        <div id="page-projects" class="page active">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
                <h2>📋 Проекты</h2>
                <button class="btn btn-success" onclick="openProjectModal()">+ Новый проект</button>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Название</th><th>Статус</th><th>Стоимость для клиента</th><th>Себестоимость</th><th>Прибыль</th><th>Дата</th><th>Действия</th></tr></thead>
                    <tbody id="projects-table"></tbody>
                </table>
            </div>
        </div>
    `;
    loadProjects();
}

// ============================================================
// 14. МОДАЛЬНОЕ ОКНО ПРОЕКТА (С НАЛОГОМ, МАРЖИНАЛЬНОСТЬЮ И СТОИМОСТЬЮ)
// ============================================================
function openProjectModal() {
    document.getElementById('project-modal').classList.add('active');
    document.getElementById('project-name').value = '';
    document.getElementById('project-start').value = '';
    document.getElementById('project-end').value = '';
    document.getElementById('project-desc').value = '';
    document.getElementById('project-client-cost').value = '';
    document.getElementById('project-tax').value = '0';
    document.getElementById('project-margin').value = '0';
    document.getElementById('project-client-id').value = '';
}

function closeProjectModal() {
    document.getElementById('project-modal').classList.remove('active');
}

document.getElementById('project-submit').addEventListener('click', function() {
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }
    var name = document.getElementById('project-name').value.trim();
    var start_date = document.getElementById('project-start').value;
    var end_date = document.getElementById('project-end').value;
    var description = document.getElementById('project-desc').value.trim();
    var client_cost = parseFloat(document.getElementById('project-client-cost').value);
    var tax_rate = parseFloat(document.getElementById('project-tax').value) || 0;
    var margin_percent = parseFloat(document.getElementById('project-margin').value) || 0;
    var client_id = parseInt(document.getElementById('project-client-id').value) || null;
    
    if (!name || !start_date || !end_date) {
        alert('Заполните все обязательные поля (отмечены *)');
        return;
    }
    
    if (!client_cost || client_cost <= 0) {
        alert('Укажите стоимость проекта для заказчика (сумма должна быть больше 0)');
        return;
    }
    
    fetch('/api/projects?session_token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: name,
            start_date: start_date,
            end_date: end_date,
            description: description,
            client_cost: client_cost,
            tax_rate: tax_rate,
            margin_percent: margin_percent,
            client_id: client_id
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.id) {
            alert('✅ Проект создан!');
            closeProjectModal();
            loadProjects();
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
});

document.getElementById('project-modal').addEventListener('click', function(e) {
    if (e.target === this) closeProjectModal();
});

// ============================================================
// 15. СОТРУДНИКИ
// ============================================================
function openEmployeeModal() {
    document.getElementById('employee-modal').classList.add('active');
    document.getElementById('emp-surname').value = '';
    document.getElementById('emp-name').value = '';
    document.getElementById('emp-patronymic').value = '';
    document.getElementById('emp-position').value = '';
    document.getElementById('emp-salary').value = '';
    document.getElementById('emp-tax').value = '';
}

function closeEmployeeModal() {
    document.getElementById('employee-modal').classList.remove('active');
}

document.getElementById('employee-submit').addEventListener('click', function() {
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }

    var surname = document.getElementById('emp-surname').value.trim();
    var name = document.getElementById('emp-name').value.trim();
    var patronymic = document.getElementById('emp-patronymic').value.trim();
    var position = document.getElementById('emp-position').value.trim();
    var monthly_salary = parseFloat(document.getElementById('emp-salary').value);
    var tax_rate = parseFloat(document.getElementById('emp-tax').value) || 0;

    if (!surname || !name || !position || isNaN(monthly_salary)) {
        alert('Заполните все обязательные поля');
        return;
    }

    fetch('/api/employees?session_token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            surname: surname,
            name: name,
            patronymic: patronymic,
            position: position,
            monthly_salary: monthly_salary,
            tax_rate: tax_rate
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.id) {
            alert('✅ Сотрудник добавлен!');
            closeEmployeeModal();
            loadEmployees();
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
});

document.getElementById('employee-modal').addEventListener('click', function(e) {
    if (e.target === this) closeEmployeeModal();
});

function loadEmployees() {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var tbody = document.getElementById('employees-table');
    tbody.innerHTML = '<tr><td colspan="5" class="empty">⏳ Загрузка...</td></tr>';
    
    fetch('/api/employees?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty">👤 Нет сотрудников</td></tr>';
                return;
            }
            var html = '';
            data.forEach(function(e) {
                html += '<tr>' +
                    '<td>' + e.surname + ' ' + e.name + ' ' + (e.patronymic || '') + '</td>' +
                    '<td>' + e.position + '</td>' +
                    '<td>💰 ' + e.monthly_salary + '</td>' +
                    '<td>' + e.tax_rate + '%</td>' +
                    '<td><button class="btn-delete" onclick="deleteEmployee(' + e.id + ')">🗑️ Удалить</button></td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
        })
        .catch(function() {
            tbody.innerHTML = '<tr><td colspan="5" class="error">❌ Ошибка загрузки</td></tr>';
        });
}

function deleteEmployee(employeeId) {
    if (!confirm('Вы уверены, что хотите удалить этого сотрудника?')) return;
    
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }
    
    fetch('/api/employees/' + employeeId + '?session_token=' + token, {
        method: 'DELETE'
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.message) {
            alert('✅ ' + data.message);
            loadEmployees();
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
}

// ============================================================
// 16. ОБОРУДОВАНИЕ
// ============================================================
function openEquipmentModal() {
    document.getElementById('equipment-modal').classList.add('active');
    document.getElementById('eq-name').value = '';
    document.getElementById('eq-type').value = '';
    document.getElementById('eq-price').value = '';
    document.getElementById('eq-desc').value = '';
}

function closeEquipmentModal() {
    document.getElementById('equipment-modal').classList.remove('active');
}

document.getElementById('equipment-submit').addEventListener('click', function() {
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }

    var name = document.getElementById('eq-name').value.trim();
    var unit_type = document.getElementById('eq-type').value.trim();
    var price_per_unit = parseFloat(document.getElementById('eq-price').value);
    var description = document.getElementById('eq-desc').value.trim();

    if (!name || !unit_type || isNaN(price_per_unit)) {
        alert('Заполните все обязательные поля');
        return;
    }

    fetch('/api/equipment?session_token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: name,
            unit_type: unit_type,
            price_per_unit: price_per_unit,
            description: description
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.id) {
            alert('✅ Оборудование добавлено!');
            closeEquipmentModal();
            loadEquipment();
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
});

document.getElementById('equipment-modal').addEventListener('click', function(e) {
    if (e.target === this) closeEquipmentModal();
});

function loadEquipment() {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var tbody = document.getElementById('equipment-table');
    tbody.innerHTML = '<tr><td colspan="4" class="empty">⏳ Загрузка...</td></tr>';
    
    fetch('/api/equipment?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="empty">💻 Нет оборудования</td></tr>';
                return;
            }
            var html = '';
            data.forEach(function(e) {
                html += '<tr>' +
                    '<td>' + e.name + '</td>' +
                    '<td>' + e.unit_type + '</td>' +
                    '<td>💰 ' + e.price_per_unit + '</td>' +
                    '<td><button class="btn-delete" onclick="deleteEquipment(' + e.id + ')">🗑️ Удалить</button></td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
        })
        .catch(function() {
            tbody.innerHTML = '<tr><td colspan="4" class="error">❌ Ошибка загрузки</td></tr>';
        });
}

function deleteEquipment(equipmentId) {
    if (!confirm('Вы уверены, что хотите удалить это оборудование?')) return;
    
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }
    
    fetch('/api/equipment/' + equipmentId + '?session_token=' + token, {
        method: 'DELETE'
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.message) {
            alert('✅ ' + data.message);
            loadEquipment();
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
}

// ============================================================
// 17. КЛИЕНТЫ
// ============================================================
function openClientModal() {
    document.getElementById('client-modal').classList.add('active');
    document.getElementById('client-inn').value = '';
    document.getElementById('client-type').value = '';
    document.getElementById('client-name').value = '';
    document.getElementById('client-email').value = '';
    document.getElementById('client-phone').value = '';
}

function closeClientModal() {
    document.getElementById('client-modal').classList.remove('active');
}

document.getElementById('client-submit').addEventListener('click', function() {
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }

    var inn = document.getElementById('client-inn').value.trim();
    var type = document.getElementById('client-type').value.trim();
    var name = document.getElementById('client-name').value.trim();
    var email = document.getElementById('client-email').value.trim();
    var phone = document.getElementById('client-phone').value.trim();

    if (!inn || !type) {
        alert('Заполните ИНН и тип');
        return;
    }

    fetch('/api/clients?session_token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            inn: inn,
            type: type,
            name: name,
            email: email,
            phone: phone
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.id) {
            alert('✅ Клиент добавлен!');
            closeClientModal();
            loadClients();
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
});

document.getElementById('client-modal').addEventListener('click', function(e) {
    if (e.target === this) closeClientModal();
});

function loadClients() {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var tbody = document.getElementById('clients-table');
    tbody.innerHTML = '<tr><td colspan="4" class="empty">⏳ Загрузка...</td></tr>';
    
    fetch('/api/clients?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="empty">🏢 Нет клиентов</td></tr>';
                return;
            }
            var html = '';
            data.forEach(function(c) {
                html += '<tr>' +
                    '<td>' + c.inn + '</td>' +
                    '<td>' + (c.name || c.inn) + '</td>' +
                    '<td>' + c.type + '</td>' +
                    '<td><button class="btn-delete" onclick="deleteClient(' + c.id + ')">🗑️ Удалить</button></td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
        })
        .catch(function() {
            tbody.innerHTML = '<tr><td colspan="4" class="error">❌ Ошибка загрузки</td></tr>';
        });
}

function deleteClient(clientId) {
    if (!confirm('Вы уверены, что хотите удалить этого клиента?')) return;
    
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }
    
    fetch('/api/clients/' + clientId + '?session_token=' + token, {
        method: 'DELETE'
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.message) {
            alert('✅ ' + data.message);
            loadClients();
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
}

// ============================================================
// 18. СТАТИСТИКА
// ============================================================
function loadStats() {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var content = document.getElementById('stats-content');
    content.innerHTML = '<p class="empty">⏳ Загрузка...</p>';
    
    Promise.all([
        fetch('/api/projects?session_token=' + token).then(function(r) { return r.json(); }).catch(function() { return []; }),
        fetch('/api/employees?session_token=' + token).then(function(r) { return r.json(); }).catch(function() { return []; }),
        fetch('/api/equipment?session_token=' + token).then(function(r) { return r.json(); }).catch(function() { return []; }),
        fetch('/api/clients?session_token=' + token).then(function(r) { return r.json(); }).catch(function() { return []; })
    ])
    .then(function(data) {
        var projects = data[0];
        var employees = data[1];
        var equipment = data[2];
        var clients = data[3];
        var totalClientCost = Array.isArray(projects) ? projects.reduce(function(s, p) { return s + parseFloat(p.client_cost || 0); }, 0) : 0;
        var totalCostPrice = Array.isArray(projects) ? projects.reduce(function(s, p) { return s + parseFloat(p.cost_price || 0); }, 0) : 0;
        var totalProfit = totalClientCost - totalCostPrice;
        
        content.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:20px;">' +
            '<div class="stat-card"><div class="number">' + (Array.isArray(projects) ? projects.length : 0) + '</div><div class="label">📁 Проектов</div></div>' +
            '<div class="stat-card"><div class="number">' + (Array.isArray(employees) ? employees.length : 0) + '</div><div class="label">👨‍💻 Сотрудников</div></div>' +
            '<div class="stat-card"><div class="number">' + (Array.isArray(equipment) ? equipment.length : 0) + '</div><div class="label">💻 Оборудования</div></div>' +
            '<div class="stat-card"><div class="number">' + (Array.isArray(clients) ? clients.length : 0) + '</div><div class="label">🏢 Клиентов</div></div>' +
            '<div class="stat-card"><div class="number">' + totalClientCost.toFixed(2) + '</div><div class="label">💰 Общая стоимость проектов</div></div>' +
            '<div class="stat-card"><div class="number">' + totalCostPrice.toFixed(2) + '</div><div class="label">📊 Общая себестоимость</div></div>' +
            '<div class="stat-card"><div class="number profit-positive">' + totalProfit.toFixed(2) + '</div><div class="label">📈 Общая прибыль</div></div>' +
            '</div>';
    })
    .catch(function() {
        content.innerHTML = '<p class="error">❌ Ошибка загрузки</p>';
    });
}

// ============================================================
// 19. ПОЛЬЗОВАТЕЛИ
// ============================================================
function loadUsers() {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var tbody = document.getElementById('users-table');
    tbody.innerHTML = '<tr><td colspan="6" class="empty">⏳ Загрузка...</td></tr>';
    
    fetch('/api/users?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty">👥 Нет пользователей</td></tr>';
                return;
            }
            var html = '';
            data.forEach(function(u) {
                html += '<tr>' +
                    '<td>' + u.id + '</td>' +
                    '<td>' + u.username + '</td>' +
                    '<td>' + (u.phone || '—') + '</td>' +
                    '<td>' + (u.telegram_id || '—') + '</td>' +
                    '<td><span class="role-badge ' + u.role + '">' + (u.role || 'user').toUpperCase() + '</span></td>' +
                    '<td>' + (u.team_id || '—') + '</td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
        })
        .catch(function() {
            tbody.innerHTML = '<tr><td colspan="6" class="error">❌ Ошибка загрузки</td></tr>';
        });
}

// ============================================================
// 20. КОМАНДЫ
// ============================================================
function createTeam() {
    var name = document.getElementById('team-name-input').value.trim();
    var description = document.getElementById('team-desc-input').value.trim();
    var token = localStorage.getItem('session_token');
    
    if (!name) {
        alert('Введите название команды');
        return;
    }
    
    fetch('/api/teams?session_token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, description: description })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.id) {
            alert('✅ Команда создана!');
            document.getElementById('team-name-input').value = '';
            document.getElementById('team-desc-input').value = '';
            loadTeams();
            loadUsers();
        } else {
            alert('❌ ' + (data.detail || 'Ошибка создания'));
        }
    })
    .catch(function() { alert('❌ Ошибка сервера'); });
}

function loadTeams() {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var content = document.getElementById('teams-content');
    content.innerHTML = '<p class="empty">⏳ Загрузка...</p>';
    
    fetch('/api/teams?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || data.length === 0) {
                content.innerHTML = '<p class="empty">🏷️ Нет команд</p>';
                return;
            }
            var html = '<div class="table-wrap"><table><thead><tr><th>Название</th><th>Описание</th><th>Владелец</th><th>Участников</th></tr></thead><tbody>';
            data.forEach(function(t) {
                var isOwner = t.created_by === currentUserId;
                html += '<tr><td>' + t.name + (isOwner ? ' <span class="owner-badge">👑 Владелец</span>' : '') + '</td><td>' + (t.description || '—') + '</td><td>' + (t.owner_username || '—') + '</td><td>' + t.member_count + '</td></tr>';
            });
            html += '</tbody></table></div>';
            content.innerHTML = html;
        })
        .catch(function() {
            content.innerHTML = '<p class="error">❌ Ошибка загрузки</p>';
        });
}

// ============================================================
// 21. ЧАТ
// ============================================================
function loadChat() {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var content = document.getElementById('chat-content');
    content.innerHTML = '<p class="empty">⏳ Загрузка...</p>';
    
    fetch('/api/teams?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(teams) {
            if (!teams || teams.length === 0) {
                content.innerHTML = '<p class="empty">💬 У вас нет команд. Создайте или вступите в команду, чтобы писать в чат.</p>';
                return;
            }
            var teamId = teams[0].id;
            currentTeamId = teamId;
            loadChatMessages(teamId);
        })
        .catch(function() {
            content.innerHTML = '<p class="error">❌ Ошибка загрузки</p>';
        });
}

function loadChatMessages(teamId) {
    var token = localStorage.getItem('session_token');
    if (!token) return;
    var content = document.getElementById('chat-content');
    
    fetch('/api/teams?session_token=' + token)
        .then(function(r) { return r.json(); })
        .then(function(teams) {
            var team = teams.find(function(t) { return t.id === teamId; });
            if (!team) {
                content.innerHTML = '<p class="error">❌ Команда не найдена</p>';
                return;
            }
            
            fetch('/api/chat/messages?team_id=' + teamId + '&session_token=' + token)
                .then(function(r) { return r.json(); })
                .then(function(messages) {
                    var html = '<h3>💬 Чат: ' + team.name + '</h3>';
                    html += '<div class="chat-box" id="chat-box">';
                    if (!messages || messages.length === 0) {
                        html += '<p class="empty">Нет сообщений</p>';
                    } else {
                        messages.forEach(function(m) {
                            html += '<div class="chat-message"><span class="username">' + m.username + '</span><span class="time">' + new Date(m.created_at).toLocaleTimeString() + '</span><div class="text">' + m.message + '</div></div>';
                        });
                    }
                    html += '</div>';
                    html += '<div class="chat-input"><input type="text" id="chat-input" placeholder="Введите сообщение..." /><button class="btn btn-success" onclick="sendMessage(' + teamId + ')">Отправить</button></div>';
                    content.innerHTML = html;
                    
                    var chatBox = document.getElementById('chat-box');
                    if (chatBox) {
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }
                })
                .catch(function() {
                    content.innerHTML = '<p class="error">❌ Ошибка загрузки сообщений</p>';
                });
        })
        .catch(function() {
            content.innerHTML = '<p class="error">❌ Ошибка загрузки команды</p>';
        });
}

function sendMessage(teamId) {
    if (!teamId) {
        alert('Вы не состоите в команде');
        return;
    }
    
    var token = localStorage.getItem('session_token');
    if (!token) return;
    
    var input = document.getElementById('chat-input');
    var message = input.value.trim();
    if (!message) return;
    
    fetch('/api/chat/send?session_token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team_id: teamId, message: message })
    })
    .then(function(response) {
        return response.json().then(function(data) {
            if (!response.ok) {
                if (response.status === 422) {
                    var errorMsg = 'Ошибка валидации: ';
                    if (Array.isArray(data.detail)) {
                        data.detail.forEach(function(err) {
                            errorMsg += err.loc.join('.') + ': ' + err.msg + ' ';
                        });
                    } else {
                        errorMsg += data.detail || 'Неизвестная ошибка';
                    }
                    throw new Error(errorMsg);
                }
                throw new Error(data.detail || 'Ошибка сервера');
            }
            return data;
        });
    })
    .then(function(data) {
        if (data.id) {
            input.value = '';
            loadChatMessages(teamId);
        } else {
            alert('Ошибка отправки сообщения: ' + JSON.stringify(data));
        }
    })
    .catch(function(err) {
        alert('❌ ' + err.message);
        console.error(err);
    });
}

// ============================================================
// 22. РЕСУРСЫ
// ============================================================
function openResourceModal(projectId) {
    currentProjectId = projectId;
    document.getElementById('resource-modal').classList.add('active');
    document.getElementById('res-name').value = '';
    document.getElementById('res-service').value = '';
    document.getElementById('res-hours').value = '';
    document.getElementById('res-margin').value = '';
    loadExecutors();
}

function closeResourceModal() {
    document.getElementById('resource-modal').classList.remove('active');
}

function loadExecutors() {
    var token = localStorage.getItem('session_token');
    var type = document.getElementById('res-type').value;
    var url = '';
    
    if (type === 'сотрудник') url = '/api/employees?session_token=' + token;
    else if (type === 'исполнитель') url = '/api/contractors?session_token=' + token;
    else if (type === 'оборудование') url = '/api/equipment?session_token=' + token;
    
    if (!url) return;
    
    var select = document.getElementById('res-executor');
    select.innerHTML = '<option value="">Загрузка...</option>';
    
    fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            select.innerHTML = '<option value="">Выберите исполнителя</option>';
            if (data && data.length > 0) {
                data.forEach(function(item) {
                    var name = item.name || item.surname + ' ' + item.name || item.name;
                    select.innerHTML += '<option value="' + item.id + '">' + name + '</option>';
                });
            }
        })
        .catch(function() {
            select.innerHTML = '<option value="">Ошибка загрузки</option>';
        });
}

document.getElementById('res-type').addEventListener('change', function() {
    loadExecutors();
});

document.getElementById('resource-submit').addEventListener('click', function() {
    var token = localStorage.getItem('session_token');
    if (!token) {
        alert('Вы не авторизованы');
        return;
    }
    
    var resource_name = document.getElementById('res-name').value.trim();
    var resource_type = document.getElementById('res-type').value;
    var executor_id = document.getElementById('res-executor').value;
    var service_name = document.getElementById('res-service').value.trim();
    var hours_days = parseInt(document.getElementById('res-hours').value);
    var margin_percent = parseFloat(document.getElementById('res-margin').value) || 0;
    
    if (!resource_name || !executor_id || !hours_days) {
        alert('Заполните все обязательные поля');
        return;
    }
    
    fetch('/api/projects/' + currentProjectId + '/resources?session_token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            resource_name: resource_name,
            resource_type: resource_type,
            executor_id: parseInt(executor_id),
            service_name: service_name,
            hours_days: hours_days,
            margin_percent: margin_percent,
            cost_price_value: 0,
            base_salary: 0,
            price_per_unit: 0,
            tax_rate_input: 0
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.resource_id) {
            alert('✅ Ресурс добавлен!');
            closeResourceModal();
            loadProjectDetails(currentProjectId);
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    })
    .catch(function() {
        alert('❌ Ошибка сервера');
    });
});

document.getElementById('resource-modal').addEventListener('click', function(e) {
    if (e.target === this) closeResourceModal();
});

// ============================================================
// 23. ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК
// ============================================================
document.querySelectorAll('.menu .btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.menu .btn').forEach(function(b) { b.classList.remove('active'); });
        this.classList.add('active');
        document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
        document.getElementById('page-' + this.dataset.page).classList.add('active');
        
        var page = this.dataset.page;
        if (page === 'projects') loadProjects();
        else if (page === 'employees') loadEmployees();
        else if (page === 'equipment') loadEquipment();
        else if (page === 'clients') loadClients();
        else if (page === 'stats') loadStats();
        else if (page === 'users') loadUsers();
        else if (page === 'teams') loadTeams();
        else if (page === 'chat') loadChat();
    });
});
</script>
</body>
</html>
"""

# ============================================================
# ЭНДПОИНТЫ
# ============================================================

@app.post("/api/auth/register")
def register(data: RegisterRequest, db = Depends(get_db)):
    try:
        username, password, phone, telegram_id = data.username, data.password, data.phone, data.telegram_id
        
        if not username or not password or not phone or not telegram_id:
            raise HTTPException(status_code=400, detail="Заполните все поля")
        
        if db.query(UserDB).filter(UserDB.username == username).first():
            raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
        
        if db.query(UserDB).filter(UserDB.phone == phone).first():
            raise HTTPException(status_code=400, detail="Телефон уже используется")
        
        if not telegram_id.isdigit():
            raise HTTPException(status_code=400, detail="Telegram ID должен содержать только цифры")
        
        if db.query(UserDB).filter(UserDB.telegram_id == telegram_id).first():
            raise HTTPException(status_code=400, detail="Telegram ID уже используется")
        
        hashed = hash_password(password)
        user = UserDB(
            username=username,
            hashed_password=hashed,
            phone=phone,
            telegram_id=telegram_id,
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {"message": "Регистрация успешна! Теперь войдите.", "id": user.id}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login")
def login(data: LoginRequest, db = Depends(get_db)):
    try:
        username, password = data.username, data.password
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Введите логин и пароль")
        
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        user.last_login = datetime.utcnow()
        db.commit()
        
        session_token = f"session_{int(datetime.utcnow().timestamp())}_{user.id}"
        sessions[session_token] = user.id
        
        return {"message": "Вход выполнен", "user_id": user.id, "session_token": session_token}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка входа: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/request-code")
def request_code(data: CodeRequest, db = Depends(get_db)):
    try:
        username = data.username
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if not user.telegram_id:
            raise HTTPException(status_code=400, detail="У пользователя не привязан Telegram")
        
        code = generate_code()
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        db.query(VerificationCodeDB).filter(
            VerificationCodeDB.phone == user.phone,
            VerificationCodeDB.is_used == False
        ).delete()
        
        ver_code = VerificationCodeDB(
            phone=user.phone,
            code=code,
            expires_at=expires_at
        )
        db.add(ver_code)
        db.commit()
        
        temp_codes[user.phone] = {
            "code": code,
            "expires_at": expires_at,
            "used": False
        }
        
        sent = send_telegram_code(user.telegram_id, code)
        
        if sent:
            print(f"✅ Код отправлен в Telegram для {user.username}")
        else:
            print(f"⚠️ Код НЕ отправлен. Код: {code}")
        
        return {
            "message": "Код отправлен" if sent else "Не удалось отправить код",
            "sent": sent,
            "expires_in": 300
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка запроса кода: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/verify-code")
def verify_code(data: dict, db = Depends(get_db)):
    try:
        username = data.get("username")
        code = data.get("code")
        
        if not username or not code:
            raise HTTPException(status_code=400, detail="Введите имя пользователя и код")
        
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        is_valid = False
        
        ver_code = db.query(VerificationCodeDB).filter(
            VerificationCodeDB.phone == user.phone,
            VerificationCodeDB.code == code,
            VerificationCodeDB.is_used == False,
            VerificationCodeDB.expires_at > datetime.utcnow()
        ).first()
        
        if ver_code:
            ver_code.is_used = True
            db.commit()
            is_valid = True
        elif user.phone in temp_codes:
            data = temp_codes[user.phone]
            if data["code"] == code and not data["used"] and data["expires_at"] > datetime.utcnow():
                data["used"] = True
                is_valid = True
        
        if not is_valid:
            raise HTTPException(status_code=400, detail="Неверный или истекший код")
        
        session_token = f"session_{int(datetime.utcnow().timestamp())}_{user.id}"
        sessions[session_token] = user.id
        
        return {"message": "Успешный вход", "user_id": user.id, "session_token": session_token}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка проверки кода: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/me")
def get_current_user(session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user = db.query(UserDB).filter(UserDB.id == sessions[session_token]).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            "id": user.id,
            "phone": user.phone,
            "username": user.username,
            "telegram_id": user.telegram_id,
            "role": user.role,
            "team_id": user.team_id,
            "created_at": user.created_at,
            "last_login": user.last_login
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения пользователя: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/logout")
def logout(session_token: str):
    if session_token in sessions:
        del sessions[session_token]
    return {"message": "Выход выполнен"}

@app.post("/api/auth/set-role")
def set_role(data: SetRoleRequest, session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        admin_id = sessions[session_token]
        admin = db.query(UserDB).filter(UserDB.id == admin_id).first()
        if not admin or admin.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для глобальных администраторов.")
        
        user = db.query(UserDB).filter(UserDB.username == data.username).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if data.new_role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Неверная роль. Доступны: admin, user")
        
        user.role = data.new_role
        db.commit()
        return {"message": f"Роль пользователя {data.username} изменена на {data.new_role}"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка смены роли: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 📁 КОМАНДЫ
# =================================================================

@app.post("/api/teams")
def create_team(data: CreateTeamRequest, session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.team_id is not None:
            raise HTTPException(status_code=403, detail="Вы уже состоите в команде")
        
        existing = db.query(TeamDB).filter(TeamDB.name == data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Команда с таким именем уже существует")
        
        team = TeamDB(
            name=data.name,
            description=data.description,
            created_by=user_id
        )
        db.add(team)
        db.commit()
        db.refresh(team)
        
        user.team_id = team.id
        db.commit()
        
        return {"id": team.id, "name": team.name, "message": "Команда создана успешно"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка создания команды: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/teams")
def get_teams(session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role == "admin":
            teams = db.query(TeamDB).all()
        else:
            teams = db.query(TeamDB).filter(TeamDB.id == user.team_id).all()
        
        result = []
        for t in teams:
            owner = db.query(UserDB).filter(UserDB.id == t.created_by).first()
            result.append({
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "created_at": t.created_at,
                "created_by": t.created_by,
                "owner_username": owner.username if owner else "—",
                "member_count": len(t.users)
            })
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения команд: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 📁 ПРОЕКТЫ
# =================================================================

@app.get("/api/projects")
def get_projects(session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role == "admin":
            projects = db.query(ProjectDB).all()
        else:
            projects = db.query(ProjectDB).filter(ProjectDB.owner_id == user_id).all()
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "client_cost": str(p.client_cost) if hasattr(p, 'client_cost') else "0",
                "total_cost_project": str(p.total_cost_project),
                "cost_price": str(p.cost_price),
                "pure_profit": str(p.pure_profit),
                "start_date": str(p.start_date) if p.start_date else None,
                "end_date": str(p.end_date) if p.end_date else None,
                "owner_id": p.owner_id,
                "tax_rate": str(p.tax_rate) if hasattr(p, 'tax_rate') else "0",
                "margin_percent": str(p.margin_percent) if hasattr(p, 'margin_percent') else "0"
            }
            for p in projects
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения проектов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects")
def create_project(
    session_token: str,
    data: dict,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        name = data.get("name")
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        description = data.get("description", "")
        client_cost = data.get("client_cost", 0)
        tax_rate = data.get("tax_rate", 0)
        margin_percent = data.get("margin_percent", 0)
        client_id = data.get("client_id", None)
        
        if not name or not start_date_str or not end_date_str:
            raise HTTPException(status_code=400, detail="Заполните все обязательные поля")
        
        if not client_cost or client_cost <= 0:
            raise HTTPException(status_code=400, detail="Укажите стоимость проекта для заказчика")
        
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте ГГГГ-ММ-ДД")
        
        new_project = ProjectDB(
            name=name,
            start_date=start_date,
            end_date=end_date,
            description=description,
            client_cost=Decimal(client_cost),
            tax_rate=Decimal(tax_rate),
            margin_percent=Decimal(margin_percent),
            client_id=client_id,
            status="создан",
            owner_id=user_id
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return {"id": new_project.id, "name": new_project.name, "message": "Проект создан успешно"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка создания проекта: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не найден")
        
        if user.role != "admin" and project.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Доступ запрещён. Вы не владелец проекта.")
        
        db.delete(project)
        db.commit()
        return {"message": "Проект удален"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка удаления проекта: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_id}")
def get_project_details(
    project_id: int,
    session_token: str,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не найден")
        
        if user.role != "admin" and project.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        resources = db.query(ProjectResourceDB).filter(ProjectResourceDB.project_id == project_id).all()
        
        # Пересчитываем стоимость проекта
        total_cost = Decimal(0)
        total_cost_price = Decimal(0)
        for r in resources:
            total_cost += r.total_cost
            total_cost_price += r.cost_price
        
        # Обновляем проект
        project.total_cost_project = total_cost
        project.cost_price = total_cost_price
        project.pure_profit = Decimal(str(project.client_cost)) - total_cost_price if hasattr(project, 'client_cost') else Decimal(0)
        
        db.commit()
        
        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "start_date": str(project.start_date) if project.start_date else None,
                "end_date": str(project.end_date) if project.end_date else None,
                "status": project.status,
                "client_cost": str(project.client_cost) if hasattr(project, 'client_cost') else "0",
                "tax_rate": str(project.tax_rate) if hasattr(project, 'tax_rate') else "0",
                "margin_percent": str(project.margin_percent) if hasattr(project, 'margin_percent') else "0",
                "total_cost_project": str(project.total_cost_project),
                "cost_price": str(project.cost_price),
                "pure_profit": str(project.pure_profit)
            },
            "resources": [
                {
                    "id": r.id,
                    "name": r.resource_name,
                    "type": r.resource_type,
                    "service": r.service_name,
                    "days": r.hours_days,
                    "cost_price": str(r.cost_price),
                    "margin_percent": str(r.margin_percent),
                    "total_cost": str(r.total_cost)
                }
                for r in resources
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения проекта: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# 🔥 ДОБАВЛЕНИЕ РЕСУРСА В ПРОЕКТ
# ============================================================
@app.post("/api/projects/{project_id}/resources")
def add_resource(
    project_id: int,
    session_token: str,
    data: dict,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не найден")
        
        if user.role != "admin" and project.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        resource_name = data.get("resource_name")
        resource_type = data.get("resource_type")
        executor_id = data.get("executor_id")
        service_name = data.get("service_name", "")
        hours_days = data.get("hours_days", 0)
        margin_percent = data.get("margin_percent", 0)
        
        # Расчет себестоимости (упрощенный)
        cost_price = Decimal(hours_days) * Decimal(1000)
        total_cost = cost_price * (1 + Decimal(margin_percent) / 100)
        
        new_res = ProjectResourceDB(
            project_id=project_id,
            resource_name=resource_name,
            resource_type=resource_type,
            service_name=service_name,
            executor_id=executor_id,
            hours_days=hours_days,
            cost_price=cost_price,
            margin_percent=Decimal(margin_percent),
            total_cost=total_cost
        )
        db.add(new_res)
        db.commit()
        db.refresh(new_res)
        
        # Пересчитываем стоимость проекта
        resources = db.query(ProjectResourceDB).filter(ProjectResourceDB.project_id == project_id).all()
        total_cost_all = Decimal(0)
        total_cost_price_all = Decimal(0)
        for r in resources:
            total_cost_all += r.total_cost
            total_cost_price_all += r.cost_price
        
        project.total_cost_project = total_cost_all
        project.cost_price = total_cost_price_all
        project.pure_profit = Decimal(str(project.client_cost)) - total_cost_price_all if hasattr(project, 'client_cost') else Decimal(0)
        db.commit()
        
        return {
            "resource_id": new_res.id,
            "message": "Ресурс добавлен",
            "project_total": str(project.total_cost_project),
            "pure_profit": str(project.pure_profit)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка добавления ресурса: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 📁 РЕЕСТРЫ
# =================================================================

# --- СОТРУДНИКИ ---
@app.get("/api/employees")
def get_employees(session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        employees = db.query(EmployeeDB).all()
        return [
            {
                "id": e.id,
                "surname": e.surname,
                "name": e.name,
                "patronymic": e.patronymic,
                "position": e.position,
                "monthly_salary": str(e.monthly_salary),
                "tax_rate": str(e.tax_rate)
            }
            for e in employees
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения сотрудников: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/employees")
def create_employee(
    session_token: str,
    data: dict,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        surname = data.get("surname")
        name = data.get("name")
        position = data.get("position")
        monthly_salary = data.get("monthly_salary")
        patronymic = data.get("patronymic", "")
        tax_rate = data.get("tax_rate", 0)
        
        if not surname or not name or not position or not monthly_salary:
            raise HTTPException(status_code=400, detail="Заполните все обязательные поля")
        
        emp = EmployeeDB(
            surname=surname,
            name=name,
            patronymic=patronymic,
            position=position,
            monthly_salary=Decimal(monthly_salary),
            tax_rate=Decimal(tax_rate)
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        return {"id": emp.id, "name": f"{emp.surname} {emp.name}", "message": "Сотрудник добавлен"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка создания сотрудника: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/employees/{employee_id}")
def delete_employee(employee_id: int, session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        emp = db.query(EmployeeDB).filter(EmployeeDB.id == employee_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        
        db.delete(emp)
        db.commit()
        return {"message": "Сотрудник удален"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка удаления сотрудника: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ОБОРУДОВАНИЕ ---
@app.get("/api/equipment")
def get_equipment(session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        equipment = db.query(EquipmentDB).all()
        return [
            {
                "id": e.id,
                "name": e.name,
                "description": e.description,
                "unit_type": e.unit_type,
                "price_per_unit": str(e.price_per_unit)
            }
            for e in equipment
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения оборудования: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/equipment")
def create_equipment(
    session_token: str,
    data: dict,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        name = data.get("name")
        unit_type = data.get("unit_type")
        price_per_unit = data.get("price_per_unit")
        description = data.get("description", "")
        acquisition_type = data.get("acquisition_type", "собственное")
        
        if not name or not unit_type or not price_per_unit:
            raise HTTPException(status_code=400, detail="Заполните все обязательные поля")
        
        eq = EquipmentDB(
            name=name,
            description=description,
            acquisition_type=acquisition_type,
            unit_type=unit_type,
            price_per_unit=Decimal(price_per_unit)
        )
        db.add(eq)
        db.commit()
        db.refresh(eq)
        return {"id": eq.id, "name": eq.name, "message": "Оборудование добавлено"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка создания оборудования: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/equipment/{equipment_id}")
def delete_equipment(equipment_id: int, session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        eq = db.query(EquipmentDB).filter(EquipmentDB.id == equipment_id).first()
        if not eq:
            raise HTTPException(status_code=404, detail="Оборудование не найдено")
        
        db.delete(eq)
        db.commit()
        return {"message": "Оборудование удалено"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка удаления оборудования: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- КЛИЕНТЫ ---
@app.get("/api/clients")
def get_clients(session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        clients = db.query(ClientDB).all()
        return [
            {
                "id": c.id,
                "inn": c.inn,
                "type": c.type,
                "name": c.name,
                "email": c.email,
                "phone": c.phone
            }
            for c in clients
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения клиентов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clients")
def create_client(
    session_token: str,
    data: dict,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        inn = data.get("inn")
        type = data.get("type")
        name = data.get("name", "")
        email = data.get("email", "")
        phone = data.get("phone", "")
        
        if not inn or not type:
            raise HTTPException(status_code=400, detail="Заполните ИНН и тип")
        
        cli = ClientDB(
            inn=inn,
            type=type,
            name=name,
            email=email,
            phone=phone
        )
        db.add(cli)
        db.commit()
        db.refresh(cli)
        return {"id": cli.id, "name": cli.name or cli.inn, "message": "Заказчик добавлен"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка создания заказчика: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int, session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администраторов.")
        
        cli = db.query(ClientDB).filter(ClientDB.id == client_id).first()
        if not cli:
            raise HTTPException(status_code=404, detail="Заказчик не найден")
        
        db.delete(cli)
        db.commit()
        return {"message": "Заказчик удален"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка удаления заказчика: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 📁 ПОЛЬЗОВАТЕЛИ
# =================================================================

@app.get("/api/users")
def get_users(session_token: str, db = Depends(get_db)):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.role != "admin" and user.team_id is None:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        users = db.query(UserDB).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "phone": u.phone,
                "telegram_id": u.telegram_id,
                "role": u.role,
                "team_id": u.team_id,
                "created_at": u.created_at
            }
            for u in users
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения пользователей: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 📁 ЧАТ
# =================================================================

@app.post("/api/chat/send")
def send_message(
    session_token: str,
    data: SendMessageRequest,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.team_id != data.team_id:
            raise HTTPException(status_code=403, detail="Вы не состоите в этой команде")
        
        team = db.query(TeamDB).filter(TeamDB.id == data.team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Команда не найдена")
        
        message = ChatMessageDB(
            team_id=data.team_id,
            user_id=user_id,
            message=data.message
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return {
            "id": message.id,
            "username": user.username,
            "message": message.message,
            "created_at": message.created_at
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/messages")
def get_messages(
    team_id: int,
    session_token: str,
    limit: int = 100,
    db = Depends(get_db)
):
    try:
        if session_token not in sessions:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        user_id = sessions[session_token]
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if user.team_id != team_id and user.role != "admin":
            raise HTTPException(status_code=403, detail="Вы не состоите в этой команде")
        
        messages = db.query(ChatMessageDB).filter(
            ChatMessageDB.team_id == team_id
        ).order_by(ChatMessageDB.created_at.desc()).limit(limit).all()
        
        messages = messages[::-1]
        
        return [
            {
                "id": m.id,
                "username": m.user.username if m.user else "Unknown",
                "message": m.message,
                "created_at": m.created_at
            }
            for m in messages
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения сообщений: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 📁 ГЛАВНАЯ СТРАНИЦА
# =================================================================

@app.get("/", response_class=HTMLResponse)
def serve_front():
    return HTMLResponse(content=HTML_PAGE)

# =================================================================
# 🏠 ЗАПУСК
# =================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)