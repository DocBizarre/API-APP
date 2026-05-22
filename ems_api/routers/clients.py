"""Endpoints REST pour la ressource Client."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Client  # importe TOUS les modèles d'un coup
from ..schemas.client import ClientCreate, ClientUpdate, ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=List[ClientOut])
def list_clients(
    search: Optional[str] = Query(None, description="Recherche nom/contact/email"),
    db: Session = Depends(get_db),
):
    """Liste tous les clients (filtrage optionnel par recherche libre)."""
    q = db.query(Client)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Client.nom.ilike(like),
                         Client.contact.ilike(like),
                         Client.email.ilike(like)))
    return q.order_by(Client.nom).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)):
    """Récupère un client par son ID."""
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(404, f"Client {client_id} introuvable")
    return c


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    """Crée un nouveau client (ou met à jour si le nom existe déjà — upsert)."""
    # Upsert sur le nom (comportement de l'app actuelle)
    existing = db.query(Client).filter(Client.nom == data.nom).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    c = Client(id=str(uuid4()), **data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: str, data: ClientUpdate,
                  db: Session = Depends(get_db)):
    """Met à jour un client existant (champs non fournis = inchangés)."""
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(404, f"Client {client_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: str, db: Session = Depends(get_db)):
    """Supprime un client (et ses moteurs en cascade)."""
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(404, f"Client {client_id} introuvable")
    db.delete(c)
    db.commit()
    return None
