from pydantic import BaseModel
from typing import Optional


class Trip(BaseModel):
    trip_id: str
    name: str
    destinations: list[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class TripMemoryLogEntry(BaseModel):
    trip_id: str
    entry_id: Optional[int] = None
    content: str
    created_at: Optional[str] = None
