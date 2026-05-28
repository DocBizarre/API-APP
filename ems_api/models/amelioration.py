"""Modèle Amelioration (amélioration continue / tickets)."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class Amelioration(Base):
    __tablename__ = "ameliorations"

    id              = Column(String, primary_key=True, index=True)
    num_ticket      = Column(String, nullable=False, unique=True, index=True)
    titre           = Column(String, nullable=False)
    client_id       = Column(String, ForeignKey("clients.id"), index=True)
    description     = Column(String, default="")
    priorite        = Column(String, default="Moyenne", index=True)   # Basse / Moyenne / Haute
    statut          = Column(String, default="À étudier", index=True)
    technicien      = Column(String, default="")   # CSV multi-tech (cohérent avec Intervention)
    date_cible      = Column(String, default="")   # JJ/MM/AAAA
    commentaires    = Column(String, default="")
    dossier_path    = Column(String, default="")
    version         = Column(Integer, default=1)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(),
                              onupdate=func.now())

    client = relationship("Client", back_populates="ameliorations")
