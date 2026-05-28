"""Endpoints REST pour la ressource Client."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Client
from ..schemas.client import ClientCreate, ClientUpdate, ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


def _to_out(c: Client) -> dict:
    d = {}
    for col in c.__table__.columns:
        val = getattr(c, col.name)
        if val is None and not col.name.endswith("_at"):
            val = ""
        d[col.name] = val
    return d


@router.get("", response_model=List[ClientOut])
def list_clients(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Client)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Client.nom.ilike(like),
                         Client.contact.ilike(like),
                         Client.email.ilike(like)))
    return [_to_out(c) for c in q.order_by(Client.nom).all()]


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)):
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(404, f"Client {client_id} introuvable")
    return _to_out(c)


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    existing = db.query(Client).filter(Client.nom == data.nom).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    c = Client(id=str(uuid4()), **data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: str, data: ClientUpdate,
                  db: Session = Depends(get_db)):
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(404, f"Client {client_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    c.version = (c.version or 0) + 1
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: str, db: Session = Depends(get_db)):
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(404, f"Client {client_id} introuvable")
    db.delete(c)
    db.commit()
    return None
