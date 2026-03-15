# Импортируем типы колонок для таблиц БД
from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

# Таблица пользователей
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True) # Уникальный ID в БД
    telegram_id = Column(BigInteger, unique=True, nullable=False) # ID из Telegram
    username = Column(String, nullable=True) # Никнейм пользователя
    first_name = Column(String, nullable=True) # Имя пользователя
    registered_at = Column(DateTime, default=datetime.utcnow) # Когда нажал /start впервые

    words = relationship("UserWord", back_populates="user") # Связь с таблицей UserWord

# Таблица слов (общая база всех слов)
class WordCard(Base):
    __tablename__ = "word_cards"
    id = Column(Integer, primary_key=True, index=True)  # Уникальный ID слова
    english = Column(String, nullable=False)  # Слово на английском
    russian = Column(String, nullable=False)  # Перевод на русский
    transcription = Column(String, nullable=True)  # Транскрипция (не обязательно)
    example = Column(String, nullable=True)  # Пример использования (не обязательно)

    id_base = Column(Boolean, default=False)
    users_link = relationship("UserWord", back_populates="word") # Связь с таблицей UserWord (у каких пользователей есть это слово)

# Таблица связей (какие слова у каких пользователей)
class UserWord(Base):
    __tablename__ = "user_words"

    id = Column(Integer, primary_key=True, index=True)  # Уникальный ID записи
    user_id = Column(Integer, ForeignKey("users.id"))  # Ссылка на таблицу users
    word_id = Column(Integer, ForeignKey("word_cards.id"))  # Ссылка на таблицу word_cards

    added_at = Column(DateTime, default=datetime.utcnow) # Когда слово было добавлено пользователю

    # Обратные связи
    user = relationship("User", back_populates="words")
    word = relationship("WordCard", back_populates="users_link")