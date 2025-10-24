# bot.py
# Python 3.10+
# pip install python-telegram-bot==21.4
# export BOT_TOKEN = 8433955587:AAEWYkdVGjcY59JV6qly2cpPPxgVt5eMwUU
import os
from dataclasses import dataclass
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ========== Константы и тексты ==========
DISCLAIMER = (
    "⚠️ Это скрининговый опрос (EAT-26 и SCOFF), а не медицинский диагноз. "
    "Если вас беспокоят питание, вес, образ тела или настроение, обратитесь к врачу/специалисту по РПП."
)

SUPPORT_HINT = (
    "Если вам трудно прямо сейчас, обратитесь к близким, к локальным горячим линиям психологической помощи "
    "или запишитесь к специалисту."
)

# ========== Модель данных ==========
@dataclass
class EatOption:
    text: str
    code: str  # один из: "ALWAYS","USUALLY","OFTEN","SOMETIMES","RARELY","NEVER"

@dataclass
class EatQuestion:
    text: str
    reverse: bool = False  # только для п.26

@dataclass
class ScoffQuestion:
    text: str

# Шкала EAT-26 (русская): Всегда, Как правило, Довольно часто, Иногда, Редко, Никогда
# Прямой счёт (пункты 1–25): 3,2,1,0,0,0
# Обратный счёт (только пункт 26): 0,0,0,1,2,3
EAT_OPTIONS: List[EatOption] = [
    EatOption("Всегда", "ALWAYS"),
    EatOption("Как правило", "USUALLY"),
    EatOption("Довольно часто", "OFTEN"),
    EatOption("Иногда", "SOMETIMES"),
    EatOption("Редко", "RARELY"),
    EatOption("Никогда", "NEVER"),
]

DIRECT_SCORES = {"ALWAYS": 3, "USUALLY": 2, "OFTEN": 1, "SOMETIMES": 0, "RARELY": 0, "NEVER": 0}
REVERSE_SCORES = {"ALWAYS": 0, "USUALLY": 0, "OFTEN": 0, "SOMETIMES": 1, "RARELY": 2, "NEVER": 3}

# Вопросы EAT-26 из вашего файла, п.26 — обратный счёт
EAT_QUESTIONS: List[EatQuestion] = [
    EatQuestion("Меня пугает мысль о том, что я располнею"),
    EatQuestion("Я воздерживаюсь от еды, будучи голодным(ой)"),
    EatQuestion("Я нахожу, что я поглощён(на) мыслями о еде"),
    EatQuestion("У меня бывают приступы бесконтрольного поглощения пищи, во время которых я не могу себя остановить"),
    EatQuestion("Я делю свою еду на мелкие кусочки"),
    EatQuestion("Я знаю, сколько калорий в пище, которую я ем"),
    EatQuestion("Я в особенности воздерживаюсь от еды, содержащей много углеводов (хлеб, рис, картофель)"),
    EatQuestion("Я чувствую, что окружающие предпочли бы, чтобы я больше ел(а)"),
    EatQuestion("Меня рвёт после еды"),
    EatQuestion("Я испытываю обострённое чувство вины после еды"),
    EatQuestion("Я озабочен(а) желанием похудеть"),
    EatQuestion("Когда я занимаюсь спортом, то думаю, что я сжигаю калории"),
    EatQuestion("Окружающие считают меня слишком худым(ой)"),
    EatQuestion("Я озабочен(а) мыслями об имеющимся в моём теле жире"),
    EatQuestion("На то, чтобы съесть еду, у меня уходит больше времени, чем у других людей"),
    EatQuestion("Я воздерживаюсь от еды, содержащей сахар"),
    EatQuestion("Я ем диетические продукты"),
    EatQuestion("Я чувствую, что вопросы, связанные с едой, контролируют мою жизнь"),
    EatQuestion("У меня есть самоконтроль в вопросах, связанных с едой"),
    EatQuestion("Я чувствую, что окружающие оказывают на меня давление, чтобы я ел(а)"),
    EatQuestion("Я трачу слишком много времени на вопросы, связанные с едой"),
    EatQuestion("Я чувствую дискомфорт после того, как поем сладости"),
    EatQuestion("Я соблюдаю диету"),
    EatQuestion("Мне нравится ощущение пустого желудка"),
    EatQuestion("После еды у меня бывает импульсивное желание её вырвать"),
    EatQuestion("Я получаю удовольствие, когда пробую новые и вкусные блюда", reverse=True),
]

SCOFF_QUESTIONS: List[ScoffQuestion] = [
    ScoffQuestion("За последние полгода случалось ли у вас безудержное объедание с чувством, что остановиться не можете?"),
    ScoffQuestion("Провоцировали ли вы за последние полгода рвоту для контроля веса/фигуры?"),
    ScoffQuestion("Использовали ли вы за последние полгода мочегонные, слабительные или «специальные» диетические препараты для контроля веса/фигуры?"),
    ScoffQuestion("Занимались ли вы в течение последних 6 месяцев физнагрузкой >60 минут за день ради контроля веса/фигуры?"),
    ScoffQuestion("За последние полгода вы сбросили 9 кг или больше?"),
]

# ========== Ключи состояния ==========
PHASE_KEY = "phase"  # "intro"|"eat"|"scoff"|"done"
EAT_IDX_KEY = "eat_idx"
SCOFF_IDX_KEY = "scoff_idx"
EAT_SCORE_KEY = "eat_score"
EAT_ANS_KEY = "eat_answers"     # список кодов ("ALWAYS",...)
SCOFF_ANS_KEY = "scoff_answers" # список bool

# ========== Вспомогательные функции ==========
def eat_score_for(code: str, reverse: bool) -> int:
    return (REVERSE_SCORES if reverse else DIRECT_SCORES)[code]

def eat_keyboard(q_index: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(opt.text, callback_data=f"eat:{q_index}:{opt.code}")] for opt in EAT_OPTIONS]
    return InlineKeyboardMarkup(rows)

def scoff_keyboard(q_index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Да", callback_data=f"scoff:{q_index}:yes")],
        [InlineKeyboardButton("Нет", callback_data=f"scoff:{q_index}:no")]
    ])

async def send_eat_question(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int):
    q = EAT_QUESTIONS[idx]
    text = f"EAT-26 — вопрос {idx+1}/{len(EAT_QUESTIONS)}\n\n{q.text}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=eat_keyboard(idx))
    else:
        await update.effective_chat.send_message(text=text, reply_markup=eat_keyboard(idx))

async def send_scoff_question(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int):
    q = SCOFF_QUESTIONS[idx]
    text = f"SCOFF — вопрос {idx+1}/{len(SCOFF_QUESTIONS)}\n\n{q.text}\n\nОтветьте «Да» или «Нет»."
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=scoff_keyboard(idx))
    else:
        await update.effective_chat.send_message(text=text, reply_markup=scoff_keyboard(idx))

def interpretation_text(eat_total: int, scoff_yes: int) -> str:
    lines = []
    # EAT-26
    if eat_total >= 20:
        lines.append("📊 **EAT-26:** ≥ 20 — повышенная вероятность нарушений пищевого поведения.")
    else:
        lines.append("📊 **EAT-26:** < 20 — выраженных признаков по шкале EAT-26 не выявлено.")
    # SCOFF
    if scoff_yes >= 4:
        lines.append("🧩 **SCOFF:** 4–5 «да» — высокая вероятность проблем с отношением к приёму пищи.")
    elif scoff_yes >= 2:
        lines.append("🧩 **SCOFF:** ≥ 2 «да» — есть основания для внимания и консультации.")
    else:
        lines.append("🧩 **SCOFF:** 0–1 «да» — по опроснику выраженных признаков не выявлено.")
    # Итог
    if (eat_total >= 20) or (scoff_yes >= 2):
        lines.append("\nРекомендация: обсудите результат со специалистом по РПП/врачом.")
    return "\n".join(lines)

def answers_preview(eat_ans: List[str], scoff_ans: List[bool]) -> str:
    # EAT
    eat_lines = []
    for i, code in enumerate(eat_ans):
        opt_text = next((o.text for o in EAT_OPTIONS if o.code == code), code)
        eat_lines.append(f"{i+1}. {opt_text}")
    # SCOFF
    scoff_lines = []
    for i, val in enumerate(scoff_ans):
        scoff_lines.append(f"{i+1}. {'Да' if val else 'Нет'}")
    return (
        "*Ваши ответы (EAT-26):*\n" + "\n".join(eat_lines) +
        "\n\n*Ваши ответы (SCOFF):*\n" + "\n".join(scoff_lines)
    )

# ========== Хендлеры ==========
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[PHASE_KEY] = "intro"
    context.user_data[EAT_IDX_KEY] = 0
    context.user_data[SCOFF_IDX_KEY] = 0
    context.user_data[EAT_SCORE_KEY] = 0
    context.user_data[EAT_ANS_KEY] = []
    context.user_data[SCOFF_ANS_KEY] = []

    intro = (
        "Привет! Я проведу анонимный скрининг на возможные нарушения пищевого поведения по шкалам EAT-26 и SCOFF.\n\n"
        f"{DISCLAIMER}\n\n"
        "Нажмите «Начать», чтобы приступить."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Начать", callback_data="begin")]])
    await update.effective_chat.send_message(intro, reply_markup=kb)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(
        "Команды:\n"
        "/start — начать заново\n"
        "/help — помощь\n"
        "/restart — перезапустить опрос"
    )

async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # Начало
    if data == "begin":
        context.user_data[PHASE_KEY] = "eat"
        await send_eat_question(update, context, 0)
        return

    # Ответы EAT
    if data.startswith("eat:"):
        _, idx_str, code = data.split(":")
        idx = int(idx_str)
        question = EAT_QUESTIONS[idx]
        # Записать ответ
        eat_ans: List[str] = context.user_data[EAT_ANS_KEY]
        # Вставляем по порядку (на случай редактирования назад это можно усложнить)
        if len(eat_ans) == idx:
            eat_ans.append(code)
        else:
            if idx < len(eat_ans):
                eat_ans[idx] = code
            else:
                # заполним пропуски, если что
                while len(eat_ans) < idx:
                    eat_ans.append("SOMETIMES")
                eat_ans.append(code)

        # Подсчитать балл
        delta = eat_score_for(code, question.reverse)
        context.user_data[EAT_SCORE_KEY] = int(context.user_data[EAT_SCORE_KEY]) + delta

        next_idx = idx + 1
        if next_idx < len(EAT_QUESTIONS):
            await send_eat_question(update, context, next_idx)
        else:
            # Переходим к SCOFF
            context.user_data[PHASE_KEY] = "scoff"
            await send_scoff_question(update, context, 0)
        return

    # Ответы SCOFF
    if data.startswith("scoff:"):
        _, idx_str, yn = data.split(":")
        idx = int(idx_str)
        val = (yn == "yes")
        scoff_ans: List[bool] = context.user_data[SCOFF_ANS_KEY]
        if len(scoff_ans) == idx:
            scoff_ans.append(val)
        else:
            if idx < len(scoff_ans):
                scoff_ans[idx] = val
            else:
                while len(scoff_ans) < idx:
                    scoff_ans.append(False)
                scoff_ans.append(val)

        next_idx = idx + 1
        if next_idx < len(SCOFF_QUESTIONS):
            await send_scoff_question(update, context, next_idx)
        else:
            # Итоги
            total = int(context.user_data[EAT_SCORE_KEY])
            yes_count = sum(1 for v in scoff_ans if v)

            summary = (
                "✅ Скрининг завершён.\n\n"
                f"Суммарный балл **EAT-26:** *{total}*\n"
                f"Количество «да» по **SCOFF:** *{yes_count}*\n\n"
                f"{interpretation_text(total, yes_count)}\n\n"
                f"{DISCLAIMER}\n\n"
                f"{SUPPORT_HINT}\n\n"
                f"{answers_preview(context.user_data[EAT_ANS_KEY], scoff_ans)}"
            )
            await q.edit_message_text(summary, parse_mode="Markdown")

            # Сброс
            context.user_data.clear()
        return

# ========== Точка входа ==========
def main():
    token = os.getenv("8433955587:AAGx8f69pGidInkxvNk_I3FOb8Wu2UTqRkM"
    if not token:
        raise RuntimeError("Задайте BOT_TOKEN в переменных окружения, например:\nexport BOT_TOKEN=123456:ABC...")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CallbackQueryHandler(on_callback))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
