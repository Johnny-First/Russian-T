
from aiogram.fsm.state import StatesGroup, State
from aiogram import F, types, Dispatcher
from aiogram.filters import Command  
from ..config import get_base_keyboard, get_my_keyboard, admin_get_categories_keyboard, admin_get_questions_keyboard, get_difficulty_keyboard, get_question_management_keyboard
from ..config.keyboards import admin_get_categories_for_questions_keyboard
import sqlite3
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from ..database.models import QuestionManager, CategoryManager, ProgressManager
from ..config import get_admin_keyboard
from ..config.settings import settings

class AdminStates(StatesGroup):
    waiting_broadcast = State() 
    waiting_new_category_name = State()
    waiting_new_category_description = State()
    waiting_new_category_difficulty = State()
    waiting_question_text = State()
    waiting_question_explanation = State()
    waiting_question_difficulty = State()
    waiting_answer_text = State()
    waiting_answer_correct = State()
    waiting_category_delete = State()
    waiting_question_delete = State()
    waiting_question_edit = State()
    edit_question_id = State()
    edit_question_text = State()
    edit_question_explanation = State()
    edit_question_difficulty = State()
    edit_draft_answers = State()

class AdminHandlers:
    def __init__(self, dp: Dispatcher):
        self.admin_ids = settings.get_admin_ids()

        dp.message.register(self.admin_panel, Command("admin"))
        dp.callback_query.register(self.admin_panel_callback, F.data == "admin")        

        # Handle only top-level admin actions; do not swallow more specific admin_* callbacks
        dp.callback_query.register(
            self.admin_action_callback,
            (
                F.data == "admin_mailing"
            ) | (
                F.data == "admin_questions"
            ) | (
                F.data == "admin_stats"
            )
        )

        dp.message.register(
            self.broadcast_message,
            StateFilter(AdminStates.waiting_broadcast)
        )
        dp.message.register(
            self.process_new_category_name,
            StateFilter(AdminStates.waiting_new_category_name)
        )
        dp.message.register(
            self.process_new_category_description,
            StateFilter(AdminStates.waiting_new_category_description)
        )
        dp.message.register(
            self.process_question_text,
            StateFilter(AdminStates.waiting_question_text)
        )
        dp.message.register(
            self.process_question_explanation,
            StateFilter(AdminStates.waiting_question_explanation)
        )
        dp.message.register(
            self.process_answer_text,
            StateFilter(AdminStates.waiting_answer_text)
        )
        
        # Callback handlers
        dp.callback_query.register(
            self.process_difficulty_selection,
            F.data.startswith("difficulty_")
        )
        dp.callback_query.register(
            self.add_more_answer,
            F.data == "admin_add_more_answer"
        )
        dp.callback_query.register(
            self.finish_question_creation,
            F.data == "finish_question"
        )
        dp.callback_query.register(
            self.start_pick_correct_answer,
            F.data == "admin_pick_correct"
        )
        dp.callback_query.register(
            self.set_correct_answer,
            F.data.startswith("admin_set_correct_")
        )
        dp.callback_query.register(
            self.add_category_for_questions,
            F.data == "admin_add_category_q"
        )
        dp.callback_query.register(
            self.delete_category_from_questions,
            F.data.startswith("delete_category_")
        )
        dp.callback_query.register(
            self.process_category_selection,
            F.data.startswith("admin_category_")
        )
        dp.callback_query.register(
            self.process_questions_category_selection,
            F.data.startswith("admin_qcat_")
        )
        dp.callback_query.register(
            self.process_question_selection,
            F.data.startswith("admin_question_")
        )
        dp.callback_query.register(
            self.process_question_management,
            F.data.startswith("edit_question_") | F.data.startswith("toggle_question_") | F.data.startswith("delete_question_")
        )
        dp.callback_query.register(
            self.process_add_question,
            F.data.startswith("admin_add_question_")
        )
        
    async def start_pick_correct_answer(self, callback: types.CallbackQuery, state: FSMContext):
        """Показать список собранных ответов и дать выбрать правильный"""
        data = await state.get_data()
        draft_answers = data.get('draft_answers', [])
        if len(draft_answers) < 2:
            await callback.answer("Нужно минимум 2 варианта", show_alert=True)
            return
        buttons = []
        for idx, text in enumerate(draft_answers):
            label = f"{idx+1}. {text[:30]}" + ("..." if len(text) > 30 else "")
            buttons.append([types.InlineKeyboardButton(text=label, callback_data=f"admin_set_correct_{idx}")])
        buttons.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_add_more_answer")])
        await callback.message.edit_text(
            "Выберите правильный ответ:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()

    async def set_correct_answer(self, callback: types.CallbackQuery, state: FSMContext):
        """Сохранить ответы в БД, пометив выбранный как правильный"""
        idx_str = callback.data.split("_")[-1]
        if not idx_str.isdigit():
            await callback.answer()
            return
        idx = int(idx_str)
        data = await state.get_data()
        draft_answers = data.get('draft_answers', [])
        question_id = data.get('current_question_id')
        is_edit = data.get('is_edit')
        if idx < 0 or idx >= len(draft_answers) or not question_id:
            await callback.answer("Некорректный выбор", show_alert=True)
            return
        # Перезаписать ответы, если редактирование
        if is_edit:
            await QuestionManager.delete_answers_for_question(question_id)
        # Сохранить все ответы
        for i, text in enumerate(draft_answers):
            await QuestionManager.add_answer(question_id, text, is_correct=(i == idx))
        
        # Получить итоговый вопрос с ответами для сводки
        question_data = await QuestionManager.get_question_with_answers(question_id)
        question = question_data['question'] if question_data else None
        answers = question_data['answers'] if question_data else []
        
        # Собрать текст подтверждения
        title = "✅ <b>Вопрос обновлён</b>\n\n" if is_edit else "✅ <b>Вопрос добавлен</b>\n\n"
        summary_text = title
        if question:
            summary_text += f"<b>Вопрос:</b> {question[1]}\n"
            summary_text += f"<b>Сложность:</b> {question[2]}\n\n"
        summary_text += "<b>Варианты ответов:</b>\n"
        for i, a in enumerate(answers, 1):
            correct_mark = "✅" if a[2] else "❌"
            summary_text += f"{i}. {correct_mark} {a[1]}\n"
        
        # Клавиатура навигации
        category_id = data.get('question_category_id') or data.get('selected_category_id')
        nav_keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="📋 К вопросам категории", callback_data=(f"admin_qcat_{category_id}" if category_id else "admin_questions"))],
                [types.InlineKeyboardButton(text="➕ Добавить ещё вопрос", callback_data=(f"admin_add_question_{category_id}" if category_id else "admin_questions"))],
                [types.InlineKeyboardButton(text="🏠 Админ", callback_data="admin")],
            ]
        )
        
        await callback.message.edit_text(
            summary_text,
            reply_markup=nav_keyboard,
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()
        
    async def admin_panel(self, message: types.Message, state: FSMContext):
        await state.clear()        
        if message.from_user.id not in self.admin_ids:
            await message.answer("У вас нет доступа к админ-панели.")
            return
        await message.answer(
            "Что бы вы хотели сделать, админ?",
            reply_markup=get_admin_keyboard()
        )

    async def admin_panel_callback(self, callback: types.CallbackQuery, state: FSMContext):     
        await state.clear()           
        if callback.from_user.id not in self.admin_ids:
            await callback.answer("У вас нет доступа к админ-панели", show_alert=True)
            return
        await callback.message.edit_text(
            "Что бы вы хотели сделать, админ?",
            reply_markup=get_admin_keyboard()
        )
 

    async def admin_action_callback(self, callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        data = "_".join(callback.data.split("_")[1:])
        if callback.from_user.id not in self.admin_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        
        if data == "mailing":
            await callback.message.answer(
                "📢 Отправьте текст для рассылки.\n\n💡 Вы также можете отправить фотографию с подписью - она будет разослана всем пользователям.", 
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Назад", callback_data="admin")]])
            )
            await state.set_state(AdminStates.waiting_broadcast)
            await callback.answer()
            
        elif data == "questions":
            await callback.message.edit_text(
                "❓ Управление вопросами. Выберите категорию:",
                reply_markup=await admin_get_categories_for_questions_keyboard()
            )
            await callback.answer()
            
        elif data == "stats":
            await self.show_admin_stats(callback)
            await callback.answer()
            
        elif data == "add_category":
            await callback.message.edit_text(
                "📝 Введите название новой категории:",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[
                        types.InlineKeyboardButton(text="Назад", callback_data="admin_questions")
                    ]]
                )
            )
            await state.set_state(AdminStates.waiting_new_category_name)
            await callback.answer()
        
        else:
            await callback.answer("Неизвестное действие", show_alert=True)

    async def process_category_selection(self, callback: types.CallbackQuery, state: FSMContext):
        """Обработка выбора категории в админ-панели"""
        category_id = int(callback.data.split("_")[2])
        await state.update_data(selected_category_id=category_id)
        
        # Показываем меню управления категорией
        category = await CategoryManager.get_category_by_id(category_id)
        if category:
            category_id, name, description = category
            text = f"📚 <b>Категория: {name}</b>\n\n"
            text += f"📝 Описание: {description or 'Не указано'}\n\n"
            text += "Выберите действие:"
            
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_category_{category_id}")],
                    [types.InlineKeyboardButton(text="🔄 Изменить статус", callback_data=f"toggle_category_{category_id}")],
                    [types.InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_category_{category_id}")],
                    [types.InlineKeyboardButton(text="❓ Управлять вопросами", callback_data=f"manage_questions_{category_id}")],
                    [types.InlineKeyboardButton(text="Назад", callback_data="admin_categories")]
                ]
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        await callback.answer()

    async def process_question_selection(self, callback: types.CallbackQuery, state: FSMContext):
        """Обработка выбора вопроса в админ-панели"""
        question_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о вопросе
        question_data = await QuestionManager.get_question_with_answers(question_id)
        if question_data:
            question = question_data['question']
            answers = question_data['answers']
            
            question_id, question_text, difficulty_level, explanation = question
            
            # Получаем статус
            is_active = await QuestionManager.get_question_status(question_id)
            status_emoji = "✅" if is_active else "❌"
            text = f"{status_emoji} <b>Вопрос:</b>\n{question_text}\n\n"
            text += f"🎯 Уровень: {difficulty_level}\n"
            if explanation:
                text += f"💡 Объяснение: {explanation}\n\n"
            
            text += "<b>Варианты ответов:</b>\n"
            for i, answer in enumerate(answers, 1):
                answer_id, answer_text, is_correct = answer
                correct_mark = "✅" if is_correct else "❌"
                text += f"{i}. {correct_mark} {answer_text}\n"
            
            # Создаем локальную клавиатуру управления с корректной кнопкой Назад
            data = await state.get_data()
            category_id = data.get('selected_category_id')
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_question_{question_id}")],
                    [types.InlineKeyboardButton(text="🔄 Изменить статус", callback_data=f"toggle_question_{question_id}")],
                    [types.InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_question_{question_id}")],
                    [types.InlineKeyboardButton(text="Назад", callback_data=(f"admin_qcat_{category_id}" if category_id else "admin_questions"))],
                ]
            )
            
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        await callback.answer()

    async def process_add_question(self, callback: types.CallbackQuery, state: FSMContext):
        """Начало добавления нового вопроса"""
        category_id = int(callback.data.split("_")[3])
        await state.update_data(question_category_id=category_id)
        
        await callback.message.edit_text(
            "❓ <b>Добавление нового вопроса</b>\n\n📝 Введите текст вопроса:",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(text="Отмена", callback_data="admin_questions")
                ]]
            ),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_question_text)
        await callback.answer()

    async def process_question_management(self, callback: types.CallbackQuery, state: FSMContext):
        """Обработка управления вопросом"""
        action = callback.data.split("_")[0]
        question_id = int(callback.data.split("_")[2])
        
        if action == "edit":
            # Перезапускаем существующий механизм добавления как редактирование
            data = await state.get_data()
            category_id = data.get('selected_category_id')
            await state.update_data(current_question_id=question_id, question_category_id=category_id, is_edit=True)
            await state.set_state(AdminStates.waiting_question_text)
            await callback.message.edit_text(
                "✏️ Введите новый текст вопроса:",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="Отмена", callback_data=f"admin_question_{question_id}")]]
                )
            )
            await callback.answer()
            return
        elif action == "toggle":
            # Переключаем статус вопроса надёжно
            current_status = await QuestionManager.get_question_status(question_id)
            await QuestionManager.update_question_status(question_id, not current_status)
            await callback.answer("Статус вопроса изменен", show_alert=True)
            # Обновляем карточку вопроса
            await self.process_question_selection(callback, state)
        elif action == "delete":
            await QuestionManager.delete_question(question_id)
            await callback.answer("Вопрос удален", show_alert=True)
            # Возвращаемся к списку вопросов
            data = await state.get_data()
            category_id = data.get('selected_category_id')
            if category_id:
                await callback.message.edit_text(
                    "❓ Вопросы в категории:",
                    reply_markup=await admin_get_questions_keyboard(category_id)
                )
        
        await callback.answer()

    async def delete_category_from_questions(self, callback: types.CallbackQuery, state: FSMContext):
        """Удаление категории из панели управления вопросами"""
        category_id = int(callback.data.split("_")[2])
        await CategoryManager.delete_category(category_id)
        await callback.message.edit_text(
            "📚 Категория удалена. Выберите категорию:",
            reply_markup=await admin_get_categories_for_questions_keyboard()
        )
        await callback.answer()

    async def process_questions_category_selection(self, callback: types.CallbackQuery, state: FSMContext):
        """Выбор категории для управления вопросами"""
        category_id = int(callback.data.split("_")[2])
        await state.update_data(selected_category_id=category_id)
        await callback.message.edit_text(
            "❓ Вопросы в категории:",
            reply_markup=await admin_get_questions_keyboard(category_id)
        )
        await callback.answer()

    async def process_new_category_name(self, message: types.Message, state: FSMContext):
        """Обработка названия новой категории"""
        category_name = message.text.strip()
        
        if len(category_name) == 0:
            await message.answer("Название категории не может быть пустым. Попробуйте еще раз.")
            return
        
        # Создаем категорию сразу (без описания)
        try:
            await CategoryManager.add_category(category_name)
            await message.answer(
                f"✅ Категория '{category_name}' добавлена.",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="К категориям вопросов", callback_data="admin_questions")]]
                )
            )
            await state.clear()
        except Exception as e:
            await message.answer(
                f"❌ Ошибка при добавлении категории: {str(e)}",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="Назад", callback_data="admin_questions")]]
                )
            )

    async def process_new_category_description(self, message: types.Message, state: FSMContext):
        """(Не используется)"""
        await state.clear()
        await message.answer(
            "Возврат к категориям вопросов",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="К категориям вопросов", callback_data="admin_questions")]]
            )
        )
    async def add_category_for_questions(self, callback: types.CallbackQuery, state: FSMContext):
        """Старт добавления категории из панели вопросов"""
        await callback.message.edit_text(
            "📝 Введите название новой категории:",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="Назад", callback_data="admin_questions")]]
            )
        )
        await state.set_state(AdminStates.waiting_new_category_name)
        await callback.answer()

    async def process_difficulty_selection(self, callback: types.CallbackQuery, state: FSMContext):
        """Обработка выбора уровня сложности: и для категорий, и для вопросов"""
        difficulty = callback.data.split("_")[1]
        current_state = await state.get_state()

        # Ветка добавления категории
        if current_state == AdminStates.waiting_new_category_difficulty.state:
            data = await state.get_data()
            category_name = data.get('category_name')
            category_description = data.get('category_description')
            try:
                await CategoryManager.add_category(category_name)
                await callback.message.edit_text(
                    f"✅ Категория '{category_name}' успешно добавлена!",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[[types.InlineKeyboardButton(text="К категориям", callback_data="admin_categories")]]
                    )
                )
                await state.clear()
            except Exception as e:
                await callback.message.edit_text(
                    f"❌ Ошибка при добавлении категории: {str(e)}",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[[types.InlineKeyboardButton(text="Назад", callback_data="admin_categories")]]
                    )
                )
            await callback.answer()
            return

        # Ветка добавления вопроса
        if current_state == AdminStates.waiting_question_difficulty.state:
            data = await state.get_data()
            question_text = data.get('question_text')
            question_explanation = data.get('question_explanation')
            category_id = data.get('question_category_id')
            is_edit = data.get('is_edit')

            try:
                if is_edit:
                    # Обновляем вопрос, ответы перезапишем после выбора правильного
                    question_id = data.get('current_question_id')
                    await QuestionManager.update_question(question_id, question_text, difficulty, question_explanation)
                    await state.update_data(draft_answers=[])
                else:
                    question_id = await QuestionManager.add_question(
                        question_text=question_text,
                        category_id=category_id,
                        difficulty_level=difficulty,
                        explanation=question_explanation,
                    )
                    await state.update_data(current_question_id=question_id, draft_answers=[])
                await callback.message.edit_text(
                    "🧩 Теперь добавим варианты ответов. Отправьте текст ответа:",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[[types.InlineKeyboardButton(text="Отмена", callback_data="finish_question")]]
                    ),
                    parse_mode="HTML"
                )
                await state.set_state(AdminStates.waiting_answer_text)
            except Exception as e:
                await callback.message.edit_text(
                    f"❌ Ошибка при сохранении вопроса: {str(e)}",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[[types.InlineKeyboardButton(text="Назад", callback_data="admin_questions")]]
                    )
                )
            await callback.answer()
            return

        await callback.answer("Неверное состояние", show_alert=True)

    async def add_more_answer(self, callback: types.CallbackQuery, state: FSMContext):
        """Запросить ввод очередного варианта ответа"""
        await callback.message.edit_text(
            "✍️ Введите текст ответа:",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="Отмена", callback_data="finish_question")]]
            ),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_answer_text)
        await callback.answer()

    async def finish_question_creation(self, callback: types.CallbackQuery, state: FSMContext):
        """Завершение добавления вопроса: возвращаемся к списку вопросов категории"""
        data = await state.get_data()
        category_id = data.get('question_category_id') or data.get('selected_category_id')
        await state.clear()
        if category_id:
            await callback.message.edit_text(
                "❓ Вопросы в категории:",
                reply_markup=await admin_get_questions_keyboard(category_id)
            )
        else:
            await callback.message.edit_text(
                "❓ Управление вопросами. Выберите категорию:",
                reply_markup=await admin_get_categories_for_questions_keyboard()
            )
        await callback.answer()

    async def process_question_text(self, message: types.Message, state: FSMContext):
        """Обработка текста вопроса"""
        question_text = message.text.strip()
        
        if len(question_text) == 0:
            await message.answer("Текст вопроса не может быть пустым. Попробуйте еще раз.")
            return
        
        await state.update_data(question_text=question_text)
        await state.set_state(AdminStates.waiting_question_explanation)
        
        await message.answer(
            "💡 Введите объяснение к вопросу (или отправьте '-' чтобы пропустить):",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(text="Отмена", callback_data="admin_questions")
                ]]
            )
        )

    async def process_question_explanation(self, message: types.Message, state: FSMContext):
        """Обработка объяснения вопроса"""
        explanation = message.text.strip() if message.text.strip() != "-" else None
        
        await state.update_data(question_explanation=explanation)
        await state.set_state(AdminStates.waiting_question_difficulty)
        
        await message.answer(
            "🎯 Выберите уровень сложности вопроса:",
            reply_markup=get_difficulty_keyboard()
        )

    async def process_answer_text(self, message: types.Message, state: FSMContext):
        """Обработка текста ответа"""
        answer_text = message.text.strip()
        
        if len(answer_text) < 1:
            await message.answer("Текст ответа не может быть пустым. Попробуйте еще раз.")
            return
        
        data = await state.get_data()
        draft_answers = data.get('draft_answers', [])
        draft_answers.append(answer_text)
        await state.update_data(draft_answers=draft_answers)

        summary = "\n".join([f"{idx+1}. {text}" for idx, text in enumerate(draft_answers)]) or "(пока пусто)"
        await message.answer(
            f"📋 Текущие варианты ответов:\n{summary}",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="➕ Добавить ещё", callback_data="admin_add_more_answer")],
                    [types.InlineKeyboardButton(text="✅ Выбрать правильный", callback_data="admin_pick_correct")],
                    [types.InlineKeyboardButton(text="Завершить", callback_data="finish_question")],
                ]
            )
        )

    async def show_admin_stats(self, callback: types.CallbackQuery):
        """Показывает статистику для админа"""
        try:
            stats = await ProgressManager.get_category_stats()
            
            if not stats:
                await callback.message.edit_text(
                    "📊 Статистика пока недоступна",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[[
                            types.InlineKeyboardButton(text="Назад", callback_data="admin")
                        ]]
                    )
                )
                return
            
            text = "📊 <b>Статистика системы:</b>\n\n"
            
            for stat in stats:
                name, difficulty, total_questions, users_studied = stat
                difficulty_emoji = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(difficulty, "⚪")
                text += f"{difficulty_emoji} <b>{name}</b>\n"
                text += f"   📚 Вопросов: {total_questions}\n"
                text += f"   👥 Изучали: {users_studied} чел.\n\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[
                        types.InlineKeyboardButton(text="Назад", callback_data="admin")
                    ]]
                ),
                parse_mode="HTML"
            )
            
        except Exception as e:
            await callback.message.edit_text(
                f"❌ Ошибка при загрузке статистики: {str(e)}",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[
                        types.InlineKeyboardButton(text="Назад", callback_data="admin")
                    ]]
                )
            )

    async def broadcast_message(self, message: types.Message, state: FSMContext):
        """Обработчик рассылки сообщений"""
        from ..database.models import UserManager
        
        try:
            # Получаем всех пользователей
            conn = sqlite3.connect(settings.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            user_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            sent = 0
            failed = 0
            
            if message.photo:
                # Рассылка фотографии с подписью
                photo_file_id = message.photo[-1].file_id
                caption = message.caption or ""
                
                for user_id in user_ids:
                    try:
                        await message.bot.send_photo(
                            chat_id=user_id,
                            photo=photo_file_id,
                            caption=caption
                        )
                        sent += 1
                    except Exception as e:
                        print(f"Ошибка отправки фото пользователю {user_id}: {e}")
                        failed += 1
                        continue
                        
                result_message = f"📸 Рассылка фотографии завершена!\n✅ Отправлено: {sent} пользователям"
                if failed > 0:
                    result_message += f"\n❌ Ошибки: {failed} пользователей"
                    
            else:
                # Рассылка только текста
                broadcast_text = message.text
                
                for user_id in user_ids:
                    try:
                        await message.bot.send_message(
                            chat_id=user_id,
                            text=broadcast_text
                        )
                        sent += 1
                    except Exception as e:
                        print(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
                        failed += 1
                        continue
                        
                result_message = f"📢 Рассылка текста завершена!\n✅ Отправлено: {sent} пользователям"
                if failed > 0:
                    result_message += f"\n❌ Ошибки: {failed} пользователей"
            
            await message.answer(
                result_message,
                reply_markup=get_admin_keyboard()
            )
            
        except Exception as e:
            await message.answer(
                f"❌ Ошибка при рассылке: {str(e)}",
                reply_markup=get_admin_keyboard()
            )
        finally:
            await state.clear()