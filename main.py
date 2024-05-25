#!/usr/bin/env python
import os
from dotenv import load_dotenv
import logging
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

# Configurer l'API OpenAI
openai.api_key = os.getenv('OPEN_AI_KEY')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fonction pour démarrer le bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Bonjour! Parlez-moi de votre problème.")

# Fonction pour traiter les messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    print("user_message : ", user_message)

    

    completion = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Tu es Julie une thérapeute et une coach personnelle. Tu aides les gens à se sentir écouté et soutenu. N'hésite pas à poser des questions pour bien comprendre les problemes des gens. Soit attentive et gentille."},
        {"role": "user", "content": user_message}
    ]
    )


    ai_response = completion.choices[0].message.content
    print(ai_response)

    await update.message.reply_text(ai_response)

# Fonction pour annuler la conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day."
    )

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.getenv('TELEGRAM_KEY')).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()