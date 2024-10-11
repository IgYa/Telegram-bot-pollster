import aiosqlite

DATABASE = 'bot.db'

class Database:
    def __init__(self):
        self.connection = None

    # Метод для створення таблиці users, якщо її ще не існує
    async def connect(self):
        self.connection = await aiosqlite.connect(DATABASE)
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language TEXT,
                is_active BOOL DEFAULT True,
                is_super BOOL DEFAULT False
            )
        ''')
        await self.connection.commit()

    async def disconnect(self):
        if self.connection:
            await self.connection.close()

    # Метод для додавання нового користувача
    async def add_user(self, telegram_id, first_name, last_name, username, language):
        await self.connection.execute('''
            INSERT INTO users (telegram_id, first_name, last_name, username, language)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, first_name, last_name, username, language))
        await self.connection.commit()

    # Метод для перевірки, чи існує користувач в базі за telegram_id
    async def get_user_by_telegram_id(self, telegram_id):
        cursor = await self.connection.execute('''
            SELECT * FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        return await cursor.fetchone()
