
import os
import joblib
import pickle
import numpy as np
from scipy import sparse
from sentence_transformers import SentenceTransformer

MODEL_DIR = '/content/drive/MyDrive/hh-hr-bot/models'

SALARY_MODEL_PATH = os.path.join(MODEL_DIR, 'salary_lgbm_model.pkl')
GRADE_MODEL_PATH = os.path.join(MODEL_DIR, 'grade_rf_model.joblib')
TFIDF_DESC_PATH = os.path.join(MODEL_DIR, 'tfidf_desc.pkl')
TFIDF_TITLE_PATH = os.path.join(MODEL_DIR, 'tfidf_title.pkl')
OHE_CATS_PATH = os.path.join(MODEL_DIR, 'ohe_cats.pkl')

salary_model = joblib.load(SALARY_MODEL_PATH)
grade_model = joblib.load(GRADE_MODEL_PATH)

with open(TFIDF_DESC_PATH, 'rb') as f:
    tfidf_desc = pickle.load(f)
with open(TFIDF_TITLE_PATH, 'rb') as f:
    tfidf_title = pickle.load(f)
with open(OHE_CATS_PATH, 'rb') as f:
    ohe = pickle.load(f)

minilm_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

def prepare_features_full(features: dict):
    """ Полный пайплайн для salary (668 признаков) """
    num_feats = np.array([
        features.get('area_id', 0),
        features.get('desc_len', 0),
        features.get('desc_words', 0),
        features.get('title_len', 0),
        features.get('num_skills', 0),
        features.get('exp_junior', 0),
        features.get('exp_middle', 0),
        features.get('exp_senior', 0),
        features.get('exp_lead', 0)
    ]).reshape(1, -1)

    desc = features.get('description', "")
    tfidf_desc_vec = tfidf_desc.transform([desc])
    title = features.get('title', "")
    tfidf_title_vec = tfidf_title.transform([title])
    area_id = str(features.get('area_id', ""))
    salary_currency = str(features.get('salary_currency', "RUR"))
    ohe_cats_vec = ohe.transform([[area_id, salary_currency]])
    emb_vec = minilm_model.encode([desc])  # (1, 384)
    X = sparse.hstack([
        num_feats, tfidf_desc_vec, tfidf_title_vec, ohe_cats_vec, emb_vec
    ]).tocsr()
    return X

def prepare_features_emb_only(features: dict):
    """ Только эмбеддинг по описанию для grade-классификатора (384 признака) """
    desc = features.get('description', "")
    emb_vec = minilm_model.encode([desc])  # (1, 384)
    return emb_vec

def predict_salary(features: dict) -> float:
    X = prepare_features_full(features)
    salary_pred = salary_model.predict(X)[0]
    return float(salary_pred)

def predict_grade(features: dict) -> int:
    X = prepare_features_emb_only(features)
    grade_pred = grade_model.predict(X)[0]
    return int(grade_pred)

def predict_salary_response(features: dict) -> dict:
    value = predict_salary(features)
    return {
        "salary": int(value),
        "currency": features.get("salary_currency", "RUR")
    }

def predict_grade_response(features: dict) -> dict:
    code = predict_grade(features)
    grade_map = {0: "junior", 1: "middle", 2: "senior", 3: "lead"}
    return {
        "grade_code": int(code),
        "grade_label": grade_map.get(code, "unknown")
    }    

#if __name__ == "__main__":
#    test_features = {
#        'area_id': 3,
#        'desc_len': 1400,
#        'desc_words': 120,
#        'title_len': 30,
#       'num_skills': 4,
#      'exp_junior': 0,
#        'exp_middle': 1,
#        'exp_senior': 0,
#        'exp_lead': 0,
#        'description': "Python-разработчик, опыт с Django и PostgreSQL, удалёнка.",
#        'title': "Python developer",
#        'salary_currency': "RUR"
#    }
#    print("Зарплата:", predict_salary(test_features))
#    print("Грейд:", predict_grade(test_features))

