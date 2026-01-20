import telebot
from dotenv import load_dotenv
import os
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Подключаем базу данных и модели
from database import engine, Base, SessionLocal
from models import WordCard
from sqlalchemy import func

# Создаём таблицы один раз при запуске (если их ещё нет)
Base.metadata.create_all(bind=engine)

# Временное хранилище для многошаговых процессов (/add и /edit)
user_data = {}

# Загружаем телеграм токен
load_dotenv()
TOKEN = os.getenv('TOKEN')

if TOKEN is None:
    print("Ошибка: переменная TOKEN не найдена в .env!")
    exit(1)

bot = telebot.TeleBot(TOKEN)


# ────────────────────────────────────────────────
# Стартовое меню
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("Добавить слово (/add)"))
    markup.add(KeyboardButton("Показать случайное (/next)"))
    markup.add(KeyboardButton("Статистика (/stats)"))
    markup.add(KeyboardButton("Помощь (/help)"))

    bot.reply_to(message,
                 "Привет! Я бот для изучения английских слов.\n\n"
                 "Что хочешь сделать?",
                 reply_markup=markup)


# Помощь
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "Я знаю команды:\n"
        "/start — приветствие и меню\n"
        "/help — эта помощь\n"
        "/add — добавить новое слово\n"
        "/next — показать случайную карточку\n"
        "/stats — статистика\n"
        "/delete — удалить карточку по ID\n\n"
        "Также под карточкой есть кнопки: Следующая, Повторить, Удалить, Изменить"
    )
    bot.reply_to(message, help_text)


# ────────────────────────────────────────────────
# Команда /add — пошаговое добавление слова
@bot.message_handler(commands=['add'])
def add_word_start(message):
    msg = bot.reply_to(message, "Отлично! Добавляем новое слово.\n\nНапиши слово на английском:")
    bot.register_next_step_handler(msg, add_word_english)


def add_word_english(message):
    english = message.text.strip()
    if not english:
        bot.reply_to(message, "Слово не может быть пустым. Попробуй /add заново.")
        return

    user_data[message.from_user.id] = {'english': english}

    msg = bot.reply_to(message, f"Слово: {english}\n\nТеперь напиши перевод на русский:")
    bot.register_next_step_handler(msg, add_word_russian, user_data)


def add_word_russian(message, user_data):
    russian = message.text.strip()
    if not russian:
        bot.reply_to(message, "Перевод не может быть пустым. Попробуй /add заново.")
        return

    user_data[message.from_user.id]['russian'] = russian

    msg = bot.reply_to(message, f"Перевод: {russian}\n\nТранскрипция (если знаешь, иначе напиши '-'):")
    bot.register_next_step_handler(msg, add_word_transcription, user_data)


def add_word_transcription(message, user_data):
    transcription = message.text.strip()
    user_data[message.from_user.id]['transcription'] = transcription if transcription != '-' else None

    msg = bot.reply_to(message, "Пример предложения (или напиши '-', если нет):")
    bot.register_next_step_handler(msg, add_word_save, user_data)


def add_word_save(message, user_data):
    example = message.text.strip()
    example = example if example != '-' else None

    card = user_data.get(message.from_user.id)
    if not card:
        bot.reply_to(message, "Что-то пошло не так. Попробуй /add заново.")
        return

    db = SessionLocal()
    try:
        new_card = WordCard(
            english=card['english'],
            russian=card['russian'],
            transcription=card.get('transcription'),
            example=example
        )
        db.add(new_card)
        db.commit()
        db.refresh(new_card)

        bot.reply_to(message,
                     f"Слово успешно добавлено!\n\n"
                     f"ID: {new_card.id}\n"
                     f"Английский: {new_card.english}\n"
                     f"Русский: {new_card.russian}")
    except Exception as e:
        db.rollback()
        bot.reply_to(message, f"Ошибка при сохранении: {str(e)}")
    finally:
        db.close()

    # Очищаем временные данные
    if message.from_user.id in user_data:
        del user_data[message.from_user.id]


# ────────────────────────────────────────────────
# Команда /next — показывает случайную карточку с кнопками
@bot.message_handler(commands=['next'])
def show_next_card(message):
    db = SessionLocal()
    try:
        random_card = db.query(WordCard).order_by(func.random()).first()

        if not random_card:
            bot.reply_to(message, "В базе пока нет слов. Добавь первое через /add!")
            return

        # Формируем текст карточки
        response = f"Слово для повторения:\n\n"
        response += f"🇬🇧 <b>{random_card.english}</b>\n"

        if random_card.transcription:
            response += f"Транскрипция: {random_card.transcription}\n"

        response += f"🇷🇺 {random_card.russian}\n"

        if random_card.example:
            response += f"\nПример:\n{random_card.example}\n\n"

        response += f"ID: {random_card.id}"

        # Создаём inline-кнопки
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("Следующая карточка", callback_data="next_card"))
        markup.add(InlineKeyboardButton("Повторить эту", callback_data=f"repeat_{random_card.id}"))
        markup.add(InlineKeyboardButton("Удалить эту", callback_data=f"delete_{random_card.id}"))
        markup.add(InlineKeyboardButton("Изменить", callback_data=f"edit_{random_card.id}"))

        bot.reply_to(message, response, parse_mode='HTML', reply_markup=markup)

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")
    finally:
        db.close()


# ────────────────────────────────────────────────
# Команда /delete — удаление по ID
@bot.message_handler(commands=['delete'])
def delete_word_start(message):
    msg = bot.reply_to(message, "Удаляем карточку.\n\nНапиши ID слова (число из /next или из базы):")
    bot.register_next_step_handler(msg, delete_word_confirm)


def delete_word_confirm(message):
    try:
        word_id = int(message.text.strip())
    except ValueError:
        bot.reply_to(message, "ID должен быть числом. Попробуй /delete заново.")
        return

    db = SessionLocal()
    try:
        card = db.query(WordCard).filter(WordCard.id == word_id).first()
        if not card:
            bot.reply_to(message, f"Карточка с ID {word_id} не найдена.")
            return

        db.delete(card)
        db.commit()

        bot.reply_to(message, f"Карточка удалена!\nID: {word_id}\nСлово: {card.english} — {card.russian}")
    except Exception as e:
        db.rollback()
        bot.reply_to(message, f"Ошибка при удалении: {str(e)}")
    finally:
        db.close()


# ────────────────────────────────────────────────
# Команда /stats — статистика
@bot.message_handler(commands=['stats'])
def show_stats(message):
    db = SessionLocal()
    try:
        total = db.query(WordCard).count()
        bot.reply_to(message, f"Всего карточек в базе: {total}")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")
    finally:
        db.close()


# ────────────────────────────────────────────────
# Обработка нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    db = SessionLocal()
    try:
        if call.data == "next_card":
            show_next_card(call.message)

        elif call.data.startswith("delete_"):
            word_id = int(call.data.split("_")[1])
            card = db.query(WordCard).filter(WordCard.id == word_id).first()
            if card:
                db.delete(card)
                db.commit()
                bot.answer_callback_query(call.id, "Карточка удалена!", show_alert=True)
                bot.edit_message_text("Карточка удалена.", call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "Карточка не найдена.", show_alert=True)

        elif call.data.startswith("edit_"):
            word_id = int(call.data.split("_")[1])
            card = db.query(WordCard).filter(WordCard.id == word_id).first()
            if not card:
                bot.answer_callback_query(call.id, "Карточка не найдена.", show_alert=True)
                return

            user_data[call.from_user.id] = {'edit_id': word_id}

            response = f"Редактируем карточку ID {word_id}\n\n"
            response += f"Текущее английское слово: <b>{card.english}</b>\n\n"
            response += "Новое английское слово (или Enter, чтобы оставить):"

            msg = bot.send_message(call.message.chat.id, response, parse_mode='HTML')
            bot.register_next_step_handler(msg, edit_english, user_data, call.message.chat.id)

        elif call.data.startswith("repeat_"):
            word_id = int(call.data.split("_")[1])
            card = db.query(WordCard).filter(WordCard.id == word_id).first()
            if card:
                response = f"Повторяем карточку:\n\n"
                response += f"🇬🇧 <b>{card.english}</b>\n"
                if card.transcription:
                    response += f"Транскрипция: {card.transcription}\n"
                response += f"🇷🇺 {card.russian}\n"
                if card.example:
                    response += f"\nПример:\n{card.example}"
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(InlineKeyboardButton("Следующая карточка", callback_data="next_card"))
                markup.add(InlineKeyboardButton("Повторить эту", callback_data=f"repeat_{word_id}"))
                markup.add(InlineKeyboardButton("Удалить эту", callback_data=f"delete_{word_id}"))
                markup.add(InlineKeyboardButton("Изменить", callback_data=f"edit_{word_id}"))
                bot.edit_message_text(response, call.message.chat.id, call.message.message_id,
                                      parse_mode='HTML', reply_markup=markup)
            else:
                bot.answer_callback_query(call.id, "Карточка не найдена.", show_alert=True)

    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}", show_alert=True)
    finally:
        db.close()


# Шаги редактирования (все функции edit_... остаются без изменений)
# (вставь их сюда, если они у тебя ещё не в файле — код из предыдущего сообщения)


if __name__ == '__main__':
    print('Bot is running')
    bot.polling()