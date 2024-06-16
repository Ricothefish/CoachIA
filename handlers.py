import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import os

from database import session, User, Message, Subscription
from openai_client import generate_response, transcribe_audio

load_dotenv()

DOMAIN = os.getenv('DOMAIN')

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()
    if not db_user:
        db_user = User(user_id=user.id, username=user.username)
        session.add(db_user)
        session.commit()
    await update.message.reply_text("Bonjour ! Je suis Julie, votre confidente virtuelle et coach de vie. Je suis ici pour vous écouter et vous conseiller.\n \nCependant, je ne remplace pas un professionnel de santé. Si vous avez des problèmes sérieux, contactez un professionnel ou un service spécialisé. En France, vous pouvez appeler le 3114 pour obtenir immédiatement de l'aide d'une vraie personne. \n \n Hâte de discuter avec vous ! 🌟")

def check_user_quota(db_user):
    user_message_count = session.query(Message).filter_by(user_id=db_user.user_id, is_sent_by_user=True).count()

    if user_message_count >= 5:
        payment = session.query(Subscription).filter_by(user_id=db_user.user_id).order_by(Subscription.created_at.desc()).first()
        
        if not payment or not payment.end_date or payment.end_date < datetime.utcnow():
            return False
    return True

def create_message_history(db_user):
    recent_messages = session.query(Message).filter_by(user_id=db_user.user_id).order_by(Message.created_at.desc()).limit(6).all()
    recent_messages = reversed(recent_messages)  # Reverse to maintain the order

    conversation_history = ""
    for msg in recent_messages:
        if msg.is_sent_by_user:
            conversation_history += f"utilisateur: {msg.message}\n"
        else:
            conversation_history += f"toi: {msg.message}\n"
    
    return conversation_history

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()

    # Sauvegarder le message de l'utilisateur
    user_msg = Message(user_id=db_user.user_id, message=user_message, is_sent_by_user=True)
    session.add(user_msg)
    session.commit()

    if not check_user_quota(db_user):
        payment_url = f"https://{DOMAIN}/redirect_to_stripe?user_id={db_user.user_id}"
        text = f"Vous avez atteint la limite de messages gratuits. Veuillez vous abonnez pour continuer à discuter avec moi."

        
        # Création du bouton inline
        keyboard = [[InlineKeyboardButton("👩 Continuer la conversation", url=payment_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        


        bot_msg = Message(user_id=db_user.user_id, message=text, is_sent_by_user=False)
        session.add(bot_msg)
        session.commit()

        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup
        )

        return

    conversation_history = create_message_history(db_user)
    ai_response = generate_response(conversation_history, user_message)

    # Sauvegarder la réponse de l'IA
    bot_msg = Message(user_id=db_user.user_id, message=ai_response, is_sent_by_user=False)
    session.add(bot_msg)
    session.commit()

    await update.message.reply_text(ai_response)

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Télécharger le message vocal
    voice_file = await update.message.voice.get_file()
    voice_file_path = "user_voice.ogg"
    await voice_file.download_to_drive(voice_file_path)

    user_message = transcribe_audio(voice_file_path)
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()

    # Sauvegarder le message de l'utilisateur
    user_msg = Message(user_id=db_user.user_id, message=user_message, is_sent_by_user=True)
    session.add(user_msg)
    session.commit()

    if not check_user_quota(db_user):
        payment_url = f"https://{DOMAIN}/redirect_to_stripe?user_id={db_user.user_id}"
        text = f"Vous avez atteint la limite de messages gratuits. Veuillez vous abonnez pour continuer à discuter avec moi."

        
        # Création du bouton inline
        keyboard = [[InlineKeyboardButton("👩 Continuer la conversation", url=payment_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        


        bot_msg = Message(user_id=db_user.user_id, message=text, is_sent_by_user=False)
        session.add(bot_msg)
        session.commit()

        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup
        )

        return

    conversation_history = create_message_history(db_user)
    ai_response = generate_response(conversation_history, user_message)

    # Sauvegarder la réponse de l'IA
    bot_msg = Message(user_id=db_user.user_id, message=ai_response, is_sent_by_user=False)
    session.add(bot_msg)
    session.commit()

    await update.message.reply_text(ai_response)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text("Bye! I hope we can talk again some day.")



async def manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()

    if db_user:
        # URL fixe pour rediriger l'utilisateur vers le portail client
        manage_url = f"https://{DOMAIN}.com/create-customer-portal-session?user_id={db_user.user_id}"
        # Création du bouton inline
        keyboard = [[InlineKeyboardButton("Gérer votre abonnement", url=manage_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Cliquez sur le bouton ci-dessous pour gérer votre abonnement.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Utilisateur non trouvé. Veuillez réessayer.")

