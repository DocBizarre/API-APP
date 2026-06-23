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
    """Crée toutes les tables si elles n'existent pas + migrations légères."""
    from .models import client, moteur, intervention, garantie  # noqa
    from .models import amelioration, technicien  # noqa
    from .models import configurations  # noqa
    from .models import affaire, contact  # noqa
    Base.metadata.create_all(bind=engine)

    # Migrations : ajout de colonnes manquantes sur tables existantes
    from sqlalchemy import text, inspect as _inspect
    _migrations = [
        ("interventions", "moteurs_supplementaires_json", "TEXT DEFAULT '[]'"),
        ("interventions", "marque",                       "TEXT DEFAULT ''"),
        ("interventions", "commentaire",                  "TEXT DEFAULT ''"),
        ("interventions", "nom_signataire",               "TEXT DEFAULT ''"),
        ("interventions", "email_signataire",             "TEXT DEFAULT ''"),
        ("interventions", "telephone_signataire",         "TEXT DEFAULT ''"),
        ("interventions", "nom_demandeur",                "TEXT DEFAULT ''"),
        ("interventions", "email_demandeur",              "TEXT DEFAULT ''"),
        ("interventions", "telephone_demandeur",          "TEXT DEFAULT ''"),
        ("moteurs", "client_utilisateur_nom",     "TEXT DEFAULT ''"),
        ("moteurs", "client_utilisateur_email",   "TEXT DEFAULT ''"),
        ("moteurs", "client_utilisateur_tel",     "TEXT DEFAULT ''"),
        ("moteurs", "client_utilisateur_adresse", "TEXT DEFAULT ''"),
        ("moteurs", "parent_moteur_id",           "TEXT"),
        ("affaires", "prix_ht",                 "TEXT DEFAULT ''"),
        ("affaires", "exonere_tva",             "INTEGER DEFAULT 0"),
        ("affaires", "date_achat",              "TEXT DEFAULT ''"),
        ("affaires", "fournisseur",             "TEXT DEFAULT ''"),
        ("affaires", "etablissement_financier",   "TEXT DEFAULT ''"),
        ("affaires", "echeances_facturation",     "TEXT DEFAULT '[]'"),
        ("affaires", "num_commande_client",       "TEXT DEFAULT ''"),
        ("affaires", "whiteboard",               "TEXT DEFAULT ''"),
        ("affaires", "transporteur",             "TEXT DEFAULT ''"),
        ("affaires", "contact_transport",        "TEXT DEFAULT ''"),
        ("affaires", "prix_transport",           "TEXT DEFAULT ''"),
        ("affaires", "num_suivi_transport",      "TEXT DEFAULT ''"),
        ("affaires", "instructions_transport",   "TEXT DEFAULT ''"),
        ("affaire_items", "dossier_path",       "TEXT DEFAULT ''"),
        ("contacts", "usage_count",             "INTEGER DEFAULT 1"),
        ("garanties", "responsable",             "TEXT DEFAULT ''"),
        ("garanties", "client_notifie",          "INTEGER DEFAULT 0"),
        ("garanties", "tech_notifie",            "INTEGER DEFAULT 0"),
        ("garanties", "nom_demandeur",           "TEXT DEFAULT ''"),
        ("garanties", "email_demandeur",         "TEXT DEFAULT ''"),
        ("garanties", "telephone_demandeur",     "TEXT DEFAULT ''"),
    ]
    insp = _inspect(engine)
    for table, col, col_def in _migrations:
        try:
            existing = [c["name"] for c in insp.get_columns(table)]
            if col not in existing:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                    conn.commit()
        except Exception:
            pass

    # Ancienne table sous_ensembles (modèle dédié) : les sous-ensembles sont
    # désormais des Moteur rattachés via parent_moteur_id. Nettoyage de la
    # table devenue obsolète si elle existe encore (ancien essai local).
    try:
        if "sous_ensembles" in insp.get_table_names():
            with engine.connect() as conn:
                conn.execute(text("DROP TABLE sous_ensembles"))
                conn.commit()
    except Exception:
        pass

    # Seed marques par défaut si la table est vide
    from .models.configurations import MarqueMoteur
    from sqlalchemy.orm import Session as _Session
    with _Session(engine) as _s:
        if _s.query(MarqueMoteur).count() == 0:
            _defaults = [
                "Volvo Penta", "Caterpillar", "John Deere", "Yanmar",
                "MTU", "MAN", "Cummins", "Perkins", "Deutz", "Scania",
            ]
            for i, lib in enumerate(_defaults):
                _s.add(MarqueMoteur(libelle=lib, ordre=i))
            _s.commit()
