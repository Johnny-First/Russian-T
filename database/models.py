import aiosqlite
from ..config.settings import settings

DB_PATH = settings.DB_PATH
 
class DatabaseManager:
    """Основной класс для управления базой данных"""
    
    @staticmethod
    async def create_all_tables():
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    total_questions INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_text TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    difficulty_level TEXT DEFAULT 'beginner',
                    explanation TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    answer_text TEXT NOT NULL,
                    is_correct BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (question_id) REFERENCES questions (id)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    questions_answered INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    answer_id INTEGER NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (question_id) REFERENCES questions (id),
                    FOREIGN KEY (answer_id) REFERENCES answers (id)
                )
            ''')
            await conn.commit()


class UserManager:
    """Класс для управления пользователями"""
    
    @staticmethod
    async def add_user(user_id: int, username: str, first_name: str, last_name: str):
        """Добавление нового пользователя"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
                (user_id, username, first_name, last_name)
            )
            await conn.commit()
    
    @staticmethod
    async def get_user_stats(user_id: int):
        """Получение статистики пользователя"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT total_questions, correct_answers FROM users WHERE user_id = ?',
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result:
                total, correct = result
                accuracy = (correct / total * 100) if total > 0 else 0
                return {
                    'total_questions': total,
                    'correct_answers': correct,
                    'accuracy': round(accuracy, 1)
                }
            return None
    
    @staticmethod
    async def update_user_stats(user_id: int, is_correct: bool):
        """Обновление статистики пользователя"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                '''UPDATE users 
                SET total_questions = total_questions + 1,
                    correct_answers = correct_answers + ?
                WHERE user_id = ?''',
                (1 if is_correct else 0, user_id)
            )
            await conn.commit()
    
    @staticmethod
    async def update_user_level(user_id: int, level: str):
        return  # убрали уровни пользователя


class MessageManager:
    """Класс для управления сообщениями"""
    
    @staticmethod
    async def get_message_count(user_id: int):
        """Получение количества сообщений пользователя"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT COUNT(*) FROM messages WHERE user_id = ?',
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
        return result[0] if result else 0
    
    @staticmethod
    async def add_message(user_id: int, role: str, message: str):
        """Добавление нового сообщения с ограничением на 5 сообщений"""
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем количество сообщений пользователя
            message_count = await MessageManager.get_message_count(user_id)
            
            if message_count >= 5:
                # Если сообщений уже 5, удаляем самое старое
                await conn.execute(
                    'DELETE FROM messages WHERE user_id = ? AND id = (SELECT MIN(id) FROM messages WHERE user_id = ?)',
                    (user_id, user_id)
                )
            
            # Добавляем новое сообщение
            await conn.execute(
                'INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)',
                (user_id, role, message)
            )
            await conn.commit()

    @staticmethod
    async def get_history(user_id, limit=10):
        """Получение истории сообщений пользователя"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]


class CategoryManager:
    """Класс для управления категориями"""
    
    @staticmethod
    async def add_category(name: str):
        """Добавление новой категории"""
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute(
                    '''INSERT INTO categories (name) 
                    VALUES (?) 
                    ON CONFLICT(name) 
                        DO UPDATE SET name = excluded.name;''',
                    (name,)
                )
                await conn.commit()
        except Exception as e:
            print(f"Ошибка в add_category: {e}")  
            raise e
    
    @staticmethod
    async def delete_category(category_id: int):
        """Удаление категории и всех вопросов в ней"""
        async with aiosqlite.connect(DB_PATH) as conn:
            # Получаем все вопросы в категории
            async with conn.execute('SELECT id FROM questions WHERE category_id = ?', (category_id,)) as cursor:
                question_ids = await cursor.fetchall()
            
            # Удаляем ответы на эти вопросы
            for question_id in question_ids:
                await conn.execute('DELETE FROM answers WHERE question_id = ?', (question_id[0],))
                await conn.execute('DELETE FROM user_answers WHERE question_id = ?', (question_id[0],))
            
            # Удаляем вопросы
            await conn.execute('DELETE FROM questions WHERE category_id = ?', (category_id,))
            
            # Удаляем прогресс пользователей по этой категории
            await conn.execute('DELETE FROM user_progress WHERE category_id = ?', (category_id,))
            
            # Удаляем саму категорию
            await conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            await conn.commit()

    @staticmethod
    async def get_all_categories():
        """Получить все категории для админ-панели"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT id, name, is_active FROM categories ORDER BY created_at DESC') as cursor:
                categories = await cursor.fetchall()
        return categories
    
    @staticmethod
    async def get_available_categories():
        """Получить только доступные категории (is_active = 1), без ранжирования по уровню"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT id, name FROM categories WHERE is_active = 1 ORDER BY name') as cursor:
                categories = await cursor.fetchall()
        return categories

    @staticmethod
    async def get_category_by_id(category_id: int):
        """Получение категории по ID"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT id, name FROM categories WHERE id = ?', 
                                  (category_id,)) as cursor:
                result = await cursor.fetchone()
        return result
    
    @staticmethod
    async def update_category_status(category_id: int, is_active: bool):
        """Обновление статуса категории"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'UPDATE categories SET is_active = ? WHERE id = ?',
                (is_active, category_id)
            )
            await conn.commit()


class QuestionManager:
    """Класс для управления вопросами"""
    
    @staticmethod
    async def add_question(question_text: str, category_id: int, difficulty_level: str = 'beginner', explanation: str = None):
        """Добавление нового вопроса"""
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                'INSERT INTO questions (question_text, category_id, difficulty_level, explanation) VALUES (?, ?, ?, ?)',
                (question_text, category_id, difficulty_level, explanation)
            )
            question_id = cursor.lastrowid
            await conn.commit()
            return question_id
    
    @staticmethod
    async def add_answer(question_id: int, answer_text: str, is_correct: bool = False):
        """Добавление ответа к вопросу"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'INSERT INTO answers (question_id, answer_text, is_correct) VALUES (?, ?, ?)',
                (question_id, answer_text, is_correct)
            )
            await conn.commit()
    
    @staticmethod
    async def delete_question(question_id: int):
        """Удаление вопроса и всех его ответов"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('DELETE FROM answers WHERE question_id = ?', (question_id,))
            await conn.execute('DELETE FROM user_answers WHERE question_id = ?', (question_id,))
            await conn.execute('DELETE FROM questions WHERE id = ?', (question_id,))
            await conn.commit()
    
    @staticmethod
    async def get_questions_by_category(category_id: int, limit: int = 10):
        """Получить вопросы по категории"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT id, question_text, difficulty_level, explanation FROM questions WHERE category_id = ? AND is_active = 1 ORDER BY RANDOM() LIMIT ?',
                (category_id, limit)
            ) as cursor:
                questions = await cursor.fetchall()
        return questions
    
    @staticmethod
    async def get_question_with_answers(question_id: int):
        """Получить вопрос с ответами"""
        async with aiosqlite.connect(DB_PATH) as conn:
            # Получаем вопрос
            async with conn.execute(
                'SELECT id, question_text, difficulty_level, explanation FROM questions WHERE id = ?',
                (question_id,)
            ) as cursor:
                question = await cursor.fetchone()
            
            if not question:
                return None
            
            # Получаем ответы
            async with conn.execute(
                'SELECT id, answer_text, is_correct FROM answers WHERE question_id = ? ORDER BY RANDOM()',
                (question_id,)
            ) as cursor:
                answers = await cursor.fetchall()
            
            return {
                'question': question,
                'answers': answers
            }
    
    @staticmethod
    async def get_random_question_by_category(category_id: int):
        """Получить случайный вопрос по категории"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT id FROM questions WHERE category_id = ? AND is_active = 1 ORDER BY RANDOM() LIMIT 1',
                (category_id,)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result:
                return await QuestionManager.get_question_with_answers(result[0])
            return None

    @staticmethod
    async def get_random_question_global_all():
        """Получить случайный активный вопрос из всех категорий (без фильтра по ответам)"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT id FROM questions WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1'
            ) as cursor:
                result = await cursor.fetchone()
        if result:
            return await QuestionManager.get_question_with_answers(result[0])
        return None

    @staticmethod
    async def get_random_question_global_answered(user_id: int):
        """Получить случайный активный вопрос из всех категорий, на который пользователь уже отвечал"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                '''
                SELECT q.id
                FROM questions q
                INNER JOIN user_answers ua ON q.id = ua.question_id
                WHERE q.is_active = 1 AND ua.user_id = ?
                ORDER BY RANDOM() LIMIT 1
                ''',
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
        if result:
            return await QuestionManager.get_question_with_answers(result[0])
        return None

    @staticmethod
    async def get_random_question_by_category_answered(user_id: int, category_id: int):
        """Получить случайный активный вопрос из категории, на который пользователь уже отвечал"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                '''
                SELECT DISTINCT q.id
                FROM questions q
                INNER JOIN user_answers ua ON q.id = ua.question_id
                WHERE q.is_active = 1 AND q.category_id = ? AND ua.user_id = ?
                ORDER BY RANDOM() LIMIT 1
                ''',
                (category_id, user_id)
            ) as cursor:
                result = await cursor.fetchone()
        if result:
            return await QuestionManager.get_question_with_answers(result[0])
        return None

    @staticmethod
    async def get_random_question_by_category_answered_excluding(user_id: int, category_id: int, excluded_question_ids: list):
        """Получить случайный активный вопрос из категории, на который пользователь уже отвечал, исключая указанные ID"""
        if not excluded_question_ids:
            return await QuestionManager.get_random_question_by_category_answered(user_id, category_id)
        
        placeholders = ','.join(['?' for _ in excluded_question_ids])
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                f'''
                SELECT DISTINCT q.id
                FROM questions q
                INNER JOIN user_answers ua ON q.id = ua.question_id
                WHERE q.is_active = 1 AND q.category_id = ? AND ua.user_id = ? 
                AND q.id NOT IN ({placeholders})
                ORDER BY RANDOM() LIMIT 1
                ''',
                (category_id, user_id) + tuple(excluded_question_ids)
            ) as cursor:
                result = await cursor.fetchone()
        if result:
            return await QuestionManager.get_question_with_answers(result[0])
        return None

    @staticmethod
    async def get_unseen_random_question_by_category(user_id: int, category_id: int):
        """Случайный активный вопрос по категории, который пользователь еще не видел"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                '''
                SELECT q.id
                FROM questions q
                WHERE q.category_id = ?
                  AND q.is_active = 1
                  AND NOT EXISTS (
                    SELECT 1 FROM user_answers ua
                    WHERE ua.user_id = ? AND ua.question_id = q.id AND ua.is_correct = 1
                  )
                ORDER BY RANDOM()
                LIMIT 1
                ''',
                (category_id, user_id)
            ) as cursor:
                result = await cursor.fetchone()
        if result:
            return await QuestionManager.get_question_with_answers(result[0])
        return None

    @staticmethod
    async def get_unseen_random_question_global(user_id: int):
        """Случайный активный вопрос из любых категорий, который пользователь еще не видел"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                '''
                SELECT q.id
                FROM questions q
                WHERE q.is_active = 1
                  AND NOT EXISTS (
                    SELECT 1 FROM user_answers ua
                    WHERE ua.user_id = ? AND ua.question_id = q.id AND ua.is_correct = 1
                  )
                ORDER BY RANDOM()
                LIMIT 1
                ''',
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
        if result:
            return await QuestionManager.get_question_with_answers(result[0])
        return None
    
    @staticmethod
    async def update_question_status(question_id: int, is_active: bool):
        """Обновление статуса вопроса"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'UPDATE questions SET is_active = ? WHERE id = ?',
                (is_active, question_id)
            )
            await conn.commit()

    @staticmethod
    async def get_question_status(question_id: int):
        """Получить текущий статус активности вопроса"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT is_active FROM questions WHERE id = ?',
                (question_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return bool(row[0]) if row else False

    @staticmethod
    async def update_question(question_id: int, question_text: str, difficulty_level: str, explanation: str | None):
        """Обновить текст, сложность и объяснение вопроса"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'UPDATE questions SET question_text = ?, difficulty_level = ?, explanation = ? WHERE id = ?',
                (question_text, difficulty_level, explanation, question_id)
            )
            await conn.commit()

    @staticmethod
    async def delete_answers_for_question(question_id: int):
        """Удалить все ответы для вопроса"""
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('DELETE FROM answers WHERE question_id = ?', (question_id,))
            await conn.commit()
    
    @staticmethod
    async def get_all_questions_by_category(category_id: int):
        """Получить все вопросы категории для админ-панели"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT id, question_text, difficulty_level, is_active FROM questions WHERE category_id = ? ORDER BY created_at DESC',
                (category_id,)
            ) as cursor:
                questions = await cursor.fetchall()
        return questions


class ProgressManager:
    """Класс для управления прогрессом пользователей"""
    
    @staticmethod
    async def record_answer(user_id: int, question_id: int, answer_id: int, is_correct: bool):
        """Запись ответа пользователя"""
        async with aiosqlite.connect(DB_PATH) as conn:
            # Записываем ответ
            await conn.execute(
                'INSERT INTO user_answers (user_id, question_id, answer_id, is_correct) VALUES (?, ?, ?, ?)',
                (user_id, question_id, answer_id, is_correct)
            )
            
            # Получаем категорию вопроса
            async with conn.execute(
                'SELECT category_id FROM questions WHERE id = ?',
                (question_id,)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result:
                category_id = result[0]
                
                # Обновляем или создаем прогресс по категории
                await conn.execute(
                    '''INSERT OR REPLACE INTO user_progress 
                    (user_id, category_id, questions_answered, correct_answers, last_activity)
                    VALUES (?, ?, 
                        COALESCE((SELECT questions_answered FROM user_progress WHERE user_id = ? AND category_id = ?), 0) + 1,
                        COALESCE((SELECT correct_answers FROM user_progress WHERE user_id = ? AND category_id = ?), 0) + ?,
                        CURRENT_TIMESTAMP)''',
                    (user_id, category_id, user_id, category_id, user_id, category_id, 1 if is_correct else 0)
                )
            
            await conn.commit()

    @staticmethod
    async def record_answer_repeat_mode(user_id: int, question_id: int, answer_id: int, is_correct: bool):
        """Запись ответа пользователя в режиме повторения (только в user_answers, без обновления статистики)"""
        async with aiosqlite.connect(DB_PATH) as conn:
            # Записываем ответ только в user_answers, НЕ обновляем user_progress и статистику пользователя
            await conn.execute(
                'INSERT INTO user_answers (user_id, question_id, answer_id, is_correct) VALUES (?, ?, ?, ?)',
                (user_id, question_id, answer_id, is_correct)
            )
            await conn.commit()

    @staticmethod
    async def clear_repeat_mode_answers(user_id: int):
        """Очистить все ответы пользователя в режиме повторения (для новой сессии)"""
        async with aiosqlite.connect(DB_PATH) as conn:
            # Удаляем все записи user_answers для пользователя
            await conn.execute('DELETE FROM user_answers WHERE user_id = ?', (user_id,))
            await conn.commit()

    @staticmethod
    async def user_has_answered_question(user_id: int, question_id: int) -> bool:
        """Проверить, отвечал ли пользователь на данный вопрос ранее"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT 1 FROM user_answers WHERE user_id = ? AND question_id = ? LIMIT 1',
                (user_id, question_id)
            ) as cursor:
                row = await cursor.fetchone()
        return row is not None

    @staticmethod
    async def user_has_answered_correctly(user_id: int, question_id: int) -> bool:
        """Проверить, отвечал ли пользователь правильно на данный вопрос"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT 1 FROM user_answers WHERE user_id = ? AND question_id = ? AND is_correct = 1 LIMIT 1',
                (user_id, question_id)
            ) as cursor:
                row = await cursor.fetchone()
        return row is not None
    
    @staticmethod
    async def get_user_progress_by_category(user_id: int, category_id: int):
        """Получить прогресс пользователя по категории"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT questions_answered, correct_answers FROM user_progress WHERE user_id = ? AND category_id = ?',
                (user_id, category_id)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result:
                answered, correct = result
                accuracy = (correct / answered * 100) if answered > 0 else 0
                return {
                    'questions_answered': answered,
                    'correct_answers': correct,
                    'accuracy': round(accuracy, 1)
                }
            return None
    
    @staticmethod
    async def get_user_overall_progress(user_id: int):
        """Получить общий прогресс пользователя"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                '''SELECT 
                    SUM(questions_answered) as total_answered,
                    SUM(correct_answers) as total_correct,
                    COUNT(DISTINCT category_id) as categories_studied
                FROM user_progress WHERE user_id = ?''',
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result and result[0]:
                total_answered, total_correct, categories_studied = result
                accuracy = (total_correct / total_answered * 100) if total_answered > 0 else 0
                return {
                    'total_questions_answered': total_answered,
                    'total_correct_answers': total_correct,
                    'accuracy': round(accuracy, 1),
                    'categories_studied': categories_studied
                }
            return None
    
    @staticmethod
    async def get_category_stats():
        """Получить статистику по категориям"""
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                '''SELECT 
                    c.name,
                    COUNT(DISTINCT q.id) as total_questions,
                    COUNT(DISTINCT up.user_id) as users_studied
                FROM categories c
                LEFT JOIN questions q ON c.id = q.category_id AND q.is_active = 1
                LEFT JOIN user_progress up ON c.id = up.category_id
                WHERE c.is_active = 1
                GROUP BY c.id, c.name
                ORDER BY c.name''',
            ) as cursor:
                stats = await cursor.fetchall()
        return stats


# Функции-алиасы для обратной совместимости
async def create_all_tables():
    """Алиас для DatabaseManager.create_all_tables"""
    return await DatabaseManager.create_all_tables()

async def add_user(user_id: int, username: str, first_name: str, last_name: str):
    """Алиас для UserManager.add_user"""
    return await UserManager.add_user(user_id, username, first_name, last_name)

async def add_message(user_id: int, role: str, message: str):
    """Алиас для MessageManager.add_message"""
    return await MessageManager.add_message(user_id, role, message)

async def get_history(user_id, limit=10):
    """Алиас для MessageManager.get_history"""
    return await MessageManager.get_history(user_id, limit)

async def get_message_count(user_id: int):
    """Алиас для MessageManager.get_message_count"""
    return await MessageManager.get_message_count(user_id)

async def add_category(name: str):
    """Алиас для CategoryManager.add_category"""
    return await CategoryManager.add_category(name)

async def delete_category(category_id: int):
    """Алиас для CategoryManager.delete_category"""
    return await CategoryManager.delete_category(category_id)

async def get_all_categories():
    """Алиас для CategoryManager.get_all_categories"""
    return await CategoryManager.get_all_categories()

async def get_available_categories():
    """Алиас для CategoryManager.get_available_categories"""
    return await CategoryManager.get_available_categories()

async def get_category_by_id(category_id: int):
    """Алиас для CategoryManager.get_category_by_id"""
    return await CategoryManager.get_category_by_id(category_id) 