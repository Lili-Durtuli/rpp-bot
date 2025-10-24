# RPP Screening Bot (EAT-26 + SCOFF)

Телеграм-бот для анонимного скрининга нарушений пищевого поведения по шкалам **EAT-26** и **SCOFF**.

## Локальный запуск

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# PowerShell: . .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# задайте токен (получите у @BotFather)
export BOT_TOKEN=123456:ABC...   # PowerShell: $env:BOT_TOKEN="123:ABC..."

python bot.py
# rpp-bot
