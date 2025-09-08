from aiogram import types
from typing import Dict
from ..database.models import CategoryManager, QuestionManager

def get_my_keyboard(role: str, data: Dict[str, str]) -> types.InlineKeyboardMarkup:
    buttons = []
    row = []
    for name, callback in data.items():  
        row.append(types.InlineKeyboardButton(
            text=name, 
            callback_data=f"{role}{callback}"
        ))
        if len(row) == 2:  
            buttons.append(row)
            row = []
    if row:  
        buttons.append(row)
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_base_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📚 Начать обучение", callback_data="start_learning")],
            [types.InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
            [types.InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")]
        ]
    )

def get_admin_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_mailing")],
            [types.InlineKeyboardButton(text="❓ Управление вопросами", callback_data="admin_questions")],
            [types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
        ]
    )

def get_learning_keyboard():
    """Клавиатура обучения без кнопки случайного вопроса (для всех внутренних экранов)."""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔁 Повторение", callback_data="review_mode")],
            [types.InlineKeyboardButton(text="📚 Выбрать категорию", callback_data="select_category")],
            [types.InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_learning")]
        ]
    )

def get_learning_keyboard_main():
    """Главная клавиатура обучения с кнопкой случайного вопроса (только на первом экране)."""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🎯 Случайный вопрос", callback_data="random_question")],
            [types.InlineKeyboardButton(text="🔁 Повторение", callback_data="review_mode")],
            [types.InlineKeyboardButton(text="📚 Выбрать категорию", callback_data="select_category")],
            [types.InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
            [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    )

def get_repeat_session_completed_keyboard():
    """Клавиатура когда все вопросы в сессии повторения закончились"""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Повторить сессию", callback_data="restart_repeat_session")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_learning")]
        ]
    )
async def admin_get_categories_keyboard():
    categories = await CategoryManager.get_all_categories()
    buttons = []
    row = []
    for category in categories:
        category_id, name, is_active = category
        status_emoji = "✅" if is_active else "❌"
        button_text = f"{status_emoji} {name}"
        row.append(types.InlineKeyboardButton(text=button_text, callback_data=f"admin_category_{category_id}"))
        if len(row) == 1:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([types.InlineKeyboardButton(text="Назад", callback_data="admin")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

async def admin_get_categories_for_questions_keyboard():
    categories = await CategoryManager.get_all_categories()
    buttons = []
    row = []
    for category in categories:
        category_id, name, is_active = category
        status_emoji = "✅" if is_active else "❌"
        button_text = f"{status_emoji} {name}"
        row.append(types.InlineKeyboardButton(text=button_text, callback_data=f"admin_qcat_{category_id}"))
        if len(row) == 1:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([types.InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category_q")])
    buttons.append([types.InlineKeyboardButton(text="Назад", callback_data="admin")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_categories_keyboard():
    categories = await CategoryManager.get_available_categories()
    buttons = []
    row = []
    if not categories:
        buttons.append([types.InlineKeyboardButton(text="📚 Категории пока не добавлены", callback_data="no_categories")])
    else:
        for category in categories:
            category_id, name = category
            button_text = f"{name}"
            row.append(types.InlineKeyboardButton(text=button_text, callback_data=f"category_{category_id}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_learning")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_question_keyboard(answers):
    """Создает клавиатуру с вариантами ответов"""
    buttons = []
    for answer in answers:
        answer_id, answer_text, is_correct = answer
        buttons.append([types.InlineKeyboardButton(
            text=answer_text, 
            callback_data=f"answer_{answer_id}"
        )])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_question_navigation_keyboard(question_id, category_id):
    """Создает клавиатуру навигации для вопроса"""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Следующий вопрос", callback_data=f"next_question_{category_id}")],
            [types.InlineKeyboardButton(text="📚 К категориям", callback_data="select_category")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_learning")]
        ]
    )

async def admin_get_questions_keyboard(category_id):
    """Клавиатура для управления вопросами в админ-панели"""
    questions = await QuestionManager.get_all_questions_by_category(category_id)
    buttons = []
    
    if not questions:
        buttons.append([types.InlineKeyboardButton(text="В этой категории пока нет вопросов", callback_data="no_questions")])
    else:
        for question in questions:
            question_id, question_text, difficulty_level, is_active = question
            status_emoji = "✅" if is_active else "❌"
            difficulty_emoji = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(difficulty_level, "⚪")
            button_text = f"{status_emoji} {difficulty_emoji} {question_text[:30]}..."
            buttons.append([types.InlineKeyboardButton(
                text=button_text, 
                callback_data=f"admin_question_{question_id}"
            )])
    
    buttons.append([types.InlineKeyboardButton(text="➕ Добавить вопрос", callback_data=f"admin_add_question_{category_id}")])
    buttons.append([types.InlineKeyboardButton(text="🗑️ Удалить категорию", callback_data=f"delete_category_{category_id}")])
    buttons.append([types.InlineKeyboardButton(text="Назад", callback_data="admin_questions")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_difficulty_keyboard():
    """Клавиатура выбора уровня сложности"""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🟢 Начальный", callback_data="difficulty_beginner")],
            [types.InlineKeyboardButton(text="🟡 Средний", callback_data="difficulty_intermediate")],
            [types.InlineKeyboardButton(text="🔴 Продвинутый", callback_data="difficulty_advanced")],
            [types.InlineKeyboardButton(text="Назад", callback_data="admin_categories")]
        ]
    )

def get_question_management_keyboard(question_id):
    """Клавиатура управления конкретным вопросом"""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_question_{question_id}")],
            [types.InlineKeyboardButton(text="🔄 Изменить статус", callback_data=f"toggle_question_{question_id}")],
            [types.InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_question_{question_id}")],
            [types.InlineKeyboardButton(text="Назад", callback_data="admin_questions")]
        ]
    )
