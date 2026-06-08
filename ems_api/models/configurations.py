"""Tables de configuration : types d'intervention, statuts garantie, config clé/valeur."""
from sqlalchemy import Column, String, Integer
from ..database import Base


class TypeIntervention(Base):
    __tablename__ = "types_intervention"
    id = Column(Integer, primary_key=True, autoincrement=True)
    libelle = Column(String, nullable=False, unique=True, index=True)
    ordre = Column(Integer, default=0)


class StatutGarantie(Base):
    __tablename__ = "statuts_garantie"
    id = Column(Integer, primary_key=True, autoincrement=True)
    libelle = Column(String, nullable=False, unique=True, index=True)
    ordre = Column(Integer, default=0)


class MarqueMoteur(Base):
    __tablename__ = "marques_moteur"
    id = Column(Integer, primary_key=True, autoincrement=True)
    libelle = Column(String, nullable=False, unique=True, index=True)
    ordre = Column(Integer, default=0)


class Config(Base):
    __tablename__ = "config"
    cle = Column(String, primary_key=True)
    valeur = Column(String, default="")
