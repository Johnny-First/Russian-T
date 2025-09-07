from aiogram import Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from ..services.ai import AI_GPT
from ..config import get_base_keyboard
from ..database.models import MessageManager
from .admin import AdminStates
import asyncio

class AI_Handlers:  
    def __init__(self, dp: Dispatcher):
        self.gpt = AI_GPT()
        dp.message.register(
            self.fallback_handler,
            F.text,
            # ~Command(commands=["admin", "start", "help", "catalog", "order"]),
            # ~StateFilter(AdminStates.waiting_category_name),
            # ~StateFilter(AdminStates.waiting_flower_name),
            # ~StateFilter(AdminStates.waiting_flower_caption),
            # ~StateFilter(AdminStates.waiting_flower_photo),
            # ~StateFilter(AdminStates.waiting_flower_category),
        )

    async def fallback_handler(self, message: types.Message):
        if message.text and message.text.startswith('/'):
            return
            
        user_id = message.from_user.id

        try:
            await MessageManager.add_message(user_id, "user", message.text)
            history = await MessageManager.get_history(user_id, limit=5)
            
            # Создаем первоначальное сообщение с курсором
            bot_message = await message.answer("ChatGPT печатает...", reply_markup=get_base_keyboard())
            full_response = ""
            current_batch = ""
            char_count = 0
            BATCH_SIZE = 100  # ~30-35 слов (в среднем 6-7 символов на слово + пробелы)
            
            # Получаем потоковый ответ и обрабатываем порциями
            async for chunk in self.gpt.ask_gpt_stream(history):
                if chunk:
                    full_response += chunk
                    current_batch += chunk
                    char_count += len(chunk)
                    
                    # Если накопили достаточно символов - выводим порцию
                    if char_count >= BATCH_SIZE:
                        try:
                            await bot_message.edit_text(
                                full_response + "▌", 
                                reply_markup=get_base_keyboard()
                            )
                            current_batch = ""  # Сбрасываем текущую порцию
                            char_count = 0      # Сбрасываем счетчик символов
                        except Exception as edit_error:
                            # Если ошибка редактирования (например, сообщение слишком длинное),
                            # продолжаем накапливать, но не сбрасываем счетчики
                            pass
            
            # Выводим оставшиеся символы (если меньше BATCH_SIZE)
            if current_batch:
                try:
                    await bot_message.edit_text(
                        full_response + "▌", 
                        reply_markup=get_base_keyboard()
                    )
                except Exception as e:
                    # Если не удалось отредактировать, продолжаем
                    pass
            
            # Финальное обновление без курсора
            try:
                await bot_message.edit_text(full_response, reply_markup=get_base_keyboard())
            except Exception as e:
                # Если сообщение слишком длинное, отправляем как новое
                await bot_message.delete()
                bot_message = await message.answer(full_response, reply_markup=get_base_keyboard())
            
            # Сохраняем полный ответ в базу
            await MessageManager.add_message(user_id, "assistant", full_response)
            
            # Удаляем сообщение "печатает..."
            

        except Exception as e:
            # В случае ошибки удаляем сообщение "печатает..." и показываем ошибку
            
            await message.answer(f"Произошла ошибка: {str(e)}", reply_markup=get_base_keyboard())