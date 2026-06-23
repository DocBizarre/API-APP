"""Contacts réutilisables : signataires et demandeurs."""
from sqlalchemy import Column, String, Integer
from ..database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id          = Column(String, primary_key=True, index=True)
    nom         = Column(String, nullable=False, unique=True, index=True)
    email       = Column(String, default="")
    telephone   = Column(String, default="")
    usage_count = Column(Integer, default=1)
