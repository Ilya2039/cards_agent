# === bot.py ===
import asyncio
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    Document,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from utils.extract import extract_text_from_docx
from utils.cards   import load_hypotheses
from utils.giga    import select_relevant_hypotheses
from config        import TOKEN

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp  = Dispatcher()

# user_id → set(indexes)
user_confirmed_cards: dict[int, set[int]] = {}


# ─── /start ────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer(
        "Привет! Пришлите .docx со страт-диалогом – я подберу релевантные гипотезы и вопросы 🙂"
    )


# ─── Приём .docx ───────────────────────────────────────────────────────────
@dp.message(F.document)
async def handle_docx(m: Message):
    doc: Document = m.document
    uid           = m.from_user.id

    if not doc.file_name.lower().endswith(".docx"):
        await m.answer("Нужен именно .docx файл 😉")
        return

    await m.answer("🔍 Обрабатываю файл…")
    tmp = Path(f"/tmp/dialog_{uid}.docx")
    await bot.download(doc, destination=tmp)

    # читаем текст
    try:
        dialog_text = extract_text_from_docx(tmp)
    except Exception as exc:
        await m.answer(f"Не смог прочитать файл: {exc}")
        return

    # подбираем карточки
    all_cards = load_hypotheses()
    selected  = select_relevant_hypotheses(dialog_text, all_cards, user_id=uid)

    if not selected:
        await m.answer("😕 Подходящих гипотез не нашлось")
        return

    user_confirmed_cards[uid] = set()

    for idx, card in enumerate(selected):
        qs_md = "\n".join(f"{i+1}. {q}" for i, q in enumerate(card["questions"]))
        reason = card.get("reason") or ""

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",            # <-- нужный формат
                        callback_data=f"confirm_{idx}",
                    )
                ]
            ]
        )

        text = f"💡 *{card['title']}*\n\n_Почему релевантна:_ {reason}\n\n{qs_md}" if reason else f"💡 *{card['title']}*\n\n{qs_md}"
        await m.answer(text, parse_mode="Markdown", reply_markup=kb)


# ─── «Подтвердить» ─────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("confirm_"))
async def confirm(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split("_")[1])

    if uid not in user_confirmed_cards:
        await cb.answer("Сначала загрузите файл", show_alert=True)
        return

    if idx in user_confirmed_cards[uid]:
        await cb.answer("Эта карточка уже отмечена", show_alert=True)
        return

    try:
        card = select_relevant_hypotheses.last_results[uid][idx]
    except (KeyError, IndexError):
        await cb.answer("Не нашёл карточку – загрузите файл заново", show_alert=True)
        return

    user_confirmed_cards[uid].add(idx)

    qs_md = "\n".join(f"{i+1}. {q}" for i, q in enumerate(card["questions"]))
    reason = card.get("reason") or ""
    text = f"☑️ *Подтверждено:* *{card['title']}*\n\n_Почему релевантна:_ {reason}\n\n{qs_md}" if reason else f"☑️ *Подтверждено:* *{card['title']}*\n\n{qs_md}"
    await cb.message.answer(text, parse_mode="Markdown")
    await cb.answer()   # убираем «часики»


# ─── Запуск ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))