from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes,MessageHandler, filters, ConversationHandler
from model_inference import predict_salary, predict_salary_response, predict_grade
from telegram.constants import ParseMode
from market_analytics import top_5_skills, compare_vacancy_to_market, top_vacancies, get_area_id_by_city, promotion_skills
import pandas as pd
from dotenv import load_dotenv
import os


SALARY_INPUT = 1

SKILLS_INPUT = 2

ANALYZE_INPUT = 3

TOPJOBS_INPUT = 4

GRADE_INPUT = 5

MAIN_MENU_TEXT = (
    "Вы можете воспользоваться следующими командами:\n"
    "/salary — прогноз зарплаты по вакансии\n"
    "/skills — топ-5 навыков по вакансии\n"
    "/analyze — сравнить вакансию с рынком\n"
    "/top — топ-вакансий по фильтрам\n"
    "/grade — определить грейд\n"
    "/help — справка"
)

# Загрузить переменные окружения из .env
load_dotenv(dotenv_path="/content/drive/MyDrive/hh-hr-bot/.env")

# Получить токен из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Отправляем картинку
    await update.message.reply_photo(
        photo=open('src/bot/baner.jpg', 'rb'),  # Укажи имя файла-баннера (jpg/png)
        caption="👋 Добро пожаловать в HR-бот!\n\nМогу предсказать зарплату, грейд, показать топ навыков и сравнить вакансию с рынком.\n\n"
        "📌Команды:\n"
        "/salary — прогноз зарплаты\n"
        "/grade — определение грейда\n"
        "/skills — топ-5 востребованных навыков\n"
        "/analyze — сравнить вакансию с рынком\n"
        "/nextskills — Навыки для карьерного роста\n"
        "/top — ТОП вакансий с рынком\n"
        "\nДля справки введите /help"
    )
    #await update.message.reply_text(
    #    "👋 Привет! Я HR-бот. Могу предсказать зарплату, грейд, показать топ навыков и сравнить вакансию с рынком.\n"
    #    "Команды:\n"
    #    "/salary — прогноз зарплаты\n"
    #    "/grade — определение грейда\n"
    ##    "/skills — топ-5 востребованных навыков\n"
     #   "/analyze — сравнить вакансию с рынком\n"
    #    "/nextskills — Навыки для карьерного роста\n"
    ##    "/top — ТОП вакансий с рынком\n"
     #   "\nДля справки введите /help"
    #)

# Состояния
SALARY_DESC, SALARY_CITY, SALARY_SKILLS, SALARY_GRADE = range(4)

async def salary_start(update, context):
    await update.message.reply_text(
        "Опишите вакансию (например: Python-разработчик, поддержка веб-сервиса, автоматизация бизнес-процессов):"
    )
    return SALARY_DESC

async def salary_get_city(update, context):
    context.user_data['description'] = update.message.text.strip()
    await update.message.reply_text("В каком городе или регионе расположена вакансия?")
    return SALARY_CITY

async def salary_get_skills(update, context):
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text(
        "Перечислите ключевые навыки через запятую (например: Python, Django, SQL, коммуникабельность):"
    )
    return SALARY_SKILLS

async def salary_get_grade(update, context):
    context.user_data['skills'] = [s.strip() for s in update.message.text.split(',')]
    await update.message.reply_text(
        "Укажите уровень вакансии (junior, middle, senior, lead).\n"
        "Если не знаете — напишите ‘-’ или оставьте пустым."
    )
    return SALARY_GRADE

async def salary_finish(update, context):
    grade_input = update.message.text.strip().lower()
    grade = grade_input if grade_input in ['junior', 'middle', 'senior', 'lead'] else None
    context.user_data['grade'] = grade

    # --- Готовим данные для модели ---
    description = context.user_data['description']
    city = context.user_data['city']
    skills = context.user_data['skills']
    grade = context.user_data['grade']

    # Найти area_id по названию города (твоя таблица area)

    area_id = get_area_id_by_city(city) or 0


    # Кодируем грейд
    exp_junior = int(grade == 'junior') if grade else 0
    exp_middle = int(grade == 'middle') if grade else 0
    exp_senior = int(grade == 'senior') if grade else 0
    exp_lead = int(grade == 'lead') if grade else 0

    # Остальные признаки
    desc_len = len(description)
    desc_words = len(description.split())
    title_len = min(desc_len, 40)
    num_skills = len(skills)

    features = {
        'area_id': area_id,
        'desc_len': desc_len,
        'desc_words': desc_words,
        'title_len': title_len,
        'num_skills': num_skills,
        'exp_junior': exp_junior,
        'exp_middle': exp_middle,
        'exp_senior': exp_senior,
        'exp_lead': exp_lead,
        'description': description,
        'title': description[:40],
        'salary_currency': "RUR"
    }
    salary = predict_salary(features)
    msg = (
        f"<b>Прогнозируемая зарплата по вакансии:</b> {int(salary):,}".replace(',', ' ') +f" {features['salary_currency']}\n\n"
        f"Ваши данные:\n"
        f"Город: {city} (area_id: {area_id})\n"
        f"Навыки: {', '.join(skills)}\n"
        f"Уровень: {grade if grade else 'не указан'}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
    await update.message.reply_text(MAIN_MENU_TEXT)
    return ConversationHandler.END

GRADE_DESC, GRADE_CITY, GRADE_SKILLS = range(3)

async def grade_start(update, context):
    await update.message.reply_text(
        "Опишите вакансию или свой опыт работы (например: Python-разработчик, поддержка веб-сервиса, автоматизация бизнес-процессов):"
    )
    return GRADE_DESC

async def grade_get_city(update, context):
    context.user_data['description'] = update.message.text.strip()
    await update.message.reply_text("В каком городе или регионе расположена вакансия (или где вы работаете)?")
    return GRADE_CITY

async def grade_get_skills(update, context):
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text(
        "Перечислите ключевые навыки через запятую (например: Python, Django, SQL, коммуникабельность):"
    )
    return GRADE_SKILLS

async def grade_finish(update, context):
    description = context.user_data['description']
    city = context.user_data['city']
    skills = [s.strip() for s in update.message.text.split(',')]

    area_id = get_area_id_by_city(city) or 0
    desc_len = len(description)
    desc_words = len(description.split())
    title = description[:40]
    title_len = len(title)
    num_skills = len(skills)

    # exp_* признаки все по 0 — модель сама определяет грейд
    features = {
        'area_id': area_id,
        'desc_len': desc_len,
        'desc_words': desc_words,
        'title_len': title_len,
        'num_skills': num_skills,
        'exp_junior': 0,
        'exp_middle': 0,
        'exp_senior': 0,
        'exp_lead': 0,
        'description': description,
        'title': title,
        'salary_currency': "RUR"
    }

    grade_code = predict_grade(features)
    grade_map = {0: "junior", 1: "middle", 2: "senior", 3: "lead"}
    grade_label = grade_map.get(grade_code, "unknown")

    msg = (
        f"<b>Определённый грейд:</b> <b>{grade_label.title()}</b> ({grade_code})\n\n"
        f"Ваши данные:\n"
        f"Город: {city} (area_id: {area_id})\n"
        f"Навыки: {', '.join(skills)}\n"
        f"Описание: {description[:40]}..."
    )
    await update.message.reply_text(msg, parse_mode="HTML")
    await update.message.reply_text(MAIN_MENU_TEXT)
    return ConversationHandler.END

SKILLS_TITLE, SKILLS_CITY, SKILLS_GRADE = range(3)

async def skills_start(update, context):
    await update.message.reply_text(
        "Введите профессию или краткое название вакансии (например: Python-разработчик, аналитик данных, менеджер по продажам):"
    )
    return SKILLS_TITLE

async def skills_get_city(update, context):
    context.user_data['title'] = update.message.text.strip()
    await update.message.reply_text("В каком городе или регионе вас интересует рынок вакансий?")
    return SKILLS_CITY

async def skills_get_grade(update, context):
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text(
        "Укажите уровень (junior, middle, senior, lead). Если не важен — напишите ‘-’ или оставьте пустым."
    )
    return SKILLS_GRADE

async def skills_finish(update, context):
    grade_input = update.message.text.strip().lower()
    title = context.user_data['title']
    city = context.user_data['city']
    grade = grade_input if grade_input in ['junior', 'middle', 'senior', 'lead'] else None

    # Получить area_id
    area_id = get_area_id_by_city(city) or 0

    # Преобразовать грейд в нужный формат для top_5_skills (int или str)
    grade_map = {'junior': 0, 'middle': 1, 'senior': 2, 'lead': 3}
    grade_code = grade_map.get(grade, None) if grade else None

    # Получить топ-5 навыков
    df = top_5_skills(title=title, area_id=area_id, grade=grade_code)

    if df.empty:
        await update.message.reply_text("Нет данных для выбранных параметров.")
        return ConversationHandler.END

    # Формируем красивый ответ
    msg = f"<b>Топ-5 навыков по запросу:</b>\nПрофессия: {title}\nГород: {city}\n"
    if grade:
        msg += f"Уровень: {grade}\n"
    msg += "\n"
    for i, row in df.iterrows():
        salary = f"{int(row['mean_salary']):,}".replace(',', ' ') if row['mean_salary'] else "-"
        msg += (
            f"{i+1}. <b>{row['skill_name']}</b> — {row['frequency']} вакансий, "
            f"ср. зарплата: {salary} руб.\n"
        )
    await update.message.reply_text(msg, parse_mode="HTML")
    await update.message.reply_text(MAIN_MENU_TEXT)
    return ConversationHandler.END

NEXTSKILLS_TITLE, NEXTSKILLS_CITY, NEXTSKILLS_FROM, NEXTSKILLS_TO = range(4)

async def nextskills_start(update, context):
    await update.message.reply_text(
        "Для какой профессии вы хотите узнать навыки для карьерного роста? (например: Python-разработчик)"
    )
    return NEXTSKILLS_TITLE

async def nextskills_get_city(update, context):
    context.user_data['title'] = update.message.text.strip()
    await update.message.reply_text("Укажите город или регион (или ‘-’ если не важно):")
    return NEXTSKILLS_CITY

async def nextskills_get_from(update, context):
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text(
        "С какого грейда хотите начать (junior, middle, senior)?"
    )
    return NEXTSKILLS_FROM

async def nextskills_get_to(update, context):
    context.user_data['grade_from'] = update.message.text.strip().lower()
    await update.message.reply_text(
        "На какой грейд хотите перейти (middle, senior, lead)?"
    )
    return NEXTSKILLS_TO

async def nextskills_finish(update, context):
    grade_to = update.message.text.strip().lower()
    title = context.user_data['title']
    city = context.user_data['city']
    grade_from = context.user_data['grade_from']

    # Получить area_id
    area_id = get_area_id_by_city(city) if city and city != '-' else None

    # Аналитика
    result = promotion_skills(title=title, area_id=area_id, grade_from=grade_from, grade_to=grade_to, top_n=7)
    if not result:
        await update.message.reply_text("Нет данных для выбранных параметров или мало вакансий для анализа.")
    else:
        msg = (
            f"Для перехода с <b>{grade_from}</b> на <b>{grade_to}</b> по профессии <b>{title}</b> "
            f"на рынке чаще всего выделяют навыки:\n"
        )
        for i, (skill, delta, freq) in enumerate(result, 1):
            msg += f"{i}. <b>{skill}</b> (+{delta} вакансий, всего {freq})\n"
        await update.message.reply_text(msg, parse_mode="HTML")

    await update.message.reply_text(MAIN_MENU_TEXT)
    return ConversationHandler.END

ANALYZE_DESC, ANALYZE_CITY, ANALYZE_SKILLS, ANALYZE_SALARY = range(4)

async def analyze_start(update, context):
    await update.message.reply_text(
        "Опишите вакансию или ваш опыт работы (например: Python-разработчик, поддержка веб-сервиса, автоматизация бизнес-процессов):"
    )
    return ANALYZE_DESC

async def analyze_get_city(update, context):
    context.user_data['description'] = update.message.text.strip()
    await update.message.reply_text("В каком городе или регионе расположена вакансия (или где вы работаете)?")
    return ANALYZE_CITY

async def analyze_get_skills(update, context):
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text(
        "Перечислите ключевые навыки через запятую (например: Python, Django, SQL, коммуникабельность):"
    )
    return ANALYZE_SKILLS

#async def analyze_get_grade(update, context):
#    context.user_data['skills'] = [s.strip() for s in update.message.text.split(',')]
#    await update.message.reply_text(
#        "Укажите уровень (junior, middle, senior, lead). Если не важен — напишите ‘-’ или оставьте пустым."
#    )
 #   return SKILLS_GRADE    

async def analyze_get_salary(update, context):
    context.user_data['skills'] = [s.strip() for s in update.message.text.split(',')]
    await update.message.reply_text(
        "Укажите вашу зарплату (если хотите сравнить с рынком). Если не хотите — напишите ‘-’ или оставьте пустым."
    )
    return ANALYZE_SALARY

async def analyze_finish(update, context):
    description = context.user_data['description']
    city = context.user_data['city']
    skills = context.user_data['skills']
    salary_input = update.message.text.strip()
    try:
        salary_rub = int(salary_input.replace(' ', '').replace('руб', '')) if salary_input and salary_input != '-' else None
    except ValueError:
        salary_rub = None

    area_id = get_area_id_by_city(city) or 0

    vac = {
        'title': description[:40],          # для title
        'area_id': area_id,
        'experience_hh': None,              # если хочешь — добавить шаг с опытом
        'skills': skills,
        'salary_rub': salary_rub
    }

    # Анализ
    result = compare_vacancy_to_market(vac)
    await update.message.reply_text(result)
    await update.message.reply_text(MAIN_MENU_TEXT)
    return ConversationHandler.END

TOP_CITY, TOP_TITLE, TOP_GRADE = range(3)

async def top_start(update, context):
    await update.message.reply_text("В каком городе или регионе вас интересуют вакансии?")
    return TOP_CITY

async def top_get_title(update, context):
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text(
        "Введите ключевое слово или профессию (например: Python, маркетолог, менеджер по продажам):"
    )
    return TOP_TITLE

async def top_get_grade(update, context):
    context.user_data['title'] = update.message.text.strip()
    await update.message.reply_text(
        "Укажите уровень (junior, middle, senior, lead), если важно. Если не важно — напишите ‘-’ или оставьте пустым."
    )
    return TOP_GRADE

async def top_finish(update, context):
    city = context.user_data['city']
    title = context.user_data['title']
    grade_input = update.message.text.strip().lower()

    area_id = get_area_id_by_city(city) or 0

    grade_map = {'junior': 0, 'middle': 1, 'senior': 2, 'lead': 3}
    grade = grade_map.get(grade_input, None) if grade_input and grade_input != '-' else None

    # Получаем топ-вакансий (твоя функция должна возвращать DataFrame/список вакансий)
    df = top_vacancies(area_name=city, keyword=title, grade=grade)

    if df.empty:
        await update.message.reply_text("Не найдено вакансий по заданным параметрам.")
        await update.message.reply_text(MAIN_MENU_TEXT)
        return ConversationHandler.END

    msg = f"<b>Топ-5 вакансий по вашему запросу:</b>\nГород: {city}\nПрофессия: {title}\n"
    if grade_input and grade_input != '-':
        msg += f"Грейд: {grade_input}\n"
    msg += "\n"
    for i, row in df.iterrows():
        salary = f"{int(row['salary_rub']):,}".replace(',', ' ') if row['salary_rub'] else "-"
        msg += (
            f"{i+1}. <b>{row['title']}</b> ({row['employer']})\n"
            f"Зарплата: {salary} руб.\n"
            f"Город: {city}\n"
            "— — —\n"
        )
    await update.message.reply_text(msg, parse_mode="HTML")
    await update.message.reply_text(MAIN_MENU_TEXT)
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Напиши /salary, /grade, /skills или /analyze для получения аналитики по рынку труда.\n"
        "/salary — Команда позволяет быстро получить прогноз средней зарплаты по любой вакансии.\n" 
        "Подходит и работодателям, и соискателям: можно оценить “адекватность” зарплаты для предложенной позиции на рынке.\n"
        
    )

def main():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_salary = ConversationHandler(
        entry_points=[CommandHandler("salary", salary_start)],
        states={
            SALARY_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, salary_get_city)],
            SALARY_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, salary_get_skills)],
            SALARY_SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, salary_get_grade)],
            SALARY_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, salary_finish)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )

    conv_skills = ConversationHandler(
       entry_points=[CommandHandler("skills", skills_start)],
        states={
            SKILLS_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, skills_get_city)],
            SKILLS_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, skills_get_grade)],
            SKILLS_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, skills_finish)],
        },
            fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )

    conv_topjobs = ConversationHandler(
        entry_points=[CommandHandler("top", top_start)],
        states={
            TOP_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, top_get_title)],
            TOP_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, top_get_grade)],
            TOP_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, top_finish)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )

    conv_grade = ConversationHandler(
        entry_points=[CommandHandler("grade", grade_start)],
        states={
            GRADE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, grade_get_city)],
            GRADE_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, grade_get_skills)],
            GRADE_SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, grade_finish)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )

    # Добавить handler:
    conv_nextskills = ConversationHandler(
        entry_points=[CommandHandler("nextskills", nextskills_start)],
        states={
            NEXTSKILLS_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nextskills_get_city)],
            NEXTSKILLS_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, nextskills_get_from)],
            NEXTSKILLS_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, nextskills_get_to)],
            NEXTSKILLS_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, nextskills_finish)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )
    conv_analyze = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_start)],
        states={
            ANALYZE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_get_city)],
            ANALYZE_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_get_skills)],
            ANALYZE_SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_get_salary)],
            ANALYZE_SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_finish)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_salary)
    app.add_handler(conv_skills)
    app.add_handler(conv_analyze)
    app.add_handler(conv_topjobs)
    app.add_handler(conv_grade)
    app.add_handler(conv_nextskills)


    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
