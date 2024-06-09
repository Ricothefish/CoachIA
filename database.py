from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
DATABASE_URL = "sqlite:///telegram_bot.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, unique=True, nullable=False)
    stripe_customer_id = Column(String, nullable=True)
    username = Column(String)
    created_at = Column(DateTime, default=func.now())

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    message = Column(String, nullable=False)
    is_sent_by_user = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=func.now())

class Subscription(Base):
    __tablename__ = 'subscriptions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    start_date = Column(DateTime)
    end_date= Column(DateTime)
    created_at = Column(DateTime, default=func.now())  # Nouvelle colonne ajoutée

Base.metadata.create_all(engine)
