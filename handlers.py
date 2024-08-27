import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import uuid
import os
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from database import engine, User, Message, Subscription, Feedback
from openai_client import generate_response, transcribe_audio, create_speech

load_dotenv()

DOMAIN = os.getenv('DOMAIN')

logger = logging.getLogger(__name__)

Session = sessionmaker(bind=engine)

@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        user = update.message.from_user
        db_user = session.query(User).filter_by(user_id=user.id).first()
        if not db_user:
            db_user = User(user_id=user.id, username=user.username)
            session.add(db_user)
    await update.message.reply_text("Hello! I am Julie, your virtual confidant and life coach. I am here to listen and advise you.\n \nHowever, I do not replace a healthcare professional. If you have serious problems, contact a professional or a specialized service.\n \nYou can send me messages 💬 or voice notes 🔊\n \nLooking forward to chatting with you! 🌟")

def check_user_quota(db_user):
    with session_scope() as session:
        user_message_count = session.query(Message).filter_by(user_id=db_user.user_id, is_sent_by_user=True).count()
        if user_message_count >= 5:
            payment = session.query(Subscription).filter_by(user_id=db_user.user_id).order_by(Subscription.created_at.desc()).first()
            if not payment or not payment.end_date or payment.end_date < datetime.utcnow():
                return False
    return True

def create_message_history(db_user):
    with session_scope() as session:
        recent_messages = session.query(Message).filter_by(user_id=db_user.user_id).order_by(Message.created_at.desc()).limit(6).all()
        recent_messages = reversed(recent_messages)
        conversation_history = ""
        for msg in recent_messages:
            if msg.is_sent_by_user:
                conversation_history += f"user: {msg.message}\n"
            else:
                conversation_history += f"you: {msg.message}\n"
    return conversation_history

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        user_message = update.message.text
        user = update.message.from_user
        db_user = session.query(User).filter_by(user_id=user.id).first()

        if context.user_data.get('collecting_feedback'):
            feedback = Feedback(user_id=db_user.user_id, feedback_text=user_message)
            session.add(feedback)
            await update.message.reply_text(
                "Thank you very much for your valuable feedback! We will take it into account. \n \nYou can now resume your normal conversation."
            )
            context.user_data['collecting_feedback'] = False
            return

        user_msg = Message(user_id=db_user.user_id, message=user_message, is_sent_by_user=True)
        session.add(user_msg)

        if not check_user_quota(db_user):
            payment_url = f"https://{DOMAIN}/redirect_to_stripe?user_id={db_user.user_id}"
            text = f"You have reached the message limit 🙁 \n \nTo continue our conversation, a subscription of $9.99/month (no commitment) is required.\n \nI am available 24/7, always here to help you through tough times and to become the best version of yourself \n\nClick on 'Continue chatting' to no longer face your problems alone."
            keyboard = [[InlineKeyboardButton("👩 Continue chatting", url=payment_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            bot_msg = Message(user_id=db_user.user_id, message=text, is_sent_by_user=False)
            session.add(bot_msg)
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup
            )
            return

        conversation_history = create_message_history(db_user)
        ai_response = generate_response(conversation_history, user_message)
        bot_msg = Message(user_id=db_user.user_id, message=ai_response, is_sent_by_user=False)
        session.add(bot_msg)

    await update.message.reply_text(ai_response)

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        voice_file = await update.message.voice.get_file()
        voice_file_path = f"user_voice_{uuid.uuid4()}.ogg"
        await voice_file.download_to_drive(voice_file_path)

        user_message = transcribe_audio(voice_file_path)
        user = update.message.from_user
        db_user = session.query(User).filter_by(user_id=user.id).first()

        if context.user_data.get('collecting_feedback'):
            feedback = Feedback(user_id=db_user.user_id, feedback_text=user_message)
            session.add(feedback)
            await update.message.reply_text(
                "Thank you very much for your valuable feedback! We will take it into account. \n \nYou can now resume your normal conversation."
            )
            context.user_data['collecting_feedback'] = False
            return

        user_msg = Message(user_id=db_user.user_id, message=user_message, is_sent_by_user=True)
        session.add(user_msg)

        if not check_user_quota(db_user):
            payment_url = f"https://{DOMAIN}/redirect_to_stripe?user_id={db_user.user_id}"
            text = "You have reached the message limit 🙁 \n \nTo continue our conversation, a subscription of $9.99/month (no commitment) is required.\n \nI am available 24/7, always here to help you through tough times and to become the best version of yourself \n\nClick on 'Continue chatting' to no longer face your problems alone."
            keyboard = [[InlineKeyboardButton("👩 Continue chatting", url=payment_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            bot_msg = Message(user_id=db_user.user_id, message=text, is_sent_by_user=False)
            session.add(bot_msg)
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup
            )
            return

        conversation_history = create_message_history(db_user)
        ai_response = generate_response(conversation_history, user_message)
        bot_msg = Message(user_id=db_user.user_id, message=ai_response, is_sent_by_user=False)
        session.add(bot_msg)

    speech_file_path = create_speech(ai_response)
    with open(speech_file_path, 'rb') as audio_file:
        await update.message.reply_voice(voice=audio_file)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text("Bye! I hope we can talk again some day.")

async def manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        user = update.message.from_user
        db_user = session.query(User).filter_by(user_id=user.id).first()

        if db_user:
            manage_url = f"https://{DOMAIN}/create-customer-portal-session?user_id={db_user.user_id}"
            keyboard = [[InlineKeyboardButton("Manage subscription", url=manage_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Click here to manage your subscription.",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("User not found, please retry again.")

async def collect_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        user = update.message.from_user
        db_user = session.query(User).filter_by(user_id=user.id).first()

        if db_user:
            await update.message.reply_text(
                "We would love to hear your feedback! \n \nPlease share your comments by replying to this message."
            )
            context.user_data['collecting_feedback'] = True
        else:
            await update.message.reply_text("User not found, please retry again.")


