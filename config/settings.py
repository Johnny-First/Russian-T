import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

class Settings:
    # Основные настройки бота
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # AI настройки
    DEEP_KEY = os.getenv("DEEP_KEY")
    
    # Настройки админов
    ADMIN_IDS = os.getenv("ADMIN_IDS", "")
    
    # Дополнительные настройки
    CHANNEL_URL = os.getenv("CHANNEL_URL", "")
    
    # Настройки базы данных
    DB_PATH = os.getenv("DB_PATH", "russian_teacher.db")
    
    @classmethod
    def get_admin_ids(cls):
        """Возвращает список ID администраторов"""
        if not cls.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in cls.ADMIN_IDS.split(",") if x.strip()]
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return user_id in cls.get_admin_ids()

# Создаем глобальный экземпляр настроек
settings = Settings() 
        