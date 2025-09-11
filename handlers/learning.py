from aiogram import F, types, Dispatcher
from aiogram.fsm.context import FSMContext
from ..database.models import CategoryManager, QuestionManager, ProgressManager
from ..config.keyboards import (
    get_learning_keyboard, 
    get_categories_keyboard,
    get_question_keyboard,
    get_question_navigation_keyboard,
    get_repeat_session_completed_keyboard
)

class LearningHandlers:
    def __init__(self, dp: Dispatcher):
        dp.callback_query.register(self.start_learning, F.data == "start_learning")
        dp.callback_query.register(self.select_category, F.data == "select_category")
        dp.callback_query.register(self.random_question, F.data == "random_question")
        dp.callback_query.register(self.review_mode, F.data == "review_mode")
        dp.callback_query.register(self.restart_repeat_session, F.data == "restart_repeat_session")
        dp.callback_query.register(self.my_stats, F.data == "my_stats")
        dp.callback_query.register(self.category_selected, F.data.startswith("category_"))
        dp.callback_query.register(self.answer_question, F.data.startswith("answer_"))
        dp.callback_query.register(self.next_question, F.data.startswith("next_question_"))

    async def start_learning(self, callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(
            "📚 <b>Режим: Обучение</b>\n\nВыберите способ обучения:",
            reply_markup=get_learning_keyboard(),
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
        
        # Глобально случайный невиденный вопрос
        question_data = await QuestionManager.get_unseen_random_question_global(callback.from_user.id)
        if not question_data:
            await callback.message.edit_text(
                "📚 <b>Режим: Обучение</b>\n\n📚 К сожалению, нет новых вопросов. Все уже пройдены.",
                reply_markup=get_learning_keyboard(),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        # найти категорию
        from ..database.models import aiosqlite, DB_PATH
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT category_id FROM questions WHERE id = ?', (question_data['question'][0],)) as cur:
                row = await cur.fetchone()
                category_id = row[0] if row else None
        
        # Добавляем режим обучения для случайного вопроса
        await state.update_data(is_repeat_mode=False)
        await self.show_question(callback, question_data, category_id, state)
        await callback.answer()

    async def review_mode(self, callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        
        # Сохраняем режим повторения в состоянии и инициализируем сессию
        await state.update_data(
            is_repeat_mode=True,
            repeat_session_answered_questions=[]  # Список ID вопросов, отвеченных в текущей сессии
        )
        
        # Показываем выбор категорий для повторения
        from ..config.keyboards import get_categories_keyboard
        await callback.message.edit_text(
            "🔁 <b>Режим: Повторение</b>\n\nВыберите категорию для повторения вопросов:",
            reply_markup=await get_categories_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    async def restart_repeat_session(self, callback: types.CallbackQuery, state: FSMContext):
        """Перезапуск сессии повторения"""
        # Сбрасываем список отвеченных вопросов в сессии
        await state.update_data(repeat_session_answered_questions=[])
        
        # Показываем выбор категорий для повторения
        await callback.message.edit_text(
            "🔁 <b>Режим: Повторение</b>\n\nВыберите категорию для повторения вопросов:",
            reply_markup=await get_categories_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    async def category_selected(self, callback: types.CallbackQuery, state: FSMContext):
        category_id = int(callback.data.split("_")[1])
        
        # Проверяем режим повторения
        data = await state.get_data()
        is_repeat_mode = data.get('is_repeat_mode', False)
        
        if is_repeat_mode:
            # В режиме повторения показываем только вопросы, на которые уже отвечали, исключая уже показанные в сессии
            answered_in_session = data.get('repeat_session_answered_questions', [])
            question_data = await QuestionManager.get_random_question_by_category_answered_excluding(
                callback.from_user.id, category_id, answered_in_session
            )
            if not question_data:
                # Все вопросы в сессии закончились - показываем сообщение о завершении
                await callback.message.edit_text(
                    "🔁 <b>Режим: Повторение</b>\n\n🎉 <b>Молодец! Вы все повторили!</b>\n\nВ этой категории больше нет вопросов для повторения в текущей сессии.",
                    reply_markup=get_repeat_session_completed_keyboard(),
                    parse_mode="HTML"
                )
                await callback.answer()
                return
        else:
            # Обычный режим - показываем неотвеченные вопросы
            question_data = await QuestionManager.get_unseen_random_question_by_category(callback.from_user.id, category_id)
            
            if not question_data:
                await callback.message.edit_text(
                    "📚 <b>Режим: Обучение</b>\n\n📚 В этой категории пока нет вопросов.",
                    reply_markup=get_learning_keyboard(),
                    parse_mode="HTML"
                )
                await callback.answer()
                return
        
        # Подготовим данные вопроса и состояние
        question = question_data['question']
        answers = question_data['answers']
        question_id, question_text, difficulty_level, explanation = question
        
        # В режиме повторения добавляем вопрос в сессию сразу при показе
        if is_repeat_mode:
            answered_in_session = data.get('repeat_session_answered_questions', [])
            if question_id not in answered_in_session:
                answered_in_session.append(question_id)
                await state.update_data(repeat_session_answered_questions=answered_in_session)
        
        await state.update_data(
            current_question_id=question_id,
            current_category_id=category_id,
            correct_answer_id=None,
            is_repeat_mode=is_repeat_mode
        )
        for answer in answers:
            if answer[2]:
                await state.update_data(correct_answer_id=answer[0])
                break
        
        difficulty_emoji = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(difficulty_level, "⚪")
        
        # Добавляем подпись режима
        mode_text = "🔁 <b>Режим: Повторение</b>" if is_repeat_mode else "📚 <b>Режим: Обучение</b>"
        text = f"{mode_text}\n\n{difficulty_emoji} <b>Вопрос:</b>\n\n{question_text}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_question_keyboard(answers),
            parse_mode="HTML"
        )
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
            
            # В режиме повторения добавляем вопрос в сессию сразу при показе
            if is_repeat_mode:
                answered_in_session = data.get('repeat_session_answered_questions', [])
                if question_id not in answered_in_session:
                    answered_in_session.append(question_id)
                    await state.update_data(repeat_session_answered_questions=answered_in_session)
            
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
        
        # Проверяем режим
        is_repeat_mode = data.get('is_repeat_mode', False)
        if is_repeat_mode:
            # В режиме повторения НЕ записываем в БД, НЕ изменяем статистику
            pass
        else:
            # Обычный режим - проверяем, отвечал ли уже на этот вопрос
            from ..database.models import ProgressManager, UserManager
            already_answered = await ProgressManager.user_has_answered_question(callback.from_user.id, question_id)
            
            if not already_answered:
                # Первый ответ на вопрос - записываем статистику
                await ProgressManager.record_answer(callback.from_user.id, question_id, answer_id, is_correct)
                await UserManager.update_user_stats(callback.from_user.id, is_correct)
                
                # Если ответ неправильный, показываем тот же вопрос снова
                if not is_correct:
                    # Получаем информацию о правильном ответе
                    question_data = await QuestionManager.get_question_with_answers(question_id)
                    correct_answer_text = None
                    for answer in question_data['answers']:
                        if answer[2]:  # is_correct
                            correct_answer_text = answer[1]
                            break
                    
                    # Формируем ответ
                    result_text = f"❌ <b>Неправильно!</b>\n\nПравильный ответ: {correct_answer_text}"
                    
                    # Добавляем объяснение, если есть
                    question = question_data['question']
                    if question[3]:  # explanation
                        result_text += f"\n\n💡 <b>Объяснение:</b>\n{question[3]}"
                    
                    result_text += f"\n\n🔄 <b>Попробуйте еще раз:</b>"
                    
                    await callback.message.edit_text(
                        result_text,
                        reply_markup=get_question_keyboard(question_data['answers']),
                        parse_mode="HTML"
                    )
                    await callback.answer()
                    return
            else:
                # Уже отвечал на этот вопрос - не изменяем статистику
                # Но если сейчас правильно, записываем в историю
                if is_correct:
                    from ..database.models import aiosqlite, DB_PATH
                    async with aiosqlite.connect(DB_PATH) as conn:
                        await conn.execute(
                            'INSERT INTO user_answers (user_id, question_id, answer_id, is_correct) VALUES (?, ?, ?, 1)',
                            (callback.from_user.id, question_id, answer_id)
                        )
                        await conn.commit()
        
        # Получаем информацию о правильном ответе
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
        
        await callback.message.edit_text(
            result_text,
            reply_markup=get_question_navigation_keyboard(question_id, data.get('current_category_id')),
            parse_mode="HTML"
        )
        await callback.answer()

    async def next_question(self, callback: types.CallbackQuery, state: FSMContext):
        """Показывает следующий вопрос"""
        data = await state.get_data()
        is_repeat_mode = data.get('is_repeat_mode', False)
        category_id = data.get('current_category_id')
        
        if not category_id:
            await callback.message.edit_text(
                "❌ Ошибка: не удалось определить категорию.",
                reply_markup=get_learning_keyboard()
            )
            await callback.answer()
            return
        
        if is_repeat_mode:
            # В режиме повторения показываем только вопросы, на которые уже отвечали, исключая уже показанные в сессии
            answered_in_session = data.get('repeat_session_answered_questions', [])
            question_data = await QuestionManager.get_random_question_by_category_answered_excluding(
                callback.from_user.id, category_id, answered_in_session
            )
            if not question_data:
                # Все вопросы в сессии закончились - показываем сообщение о завершении
                await callback.message.edit_text(
                    "🔁 <b>Режим: Повторение</b>\n\n🎉 <b>Молодец! Вы все повторили!</b>\n\nВ этой категории больше нет вопросов для повторения в текущей сессии.",
                    reply_markup=get_repeat_session_completed_keyboard(),
                    parse_mode="HTML"
                )
                await callback.answer()
                return
        else:
            # Обычный режим - показываем неотвеченные вопросы
            question_data = await QuestionManager.get_unseen_random_question_by_category(callback.from_user.id, category_id)
            
            if not question_data:
                await callback.message.edit_text(
                    "📚 <b>Режим: Обучение</b>\n\n📚 В этой категории больше нет вопросов.",
                    reply_markup=get_learning_keyboard(),
                    parse_mode="HTML"
                )
                await callback.answer()
                return
        
        await self.show_question(callback, question_data, category_id, state)
        await callback.answer()

    async def my_stats(self, callback: types.CallbackQuery, state: FSMContext):
        """Показывает статистику пользователя по категориям"""
        # Получаем общую статистику
        overall_progress = await ProgressManager.get_user_overall_progress(callback.from_user.id)
        category_stats = await ProgressManager.get_user_stats_by_categories(callback.from_user.id)
         
        if not overall_progress or not category_stats:
            await callback.message.edit_text(
                "📊 У вас пока нет статистики. Начните изучение!",
                reply_markup=get_learning_keyboard()
            )
            await callback.answer()
            return
        
        stats_text = f"📊 <b>Ваша статистика по категориям:</b>\n\n"
        
        # Общая статистика
        stats_text += f"🎯 <b>Общая статистика:</b>\n"
        stats_text += f"• Всего вопросов: {overall_progress['total_questions_answered']}\n"
        stats_text += f"• Правильных ответов: {overall_progress['total_correct_answers']}\n"
        stats_text += f"• Точность: {overall_progress['accuracy']}%\n"
        stats_text += f"• Изучено категорий: {overall_progress['categories_studied']}\n\n"
        
        # Статистика по категориям
        stats_text += f"📚 <b>По категориям:</b>\n"
        for category_name, total_questions_answered, total_correct_answers, accuracy in category_stats:
            stats_text += f"• <b>{category_name}:</b> {total_correct_answers}/{total_questions_answered} ({accuracy}%)\n"
        
        await callback.message.edit_text(
            stats_text,
            reply_markup=get_learning_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
