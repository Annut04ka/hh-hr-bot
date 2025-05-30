from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes,MessageHandler, filters, ConversationHandler
from model_inference import predict_salary
from telegram.constants import ParseMode
from market_analytics import top_5_skills, compare_vacancy_to_market
import pandas as pd


SALARY_INPUT = 1

SKILLS_INPUT = 2

ANALYZE_INPUT = 3

TELEGRAM_TOKEN = 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я HR-бот. Могу предсказать зарплату, грейд, показать топ навыков и сравнить вакансию с рынком.\n"
        "Команды:\n"
        "/salary — прогноз зарплаты\n"
        "/grade — определение грейда\n"
        "/skills — топ-5 востребованных навыков\n"
        "/analyze — сравнить вакансию с рынком\n"
        "\nДля справки введите /help"
    )
async def salary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите параметры вакансии через запятую в формате:\n"
        "area_id, desc_len, desc_words, title_len, num_skills, exp_junior, exp_middle, exp_senior, exp_lead, description, title, salary_currency\n\n"
        "Пример:\n"
        "3, 1200, 100, 30, 4, 0, 1, 0, 0, Python-разработчик, Python developer, RUR"
    )
    return SALARY_INPUT

async def handle_salary_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 12:
            await update.message.reply_text("Ошибка: введено слишком мало параметров. Проверьте формат.")
            return SALARY_INPUT

        features = {
            'area_id': int(parts[0]),
            'desc_len': int(parts[1]),
            'desc_words': int(parts[2]),
            'title_len': int(parts[3]),
            'num_skills': int(parts[4]),
            'exp_junior': int(parts[5]),
            'exp_middle': int(parts[6]),
            'exp_senior': int(parts[7]),
            'exp_lead': int(parts[8]),
            'description': parts[9],
            'title': parts[10],
            'salary_currency': parts[11]
        }
        salary = predict_salary(features)
        await update.message.reply_text(
            f"Прогнозируемая зарплата: <b>{int(salary):,} {features['salary_currency']}</b>",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
        return SALARY_INPUT

async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите параметры через запятую в формате:\n"
        "title, area_id, grade (например: Python developer, 3, 2)\n"
        "Где grade: 0 — junior, 1 — middle, 2 — senior, 3 — lead\n"
        "Можно оставить grade или area_id пустым, если хотите искать по всем регионам/грейдам."
    )
    return SKILLS_INPUT

async def handle_skills_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        parts = [p.strip() for p in text.split(",")]

        title = parts[0] if len(parts) > 0 and parts[0] else None
        area_id = int(parts[1]) if len(parts) > 1 and parts[1] else None
        grade = int(parts[2]) if len(parts) > 2 and parts[2] else None

        result = top_5_skills(title=title, area_id=area_id, grade=grade)

        if result.empty:
            await update.message.reply_text("Нет данных для указанных параметров.")
        else:
            msg = "Топ-5 востребованных навыков:\n"
            for i, row in result.iterrows():
                msg += f"{i+1}. {row['skill_name']} — {row['frequency']} вакансий, средняя зарплата: {int(row['mean_salary']) if not pd.isna(row['mean_salary']) else '-'}\n"
            await update.message.reply_text(msg)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
        return SKILLS_INPUT

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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши /salary, /grade, /skills или /analyze для получения аналитики по рынку труда.")

def main():
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_salary = ConversationHandler(
        entry_points=[CommandHandler("salary", salary_command)],
        states={
            SALARY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_salary_input)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )

    conv_skills = ConversationHandler(
        entry_points=[CommandHandler("skills", skills_command)],
        states={
            SKILLS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_skills_input)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
    )
    conv_analyze = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_command)],
        states={
            ANALYZE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_analyze_input)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Операция отменена."))]
     )


    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_salary)
    app.add_handler(conv_skills)
    app.add_handler(conv_analyze)


    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
