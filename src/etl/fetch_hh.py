import requests
import time
import pandas as pd
import duckdb
from tqdm import tqdm
from pathlib import Path

Path("data/raw").mkdir(parents=True, exist_ok=True)

def fetch_vacancy_ids(pages=3, per_page=100, area="113"):
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
            "skills_raw": ", ".join(s["name"] for s in v.get("key_skills", []))
        })
        time.sleep(0.05)  # не перегружаем hh.ru
    return pd.DataFrame(all_rows)

if __name__ == "__main__":
    # 3 страницы по 100 = 300 вакансий (можно увеличить до лимита)
    vac_ids = fetch_vacancy_ids(pages=3, per_page=100, area="113")
    df = fetch_full_vacancies(vac_ids)
    # Сохраняем в csv
    df.to_csv("data/raw/sample_vacancies.csv", index=False)
    # Сохраняем в DuckDB
    con = duckdb.connect("data/hh.duckdb")
    con.execute("CREATE OR REPLACE TABLE vacancy AS SELECT * FROM df")
    con.close()
    print(f"Сохранили {len(df)} вакансий в data/raw/sample_vacancies.csv и data/hh.duckdb")
