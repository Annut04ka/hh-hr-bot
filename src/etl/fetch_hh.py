import requests
import time
import pandas as pd
import duckdb
from tqdm import tqdm
from pathlib import Path

Path("data/raw").mkdir(parents=True, exist_ok=True)

# Какие регионы выгружаем (можно расширить!)
REGIONS = [
    1,    # Москва
    2,    # Санкт-Петербург
    3,    # Екатеринбург
    4,    # Новосибирск
    #66,   # Красноярск
    78,   # Нижний Новгород,
    #5,
    #8 
    # Добавь ещё, если хочешь (id смотри в справочнике hh.ru)
]

PAGES_PER_REGION = 1   # максимум 500 вакансий на регион
PER_PAGE = 10

def fetch_vacancy_ids(pages=1, per_page=10, area="1"):
    """Собирает id вакансий по поиску"""
    vac_ids = []
    for page in tqdm(range(pages), desc="Выгружаем id"):
        url = "https://api.hh.ru/vacancies"
        params = dict(area=area, per_page=per_page, page=page, text="*")
        r = requests.get(url, params=params)
        for item in r.json()["items"]:
            vac_ids.append(item["id"])
        time.sleep(0.2)
    return vac_ids

def fetch_full_vacancies(vac_ids):
    """Детально собирает вакансии по id (description, key_skills и др.)"""
    all_rows = []
    for vid in tqdm(vac_ids, desc="Грузим вакансии по id"):
        url = f"https://api.hh.ru/vacancies/{vid}"
        v = requests.get(url).json()
        # ПРОВЕРКА!
        if not v or 'id' not in v:
            print(f"Нет id для {vid}, ответ: {v}")
            continue
        all_rows.append({
            "id": v["id"],
            "title": v["name"],
            "published_at": v["published_at"],
            "description": v.get("description", ""),
            "salary_from": (v["salary"] or {}).get("from") if v.get("salary") else None,
            "salary_to": (v["salary"] or {}).get("to") if v.get("salary") else None,
            "salary_currency": (v["salary"] or {}).get("currency") if v.get("salary") else None,
            "experience_hh": (v.get("experience") or {}).get("name"),
            "area_id": int(v["area"]["id"]),
            "skills_raw": ", ".join(s["name"] for s in v.get("key_skills", [])),
            "employer": v.get("employer", {}).get("name", "")
        })
        time.sleep(1.00)  # не перегружаем hh.ru
    return pd.DataFrame(all_rows)

if __name__ == "__main__":
    # 5 страницы по 100 = 500 вакансий на регион (можно увеличить до лимита)
    #vac_ids = fetch_vacancy_ids(pages=3, per_page=100, area="113")
    #df = fetch_full_vacancies(vac_ids)
    all_vac_ids = set()
    for area in REGIONS:
        print(f"\n=== Грузим регион area_id={area} ===")
        ids = fetch_vacancy_ids(pages=PAGES_PER_REGION, per_page=PER_PAGE, area=str(area))
        all_vac_ids.update(ids)
    print(f"\nИтого уникальных вакансий: {len(all_vac_ids)}")

    new_vacancies_df = fetch_full_vacancies(list(all_vac_ids))
    # Сохраняем в csv
    #df.to_csv("data/raw/sample_vacancies_3000.csv", index=False)

    # Считай старый датасет с новым полем employer
    old_df = pd.read_csv("data/raw/sample_vacancies_3000.csv")

    # Добавь новые вакансии к старым
    all_df = pd.concat([old_df, new_vacancies_df], ignore_index=True)

    # Сохрани итоговый файл
    all_df.to_csv("data/raw/sample_vacancies_3000.csv", index=False)
    print(f"\n=== обновили файл")

    # Сохраняем в DuckDB
    #con = duckdb.connect("data/hh.duckdb_3000")
    #con.execute("CREATE OR REPLACE TABLE vacancy AS SELECT * FROM df")
    #con.close()
    #print(f"Сохранили {len(df)} вакансий в data/raw/sample_vacancies_3000.csv и data/hh.duckdb_3000")
 

    # Подключаемся к базе
    con = duckdb.connect('/content/drive/MyDrive/hh-hr-bot/data/hh.duckdb_3000')

    # Пусть new_vacancies_df — твой DataFrame с новыми вакансиями и skills_list

    # 1. Добавление новых вакансий
    existing_ids = set(con.execute("SELECT id FROM vacancy").fetchdf()['id'].astype(str))
    new_df = new_vacancies_df[~new_vacancies_df['id'].astype(str).isin(existing_ids)]
    vacancy_cols = ['id', 'title', 'published_at', 'description', 'salary_from', 'salary_to',
                    'salary_currency', 'experience_hh', 'area_id', 'skills_raw', 'employer']
    #con.executemany(
    #    f"INSERT INTO vacancy ({', '.join(vacancy_cols)}) VALUES ({', '.join(['?']*len(vacancy_cols))})",
    #    new_df[vacancy_cols].values.tolist()
    params = new_df[vacancy_cols].values.tolist()
    if  params:
       con.executemany(
           f"INSERT INTO vacancy ({', '.join(vacancy_cols)}) VALUES ({', '.join(['?']*len(vacancy_cols))})",
           params
       )
       print(f"Добавлено строк: {len(params)}")
    else:
       print("Нет новых строк для вставки.")    
    #)

    # 2. Добавление новых навыков
    all_new_skills = set()
    for skills in new_df['skills_raw']:
        if pd.notnull(skills):
            for s in skills:
                all_new_skills.add(s.strip().lower())
    existing_skills = set(con.execute("SELECT name FROM skill").fetchdf()['name'].str.lower())
    to_add = list(all_new_skills - existing_skills)
    for skill in to_add:
        con.execute("INSERT INTO skill(name) VALUES (?)", [skill])

    # 3. Добавление связей vacancy_skill
    # Получаем set всех названий навыков в нижнем регистре
    skill_names = set(s.lower().strip() for s, in con.execute("SELECT name FROM skill").fetchall())

    for _, row in new_df.iterrows():
       vid = row['id']
       # skills_raw — строка "Python, SQL, ..." → преобразуем в список
       if pd.notnull(row['skills_raw']):
           for s in str(row['skills_raw']).split(','):
               s_norm = s.strip().lower()
               if s_norm in skill_names:
                   # Записываем пару: id вакансии, строка-навык
                   con.execute(
                       "INSERT INTO vacancy_skill (vacancy_id, skill_name) VALUES (?, ?)",
                       [vid, s.strip()]
                   )
    con.close()              
