"""Fournisseurs réutilisables (autocomplétion achats / bons de commande)."""
from sqlalchemy import Column, String, Integer
from ..database import Base


class Fournisseur(Base):
    __tablename__ = "fournisseurs"

    id           = Column(String, primary_key=True, index=True)
    nom          = Column(String, nullable=False, unique=True, index=True)
    contact      = Column(String, default="")
    email        = Column(String, default="")
    telephone    = Column(String, default="")
    rue          = Column(String, default="")
    code_postal  = Column(String, default="")
    ville        = Column(String, default="")
    pays         = Column(String, default="")
    usage_count  = Column(Integer, default=1)
