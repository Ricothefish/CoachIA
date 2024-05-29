import logging
from telegram import Update
from telegram.ext import ContextTypes
from pathlib import Path

from database import session, User, Message, Payment
from openai_client import generate_response, transcribe_audio

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    db_user = session.query(User).filter_by(user_id=user.id).first()
    if not db_user:
        db_user = User(user_id=user.id, username=user.username)
        session.add(db_user)
        session.commit()
    await update.message.reply_text("Bonjour! Parlez-moi de votre problème.")

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

    # Vérifier le nombre de messages envoyés par l'utilisateur
    user_message_count = session.query(Message).filter_by(user_id=db_user.id, is_sent_by_user=True).count()

    if user_message_count >= 5:
        payment = session.query(Payment).filter_by(user_id=db_user.id, is_paid=False).first()
        if not payment:
            payment = Payment(user_id=db_user.id)
            session.add(payment)
            session.commit()
            payment_url = f"https://example.com/pay?user_id={db_user.id}"  # Remplacez par votre lien de paiement réel
            await update.message.reply_text(f"Vous avez atteint la limite de messages gratuits. Veuillez payer pour continuer à utiliser le service en cliquant sur ce lien : {payment_url}")
            return
        else:
            if not payment.is_paid:
                payment_url = f"https://example.com/pay?user_id={db_user.id}"  # Remplacez par votre lien de paiement réel
                await update.message.reply_text(f"Veuillez payer pour continuer à utiliser le service en cliquant sur ce lien : {payment_url}")
                return

    conversation_history = ""
    for msg in recent_messages:
        if msg.is_sent_by_user:
            conversation_history += f"utilisateur: {msg.message}\n"
        else:
            conversation_history += f"toi: {msg.message}\n"

    ai_response = generate_response(conversation_history, user_message)

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

    user_message = transcribe_audio(voice_file_path)
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

    ai_response = generate_response(conversation_history, user_message)
    await update.message.reply_text(ai_response)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text("Bye! I hope we can talk again some day.")