import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

from app.lib.db.models import Trip, TripMemoryLogEntry

DB_PATH = Path(__file__).parents[3] / "data" / "travel_agent.db"


class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trips (
                    trip_id     TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    destinations TEXT NOT NULL,
                    start_date  TEXT,
                    end_date    TEXT,
                    notes       TEXT,
                    research_status TEXT NOT NULL DEFAULT 'not_started',
                    research_report TEXT,
                    research_report_ui TEXT,
                    research_error  TEXT,
                    created_at  TEXT NOT NULL,
                    research_updated_at TEXT,
                    research_started_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_log (
                    entry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id    TEXT NOT NULL REFERENCES trips(trip_id),
                    content    TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def create_trip(self, trip: Trip) -> Trip:
        trip = trip.model_copy(
            update={"created_at": trip.created_at or datetime.now(timezone.utc).isoformat()})
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trips (trip_id, name, destinations, start_date, end_date, notes, created_at, research_status, research_report, research_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (trip.trip_id, trip.name, json.dumps(trip.destinations), trip.start_date, trip.end_date, trip.notes, trip.created_at,
                 trip.research_status, trip.research_report, trip.research_error),
            )
        return trip

    def update_research_status(self, trip_id: str, status: str, report: str | None = None, error: str | None = None) -> Trip | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            if status == "running":
                conn.execute(
                    "UPDATE trips SET research_status = ?, research_report = ?, research_error = ?, research_started_at = ?, research_updated_at = ? WHERE trip_id = ?",
                    (status, report, error, now, now, trip_id),
                )
            else:
                conn.execute(
                    "UPDATE trips SET research_status = ?, research_report = ?, research_error = ?, research_updated_at = ? WHERE trip_id = ?",
                    (status, report, error, now, trip_id),
                )
        return self.get_trip(trip_id)

    def append_report_ui_sections(self, trip_id: str, sections: list[dict]) -> Trip | None:
        """Upserts a batch of A2UI section entries (each {question_id, surface_id, messages}) into
        research_report_ui, keyed by question_id. Takes the whole batch in one call — a single
        read-modify-write — rather than one call per section, since concurrent per-section writes to
        the same row would race (lost updates)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT research_report_ui FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
            existing = json.loads(row["research_report_ui"]) if row and row["research_report_ui"] else []
            by_question_id = {s["question_id"]: s for s in existing}
            for section in sections:
                by_question_id[section["question_id"]] = section
            conn.execute(
                "UPDATE trips SET research_report_ui = ? WHERE trip_id = ?",
                (json.dumps(list(by_question_id.values())), trip_id),
            )
        return self.get_trip(trip_id)

    def get_trip(self, trip_id: str) -> Trip | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_trip(row)

    def list_trips(self) -> list[Trip]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trips ORDER BY created_at DESC").fetchall()
        return [self._row_to_trip(r) for r in rows]

    def add_memory_entry(self, entry: TripMemoryLogEntry) -> TripMemoryLogEntry:
        created_at = entry.created_at or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO memory_log (trip_id, content, created_at) VALUES (?, ?, ?)",
                (entry.trip_id, entry.content, created_at),
            )
        return entry.model_copy(update={"entry_id": cursor.lastrowid, "created_at": created_at})

    def get_memory_entries(self, trip_id: str, limit: int = 20) -> list[TripMemoryLogEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memory_log WHERE trip_id = ? ORDER BY created_at DESC LIMIT ?",
                (trip_id, limit),
            ).fetchall()
        return [self._row_to_memory_entry(r) for r in reversed(rows)]

    def _row_to_trip(self, row: sqlite3.Row) -> Trip:
        return Trip(
            trip_id=row["trip_id"],
            name=row["name"],
            destinations=json.loads(row["destinations"]),
            start_date=row["start_date"],
            end_date=row["end_date"],
            notes=row["notes"],
            created_at=row["created_at"],
            research_status=row["research_status"],
            research_report=row["research_report"],
            research_report_ui=row["research_report_ui"],
            research_error=row["research_error"],
            research_updated_at=row["research_updated_at"],
            research_started_at=row["research_started_at"],
        )

    def _row_to_memory_entry(self, row: sqlite3.Row) -> TripMemoryLogEntry:
        return TripMemoryLogEntry(
            entry_id=row["entry_id"],
            trip_id=row["trip_id"],
            content=row["content"],
            created_at=row["created_at"],
        )
