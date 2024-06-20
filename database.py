import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, func, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()  # Charge les variables d'environnement à partir du fichier .env

Base = declarative_base()

DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')
DATABASE_NAME = os.getenv('DATABASE_NAME')

DATABASE_URL = f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, unique=True, nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)  # Spécifier la longueur maximale
    username = Column(String(255))  # Spécifier la longueur maximale
    created_at = Column(DateTime, default=func.now())

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    message = Column(Text, nullable=False)  # Utiliser le type Text pour des messages longs
    is_sent_by_user = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=func.now())

class Subscription(Base):
    __tablename__ = 'subscriptions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    start_date = Column(DateTime)
    end_date= Column(DateTime)
    created_at = Column(DateTime, default=func.now())  # Nouvelle colonne ajoutée


class Feedback(Base):
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    feedback_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())



Base.metadata.create_all(engine)
