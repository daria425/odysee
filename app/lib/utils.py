from pathlib import Path
import json
from app.lib.db.models import Trip


def load_prompt(path: str, **kwargs) -> str:
    text = Path(path).read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def load_profile() -> dict:
    path = Path(__file__).parents[2] / "data" / "user-profile.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_questions() -> dict:
    path = Path(__file__).parents[2] / "data" / "key_qs.json"
    return json.loads(path.read_text(encoding="utf-8"))


def parse_start_command(message: str, trip_id: str) -> Trip | None:
    """Parse '/start name | dest1, dest2 | date' — returns None if format is wrong."""
    body = message[len("/start"):].strip()
    parts = [p.strip() for p in body.split("|")]
    if len(parts) != 3:
        return None
    name, destinations_raw, date = parts
    destinations = [d.strip() for d in destinations_raw.split(",") if d.strip()]
    if not name or not destinations or not date:
        return None
    return Trip(trip_id=trip_id, name=name, destinations=destinations, start_date=date)
