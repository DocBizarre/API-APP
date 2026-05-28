"""Schémas Pydantic – Technicien."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
 
 
class TechnicienCreate(BaseModel):
    nom:        str
    email:      str = ""
    telephone:  str = ""
 
 
class TechnicienUpdate(BaseModel):
    nom:        Optional[str] = None
    email:      Optional[str] = None
    telephone:  Optional[str] = None
 
 
class TechnicienOut(BaseModel):
    id:         str
    nom:        str
    email:      str
    telephone:  str
    version:    int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
 
    model_config = {"from_attributes": True}