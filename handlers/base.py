from aiogram import F, types, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from ..config import get_base_keyboard, get_categories_keyboard, get_learning_keyboard, get_learning_keyboard_main
from ..database.models import UserManager, ProgressManager

class BaseHandlers:
    def __init__(self, dp: Dispatcher):
        dp.message.register(self.start_cmd, Command("start"))
        dp.callback_query.register(self.start_learning, F.data == "start_learning")
        dp.callback_query.register(self.select_category, F.data == "select_category")
        dp.callback_query.register(self.random_question, F.data == "random_question")
        dp.callback_query.register(self.my_stats, F.data == "my_stats")
        dp.callback_query.register(self.about, F.data == "about")
        dp.callback_query.register(self.main_menu, F.data == "main_menu")
        dp.callback_query.register(self.answer_question, F.data.startswith("answer_"))

    async def start_cmd(self, message: types.Message, state: FSMContext):
        await state.clear()
        await UserManager.add_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        await message.answer(
            "🇷🇺 Добро пожаловать в бота-репетитора по русскому языку!\n\n"
            "Здесь вы можете изучать русский язык, проходя тесты и викторины по различным темам.\n\n"
            "Выберите действие:",
            reply_markup=get_base_keyboard()
        )
    async def start_learning(self, callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        # Ensure user is in DB for future broadcasts
        from ..database.models import UserManager
        await UserManager.add_user(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
        await callback.message.edit_text(
            "📚 <b>Режим: Обучение</b>\n\nВыберите способ обучения:",
            reply_markup=get_learning_keyboard_main(),
            parse_mode="HTML"
        )
        await callback.answer()

    async def select_category(self, callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        categories_keyboard = await get_categories_keyboard()
        await callback.message.edit_text(
            "📚 <b>Режим: Обучение</b>\n\nВыберите категорию для изучения:",
            reply_markup=categories_keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    async def random_question(self, callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        from ..database.models import CategoryManager, QuestionManager
        
        # Получаем случайный невиденный вопрос глобально
        question_data = await QuestionManager.get_unseen_random_question_global(callback.from_user.id)
        if not question_data:
            await callback.message.edit_text(
                "📚 <b>Режим: Обучение</b>\n\n📚 К сожалению, нет новых вопросов. Все уже пройдены.",
                reply_markup=get_learning_keyboard(),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        # Если нашли глобально, вытянем category_id
        from ..database.models import aiosqlite, DB_PATH
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT category_id FROM questions WHERE id = ?', (question_data['question'][0],)) as cur:
                row = await cur.fetchone()
                category_id = row[0] if row else None
        await self.show_question(callback, question_data, category_id, state)
        await callback.answer()


    async def show_question(self, callback: types.CallbackQuery, question_data, category_id, state: FSMContext = None):
        """Показывает вопрос с вариантами ответов"""
        from ..config.keyboards import get_question_keyboard, get_question_navigation_keyboard
        
        question = question_data['question']
        answers = question_data['answers']
        
        question_id, question_text, difficulty_level, explanation = question
        
        # Сохраняем данные вопроса в state для проверки ответа
        is_repeat_mode = False
        if state:
            data = await state.get_data()
            is_repeat_mode = data.get('is_repeat_mode', False)
            await state.update_data(
                current_question_id=question_id,
                current_category_id=category_id,
                correct_answer_id=None,
                is_repeat_mode=is_repeat_mode
            )
            
            # Находим правильный ответ
            for answer in answers:
                if answer[2]:  # is_correct
                    await state.update_data(correct_answer_id=answer[0])
                    break
        
        # Добавляем подпись режима и эмодзи сложности
        difficulty_emoji = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(difficulty_level, "⚪")
        mode_text = "🔁 <b>Режим: Повторение</b>" if is_repeat_mode else "📚 <b>Режим: Обучение</b>"
        text = f"{mode_text}\n\n{difficulty_emoji} <b>Вопрос:</b>\n\n{question_text}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_question_keyboard(answers),
            parse_mode="HTML"
        )

    async def answer_question(self, callback: types.CallbackQuery, state: FSMContext):
        """Обрабатывает ответ пользователя на вопрос"""
        token = callback.data.split("_", 1)[1]
        if not token.isdigit():
            await callback.answer()
            return
        answer_id = int(token)
        
        data = await state.get_data()
        question_id = data.get('current_question_id')
        correct_answer_id = data.get('correct_answer_id')
        
        if not question_id or correct_answer_id is None:
            await callback.answer("Ошибка: данные вопроса не найдены", show_alert=True)
            return
        
        is_correct = answer_id == correct_answer_id
        
        # Записываем ответ только если это первый ответ на этот вопрос для пользователя (статистику не меняем при повторном ответе)
        from ..database.models import ProgressManager, UserManager
        already = await ProgressManager.user_has_answered_question(callback.from_user.id, question_id)
        if not already:
            await ProgressManager.record_answer(callback.from_user.id, question_id, answer_id, is_correct)
            await UserManager.update_user_stats(callback.from_user.id, is_correct)
        else:
            # Если уже отвечал, но сейчас правильно — зафиксируем правильный в истории (без изменения статистики)
            if is_correct:
                from ..database.models import aiosqlite, DB_PATH
                async with aiosqlite.connect(DB_PATH) as conn:
                    await conn.execute(
                        'INSERT INTO user_answers (user_id, question_id, answer_id, is_correct) VALUES (?, ?, ?, 1)',
                        (callback.from_user.id, question_id, answer_id)
                    )
                    await conn.commit()
        
        # Получаем информацию о правильном ответе
        from ..database.models import QuestionManager
        question_data = await QuestionManager.get_question_with_answers(question_id)
        correct_answer_text = None
        for answer in question_data['answers']:
            if answer[2]:  # is_correct
                correct_answer_text = answer[1]
                break
        
        # Формируем ответ
        if is_correct:
            result_text = "✅ <b>Правильно!</b>"
        else:
            result_text = f"❌ <b>Неправильно!</b>\n\nПравильный ответ: {correct_answer_text}"
        
        # Добавляем объяснение, если есть
        question = question_data['question']
        if question[3]:  # explanation
            result_text += f"\n\n💡 <b>Объяснение:</b>\n{question[3]}"
        
        from ..config.keyboards import get_question_navigation_keyboard
        await callback.message.edit_text(
            result_text,
            reply_markup=get_question_navigation_keyboard(question_id, data.get('current_category_id')),
            parse_mode="HTML"
        )
        await callback.answer()


    async def my_stats(self, callback: types.CallbackQuery, state: FSMContext):
        """Показывает статистику пользователя"""
        from ..database.models import UserManager, ProgressManager
        
        user_stats = await UserManager.get_user_stats(callback.from_user.id)
        overall_progress = await ProgressManager.get_user_overall_progress(callback.from_user.id)
        
        if not user_stats:
            await callback.message.edit_text(
                "📊 У вас пока нет статистики. Начните изучение!",
                reply_markup=get_learning_keyboard()
            )
            await callback.answer()
            return
        
        stats_text = f"📊 <b>Ваша статистика:</b>\n\n"
        stats_text += f"🎯 Всего вопросов: {user_stats['total_questions']}\n"
        stats_text += f"✅ Правильных ответов: {user_stats['correct_answers']}\n"
        stats_text += f"📈 Точность: {user_stats['accuracy']}%\n"
        
        if overall_progress:
            stats_text += f"\n📚 Изучено категорий: {overall_progress['categories_studied']}"
        
        await callback.message.edit_text(
            stats_text,
            reply_markup=get_learning_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    async def about(self, callback: types.CallbackQuery, state: FSMContext):
        """Информация о боте"""
        about_text = (
            "ℹ️ <b>О боте-репетиторе по русскому языку</b>\n\n"
            "Этот бот поможет вам изучать русский язык через интерактивные тесты и викторины.\n\n"
            "🎯 <b>Возможности:</b>\n"
            "• Прохождение тестов по различным темам\n"
            "• Случайные вопросы для повторения\n"
            "• Отслеживание прогресса обучения\n"
            "• Разные уровни сложности\n\n"
            "📚 <b>Как начать:</b>\n"
            "1. Выберите категорию для изучения\n"
            "2. Отвечайте на вопросы\n"
            "3. Следите за своим прогрессом\n\n"
            "Удачи в изучении русского языка! 🇷🇺"
        )
        
        await callback.message.edit_text(
            about_text,
            reply_markup=get_base_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    async def main_menu(self, callback: types.CallbackQuery, state: FSMContext):
        """Возврат в главное меню"""
        await state.clear()
        await callback.message.edit_text(
            "🏠 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=get_base_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()