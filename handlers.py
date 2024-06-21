import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import uuid
import os

from database import session, User, Message, Subscription, Feedback
from openai_client import generate_response, transcribe_audio, create_speech

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
    await update.message.reply_text("Bonjour ! Je suis Julie, ta confidente virtuelle et coach de vie. Je suis ici pour t’écouter et te conseiller.\n \n Cependant, je ne remplace pas un professionnel de santé. Si tu as des problèmes sérieux, contacte un professionnel ou un service spécialisé. En France, tu peux appeler le 3114 pour obtenir immédiatement de l'aide d'une vraie personne. \n \nTu peux m’envoyer des messages 💬 ou des vocaux 🔊\n \nHâte de discuter avec toi ! 🌟")

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

    if context.user_data.get('collecting_feedback'):
        # Traiter le feedback
        feedback = Feedback(user_id=db_user.user_id, feedback_text=user_message)
        session.add(feedback)
        session.commit()
        
        await update.message.reply_text(
            "Merci beaucoup pour votre précieux avis ! Nous allons le prendre en compte. \n \nVous pouvez maintenant reprendre votre conversation normale."
        )
        context.user_data['collecting_feedback'] = False
        return

    # Sauvegarder le message de l'utilisateur
    user_msg = Message(user_id=db_user.user_id, message=user_message, is_sent_by_user=True)
    session.add(user_msg)
    session.commit()

    if not check_user_quota(db_user):
        payment_url = f"https://{DOMAIN}/redirect_to_stripe?user_id={db_user.user_id}"
        text = f"Tu as atteint la limite de message. \n \nPour continuer à discuter ensemble, un abonnement de 9,99€ / mois (sans engagement) est nécessaire.\n \nJe suis dispo 24/24, toujours là pour t’aider à surmonter tes périodes difficiles et à devenir la meilleure version de toi même ☺️ \n\nClique sur “Continuer à discuter” pour ne plus être seul face à tes problèmes."

        
        # Création du bouton inline
        keyboard = [[InlineKeyboardButton("👩 Continuer à discuter", url=payment_url)]]
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
    voice_file_path = f"user_voice_{uuid.uuid4()}.ogg"
    await voice_file.download_to_drive(voice_file_path)

    user_message = transcribe_audio(voice_file_path)
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()

    if context.user_data.get('collecting_feedback'):
        # Traiter le feedback
        feedback = Feedback(user_id=db_user.user_id, feedback_text=user_message)
        session.add(feedback)
        session.commit()
        
        await update.message.reply_text(
            "Merci beaucoup pour votre précieux avis ! Nous allons le prendre en compte. \n \nVous pouvez maintenant reprendre votre conversation normale."
        )
        context.user_data['collecting_feedback'] = False
        return

    # Sauvegarder le message de l'utilisateur
    user_msg = Message(user_id=db_user.user_id, message=user_message, is_sent_by_user=True)
    session.add(user_msg)
    session.commit()

    if not check_user_quota(db_user):
        payment_url = f"https://{DOMAIN}/redirect_to_stripe?user_id={db_user.user_id}"
        text = "Vous avez atteint la limite de messages gratuits. Veuillez vous abonnez pour continuer à discuter avec moi."

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

    # Générer un fichier audio à partir de la réponse de l'IA avec un nom de fichier unique
     # Générer un fichier audio à partir de la réponse de l'IA en appelant create_speech
    speech_file_path = create_speech(ai_response)

    # Envoyer le fichier audio à l'utilisateur
    with open(speech_file_path, 'rb') as audio_file:
        await update.message.reply_voice(voice=audio_file)

    # Supprimer le fichier audio après l'envoi
    #os.remove(speech_file_path)
    #os.remove(voice_file_path)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text("Bye! I hope we can talk again some day.")


async def manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()

    if db_user:
        # URL fixe pour rediriger l'utilisateur vers le portail client
        manage_url = f"https://{DOMAIN}/create-customer-portal-session?user_id={db_user.user_id}"
        # Création du bouton inline
        keyboard = [[InlineKeyboardButton("Gérer votre abonnement", url=manage_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Cliquez sur le bouton ci-dessous pour gérer votre abonnement.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Utilisateur non trouvé. Veuillez réessayer.")


# Commande pour initier la collecte des avis
async def collect_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()

    if db_user:
        await update.message.reply_text(
            "Nous aimerions beaucoup connaître votre avis ! \n \nVeuillez partager vos commentaires en répondant à ce message."
        )
        context.user_data['collecting_feedback'] = True
    else:
        await update.message.reply_text("Utilisateur non trouvé. Veuillez réessayer.")


