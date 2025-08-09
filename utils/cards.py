# utils/cards.py

import json

def load_hypotheses():
    with open("data_json/cards_ru_part.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data  # <- это список карточек