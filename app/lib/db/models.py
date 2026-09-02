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
    research_status: str = "not_started"  # not_started | running | done | failed
    research_report: Optional[str] = None
    research_report_ui: Optional[str] = None
    research_error: Optional[str] = None
    research_updated_at: Optional[str] = None
    research_started_at: Optional[str] = None


class TripMemoryLogEntry(BaseModel):
    trip_id: str
    entry_id: Optional[int] = None
    content: str
    created_at: Optional[str] = None
