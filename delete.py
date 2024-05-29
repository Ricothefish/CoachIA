from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine, MetaData

DATABASE_URL = "sqlite:///telegram_bot.db"

# Configurer la base de données SQLite avec SQLAlchemy
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Définir la base pour les modèles SQLAlchemy
Base = declarative_base()

def clear_all_tables(session):
    meta = MetaData()
    meta.reflect(bind=engine)
    for table in reversed(meta.sorted_tables):
        print(f"Effacement de la table {table}")
        session.execute(table.delete())
    session.commit()

if __name__ == "__main__":
    clear_all_tables(session)
    print("Toutes les tables ont été effacées.")
