from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Date, Boolean, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    phone = Column(String, unique=True)
    telegram_id = Column(String, unique=True)
    role = Column(String, default="user")  # admin, user
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Явно указываем foreign_keys для связи с командой
    team = relationship("TeamDB", foreign_keys=[team_id], back_populates="users")
    messages = relationship("ChatMessageDB", foreign_keys="[ChatMessageDB.user_id]", back_populates="user")
    projects = relationship("ProjectDB", foreign_keys="[ProjectDB.owner_id]", back_populates="owner")

class TeamDB(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    description = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Явно указываем foreign_keys для связи с пользователями
    users = relationship("UserDB", foreign_keys=[UserDB.team_id], back_populates="team")
    messages = relationship("ChatMessageDB", foreign_keys="[ChatMessageDB.team_id]", back_populates="team")

class ProjectDB(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(Text, default="")
    status = Column(String, default="создан")  # создан, в работе, завершен, отменен
    start_date = Column(Date)
    end_date = Column(Date)
    
    # Финансовые поля
    client_cost = Column(Numeric(10, 2), default=0)  # стоимость для заказчика
    total_cost_project = Column(Numeric(10, 2), default=0)  # общая стоимость проекта
    cost_price = Column(Numeric(10, 2), default=0)  # себестоимость
    pure_profit = Column(Numeric(10, 2), default=0)  # чистая прибыль
    tax_rate = Column(Numeric(5, 2), default=0)  # налоговая ставка
    margin_percent = Column(Numeric(5, 2), default=0)  # маржинальность
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Явно указываем foreign_keys для связей
    owner = relationship("UserDB", foreign_keys=[owner_id], back_populates="projects")
    client = relationship("ClientDB", foreign_keys=[client_id], back_populates="projects")
    resources = relationship("ProjectResourceDB", foreign_keys="[ProjectResourceDB.project_id]", back_populates="project")

class ProjectResourceDB(Base):
    __tablename__ = "project_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    resource_name = Column(String)
    resource_type = Column(String)  # сотрудник, исполнитель, оборудование
    service_name = Column(String, default="")
    executor_id = Column(Integer)
    hours_days = Column(Integer, default=0)  # количество часов или дней
    cost_price = Column(Numeric(10, 2), default=0)  # себестоимость ресурса
    margin_percent = Column(Numeric(5, 2), default=0)  # маржинальность ресурса
    total_cost = Column(Numeric(10, 2), default=0)  # итоговая стоимость с маржинальностью
    
    project = relationship("ProjectDB", foreign_keys=[project_id], back_populates="resources")

class EmployeeDB(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    surname = Column(String)
    name = Column(String)
    patronymic = Column(String, default="")
    position = Column(String)
    monthly_salary = Column(Numeric(10, 2))
    tax_rate = Column(Numeric(5, 2), default=0)

class ContractorDB(Base):
    __tablename__ = "contractors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    inn = Column(String, unique=True)
    phone = Column(String)
    email = Column(String)
    rate_per_hour = Column(Numeric(10, 2))
    tax_rate = Column(Numeric(5, 2), default=0)

class EquipmentDB(Base):
    __tablename__ = "equipment"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(Text, default="")
    acquisition_type = Column(String, default="собственное")  # собственное, аренда
    unit_type = Column(String)  # час, день, шт
    price_per_unit = Column(Numeric(10, 2))

class ClientDB(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    inn = Column(String, unique=True)
    type = Column(String)  # Физлицо, ИП, Юрлицо
    name = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")
    
    projects = relationship("ProjectDB", foreign_keys="[ProjectDB.client_id]", back_populates="client")

class VerificationCodeDB(Base):
    __tablename__ = "verification_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String)
    code = Column(String)
    expires_at = Column(DateTime)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatMessageDB(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Явно указываем foreign_keys для связей
    user = relationship("UserDB", foreign_keys=[user_id], back_populates="messages")
    team = relationship("TeamDB", foreign_keys=[team_id], back_populates="messages")