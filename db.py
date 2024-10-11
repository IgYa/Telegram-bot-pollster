import aiosqlite

DATABASE = 'bot.db'

# Функція для створення таблиці users, якщо її ще не існує
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language TEXT
            )
        ''')
        await db.commit()

# Функція для додавання нового користувача
async def add_user(telegram_id, first_name, last_name, username, language):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            INSERT INTO users (telegram_id, first_name, last_name, username, language)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, first_name, last_name, username, language))
        await db.commit()

# Функція для перевірки, чи існує користувач в базі за telegram_id
async def get_user_by_telegram_id(telegram_id):
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute('''
            SELECT * FROM users WHERE telegram_id = ?
        ''', (telegram_id,)) as cursor:
            return await cursor.fetchone()
