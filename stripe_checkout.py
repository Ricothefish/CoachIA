import os
import asyncio
import json
import nest_asyncio
from datetime import datetime, timezone
import pytz
import requests
import aiohttp
from flask import Flask, request, redirect, jsonify
import stripe
from dotenv import load_dotenv
from telegram import Bot
from database import engine, Subscription, User, Message
from flask_sslify import SSLify
import logging
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Charger les variables d'environnement à partir du fichier .env
load_dotenv()

app = Flask(__name__)

ENV = os.getenv('FLASK_ENV')

if ENV == "prod":
    sslify = SSLify(app)

stripe.api_key = os.getenv('STRIPE_API_KEY')
PRODUCT_ID = os.getenv('PRODUCT_ID')
DOMAIN = os.getenv('DOMAIN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME')
STRIPE_ENDPOINT_SECRET = os.getenv('STRIPE_ENDPOINT_SECRET')
nest_asyncio.apply()

bot = Bot(token=TELEGRAM_BOT_TOKEN)

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

# Fonction asynchrone pour envoyer un message Telegram
def send_telegram_message(chat_id, text):
    bot_token = TELEGRAM_BOT_TOKEN
    telegram_url = f'https://api.telegram.org/bot{bot_token}/sendMessage'

    with session_scope() as session:
        user_msg = Message(user_id=chat_id, message=text, is_sent_by_user=False)
        session.add(user_msg)

    requests.post(telegram_url, data={'chat_id': chat_id, 'text': text})

@app.route('/', methods=['GET'])
def redirect_to_telegram():
    print("redirect")
    app.logger.info("redirect")
    return redirect(f'https://t.me/{TELEGRAM_BOT_USERNAME}?start=start')

def create_checkout_session(user_id):
    try:
        app.logger.info("route pay")

        if not user_id:
            raise ValueError("user_id is required")

        app.logger.info("userId: %s", user_id)

        with session_scope() as session:
            # Vérifier si l'utilisateur existe
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                raise ValueError("User not found")

            # Créer un client Stripe si l'utilisateur n'a pas encore de stripe_customer_id
            if not user.stripe_customer_id:
                app.logger.info("no stripe customer id")
                customer = stripe.Customer.create(metadata={"user_id": user_id})
                user.stripe_customer_id = customer.id
                app.logger.info("new stripe customer id: %s", customer.id)

            # Préparer les paramètres pour la création de la session Stripe
            checkout_session_params = {
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': PRODUCT_ID,
                    'quantity': 1,
                }],
                'mode': 'subscription',
                'success_url': f'https://{DOMAIN}/success?session_id={{CHECKOUT_SESSION_ID}}&user_id={user_id}',
                'cancel_url': f'https://{DOMAIN}/cancel?user_id={user_id}',
                'customer': user.stripe_customer_id
            }

        # Créer la session de paiement
        checkout_session = stripe.checkout.Session.create(**checkout_session_params)

        return jsonify({
            'id': checkout_session.id,
            'url': checkout_session.url
        })

    except Exception as e:
        app.logger.error("An error occurred: %s", str(e))
        response = jsonify({'error': str(e)})
        response.status_code = 500
        return response

@app.route('/redirect_to_stripe', methods=['GET'])
def redirect_to_stripe():
    user_id = request.args.get('user_id')

    with session_scope() as session:
        # Vérifier si l'utilisateur existe
        user = session.query(User).filter_by(user_id=user_id).first()
        app.logger.info("user")
        app.logger.info(user)
        if not user:
            send_telegram_message(chat_id=user_id, text="Unknown user")
            return redirect(f'https://t.me/{TELEGRAM_BOT_USERNAME}')
        
        # Récupérer l'enregistrement de l'abonnement le plus récent pour l'utilisateur
        subscription = session.query(Subscription)\
            .filter_by(user_id=user_id)\
            .order_by(Subscription.created_at.desc())\
            .first()
        app.logger.info("subscription")
        app.logger.info(subscription)

        # Vérifier si l'utilisateur a déjà un abonnement actif (end_date dans le futur)
        if subscription and subscription.end_date and subscription.end_date > datetime.now():
            app.logger.info("user already subscribed")
            # Rediriger vers le bot Telegram et envoyer un message
            send_telegram_message(user_id, "You already have a subscription")
            return redirect(f'https://t.me/{TELEGRAM_BOT_USERNAME}')

    response = create_checkout_session(user_id)
    session_url = response.json.get('url')
    return redirect(session_url)

@app.route('/success', methods=['GET'])
def payment_success():
    user_id = request.args.get('user_id')

    # Envoyer un message de succès à l'utilisateur Telegram
    send_telegram_message(chat_id=user_id, text="Your payment was successful.")

    return redirect(f'https://t.me/{TELEGRAM_BOT_USERNAME}')

@app.route('/cancel', methods=['GET'])
def payment_cancel():
    user_id = request.args.get('user_id')

    # Envoyer un message d'annulation à l'utilisateur Telegram
    send_telegram_message(chat_id=user_id, text="Your payment has been canceled. If you wish to continue using the service, please try again.")
    
    return redirect(f'https://t.me/{TELEGRAM_BOT_USERNAME}')

@app.route('/create-customer-portal-session', methods=['GET'])
def create_customer_portal_session():
    user_id = request.args.get('user_id')
    
    with session_scope() as session:
        # Récupérer l'utilisateur et vérifier s'il a déjà un stripe_customer_id
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user or not user.stripe_customer_id:
            return "User has no active Stripe customer ID", 400

        stripe_customer_id = user.stripe_customer_id

    # Créer une session de portail client
    portal_session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=f'https://t.me/{TELEGRAM_BOT_USERNAME}'
    )

    return redirect(portal_session.url)

@app.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    data_object = data['object']

    print('event ' + event_type)

    if event_type == 'invoice.paid':
        handle_invoice_paid(data_object)
        
    return jsonify({'status': 'success'})

def handle_invoice_paid(data_object):
    # Récupérer l'ID du client Stripe
    stripe_customer_id = data_object['customer']
    
    with session_scope() as session:
        # Récupérer l'utilisateur associé à cet ID de client Stripe
        user = session.query(User).filter_by(stripe_customer_id=stripe_customer_id).first()

        if user:
            # Récupérer la ligne d'abonnement de la facture
            line_item = data_object['lines']['data'][0]
            
            # Récupérer les dates de début et de fin de la période de facturation
            start_date_timestamp = line_item['period']['start']
            end_date_timestamp = line_item['period']['end']

            # Convertir les timestamps en datetime UTC
            start_date = datetime.fromtimestamp(start_date_timestamp, tz=timezone.utc)
            end_date = datetime.fromtimestamp(end_date_timestamp, tz=timezone.utc)

            print(start_date)
            print(end_date)

            # Créer une nouvelle entrée dans la table subscriptions
            new_subscription = Subscription(
                user_id=user.user_id,
                start_date=start_date,
                end_date=end_date
            )

            # Ajouter et valider la nouvelle entrée
            session.add(new_subscription)
            print(f'🔔 Subscription created for user_id: {user.user_id}')

        else:
            print(f'User not found for stripe_customer_id: {stripe_customer_id}')

print("Starting application...")

# Configurer le logger pour envoyer les messages à stdout
if __name__ != "__main__":
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 3000))
    print(f"Running Flask application on port {port}...", flush=True)
    app.run(host='0.0.0.0', port=port)

    
