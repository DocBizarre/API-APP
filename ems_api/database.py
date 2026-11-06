"""
Session SQLAlchemy. SQLite par défaut, abstrait pour migrer vers
PostgreSQL/MySQL ultérieurement sans toucher au code métier.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from .config import settings

settings.init_dirs()

# check_same_thread=False : nécessaire pour SQLite + FastAPI
engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """WAL : les lectures (recherche, planning) ne sont plus bloquées par une
    écriture concurrente (mode par défaut = journal rollback, plus restrictif
    pour un serveur multi-utilisateurs)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

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
    from .models import bon_commande  # noqa
    from .models import reception_achat  # noqa
    from .models import intention_achat  # noqa
    from .models import fournisseur  # noqa
    from .models import commercial  # noqa
    from .models import devis  # noqa
    from .models import navire  # noqa
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
        ("affaires", "reference_fournisseur",   "TEXT DEFAULT ''"),
        ("affaires", "etablissement_financier",   "TEXT DEFAULT ''"),
        ("affaires", "echeances_facturation",     "TEXT DEFAULT '[]'"),
        ("affaires", "lots_vendus",               "TEXT DEFAULT '[]'"),
        ("affaires", "num_commande_client",       "TEXT DEFAULT ''"),
        ("affaires", "whiteboard",               "TEXT DEFAULT ''"),
        ("affaires", "transporteur",             "TEXT DEFAULT ''"),
        ("affaires", "contact_transport",        "TEXT DEFAULT ''"),
        ("affaires", "prix_transport",           "TEXT DEFAULT ''"),
        ("affaires", "num_suivi_transport",      "TEXT DEFAULT ''"),
        ("affaires", "instructions_transport",   "TEXT DEFAULT ''"),
        ("affaires", "livraison_nom",            "TEXT DEFAULT ''"),
        ("affaires", "livraison_rue",            "TEXT DEFAULT ''"),
        ("affaires", "livraison_code_postal",    "TEXT DEFAULT ''"),
        ("affaires", "livraison_ville",          "TEXT DEFAULT ''"),
        ("affaires", "livraison_pays",           "TEXT DEFAULT 'France'"),
        ("affaires", "conditions_reglement",     "TEXT DEFAULT ''"),
        ("affaires", "garanties",                "TEXT DEFAULT ''"),
        ("affaires", "resp_technique",           "TEXT DEFAULT ''"),
        ("affaires", "commercial",               "TEXT DEFAULT ''"),
        ("affaires", "commercial_email",         "TEXT DEFAULT ''"),
        ("affaires", "commercial_tel",           "TEXT DEFAULT ''"),
        ("affaires", "interlocuteurs_client",    "TEXT DEFAULT '[]'"),
        ("affaires", "date_fat",                 "TEXT DEFAULT ''"),
        ("affaires", "date_fin_fat",             "TEXT DEFAULT ''"),
        ("affaire_items", "dossier_path",       "TEXT DEFAULT ''"),
        ("contacts", "usage_count",             "INTEGER DEFAULT 1"),
        ("contacts", "entreprise",              "TEXT DEFAULT ''"),
        ("garanties", "responsable",             "TEXT DEFAULT ''"),
        ("garanties", "client_notifie",          "INTEGER DEFAULT 0"),
        ("garanties", "tech_notifie",            "INTEGER DEFAULT 0"),
        ("garanties", "nom_demandeur",           "TEXT DEFAULT ''"),
        ("garanties", "email_demandeur",         "TEXT DEFAULT ''"),
        ("garanties", "telephone_demandeur",     "TEXT DEFAULT ''"),
        ("types_moteur", "marque",               "TEXT DEFAULT ''"),
        ("pieces", "prix_achat",                 "REAL DEFAULT 0"),
        ("pieces", "prix_vente",                 "REAL DEFAULT 0"),
        ("bons_commande", "date_livraison_reelle", "TEXT DEFAULT ''"),
        ("bons_commande", "date_reglement",        "TEXT DEFAULT ''"),
        ("bons_commande", "paiements",             "TEXT DEFAULT '[]'"),
        ("bons_commande", "fournisseur_rue",         "TEXT DEFAULT ''"),
        ("bons_commande", "fournisseur_code_postal", "TEXT DEFAULT ''"),
        ("bons_commande", "fournisseur_ville",       "TEXT DEFAULT ''"),
        ("bons_commande", "fournisseur_pays",        "TEXT DEFAULT 'France'"),
        ("bons_commande", "reference_fournisseur",   "TEXT DEFAULT ''"),
        ("bons_commande", "charge_commande_nom",     "TEXT DEFAULT ''"),
        ("bons_commande", "charge_commande_email",   "TEXT DEFAULT ''"),
        ("bons_commande", "charge_commande_tel",     "TEXT DEFAULT ''"),
        ("bons_commande", "livraison_nom",           "TEXT DEFAULT ''"),
        ("bons_commande", "livraison_rue",           "TEXT DEFAULT ''"),
        ("bons_commande", "livraison_code_postal",   "TEXT DEFAULT ''"),
        ("bons_commande", "livraison_ville",         "TEXT DEFAULT ''"),
        ("bons_commande", "livraison_pays",          "TEXT DEFAULT 'France'"),
        ("bons_commande", "frais_port",               "REAL DEFAULT 0"),
        ("bons_commande", "chapitre_cout",            "TEXT DEFAULT ''"),
        ("bons_commande", "interlocuteurs_fournisseur", "TEXT DEFAULT '[]'"),
        ("bons_commande", "reference_monstock",       "TEXT DEFAULT ''"),
        ("bons_commande", "lien_monstock",             "TEXT DEFAULT ''"),
        ("bons_commande", "envoye_le",                 "TEXT DEFAULT ''"),
        ("bons_commande", "envoye_a",                  "TEXT DEFAULT ''"),
        ("receptions_achat", "statut_avant",           "TEXT DEFAULT ''"),
        ("intentions_achat", "envoye_le",              "TEXT DEFAULT ''"),
        ("intentions_achat", "envoye_a",               "TEXT DEFAULT ''"),
        ("affaire_couts", "stade",                    "TEXT DEFAULT 'P1'"),
        ("affaire_couts", "bon_commande_id",          "TEXT"),
        ("affaire_couts", "poste_lie_id",             "TEXT"),
        ("devis", "navire_nom",             "TEXT DEFAULT ''"),
        ("devis", "navire_immatriculation", "TEXT DEFAULT ''"),
        ("devis", "navire_pavillon",        "TEXT DEFAULT ''"),
        ("devis", "navire_port_attache",    "TEXT DEFAULT ''"),
        ("devis", "navire_type_usage",      "TEXT DEFAULT ''"),
        ("devis", "lieu_intervention",      "TEXT DEFAULT ''"),
        ("devis", "acompte_pct",            "REAL DEFAULT 30"),
        ("devis", "delai_paiement_jours",   "INTEGER DEFAULT 30"),
        ("devis", "moteurs_supplementaires_json", "TEXT DEFAULT '[]'"),
        ("devis", "destinataire_nom",       "TEXT DEFAULT ''"),
        ("devis", "destinataire_email",     "TEXT DEFAULT ''"),
        ("devis", "destinataire_telephone", "TEXT DEFAULT ''"),
        ("devis", "demande_client",         "TEXT DEFAULT ''"),
        ("affaires", "navire_immatriculation", "TEXT DEFAULT ''"),
        ("affaires", "navire_port_attache",    "TEXT DEFAULT ''"),
        ("moteurs", "navire_immatriculation", "TEXT DEFAULT ''"),
        ("moteurs", "navire_port_attache",    "TEXT DEFAULT ''"),
        ("moteurs", "puissance_rpm",          "TEXT DEFAULT ''"),
        ("moteurs", "puissance_pme_rpm",       "TEXT DEFAULT ''"),
        ("affaires", "complexite",            "TEXT DEFAULT ''"),
        ("affaires", "date_visite_appli_debut",  "TEXT DEFAULT ''"),
        ("affaires", "date_visite_appli_fin",    "TEXT DEFAULT ''"),
        ("affaires", "date_commissioning_debut", "TEXT DEFAULT ''"),
        ("affaires", "date_commissioning_fin",   "TEXT DEFAULT ''"),
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

    # Reprise ponctuelle de l'ancien champ fournisseur_adresse (une seule ligne)
    # vers le nouveau champ structuré fournisseur_rue, avant abandon de la colonne.
    # (Pas de vérification via insp.get_columns ici : son cache interne ne voit pas
    # les colonnes tout juste ajoutées par la boucle ALTER TABLE ci-dessus ; on tente
    # directement l'UPDATE, qui échoue silencieusement si une des colonnes manque.)
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "UPDATE bons_commande SET fournisseur_rue = fournisseur_adresse "
                "WHERE (fournisseur_rue IS NULL OR fournisseur_rue = '') "
                "AND fournisseur_adresse IS NOT NULL AND fournisseur_adresse != ''"
            ))
            conn.commit()
    except Exception:
        pass

    # Migration ponctuelle : l'ancien contact fournisseur (3 champs plats
    # fournisseur_contact/email/tel, un seul contact possible) est remplacé par
    # une liste JSON interlocuteurs_fournisseur (même format que les
    # interlocuteurs client). On reprend chaque BC déjà rempli avec l'ancien
    # champ pour ne pas perdre les contacts déjà saisis. Idempotent : un BC
    # dont interlocuteurs_fournisseur n'est plus vide est ignoré.
    try:
        import json as _json2
        from .models.bon_commande import BonCommande as _BCMig
        from sqlalchemy.orm import Session as _SessionMig
        with _SessionMig(engine) as _s5:
            _bcs_a_migrer = _s5.query(_BCMig).filter(
                _BCMig.fournisseur_contact.isnot(None), _BCMig.fournisseur_contact != ""
            ).all()
            for _bc in _bcs_a_migrer:
                try:
                    _existants = _json2.loads(_bc.interlocuteurs_fournisseur or "[]")
                except Exception:
                    _existants = []
                if _existants:
                    continue
                _s5_entry = {
                    "nom": _bc.fournisseur_contact or "",
                    "email": _bc.fournisseur_email or "",
                    "telephone": _bc.fournisseur_tel or "",
                    "role": "",
                }
                _bc.interlocuteurs_fournisseur = _json2.dumps([_s5_entry])
            _s5.commit()
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

    # Migration ponctuelle : ancien échéancier global (prix_ht + echeances_facturation)
    # -> nouveau système "lots vendus". Chaque affaire ayant un prix_ht mais pas encore
    # de lot est convertie en un lot unique "Prestation globale" qui reprend son prix
    # et son échéancier existant. Idempotent : une affaire déjà migrée (lots_vendus
    # non vide) est ignorée, donc cette boucle ne s'exécute utilement qu'une fois.
    try:
        import json as _json
        from uuid import uuid4 as _uuid4
        from .models.affaire import Affaire as _Affaire
        from sqlalchemy.orm import Session as _Session2
        with _Session2(engine) as _s2:
            _affaires = _s2.query(_Affaire).filter(
                _Affaire.prix_ht.isnot(None), _Affaire.prix_ht != ""
            ).all()
            for _a in _affaires:
                try:
                    _lots = _json.loads(_a.lots_vendus or "[]")
                except Exception:
                    _lots = []
                if _lots:
                    continue
                try:
                    _echs = _json.loads(_a.echeances_facturation or "[]")
                except Exception:
                    _echs = []
                _lot = {
                    "id": "lot_" + _uuid4().hex[:10],
                    "libelle": "Prestation globale",
                    "prix_ht": _a.prix_ht,
                    "echeances": _echs,
                }
                _a.lots_vendus = _json.dumps([_lot])
                _a.echeances_facturation = "[]"
            _s2.commit()
    except Exception:
        pass

    # Backfill ponctuel de la table navires à partir de Moteur.navire et
    # Affaire.navire_machine déjà en base (créés avant l'existence de la table
    # navires, donc jamais passés par _upsert_navire). Ne s'exécute que si la
    # table est encore vide : au premier navire enregistré (par cette boucle ou
    # par un upsert normal), on considère le registre initialisé.
    try:
        from .models.navire import Navire as _Navire
        from .models.moteur import Moteur as _MoteurBF
        from .models.affaire import Affaire as _AffaireBF
        from uuid import uuid4 as _uuid4bf
        from sqlalchemy.orm import Session as _SessionBF
        with _SessionBF(engine) as _s3:
            if _s3.query(_Navire).count() == 0:
                _registry = {}
                for _m in _s3.query(_MoteurBF).filter(
                        _MoteurBF.navire.isnot(None), _MoteurBF.navire != "").all():
                    _nom = (_m.navire or "").strip()
                    if not _nom:
                        continue
                    _entry = _registry.setdefault(_nom.lower(), {
                        "nom": _nom, "immatriculation": "", "port_attache": "",
                        "proprietaire_id": None, "usage_count": 0,
                    })
                    _entry["usage_count"] += 1
                    if _m.navire_immatriculation and not _entry["immatriculation"]:
                        _entry["immatriculation"] = _m.navire_immatriculation
                    if _m.navire_port_attache and not _entry["port_attache"]:
                        _entry["port_attache"] = _m.navire_port_attache
                    if _m.client_id and not _entry["proprietaire_id"]:
                        _entry["proprietaire_id"] = _m.client_id
                for _a in _s3.query(_AffaireBF).filter(
                        _AffaireBF.navire_machine.isnot(None), _AffaireBF.navire_machine != "").all():
                    _nom = (_a.navire_machine or "").strip()
                    if not _nom:
                        continue
                    _entry = _registry.setdefault(_nom.lower(), {
                        "nom": _nom, "immatriculation": "", "port_attache": "",
                        "proprietaire_id": None, "usage_count": 0,
                    })
                    _entry["usage_count"] += 1
                    if _a.navire_immatriculation and not _entry["immatriculation"]:
                        _entry["immatriculation"] = _a.navire_immatriculation
                    if _a.navire_port_attache and not _entry["port_attache"]:
                        _entry["port_attache"] = _a.navire_port_attache
                    if _a.client_id and not _entry["proprietaire_id"]:
                        _entry["proprietaire_id"] = _a.client_id
                for _entry in _registry.values():
                    _s3.add(_Navire(id=str(_uuid4bf()), **_entry))
                _s3.commit()
    except Exception:
        pass

    # Backfill ponctuel : avant ce correctif, un bon de commande lié à une
    # affaire mais sans chapitre de coût choisi ("non affecté") ne générait
    # aucun poste de bilan et disparaissait silencieusement du suivi. On crée
    # ici le poste manquant (catégorie vide = "non classé"/à affecter) pour
    # chaque BC déjà lié à une affaire qui n'a pas encore de poste associé.
    try:
        from .models.bon_commande import BonCommande as _BC
        from .models.affaire import AffaireCoutLigne as _ACL
        from uuid import uuid4 as _uuid4cb
        from sqlalchemy.orm import Session as _SessionCB
        with _SessionCB(engine) as _s4:
            _synced_bc_ids = {
                row[0] for row in _s4.query(_ACL.bon_commande_id)
                                      .filter(_ACL.bon_commande_id.isnot(None)).all()
            }
            _bcs = _s4.query(_BC).filter(_BC.affaire_id.isnot(None)).all()
            for _bc in _bcs:
                if _bc.id in _synced_bc_ids:
                    continue
                _montant = sum(l.montant_ligne or 0 for l in _bc.lignes) + (_bc.frais_port or 0)
                _libelle = f"BC {_bc.num_bc}" + (f" — {_bc.fournisseur_nom}" if _bc.fournisseur_nom else "")
                _s4.add(_ACL(
                    id=str(_uuid4cb()),
                    affaire_id=_bc.affaire_id,
                    bon_commande_id=_bc.id,
                    categorie=_bc.chapitre_cout or "",
                    libelle=_libelle,
                    stade="P2",
                    cout_prevu=0,
                    cout_reel=_montant,
                    commentaire=f"Généré automatiquement depuis le bon de commande {_bc.num_bc}.",
                    ordre=9999,
                ))
            _s4.commit()
    except Exception:
        pass

    # Backfill ponctuel : retrouver l'entreprise des contacts existants
    # (créés avant l'ajout du champ entreprise) en les recoupant avec les
    # affaires (interlocuteurs_client) et interventions (signataire/demandeur)
    # auxquelles ils sont déjà rattachés via leur nom. Idempotent : un contact
    # dont l'entreprise est déjà renseignée n'est jamais modifié.
    try:
        import json as _json3
        from .models.contact import Contact as _ContactBF
        from .models.affaire import Affaire as _AffaireEBF
        from .models.intervention import Intervention as _InterventionEBF
        from .models.client import Client as _ClientEBF
        from sqlalchemy.orm import Session as _SessionEBF
        with _SessionEBF(engine) as _s6:
            _contacts_sans_entreprise = {
                c.nom.strip().lower(): c
                for c in _s6.query(_ContactBF).filter(
                    _ContactBF.entreprise.is_(None) | (_ContactBF.entreprise == "")
                ).all()
            }
            if _contacts_sans_entreprise:
                for _inv in (_s6.query(_InterventionEBF)
                             .filter(_InterventionEBF.client_id.isnot(None)).all()):
                    _client = _s6.query(_ClientEBF).filter(_ClientEBF.id == _inv.client_id).first()
                    if not _client or not _client.nom:
                        continue
                    for _nom in (_inv.nom_signataire, _inv.nom_demandeur):
                        _key = (_nom or "").strip().lower()
                        _c = _contacts_sans_entreprise.get(_key)
                        if _c and not _c.entreprise:
                            _c.entreprise = _client.nom
                for _aff in (_s6.query(_AffaireEBF)
                             .filter(_AffaireEBF.client_id.isnot(None)).all()):
                    _client = _s6.query(_ClientEBF).filter(_ClientEBF.id == _aff.client_id).first()
                    if not _client or not _client.nom:
                        continue
                    try:
                        _interlocuteurs = _json3.loads(_aff.interlocuteurs_client or "[]")
                    except Exception:
                        _interlocuteurs = []
                    for _it in _interlocuteurs:
                        _key = (_it.get("nom", "") or "").strip().lower()
                        _c = _contacts_sans_entreprise.get(_key)
                        if _c and not _c.entreprise:
                            _c.entreprise = _client.nom
                _s6.commit()
    except Exception:
        pass

    # Backfill ponctuel : reformater au standard international (+33 6 ...)
    # les numéros de téléphone déjà enregistrés dans la table contacts avant
    # l'ajout de la normalisation. Best-effort : un numéro non reconnu par la
    # librairie phonenumbers est laissé tel quel (jamais de perte de donnée).
    try:
        from .models.contact import Contact as _ContactTelBF
        from .services.phone import format_telephone as _format_tel_bf
        from sqlalchemy.orm import Session as _SessionTelBF
        with _SessionTelBF(engine) as _s7:
            for _c in _s7.query(_ContactTelBF).filter(
                    _ContactTelBF.telephone.isnot(None), _ContactTelBF.telephone != "").all():
                try:
                    _formatted = _format_tel_bf(_c.telephone)
                except ValueError:
                    continue
                if _formatted and _formatted != _c.telephone:
                    _c.telephone = _formatted
            _s7.commit()
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

    # Reprise ponctuelle : liens références produits ↔ fournisseurs déduits des
    # bons de commande / intentions d'achat déjà enregistrés (une seule fois,
    # marqueur dans la table config ; le prix retenu est celui du dernier achat).
    try:
        from .models.configurations import Config as _CfgPF
        from .services.piece_fournisseurs import backfill_depuis_achats
        with _Session(engine) as _s8:
            _cle = "migration:piece_fournisseurs_backfill"
            if not _s8.query(_CfgPF).filter(_CfgPF.cle == _cle).first():
                _n = backfill_depuis_achats(_s8)
                _s8.add(_CfgPF(cle=_cle, valeur=str(_n)))
                _s8.commit()
    except Exception:
        import logging as _logPF
        _logPF.getLogger(__name__).warning("Reprise des liens pièces/fournisseurs impossible",
                                           exc_info=True)
