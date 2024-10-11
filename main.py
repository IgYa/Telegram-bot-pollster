import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram import types
from aiogram.types import FSInputFile, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from PIL import Image, ImageDraw, ImageFont
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from db import Database

load_dotenv()

# Вставте свій токен бота
API_TOKEN = os.getenv('API_TOKEN')

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Ініціалізуємо бота та диспетчер
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Константи
TOTAL_TIME = 120  # Наприклад, 120 секунд, відлік кожні 10сек, але оцінка підраховується кожну секунду
QUESTION = "Який це колір #FFFFFF ?"
CORRECT_ANSWER = 2  # Правильна відповідь (друга), максимальна оцінка 100 балів
ROW = 4  # 4 варіанти на рядок

# Створюємо об'єкт для роботи з БД
db = Database()

# Словник для збереження інформації про користувачів (їх таймери)
user_data = {}


# Функція для створення зображення з питанням
def create_question_image(text, width=600, height=200, font_size=40):
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)  # Windows
    except IOError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2
    draw.text((text_x, text_y), text, fill=(0, 0, 0), font=font)
    image_path = "question.png"
    image.save(image_path)
    return image_path


# Функція для клавіатури варіантів
def get_vote_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Black", callback_data="vote_option_1")
    builder.button(text="White", callback_data="vote_option_2")
    builder.button(text="Blue", callback_data="vote_option_3")
    builder.button(text="Red", callback_data="vote_option_4")
    builder.adjust(ROW)
    return builder.as_markup()


# Функція для розрахунку оцінки
def calculate_score(elapsed_time: int, total_time: int) -> int:
    return int((total_time - elapsed_time) / total_time * 100)


# Стартова команда з таймером
@dp.message(Command('start'))
async def start_poll(message: types.Message):
    # Отримуємо дані користувача з Телеграма
    telegram_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ''  # Може бути None
    username = message.from_user.username or ''  # Може бути None
    language = message.from_user.language_code or ''  # Може бути None

    # Перевіряємо, чи є користувач у базі
    user = await db.get_user_by_telegram_id(telegram_id)

    if user is None:
        # Якщо користувача немає, додаємо його в базу
        await db.add_user(telegram_id, first_name, last_name, username, language)
        await message.answer(f"Вітаю, {first_name}!")
    else:
        # Якщо користувач уже є в базі
        await message.answer(f"Привіт, {first_name}! Радий бачити вас знову.")

    # Створюємо зображення з питанням
    img_path = create_question_image(QUESTION)

    # Відправляємо зображення з варіантами відповідей
    try:
        photo = FSInputFile(img_path)
        await message.answer_photo(photo=photo, caption=f"{first_name}, будь ласка, оберіть відповідь:",
                                   reply_markup=get_vote_keyboard())
    except TelegramBadRequest as e:
        logging.error(f"Помилка відправки зображення: {e}")
    finally:
        os.remove(img_path)

    # Запускаємо зворотній відлік
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=TOTAL_TIME)

    # Зберігаємо інформацію про користувача і таймер
    user_data[message.from_user.id] = {'start_time': start_time, 'end_time': end_time, 'answered': False,
                                       'time_message': None}

    await message.answer(f"Зворотній відлік розпочато! У вас є {TOTAL_TIME} секунд.")

    while datetime.now() < end_time:
        # Якщо користувач уже обрав відповідь — перервати цикл
        if user_data[message.from_user.id]['answered']:
            break

        elapsed_time = (datetime.now() - start_time).seconds
        remaining_time = TOTAL_TIME - elapsed_time

        # Якщо залишився час і минуло 10 секунд
        if remaining_time % 10 == 0:
            score = calculate_score(elapsed_time, TOTAL_TIME)

            # Видаляємо попереднє повідомлення, якщо воно існує
            if user_data[message.from_user.id]['time_message'] is not None:
                try:
                    await user_data[message.from_user.id]['time_message'].delete()
                except TelegramBadRequest:
                    pass

            # Надсилаємо нове повідомлення і зберігаємо його ID
            time_message = await message.answer(f"Залишилось часу: {remaining_time} секунд. Оцінка: {score}")
            user_data[message.from_user.id]['time_message'] = time_message

        await asyncio.sleep(1)  # Оновлюємо щосекунди

    if not user_data[message.from_user.id]['answered']:
        # Коли час завершився, якщо не було відповіді
        await message.answer("Час вийшов! Оцінка 0.")
        # Видаляємо останнє повідомлення про час, якщо воно є
        if user_data[message.from_user.id]['time_message'] is not None:
            try:
                await user_data[message.from_user.id]['time_message'].delete()
            except TelegramBadRequest:
                pass

# Обробка вибору варіантів відповіді
@dp.callback_query(lambda c: c.data.startswith('vote_option_'))
async def process_vote(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_first_name = callback_query.from_user.first_name  # Отримуємо ім'я користувача
    option_selected = int(callback_query.data.split('_')[-1])

    if user_id in user_data and not user_data[user_id]['answered']:
        # Обчислюємо час, що минув з початку
        elapsed_time = (datetime.now() - user_data[user_id]['start_time']).seconds

        # Позначаємо, що користувач обрав відповідь
        user_data[user_id]['answered'] = True

        # Перевіряємо, чи відповів користувач правильно
        if option_selected == CORRECT_ANSWER:
            # Якщо відповідь правильна і час не вийшов
            if elapsed_time <= TOTAL_TIME:
                score = calculate_score(elapsed_time, TOTAL_TIME)
                await bot.send_message(user_id, f"{user_first_name}, Ваша відповідь правильна! Оцінка: {score}")
            else:
                await bot.send_message(user_id, f"{user_first_name}, час вийшов! Ви не встигли відповісти вчасно.")
        else:
            # Якщо відповідь неправильна
            await bot.send_message(user_id, f"{user_first_name}, неправильна відповідь. Оцінка: 0.")
    else:
        await bot.answer_callback_query(callback_query.id, text="Ви вже обрали відповідь або час вийшов!")

    # Відповідь на callback
    await bot.answer_callback_query(callback_query.id)


# Функція для додавання команд у меню
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Почати опитування"),
        # Додавайте інші команди тут, якщо потрібно
    ]
    await bot.set_my_commands(commands)


async def on_startup():
    # Відкриваємо сесію при старті бота
    await db.connect()


async def on_shutdown():
    # Закриваємо сесію при зупинці бота
    await db.disconnect()


# Запуск бота
async def main():
    # Встановлюємо команди меню
    await set_commands(bot)

    await on_startup()  # Відкриття сесії БД при запуску
    print("DB started")
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()  # Закриття сесії БД при завершенні роботи
        print("DB closed")


if __name__ == '__main__':
    asyncio.run(main())
