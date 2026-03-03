# Подключаем библиотеки для работы
import telebot
from dotenv import load_dotenv
import os
import random
import logging

from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import engine, Base, SessionLocal
from models import WordCard, User, UserWord
from sqlalchemy import func

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание таблиц при запуске
Base.metadata.create_all(bind=engine)

# Словарь для временного хранения данных пользователя (пока добавляет слово)
user_data = {}

# Загружаем токен из .env файла
load_dotenv()
TOKEN = os.getenv('TOKEN')
# Проверка — если токена нет, бот не запустится
if TOKEN is None:
    print("Ошибка: переменная TOKEN не найдена в .env!")
    exit(1)

# Создаём экземпляр бота
bot = telebot.TeleBot(TOKEN)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Подключаемся к базе данных
    db = SessionLocal()
    try:
        # Ищем пользователя по его Telegram ID
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        # Если пользователя нет в базе — регистрируем его
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            db.add(user)
            db.flush() # Получаем ID нового пользователя

            # Привязка базовых слов из БД при первой регистрации
            common_words = db.query(WordCard).all()
            for word in common_words:
                new_link = UserWord(user_id=user.id, word_id=word.id)
                db.add(new_link)

            db.commit() # Сохраняем изменения
            print(f"Новый пользователь {user.username} зарегистрирован. Базовые слова привязаны.")
        else:
            print(f"Пользователь {user.username} уже в базе")
    # Сообщение об ошибке
    except Exception as e:
        print(f"Ошибка при регистрации пользователя: {e}")

    finally:
        db.close() # Закрываем подключение к БД

    # Кнопки главного меню
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("Добавить слово ➕"))
    markup.add(KeyboardButton("Показать случайное 🎲"))
    markup.add(KeyboardButton("Статистика 📈"))
    markup.add(KeyboardButton("Помощь 🆘"))

    # Текст приветствия
    welcome_text = (
        f"Привет 👋 {message.from_user.first_name}! Давай попрактикуемся в английском языке.\n\n"
        "Тренировки можешь проходить в удобном для себя темпе.\n\n"
        "У тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения. Для этого воспользуйся инструментами:\n\n"
        "➕ добавить слово\n"
        "🗑 удалить слово\n\n"
        "Ну что, начнём ⬇️"
    )
    bot.reply_to(message, welcome_text, reply_markup=markup)

# Обработчик кнопок главного меню
@bot.message_handler(content_types=['text'])
def handle_menu_buttons(message):
    if message.text == "Добавить слово ➕":
        add_word_start(message)

    elif message.text == "Показать случайное 🎲":
        show_next_card(message)

    elif message.text == "Статистика 📈":
        show_stats(message)

    elif message.text == "Помощь 🆘":
        send_help(message)

    elif message.text == "Удалить слово 🗑":
        delete_word_start(message)

    else:
        bot.reply_to(message, "Выберите команду из меню или используйте /help для справки")

# Обработчик команды /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        "/next — Начать тренировку (квиз)\n"
        "/add — Добавить своё слово\n"
        "/stats — Посмотреть прогресс\n\n"
        "💡 <i>Управлять словами (изменять или удалять) можно прямо во время тренировки, ответив на слово правильно!</i>"
    )
    bot.reply_to(message, help_text, parse_mode='HTML')

# Команда /add — пошаговое добавление слова
@bot.message_handler(commands=['add'])
def add_word_start(message):
    msg = bot.reply_to(message, "Отлично! Добавляем новое слово.\n\nНапиши слово на английском:")
    bot.register_next_step_handler(msg, add_word_english)

# Шаг 1: получаем английское слово
def add_word_english(message):
    english = message.text.strip()
    if not english:
        bot.reply_to(message, "Слово не может быть пустым. Попробуй /add заново.")
        return

    # Сохраняем временно в словарь user_data
    user_data[message.from_user.id] = {'english': english}

    msg = bot.reply_to(message, f"Слово: {english}\n\nТеперь напиши перевод на русский:")
    bot.register_next_step_handler(msg, add_word_russian, user_data)

# Шаг 2: получаем Русский перевод
def add_word_russian(message, user_data):
    russian = message.text.strip()
    if not russian:
        bot.reply_to(message, "Перевод не может быть пустым. Попробуй /add заново.")
        return

    user_data[message.from_user.id]['russian'] = russian

    msg = bot.reply_to(message, f"Перевод: {russian}\n\nТранскрипция (если знаешь, иначе напиши '-'):")
    bot.register_next_step_handler(msg, add_word_transcription, user_data)

# Шаг 3: получаем транскрипцию
def add_word_transcription(message, user_data):
    transcription = message.text.strip()
    user_data[message.from_user.id]['transcription'] = transcription if transcription != '-' else None

    msg = bot.reply_to(message, "Пример предложения (или напиши '-', если нет):")
    bot.register_next_step_handler(msg, add_word_save, user_data)

# Шаг 4: сохраняем слово в базу данных
def add_word_save(message, user_data):
    example = message.text.strip()
    example = example if example != '-' else None

    card_data = user_data.get(message.from_user.id)
    if not card_data:
        bot.reply_to(message, "Что-то пошло не так. Попробуй /add заново.")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()

        # Создаём новую карточку слова
        new_word = WordCard(
            english=card_data['english'],
            russian=card_data['russian'],
            transcription=card_data.get('transcription'),
            example=example
        )

        db.add(new_word)
        db.flush() # Получаем ID нового слова

        # Создаём связь: этот пользователь → это слово
        new_user_word = UserWord(
            user_id=user.id,
            word_id=new_word.id
        )
        db.add(new_user_word)
        db.commit()

        bot.reply_to(message,
                     f"Слово успешно добавлено в ваш список!\n\n"
                     f"ID: {new_word.id}\n"
                     f"Английский: {new_word.english}\n"
                     f"Русский: {new_word.russian}")

    except Exception as e:
        db.rollback() # Отменяем изменения если ошибка
        bot.reply_to(message, f"Ошибка при сохранении: {str(e)}")
        print(f"Ошибка: {e}")
    finally:
        db.close()

    # Очищаем временные данные
    if message.from_user.id in user_data:
        del user_data[message.from_user.id]

# Команда /next (квиз)
@bot.message_handler(commands=['next'])
def show_next_card(message):
    chat_id = message.chat.id
    user_tg_id = message.from_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_tg_id).first()

        # Получаем все ID слов которые есть у этого пользователя
        user_word_ids = db.query(UserWord.word_id).filter(UserWord.user_id == user.id).all()
        user_word_ids = [id_tuple[0] for id_tuple in user_word_ids]

        if not user_word_ids:
            bot.reply_to(message, "В твоем списке пока нет слов. Добавь их через /add!")
            return

        # Выбираем случайное слово из списка пользователя
        target_word_id = random.choice(user_word_ids)
        target_card = db.query(WordCard).filter(WordCard.id == target_word_id).first()

        # Правильный ответ — английское слово
        correct_answer = target_card.english

        # Получаем другие английские слова для неправильных вариантов
        other_words = db.query(WordCard.english).filter(WordCard.id != target_card.id).all()
        other_english_words = [w[0] for w in other_words]

        # Выбираем 3 случайных неправильных ответа
        wrong_answers = random.sample(other_english_words, min(3, len(other_english_words)))

        # Обработка случая когда в БД слишком мало слов
        if not other_english_words:
            bot.reply_to(message, "В базе слишком мало слов для квиза. Добавьте ещё слова через /add!")
            return

        # Собираем всё варианты и перемешиваем
        options = wrong_answers + [correct_answer]
        random.shuffle(options)

        # Создаем кнопки с вариантами ответов
        markup = InlineKeyboardMarkup(row_width=2)
        for option in options:
            is_correct = "right" if option == correct_answer else "wrong"
            markup.add(InlineKeyboardButton(option, callback_data=f"quiz_{is_correct}_{target_card.id}"))

        # Отправляем вопрос
        bot.send_message(chat_id,
                         f"Какое английское слово означает:\n\n🇷🇺 <b>{target_card.russian}</b>",
                         parse_mode='HTML',
                         reply_markup=markup)

    except Exception as e:
        bot.reply_to(message, f"Ошибка в тесте: {str(e)}")
    finally:
        db.close()


# Команда /delete — удаление слова по ID
@bot.message_handler(commands=['delete'])
def delete_word_start(message):
    msg = bot.reply_to(message, "Удаляем карточку.\n\nНапиши ID слова (число из /next или из базы):")
    bot.register_next_step_handler(msg, delete_word_confirm)

# Подтверждение удаления
def delete_word_confirm(message):
    try:
        word_id = int(message.text.strip())
    except ValueError:
        bot.reply_to(message, "ID должен быть числом. Попробуй /delete заново.")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()

        # Ищем связь пользователя с этим словом
        link = db.query(UserWord).filter(
            UserWord.user_id == user.id,
            UserWord.word_id == word_id
        ).first()

        if not link:
            bot.reply_to(message, f"Слово с ID {word_id} не найдено в ВАШЕМ списке.")
            return

        # Находим само слово чтобы показать название
        card = db.query(WordCard).filter(WordCard.id == word_id).first()

        # Удаляем только связь, слово остаётся в БД
        db.delete(link)
        db.commit()

        bot.reply_to(message,
                     f"Слово «{card.english}» удалено из вашего личного списка.\nВ общей базе оно сохранилось.")

    except Exception as e:
        db.rollback()
        bot.reply_to(message, f"Ошибка при удалении: {str(e)}")
    finally:
        db.close()

# Команда /stats — статистика
@bot.message_handler(commands=['stats'])
def show_stats(message):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()

        if not user:
            bot.reply_to(message, "Сначала нажми /start, чтобы я тебя запомнил.")
            return

        # Считаем сколько слов в личном списке пользователя
        user_total = db.query(UserWord).filter(UserWord.user_id == user.id).count()

        # Cколько всего слов в общем базе
        global_total = db.query(WordCard).count()

        response = (
            f"📊 <b>Твоя статистика:</b>\n"
            f"Слов в твоем списке: {user_total}\n\n"
            f"🌍 <b>Общая база:</b>\n"
            f"Всего слов в системе: {global_total}"
        )

        bot.reply_to(message, response, parse_mode='HTML')

    except Exception as e:
        bot.reply_to(message, f"Ошибка статистики: {str(e)}")
    finally:
        db.close()

# Функция редактирования слова (английское слово)
def edit_word_english(message, user_data):
    user_id = message.from_user.id
    english = message.text.strip()

    if english:  # Если пользователь что-то ввел
        # Проверка: только буквы и длина до 100 символов
        if not english.isalpha() or len(english) > 100:
            bot.reply_to(message, "Некорректное слово. Попробуйте снова.")
            return
        user_data[user_id]['english'] = english

    # Переход к следующему шагу — русский перевод
    msg = bot.send_message(message.chat.id,
                           "Новый перевод на русский (или Enter для пропуска):")
    bot.register_next_step_handler(msg, edit_word_russian, user_data)

# Функция редактирования слова (Русский перевод)
def edit_word_russian(message, user_data):
    user_id = message.from_user.id
    russian = message.text.strip()

    if russian: # Если пользователь что-то ввел
        # Проверка длины (до 200 символов)
        if len(russian) > 200:
            bot.reply_to(message, "Перевод слишком длинный. Попробуйте снова.")
            return
        user_data[user_id]['russian'] = russian

    # Переход к следующему шагу — транскрипция
    msg = bot.send_message(message.chat.id,
                           "Новая транскрипция (или Enter для пропуска):")
    bot.register_next_step_handler(msg, edit_word_transcription,user_data)

# Функция редактирования слова (Транскрипция)
def edit_word_transcription(message, user_data):
    user_id = message.from_user.id
    transcription = message.text.strip()

    # Если пользователь ввёл что-то
    if transcription and transcription != '-':
        user_data[user_id]['transcription'] = transcription

    # Переход к следующему шагу — пример предложения
    msg = bot.send_message(message.chat.id,
                           "Новый пример предложения (или Enter для пропуска):")
    bot.register_next_step_handler(msg, edit_word_example, user_data)

# Функция редактирования слова (пример предложения)
def edit_word_example(message, user_data):
    user_id = message.from_user.id
    example = message.text.strip()

    # Если пользователь ввёл что-то
    if example and example != '-':
        user_data[user_id]['example'] = example

    # Переход к следующему шагу — сохранение
    edit_word_save(message, user_data)

def edit_word_save(message, user_data):
    user_id = message.from_user.id

    db = SessionLocal()
    try:
        edit_data = user_data.get(user_id)
        if not edit_data:
            bot.reply_to(message, "Что-то пошло не так. Попробуйте /start")
            return

        word = db.query(WordCard).filter(WordCard.id == edit_data['edit_id']).first()
        if not word:
            bot.reply_to(message, "Слово не найдено в базе.")
            return

        user = db.query(User).filter(User.telegram_id == user_id).first()

        # Проверка прав (владеет ли пользователь этим словом)
        link = db.query(UserWord).filter(
            UserWord.user_id == user.id,
            UserWord.word_id == word.id
        ).first()

        if not link:
            bot.reply_to(message, "Это не ваше слово! Вы не можете его редактировать.")
            return

        # Обновляем поля если они были введены
        if edit_data.get('english'):
            word.english = edit_data['english']
        if edit_data.get('russian'):
            word.russian = edit_data['russian']
        if edit_data.get('transcription'):
            word.transcription = edit_data['transcription']

        db.commit()
        bot.reply_to(message, f"✅ Слово «{word.english}» успешно отредактировано!")
        logger.info(f"Пользователь {user.username} отредактировал слово: {word.english}")

    except Exception as e:
        db.rollback()
        bot.reply_to(message, f"Ошибка при редактировании: {str(e)}")
        logger.error(f"Ошибка при редактировании слова: {e}")
    finally:
        db.close()
        if user_id in user_data:
            del user_data[user_id]

# Обработка нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    db = SessionLocal()
    try:
        # Обработка ответов квиза (Правильный/Неправильный ответ)
        if call.data.startswith("quiz_"):
            parts = call.data.split("_")
            status = parts[1]  # right или wrong
            word_id = int(parts[2])
            card = db.query(WordCard).filter(WordCard.id == word_id).first()

            if status == "right":
                bot.answer_callback_query(call.id, "✅ Верно!")

                # Всплывающее окно при правильном ответе
                res = f"✅ <b>Правильно!</b>\n\n🇬🇧 {card.english} = 🇷🇺 {card.russian}"
                if card.example:
                    res += f"\n\nПример: {card.example}"

                # Кнопки для управления после правильного ответа
                markup = InlineKeyboardMarkup(row_width=2)
                btn_next = InlineKeyboardButton("Следующее слово ➡️", callback_data="next_card")
                btn_edit = InlineKeyboardButton("Изменить ✏️", callback_data=f"edit_{card.id}")
                btn_delete = InlineKeyboardButton("Удалить из моего списка 🗑", callback_data=f"delete_{card.id}")

                markup.add(btn_next)
                markup.add(btn_edit, btn_delete)

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=res,
                    parse_mode='HTML',
                    reply_markup=markup
                )

            elif status == "wrong":
                bot.answer_callback_query(call.id, "❌ Неверно, попробуйте ещё раз!")
                bot.send_message(
                    call.message.chat.id,
                    f"❌ <b>Неверно!</b>\n\nПопробуйте ещё раз для слова:\n🇬🇧 <b>{card.english}</b>",
                    parse_mode='HTML'
                )

        # Следующая карточка
        elif call.data == "next_card":
            show_next_card(call.message)

        # Удаление слова
        elif call.data.startswith("delete_"):
            word_id = int(call.data.split("_")[1])
            user = db.query(User).filter(User.telegram_id == call.from_user.id).first()

            # Удаление только связи пользователя со словом
            link = db.query(UserWord).filter(UserWord.user_id == user.id, UserWord.word_id == word_id).first()
            if link:
                db.delete(link)
                db.commit()
                bot.answer_callback_query(call.id, "Слово удалено из вашего списка")
                bot.edit_message_text("Слово удалено из вашего списка.", call.message.chat.id, call.message.message_id)

        # Редактирование слова
        elif call.data.startswith("edit_"):
            word_id = int(call.data.split("_")[1])
            user = db.query(User).filter(User.telegram_id == call.from_user.id).first()

            link = db.query(UserWord).filter(
                UserWord.user_id == user.id,
                UserWord.word_id == word_id
            ).first()

            if not link:
                bot.answer_callback_query(call.id, "❌ Это не ваше слово!")
                return

            user_data[call.from_user.id] = {'edit_id': word_id}
            msg = bot.send_message(call.message.chat.id,
                                   "Введите новое значение для английского слова (или Enter для пропуска):")
            bot.register_next_step_handler(msg, edit_word_english, user_data)

    # Сообщение об ошибке
    except Exception as e:
        print(f"Ошибка в callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


# Запуск бота
if __name__ == '__main__':
    print('Bot is running')
    bot.polling()