from aiogram import Bot, Dispatcher
import asyncio
from .config import settings
from .database.models import create_all_tables
from .handlers import ( 
    LearningHandlers,
    BaseHandlers,
    AdminHandlers,
    AI_Handlers
)

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    
    await create_all_tables()
    BaseHandlers(dp)
    AdminHandlers(dp)
    LearningHandlers(dp)
    AI_Handlers(dp)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())