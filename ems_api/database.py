"""
Session SQLAlchemy. SQLite par défaut, abstrait pour migrer vers
PostgreSQL/MySQL ultérieurement sans toucher au code métier.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from .config import settings

settings.init_dirs()

# check_same_thread=False : nécessaire pour SQLite + FastAPI
engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dépendance FastAPI : fournit une session DB par requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    # Import des modèles ici pour qu'ils s'enregistrent dans Base.metadata
    from .models import client, moteur, intervention, garantie  # noqa
    from .models import amelioration, technicien  # noqa
    from .models import configurations #noqa
    Base.metadata.create_all(bind=engine)
