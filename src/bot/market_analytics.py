import duckdb

# Подключение к базе (укажи свой путь, если другой)
con = duckdb.connect('/content/drive/MyDrive/hh-hr-bot/data/hh.duckdb_3000')

# Карта грейдов для удобной фильтрации по “человеческим” грейдам
grade_map = {
    'Нет опыта': 0,          # junior
    'От 1 года до 3 лет': 1, # middle
    'От 3 до 6 лет': 2,      # senior
    'Более 6 лет': 3         # lead
}

def top_5_skills(title=None, area_id=None, grade=None):
    """
    Возвращает топ-5 навыков по частоте и средней зарплате.
    Фильтры:
      - title (str): фильтр по профессии (подстрока в названии вакансии)
      - area_id (int): фильтр по региону
      - grade (int/str): фильтр по грейду (0-3 или "Нет опыта", ...)
    """
    # Преобразуем grade к строке на русском, если нужно
    experience_hh = None
    if grade is not None:
        if isinstance(grade, int):
            for k, v in grade_map.items():
                if v == grade:
                    experience_hh = k
                    break
        elif grade in grade_map:
            experience_hh = grade
        else:
            raise ValueError("grade должен быть int (0-3) или одним из: " + ", ".join(grade_map.keys()))

    query = """
    SELECT
        vs.skill_name,
        COUNT(*) AS frequency,
        ROUND(AVG(vp.salary_rub), 0) AS mean_salary
    FROM vacancy_skill vs
    JOIN vacancy v ON vs.vacancy_id = v.id
    JOIN vacancy_proc vp ON v.id = vp.id
    WHERE 1=1
    """
    params = []
    if title:
        query += " AND LOWER(v.title) LIKE ?"
        params.append(f"%{title.lower()}%")
    if area_id is not None:
        query += " AND v.area_id = ?"
        params.append(area_id)
    if experience_hh is not None:
        query += " AND v.experience_hh = ?"
        params.append(experience_hh)
    query += """
    GROUP BY vs.skill_name
    ORDER BY frequency DESC
    LIMIT 5
    """
    return con.execute(query, params).df()

def compare_vacancy_to_market(vac: dict):
    """
    Сравнивает переданную вакансию (dict) с рынком аналогичных вакансий:
      - title (str)
      - area_id (int)
      - experience_hh (str, например, 'От 1 года до 3 лет')
      - skills (list или строка через ;)
      - salary_rub (int/float, опционально)
    Возвращает текстовый отчёт с анализом зарплаты и навыков.
    """
    title = vac['title']
    area_id = vac['area_id']
    experience_hh = vac['experience_hh']
    skills = vac['skills']
    salary = vac.get('salary_rub', None)

    # === 1. Формируем "аналогичный рынок" вакансий ===
    query = """
    SELECT v.id, v.title, v.area_id, v.experience_hh, vp.salary_rub
    FROM vacancy v
    JOIN vacancy_proc vp ON v.id = vp.id
    WHERE v.area_id = ?
      AND v.experience_hh = ?
      AND LOWER(v.title) LIKE ?
      AND vp.salary_rub IS NOT NULL
    """
    params = [area_id, experience_hh, f"%{title.lower()}%"]
    df_market = con.execute(query, params).fetchdf()

    if df_market.empty:
        return "Нет сопоставимых вакансий для сравнения."

    # === 2. Медианная зарплата по рынку ===
    market_salary = df_market['salary_rub'].median()
    result = ""
    if salary:
        diff = salary - market_salary
        perc = round(100 * diff / market_salary, 1)
        result += (
            f"Ваша вакансия: {title} ({experience_hh}, регион {area_id})\n"
            f"Зарплата: {int(salary)} руб.\n"
            f"Медиана рынка: {int(market_salary)} руб.\n"
            f"Отклонение: {'+' if diff > 0 else ''}{int(diff)} руб. "
            f"({'+' if perc > 0 else ''}{perc}%)\n"
        )
    else:
        result += (
            f"Ваша вакансия: {title} ({experience_hh}, регион {area_id})\n"
            f"Медиана зарплаты по рынку: {int(market_salary)} руб.\n"
        )

    # === 3. Анализ навыков ===
    # BinderError fix: явно приводим id к BIGINT
    q_skills = """
    SELECT vs.skill_name
    FROM vacancy_skill vs
    WHERE vs.vacancy_id IN (
        SELECT CAST(v.id AS BIGINT)
        FROM vacancy v
        WHERE v.area_id = ?
          AND v.experience_hh = ?
          AND LOWER(v.title) LIKE ?
    )
    """
    skills_df = con.execute(q_skills, params).fetchdf()

    if not skills_df.empty:
        top_skills = (
            skills_df['skill_name']
            .value_counts()
            .head(10)
            .index
            .tolist()
        )
        if isinstance(skills, str):
            your_skills = [s.strip() for s in skills.split(';') if s.strip()]
        else:
            your_skills = list(skills)
        common = [s for s in your_skills if s in top_skills]
        unique = [s for s in your_skills if s not in top_skills]
        missing = [s for s in top_skills if s not in your_skills]
        result += (
            f"\nВаши навыки: {', '.join(your_skills)}\n"
            f"Топ-10 популярных навыков на рынке: {', '.join(top_skills)}\n"
        )
        if unique:
            result += f"Уникальные для вас навыки (редко встречаются): {', '.join(unique)}\n"
        if missing:
            result += f"Рекомендуется добавить популярные навыки: {', '.join(missing)}\n"
    return result

#получение города
def get_area_id_by_city(city_name):
    """
    Возвращает area_id по названию города (или None, если не найдено).
    Поиск регистронезависимый и по подстроке.
    """
    query = "SELECT area_id FROM cities WHERE LOWER(area_name) LIKE ? LIMIT 1"
    result = con.execute(query, [f"%{city_name.lower()}%"]).fetchdf()
    if not result.empty:
        return int(result.iloc[0]['area_id'])
    else:
        return None

def top_vacancies(area_name=None, keyword=None, grade=None, limit=5):
    """
    Возвращает топ-вакансий по зарплате с учётом фильтров.
    area_name: (str) — название города или региона (например, 'Москва')
    keyword: (str) — ключевое слово в названии вакансии (например, 'python')
    grade: (int/str) — грейд (например, 1 или 'От 1 года до 3 лет')
    limit: (int) — сколько вакансий показать
    """
    # Поиск area_id по названию региона
    area_id = None
    if area_name:
        area_query = "SELECT id FROM area WHERE LOWER(name) LIKE ? LIMIT 1"
        df_area = con.execute(area_query, [f"%{area_name.lower()}%"]).fetchdf()
        if not df_area.empty:
            area_id = int(df_area.iloc[0]['id'])
        else:
            area_id = None

    # Фильтр по грейду
    experience_hh = None
    if grade is not None:
        if isinstance(grade, int):
            for k, v in grade_map.items():
                if v == grade:
                    experience_hh = k
                    break
        elif grade in grade_map:
            experience_hh = grade
        else:
            experience_hh = grade  # Вдруг ввели текст напрямую

    query = """
    SELECT v.title, v.employer, v.area_id, v.experience_hh, vp.salary_rub
    FROM vacancy v
    JOIN vacancy_proc vp ON v.id = vp.id
    WHERE vp.salary_rub IS NOT NULL
    """
    params = []
    if area_id:
        query += " AND v.area_id = ?"
        params.append(area_id)
    if keyword:
        query += " AND LOWER(v.title) LIKE ?"
        params.append(f"%{keyword.lower()}%")
    if experience_hh:
        query += " AND v.experience_hh = ?"
        params.append(experience_hh)
    query += """
    ORDER BY vp.salary_rub DESC
    LIMIT ?
    """
    params.append(limit)

    return con.execute(query, params).fetchdf()
