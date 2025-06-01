from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes,MessageHandler, filters, ConversationHandler
from model_inference import predict_salary, predict_salary_response, predict_grade
from telegram.constants import ParseMode
from market_analytics import top_5_skills, compare_vacancy_to_market, top_vacancies, get_area_id_by_city, promotion_skills
import pandas as pd


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

TELEGRAM_TOKEN = '7772058273:AAHb5uhZ8UsH-rHy_ORS7e34rBAyKpyoksk'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я HR-бот. Могу предсказать зарплату, грейд, показать топ навыков и сравнить вакансию с рынком.\n"
        "Команды:\n"
        "/salary — прогноз зарплаты\n"
        "/grade — определение грейда\n"
        "/skills — топ-5 востребованных навыков\n"
        "/analyze — сравнить вакансию с рынком\n"
        "/nextskills — Навыки для карьерного роста\n"
        "/top — ТОП вакансий с рынком\n"
        "\nДля справки введите /help"
    )

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

async def grade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите параметры вакансии через запятую в формате:\n"
        "desc_len, desc_words, num_skills, description\n"
        "Пример:\n"
        "1200, 100, 4, Python-разработчик с опытом работы в команде, знание SQL и Django"
    )
    return GRADE_INPUT

async def handle_grade_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        parts = text.split(",", 3)  # Только первые 3 запятые разбивают на 4 части

        if len(parts) < 4:
            await update.message.reply_text("Ошибка: введено слишком мало параметров. Проверьте формат.")
            return GRADE_INPUT

        features = {
            'desc_len': int(parts[0].strip()),
            'desc_words': int(parts[1].strip()),
            'num_skills': int(parts[2].strip()),
            'description': parts[3].strip()
        }

        grade_code = predict_grade(features)
        grade_map = {
            0: "junior",
            1: "middle",
            2: "senior",
            3: "lead"
        }
        grade_label = grade_map.get(grade_code, "unknown")
        await update.message.reply_text(
            f"Определённый грейд: <b>{grade_label.title()} ({grade_code})</b>",
            parse_mode="HTML"
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
        return GRADE_INPUT

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

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите параметры через запятую в формате:\n"
        "title, area_id, experience_hh, skills, salary_rub\n"
        "Пример:\n"
        "Python developer, 3, От 1 года до 3 лет, Python;SQL;Django;English, 120000\n"
        "Если не хотите указывать зарплату — оставьте поле пустым (последний параметр)."
    )
    return ANALYZE_INPUT

async def handle_analyze_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        parts = [p.strip() for p in text.split(",")]

        if len(parts) < 4:
            await update.message.reply_text("Ошибка: слишком мало параметров. Проверьте формат.")
            return ANALYZE_INPUT

        title = parts[0]
        area_id = int(parts[1])
        experience_hh = parts[2]
        skills = parts[3]
        salary_rub = int(parts[4]) if len(parts) > 4 and parts[4] else None

        vacancy = {
            'title': title,
            'area_id': area_id,
            'experience_hh': experience_hh,
            'skills': skills,
            'salary_rub': salary_rub
        }
        result = compare_vacancy_to_market(vacancy)
        await update.message.reply_text(result)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
        return ANALYZE_INPUT

async def topjobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите параметры через пробел:\n"
        "город ключевое_слово_в_названии грейд (например: Москва python 1)\n"
        "Грейд: 0 — junior, 1 — middle, 2 — senior, 3 — lead.\n"
        "Если хотите искать по всем грейдам — оставьте поле пустым."
    )
    return TOPJOBS_INPUT

async def handle_topjobs_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        parts = text.split()

        if len(parts) < 2:
            await update.message.reply_text("Ошибка: укажите хотя бы город и ключевое слово.")
            return TOPJOBS_INPUT

        area_name = parts[0]
        keyword = parts[1]
        grade = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None

        df = top_vacancies(area_name=area_name, keyword=keyword, grade=grade, limit=5)
        if df.empty:
            await update.message.reply_text("Вакансий не найдено по указанным фильтрам.")
            return ConversationHandler.END

        msg = "Топ-5 вакансий:\n"
        for i, row in df.iterrows():
            msg += (f"{i+1}. {row['title']} ({row['employer']})\n"
                    f"   Город: {area_name}, Грейд: {row['experience_hh']}\n"
                    f"   Зарплата: {int(row['salary_rub'])} руб.\n")
        await update.message.reply_text(msg)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
        return TOPJOBS_INPUT

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши /salary, /grade, /skills или /analyze для получения аналитики по рынку труда.")

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
        entry_points=[CommandHandler("top", topjobs_command)],
        states={
            TOPJOBS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topjobs_input)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )
    conv_grade = ConversationHandler(
        entry_points=[CommandHandler("grade", grade_command)],
        states={
            GRADE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_grade_input)],
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_salary)
    app.add_handler(conv_skills)
    #app.add_handler(conv_analyze)
    app.add_handler(conv_topjobs)
    app.add_handler(conv_grade)
    app.add_handler(conv_nextskills)


    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
