"""Endpoints REST pour les contacts (signataires / demandeurs)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Contact

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=List[dict])
def list_contacts(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Contact)
    if search:
        q = q.filter(Contact.nom.ilike(f"%{search}%"))
    contacts = q.order_by(Contact.usage_count.desc(), Contact.nom).all()
    return [
        {"nom": c.nom, "email": c.email, "telephone": c.telephone}
        for c in contacts
    ]
