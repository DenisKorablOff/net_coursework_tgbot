# Подключаем библиотеки для работы с БД
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Загружаем переменные из .env (пароль и настройки)
load_dotenv()

# Данные из .env для работы БД
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')

# Проверка: если пароль не найден — ошибка
if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD не найден в .env! Укажи пароль в .env")

# Подключение к PostgreSQL
DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DSN)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base — базовый класс для всех моделей таблиц
Base = declarative_base()

# Функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()