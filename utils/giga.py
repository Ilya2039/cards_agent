import logging
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_gigachat import GigaChat
from config import AUTH_GIGA

# === Настройка логирования ===
logger = logging.getLogger("utils.giga")
logger.setLevel(logging.INFO)

log_path = os.path.join(os.path.dirname(__file__), "card_checks.log")
file_handler = logging.FileHandler(log_path, encoding="utf-8")
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")
file_handler.setFormatter(formatter)

if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    logger.addHandler(file_handler)

# === Модель ===
llm = GigaChat(
    credentials=AUTH_GIGA,
    verify_ssl_certs=False,
    scope="GIGACHAT_API_CORP",
    model="GigaChat-2-Max",
    profanity_check=False,
    timeout=999,
    temperature=0.0,
)

def build_relevance_prompt(card_title: str, dialog_text: str) -> str:
    return f"""Ты — опытный бизнес-аналитик. Проанализируй, относится ли тема \"{card_title}\" к приведённому бизнес-контексту.

Контекст включает:
— Стратегический диалог с клиентом
— Финансовые показатели компании (например: прибыль, выручка, рентабельность, издержки)
— Описание проблем, целей, планов и внешней среды компании

Инструкция:
Определи, действительно ли тема гипотезы напрямую связана с ситуацией в контексте. Учитывай как смысл, так и конкретные данные — особенно финансовые. Не соглашайся, если связь лишь косвенная. Важна точная релевантность.

Ответь строго:
- Сначала «да» или «нет» (с маленькой буквы)
- Затем кратко поясни, почему

Контекст:
\"\"\"
{dialog_text}
\"\"\"
"""

def build_prompt_for_questions(card: dict, dialog_text: str) -> str:
    hyp_text = "\n".join(f"- {h}" for h in card["hypotheses"])
    action_text = "\n".join(f"- {a}" for a in card["actions"])

    return f"""Ты - профессиональный консалтер, который готовится к бизнес-встрече с клиентом. Преобразуй следующие фразы в краткие открытые вопросы, которые можно задать на встрече. Вопросы обращены к клиенту, общайся на вы. Ниже представлены гипотезы и возможные действия. Составь краткие вопросы по следующему правилу: одна фраза из блока гипотезы или возможные действия – один вопрос. Вопросы выведи списком с нумерацией.

Контекст:
\"\"\"
{dialog_text}
\"\"\"

Гипотезы:
{hyp_text}

Возможные действия:
{action_text}
"""

def process_card(card, dialog_text: str, idx: int, total: int) -> tuple[dict | None, dict | None]:
    logger.info(f"[{idx}/{total}] ▶️ Проверяю карточку: {card['title']}")

    def retry_llm(prompt):
        for attempt in range(3):
            try:
                return llm.invoke(prompt).content.strip()
            except Exception as e:
                logger.warning(f"Попытка {attempt+1}/3 не удалась для карточки '{card['title']}': {e}")
                time.sleep(5)
        raise RuntimeError("Максимальное число попыток превышено")

    try:
        relevance_prompt = build_relevance_prompt(card["title"], dialog_text)
        relevance_response_full = retry_llm(relevance_prompt)
        first_word = relevance_response_full.strip().split()[0].lower()
    except Exception as e:
        logger.exception(f"❌ Ошибка релевантности GigaChat: {e}")
        return None, None

    if first_word != "да":
        logger.info(f"[{idx}/{total}] ❌ Не релевантна: {relevance_response_full}")
        return None, {
            "title": card["title"],
            "reason": relevance_response_full
        }

    logger.info(f"[{idx}/{total}] ✅ Релевантна: {relevance_response_full}")

    try:
        prompt = build_prompt_for_questions(card, dialog_text)
        response = retry_llm(prompt)
    except Exception as e:
        logger.exception("Ошибка при генерации вопросов: %s", e)
        return None, {
            "title": card["title"],
            "reason": relevance_response_full
        }

    questions_raw = response.split("\n")
    questions_cleaned = [
        q.strip("•-*–—.0123456789 ").replace("###", "").strip()
        for q in questions_raw
        if q.strip().endswith("?")
    ]

    if not questions_cleaned:
        logger.warning(f"[{idx}/{total}] ⚠️ Нет вопросов")
        return None, {
            "title": card["title"],
            "reason": relevance_response_full
        }

    matched = {
        "title": card["title"],
        "hypotheses": card["hypotheses"],
        "actions": card["actions"],
        "questions": questions_cleaned
    }
    explanation = {
        "title": card["title"],
        "reason": relevance_response_full
    }

    return matched, explanation

def select_relevant_hypotheses(dialog_text: str, all_cards: list[dict], user_id: int = 0) -> list[dict]:
    matched_cards = []
    explanations = []

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {
            executor.submit(process_card, card, dialog_text, idx, len(all_cards)): card
            for idx, card in enumerate(all_cards, start=1)
        }

        for future in as_completed(futures):
            matched, explanation = future.result()
            if matched:
                matched_cards.append(matched)
            if explanation:
                explanations.append(explanation)

    # Исключаем пары
    pairs = [
        ("Рынок падает, выручка компании растет", "Рынок растет, выручка компании падает"),
        ("Выручка растет или стабильна, а прибыль снижается", "Рост прибыли без роста выручки")
    ]
    final_cards = []
    titles_seen = set()
    for card in matched_cards:
        skip = False
        for a, b in pairs:
            if card["title"] == b and a in titles_seen:
                skip = True
                break
        if not skip:
            final_cards.append(card)
            titles_seen.add(card["title"])

    # Сохраняем результаты
    select_relevant_hypotheses.last_results[user_id] = final_cards

    explanations_path = os.path.join(os.path.dirname(__file__), f"explanations_{user_id}.json")
    with open(explanations_path, "w", encoding="utf-8") as f:
        json.dump(explanations, f, ensure_ascii=False, indent=2)

    return final_cards

# ВАЖНО: только теперь назначаем атрибут
select_relevant_hypotheses.last_results = {}


