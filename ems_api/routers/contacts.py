"""Endpoints REST pour les contacts (signataires / demandeurs)."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Contact
from ..schemas.contact import ContactCreate, ContactUpdate, ContactOut

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _to_out(c: Contact) -> dict:
    d = {}
    for col in c.__table__.columns:
        val = getattr(c, col.name)
        if val is None:
            val = ""
        d[col.name] = val
    return d


@router.get("", response_model=List[ContactOut])
def list_contacts(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Contact)
    if search:
        q = q.filter(Contact.nom.ilike(f"%{search}%"))
    contacts = q.order_by(Contact.usage_count.desc(), Contact.nom).all()
    return [_to_out(c) for c in contacts]


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: str, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(404, f"Contact {contact_id} introuvable")
    return _to_out(c)


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(data: ContactCreate, db: Session = Depends(get_db)):
    existing = db.query(Contact).filter(Contact.nom == data.nom).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    c = Contact(id=str(uuid4()), **data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: str, data: ContactUpdate,
                   db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(404, f"Contact {contact_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: str, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(404, f"Contact {contact_id} introuvable")
    db.delete(c)
    db.commit()
    return None
