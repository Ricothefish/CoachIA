#!/usr/bin/env python
import os
from dotenv import load_dotenv
import logging
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

load_dotenv()

# Configurer l'API OpenAI
openai.api_key = os.getenv('OPEN_AI_KEY')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurer la base de données SQLite avec SQLAlchemy
Base = declarative_base()
DATABASE_URL = "sqlite:///telegram_bot.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    created_at = Column(DateTime, default=func.now())

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(String, nullable=False)
    is_sent_by_user = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=func.now())

Base.metadata.create_all(engine)


def text_to_speech(text: str, language: str = 'fr') -> str:
    speech_file_path = Path("response.mp3")
    response = openai.audio.speech.create(
        model="tts-1",
        voice="alloy",  # Vous pouvez changer la voix ici si nécessaire
        input=text
    )
    response.with_streaming_response.method(speech_file_path)
    return str(speech_file_path)




# Fonction pour démarrer le bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()
    if not db_user:
        db_user = User(user_id=user.id, username=user.username)
        session.add(db_user)
        session.commit()
    await update.message.reply_text("Bonjour! Parlez-moi de votre problème.")

# Fonction pour traiter les messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
   


    user_message = update.message.text
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()
    
    # Sauvegarder le message de l'utilisateur
    user_msg = Message(user_id=db_user.id, message=user_message, is_sent_by_user=True)
    session.add(user_msg)
    session.commit()

    # Récupérer les 3 derniers messages de l'utilisateur et de l'IA
    recent_messages = session.query(Message).filter_by(user_id=db_user.id).order_by(Message.created_at.desc()).limit(6).all()
    recent_messages = reversed(recent_messages)  # Reverse to maintain the order

    conversation_history = ""
    for msg in recent_messages:
        if msg.is_sent_by_user:
            conversation_history += f"utilisateur: {msg.message}\n"
        else:
            conversation_history += f"toi: {msg.message}\n"


    print(str(conversation_history))

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": f"Tu es Julie une thérapeute et une coach personnelle. Tu aides les gens à se sentir écouté et soutenu. N'hésite pas à poser des questions pour bien comprendre les problemes des gens. Soit attentive et gentille. Ne fais pas des messages trop long. Voici notre historique de conversation: {conversation_history}"},
            {"role": "user", "content": user_message}
        ]
    )

    ai_response = completion.choices[0].message.content
    
    # Sauvegarder la réponse de l'IA
    bot_msg = Message(user_id=db_user.id, message=ai_response, is_sent_by_user=False)
    session.add(bot_msg)
    session.commit()

    await update.message.reply_text(ai_response)





async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:


 


    # Télécharger le message vocal
    voice_file = await update.message.voice.get_file()
    voice_file_path = "user_voice.ogg"
    await voice_file.download_to_drive(voice_file_path)
    
    # Ouvrir le fichier audio pour la transcription
    audio_file = open(voice_file_path, "rb")
    
    # Utiliser l'API de transcription de OpenAI
    transcription = openai.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text",
        language="fr"
    )
    
    # Obtenir le texte transcrit
    user_message = transcription
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()
    
    # Sauvegarder le message de l'utilisateur
    user_msg = Message(user_id=db_user.id, message=user_message, is_sent_by_user=True)
    session.add(user_msg)
    session.commit()

    # Récupérer les 3 derniers messages de l'utilisateur et de l'IA
    recent_messages = session.query(Message).filter_by(user_id=db_user.id).order_by(Message.created_at.desc()).limit(6).all()
    recent_messages = reversed(recent_messages)  # Reverse to maintain the order

    conversation_history = ""
    for msg in recent_messages:
        if msg.is_sent_by_user:
            conversation_history += f"utilisateur: {msg.message}\n"
        else:
            conversation_history += f"toi: {msg.message}\n"

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": f"Tu es Julie une thérapeute et une coach personnelle. Tu aides les gens à se sentir écouté et soutenu. N'hésite pas à poser des questions pour bien comprendre les problemes des gens. Soit attentive et gentille. Ne fais pas des messages trop long. Voici notre historique de conversation: {conversation_history}"},
            {"role": "user", "content": user_message}
        ]
    )

    ai_response = completion.choices[0].message.content


    await update.message.reply_text(ai_response)


# Fonction pour annuler la conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text("Bye! I hope we can talk again some day.")









def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.getenv('TELEGRAM_KEY')).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE & ~filters.COMMAND, audio_handler))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()