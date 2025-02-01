# MacroCalBot

## Setup

1. Clone the repository
2. Copy `config.example.json` to `config.json`
3. Update `config.json` with your credentials:
   - Telegram Bot Token (from BotFather)
   - Nutritionix API credentials
   - Place your Google Vision API credentials in `vision-api-credentials.json`
   - Place your Firebase credentials in `firebase_credentials.json`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the bot: `python bot.py`

## Configuration

The following credentials are required:

- Telegram Bot Token
- Nutritionix API credentials (app_id and api_key)
- Google Vision API credentials
- Firebase credentials

Never commit your actual credentials to git!
